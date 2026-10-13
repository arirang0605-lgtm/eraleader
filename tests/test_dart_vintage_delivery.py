"""Read-only CFS vintage first-known evidence flows into optional research page."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import sqlite3

import pytest

from test_dart_vintage_registry import fx, capture, reg
from test_official_api_pit_bridge import packs, cached
from eraleader import official_api_pit_bridge as bridge
from eraleader.official_dart_vintage_delivery import (
    audit_dart_cfs_vintages,render_dart_cfs_vintages,
    write_dart_cfs_vintage_sidecar,
)


def pinned_market_snapshot(fx,packs,cached):
    captures=[]
    for year in (2023,2024,2025):
        original=capture(fx,year=year,nonce=year-2023,amount=str(10000+year))
        captures.append(original)
        reg(fx,*original,seconds=20+year-2023)
    decision=(datetime(2026,10,12,14,tzinfo=timezone.utc)).isoformat()
    snap=bridge.build_official_price_snapshot(
        kospi=packs[0],kosdaq=packs[1],
        as_of="2026-10-12",decision_at=decision,top=2,
        dart_directory=fx["directory"],
        dart_financial_receipts=tuple(captures),
    )
    assert snap["official_financial_research_observations"][0]["observed_dart_corp_code"]=="00126380"
    return snap,captures


def test_prospective_three_fy_registry_to_existing_price_watch_dashboard(
        packs,cached,fx,tmp_path):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    report=audit_dart_cfs_vintages(snap,fx["db"])
    assert report["annual_report_vintages_checked"]==3
    assert report["asof_available_vintages"]==3
    assert report["needs_revision_reconciliation"]==0
    assert report["official_leaders"]==0
    assert report["historical_first_publication_certified"] is False
    assert all(row["registered_vintages_available"]==1
               for row in report["observations"])
    page=render_dart_cfs_vintages(report)
    assert "005930" in page and "최초 등록시각" in page
    assert "투자" not in page or "순위" in page
    target=tmp_path/"fresh_watch"
    result=bridge.run_official_research(snap,target,vintage_ledger=fx["db"])
    assert result["dart_vintage_html"]
    assert result["dart_vintage_json"]
    assert "DART 최초 등록·정정 상태" in (target/"site"/"kr.html").read_text()
    assert "dart_cfs_vintages.html" in (target/"site"/"index.html").read_text()
    posted=json.loads((target/"dart_cfs_vintages.json").read_text())
    assert posted["asof_available_vintages"]==3
    assert result["messages_sent"]==0 and result["official_leaders"]==0
    assert all(row["total_score_100"] is None for row in snap["rows"])


def test_future_registration_absent_from_older_asof_snapshot(fx,packs,cached):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    snap["official_api_evidence"]["decision_at"]="2026-10-12T12:00:10+00:00"
    report=audit_dart_cfs_vintages(snap,fx["db"])
    assert report["asof_available_vintages"]==0
    assert all(row["status"]=="NO_PIT_VINTAGE_AS_OF" for row in report["observations"])


def test_different_receipt_pin_must_not_claim_same_financial_lineage(fx,packs,cached):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    snap["official_api_evidence"]["dart_financial_first_receipts"][0][
        "first_receipt_sha256"]="f"*64
    with pytest.raises(ValueError,match="mismatch"):
        audit_dart_cfs_vintages(snap,fx["db"])


def test_same_accession_changed_after_first_known_is_visible_but_not_automatically_selected(
        fx,packs,cached):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    updated=capture(fx,year=2025,nonce=5,amount="30,000")
    reg(fx,*updated,seconds=55)
    report=audit_dart_cfs_vintages(snap,fx["db"])
    assert report["needs_revision_reconciliation"]==1
    year2025=[row for row in report["observations"] if row["fiscal_year"]==2025][0]
    assert year2025["status"]=="SAME_ACCESSION_CHANGED_UNVERIFIED"
    assert year2025["revision_or_receipt_conflict"] is True
    assert "정정 검토 필요" in render_dart_cfs_vintages(report)


def test_vintage_sidecar_pin_seal_fail_closed_and_no_overwrite(fx,packs,cached,tmp_path):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    report=audit_dart_cfs_vintages(snap,fx["db"])
    site=tmp_path/"site";site.mkdir()
    paths=write_dart_cfs_vintage_sidecar(report,site)
    assert all(p.is_file() for p in paths)
    expected=paths[1].read_bytes()
    with pytest.raises(FileExistsError):
        write_dart_cfs_vintage_sidecar(report,site)
    assert expected==paths[1].read_bytes()
    report["official_leaders"]=1
    with pytest.raises(ValueError,match="modified or promoted"):
        render_dart_cfs_vintages(report)


def test_corrupt_registry_blocks_dashboard_publication(fx,packs,cached,tmp_path):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    with sqlite3.connect(fx["db"]) as db:
        db.execute("DROP TRIGGER dart_cfs_no_update")
        db.execute("UPDATE dart_cfs_vintages SET event_payload='{}' WHERE seq=1")
        db.commit()
    with pytest.raises(ValueError,match="corrupted"):
        audit_dart_cfs_vintages(snap,fx["db"])
    assert not (tmp_path/"site"/"dart_cfs_vintages.html").exists()


def test_empty_receipt_source_keeps_watch_without_fake_coverage(fx,packs,cached):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    snap.pop("official_financial_research_observations")
    snap["official_api_evidence"]["dart_financial_first_receipts"]=[]
    report=audit_dart_cfs_vintages(snap,fx["db"])
    assert report["annual_report_vintages_checked"]==0
    assert report["asof_available_vintages"]==0
    assert report["official_leaders"]==0


def test_correction_conflict_blocks_output_before_watch_sqlite_is_written(
        fx,packs,cached,tmp_path):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    updated=capture(fx,year=2025,nonce=5,amount="31,000")
    reg(fx,*updated,seconds=50)
    output=tmp_path/"must_not_publish_incomplete_data"
    with pytest.raises(ValueError,match="revised FY CFS"):
        bridge.run_official_research(snap,output,vintage_ledger=fx["db"])
    assert not output.exists()
    assert not (tmp_path/"must_not_publish_incomplete_data"/"state.sqlite").exists()


def test_missing_asof_registration_blocks_before_dashboard_write(
        fx,packs,cached,tmp_path):
    snap,_=pinned_market_snapshot(fx,packs,cached)
    snap["official_api_evidence"]["decision_at"]="2026-10-12T12:00:10Z"
    output=tmp_path/"too_early_to_know_annual_cfs"
    with pytest.raises(ValueError,match="Unregistered"):
        bridge.run_official_research(snap,output,vintage_ledger=fx["db"])
    assert not output.exists()
