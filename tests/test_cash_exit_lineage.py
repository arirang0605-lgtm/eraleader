"""Synthetic dual-vintage cash exit PIT reconciliation. Never performance proof."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json

import pytest

from eraleader.cash_exit_lineage import (
    audit_dual_vintage_cash_exit, main, STATUS_BLOCKED, STATUS_MATCH,
)
from eraleader.issuer_lineage import SCHEMA
from test_delist_cash import bars, split, settlement, SEC, SIGNAL, EVALUATED

SOURCE = "SYN-ISSUER-VINTAGE"
IDENTITY = {
    "record_id": "LEGAL-ROW-1", "security_id": SEC, "ticker": "SYN",
    "market": "KR", "source_id": SOURCE, "valid_from": "2024-01-01",
    "valid_to": "2024-04-04", "known_at": "2024-03-01T09:00:00+09:00",
    "revision": 1,
}
SPLIT_EVENT = {
    "event_id": "SPLIT-1", "security_id": SEC, "action_type": "split",
    "source_id": SOURCE, "effective_on": "2024-04-02",
    "known_at": "2024-03-25T09:00:00+09:00",
}
EXIT_EVENT = {
    "event_id": "SYN-CASH-EXIT-1", "security_id": SEC,
    "action_type": "cash_delist", "source_id": SOURCE,
    "effective_on": "2024-04-04",
    "known_at": "2024-04-16T09:00:00+09:00",
}


def bundle(*, market="KR"):
    if market == "KR":
        return {
            "decision": SIGNAL, "evaluation": EVALUATED,
            "price": {
                "schema_version": "cash_delist_research_v1",
                "price_basis": "raw_unadjusted",
                "bars": bars(), "actions": split(), "settlement": settlement(),
            },
            "identity": dict(IDENTITY),
            "known_action": dict(SPLIT_EVENT),
            "exit_action": dict(EXIT_EVENT),
            "decision_retrieved": "2024-03-28T09:00:00+09:00",
            "eval_retrieved": "2024-04-20T09:00:00+09:00",
        }
    security = "US-DST-CASH"
    z = {
        "schema_version": "cash_delist_research_v1", "price_basis": "raw_unadjusted",
        "bars": [
            {"security_id": security, "session": day, "close": 100,
             "tradable": True, "available_at": stamp}
            for day, stamp in [
                ("2024-03-07", "2024-03-07T17:00:00-05:00"),
                ("2024-03-08", "2024-03-08T17:00:00-05:00"),
                ("2024-03-11", "2024-03-11T17:00:00-04:00"),
            ]
        ], "actions": [],
        "settlement": {
            "security_id": security, "source_id": "UNVERIFIED-US-PAYMENT",
            "event_id": "USD-EXIT", "action_type": "cash_delist",
            "last_trading_on": "2024-03-11", "effective_on": "2024-03-12",
            "cash_per_share": 105, "currency": "USD",
            "provenance": "synthetic_fixture",
            "announced_at": "2024-03-06T09:00:00-05:00",
            "paid_at": "2024-03-20T10:00:00-04:00",
            "available_at": "2024-03-21T09:00:00-04:00",
            "cash_payment_confirmed": True,
        },
    }
    identity = {
        "record_id": "US-ROW-1", "security_id": security,
        "ticker": "USDST", "market": "US", "source_id": SOURCE,
        "valid_from": "2024-01-01", "valid_to": "2024-03-12",
        "known_at": "2024-03-01T10:00:00-05:00", "revision": 1,
    }
    action = {
        "event_id": "USD-EXIT", "security_id": security,
        "action_type": "cash_delist", "source_id": SOURCE,
        "effective_on": "2024-03-12",
        "known_at": "2024-03-21T09:00:00-04:00",
    }
    return {
        "decision": "2024-03-07T18:00:00-05:00",
        "evaluation": "2024-04-01T18:00:00-04:00",
        "price": z, "identity": identity, "known_action": None,
        "exit_action": action,
        "decision_retrieved": "2024-03-06T10:00:00-05:00",
        "eval_retrieved": "2024-03-22T11:00:00-04:00",
    }


def prepare(tmp_path: Path, data=None):
    scenario = deepcopy(data if data is not None else bundle())
    root = tmp_path
    root.mkdir(exist_ok=True, parents=True)
    def registry(received, events):
        return {
            "schema_version": SCHEMA, "market": scenario["identity"]["market"],
            "source_id": SOURCE, "publisher_id_claimed": "SYNTHETIC_ONLY",
            "retrieved_at": received,
            "identities": [scenario["identity"]],
            "events": events, "observed_tickers": [],
        }
    old_events = [scenario["known_action"]] if scenario["known_action"] else []
    new_events = old_events + [scenario["exit_action"]]
    files = []
    for name, body in [
        ("cash.json", scenario["price"]),
        ("decision_lineage.json", registry(scenario["decision_retrieved"], old_events)),
        ("eval_lineage.json", registry(scenario["eval_retrieved"], new_events)),
    ]:
        p = root / name
        p.write_text(json.dumps(body), encoding="utf-8")
        files.append(p)
    return scenario, files


def audit(tmp_path, data=None):
    scenario, (cash, before, after) = prepare(tmp_path, data)
    return audit_dual_vintage_cash_exit(
        cash, before, after,
        security_id=scenario["price"]["bars"][0]["security_id"],
        market=scenario["identity"]["market"],
        decision_at=scenario["decision"],
        evaluated_at=scenario["evaluation"],
    )


def test_split_before_cash_exit_matches_two_vintages_but_does_not_certify(tmp_path):
    report = audit(tmp_path)
    assert report["status"] == STATUS_MATCH
    assert report["cash_exit_total_return"] == 0.1
    assert report["raw_price_actions_matched_by_type_and_day"] == 1
    assert report["terminal_cash_event_matched_by_id_type_and_date"] is True
    assert report["decision_issuer_declared_asof"] is True
    assert report["blocking_count"] == 0
    assert all(report[key] is False for key in [
        "historical_universe_pit_certified",
        "issuer_identity_independently_verified",
        "cash_payment_independently_verified",
        "action_amounts_independently_verified",
        "price_sessions_completeness_verified",
        "real_leader_prediction_certified",
    ])


def test_us_dst_retrieval_and_cash_exit_are_local_clock_safe(tmp_path):
    report = audit(tmp_path, bundle(market="US"))
    assert report["market"] == "US"
    assert report["status"] == STATUS_MATCH
    assert report["cash_exit_total_return"] == 0.05
    assert report["raw_price_actions_matched_by_type_and_day"] == 0


@pytest.mark.parametrize("mutate,reason", [
    (lambda x: x.update(decision_retrieved="2024-04-17T09:00:00+09:00"),
     "DECISION_IDENTITY_RETRIEVED_TOO_LATE"),
    (lambda x: x.update(eval_retrieved="2024-06-02T09:00:00+09:00"),
     "EXIT_IDENTITY_RETRIEVED_TOO_LATE"),
    (lambda x: x["exit_action"].update(event_id="WRONG-EXIT"),
     "MISSING_OR_CONFLICTING_EXIT_EVENT"),
    (lambda x: x["exit_action"].update(effective_on="2024-04-05"),
     "MISSING_OR_CONFLICTING_EXIT_EVENT"),
    (lambda x: x["exit_action"].update(action_type="merger"),
     "MISSING_OR_CONFLICTING_EXIT_EVENT"),
    (lambda x: x["identity"].update(security_id="OTHER-PERMANENT-ID"),
     "MISSING_OR_AMBIGUOUS_DECISION_ISSUER"),
    (lambda x: x["identity"].update(valid_to="2024-04-02"),
     "MISSING_OR_AMBIGUOUS_FINAL_ISSUER"),
    (lambda x: x.update(known_action=None),
     "RAW_PRICE_ACTION_NOT_IN_ISSUER_VINTAGE"),
])
def test_inconsistent_sources_never_produce_an_uncertified_payoff(
        tmp_path, mutate, reason):
    b = bundle()
    mutate(b)
    result = audit(tmp_path, b)
    assert result["status"] == STATUS_BLOCKED
    assert reason in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None
    assert result["historical_universe_pit_certified"] is False


def test_missing_payment_is_censored_without_dummy_zero(tmp_path):
    b = bundle()
    b["price"]["settlement"] = None
    result = audit(tmp_path, b)
    assert result["status"] == STATUS_BLOCKED
    assert result["cash_exit_total_return"] is None
    assert "MISSING_CASH_SETTLEMENT" in result["blocking_reasons"]


def test_unpaid_settlement_is_censored(tmp_path):
    b = bundle()
    b["price"]["settlement"]["cash_payment_confirmed"] = False
    result = audit(tmp_path, b)
    assert "CASH_PAYMENT_NOT_OBSERVED_BY_EVALUATION" in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None


def test_declared_extra_dividend_without_raw_action_blocks_return(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    registry = json.loads(new.read_text())
    registry["events"].append({
        "event_id": "DIV-EXTRA", "security_id": SEC,
        "action_type": "dividend", "effective_on": "2024-04-03",
        "source_id": SOURCE, "known_at": "2024-03-26T09:00:00+09:00",
    })
    new.write_text(json.dumps(registry))
    r = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "ISSUER_ACTION_NOT_IN_RAW_PRICE_PATH" in r["blocking_reasons"]
    assert r["cash_exit_total_return"] is None


def test_conflicting_prior_merger_blocks_paid_cash_return(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    registry = json.loads(new.read_text())
    registry["events"].append({
        "event_id": "MERGER-CONFLICT", "security_id": SEC,
        "action_type": "merger", "effective_on": "2024-04-03",
        "source_id": SOURCE, "known_at": "2024-03-28T09:00:00+09:00",
    })
    new.write_text(json.dumps(registry))
    r = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "CONFLICTING_NONCASH_OR_DUPLICATE_EXIT" in r["blocking_reasons"]
    assert r["cash_exit_total_return"] is None


def test_same_vintage_cannot_corroborate_itself(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    r = audit_dual_vintage_cash_exit(
        cash, old, old, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "SAME_DECLARED_VINTAGE_REUSED" in r["blocking_reasons"]
    assert r["cash_exit_total_return"] is None


def test_ticker_reuse_concurrent_issuer_does_not_change_permanent_id(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    decision = json.loads(old.read_text())
    other = deepcopy(IDENTITY)
    other.update(record_id="UNRELATED", security_id="NEW-ISSUER")
    decision["identities"].append(other)
    old.write_text(json.dumps(decision))
    r = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "AMBIGUOUS_DECISION_TICKER" in r["blocking_reasons"]
    assert r["cash_exit_total_return"] is None


def test_revision_first_known_after_decision_cannot_be_backdated(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    decision = json.loads(old.read_text())
    decision["retrieved_at"] = "2024-04-15T09:00:00+09:00"
    revised = deepcopy(decision["identities"][0])
    revised["revision"] = 2
    revised["known_at"] = "2024-04-10T09:00:00+09:00"
    revised["ticker"] = "NEW-SYN"
    decision["identities"].append(revised)
    old.write_text(json.dumps(decision))
    r = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "DECISION_IDENTITY_RETRIEVED_TOO_LATE" in r["blocking_reasons"]
    assert r["cash_exit_total_return"] is None


def test_invalid_cross_market_or_unadjusted_basis_fails_closed(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    with pytest.raises(ValueError, match="market"):
        audit_dual_vintage_cash_exit(cash, old, new, security_id=SEC,
                                     market="US", decision_at=SIGNAL, evaluated_at=EVALUATED)
    payload = json.loads(cash.read_text())
    payload["price_basis"] = "adjusted"
    cash.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="raw unadjusted"):
        audit_dual_vintage_cash_exit(cash, old, new, security_id=SEC,
                                     market="KR", decision_at=SIGNAL, evaluated_at=EVALUATED)


def test_source_symlink_refused_before_any_report(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    moved = tmp_path/"actual_source.json"
    new.rename(moved)
    new.symlink_to(moved)
    with pytest.raises(ValueError, match="symlinked"):
        audit_dual_vintage_cash_exit(cash, old, new, security_id=SEC,
                                     market="KR", decision_at=SIGNAL, evaluated_at=EVALUATED)


def test_cli_synthetic_cash_exit_writes_new_research_only_result(tmp_path, capsys):
    b, (cash, old, new) = prepare(tmp_path)
    report_file = tmp_path/"results"/"dual_vintage_cash_exit.json"
    args = [
        "--cash-file", str(cash), "--decision-lineage", str(old),
        "--evaluation-lineage", str(new), "--security-id", SEC, "--market", "KR",
        "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
        "--out", str(report_file),
    ]
    assert main(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["cash_exit_total_return"] == 0.1
    saved = json.loads(report_file.read_text())
    assert saved["status"] == STATUS_MATCH
    assert saved["historical_universe_pit_certified"] is False
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert saved == json.loads(report_file.read_text())

def test_existing_eraleader_cli_optional_dual_vintage_gate(tmp_path, capsys):
    from eraleader.cli import main as eraleader_main
    b, (cash, old, new) = prepare(tmp_path/"inputs")
    args = [
        "audit-cash-delist", "--file", str(cash),
        "--security-id", SEC, "--market", "KR",
        "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
        "--decision-lineage", str(old), "--evaluation-lineage", str(new),
        "--out", str(tmp_path/"derived"),
    ]
    eraleader_main(args)
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == STATUS_MATCH
    assert printed["cash_exit_total_return"] == 0.1
    saved = json.loads((tmp_path/"derived"/"cash_delisting_research.json").read_text())
    assert saved["blocking_count"] == 0
    assert saved["historical_universe_pit_certified"] is False


def test_cli_does_not_publish_partial_vintage_submission(tmp_path):
    from eraleader.cli import main as eraleader_main
    b, (cash, old, new) = prepare(tmp_path/"inputs")
    with pytest.raises(SystemExit) as error:
        eraleader_main([
            "audit-cash-delist", "--file", str(cash),
            "--security-id", SEC, "--market", "KR",
            "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
            "--decision-lineage", str(old), "--out", str(tmp_path/"derived"),
        ])
    assert error.value.code == 2
    assert not (tmp_path/"derived"/"cash_delisting_research.json").exists()


def test_cli_blocked_vintage_must_emit_null_payoff(tmp_path, capsys):
    from eraleader.cli import main as eraleader_main
    b, (cash, old, new) = prepare(tmp_path/"inputs")
    evaluation = json.loads(new.read_text())
    evaluation["events"] = [x for x in evaluation["events"] if x["action_type"] != "cash_delist"]
    new.write_text(json.dumps(evaluation))
    eraleader_main([
        "audit-cash-delist", "--file", str(cash),
        "--security-id", SEC, "--market", "KR",
        "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
        "--decision-lineage", str(old), "--evaluation-lineage", str(new),
        "--out", str(tmp_path/"derived"),
    ])
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == STATUS_BLOCKED
    assert printed["cash_exit_total_return"] is None
    raw = json.loads((tmp_path/"derived"/"cash_delisting_research.json").read_text())
    assert "MISSING_OR_CONFLICTING_EXIT_EVENT" in raw["blocking_reasons"]
    assert raw["historical_universe_pit_certified"] is False


@pytest.mark.parametrize("field,value,reason", [
    ("record_id", "MIGRATED-ROW-NEW", "ISSUER_RECORD_LINEAGE_BREAK"),
    ("valid_from", "2024-01-15", "ISSUER_ORIGINAL_VALID_FROM_REWRITTEN"),
])
def test_rewritten_permanent_identity_between_vintages_cannot_pass(
        tmp_path, field, value, reason):
    b, (cash, old, new) = prepare(tmp_path)
    data = json.loads(new.read_text())
    data["identities"][0][field] = value
    new.write_text(json.dumps(data))
    report = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert reason in report["blocking_reasons"]
    assert report["cash_exit_total_return"] is None


def test_claimed_issuer_provider_switch_cannot_create_a_false_vintage_pair(tmp_path):
    b, (cash, old, new) = prepare(tmp_path)
    data = json.loads(new.read_text())
    data["publisher_id_claimed"] = "SOME_OTHER_SELF_DECLARED_SOURCE"
    new.write_text(json.dumps(data))
    report = audit_dual_vintage_cash_exit(
        cash, old, new, security_id=SEC, market="KR",
        decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert "ISSUER_VINTAGE_SOURCE_CHANGED" in report["blocking_reasons"]
    assert report["historical_universe_pit_certified"] is False
    assert report["cash_exit_total_return"] is None
