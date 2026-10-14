"""DART original annual profit margins -> early WATCH JSON/HTML positive path."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path

import pytest

from eraleader.dart_profitability_watch import dart_annual_margin_context,RESEARCH_SOURCE
from eraleader.early_leader_watch_queue import publish_early_watch,_validated
from eraleader.operations_overview import audit_local_operations
from test_early_leader_watch_queue import setup,NOW


def actual_style(code="005930",when="2026-10-14T02:00:00+00:00"):
    return {
        code:{
            "dart_latest_cfs_business_year":2025,
            "dart_cfs_revenue_krw":100_000_000,
            "dart_cfs_operating_income_krw":23_000_000,
            "dart_cfs_net_income_krw":12_000_000,
            "dart_cfs_operating_margin_pct":23.0,
            "dart_cfs_net_margin_pct":12.0,
            "dart_cfs_first_receipt_sha256":"a"*64,
            "dart_cfs_first_received_at_utc":when,
            "dart_cfs_issuer_corp_code":"00126380",
            "dart_cfs_margin_source":RESEARCH_SOURCE,
            "dart_cfs_independent_pit_certified":False,
        }
    }


def test_signed_verified_positive_company_margin_reaches_neutral_watch_and_html(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    vault=tmp_path/"private_source";vault.mkdir()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style())
    published=publish_early_watch(marketwide=market,project=project,
                                  factor_input=partial,dart_cfs_capture_root=vault,
                                  clock=NOW)
    assert published["status"]=="PUBLISHED" and published["orders"]==0
    doc=_validated(Path(published["manifest"]),clock=NOW)
    assert doc["dart_profitability_companies_in_watch"]==1
    assert doc["dart_profitability_originals_available"]==1
    assert doc["receiver_project"] is None
    assert doc["selected_candidates"]==[]
    assert doc["formal_leader_selection_count"]==0
    mapping={r["security_id"]:r for r in doc["review_queue"]}
    good=mapping["005930"]
    assert good["dart_cfs_revenue_krw"]==100_000_000
    assert good["dart_cfs_operating_margin_pct"]==23.0
    assert good["dart_cfs_net_margin_pct"]==12.0
    assert good["competitive_advantage_score_20"] is None
    assert "competitiveness" in good["missing_for_5factor"]
    other=mapping["000660"]
    assert other["dart_cfs_operating_margin_pct"] is None
    assert other["dart_cfs_margin_source"] is None
    page=Path(published["site"]).read_text()
    assert "DART 연결재무 실적 수익성" in page
    assert "23.0" in page
    linked=audit_local_operations(project,clock=NOW)["kr_early_leader_watch"]
    assert linked is not None and linked["count"]==2
    assert Path(published["manifest"]).exists()
    replay=publish_early_watch(marketwide=market,project=project,
                               factor_input=partial,dart_cfs_capture_root=vault,
                               clock=NOW+timedelta(minutes=2))
    assert replay["status"]=="ALREADY_PUBLISHED"


def test_existing_watch_is_not_overwritten_by_dart_profitability_version(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    previous=publish_early_watch(marketwide=market,project=project,
                                 factor_input=partial,clock=NOW)
    frozen=Path(previous["manifest"]).read_bytes()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style())
    vault=tmp_path/"private_source";vault.mkdir()
    new=publish_early_watch(marketwide=market,project=project,
                            factor_input=partial,dart_cfs_capture_root=vault,
                            clock=NOW)
    assert new["manifest"]!=previous["manifest"]
    assert Path(previous["manifest"]).read_bytes()==frozen


def test_future_receipt_cannot_enter_watch(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    vault=tmp_path/"source";vault.mkdir()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style(when="2026-10-15T00:00:00+00:00"))
    with pytest.raises(ValueError,match="FUTURE_OR_UNVERIFIED"):
        publish_early_watch(marketwide=market,project=project,
                            factor_input=partial,dart_cfs_capture_root=vault,
                            clock=NOW)
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))


def test_private_root_absent_prevents_fake_margin_without_stopping_default_watch(tmp_path):
    _,project,market,partial=setup(tmp_path)
    import json
    s=json.loads(market.read_bytes())
    with pytest.raises(ValueError,match="PRIVATE_ROOT"):
        dart_annual_margin_context(market=s,capture_root=tmp_path/"missing",
                                   now=NOW)
    normal=publish_early_watch(marketwide=market,project=project,
                               factor_input=partial,clock=NOW)
    assert normal["watch_queue_count"]==2


def test_cli_optin_requires_actual_files(tmp_path):
    import subprocess,sys
    from pathlib import Path
    _,project,market,partial=setup(tmp_path)
    runner=Path(__file__).resolve().parents[1]/"scripts"/"publish_early_leader_watch.py"
    cmd=[sys.executable,str(runner),"--project",str(project),
         "--marketwide-report",str(market),"--factor-input",str(partial),
         "--dart-cfs-capture-root",str(tmp_path/"absent")]
    p=subprocess.run(cmd,capture_output=True,text=True)
    assert p.returncode==2
    assert "EARLY_LEADER_WATCH_PUBLICATION_BLOCKED" in p.stderr
