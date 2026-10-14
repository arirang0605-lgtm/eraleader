"""Functional daily WATCH brief: accepted observation, null, replay, UI."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json
import subprocess
import sys

import pytest
from eraleader.early_watch_daily_brief import (
    build_daily_brief,publish_daily_brief,read_daily_brief,_html
)
from eraleader.early_leader_watch_queue import _validated
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from test_early_leader_watch_queue import setup

NOW=datetime(2026,10,14,9,tzinfo=timezone.utc)


def arranged(tmp_path):
    _,project,market,partial=setup(tmp_path)
    from eraleader.early_leader_watch_queue import publish_early_watch
    result=publish_early_watch(marketwide=market,project=project,
                               factor_input=partial,clock=NOW)
    return project,Path(result["manifest"])


def test_annual_change_classifies_improving_and_weakening_but_no_daily_event(tmp_path):
    project,source=arranged(tmp_path)
    doc=_validated(source,clock=NOW)
    doc["review_queue"][0]["dart_cfs_operating_margin_change_pp"]=13.1399
    doc["review_queue"][1]["dart_cfs_operating_margin_change_pp"]=-4.2
    report=build_daily_brief(doc,clock=NOW)
    assert report["annual_margin_counts"]=={
        "MARGIN_IMPROVING_FY":1,"MARGIN_WEAKENING_FY":1,
        "MARGIN_UNCHANGED_FY":0,"MARGIN_NOT_COMPARABLE":0,
    }
    assert report["report_local_day"]=="2026-10-14"
    assert report["source_market_session"]=="2026-10-13"
    assert report["report_is_same_session_market_update"] is False
    assert report["leader_state_events"]==[]
    assert report["official_leader_confirmations"]==0
    assert report["orders_enabled"] is False
    assert "오늘 발생한 대장주" in _html(report).decode()


def test_daily_brief_actual_file_replays_without_rewriting_first_timestamp(tmp_path):
    project,source=arranged(tmp_path)
    one=publish_daily_brief(watch_manifest=source,project=project,clock=NOW)
    assert one["status"]=="PUBLISHED"
    assert one["watch_rows"]==2 and one["annual_margin_counts"]["MARGIN_NOT_COMPARABLE"]==2
    manifest=Path(one["manifest"])
    before=manifest.read_bytes()
    same=publish_daily_brief(watch_manifest=source,project=project,
                             clock=NOW+timedelta(minutes=25))
    assert same["status"]=="ALREADY_PUBLISHED"
    assert same["manifest"]==one["manifest"]
    assert manifest.read_bytes()==before
    another=publish_daily_brief(watch_manifest=source,project=project,
                                clock=NOW+timedelta(days=1))
    assert another["report_day"]=="2026-10-15"
    assert another["manifest"]!=one["manifest"]
    assert read_daily_brief(manifest,clock=NOW)["watch_rows"]==2


def test_original_watch_tamper_blocks_report_without_new_output(tmp_path):
    project,source=arranged(tmp_path)
    source.write_bytes(source.read_bytes()+b"tampered")
    with pytest.raises(ValueError):
        publish_daily_brief(watch_manifest=source,project=project,clock=NOW)
    assert not list((project/"output").glob("early_watch_daily_briefs/KR_*"))


def test_corrupted_report_page_fails_replay_and_disappears_from_dashboard(tmp_path):
    project,source=arranged(tmp_path)
    result=publish_daily_brief(watch_manifest=source,project=project,clock=NOW)
    assert audit_local_operations(project,clock=NOW)["kr_watch_daily_brief"] is not None
    page=Path(result["site"])
    page.write_bytes(b"WRONG")
    with pytest.raises(ValueError,match="REPLAY_SOURCE_CHANGED"):
        publish_daily_brief(watch_manifest=source,project=project,clock=NOW)
    assert audit_local_operations(project,clock=NOW)["kr_watch_daily_brief"] is None


def test_cli_and_operations_show_real_daily_report_link(tmp_path):
    project,source=arranged(tmp_path)
    scripts=Path(__file__).resolve().parents[1]/"scripts"
    cmd=[sys.executable,str(scripts/"render_local_operations.py"),
         "--project",str(project),"--watch-daily-brief-manifest",str(source)]
    first=subprocess.run(cmd,capture_output=True,text=True)
    assert first.returncode==0,first.stderr
    result=json.loads(first.stdout)
    assert result["watch_daily_brief_status"]=="PUBLISHED"
    assert result["watch_daily_brief_candidates"]==2
    assert result["watch_daily_brief_orders"]==0
    view=audit_local_operations(project)
    item=view["kr_watch_daily_brief"]
    assert item["watch_count"]==2
    assert item["annual_counts"]["MARGIN_NOT_COMPARABLE"]==2
    page=render_operations_overview(view)
    assert "WATCH 일일 수익성 변화 보고서 보기" in page
    assert "오늘 대장주 강화/약화 판정 아님" in page
    again=subprocess.run(cmd,capture_output=True,text=True)
    assert again.returncode==0,again.stderr
    assert json.loads(again.stdout)["watch_daily_brief_status"]=="ALREADY_PUBLISHED"
