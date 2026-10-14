"""No-lookahead KR share-flow / marcap volume date overlap gate."""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import json
import subprocess
import sys

import pandas as pd
import pytest

from test_marketwide_flow_batch import sources, FakeClient, capture, NOW
from eraleader.marketwide_volume_alignment import (
    audit_volume_alignment,publish_volume_alignment
)
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from eraleader.official_company_explorer import canonical


def make_cache(tmp_path, *,end="2026-10-02",codes=("000100","000101","000102")):
    root=tmp_path/"readonly_price_vault"
    dest=root/"datasets/external_validation/marcap/data"
    dest.mkdir(parents=True,exist_ok=True)
    days=pd.bdate_range("2026-08-17",end)
    data=[]
    for code in codes:
        for i,day in enumerate(days):
            close=1000.+i
            data.append({
                "Code":code,"Name":"KR Price","Date":day,"Market":"KOSPI",
                "Open":close,"High":close*1.01,"Low":close*.99,
                "Close":close,"Volume":1000.+i,
                "Amount":close*(1000+i),"Marcap":1e9,
            })
    pd.DataFrame(data).to_parquet(dest/"marcap-2026.parquet",index=False)
    return root


def record_three(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=3)
    return project,market


def test_stale_cache_never_aligns_old_volume_with_recent_flow(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-02")
    result=audit_volume_alignment(
        marketwide=market,project=project,legacy_root=root,clock=NOW)
    assert result["flow_stocks"]==3
    assert result["source_session_price_cache_matched"]==0
    assert result["flow_volume_fully_aligned_stocks"]==0
    assert result["flow_score_10_available"]==0
    assert result["orders_enabled"] is False
    assert result["local_cache_sha256"]
    for item in result["rows"]:
        assert item["cache_last_price_session"]=="2026-10-02"
        assert item["cache_matches_source_session"] is False
        assert item["exact_flow_volume_5_20_ratio"] is None
        assert item["alignment_status"]=="PRICE_CACHE_NOT_AT_KRX_SESSION"


def test_matching_cache_does_not_imply_same_investor_session_dates(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-13")
    report=audit_volume_alignment(
        marketwide=market,project=project,legacy_root=root,clock=NOW)
    assert report["source_session_price_cache_matched"]==3
    assert report["flow_volume_fully_aligned_stocks"]==0
    for item in report["rows"]:
        bars=item["cache_20_observed_volume"]
        assert bars is not None
        assert bars["cache_last_20_volume_observations"]>bars["cache_last_5_volume_observations"]
        assert bars["cache_volume_day"]=="2026-10-13"
        assert bars["denominator_is_investor_row_aligned"] is False
        assert item["alignment_status"]=="NO_DATED_INVESTOR_ROWS_TO_MATCH"
        assert item["exact_flow_volume_5_20_ratio"] is None


def test_cache_missing_one_security_stays_na(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-13",codes=("000100","000101"))
    report=audit_volume_alignment(
        marketwide=market,project=project,legacy_root=root,clock=NOW)
    assert report["source_session_price_cache_matched"]==2
    absent=next(x for x in report["rows"] if x["security_id"]=="000102")
    assert absent["cache_last_price_session"] is None
    assert absent["alignment_status"]=="PRICE_CACHE_MISSING_SECURITY"


def test_missing_cache_all_returns_missing_without_false_score(tmp_path):
    project,market=record_three(tmp_path)
    root=tmp_path/"empty_cache"
    root.mkdir()
    report=audit_volume_alignment(
        marketwide=market,project=project,legacy_root=root,clock=NOW)
    assert report["local_cache_sha256"] is None
    assert report["source_session_price_cache_matched"]==0
    assert report["flow_volume_fully_aligned_stocks"]==0
    assert report["flow_score_10_available"]==0


def test_idempotent_publication_preserves_sha_and_versions_changed_cache(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-02")
    first=publish_volume_alignment(marketwide=market,project=project,
                                   legacy_root=root,clock=NOW)
    assert first["status"]=="PUBLISHED"
    file=Path(first["file"])
    bytes_before=file.read_bytes()
    replay=publish_volume_alignment(marketwide=market,project=project,
                                    legacy_root=root,clock=NOW)
    assert replay["status"]=="ALREADY_PUBLISHED"
    assert file.read_bytes()==bytes_before
    root=make_cache(tmp_path,end="2026-10-13")
    second=publish_volume_alignment(marketwide=market,project=project,
                                    legacy_root=root,clock=NOW)
    assert second["status"]=="PUBLISHED"
    assert second["site"]!=first["site"]
    assert file.read_bytes()==bytes_before


def test_tampered_existing_page_and_cache_symlink_blocked(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-02")
    first=publish_volume_alignment(marketwide=market,project=project,
                                   legacy_root=root,clock=NOW)
    index=Path(first["site"])
    index.write_bytes(index.read_bytes()+b"BAD")
    with pytest.raises(ValueError,match="EXISTING_CONFLICT"):
        publish_volume_alignment(marketwide=market,project=project,
                                 legacy_root=root,clock=NOW)
    linked=tmp_path/"linked_cache"
    linked.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match="ROOT_UNSAFE"):
        audit_volume_alignment(marketwide=market,project=project,
                               legacy_root=linked,clock=NOW)


def test_operations_link_is_checked_and_broken_page_hidden(tmp_path):
    project,market=record_three(tmp_path)
    root=make_cache(tmp_path,end="2026-10-02")
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_volume_alignment"] is None
    report=publish_volume_alignment(marketwide=market,project=project,
                                    legacy_root=root,clock=NOW)
    view=audit_local_operations(project,clock=NOW)
    link=view["kr_marketwide_volume_alignment"]
    assert link["flow_stocks"]==3
    assert link["cache_session_matched"]==0
    assert link["aligned"]==0 and link["orders"]==0
    assert "기관·외국인 수급과 거래량 날짜 일치 보기" in render_operations_overview(view)
    link["href"]="../../../../untrusted"
    with pytest.raises(ValueError,match="Unsafe marketwide volume"):
        render_operations_overview(view)
    Path(report["site"]).write_bytes(b"bad")
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_volume_alignment"] is None


def test_cli_volume_alignment_no_network_and_opt_in_requires_source(tmp_path):
    _,project,market=sources(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    run=subprocess.run([
        sys.executable,str(script),"--project",str(project),
        "--marketwide-volume-alignment"],capture_output=True,text=True)
    assert run.returncode!=0
    assert not (project/"output"/"marketwide_volume_alignment").exists()
    runner=Path(__file__).resolve().parents[1]/"scripts"/"run_marketwide_volume_alignment.py"
    root=tmp_path/"empty"
    root.mkdir()
    other=subprocess.run([
        sys.executable,str(runner),"--project",str(project),
        "--marketwide-report",str(market),"--legacy-root",str(root)],
        capture_output=True,text=True)
    assert other.returncode==0,other.stderr
    obj=json.loads(other.stdout)
    assert obj["orders"]==0 and obj["flow_stocks"]==0
    assert obj["flow_volume_aligned"]==0
