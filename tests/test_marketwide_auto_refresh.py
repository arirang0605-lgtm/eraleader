"""6_2 automatic newest-available source refresh, no external calls or orders."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from eraleader.marketwide_auto_refresh import refresh_latest_marketwide
from eraleader.official_company_explorer import canonical
from eraleader.operations_overview import audit_local_operations
from test_marketwide_live_search import sample, repin

UTC=timezone.utc
NOW=datetime(2026,10,14,3,tzinfo=UTC)


def fixture(tmp_path):
    source_root=tmp_path/"sources"
    source_root.mkdir()
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    return source_root, project


def put(root,name,*,day="2026-10-08",score=True,broken=False):
    report=sample()
    report["market_session"]=day
    for row in report["securities"]:
        row["market_session"]=day
    if not score:
        row=report["securities"][0]
        row["two_factor_research_50"]=None
        row["two_factor_research_rank"]=None
        report["two_factor_research_evaluable"]=0
        report["two_factor_research_top20"]=[]
    report=repin(report)
    folder=root/name
    folder.mkdir()
    f=folder/"marketwide_kr.json"
    f.write_bytes(canonical(report)+b"\n")
    if broken:
        f.write_bytes(f.read_bytes().replace(b'"official_krx_observed":3',b'"official_krx_observed":4'))
    return f


def refresh(source_root,project,*,day="2026-10-14",now=NOW):
    return refresh_latest_marketwide(source_root=source_root,project=project,
                                     request_day=day,clock=now)


def test_latest_market_session_beats_more_complete_previous_and_repeat_is_idempotent(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"older",day="2026-10-08")
    put(root,"newer",day="2026-10-13",score=False)
    result=refresh(root,project)
    assert result["status"]=="KR_MARKETWIDE_SEARCH_REFRESHED"
    assert result["source_market_session"]=="2026-10-13"
    assert result["research_50_scored"]==0
    assert result["verified_candidates"]==2
    output=Path(result["site"])
    before=sha256(output.read_bytes()).hexdigest()
    again=refresh(root,project)
    assert again["status"]=="KR_MARKETWIDE_SEARCH_ALREADY_CURRENT"
    assert again["site"]==result["site"]
    assert before==sha256(output.read_bytes()).hexdigest()
    assert len(list((project/"output").glob("marketwide_kr_search_*")))==1
    nav=audit_local_operations(project,clock=NOW)["kr_marketwide_search"]
    assert nav["market_session"]=="2026-10-13"


def test_same_session_prefers_more_complete_data_and_keeps_prior_immutable(tmp_path):
    root,project=fixture(tmp_path)
    less=put(root,"older",day="2026-10-13",score=False)
    first=refresh(root,project)
    original=Path(first["site"]).read_bytes()
    put(root,"enhanced",day="2026-10-13",score=True)
    second=refresh(root,project)
    assert second["status"]=="KR_MARKETWIDE_SEARCH_REFRESHED"
    assert second["research_50_scored"]==1
    assert second["site"]!=first["site"]
    assert Path(first["site"]).read_bytes()==original
    nav=audit_local_operations(project,clock=NOW)["kr_marketwide_search"]
    assert nav["partial_research_scored"]==1
    assert nav["href"].endswith(Path(second["site"]).parent.name+"/index.html")


def test_broken_newest_ignored_with_explicit_rejected_counter(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"valid",day="2026-10-08")
    put(root,"broken",day="2026-10-13",broken=True)
    result=refresh(root,project)
    assert result["source_market_session"]=="2026-10-08"
    assert result["stale_warning"] is True
    assert result["rejected_candidates"]==1
    assert result["verified_candidates"]==1


def test_no_valid_source_keeps_prior_site_untouched(tmp_path):
    root,project=fixture(tmp_path)
    src=put(root,"valid",day="2026-10-08")
    result=refresh(root,project)
    before=Path(result["site"]).read_bytes()
    src.unlink()
    status=refresh(root,project)
    assert status["status"]=="NO_VERIFIED_KR_MARKETWIDE_SOURCE"
    assert Path(result["site"]).read_bytes()==before


def test_corrupted_existing_artifact_blocks_instead_of_overwriting(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"valid",day="2026-10-08")
    report=refresh(root,project)
    target=Path(report["site"])
    target.write_bytes(target.read_bytes()+b"\n<!-- changed -->")
    digest=sha256(target.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="EXISTING_OUTPUT_MISMATCH"):
        refresh(root,project)
    assert sha256(target.read_bytes()).hexdigest()==digest


def test_foreign_owned_linked_source_folder_never_followed(tmp_path):
    root,project=fixture(tmp_path)
    real=put(root,"actual",day="2026-10-08")
    alias=root/"alias"
    alias.symlink_to(real.parent,target_is_directory=True)
    result=refresh(root,project)
    assert result["verified_candidates"]==1
    linked_source=tmp_path/"source_alias"
    linked_source.symlink_to(root,target_is_directory=True)
    with pytest.raises(ValueError,match="UNSAFE_DIRECTORY"):
        refresh(linked_source,project)


def test_next_day_same_source_recalculates_stale_warning_but_no_new_price(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"valid",day="2026-10-13")
    today=refresh(root,project)
    day_after=refresh(root,project,day="2026-10-16",
                      now=datetime(2026,10,16,3,tzinfo=UTC))
    assert day_after["source_market_session"]==today["source_market_session"]
    assert day_after["requested_day"]=="2026-10-16"
    assert day_after["site"]!=today["site"]
    assert day_after["stale_warning"] is True
    assert Path(today["site"]).exists()


def test_optional_operations_command_refreshes_before_render(tmp_path):
    root,project=fixture(tmp_path)
    put(root,"current",day="2026-10-13")
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    env=dict(os.environ)
    env["PYTHONPATH"]=str(script.parents[1]/"src")
    run=subprocess.run([sys.executable,str(script),"--project",str(project),
                        "--marketwide-source-root",str(root)],
                       env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    report=json.loads(run.stdout)
    assert report["marketwide_refresh_status"] in (
        "KR_MARKETWIDE_SEARCH_REFRESHED","KR_MARKETWIDE_SEARCH_ALREADY_CURRENT")
    assert report["marketwide_observation_session"]=="2026-10-13"
    page=(project/"output"/"operations"/"site"/"index.html").read_text()
    assert "한국시장 전체 종목 검색 열기" in page
    assert "실전 적중률 N/A" in page
