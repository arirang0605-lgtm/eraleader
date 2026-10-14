from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import plistlib

import pandas as pd
import pytest

from eraleader import official_market_incremental as workflow
from eraleader.official_api_capture import capture_official_api
from eraleader.marketwide_schedule import generate_marketwide_plist
from eraleader.official_partial_factor_bridge import derive_partial_factor_input
from eraleader.early_leader_watch_queue import publish_early_watch
from eraleader.early_watch_daily_brief import publish_daily_brief
from test_official_partial_factor_bridge import source

NOW = datetime(2026, 10, 15, 0, tzinfo=timezone.utc)
CREDS = {"ERALEADER_KRX_AUTH_KEY": "A" * 40}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "output").mkdir(mode=0o700)
    (project / "scripts").mkdir()
    (project / "scripts" / "run_marketwide_daily.py").write_text("pass")
    root = tmp_path / "sources"
    root.mkdir()
    baseline = root / "baseline"
    baseline.mkdir()
    path, report = source(baseline)
    captures = project / "output" / "captures"
    captures.mkdir(mode=0o700)
    records = []
    for code in ("005930", "000660", "123456"):
        for i, day in enumerate(pd.bdate_range(end="2026-10-13", periods=270)):
            close = 10000 + i * 10
            records.append(dict(security_id=code, name=code, venue="OLD",
                session=day, open=close, high=close+200, low=close-200,
                close=close, volume=1000, turnover=close*1000, market_cap=100000000))
    monkeypatch.setattr(workflow, "read_market_bars",
                        lambda *a, **k: (pd.DataFrame(records), {}))
    return project, root, captures, path, report


def fetch_for(day="20261014", empty=None, renamed=False):
    def fetch(url, headers):
        venue = "KOSPI" if "stk_bydd" in url else "KOSDAQ"
        values = [("005930", "삼성전자"), ("000660", "SK하이닉스")] if venue == "KOSPI" else [
            ("123456", "코스닥기업")]
        rows = [] if empty in (venue, "BOTH") else [{
            "BAS_DD": day, "ISU_CD": code,
            "ISU_NM": "다른기업" if renamed and code == "005930" else name,
            "TDD_OPNPRC": "14000", "TDD_HGPRC": "16000", "TDD_LWPRC": "13000",
            "TDD_CLSPRC": "15000", "ACC_TRDVOL": "1000",
            "ACC_TRDVAL": "15000000", "MKTCAP": "100000000"} for code, name in values]
        return json.dumps({"OutBlock_1": rows}, ensure_ascii=False).encode()
    return fetch


def run(setup, **kwargs):
    project, root, captures, _, _ = setup
    return workflow.update_official_market(project=project, source_root=root,
        capture_root=captures, clock=lambda: NOW, **kwargs)


def test_missing_receipts_download_once_and_publish_existing_watch_brief(setup):
    project, _, captures, original, _ = setup
    before = original.read_bytes()
    result = run(setup, apply_official=True, creds=CREDS, fetch=fetch_for())
    assert result["published_sessions"] == ["2026-10-14"]
    assert result["external_api_calls"] == 2
    report = json.loads(Path(result["source_report_file"]).read_bytes())
    assert report["official_krx_observed"] == 3
    assert report["financial_factors_observed"] == 2
    assert report["cached_financial_source_market_session"] == "2026-10-13"
    assert report["financial_cache_refreshed"] is False
    assert report["flow_factors_observed"] == 0
    assert report["source_decision_at_utc"] == NOW.isoformat()
    partial = derive_partial_factor_input(
        marketwide=Path(result["source_report_file"]), project=project, clock=NOW)
    watch = publish_early_watch(marketwide=Path(result["source_report_file"]),
        project=project, factor_input=Path(partial["input_file"]), clock=NOW)
    brief = publish_daily_brief(watch_manifest=Path(watch["manifest"]),
                                project=project, clock=NOW)
    assert watch["watch_queue_count"] == brief["watch_rows"] == 3
    repeat = run(setup, apply_official=True, creds=CREDS,
                 fetch=lambda *_: pytest.fail("duplicate official request"))
    assert repeat["status"] == "KR_INCREMENTAL_ALREADY_CURRENT"
    assert repeat["external_api_calls"] == 0
    assert repeat["source_report_file"] == result["source_report_file"]
    assert len(list(captures.glob("first_*"))) == 2
    assert original.read_bytes() == before


def test_saved_pair_works_without_network_or_credentials(setup):
    captures = setup[2]
    for source_name in workflow.SOURCES:
        capture_official_api(source_name, captures, day="2026-10-14",
            creds=CREDS, fetch=fetch_for(), clock=lambda: NOW-timedelta(hours=1))
    result = run(setup, fetch=lambda *_: pytest.fail("network"))
    assert result["external_api_calls"] == 0
    assert result["status"] == "KR_INCREMENTAL_UPDATED"


@pytest.mark.parametrize("empty", ["KOSDAQ", "BOTH"])
def test_provider_empty_or_partial_preserves_previous_site_and_retries_no_more_today(setup, empty):
    result = run(setup, apply_official=True, creds=CREDS, fetch=fetch_for(empty=empty))
    assert result["published_sessions"] == []
    assert result["status"] == ("KR_INCREMENTAL_NO_DAILY_ROWS" if empty == "BOTH"
                               else "KR_INCREMENTAL_PROVIDER_DELAYED")
    repeat = run(setup, apply_official=True, creds=CREDS,
                 fetch=lambda *_: pytest.fail("same day repeat on empty source"))
    assert repeat["external_api_calls"] == 0
    assert not list((setup[0]/"output"/workflow.FOLDER).glob("KR_*"))


