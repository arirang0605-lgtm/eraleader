"""Official day → financial/industry same-session → demo research provenance."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader.kiwoom_investor_flow import canonical
from eraleader.official_kiwoom_daily_bridge import advance
from test_kiwoom_investor_flow import fixtures
from test_kiwoom_shared_daily_batch import Gateway

NOW = datetime(2026, 10, 13, 11, 20, tzinfo=timezone.utc)
EARLY = datetime(2026, 10, 13, 7, 0, tzinfo=timezone.utc)
YESTERDAY = datetime(2026, 10, 12, 11, 20, tzinfo=timezone.utc)
DAY = "2026-10-13"
CODES = ["005930", "000660"]


def official(root: Path, *, day=DAY, received="2026-10-13T08:10:00+00:00"):
    root.mkdir(mode=0o700, exist_ok=True)
    site = root / "site"
    site.mkdir(mode=0o700, exist_ok=True)
    for name in ("kr.html", "official_api.html"):
        (site / name).write_text("<!doctype html><body>original</body>")
    evidence = {
        "schema": "eraleader.official_api_pit_research_bridge.v1",
        "api_observation_day": day,
        "official_leaders": 0,
        "historic_universe_pit_verified": False,
        "issuer_share_class_verified": False,
        "decision_at": received,
        "dart_full_day": {"market_day": day, "row_count": 500, "page_count": 5,
                          "manifest_sha256": "d" * 64},
        "sources": [{"source": x, "row_count": 100, "first_receipt_sha256": ("a" if i==0 else "b" if i==1 else "c") * 64}
                    for i, x in enumerate(("krx-kospi", "krx-kosdaq", "dart-disclosures"))],
    }
    (root / "official_api_pit_research.json").write_bytes(canonical(evidence))
    return evidence


def cohort(root: Path, *, day=DAY,
           basic_at="2026-10-13T09:05:00+00:00",
           industry_at="2026-10-13T09:15:00+00:00"):
    root.mkdir(mode=0o700, exist_ok=True)
    first, peers = fixtures()
    first["market_session"] = day
    first["decision_at_utc"] = basic_at
    first["source_watch_run_id"] = "1" * 20
    first["content_sha256"] = sha256(canonical({
        k: v for k, v in first.items() if k != "content_sha256"})).hexdigest()
    peers["market_session"] = day
    peers["as_of_utc"] = industry_at
    peers["baseline_candidate_sha256"] = first["content_sha256"]
    peers["content_sha256"] = sha256(canonical({
        k: v for k, v in peers.items() if k != "content_sha256"})).hexdigest()
    (root / "basic_candidates_kr.json").write_bytes(canonical(first))
    (root / "industry_peers_kr.json").write_bytes(canonical(peers))
    source = json.loads((root.parent / "official" / "official_api_pit_research.json").read_text())
    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    (runs / ("1" * 20 + ".json")).write_bytes(canonical({
        "run_id": "1" * 20,
        "official_api_evidence": source,
    }))
    site = root / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text("<!doctype html><body>BASELINE_UNCHANGED</body>")
    return root


def run(tmp_path, *, clock=NOW, codes=CODES,
        apply_capture=False, apply_kiwoom=False, capture_func=None,
        broker=None):
    return advance(market_day=DAY, official_out=tmp_path/"official",
                   cohort_root=tmp_path/"cohort", codes=codes, clock=clock,
                   apply_capture=apply_capture, capture_official=capture_func,
                   apply_kiwoom=apply_kiwoom, client_factory=broker)


def _no_broker():
    raise AssertionError("broker should never be accessed")


def test_check_only_never_contacts_official_or_demo_on_missing_day(tmp_path):
    out=run(tmp_path, apply_capture=False, apply_kiwoom=True, broker=_no_broker)
    assert out["status"] == "WAIT_OFFICIAL_KRX_DART_RESEARCH"
    assert out["api_calls"] == 0
    assert not (tmp_path/"official").exists()


@pytest.mark.parametrize("when,state", [
    (EARLY,"HOLD_MARKET_RESEARCH_CUTOFF_19_KST"),
    (YESTERDAY,"HOLD_NOT_CURRENT_MARKET_DAY"),
])
def test_clock_gate_blocks_before_sources_and_broker(tmp_path, when, state):
    assert run(tmp_path,clock=when, apply_capture=True,
               capture_func=_no_broker,apply_kiwoom=True,broker=_no_broker)["status"]==state


def test_official_capture_completes_then_stops_without_same_day_cfs_peers(tmp_path):
    out = tmp_path/"official"
    calls=[]
    def capture():
        calls.append(1)
        official(out)
        return {"status":"OFFICIAL_KR_DAY_RESEARCH_ONLY", "market_session": DAY}
    state=run(tmp_path,apply_capture=True,capture_func=capture,
              apply_kiwoom=True,broker=_no_broker)
    assert calls == [1]
    assert state["status"]=="WAIT_SAME_DAY_CFS_INDUSTRY_COHORT"
    assert state["broker_requests"]==0
    assert not (tmp_path/"cohort").exists()


def test_old_krx_day_is_not_accepted_as_today(tmp_path):
    official(tmp_path/"official",day="2026-10-08")
    with pytest.raises(ValueError,match="OFFICIAL_DAY_PIT"):
        run(tmp_path,broker=_no_broker,apply_kiwoom=True)


def test_current_official_missing_candidate_returns_wait_no_broker(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort", day="2026-10-08")
    state=run(tmp_path,apply_kiwoom=True,broker=_no_broker)
    assert state["status"] == "WAIT_SAME_DAY_CFS_INDUSTRY_COHORT"
    assert state["broker_requests"] == 0


def test_same_day_complete_official_plus_cfs_cohort_enables_demo_only(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    ready=run(tmp_path,apply_kiwoom=False,broker=_no_broker)
    assert ready["status"]=="READY_TO_CHECK_KIWOOM_DEMO_NO_NETWORK"
    class Demo(Gateway):
        def status(self):
            return {"configured":{"demo":True,"real":False}, "orders_enabled":False}
    fake=Demo()
    result=run(tmp_path,apply_kiwoom=True,broker=lambda:fake)
    assert result["status"]=="KIWOOM_PUBLISHED"
    assert len(fake.calls)==2
    assert all(x["mode"]=="demo" for x in fake.calls)
    assert result["broker_orders"]==0 and result["investment_rank_changed"] is False
    again=run(tmp_path,apply_kiwoom=True,broker=_no_broker)
    assert again["status"]=="KIWOOM_SKIPPED_ALREADY_PUBLISHED"


def test_cfs_decision_before_official_receipt_fails_closed(tmp_path):
    official(tmp_path/"official",received="2026-10-13T09:30:00+00:00")
    cohort(tmp_path/"cohort",basic_at="2026-10-13T09:05:00+00:00")
    with pytest.raises(ValueError,match="PREDATES_OFFICIAL"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_corrupt_industry_sha_rejected_before_broker(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    p=tmp_path/"cohort"/"industry_peers_kr.json"
    data=json.loads(p.read_text());data["industry_covert"]="changed"
    p.write_bytes(canonical(data))
    with pytest.raises(ValueError,match="SHA"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_invalid_official_capture_result_cannot_be_treated_as_pass(tmp_path):
    def capture():
        official(tmp_path/"official")
        return {"status":"OFFICIAL_KR_DAY_RESEARCH_ONLY", "market_session":"2026-10-08"}
    with pytest.raises(ValueError,match="DID_NOT_CONFIRM"):
        run(tmp_path,apply_capture=True,capture_func=capture,broker=_no_broker)


def test_existing_empty_official_out_is_not_overwritten(tmp_path):
    (tmp_path/"official").mkdir()
    with pytest.raises(ValueError,match="ALREADY_EXISTS"):
        run(tmp_path,apply_capture=True,capture_func=_no_broker)


def test_official_full_day_missing_provider_receipt_rejected(tmp_path):
    data=official(tmp_path/"official")
    data["sources"].pop()
    (tmp_path/"official"/"official_api_pit_research.json").write_bytes(canonical(data))
    with pytest.raises(ValueError,match="INVALID"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_unlisted_security_denied_without_demo_calls(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    with pytest.raises(ValueError,match="OUTSIDE_COHORT"):
        run(tmp_path,codes=["999999"],apply_kiwoom=True,broker=_no_broker)


def test_importable_cli_check_only(tmp_path, monkeypatch, capsys):
    from scripts import run_official_kiwoom_research as cli
    def fake(**kwargs):
        assert kwargs["apply_capture"] is False
        assert kwargs["apply_kiwoom"] is False
        return {"status":"WAIT_OFFICIAL_KRX_DART_RESEARCH","broker_orders":0}
    monkeypatch.setattr(cli,"advance",fake)
    args=["--day",DAY,"--official-out",str(tmp_path/"official"),
          "--cohort-root",str(tmp_path/"cohort"),"--codes","005930,000660"]
    assert cli.main(args)==0
    assert json.loads(capsys.readouterr().out)["broker_orders"]==0


def test_zero_krx_rows_are_not_a_trading_session(tmp_path):
    data = official(tmp_path/"official")
    for row in data["sources"]:
        if row["source"] == "krx-kospi":
            row["row_count"] = 0
    (tmp_path/"official"/"official_api_pit_research.json").write_bytes(canonical(data))
    with pytest.raises(ValueError, match="OFFICIAL_DAY_PIT"):
        run(tmp_path, apply_kiwoom=True, broker=_no_broker)


def test_live_capture_requires_explicit_existing_original_root(tmp_path, capsys):
    from scripts import run_official_kiwoom_research as cli
    args = ["--day", DAY, "--official-out", str(tmp_path/"output"),
            "--cohort-root", str(tmp_path/"cohort"),
            "--codes", "005930", "--capture-official"]
    assert cli.main(args) == 2
    assert "OFFICIAL_KIWOOM_DAILY_RESEARCH_BLOCKED" in capsys.readouterr().err
    assert not (tmp_path/"output").exists()


def test_same_day_stale_first_receipt_cannot_join_demo(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    run_file=tmp_path/"cohort"/"runs"/("1"*20+".json")
    saved=json.loads(run_file.read_text())
    saved["official_api_evidence"]["sources"][0]["first_receipt_sha256"]="f"*64
    run_file.write_bytes(canonical(saved))
    with pytest.raises(ValueError,match="FIRST_ORIGINAL_RECEIPTS_DIFFER"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_same_day_dart_full_manifest_mismatch_blocks(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    run_file=tmp_path/"cohort"/"runs"/("1"*20+".json")
    saved=json.loads(run_file.read_text())
    saved["official_api_evidence"]["dart_full_day"]["manifest_sha256"]="e"*64
    run_file.write_bytes(canonical(saved))
    with pytest.raises(ValueError,match="FIRST_ORIGINAL_RECEIPTS_DIFFER"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_cohort_watch_run_file_required(tmp_path):
    official(tmp_path/"official")
    cohort(tmp_path/"cohort")
    (tmp_path/"cohort"/"runs"/("1"*20+".json")).unlink()
    with pytest.raises(ValueError,match="COHORT_RUN_ORIGINAL_MISSING"):
        run(tmp_path,apply_kiwoom=True,broker=_no_broker)


def test_zero_live_krx_response_stops_before_first_receipt_write():
    from eraleader.official_kiwoom_daily_bridge import reject_empty_live_krx
    from eraleader.official_api_capture import SOURCES
    path = "https://" + SOURCES["krx-kospi"][0] + SOURCES["krx-kospi"][1]
    value=b'{"OutBlock_1":[]}'
    with pytest.raises(ValueError, match="DAILY_ROWS_NOT_YET_AVAILABLE"):
        reject_empty_live_krx(path, {}, day=DAY,
                              fetch=lambda url, headers: value)


def test_valid_krx_response_reused_without_second_http_fetch():
    from eraleader.official_kiwoom_daily_bridge import reject_empty_live_krx
    from eraleader.official_api_capture import SOURCES
    p = "https://" + SOURCES["krx-kosdaq"][0] + SOURCES["krx-kosdaq"][1]
    value=canonical({"OutBlock_1":[{
        "BAS_DD":"20261013", "ISU_CD":"000660",
        "TDD_CLSPRC":"12345"}]})
    calls=[]
    def fetch(url, headers):
        calls.append(url)
        return value
    assert reject_empty_live_krx(p, {}, day=DAY, fetch=fetch) == value
    assert calls == [p]


def test_dart_is_passed_unchanged_into_original_full_day_validator():
    from eraleader.official_kiwoom_daily_bridge import reject_empty_live_krx
    from eraleader.official_api_capture import SOURCES
    p = "https://" + SOURCES["dart-disclosures"][0] + SOURCES["dart-disclosures"][1]
    value=b'{"status":"013"}'
    assert reject_empty_live_krx(p, {}, day=DAY, fetch=lambda u,h:value) == value
