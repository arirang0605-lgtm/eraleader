"""Batch selected-stock ka10059 using existing shared read-only adapter."""
from __future__ import annotations

from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import sys
import subprocess

import pytest
from test_marketwide_auto_refresh import fixture
from test_marketwide_handoff_bridge import put_twenty
from eraleader.marketwide_flow_batch import plan_marketwide_flow,capture_marketwide_demo_flow
from eraleader.official_company_explorer import canonical

SHARED=Path("/Volumes/T5DATA/SharedBrokerAPI/src")
if str(SHARED) not in sys.path:
    sys.path.insert(0,str(SHARED))
from shared_broker_api.selected_flow import research_selected_flow

NOW=datetime(2026,10,14,3,20,tzinfo=timezone.utc)

class FakeClient:
    project="eraleader"
    def __init__(self, fail=None):
        self.calls=[]
        self.fail=fail
    def status(self):
        return {"configured":{"demo":True,"real":False},
                "orders_enabled":False}
    def investor_flow_page(self,*,stock_code,day,mode="demo",cursor=None):
        assert mode=="demo" and cursor is None
        self.calls.append(stock_code)
        if stock_code==self.fail:
            raise ValueError("PROVIDER_UNAVAILABLE")
        target=date.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:8]}")
        rows=[]
        for i in range(20):
            dt=(target-timedelta(days=i)).strftime("%Y%m%d")
            rows.append({"dt":dt,"frgnr_invsr":str(100+i),
                         "orgn":str(-10-i)})
        response={"return_code":0,"stk_invsr_orgn":rows}
        from shared_broker_api.gateway import compact
        return {"source":"KIWOOM_KA10059","mode":"demo",
                "stock_code":stock_code,"requested_day":day,
                "orders_enabled":False,
                "first_gateway_received_utc":"2026-10-14T03:00:00+00:00",
                "response":response,"response_sha256":sha256(compact(response)).hexdigest(),
                "headers":{"cont-yn":"N"}}
    def selected_flow_research(self,*,stock_code,day,mode,max_pages,recent_sessions):
        return research_selected_flow(self,stock_code=stock_code,day=day,
                                      mode=mode,as_of=NOW,max_pages=max_pages,
                                      recent_sessions=recent_sessions)


def sources(tmp_path):
    root,project=fixture(tmp_path)
    source=put_twenty(root,"latest")
    return root,project,source


def plan(project,source,limit=3):
    return plan_marketwide_flow(marketwide=source,project=project,
                                limit=limit,clock=NOW)


def capture(project,source,client,limit=3):
    return capture_marketwide_demo_flow(
        marketwide=source,project=project,client=client,limit=limit,clock=NOW)


def test_plan_no_network_chooses_observed_price_watch_priority(tmp_path):
    _,project,source=sources(tmp_path)
    result=plan(project,source)
    assert result["status"]=="FLOW_BATCH_READY_DEMO_RESEARCH"
    assert result["new_codes"]==["000100","000101","000102"]
    assert result["uncollected_eligible"]==20
    assert result["api_calls"]==0 and result["orders_enabled"] is False
    assert not (project/"output"/"marketwide_flow_batches").exists()


def test_apply_only_demo_shared_readonly_three_then_next_cohort(tmp_path):
    _,project,source=sources(tmp_path)
    client=FakeClient()
    first=capture(project,source,client)
    assert first["status"]=="FLOW_BATCH_DEMO_RESEARCH_PUBLISHED"
    assert first["stock_codes"]==["000100","000101","000102"]
    assert first["complete_20_observation_count"]==3
    assert first["orders_enabled"] is False
    assert first["official_leaders"]==0
    assert client.calls==first["stock_codes"]
    manifest=Path(first["manifest"])
    doc=json.loads(manifest.read_bytes())
    assert doc["market"]=="KR" and doc["mode"]=="demo"
    assert doc["reported_20_observations"]==3
    assert all((manifest.parent/(c+".json")).exists() for c in first["stock_codes"])
    pending=plan(project,source)
    assert pending["already_collected"]==3
    assert pending["new_codes"]==["000103","000104","000105"]
    second=capture(project,source,client)
    assert second["stock_codes"]==pending["new_codes"]
    assert len(list(manifest.parent.parent.glob("KR_*")))==2
    assert all(x["orders_enabled"] is False for x in (first,second))