def test_interrupted_pair_reuses_first_successful_capture_on_retry(setup):
    count = 0
    def failed(url, headers):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("provider unavailable")
        return fetch_for()(url, headers)
    with pytest.raises(OSError):
        run(setup, apply_official=True, creds=CREDS, fetch=failed)
    assert len(list(setup[2].glob("first_*"))) == 1
    result = run(setup, apply_official=True, creds=CREDS, fetch=fetch_for())
    assert result["external_api_calls"] == 1
    assert result["published_sessions"] == ["2026-10-14"]


def test_future_day_blocks_without_request(setup):
    with pytest.raises(ValueError, match="NOT_CLOSED"):
        run(setup, through_day="2026-10-15", apply_official=True,
            fetch=lambda *_: pytest.fail("future request"))


def test_company_identity_change_drops_cached_financial_values(setup):
    result = run(setup, apply_official=True, creds=CREDS, fetch=fetch_for(renamed=True))
    report = json.loads(Path(result["source_report_file"]).read_bytes())
    row = next(x for x in report["securities"] if x["security_id"] == "005930")
    assert row["revenue_yoy"] is None and row["industry_code"] is None
    assert row["earnings_research_25"] is None


def test_tampered_official_receipt_blocks_replay(setup):
    run(setup, apply_official=True, creds=CREDS, fetch=fetch_for())
    raw = next(setup[2].glob("first_*/raw_response.json"))
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(ValueError, match="invalid"):
        run(setup)


def test_incremental_schedule_points_to_full_existing_pipeline_after_19(setup):
    project, root, captures, _, _ = setup
    dest = project/"output"/"daily.plist"
    data = generate_marketwide_plist(project=project, source_root=root,
        destination=dest, hour=19, auto_watch=True, update_official=True,
        capture_root=captures)
    args = plistlib.loads(dest.read_bytes())["ProgramArguments"]
    assert args[1].endswith("run_marketwide_daily.py")
    assert "--apply-official" in args
    assert data["official_incremental_update_enabled"] is True
    assert data["auto_job_installed"] is False
    with pytest.raises(ValueError, match="AFTER_19"):
        generate_marketwide_plist(project=project, source_root=root,
            destination=project/"output"/"early.plist", hour=18,
            auto_watch=True, update_official=True, capture_root=captures)

def test_empty_pair_retries_on_next_local_day(setup):
    run(setup, apply_official=True, creds=CREDS, fetch=fetch_for(empty="BOTH"))
    project, root, captures, _, _ = setup
    result = workflow.update_official_market(project=project, source_root=root,
        capture_root=captures, through_day="2026-10-14",
        clock=lambda: NOW+timedelta(days=1), apply_official=True,
        creds=CREDS, fetch=fetch_for())
    assert result["external_api_calls"] == 2
    assert result["published_sessions"] == ["2026-10-14"]


def test_two_missing_days_accumulate_then_replay_without_requests(setup):
    from urllib.parse import urlsplit, parse_qs
    project, root, captures, _, _ = setup
    def dated(url, headers):
        day = parse_qs(urlsplit(url).query)["basDd"][0]
        return fetch_for(day)(url, headers)
    kwargs = dict(project=project, source_root=root, capture_root=captures,
        through_day="2026-10-15", clock=lambda: NOW+timedelta(days=1),
        apply_official=True, creds=CREDS)
    result = workflow.update_official_market(**kwargs, fetch=dated)
    assert result["published_sessions"] == ["2026-10-14", "2026-10-15"]
    assert result["external_api_calls"] == 4
    repeat = workflow.update_official_market(**kwargs,
        fetch=lambda *_: pytest.fail("duplicate backfill"))
    assert repeat["external_api_calls"] == 0
    assert repeat["source_market_session"] == "2026-10-15"


def test_previous_session_flow_does_not_move_to_new_day(setup):
    from test_marketwide_live_search import repin
    from eraleader.official_company_explorer import canonical
    baseline = setup[3]
    report = json.loads(baseline.read_bytes())
    report["securities"][0]["institutional_flow"] = 12
    report["securities"][0]["foreign_flow"] = 23
    report.update(flow_factors_observed=1, flow_matched_session_companies=1,
        flow_certification="FIRST_LOCAL_RECEIPT_RESEARCH_ONLY_NOT_HISTORIC_PIT",
        flow_source_manifest_sha256="a"*64)
    baseline.write_bytes(canonical(repin(report))+b"\n")
    result = run(setup, apply_official=True, creds=CREDS, fetch=fetch_for())
    latest = json.loads(Path(result["source_report_file"]).read_bytes())
    assert latest["flow_factors_observed"] == 0
    assert all(x["institutional_flow"] is None and x["foreign_flow"] is None
               for x in latest["securities"])


def test_another_updater_holds_capture_lock(setup):
    import fcntl
    lock = setup[0]/"output"/".official_market_daily.lock"
    with lock.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run(setup, apply_official=True,
            fetch=lambda *_: pytest.fail("concurrent request"))
    assert result["status"] == "KR_INCREMENTAL_ALREADY_RUNNING"
    assert result["external_api_calls"] == 0
