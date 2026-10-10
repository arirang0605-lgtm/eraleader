"""Red/green regression: locally claimed cash/split/dividend AMOUNTS.

Only synthetic data. Matching declared supplier values are NOT official payouts.
"""
from copy import deepcopy
from math import nan

import pytest

from eraleader.cash_exit_lineage import (
    STATUS_BLOCKED, STATUS_MATCH, audit_dual_vintage_cash_exit
)
from test_cash_exit_lineage import prepare, bundle, SOURCE, SEC, SIGNAL, EVALUATED


def examined(tmp_path, case=None, **opts):
    info, (cash, before, after) = prepare(tmp_path, case)
    return audit_dual_vintage_cash_exit(
        cash, before, after, security_id=info["price"]["bars"][0]["security_id"],
        market=info["identity"]["market"],
        decision_at=info["decision"], evaluated_at=info["evaluation"], **opts)


@pytest.mark.parametrize("kind,value,reason", [
    ("split_ratio", 3, "SPLIT_RATIO_CLAIM_MISMATCH"),
    ("split_ratio", True, "SPLIT_RATIO_CLAIM_MISMATCH"),
    ("split_ratio", nan, "SPLIT_RATIO_CLAIM_MISMATCH"),
    ("exit_cash", 54, "CASH_EXIT_AMOUNT_CLAIM_MISMATCH"),
    ("exit_cash", False, "CASH_EXIT_AMOUNT_CLAIM_MISMATCH"),
    ("exit_cash", nan, "CASH_EXIT_AMOUNT_CLAIM_MISMATCH"),
    ("exit_currency", "USD", "CASH_EXIT_CURRENCY_CLAIM_MISMATCH"),
    ("event_id", "WRONG-SPLIT-ID", "CORPORATE_ACTION_ID_MISMATCH"),
])
def test_supplied_inconsistent_action_or_exit_terms_never_pass(
        tmp_path, kind, value, reason):
    data = bundle()
    if kind == "split_ratio":
        data["known_action"]["ratio"] = value
    elif kind == "exit_cash":
        data["exit_action"]["cash_per_share"] = value
    elif kind == "exit_currency":
        data["exit_action"]["currency"] = value
    else:
        data["known_action"]["event_id"] = value
    got = examined(tmp_path, data)
    assert got["status"] == STATUS_BLOCKED
    assert got["cash_exit_total_return"] is None
    assert reason in got["blocking_reasons"]
    assert got["cash_payment_independently_verified"] is False


def test_cash_dividend_amount_different_but_same_date_and_event_is_blocked(tmp_path):
    data = bundle()
    data["price"]["bars"][-1]["close"] = 49
    data["price"]["actions"].append({
        "security_id": SEC, "action_id": "DIV-1", "action_type": "dividend",
        "effective_on": "2024-04-03", "known_at": "2024-03-27T09:00:00+09:00",
        "cash_amount": 1,
    })
    data["exit_action"]["cash_per_share"] = 55
    # Keep action dates/IDs identical while deliberately disputing the amount.
    data["known_action"] = None
    _, (cash, before, after) = prepare(tmp_path, data)
    import json
    reg = json.loads(after.read_text())
    reg["events"].append({
        "event_id": "DIV-1", "security_id": SEC, "action_type": "dividend",
        "effective_on": "2024-04-03", "source_id": SOURCE,
        "known_at": "2024-03-27T09:00:00+09:00", "cash_amount": 2,
    })
    reg["events"].append({
        "event_id": "SPLIT-1", "security_id": SEC, "action_type": "split",
        "effective_on": "2024-04-02", "source_id": SOURCE,
        "known_at": "2024-03-25T09:00:00+09:00", "ratio": 2,
    })
    after.write_text(json.dumps(reg))
    got = audit_dual_vintage_cash_exit(
        cash, before, after,
        security_id=SEC, market="KR", decision_at=SIGNAL, evaluated_at=EVALUATED,
    )
    assert got["status"] == STATUS_BLOCKED
    assert "DIVIDEND_CASH_CLAIM_MISMATCH" in got["blocking_reasons"]
    assert got["cash_exit_total_return"] is None


def test_optional_strict_amount_claims_missing_do_not_create_proven_return(tmp_path):
    got = examined(tmp_path, require_lineage_amount_claims=True)
    assert got["status"] == STATUS_BLOCKED
    assert got["cash_exit_total_return"] is None
    assert "MISSING_SPLIT_RATIO_CLAIM" in got["blocking_reasons"]
    assert "MISSING_CASH_EXIT_AMOUNT_CLAIM" in got["blocking_reasons"]
    assert got["lineage_amount_claims_required"] is True
    assert got["action_amounts_independently_verified"] is False


