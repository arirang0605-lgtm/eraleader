"""ER-NC-08: opt-in sidecar, no legacy output changes, safe static delivery."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from eraleader.delivery import render_dashboard, write_dashboard
from eraleader.news_theme_delivery import (
    render_research_html, render_research_markdown,
    validate_research, write_research_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-13T00:00:00Z"


def fixture():
    return {
        "schema": "eraleader.er_nc08_public_sidecar.v1",
        "market": "KR",
        "as_of": NOW,
        "market_session": "2026-10-12",
        "research_only": True,
        "official_leaders": 0,
        "trading_enabled": False,
        "news_quality_status": "OK",
        "news_diagnostics": [{
            "schema": "eraleader.er_nc_market_news_response.v1",
            "security_id": "SHARE.A",
            "as_of": NOW,
            "market_data_available_at": "2026-10-12T09:00:00Z",
            "diagnosis": "stale_or_unknown",
            "reason_codes": ["MATERIAL_FACT_INVALIDATED_AFTER_ORIGINAL_VERSION"],
            "event_evidence_ids": ["fact.1"],
            "research_only": True,
            "official_leaders": 0,
            "recommendation": None,
        }],
        "themes": [{
            "schema": "eraleader.er_nc_theme_lifecycle.v1",
            "theme_id": "THEME.A",
            "state": "REACTIVATING",
            "episode_id": "THEME.A_EP2",
            "as_of": NOW,
            "catalyst_state": "UNKNOWN",
            "reason_codes": ["price_breadth_recovered"],
            "research_only": True,
            "official_leaders": 0,
        }],
        "author_strategies": [{
            "strategy_id": "N_ST", "status": "NOT_READY",
            "as_of": NOW, "trade_permission": "NO_ORDER",
            "executable": False,
        }],
    }


def legacy_snapshot():
    return {
        "source_market": "KR", "market_last_observation": "2026-10-12",
        "source_market_days": 2, "source_day": "2026-10-12",
        "note": "PRICE_ONLY_RESEARCH", "data_source": "synthetic",
        "shown": 1, "model_version": "baseline_v1",
        "rows": [{
            "rank": 1, "security_id": "005930",
            "name": "Test Co", "venue": "KRX",
            "price_strength_25": 13.4, "return_6m": 0.12,
            "total_score_100": None, "state": "WATCH",
        }],
    }


def original_delivery(tmp_path):
    payload = subprocess.check_output(
        ["git", "show", "bbe9be5:src/eraleader/delivery.py"], cwd=ROOT
    )
    path = tmp_path / "delivery_original.py"
    path.write_bytes(payload)
    spec = importlib.util.spec_from_file_location("legacy_delivery_original", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_news_off_legacy_render_bytes_identical_to_git_baseline(tmp_path):
    original = original_delivery(tmp_path)
    snapshot = legacy_snapshot()
    assert render_dashboard(snapshot) == original.render_dashboard(snapshot)
    assert render_dashboard(snapshot, show_news_research=False) == original.render_dashboard(snapshot)
    before = tmp_path / "baseline"
    after = tmp_path / "current"
    original.write_dashboard(snapshot, before)
    write_dashboard(snapshot, after)
    assert (before / "kr.html").read_bytes() == (after / "kr.html").read_bytes()
    assert (before / "index.html").read_bytes() == (after / "index.html").read_bytes()


def test_news_off_sidecar_returns_nothing_and_does_not_create_root(tmp_path):
    root = tmp_path / "sidecar"
    assert write_research_bundle(fixture(), root, enabled=False) == []
    assert not root.exists()


def test_optin_dashboard_only_adds_link_when_enabled(tmp_path):
    snapshot = legacy_snapshot()
    normal = render_dashboard(snapshot)
    news = render_dashboard(snapshot, show_news_research=True)
    assert "er_nc08_research.html" not in normal
    assert "er_nc08_research.html" in news
    site = tmp_path / "site"
    write_dashboard(snapshot, site, show_news_research=True)
    assert "er_nc08_research.html" in (site / "index.html").read_text()


def test_html_and_three_reports_driven_by_same_asof_snapshot(tmp_path):
    root = tmp_path / "er_nc08"
    files = write_research_bundle(fixture(), root, enabled=True)
    assert len(files) == 5
    site = (root / "site/er_nc08_research.html").read_text()
    assert "THEME.A" in site and "SHARE.A" in site
    assert "실전 매수" in site and "2026-10-13T00:00:00Z" in site
    assert "width=device-width" in site
    for period in ("daily", "weekly", "monthly"):
        report = (root / f"reports/er_nc08_{period}.md").read_text()
        assert period in report and "THEME.A" in report
        assert "실제 전송 0건" in report
    assert (root / "alerts_preview.json").exists()


def test_duplicate_transitions_are_deduped_and_second_export_identical(tmp_path):
    payload = fixture()
    payload["news_diagnostics"].append(deepcopy(payload["news_diagnostics"][0]))
    root = tmp_path / "generated"
    paths = write_research_bundle(payload, root, enabled=True)
    shas = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    again = write_research_bundle(payload, root, enabled=True)
    assert paths == again
    assert shas == [hashlib.sha256(path.read_bytes()).hexdigest() for path in again]
    alerts = json.loads((root / "alerts_preview.json").read_text())
    assert len(alerts["alerts"]) == 2
    assert all(event["status"] == "DRY_RUN_ONLY" for event in alerts["alerts"])
    assert alerts["real_messages_sent"] == 0


def test_distinct_payload_cannot_overwrite_existing_directory(tmp_path):
    root = tmp_path / "report"
    write_research_bundle(fixture(), root, enabled=True)
    before = (root / "site/er_nc08_research.html").read_bytes()
    changed = fixture()
    changed["news_quality_status"] = "STALE"
    with pytest.raises(FileExistsError):
        write_research_bundle(changed, root, enabled=True)
    assert (root / "site/er_nc08_research.html").read_bytes() == before


def test_html_injection_is_escaped_in_page_and_reports():
    data = fixture()
    attack = "<img src=x onerror=alert(1)>"
    data["news_diagnostics"][0]["reason_codes"] = [attack]
    data["themes"][0]["theme_id"] = "<script>alert(2)</script>"
    html = render_research_html(data)
    report = render_research_markdown(data, "daily")
    assert attack not in html and attack not in report
    assert "<script>" not in html and "<script>" not in report
    assert "&lt;img" in html and "&lt;img" in report
    assert "&lt;script&gt;" in html and "&lt;script&gt;" in report


def test_missing_news_is_explicit_warning_not_neutral():
    data = fixture()
    data["news_diagnostics"] = []
    data["news_quality_status"] = "MISSING"
    rendered = render_research_html(data)
    assert "뉴스 수신상태 미확인" in rendered
    assert "대장주 확정 금지" in rendered


@pytest.mark.parametrize("target", ["news", "theme", "author"])
def test_future_derived_inputs_are_rejected(target):
    data = fixture()
    if target == "news":
        data["news_diagnostics"][0]["as_of"] = "2027-01-01T00:00:00Z"
    elif target == "theme":
        data["themes"][0]["as_of"] = "2027-01-01T00:00:00Z"
    else:
        data["author_strategies"][0]["as_of"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="Future"):
        validate_research(data)


def test_future_price_availability_is_rejected_even_if_asof_is_old():
    data = fixture()
    data["news_diagnostics"][0]["market_data_available_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="Future"):
        validate_research(data)


@pytest.mark.parametrize("change", [
    {"research_only": False},
    {"official_leaders": 1},
    {"trading_enabled": True},
    {"market": "UNKNOWN"},
])
def test_no_official_or_trading_claims_are_allowed(change):
    data = fixture()
    data.update(change)
    with pytest.raises(ValueError):
        validate_research(data)


def test_author_signal_cannot_be_faked_by_sidecar():
    data = fixture()
    data["author_strategies"][0]["status"] = "SIGNAL"
    data["author_strategies"][0]["executable"] = True
    with pytest.raises(ValueError, match="non-trading"):
        validate_research(data)


def test_symlinked_output_root_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "linked"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="ordinary"):
        write_research_bundle(fixture(), root, enabled=True)
    assert list(outside.iterdir()) == []


def test_invalid_reporting_period_is_rejected():
    with pytest.raises(ValueError):
        render_research_markdown(fixture(), "annual")


def test_large_unbounded_news_rows_are_rejected(tmp_path):
    data = fixture()
    data["news_diagnostics"] *= 300
    with pytest.raises(ValueError, match="Oversized"):
        write_research_bundle(data, tmp_path / "not_created", enabled=True)
    assert not (tmp_path / "not_created").exists()


def test_non_owned_existing_file_is_not_overwritten(tmp_path):
    file_path = tmp_path / "already"
    file_path.write_text("preserve", encoding="utf-8")
    with pytest.raises((FileExistsError, ValueError)):
        write_research_bundle(fixture(), file_path, enabled=True)
    assert file_path.read_text() == "preserve"


def test_future_market_session_cannot_be_rendered_as_early_discovery():
    data = fixture()
    data["market_session"] = "2027-01-01"
    with pytest.raises(ValueError, match="Future market session"):
        validate_research(data)
