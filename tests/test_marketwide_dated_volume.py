"""Exact dated Kiwoom investor research vs matching local marcap volume."""
from __future__ import annotations
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
import json
import pandas as pd
import pytest

from test_marketwide_flow_batch import sources,FakeClient,capture,NOW
from eraleader.marketwide_dated_flow import capture_dated_flow
from eraleader.marketwide_dated_volume import (
    evaluate_exact_volume,publish_exact_dated_volume,SCHEMA,
)

CODE="000100"


def arranged(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    collected=capture_dated_flow(marketwide=market,project=project,stock_code=CODE,
                                 client=FakeClient(),clock=NOW)
    assert collected["row_count"]==20
    return project,market


def cached(tmp_path, *,count=20, no=()):
    root=tmp_path/"readonly_marcap"
    folder=root/"datasets/external_validation/marcap/data"
    folder.mkdir(parents=True,exist_ok=True)
    last=date(2026,10,13)
    records=[]
    for offset in range(count):
        if offset in no:continue
        current=last-timedelta(days=offset)
        records.append({
            "Code":CODE,"Name":"KR Research","Date":pd.Timestamp(current),
            "Market":"KOSPI","Open":100.,"High":101.,
            "Low":99.,"Close":100.,"Volume":1000.,
            "Amount":100000.,"Marcap":10000000.,
        })
    pd.DataFrame(records).to_parquet(folder/"marcap-2026.parquet",index=False)
    return root


def assess(project,market,root):
    return evaluate_exact_volume(marketwide=market,project=project,
                                  code=CODE,legacy_root=root,clock=NOW)


def test_20_exact_dates_enable_observed_share_to_volume_research_only(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path)
    doc=assess(project,market,root)
    assert doc["schema"]==SCHEMA
    five=doc["periods"]["5"]
    twenty=doc["periods"]["20"]
    assert five["all_observation_dates_matched"] is True
    assert twenty["all_observation_dates_matched"] is True
    assert five["exact_matched_daily_volume_total_shares"]==5000
    assert twenty["exact_matched_daily_volume_total_shares"]==20000
    assert five["foreign_net_shares"]==510
    assert five["foreign_pct_of_matched_daily_volume"]==10.2
    assert twenty["foreign_net_shares"]==2190
    assert twenty["foreign_pct_of_matched_daily_volume"]==10.95
    assert twenty["institution_net_shares"]==-390
    assert twenty["institution_pct_of_matched_daily_volume"]==-1.95
    assert doc["exchange_trading_calendar_certified"] is False
    assert doc["formal_flow_score_10"] is None
    assert doc["orders_enabled"] is False


def test_missing_recent_day_blocks_both_period_ratios(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path,no=(0,))
    doc=assess(project,market,root)
    assert doc["periods"]["5"]["matched_price_volume_days"]==4
    assert doc["periods"]["20"]["matched_price_volume_days"]==19
    assert doc["periods"]["5"]["exact_matched_daily_volume_total_shares"] is None
    assert doc["periods"]["20"]["foreign_pct_of_matched_daily_volume"] is None


def test_missing_older_day_allows_five_but_blocks_twenty(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path,no=(10,))
    result=assess(project,market,root)
    assert result["periods"]["5"]["all_observation_dates_matched"] is True
    assert result["periods"]["20"]["all_observation_dates_matched"] is False
    assert result["periods"]["20"]["institution_pct_of_matched_daily_volume"] is None


def test_dated_flow_not_captured_returns_hold_without_publishing(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    root=cached(tmp_path)
    result=publish_exact_dated_volume(marketwide=market,project=project,
                                      code=CODE,legacy_root=root,clock=NOW)
    assert result["status"]=="EXACT_VOLUME_DATED_EVIDENCE_NOT_AVAILABLE"
    assert result["flow_5_20_aligned"] is False
    assert not (project/"output"/"marketwide_dated_volume").exists()


def test_immutable_versions_and_corrupt_pages_rejected(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path)
    first=publish_exact_dated_volume(marketwide=market,project=project,
                                     code=CODE,legacy_root=root,clock=NOW)
    assert first["status"]=="PUBLISHED"
    assert first["fully_aligned_20"] is True
    assert publish_exact_dated_volume(marketwide=market,project=project,
                                      code=CODE,legacy_root=root,clock=NOW)["status"]=="ALREADY_PUBLISHED"
    original=Path(first["manifest"]).read_bytes()
    root=cached(tmp_path,no=(0,))
    revised=publish_exact_dated_volume(marketwide=market,project=project,
                                       code=CODE,legacy_root=root,clock=NOW)
    assert revised["status"]=="PUBLISHED"
    assert first["manifest"]!=revised["manifest"]
    assert Path(first["manifest"]).read_bytes()==original
    Path(first["site"]).write_bytes(Path(first["site"]).read_bytes()+b"BAD")
    root=cached(tmp_path)
    with pytest.raises(ValueError,match="EXISTING_CONFLICT"):
        publish_exact_dated_volume(marketwide=market,project=project,
                                   code=CODE,legacy_root=root,clock=NOW)


def test_operations_link_only_sha_valid_dated_volume(tmp_path):
    from eraleader.operations_overview import audit_local_operations,render_operations_overview
    project,market=arranged(tmp_path)
    vault=cached(tmp_path)
    empty=audit_local_operations(project,clock=NOW)
    assert empty["kr_marketwide_dated_exact_volume"] is None
    published=publish_exact_dated_volume(
        marketwide=market,project=project,code=CODE,legacy_root=vault,clock=NOW)
    snap=audit_local_operations(project,clock=NOW)
    link=snap["kr_marketwide_dated_exact_volume"]
    assert link["code"]==CODE
    assert link["volume_days_5"]==5 and link["volume_days_20"]==20
    assert "키움 수급 날짜별 거래량 대조 보기" in render_operations_overview(snap)
    snap["kr_marketwide_dated_exact_volume"]["href"]="../../../../passwords"
    with pytest.raises(ValueError,match="Unsafe dated exact"):
        render_operations_overview(snap)
    page=Path(published["site"])
    page.write_bytes(page.read_bytes()+b"BAD")
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_dated_exact_volume"] is None


def test_cli_research_result_when_dated_evidence_absent(tmp_path):
    import subprocess,sys
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    root=cached(tmp_path)
    runner=Path(__file__).resolve().parents[1]/"scripts"/"check_marketwide_dated_volume.py"
    cmd=[sys.executable,str(runner),"--project",str(project),
         "--marketwide-report",str(market),"--code",CODE,
         "--legacy-root",str(root)]
    out=subprocess.run(cmd,capture_output=True,text=True)
    assert out.returncode==0,out.stderr
    payload=json.loads(out.stdout)
    assert payload["status"]=="EXACT_VOLUME_DATED_EVIDENCE_NOT_AVAILABLE"
    assert payload["orders_enabled"] is False
