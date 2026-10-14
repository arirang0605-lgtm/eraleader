"""6_5 schedule preparation for KR marketwide research refresh (no install)."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import plistlib
import stat
import subprocess
import sys

import pytest

from eraleader.marketwide_schedule import generate_marketwide_plist, LABEL
from test_marketwide_auto_refresh import fixture, put
from test_official_partial_factor_bridge import source

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"generate_marketwide_schedule.py"


def schedule_fixture(tmp_path):
    sources,project=fixture(tmp_path)
    scripts=project/"scripts"
    scripts.mkdir()
    # An actual isolated, executable test project rather than trusting a
    # non-existent scheduled runner path.
    (scripts/"render_local_operations.py").write_text(
        "import sys,runpy\n"
        +f"sys.path.insert(0,{str(ROOT/'src')!r})\n"
        +f"runpy.run_path({str(ROOT/'scripts'/'render_local_operations.py')!r},run_name='__main__')\n"
    )
    return sources,project


def make(tmp_path, *, hour=18, minute=40):
    sources, project=schedule_fixture(tmp_path)
    put(sources,"day",day="2026-10-13")
    plist=project/"output"/"marketwide_daily.plist"
    data=generate_marketwide_plist(
        project=project,source_root=sources,destination=plist,
        hour=hour,minute=minute)
    return sources,project,plist,data


def test_prepared_plist_is_weekday_kst_research_only(tmp_path):
    sources,project,plist,result=make(tmp_path)
    assert result["status"]=="KR_MARKETWIDE_SCHEDULE_PREPARED_NOT_INSTALLED"
    assert not result["auto_job_installed"] and not result["orders_enabled"]
    assert (stat.S_IMODE(plist.stat().st_mode) & 0o077)==0
    assert result["owner_only_access"] is True
    raw=plistlib.loads(plist.read_bytes())
    assert raw["Label"]==LABEL
    assert raw["RunAtLoad"] is False
    assert raw["ProcessType"]=="Background"
    assert raw["StartCalendarInterval"]==[
        {"Weekday":day,"Hour":18,"Minute":40} for day in range(1,6)]
    arguments=raw["ProgramArguments"]
    assert arguments[2:]==["--project",str(project),
                           "--marketwide-source-root",str(sources)]
    assert "run_local_scheduled" not in " ".join(arguments)
    assert "order" not in " ".join(arguments)


def test_prepared_job_manual_execution_generates_search_link_without_api(tmp_path):
    sources,project,plist,_=make(tmp_path)
    args=plistlib.loads(plist.read_bytes())["ProgramArguments"]
    run=subprocess.run(args,capture_output=True,text=True,check=True)
    info=json.loads(run.stdout)
    assert info["status"]=="LOCAL_OPERATIONS_OVERVIEW_RESEARCH_ONLY"
    assert info["marketwide_refresh_status"]=="KR_MARKETWIDE_SEARCH_REFRESHED"
    assert info["marketwide_observation_session"]=="2026-10-13"
    assert info["external_api_calls"]==0
    assert info["live_notifications_sent"]==0
    assert (project/"output"/"operations"/"site"/"index.html").is_file()
    repeat=subprocess.run(args,capture_output=True,text=True,check=True)
    assert json.loads(repeat.stdout)["marketwide_refresh_status"]=="KR_MARKETWIDE_SEARCH_ALREADY_CURRENT"


def test_auto_watch_schedule_executes_early_watch_daily_brief(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    snapshot=sources/"verified"
    snapshot.mkdir()
    source(snapshot, market_date=datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(), clock=datetime.now(ZoneInfo("Asia/Seoul")))
    plist=project/"output"/"auto_watch.plist"
    result=generate_marketwide_plist(
        project=project,source_root=sources,destination=plist,auto_watch=True)
    assert result["watch_daily_pipeline_enabled"] is True
    assert result["annual_cfs_source_enabled"] is False
    args=plistlib.loads(plist.read_bytes())["ProgramArguments"]
    assert args[-1]=="--marketwide-watch-auto"
    run=subprocess.run(args,capture_output=True,text=True,check=True)
    report=json.loads(run.stdout)
    assert report["marketwide_auto_watch_status"]=="PUBLISHED"
    assert report["watch_daily_brief_status"]=="PUBLISHED"
    assert report["marketwide_auto_watch_candidates"]==2
    assert report["marketwide_auto_watch_orders"]==0
    assert report["marketwide_auto_watch_external_api_calls"]==0
    repeat=json.loads(subprocess.run(args,capture_output=True,text=True,check=True).stdout)
    assert repeat["marketwide_auto_watch_status"]=="ALREADY_PUBLISHED"
    assert repeat["watch_daily_brief_status"]=="ALREADY_PUBLISHED"

def test_auto_watch_schedule_supports_verified_cfs_root(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    cfs=tmp_path/"original_dart_cfs"
    cfs.mkdir()
    destination=project/"output"/"cfs_auto.plist"
    result=generate_marketwide_plist(
        project=project,source_root=sources,destination=destination,
        auto_watch=True,dart_cfs_root=cfs)
    args=plistlib.loads(destination.read_bytes())["ProgramArguments"]
    assert args[-3:]==["--marketwide-watch-auto",
                       "--marketwide-watch-dart-cfs-root",str(cfs)]
    assert result["annual_cfs_source_enabled"] is True
    with pytest.raises(ValueError,match="DART_REQUIRES_AUTO_WATCH"):
        generate_marketwide_plist(
            project=project,source_root=sources,
            destination=project/"output"/"without_auto.plist",dart_cfs_root=cfs)
    assert not (project/"output"/"without_auto.plist").exists()

def test_cli_auto_watch_prepares_plist_without_install(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    dest=project/"output"/"cli_watch.plist"
    run=subprocess.run([sys.executable,str(SCRIPT),"--project",str(project),
                        "--source-root",str(sources),"--out",str(dest),
                        "--auto-watch"],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)["watch_daily_pipeline_enabled"] is True
    assert "--marketwide-watch-auto" in plistlib.loads(dest.read_bytes())["ProgramArguments"]

def test_plist_existing_path_never_overwritten(tmp_path):
    sources,project,plist,_=make(tmp_path)
    before=plist.read_bytes()
    with pytest.raises(ValueError,match="NEW_OUTPUT"):
        generate_marketwide_plist(
            project=project,source_root=sources,destination=plist)
    assert plist.read_bytes()==before


@pytest.mark.parametrize("hour,minute",[(24,10),(-1,20),(18,60),(18,-1),(True,0),(1,1.0)])
def test_illegal_schedule_time_rejected(tmp_path,hour,minute):
    sources,project=schedule_fixture(tmp_path)
    destination=project/"output"/"wrong.plist"
    with pytest.raises(ValueError,match="INVALID_LOCAL_TIME"):
        generate_marketwide_plist(
            project=project,source_root=sources,destination=destination,
            hour=hour,minute=minute)
    assert not destination.exists()


def test_reject_plist_outside_project_output(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    outside=tmp_path/"outside.plist"
    with pytest.raises(ValueError,match="NEW_OUTPUT"):
        generate_marketwide_plist(project=project,source_root=sources,
                                  destination=outside)
    assert not outside.exists()


def test_reject_symlink_source_root_and_symlink_target(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    alias=tmp_path/"alias"
    alias.symlink_to(sources,target_is_directory=True)
    with pytest.raises(ValueError,match="UNSAFE_DIRECTORY"):
        generate_marketwide_plist(project=project,source_root=alias,
                                  destination=project/"output"/"new.plist")
    external=tmp_path/"outside.plist"
    external.write_text("unchanged")
    target=project/"output"/"linked.plist"
    target.symlink_to(external)
    with pytest.raises(ValueError,match="NEW_OUTPUT"):
        generate_marketwide_plist(project=project,source_root=sources,
                                  destination=target)
    assert external.read_text()=="unchanged"


def test_cli_prepares_only_and_repeated_invocation_fails(tmp_path):
    sources,project=schedule_fixture(tmp_path)
    out=project/"output"/"cli.plist"
    command=[sys.executable,str(SCRIPT),"--project",str(project),
             "--source-root",str(sources),"--out",str(out)]
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)["launchd_loaded"] is False
    repeat=subprocess.run(command,capture_output=True,text=True)
    assert repeat.returncode==2
    assert repeat.stderr.strip()=="KR_MARKETWIDE_SCHEDULE_NOT_PREPARED"
    assert plistlib.loads(out.read_bytes())["Label"]==LABEL