def test_strict_consistent_claims_still_research_only(tmp_path):
    data = bundle()
    data["known_action"]["ratio"] = 2
    data["exit_action"]["cash_per_share"] = 55
    data["exit_action"]["currency"] = "KRW"
    got = examined(tmp_path, data, require_lineage_amount_claims=True)
    assert got["status"] == STATUS_MATCH
    assert got["cash_exit_total_return"] == .1
    assert got["lineage_amount_claims_required"] is True
    assert got["action_amount_claims_matched"] == 2
    assert got["action_amounts_independently_verified"] is False
    assert got["historical_universe_pit_certified"] is False


def test_missing_action_amount_default_legacy_research_compatible(tmp_path):
    got = examined(tmp_path)
    assert got["status"] == STATUS_MATCH
    assert got["cash_exit_total_return"] == .1
    assert got["lineage_amount_claims_required"] is False



@pytest.mark.parametrize("field,claimed,reason", [
    ("paid_at", "2024-04-15T11:00:00+09:00",
     "CASH_EXIT_PAID_AT_CLAIM_MISMATCH"),
    ("cash_payment_confirmed", False,
     "CASH_EXIT_PAID_CONFIRMATION_CLAIM_MISMATCH"),
])
def test_voluntary_payout_receipt_claim_conflict_is_blocked(
        tmp_path, field, claimed, reason):
    data = bundle()
    data["exit_action"][field] = claimed
    got = examined(tmp_path, data)
    assert got["status"] == STATUS_BLOCKED
    assert reason in got["blocking_reasons"]
    assert got["cash_exit_total_return"] is None


def test_strict_us_dst_without_split_still_requires_cash_amount_and_currency(tmp_path):
    data = bundle(market="US")
    data["exit_action"]["cash_per_share"] = 105
    data["exit_action"]["currency"] = "USD"
    got = examined(tmp_path, data, require_lineage_amount_claims=True)
    assert got["status"] == STATUS_MATCH
    assert got["cash_exit_total_return"] == .05
    assert got["action_amount_claims_matched"] == 1
    assert got["cash_exit_currency_claim_matched"] is True
    assert got["issuer_identity_independently_verified"] is False


def test_strict_flag_cannot_be_non_boolean(tmp_path):
    with pytest.raises(ValueError, match="boolean"):
        examined(tmp_path, require_lineage_amount_claims="true")


def test_cli_strict_amount_mode_blocks_missing_and_accepts_complete_claims(
        tmp_path, capsys):
    from eraleader.cli import main as eraleader_main
    from test_cash_exit_lineage import prepare, SEC, SIGNAL, EVALUATED
    data, (cash, before, after) = prepare(tmp_path / "declared")
    args = [
        "audit-cash-delist", "--file", str(cash),
        "--decision-lineage", str(before),
        "--evaluation-lineage", str(after),
        "--security-id", SEC, "--market", "KR",
        "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
        "--require-lineage-amount-claims",
    ]
    eraleader_main([*args, "--out", str(tmp_path / "missing")])
    capsys.readouterr()
    import json
    rejected = json.loads(
        (tmp_path / "missing" / "cash_delisting_research.json").read_text()
    )
    assert rejected["status"] == STATUS_BLOCKED
    assert rejected["cash_exit_total_return"] is None
    assert "MISSING_SPLIT_RATIO_CLAIM" in rejected["blocking_reasons"]
    evaluation = json.loads(after.read_text())
    for ev in evaluation["events"]:
        if ev["action_type"] == "split":
            ev["ratio"] = 2
        elif ev["action_type"] == "cash_delist":
            ev["cash_per_share"] = 55
            ev["currency"] = "KRW"
    after.write_text(json.dumps(evaluation))
    eraleader_main([*args, "--out", str(tmp_path / "complete")])
    capsys.readouterr()
    accepted = json.loads(
        (tmp_path / "complete" / "cash_delisting_research.json").read_text()
    )
    assert accepted["status"] == STATUS_MATCH
    assert accepted["cash_exit_total_return"] == .1
    assert accepted["lineage_amount_claims_required"] is True
    assert accepted["action_amount_claims_matched"] == 2


def test_cli_strict_requires_both_lineage_files(tmp_path):
    from eraleader.cli import main as eraleader_main
    from test_cash_exit_lineage import prepare, SEC, SIGNAL, EVALUATED
    data, (cash, before, after) = prepare(tmp_path / "input")
    with pytest.raises(SystemExit) as err:
        eraleader_main([
            "audit-cash-delist", "--file", str(cash),
            "--security-id", SEC, "--market", "KR",
            "--decision-at", SIGNAL, "--evaluated-at", EVALUATED,
            "--require-lineage-amount-claims",
            "--out", str(tmp_path / "must-not-create"),
        ])
    assert err.value.code == 2
    assert not (tmp_path / "must-not-create" / "cash_delisting_research.json").exists()
