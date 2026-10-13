"""Verified older KR research is carried forward without new trading decisions."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil

import pytest

from eraleader import official_latest_baseline_fallback as fallback
from eraleader.kiwoom_investor_flow import canonical
from test_official_kiwoom_daily_bridge import official, cohort, CODES

REQUEST = "2026-10-14"
NOW = datetime(2026, 10, 14, 11, 20, tzinfo=timezone.utc)
EARLY = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


def archive(parent: Path, *, name="pair", day="2026-10-13",
            received="2026-10-13T08:10:00+00:00",
            basic_at="2026-10-13T09:05:00+00:00",
            industry_at="2026-10-13T09:15:00+00:00") -> Path:
    area = parent / name
    area.mkdir(parents=True, exist_ok=True)
    original = area / "official"
    official(original, day=day, received=received)
    result = cohort(area / "cohort", day=day, basic_at=basic_at,
                    industry_at=industry_at)
    shutil.copyfile(original / "official_api_pit_research.json",
                    result / "official_api_pit_research.json")
    for filename in ("kr.html", "official_api.html"):
        (result / "site" / filename).write_text("<!doctype html><body>Archive</body>")
    return result


def choose(tmp_path, **overrides):
    source = archive(tmp_path)
    args = {
        "request_day": REQUEST,
        "archived_roots": [source],
        "output": tmp_path / "published",
        "codes": list(CODES),
        "reason": "WAIT_OFFICIAL_KRX_DART_RESEARCH",
        "clock": NOW,
    }
    args.update(overrides)
    return fallback.choose_and_publish(**args), args


def _clean_sha(report: dict) -> str:
    clean = dict(report)
    sha = clean.pop("content_sha256")
    assert sha == sha256(canonical(clean)).hexdigest()
    return sha


def test_exact_prior_verified_session_published_with_explicit_freshness(tmp_path):
    report, args = choose(tmp_path)
    assert report["source_market_session"] == "2026-10-13"
    assert report["request_day"] == "2026-10-14"
    assert report["quality_status"] == "RECENT_PRIOR_WEEKDAY_RESEARCH_ONLY"
    assert report["trading_session_lag"] is None
    assert report["estimated_weekday_sessions_since_market_observation"] == 1
    assert not report["stale_warning"]
    assert not report["data_recomputed_as_today"]
    assert report["candidate_rank_changed"] is False
    assert report["same_day_kiwoom_combined"] is False
    assert report["official_leaders"] == report["broker_network_calls"] == 0
    assert report["orders_enabled"] is False
    assert report["trade_signal"] is None
    assert [r["security_id"] for r in report["selected_research_rows"]] == CODES
    _clean_sha(report)
    from_disk = json.loads((args["output"] / "report.json").read_bytes())
    assert from_disk == report
    assert (args["output"] / "index.html").read_text().startswith("<!doctype html>")
    assert not list(tmp_path.glob(".fallback_inflight_*"))


def test_two_or_more_estimated_weekdays_get_warning_not_buy_status(tmp_path):
    source = archive(tmp_path)
    report = fallback.choose_and_publish(
        request_day="2026-10-16", archived_roots=[source],
        output=tmp_path / "old", codes=list(CODES),
        reason="WAIT_OFFICIAL_KRX_DART_RESEARCH",
        clock=datetime(2026, 10, 16, 11, 20, tzinfo=timezone.utc))
    assert report["estimated_weekday_sessions_since_market_observation"] == 3
    assert report["stale_warning"]
    assert report["quality_status"] == "STALE_RESEARCH_WARNING"
    html = (tmp_path / "old" / "index.html").read_text()
    assert "자료 지연 경고" in html
    assert "2026-10-13" in html
    assert "2026-10-16" in html


def test_friday_to_monday_counts_one_estimated_weekday_not_three(tmp_path):
    old = archive(
        tmp_path, day="2026-10-16",
        received="2026-10-16T08:10:00+00:00",
        basic_at="2026-10-16T09:05:00+00:00",
        industry_at="2026-10-16T09:15:00+00:00")
    result = fallback.choose_and_publish(
        request_day="2026-10-19", archived_roots=[old],
        output=tmp_path / "monday", codes=list(CODES),
        reason="HOLD_MARKET_RESEARCH_CUTOFF_19_KST",
        clock=datetime(2026, 10, 19, 11, 20, tzinfo=timezone.utc))
    assert result["calendar_days_since_market_observation"] == 3
    assert result["estimated_weekday_sessions_since_market_observation"] == 1
    assert not result["stale_warning"]


def test_latest_market_session_selected_not_latest_file_order(tmp_path):
    latest = archive(tmp_path, name="latest")
    older = archive(
        tmp_path, name="older", day="2026-10-12",
        received="2026-10-12T08:10:00+00:00",
        basic_at="2026-10-12T09:05:00+00:00",
        industry_at="2026-10-12T09:15:00+00:00")
    result = fallback.choose_and_publish(
        request_day=REQUEST, archived_roots=[older, latest],
        output=tmp_path / "published", codes=list(CODES),
        reason="WAIT_OFFICIAL_KRX_DART_RESEARCH", clock=NOW)
    assert result["source_market_session"] == "2026-10-13"
    assert not result["stale_warning"]


def test_stale_source_does_not_change_latest_issuer_or_price_watch(tmp_path):
    src = archive(tmp_path)
    before = {f: (src/f).read_bytes() for f in (
        "official_api_pit_research.json", "basic_candidates_kr.json",
        "industry_peers_kr.json")}
    fallback.choose_and_publish(
        request_day=REQUEST, archived_roots=[src],
        output=tmp_path / "new", codes=list(CODES),
        reason="WAIT_OFFICIAL_KRX_DART_RESEARCH", clock=NOW)
    assert {f: (src/f).read_bytes() for f in before} == before


def test_existing_publication_rejected_and_not_overwritten(tmp_path):
    result, args = choose(tmp_path)
    before = (args["output"] / "report.json").read_bytes()
    with pytest.raises(ValueError, match="MUST_BE_NEW"):
        fallback.choose_and_publish(**args)
    assert (args["output"] / "report.json").read_bytes() == before


def test_unverified_baseline_returns_no_source_without_fabrication(tmp_path):
    empty = tmp_path / "incomplete"
    empty.mkdir()
    out = tmp_path / "new"
    result = fallback.choose_and_publish(
        request_day=REQUEST, archived_roots=[empty], output=out,
        codes=list(CODES), reason="WAIT_OFFICIAL_KRX_DART_RESEARCH", clock=NOW)
    assert result["status"] == "NO_VERIFIED_RESEARCH_BASELINE"
    assert not out.exists()
    assert result["broker_network_calls"] == 0


@pytest.mark.parametrize("defect", ["candidate_sha", "industry_sha",
                                    "different_session", "missing_run",
                                    "symlink", "future_market_session"])
def test_corruption_and_provenance_mismatch_fail_closed(tmp_path, defect):
    src = archive(tmp_path)
    if defect == "candidate_sha":
        p = src / "basic_candidates_kr.json"
        d = json.loads(p.read_text())
        d["comparisons"][0]["name"] = "TAMPERED_NAME"
        p.write_bytes(canonical(d))
    elif defect == "industry_sha":
        p = src / "industry_peers_kr.json"
        d = json.loads(p.read_text())
        d["comparisons"] = ["injected"]
        p.write_bytes(canonical(d))
    elif defect == "different_session":
        p = src / "industry_peers_kr.json"
        d = json.loads(p.read_text())
        d["market_session"] = "2026-10-14"
        d.pop("content_sha256", None)
        d["content_sha256"] = sha256(canonical(d)).hexdigest()
        p.write_bytes(canonical(d))
    elif defect == "missing_run":
        (src / "runs" / ("1" * 20 + ".json")).unlink()
    elif defect == "symlink":
        link = tmp_path / "linked"
        link.symlink_to(src, target_is_directory=True)
        src = link
    elif defect == "future_market_session":
        p = src / "official_api_pit_research.json"
        d = json.loads(p.read_text())
        d["api_observation_day"] = "2026-10-15"
        p.write_bytes(canonical(d))
    with pytest.raises((ValueError, KeyError)):
        fallback.choose_and_publish(
            request_day=REQUEST, archived_roots=[src],
            output=tmp_path / "publication", codes=list(CODES),
            reason="WAIT_OFFICIAL_KRX_DART_RESEARCH", clock=NOW)
    assert not (tmp_path / "publication").exists()


@pytest.mark.parametrize("reason", [
    "WAIT_OFFICIAL_KRX_DART_RESEARCH", "WAIT_SAME_DAY_CFS_INDUSTRY_COHORT",
    "HOLD_MARKET_RESEARCH_CUTOFF_19_KST", "HOLD_WEEKEND"])
def test_known_current_day_data_gap_falls_back_without_broker(tmp_path, monkeypatch, reason):
    src = archive(tmp_path)
    monkeypatch.setattr(fallback, "advance",
                        lambda **kw: {"status": reason, "broker_orders": 0})
    result = fallback.advance_with_fallback(
        market_day=REQUEST, official_out=tmp_path/"missing_day",
        cohort_root=tmp_path/"missing_cohort", codes=list(CODES),
        archived_roots=[src], fallback_out=tmp_path/"fallback",
        clock=NOW, apply_kiwoom=True,
        client_factory=lambda: pytest.fail("Must not use the broker"))
    assert result["status"] == "VERIFIED_PRIOR_BASELINE_CARRIED_FORWARD"
    assert result["reason"] == reason
    assert result["broker_network_calls"] == 0


def test_only_krx_empty_receipt_failure_can_be_recovered(tmp_path, monkeypatch):
    src = archive(tmp_path)
    def missing_krx(**kwargs):
        raise ValueError(fallback.KRX_EMPTY)
    monkeypatch.setattr(fallback, "advance", missing_krx)
    result = fallback.advance_with_fallback(
        market_day=REQUEST, official_out=tmp_path/"today",
        cohort_root=tmp_path/"none", codes=list(CODES),
        archived_roots=[src], fallback_out=tmp_path/"new", clock=NOW)
    assert result["source_market_session"] == "2026-10-13"


@pytest.mark.parametrize("error", [
    "OFFICIAL_DAY_PIT_RESEARCH_EVIDENCE_INVALID",
    "UNSAFE_CREDENTIAL_FILE", "FIRST_SHA_PIN_MISMATCH"])
def test_real_integrity_or_credential_error_is_never_hidden(tmp_path, monkeypatch, error):
    src = archive(tmp_path)
    def illegal(**kwargs):
        raise ValueError(error)
    monkeypatch.setattr(fallback, "advance", illegal)
    with pytest.raises(ValueError, match=error):
        fallback.advance_with_fallback(
            market_day=REQUEST, official_out=tmp_path/"today",
            cohort_root=tmp_path/"none", codes=list(CODES),
            archived_roots=[src], fallback_out=tmp_path/"output", clock=NOW)
    assert not (tmp_path / "output").exists()


def test_current_day_success_never_enters_fallback(tmp_path, monkeypatch):
    def current(**kwargs):
        return {"status":"KIWOOM_PUBLISHED", "broker_orders":0}
    monkeypatch.setattr(fallback, "advance", current)
    monkeypatch.setattr(fallback, "choose_and_publish",
                        lambda **kw: pytest.fail("Should not override live flow"))
    result = fallback.advance_with_fallback(
        market_day=REQUEST, official_out=tmp_path/"today",
        cohort_root=tmp_path/"cohort", codes=list(CODES),
        archived_roots=[tmp_path/"missing"], fallback_out=tmp_path/"none", clock=NOW)
    assert result["status"] == "KIWOOM_PUBLISHED"


def test_archived_untrusted_company_name_is_html_escaped():
    result = {
        "selected_research_rows": [{
            "security_id":"005930",
            "name":"<script>alert(1)</script>",
            "return_3m":None, "revenue_yoy":0.14,
            "operating_income_yoy":None,
            "revenue_yoy_acceleration":None,
        }],
        "calendar_days_since_market_observation":3,
        "estimated_weekday_sessions_since_market_observation":2,
        "quality_status":"STALE_RESEARCH_WARNING",
        "stale_warning":True,
        "request_day":REQUEST,
        "source_market_session":"2026-10-11",
        "published_at_utc":NOW.isoformat(),
    }
    html = fallback._render(result)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "N/A" in html


def test_cli_optin_and_default_legacy_mode(tmp_path, monkeypatch, capsys):
    from scripts import run_official_kiwoom_research as cli
    captured = []
    monkeypatch.setattr(cli, "advance",
                        lambda **kw: {"status": "WAIT_OFFICIAL_KRX_DART_RESEARCH",
                                      "broker_orders":0})
    monkeypatch.setattr(fallback, "advance_with_fallback",
                        lambda **kw: (captured.append(kw) or
                                      {"status":"VERIFIED_PRIOR_BASELINE_CARRIED_FORWARD",
                                       "broker_orders":0}))
    args = ["--day", REQUEST, "--official-out", str(tmp_path/"today"),
            "--cohort-root", str(tmp_path/"cohort"), "--codes", "005930,000660"]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "WAIT_OFFICIAL_KRX_DART_RESEARCH"
    assert not captured
    assert cli.main(args+["--fallback-source",str(tmp_path/"original"),
                          "--fallback-out",str(tmp_path/"new")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VERIFIED_PRIOR_BASELINE_CARRIED_FORWARD"
    assert len(captured) == 1
    assert captured[0]["archived_roots"] == [tmp_path/"original"]
    assert captured[0]["apply_kiwoom"] is False
    assert cli.main(args+["--fallback-source",str(tmp_path/"original")]) == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_auto_discovery_includes_only_complete_direct_cohorts(tmp_path):
    history = tmp_path / "history"
    history.mkdir()
    complete = archive(history, name="actual")
    partial = history / "half_written"
    partial.mkdir()
    (partial / "official_api_pit_research.json").write_text("{}")
    symlink = history / "linked"
    symlink.symlink_to(complete, target_is_directory=True)
    extra = history / "ordinary.txt"
    extra.write_text("not a source")
    assert fallback.discover_archived_cohorts(history) == [complete]
    assert not symlink.is_dir() or symlink.is_symlink()


def test_auto_discovery_root_itself_is_supported(tmp_path):
    source = archive(tmp_path)
    assert fallback.discover_archived_cohorts(source) == [source]


def test_automatic_archive_cli_selects_latest_verified_offline(tmp_path, capsys, monkeypatch):
    from scripts import run_official_kiwoom_research as cli
    history = tmp_path / "history"
    history.mkdir()
    source = archive(history)
    monkeypatch.setattr(fallback, "advance",
                        lambda **kw: {"status":"WAIT_OFFICIAL_KRX_DART_RESEARCH",
                                      "broker_orders":0})
    args = [
        "--day", "2026-10-13",
        "--official-out", str(tmp_path / "unavailable_today"),
        "--cohort-root", str(tmp_path / "missing_today"),
        "--codes", ",".join(CODES),
        "--fallback-history-dir", str(history),
        "--fallback-out", str(tmp_path / "latest_result"),
    ]
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_market_session"] == "2026-10-13"
    assert result["broker_network_calls"] == 0
    assert result["source_candidate_sha256"] == json.loads(
        (source / "basic_candidates_kr.json").read_text())["content_sha256"]
    assert (tmp_path / "latest_result" / "index.html").exists()


def test_auto_discovery_empty_history_is_not_fabricated(tmp_path, capsys, monkeypatch):
    from scripts import run_official_kiwoom_research as cli
    history = tmp_path / "empty_history"
    history.mkdir()
    monkeypatch.setattr(fallback, "advance",
                        lambda **kw: {"status":"WAIT_OFFICIAL_KRX_DART_RESEARCH",
                                      "broker_orders":0})
    args = [
        "--day", "2026-10-13",
        "--official-out", str(tmp_path / "today"),
        "--cohort-root", str(tmp_path / "cohort"),
        "--codes", ",".join(CODES),
        "--fallback-history-dir", str(history),
        "--fallback-out", str(tmp_path / "new"),
    ]
    # CLI uses the real UTC clock. The synthetic request day is in the past;
    # the strict current-day gate refuses but still retains a safe no-data state.
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["fallback_status"] == "NO_VERIFIED_RESEARCH_BASELINE"
    assert not (tmp_path / "new").exists()


def test_scheduler_today_token_and_dated_new_output_are_stable(tmp_path, monkeypatch, capsys):
    from scripts import run_official_kiwoom_research as cli
    from datetime import datetime as RealDateTime

    class FixedClock:
        @staticmethod
        def now(tz):
            return RealDateTime(2026, 10, 13, 12, 0,
                                tzinfo=timezone.utc).astimezone(tz)

    captured = []
    monkeypatch.setattr(cli, "datetime", FixedClock)
    monkeypatch.setattr(fallback, "advance_with_fallback",
                        lambda **kw: (captured.append(kw) or {
                            "status": "VERIFIED_PRIOR_BASELINE_CARRIED_FORWARD",
                            "broker_orders": 0,
                        }))
    args = [
        "--day", "today",
        "--official-out", str(tmp_path/"official_{date}"),
        "--cohort-root", str(tmp_path/"cohort_{date}"),
        "--codes", ",".join(CODES),
        "--fallback-source", str(tmp_path/"historical"),
        "--fallback-out", str(tmp_path/"carry_{date}"),
    ]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["broker_orders"] == 0
    assert len(captured) == 1
    assert captured[0]["market_day"] == "2026-10-13"
    assert captured[0]["official_out"] == tmp_path/"official_20261013"
    assert captured[0]["cohort_root"] == tmp_path/"cohort_20261013"
    assert captured[0]["fallback_out"] == tmp_path/"carry_20261013"
    assert captured[0]["apply_capture"] is False
    assert captured[0]["apply_kiwoom"] is False
