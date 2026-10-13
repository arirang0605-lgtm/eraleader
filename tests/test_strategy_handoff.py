"""EraLeader -> downstream strategy handoff: real research and selected state."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader import strategy_handoff as feed
from eraleader.state_history import StateHistory
from test_official_company_explorer import source as research_source

NOW = datetime(2026,10,14,12,0,tzinfo=timezone.utc)
HIGH = {"industry":18,"competitiveness":18,"earnings":23,
        "momentum":23,"flow":8}
WEAK = {"industry":9,"competitiveness":10,"earnings":10,
        "momentum":12,"flow":5}
EVIDENCE = {"financial_pit":True,"historic_universe_pit":True,
            "corporate_actions_pit":True,"fundamental_growth":True,
            "confirmed_weekly_trend":True}


def selected(sec="005930", components=None, evidence=None):
    return {"security_id":sec,"components":components if components is not None else HIGH,
            "evidence":evidence if evidence is not None else EVIDENCE}


def ledger(tmp_path, market="KR", sec="005930", transitions=2):
    path = tmp_path / "states.sqlite"
    tracked = StateHistory(path)
    try:
        tracked.record(market,"2026-10-12",[selected(sec)])
        if transitions >= 2:
            tracked.record(market,"2026-10-13",[selected(sec)])
        if transitions >= 3:
            tracked.record(market,"2026-10-14",[selected(sec,components=WEAK)])
    finally:
        tracked.close()
    return path


def export_state(path, *, at="2026-10-13", market="KR", now=NOW):
    return feed.state_history_handoff(path,market=market,as_of=at,clock=now)


def test_real_like_research_candidates_observation_only(tmp_path):
    src = research_source(tmp_path)
    payload = feed.research_cohort_handoff(
        src,request_day="2026-10-14",clock=NOW)
    assert payload["market"] == "KR"
    assert payload["watchlist_count"] == 3
    assert payload["selection_count"] == 0
    assert payload["status"] == "WATCHLIST_ONLY_NO_VERIFIED_LEADER_SELECTION"
    assert payload["source_observed_as_of"] == "2026-10-08"
    assert {r["security_id"] for r in payload["research_watchlist"]} == {
        "005930","000660","035420"}
    assert all(r["selection_state"] == "WATCH" and
               r["score_100"] is None for r in payload["research_watchlist"])
    assert not payload["execution_authority"] and not payload["order_instruction"]
    assert not payload["selected_candidates"]


def test_research_delivery_replay_same_evidence_is_idempotent(tmp_path):
    cohort = research_source(tmp_path)
    original = feed.research_cohort_handoff(cohort,request_day="2026-10-14",clock=NOW)
    out = tmp_path / "consumer" / "kr_research.json"
    out.parent.mkdir()
    first = feed.publish_handoff(original,out)
    assert first["status"] == "DELIVERED_TO_INBOX"
    raw = out.read_bytes()
    second = feed.research_cohort_handoff(
        cohort,request_day="2026-10-14",clock=NOW + timedelta(minutes=35))
    assert feed.publish_handoff(second,out)["status"] == "ALREADY_DELIVERED"
    assert out.read_bytes() == raw
    assert feed.verify_handoff(out,expected_market="KR") == original


def test_registered_potential_and_confirmed_are_passed_as_strategy_candidates(tmp_path):
    path = ledger(tmp_path)
    potential = export_state(path,at="2026-10-12")
    assert potential["selection_count"] == 1
    assert potential["selected_candidates"][0]["selection_state"] == "POTENTIAL"
    assert potential["selected_candidates"][0]["score_100"] == 90
    confirmed = export_state(path)
    assert confirmed["selection_count"] == 1
    row = confirmed["selected_candidates"][0]
    assert row["security_id"] == "005930"
    assert row["selection_state"] == "CONFIRMED"
    assert row["first_candidate_at"] == "2026-10-12"
    assert confirmed["state_changes"][-1]["event_type"] == "LEADER_CONFIRMED"
    assert confirmed["status"] == "SELECTED_CANDIDATES_RESEARCH_FEED"
    assert confirmed["research_only"] and not confirmed["execution_authority"]
    out = tmp_path / "inbox.json"
    assert feed.publish_handoff(confirmed,out)["selected_count"] == 1
    assert feed.verify_handoff(out,expected_market="KR")["selection_count"] == 1


def test_weakened_state_removed_from_strategy_universe_and_event_forwarded(tmp_path):
    path = ledger(tmp_path, transitions=3)
    warning = export_state(path,at="2026-10-14")
    assert warning["selection_count"] == 0
    assert warning["status"] == "NO_SELECTED_CANDIDATES"
    assert warning["state_changes"][-1]["current"] == "WEAKENING"
    assert warning["state_changes"][-1]["event_type"] == "LEADER_WEAKENING"
    assert warning["state_changes"][-1]["security_id"] == "005930"


def test_missing_pit_becomes_watch_no_false_leader_handoff(tmp_path):
    db_path = tmp_path / "state.sqlite"
    db = StateHistory(db_path)
    try:
        db.record("KR","2026-10-13",[
            selected(evidence={"financial_pit":True})])
    finally:
        db.close()
    payload = export_state(db_path)
    assert payload["selection_count"] == 0
    assert payload["state_changes"] == []
    assert payload["source_kind"] == "LOCAL_STATE_HISTORY"


def test_us_market_code_preserved_in_market_neutral_contract(tmp_path):
    db_path = ledger(tmp_path,market="US",sec="AAPL")
    payload = export_state(db_path,market="US")
    assert payload["selected_candidates"][0]["security_id"] == "AAPL"
    assert payload["market"] == "US"
    path = tmp_path / "us_feed.json"
    feed.publish_handoff(payload,path)
    with pytest.raises(ValueError,match="WRONG_MARKET|UNTRUSTED"):
        feed.verify_handoff(path,expected_market="KR")


def test_changed_evidence_cannot_overwrite_strategy_inbox_file(tmp_path):
    path = ledger(tmp_path,transitions=3)
    out = tmp_path / "feed.json"
    first = export_state(path,at="2026-10-13")
    feed.publish_handoff(first,out)
    old = out.read_bytes()
    second = export_state(path,at="2026-10-14")
    with pytest.raises(ValueError,match="VERSIONED_DESTINATION"):
        feed.publish_handoff(second,out)
    assert out.read_bytes() == old
    assert feed.publish_handoff(second,tmp_path/"feed_new.json")["selected_count"] == 0


def test_handoff_payload_mutation_or_invalid_order_status_rejected(tmp_path):
    payload = export_state(ledger(tmp_path))
    out = tmp_path / "feed.json"
    feed.publish_handoff(payload,out)
    report = json.loads(out.read_bytes())
    report["order_instruction"] = True
    report.pop("content_sha256")
    report["content_sha256"] = sha256(feed.canonical(report)).hexdigest()
    out.write_bytes(feed.canonical(report) + b"\n")
    with pytest.raises(ValueError,match="UNTRUSTED"):
        feed.verify_handoff(out)
    assert feed.publish_handoff(payload,tmp_path/"other.json")["status"] == "DELIVERED_TO_INBOX"


def test_wrong_row_identity_in_original_state_ledger_blocks_handoff(tmp_path):
    path = ledger(tmp_path)
    with sqlite3.connect(path) as db:
        body = json.loads(db.execute(
            "SELECT body FROM state_history WHERE as_of='2026-10-13'"
        ).fetchone()[0])
        body["security_id"] = "000660"
        db.execute("UPDATE state_history SET body=? WHERE as_of='2026-10-13'",
                   (json.dumps(body),))
    with pytest.raises(ValueError,match="BODY_MISMATCH"):
        export_state(path)


def test_missing_or_future_input_cannot_claim_selected_signal(tmp_path):
    path = ledger(tmp_path)
    with pytest.raises(ValueError,match="FUTURE"):
        feed.state_history_handoff(
            path,market="KR",as_of="2026-10-15",clock=NOW)
    with pytest.raises(ValueError,match="FUTURE"):
        feed.research_cohort_handoff(
            research_source(tmp_path),request_day="2026-10-15",clock=NOW)
    assert not (tmp_path/"not_published.json").exists()


def test_cli_produces_transportable_readonly_feed(tmp_path,capsys):
    from scripts.export_strategy_handoff import main
    data = research_source(tmp_path)
    out = tmp_path / "handoff.json"
    args = ["--research-cohort",str(data),"--market","KR",
            "--as-of","2026-10-14","--out",str(out)]
    assert main(args) == 0
    received = json.loads(capsys.readouterr().out)
    assert received["watchlist_count"] == 3
    assert received["selected_count"] == 0
    assert received["execution_authority"] is False
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ALREADY_DELIVERED"


def test_cli_state_source_and_error_return(tmp_path,capsys):
    from scripts.export_strategy_handoff import main
    path = ledger(tmp_path)
    out = tmp_path/"selected.json"
    assert main(["--state-ledger",str(path),"--market","KR",
                 "--as-of","2026-10-13","--out",str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["selected_count"] == 1
    assert main(["--state-ledger",str(tmp_path/"missing.sqlite"),
                 "--market","KR","--as-of","2026-10-13",
                 "--out",str(tmp_path/"empty.json")]) == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_permanent_issuer_id_resolves_real_symbol_from_existing_pit_membership(tmp_path):
    from eraleader.offline_pit import OfflineLedger
    source_file = Path(__file__).parent / "fixtures" / "offline_synthetic.json"
    identity = tmp_path / "offline.sqlite"
    db = OfflineLedger(identity)
    try:
        db.import_file(source_file)
    finally:
        db.close()
    states = tmp_path / "state_history.sqlite"
    history = StateHistory(states)
    try:
        history.record("KR","2024-09-01T17:00:00+09:00",[selected("SYN-A")])
    finally:
        history.close()
    payload = feed.state_history_handoff(
        states,market="KR",as_of="2024-09-01T17:00:00+09:00",
        identity_ledger=identity,clock=NOW)
    assert payload["selection_count"] == 1
    row = payload["selected_candidates"][0]
    assert row["security_id"] == "SYN-A"
    assert row["ticker"] == "111111"
    assert row["ticker_resolved"] is True
    assert row["strategy_research_allowed"] is True
    assert payload["unresolved_selected_tickers"] == 0
    no_map = feed.state_history_handoff(
        states,market="KR",as_of="2024-09-01T17:00:00+09:00",
        clock=NOW)
    assert no_map["selected_candidates"][0]["ticker"] is None
    assert no_map["selected_candidates"][0]["strategy_research_allowed"] is False
    assert no_map["unresolved_selected_tickers"] == 1


def test_integrated_cli_can_deliver_one_way_feed_without_creating_leaders(tmp_path,capsys):
    from eraleader.cli import main
    fixture = Path(__file__).parent / "fixtures" / "offline_synthetic.json"
    main(["offline-import","--file",str(fixture),
          "--out",str(tmp_path)])
    capsys.readouterr()
    target = tmp_path / "strategy_inbox.json"
    argv = ["offline-integrated","--market","KR",
            "--as-of","2024-09-01T17:00:00+09:00",
            "--out",str(tmp_path),
            "--strategy-handoff-out",str(target)]
    main(argv)
    first = json.loads(capsys.readouterr().out)
    assert first["strategy_handoff"]["status"] == "DELIVERED_TO_INBOX"
    report = feed.verify_handoff(target,expected_market="KR")
    assert report["selected_candidates"] == []
    assert report["research_only"] is True
    assert report["execution_authority"] is False
    main(argv)
    again = json.loads(capsys.readouterr().out)
    assert again["strategy_handoff"]["status"] == "ALREADY_DELIVERED"
