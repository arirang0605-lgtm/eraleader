"""KR latest official research WATCH -> receiver-neutral outbox (no orders)."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys
from copy import deepcopy

import pytest

from eraleader.marketwide_handoff_bridge import publish_latest_marketwide_handoff
from eraleader.strategy_handoff import verify_handoff
from eraleader.official_company_explorer import canonical
from eraleader.marketwide_auto_refresh import refresh_latest_marketwide
from test_marketwide_live_search import sample, repin
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,3,tzinfo=timezone.utc)


def put_twenty(root:Path, label:str, session:str="2026-10-13",start:int=100,
               *,truncate:bool=False, later_source:bool=False):
    raw=sample()
    template=raw["securities"][0]
    securities=[]
    for i in range(20 if not truncate else 19):
        item=deepcopy(template)
        item["security_id"]=f"{start+i:06d}"
        item["name"]=f"연구가격관찰{i:02d}"
        item["price_top20_watch_rank"]=i+1
        item["price_strength_25"]=float(25-i/10)
        if i:
            item["revenue_yoy"]=None
            item["operating_income_yoy"]=None
            item["revenue_growth_acceleration"]=None
            item["two_factor_research_50"]=None
            item["two_factor_research_rank"]=None
            item["industry_code"]=None
        item["market_session"]=session
        securities.append(item)
    raw["securities"]=securities
    raw["market_session"]=session
    raw["official_krx_observed"]=len(securities)
    raw["financial_factors_observed"]=1
    raw["industry_factors_observed"]=1
    raw["local_price_lookback_evaluable"]=len(securities)
    raw["two_factor_research_top20"]=[{
        "security_id":securities[0]["security_id"],
        "research_order":1,"observed_score_50":42.5,
    }]
    if later_source:
        raw["built_at_utc"]="2026-10-14T01:00:00+00:00"
    raw=repin(raw)
    path=root/label
    path.mkdir()
    file=path/"marketwide_kr.json"
    file.write_bytes(canonical(raw)+b"\n")
    return file


def deliver(root,project,day="2026-10-14",now=NOW):
    return publish_latest_marketwide_handoff(
        source_root=root,project=project,request_day=day,clock=now)


def test_real_research_watchlist_delivered_without_any_formal_selection(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"recent")
    result=deliver(root,project)
    assert result["status"]=="KR_LATEST_PRICE_WATCH_RESEARCH_HANDOFF"
    assert result["watchlist_count"]==20
    assert result["selected_count"]==result["state_changes"]==result["orders"]==0
    assert result["execution_authority"] is False
    assert result["historical_pit_certified"] is False
    out=Path(result["outbox_file"])
    assert out.is_file()
    payload=verify_handoff(out,expected_market="KR")
    assert len(payload["research_watchlist"])==20
    assert payload["selected_candidates"]==[] and payload["state_changes"]==[]
    assert payload["source_sha256"]==result["source_sha256"]
    assert payload["order_instruction"] is False
    assert all(x["selection_state"]=="WATCH" and x["score_100"] is None
               for x in payload["research_watchlist"])
    assert Path(result["search_site"]).is_file()


def test_same_source_new_day_does_not_rewrite_original_event_or_claim_fresh(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"recent")
    first=deliver(root,project)
    out=Path(first["outbox_file"])
    oldbytes=out.read_bytes()
    replay=deliver(root,project)
    assert replay["delivery_status"]=="ALREADY_DELIVERED"
    future=deliver(root,project,day="2026-10-16",
                   now=datetime(2026,10,16,3,tzinfo=timezone.utc))
    assert future["data_stale"] is True
    assert future["delivery_status"]=="ALREADY_DELIVERED"
    assert out.read_bytes()==oldbytes
    assert len(list(out.parent.glob("KR_*.json")))==1
    original=verify_handoff(out,expected_market="KR")
    assert original["as_of"]=="2026-10-14"


def test_revised_research_snapshot_gets_its_own_version_and_preserves_old(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"initial",start=100)
    first=deliver(root,project)
    original=Path(first["outbox_file"]).read_bytes()
    put_twenty(root,"newer",start=200,later_source=True)
    newer=deliver(root,project)
    assert newer["outbox_file"]!=first["outbox_file"]
    assert Path(first["outbox_file"]).read_bytes()==original
    assert verify_handoff(Path(newer["outbox_file"]))["selection_count"]==0


def test_incomplete_price_watch_is_not_exported_as_leader_selection(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"partial",truncate=True)
    with pytest.raises(ValueError,match="NOT_PRICE_WATCH_ONLY"):
        deliver(root,project)
    assert not list((project/"output").glob("strategy_outbox/KR_*.json"))


def test_source_removed_after_first_export_has_no_new_signal(tmp_path):
    root,project=fixture(tmp_path)
    src=put_twenty(root,"ok")
    first=deliver(root,project)
    immutable=Path(first["outbox_file"]).read_bytes()
    src.unlink()
    missed=deliver(root,project)
    assert missed["status"]=="NO_VERIFIED_KR_MARKETWIDE_SOURCE"
    assert missed["watchlist_count"]==missed["selected_count"]==0
    assert Path(first["outbox_file"]).read_bytes()==immutable


def test_modified_previous_outbox_is_rejected_and_never_replaced(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"valid")
    first=deliver(root,project)
    file=Path(first["outbox_file"])
    file.write_bytes(file.read_bytes()+b"\nTAMPER")
    changed=file.read_bytes()
    with pytest.raises(ValueError):
        deliver(root,project)
    assert file.read_bytes()==changed


def test_existing_outbox_symlink_is_rejected(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"valid")
    other=tmp_path/"outside"
    other.mkdir()
    (project/"output"/"strategy_outbox").symlink_to(other,target_is_directory=True)
    with pytest.raises(ValueError,match="UNSAFE_OUTBOX"):
        deliver(root,project)
    assert not list(other.iterdir())


def test_operations_cli_explicit_outbox_end_to_end(tmp_path):
    root,project=fixture(tmp_path)
    put_twenty(root,"valid")
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-source-root",str(root),"--marketwide-publish-outbox"]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    body=json.loads(result.stdout)
    assert body["marketwide_handoff_watchlist_count"]==20
    assert body["marketwide_handoff_selected_count"]==0
    assert body["marketwide_handoff_orders"]==0
    assert body["marketwide_observation_session"]=="2026-10-13"
    assert len(list((project/"output"/"strategy_outbox").glob("KR_*.json")))==1
    again=subprocess.run(cmd,capture_output=True,text=True)
    assert again.returncode==0,again.stderr
    assert len(list((project/"output"/"strategy_outbox").glob("KR_*.json")))==1


def test_outbox_opt_in_cannot_be_run_without_source_root(tmp_path):
    _,project=fixture(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    result=subprocess.run([sys.executable,str(script),"--project",str(project),
                           "--marketwide-publish-outbox"],
                          capture_output=True,text=True)
    assert result.returncode!=0
    assert not (project/"output"/"strategy_outbox").exists()
