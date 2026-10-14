"""Test dated Kiwoom response against the original signed aggregate."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
import json
import subprocess
import sys
import pytest

from test_marketwide_flow_batch import sources,FakeClient,capture,NOW
from eraleader.marketwide_dated_flow import (
    plan_dated_capture,capture_dated_flow,read_dated_flow)
from eraleader.official_company_explorer import canonical

CODE="000100"


def arrange(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    return project,market


def plan(project,market,code=CODE):
    return plan_dated_capture(marketwide=market,project=project,
                              stock_code=code,clock=NOW)


def apply(project,market,client,code=CODE):
    return capture_dated_flow(marketwide=market,project=project,
                              stock_code=code,client=client,clock=NOW)


def test_dry_run_is_no_network_and_only_previously_verified_code(tmp_path):
    project,market=arrange(tmp_path)
    status=plan(project,market)
    assert status["status"]=="DATED_FLOW_READY_DEMO_ONE_CODE"
    assert status["stock_code"]==CODE and status["api_calls"]==0
    assert not (project/"output"/"marketwide_dated_flow").exists()
    with pytest.raises(ValueError,match="NO_PREVIOUS_20"):
        plan(project,market,"000101")
    with pytest.raises(ValueError,match="SELECTED_CODE"):
        plan(project,market,"FAKE_CODE")


def test_capture_retains_exact_dates_and_5_20_observation_sums(tmp_path):
    project,market=arrange(tmp_path)
    client=FakeClient()
    actual=apply(project,market,client)
    assert actual["status"]=="DATED_FLOW_CAPTURED_DEMO_RESEARCH"
    assert client.calls==[CODE]
    assert actual["row_count"]==20 and actual["orders_enabled"] is False
    doc=read_dated_flow(Path(actual["file"]),expected_code=CODE,clock=NOW)
    assert doc["source_market_session"]=="2026-10-13"
    assert doc["rows"][0]["session"]=="2026-10-13"
    assert len(doc["rows"])==20
    assert [d["session"] for d in doc["rows"]]==sorted(
        (d["session"] for d in doc["rows"]),reverse=True)
    assert sum(d["foreign_net_shares"] for d in doc["rows"][:5])==510
    assert sum(d["institution_net_shares"] for d in doc["rows"][:20])==-390
    assert doc["flow_score_10"] is None and doc["historical_pit_certified"] is False
    previous=plan(project,market)
    assert previous["status"]=="DATED_FLOW_ALREADY_CAPTURED"
    assert apply(project,market,client)["api_calls"]==0
    assert client.calls==[CODE]


def test_gateway_disabled_or_wrong_mode_never_creates_file(tmp_path):
    project,market=arrange(tmp_path)
    c=FakeClient()
    c.status=lambda:{"orders_enabled":True,"configured":{"demo":True}}
    with pytest.raises(ValueError,match="READONLY"):
        apply(project,market,c)
    assert c.calls==[]
    assert not (project/"output"/"marketwide_dated_flow").exists()


def test_provider_bad_sum_cannot_rewrite_original_aggregate(tmp_path):
    project,market=arrange(tmp_path)
    client=FakeClient()
    original=client.investor_flow_page
    def changed(**kw):
        page=original(**kw)
        page["response"]["stk_invsr_orgn"][0]["frgnr_invsr"]="123999"
        from shared_broker_api.gateway import compact
        page["response_sha256"]=sha256(compact(page["response"])).hexdigest()
        return page
    client.investor_flow_page=changed
    with pytest.raises(ValueError,match="ORIGINAL_AGGREGATE"):
        apply(project,market,client)
    assert not list((project/"output").glob("marketwide_dated_flow/*.json"))


def test_gateway_bad_response_sha_or_identity_rejected(tmp_path):
    project,market=arrange(tmp_path)
    c=FakeClient()
    original=c.investor_flow_page
    def bad(**kwargs):
        result=original(**kwargs)
        result["response_sha256"]="f"*64
        return result
    c.investor_flow_page=bad
    with pytest.raises(ValueError,match="SHA_OR_IDENTITY"):
        apply(project,market,c)
    assert not list((project/"output").glob("marketwide_dated_flow/*.json"))


def test_saved_dated_row_tamper_blocks_no_extra_api(tmp_path):
    project,market=arrange(tmp_path)
    c=FakeClient()
    saved=apply(project,market,c)
    file=Path(saved["file"])
    old=file.read_bytes()
    file.write_bytes(old+b"BAD")
    with pytest.raises(ValueError):
        plan(project,market)
    assert c.calls==[CODE]
    assert file.read_bytes()==old+b"BAD"


def test_cli_plan_does_not_call_provider(tmp_path):
    project,market=arrange(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"capture_marketwide_dated_flow.py"
    run=subprocess.run([sys.executable,str(script),
        "--marketwide-report",str(market),"--project",str(project),
        "--code",CODE],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)["status"]=="DATED_FLOW_READY_DEMO_ONE_CODE"
    assert not (project/"output"/"marketwide_dated_flow").exists()