def test_partial_provider_failure_has_no_new_batch_and_keeps_old(tmp_path):
    _,project,source=sources(tmp_path)
    good=FakeClient()
    completed=capture(project,source,good,limit=2)
    stable=Path(completed["manifest"]).read_bytes()
    denied=FakeClient(fail="000103")
    with pytest.raises(ValueError,match="PROVIDER_UNAVAILABLE"):
        capture(project,source,denied,limit=2)
    assert denied.calls==["000102","000103"]
    assert Path(completed["manifest"]).read_bytes()==stable
    assert len(list(Path(completed["manifest"]).parent.parent.glob("KR_*")))==1
    assert plan(project,source,limit=2)["new_codes"]==["000102","000103"]


def test_corrupted_previous_batch_fails_closed(tmp_path):
    _,project,source=sources(tmp_path)
    result=capture(project,source,FakeClient(),limit=1)
    first=Path(result["manifest"])
    first.write_bytes(first.read_bytes()+b"BAD")
    with pytest.raises(ValueError):
        plan(project,source)
    assert len(list(first.parent.parent.glob("KR_*")))==1


def test_tampered_saved_single_symbol_detected(tmp_path):
    _,project,source=sources(tmp_path)
    result=capture(project,source,FakeClient(),limit=1)
    folder=Path(result["manifest"]).parent
    file=folder/"000100.json"
    file.write_bytes(file.read_bytes()+b"mutated")
    with pytest.raises(ValueError):
        plan(project,source)


def test_source_sha_rev_changes_batch_universe(tmp_path):
    _,project,source=sources(tmp_path)
    first=capture(project,source,FakeClient(),limit=1)
    report=json.loads(source.read_bytes())
    report["securities"][0]["name"]="revised official name"
    report.pop("content_sha256")
    report["content_sha256"]=sha256(canonical(report)).hexdigest()
    source.write_bytes(canonical(report)+b"\n")
    after=plan(project,source,limit=1)
    assert after["already_collected"]==0
    assert after["new_codes"]==["000100"]
    assert Path(first["manifest"]).exists()


def test_gateway_no_demo_or_orders_enabled_never_queried(tmp_path):
    _,project,source=sources(tmp_path)
    c=FakeClient()
    c.status=lambda:{"configured":{"demo":True},"orders_enabled":True}
    with pytest.raises(ValueError,match="READ_ONLY"):
        capture(project,source,c)
    assert c.calls==[]
    assert not (project/"output"/"marketwide_flow_batches").exists()


def test_invalid_batch_size_and_stale_source_do_not_call(tmp_path):
    _,project,source=sources(tmp_path)
    for bad in (0,6,-1,True):
        with pytest.raises(ValueError,match="LIMIT"):
            plan(project,source,bad)
    c=FakeClient()
    stale=plan_marketwide_flow(
        marketwide=source,project=project,limit=2,
        clock=datetime(2026,10,28,3,tzinfo=timezone.utc))
    assert stale["status"]=="STALE_KR_MARKET_HOLD"
    assert stale["new_codes"]==[] and stale["api_calls"]==0


def test_cli_dry_run_has_no_network_and_limits_batch(tmp_path):
    _,project,source=sources(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_marketwide_flow_batch.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-report",str(source),"--max-codes","2"]
    proc=subprocess.run(cmd,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    body=json.loads(proc.stdout)
    assert body["new_codes"]==["000100","000101"]
    assert body["api_calls"]==0
    assert not (project/"output"/"marketwide_flow_batches").exists()
    bad=subprocess.run(cmd[:-1]+["9"],capture_output=True,text=True)
    assert bad.returncode==2


def test_repeated_batches_exhaust_eligible_without_network_if_no_more(tmp_path):
    _,project,source=sources(tmp_path)
    c=FakeClient()
    for step in range(4):
        result=capture(project,source,c,limit=5)
        assert result["published_count"]==5
    empty=plan(project,source,limit=5)
    assert empty["status"]=="FLOW_BATCH_ALL_ELIGIBLE_COVERED"
    assert empty["new_codes"]==[] and empty["already_collected"]==20
    assert capture(project,source,c,limit=5)["api_calls"]==0
    assert len(c.calls)==20
