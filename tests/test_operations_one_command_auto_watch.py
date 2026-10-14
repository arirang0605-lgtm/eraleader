"""Existing operations one-command KR source -> factors -> WATCH -> daily brief.

Integration tests cover the positive runnable path and ordinary missing inputs;
they do not require an extra validation service or a real API call.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

from eraleader.official_company_explorer import canonical
from eraleader.official_partial_factor_bridge import derive_partial_factor_input
from eraleader.factor_selection_pipeline import _read_assessment
from eraleader.operations_overview import audit_local_operations
from test_marketwide_auto_refresh import fixture, put
from test_official_partial_factor_bridge import source

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
NOW=datetime.now(timezone.utc)


def cli(project,root,*extra):
    run=subprocess.run(
        [sys.executable,str(SCRIPT),"--project",str(project),
         "--marketwide-source-root",str(root),"--marketwide-watch-auto",*extra],
        capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout)
    assert result["marketwide_auto_watch_orders"]==0
    assert result["marketwide_auto_watch_external_api_calls"]==0
    return result


def prepared(tmp_path):
    root,project=fixture(tmp_path)
    target=root/"current"
    target.mkdir()
    report,info=source(target,market_date=NOW.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),clock=NOW)
    return root,project,report,info


def test_one_command_auto_builds_factor_watch_and_daily_brief_from_source(tmp_path):
    root,project,src,info=prepared(tmp_path)
    result=cli(project,root)
    assert result["marketwide_auto_watch_status"]=="PUBLISHED"
    assert result["marketwide_auto_watch_candidates"]==2
    assert result["marketwide_auto_watch_factor_file"].endswith("_PARTIAL_500.json")
    assert result["watch_daily_brief_status"]=="PUBLISHED"
    assert result["watch_daily_brief_candidates"]==2
    dashboard=audit_local_operations(project)
    assert dashboard["kr_early_leader_watch"]["count"]==2
    assert dashboard["kr_watch_daily_brief"]["watch_count"]==2
    assert "WATCH 일일 수익성 변화 보고서 보기" in (
        project/"output"/"operations"/"site"/"index.html").read_text()
    before=Path(result["marketwide_auto_watch_factor_file"]).read_bytes()
    replay=cli(project,root)
    assert replay["marketwide_auto_watch_status"]=="ALREADY_PUBLISHED"
    assert replay["watch_daily_brief_status"]=="ALREADY_PUBLISHED"
    assert before==Path(replay["marketwide_auto_watch_factor_file"]).read_bytes()


def test_one_command_prefers_existing_same_source_flow_snapshot(tmp_path):
    root,project,src,info=prepared(tmp_path)
    base=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    old=Path(base["input_file"])
    factor=_read_assessment(old)
    factor["factor_rows"][0]["components"]["flow"]=7.3
    factor["factor_rows"][0]["factor_receipts"]["flow"]={
        "sha256":"a"*64,
        "available_at_utc":"2026-10-14T01:00:00+00:00",
        "provider":"LOCAL_FLOW_RESEARCH_UNCERTIFIED",
    }
    factor.pop("content_sha256")
    factor["content_sha256"]=sha256(canonical(factor)).hexdigest()
    extra=old.parent/(old.name.replace("_PARTIAL_500.json","_FLOWV1_test.json"))
    extra.write_bytes(canonical(factor)+b"\n")
    result=cli(project,root)
    assert Path(result["marketwide_auto_watch_factor_file"])==extra
    from eraleader.early_leader_watch_queue import _validated
    path=next((project/"output"/"early_leader_watch_queue").glob("KR_*/watch_queue.json"))
    watch=_validated(path)
    row=next(x for x in watch["review_queue"] if x["security_id"]=="005930")
    assert row["flow_research_10"]==7.3
    assert row["industry_and_competitive_score_20_available"] is False
    assert row["investment_rank"] is None


def test_old_source_reports_hold_without_making_fictitious_new_watch(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"older",day=(NOW.astimezone(ZoneInfo("Asia/Seoul")).date()-timedelta(days=7)).isoformat())
    result=cli(project,root)
    assert result["marketwide_auto_watch_status"]=="NO_FRESH_VERIFIED_SOURCE"
    assert result["marketwide_auto_watch_candidates"]==0
    assert "watch_daily_brief_status" not in result
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))
    assert not list((project/"output").glob("early_watch_daily_briefs/KR_*"))


def test_no_market_source_reports_no_data_and_no_orders(tmp_path):
    root,project=fixture(tmp_path)
    result=cli(project,root)
    assert result["marketwide_auto_watch_status"]=="NO_FRESH_VERIFIED_SOURCE"
    assert result["marketwide_auto_watch_candidates"]==0
    assert result["marketwide_auto_watch_factor_file"] is None
    assert result["official_leader_promotions"]==0


def test_auto_rejects_manual_conflict_and_missing_source(tmp_path):
    root,project=fixture(tmp_path)
    first=subprocess.run([sys.executable,str(SCRIPT),"--project",str(project),
                          "--marketwide-watch-auto"],capture_output=True,text=True)
    assert first.returncode!=0
    second=subprocess.run([sys.executable,str(SCRIPT),"--project",str(project),
                           "--marketwide-source-root",str(root),
                           "--marketwide-watch-auto",
                           "--watch-daily-brief-manifest",str(project/"miss.json")],
                          capture_output=True,text=True)
    assert second.returncode!=0
    assert not list((project/"output").glob("early_watch_daily_briefs/KR_*"))
