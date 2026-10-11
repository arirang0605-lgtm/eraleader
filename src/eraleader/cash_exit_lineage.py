"""Cross-check two declared as-of issuer vintages against a cash exit (research only).

Both registries and the settlement are local self-reported data. No proof of
historical completeness, issuer authenticity, cash receipt or tradable returns.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, date
from hashlib import sha256
import json
import os
from pathlib import Path

from .delist_cash import reconstruct_cash_delisting, MARKET_ZONE
from .cash_payment_receipts import audit_declared_cash_payment_receipt
from .issuer_lineage import audit_issuer_lineage, SCHEMA as LINEAGE_SCHEMA
from .issuer_lineage import _timestamp, _date

STATUS_MATCH = "LOCAL_DUAL_VINTAGE_CASH_EXIT_RESEARCH_NOT_CERTIFIED"
STATUS_BLOCKED = "CENSORED_UNCORROBORATED_CASH_EXIT"
MAX_BYTES = 5_000_000


def _same_claim_amount(claim: object, price_amount: object, *, positive: bool) -> bool:
    """Exact decimal comparison of two declared numbers, not provider proof."""
    if isinstance(claim, bool) or isinstance(price_amount, bool):
        return False
    try:
        asserted = Decimal(str(claim))
        original = Decimal(str(price_amount))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if not asserted.is_finite() or not original.is_finite():
        return False
    minimum_ok = asserted > 0 if positive else asserted >= 0
    return minimum_ok and asserted == original


def _read(path: Path) -> tuple[dict, str]:
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise ValueError("Missing, symlinked or oversized local PIT source")
    raw = p.read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Empty or oversized local PIT source")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid local PIT JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("Local PIT source must be a JSON object")
    return obj, sha256(raw).hexdigest()


def _latest_visible(bundle: dict, cutoff: datetime, session_day: date) -> list[dict]:
    """Keep newest revision KNOWN by cutoff, then interpret its date interval."""
    selected: dict[str, dict] = {}
    for row in bundle["identities"]:
        if _timestamp(row["known_at"]) > cutoff:
            continue
        key = row["record_id"]
        if key not in selected or row["revision"] > selected[key]["revision"]:
            selected[key] = row
    return [
        row for row in selected.values()
        if _date(row["valid_from"]) <= session_day
        and (not row.get("valid_to") or session_day < _date(row["valid_to"]))
    ]


def _known_events(bundle: dict, cutoff: datetime) -> list[dict]:
    return [row for row in bundle["events"] if _timestamp(row["known_at"]) <= cutoff]


def audit_dual_vintage_cash_exit(
    cash_file: Path, decision_lineage_file: Path, evaluation_lineage_file: Path,
    *, security_id: str, market: str, decision_at: str, evaluated_at: str,
    require_lineage_amount_claims: bool = False,
    settlement_receipt_file: Path | None = None,
    require_settlement_receipt: bool = False,
) -> dict:
    """Fail closed if the as-of issuer, terminal event or action path disagree.

    Results never constitute an independent issuer, PIT, settlement or return
    certificate, even when all locally declared vintages reconcile.
    """
    if market not in MARKET_ZONE or not isinstance(security_id, str) or not security_id.strip():
        raise ValueError("KR/US and a permanent security ID are required")
    if type(require_lineage_amount_claims) is not bool:
        raise ValueError("Strict amount-claim flag must be a boolean")
    if type(require_settlement_receipt) is not bool:
        raise ValueError("Require-settlement-receipt flag must be boolean")
    decision = _timestamp(decision_at)
    evaluation = _timestamp(evaluated_at)
    if evaluation < decision:
        raise ValueError("Evaluation precedes decision")
    cash, cash_hash = _read(cash_file)
    before, before_hash = _read(decision_lineage_file)
    after, after_hash = _read(evaluation_lineage_file)
    if cash.get("schema_version") != "cash_delist_research_v1" or cash.get("price_basis") != "raw_unadjusted":
        raise ValueError("Cash-exit input requires raw unadjusted research schema")
    for registry in (before, after):
        if registry.get("schema_version") != LINEAGE_SCHEMA or registry.get("market") != market:
            raise ValueError("Issuer vintage schema/market mismatch")
        if registry.get("source_id") is None or not isinstance(registry.get("identities"), list):
            raise ValueError("Invalid issuer vintage")
    decision_audit = audit_issuer_lineage(Path(decision_lineage_file), decision_at=decision_at)
    evaluation_audit = audit_issuer_lineage(Path(evaluation_lineage_file), decision_at=evaluated_at)
    calc = reconstruct_cash_delisting(
        cash["bars"], cash["actions"], cash.get("settlement"),
        security_id=security_id, market=market,
        decision_at=decision_at, evaluated_at=evaluated_at,
        price_basis=cash["price_basis"],
    )
    reasons: set[str] = set()
    if before_hash == after_hash:
        reasons.add("SAME_DECLARED_VINTAGE_REUSED")
    if (before["source_id"] != after["source_id"] or
            before["publisher_id_claimed"] != after["publisher_id_claimed"]):
        reasons.add("ISSUER_VINTAGE_SOURCE_CHANGED")
    decision_received = _timestamp(before["retrieved_at"])
    evaluation_received = _timestamp(after["retrieved_at"])
    if decision_received > decision:
        reasons.add("DECISION_IDENTITY_RETRIEVED_TOO_LATE")
    if evaluation_received > evaluation:
        reasons.add("EXIT_IDENTITY_RETRIEVED_TOO_LATE")
    if evaluation_received <= decision_received:
        reasons.add("EVALUATION_VINTAGE_NOT_LATER")
    if decision_audit["active_ticker_conflict_count"]:
        reasons.add("AMBIGUOUS_DECISION_TICKER")
    if evaluation_audit["corporate_events_with_unknown_parent_count"]:
        reasons.add("UNKNOWN_EVENT_PARENT_IN_EVALUATION_SOURCE")
    zone = MARKET_ZONE[market]
    decision_day = decision.astimezone(zone).date()
    possible = _latest_visible(before, decision, decision_day)
    matched_decision = [r for r in possible if r["security_id"] == security_id]
    if len(matched_decision) != 1:
        reasons.add("MISSING_OR_AMBIGUOUS_DECISION_ISSUER")
    decision_ticker = matched_decision[0]["ticker"] if len(matched_decision) == 1 else None
    if decision_ticker is not None and any(
        row["ticker"] == decision_ticker and row["security_id"] != security_id
        for row in possible
    ):
        reasons.add("DECISION_TICKER_REUSED_CONCURRENTLY")
    if any(e["security_id"] == security_id and e["action_type"] in
           ("merger", "delist", "cash_delist") and _date(e["effective_on"]) <= decision_day
           for e in _known_events(before, decision)):
        reasons.add("ISSUER_ALREADY_EXITED_BY_DECISION")
    terms = cash.get("settlement")
    matched_exit = False
    matched_actions = 0
    amount_claims_matched = 0
    cash_event_currency_claim_matched = False
    if not isinstance(terms, dict):
        reasons.add("MISSING_CASH_SETTLEMENT")
    elif calc["cash_exit_total_return"] is None:
        reasons.add("CASH_PAYMENT_NOT_OBSERVED_BY_EVALUATION")
    else:
        last_trade = _date(terms["last_trading_on"])
        final_day = _date(terms["effective_on"])
        last_rows = _latest_visible(after, evaluation, last_trade)
        last_matched = [r for r in last_rows if r["security_id"] == security_id]
        if len(last_matched) != 1:
            reasons.add("MISSING_OR_AMBIGUOUS_FINAL_ISSUER")
        if len(matched_decision) == 1 and len(last_matched) == 1:
            if matched_decision[0]["record_id"] != last_matched[0]["record_id"]:
                reasons.add("ISSUER_RECORD_LINEAGE_BREAK")
            if matched_decision[0]["valid_from"] != last_matched[0]["valid_from"]:
                reasons.add("ISSUER_ORIGINAL_VALID_FROM_REWRITTEN")
        if decision_ticker and any(
            r["ticker"] == decision_ticker and r["security_id"] != security_id
            for r in last_rows
        ):
            reasons.add("PERMANENT_ID_CHANGED_ON_TICKER_REUSE")
        known = _known_events(after, evaluation)
        exits = [e for e in known
                 if e["security_id"] == security_id and e["event_id"] == terms["event_id"]]
        matched_exit = (len(exits) == 1 and
                        exits[0]["action_type"] == "cash_delist" and
                        _date(exits[0]["effective_on"]) == final_day)
        if not matched_exit:
            reasons.add("MISSING_OR_CONFLICTING_EXIT_EVENT")
        else:
            exit_event = exits[0]
            # Explicit contradictions are unsafe even in legacy research
            # mode. Missing amount claims become blockers only in opt-in
            # strict mode (older offline issuer snapshots lack these keys).
            if "cash_per_share" not in exit_event:
                if require_lineage_amount_claims:
                    reasons.add("MISSING_CASH_EXIT_AMOUNT_CLAIM")
            elif not _same_claim_amount(exit_event["cash_per_share"],
                                        terms["cash_per_share"], positive=True):
                reasons.add("CASH_EXIT_AMOUNT_CLAIM_MISMATCH")
            else:
                amount_claims_matched += 1
            if "currency" not in exit_event:
                if require_lineage_amount_claims:
                    reasons.add("MISSING_CASH_EXIT_CURRENCY_CLAIM")
            elif exit_event["currency"] != terms["currency"]:
                reasons.add("CASH_EXIT_CURRENCY_CLAIM_MISMATCH")
            else:
                cash_event_currency_claim_matched = True
            if "paid_at" in exit_event:
                if _timestamp(exit_event["paid_at"]) != _timestamp(terms["paid_at"]):
                    reasons.add("CASH_EXIT_PAID_AT_CLAIM_MISMATCH")
            if "cash_payment_confirmed" in exit_event:
                if exit_event["cash_payment_confirmed"] is not True:
                    reasons.add("CASH_EXIT_PAID_CONFIRMATION_CLAIM_MISMATCH")
        if any(e["security_id"] == security_id and e["action_type"] in
               ("cash_delist", "delist", "merger") and e["event_id"] != terms["event_id"]
               and _date(e["effective_on"]) <= final_day
               for e in known):
            reasons.add("CONFLICTING_NONCASH_OR_DUPLICATE_EXIT")

        start_trade = _date(cash["bars"][0]["session"])
        price_actions = {
            (action["action_type"], action["effective_on"])
            for action in cash["actions"]
            if start_trade < _date(action["effective_on"]) <= last_trade
        }
        visible_actions = [
            e for e in known if e["security_id"] == security_id
            and e["action_type"] in ("split", "dividend")
            and start_trade < _date(e["effective_on"]) <= last_trade
        ]
        registry_actions = {
            (action["action_type"], action["effective_on"]) for action in visible_actions
        }
        if len(registry_actions) != len(visible_actions):
            reasons.add("AMBIGUOUS_DECLARED_ACTIONS")
        if price_actions - registry_actions:
            reasons.add("RAW_PRICE_ACTION_NOT_IN_ISSUER_VINTAGE")
        if registry_actions - price_actions:
            reasons.add("ISSUER_ACTION_NOT_IN_RAW_PRICE_PATH")
        matched_actions = len(price_actions & registry_actions)
        price_action_map = {
            (event["action_type"], event["effective_on"]): event
            for event in cash["actions"]
            if start_trade < _date(event["effective_on"]) <= last_trade
        }
        source_action_map = {
            (event["action_type"], event["effective_on"]): event
            for event in visible_actions
        }
        for key in sorted(price_actions & registry_actions):
            raw_action = price_action_map[key]
            source_action = source_action_map[key]
            if raw_action["action_id"] != source_action["event_id"]:
                reasons.add("CORPORATE_ACTION_ID_MISMATCH")
            amount_key = "ratio" if key[0] == "split" else "cash_amount"
            if amount_key not in source_action:
                if require_lineage_amount_claims:
                    reasons.add("MISSING_SPLIT_RATIO_CLAIM" if key[0] == "split"
                                else "MISSING_DIVIDEND_CASH_CLAIM")
            elif not _same_claim_amount(
                source_action[amount_key], raw_action[amount_key],
                positive=key[0] == "split",
            ):
                reasons.add("SPLIT_RATIO_CLAIM_MISMATCH" if key[0] == "split"
                            else "DIVIDEND_CASH_CLAIM_MISMATCH")
            else:
                amount_claims_matched += 1

    receipt_audit = None
    if settlement_receipt_file is None:
        if require_settlement_receipt:
            reasons.add("CASH_PAYMENT_RECEIPT_NOT_PROVIDED")
    elif not isinstance(terms, dict):
        reasons.add("CASH_PAYMENT_RECEIPT_CANNOT_REPLACE_MISSING_SETTLEMENT")
    else:
        receipt_audit = audit_declared_cash_payment_receipt(
            Path(settlement_receipt_file), terms, security_id=security_id,
            market=market, evaluated_at=evaluated_at,
            issuer_source_id=after["source_id"],
            issuer_publisher_id_claimed=after["publisher_id_claimed"],
        )
        reasons.update(receipt_audit["blockers"])
    # Fail closed on revisions while issuer, settlement and payout files are
    # being compared. First-pass source hashes alone could otherwise certify
    # a now-modified set of local research inputs on report publication.
    for source_file, first_hash in (
        (cash_file, cash_hash),
        (decision_lineage_file, before_hash),
        (evaluation_lineage_file, after_hash),
    ):
        _, second_hash = _read(Path(source_file))
        if second_hash != first_hash:
            raise ValueError("Original cash/issuer research source revised during audit")
    if receipt_audit is not None:
        refreshed_receipt = audit_declared_cash_payment_receipt(
            Path(settlement_receipt_file), terms, security_id=security_id,
            market=market, evaluated_at=evaluated_at,
            issuer_source_id=after["source_id"],
            issuer_publisher_id_claimed=after["publisher_id_claimed"],
        )
        if refreshed_receipt != receipt_audit:
            raise ValueError("Cash payment document or receipt revised during audit")
    blocks = sorted(reasons)
    status = STATUS_BLOCKED if blocks else STATUS_MATCH
    return {
        "status": status,
        "market": market,
        "security_id": security_id,
        "decision_at_utc": decision.isoformat(),
        "evaluated_at_utc": evaluation.isoformat(),
        "cash_source_sha256": cash_hash,
        "decision_issuer_vintage_sha256": before_hash,
        "evaluation_issuer_vintage_sha256": after_hash,
        "decision_lineage_source_id_claimed": before["source_id"],
        "evaluation_lineage_source_id_claimed": after["source_id"],
        "declared_publishers_differ": (
            before["publisher_id_claimed"] != after["publisher_id_claimed"]
        ),
        "decision_issuer_declared_asof": (
            len(matched_decision) == 1 and decision_received <= decision
            and "ISSUER_ALREADY_EXITED_BY_DECISION" not in reasons
        ),
        "terminal_cash_event_matched_by_id_type_and_date": matched_exit,
        "raw_price_actions_matched_by_type_and_day": matched_actions,
        "lineage_amount_claims_required": require_lineage_amount_claims,
        "action_amount_claims_matched": amount_claims_matched,
        "cash_exit_currency_claim_matched": cash_event_currency_claim_matched,
        "local_cash_exit_input_status": calc["status"],
        "settlement_receipt_required": require_settlement_receipt,
        "settlement_receipt_supplied": settlement_receipt_file is not None,
        "settlement_receipt_manifest_sha256": (
            receipt_audit["receipt_manifest_sha256"] if receipt_audit else None
        ),
        "settlement_receipt_claims_consistent": (
            receipt_audit["receipt_claims_consistent"] if receipt_audit else False
        ),
        "settlement_receipt_independently_authenticated": False,
        "cash_exit_total_return": (
            calc["cash_exit_total_return"] if not blocks else None
        ),
        "blocking_reasons": blocks,
        "blocking_count": len(blocks),
        "historical_universe_pit_certified": False,
        "issuer_identity_independently_verified": False,
        "cash_payment_independently_verified": False,
        "action_amounts_independently_verified": False,
        "price_sessions_completeness_verified": False,
        "real_leader_prediction_certified": False,
        "warning": (
            "A local dual-vintage crosscheck can detect contradictory issuer IDs, "
            "unobserved split/dividend events and unsupported exits, but cannot "
            "attest original provider timestamps, omitted events or legal cash proceeds."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Research-only dual as-of issuer/terminal cash-exit reconciliation"
    )
    parser.add_argument("--cash-file", type=Path, required=True)
    parser.add_argument("--decision-lineage", type=Path, required=True)
    parser.add_argument("--evaluation-lineage", type=Path, required=True)
    parser.add_argument("--security-id", required=True)
    parser.add_argument("--market", choices=("KR", "US"), required=True)
    parser.add_argument("--decision-at", required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--require-lineage-amount-claims", action="store_true",
                        help="Require explicit split/dividend and cash payout amounts in issuer events")
    parser.add_argument("--settlement-receipt", type=Path,
                        help="Local manifest and normalized cash-payment JSON; no authenticity certification")
    parser.add_argument("--require-settlement-receipt", action="store_true",
                        help="Censor a missing cash-payment evidence manifest")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_dual_vintage_cash_exit(
            args.cash_file, args.decision_lineage, args.evaluation_lineage,
            security_id=args.security_id, market=args.market,
            decision_at=args.decision_at, evaluated_at=args.evaluated_at,
            require_lineage_amount_claims=args.require_lineage_amount_claims,
            settlement_receipt_file=args.settlement_receipt,
            require_settlement_receipt=args.require_settlement_receipt,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(args.out, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"EraLeader cash exit evidence ERROR: {exc}\n")
    print(json.dumps({
        "status": report["status"],
        "blocking_count": report["blocking_count"],
        "cash_exit_total_return": report["cash_exit_total_return"],
        "historical_universe_pit_certified": False,
        "out": str(args.out),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
