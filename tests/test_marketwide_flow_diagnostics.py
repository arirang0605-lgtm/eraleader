"""Marketcap-implied total-share denominator for selected-security flow.

Entire pipeline stays RESEARCH ONLY: not verified float ownership or a flow
score, and never changes any price WATCH/candidate/trade states.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from test_marketwide_flow_batch import sources, FakeClient, capture, NOW
from eraleader.marketwide_flow_diagnostics import (
    _pct,_direction,inspect_flow_share_proxy,publish_flow_share_proxy,
    SCHEMA,PROXY
)
from eraleader.marketwide_flow_coverage import summarize_flow_coverage
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from eraleader.official_company_explorer import canonical
from eraleader.marketwide_live_search import _source


def test_actual_implied_shares_proxy_matches_observed_net_shares(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=3)
    result=inspect_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    assert result["schema"]==SCHEMA
    assert result["stocks_with_flow"]==3
    assert result["stocks_with_usable_denominator"]==3
    assert result["shares_proxy_method"]==PROXY
    assert result["formal_flow_score_10_available"] is False
    assert result["free_float_independently_verified"] is False
    assert result["turnover_or_volume_matched_by_each_observation"] is False
    assert result["orders_enabled"] is False
    source,_=_source(market)
    samples={x["security_id"]:x for x in source["securities"]}
    original=summarize_flow_coverage(marketwide=market,project=project,clock=NOW)
    flows={x["security_id"]:x for x in original["rows"]}
    for item in result["rows"]:
        code=item["security_id"]
        close=samples[code]["close"]
        cap=samples[code]["market_cap"]
        value=flows[code]["foreign_net_20_shares"]
        assert item["foreign_net_20_pct_of_implied_total_shares"]==round(
            100*value*close/cap,6)
        assert item["flow_score_10"] is None
        assert item["denominator_kind"]==PROXY
        assert item["implied_total_shares_proxy"]==round(cap/close,2)


def test_positive_negative_direction_and_missing_remain_research_only():
    assert _direction(1,3)=="BOTH_POSITIVE"
    assert _direction(-1,-3)=="BOTH_NEGATIVE"
    assert _direction(-1,3)=="MIXED_OR_ZERO"
    assert _direction(0,3)=="MIXED_OR_ZERO"
    assert _direction(None,3) is None
    assert _pct(None,close=100,cap=1000) is None
    assert _pct(100,close=None,cap=1000) is None
    assert _pct(-50,close=100,cap=10000)==-50.0
    with pytest.raises(ValueError,match="DENOMINATOR"):
        _pct(100,close=0,cap=100)


def test_missing_same_session_market_cap_is_na_not_invented(tmp_path):
    _,project,market=sources(tmp_path)
    doc=json.loads(market.read_bytes())
    doc["securities"][0]["market_cap"]=None
    unsigned=dict(doc)
    unsigned.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(unsigned)).hexdigest()
    market.write_bytes(canonical(doc)+b"\n")
    capture(project,market,FakeClient(),limit=1)
    result=inspect_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    assert result["stocks_with_flow"]==1
    assert result["stocks_with_usable_denominator"]==0
    row=result["rows"][0]
    assert row["implied_total_shares_proxy"] is None
    assert row["foreign_net_20_pct_of_implied_total_shares"] is None
    assert row["flow_score_10"] is None


def test_repeat_immutable_and_next_batch_version(tmp_path):
    _,project,market=sources(tmp_path)
    c=FakeClient()
    capture(project,market,c,limit=2)
    one=publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    assert one["status"]=="PUBLISHED"
    before=Path(one["manifest"]).read_bytes()
    assert publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)["status"]=="ALREADY_PUBLISHED"
    capture(project,market,c,limit=1)
    two=publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    assert two["status"]=="PUBLISHED"
    assert two["index"]!=one["index"]
    assert Path(one["manifest"]).read_bytes()==before
    assert two["observed_stocks"]==3
    assert len(list(Path(one["manifest"]).parent.parent.glob("KR_*")))==2
    assert "거래량 기반 매집률이 아닙니다" in Path(two["index"]).read_text()


def test_existing_diagnostics_tamper_not_overwritten(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    one=publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    html=Path(one["index"])
    html.write_bytes(html.read_bytes()+b"tampered")
    original=html.read_bytes()
    with pytest.raises(ValueError,match="EXISTING_VERSION_CONFLICT"):
        publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    assert html.read_bytes()==original


def test_diagnostics_snapshot_menu_fails_closed(tmp_path):
    _,project,market=sources(tmp_path)
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_flow_diagnostics"] is None
    capture(project,market,FakeClient(),limit=1)
    published=publish_flow_share_proxy(marketwide=market,project=project,clock=NOW)
    snapshot=audit_local_operations(project,clock=NOW)
    entry=snapshot["kr_marketwide_flow_diagnostics"]
    assert entry["observed_stocks"]==1
    assert entry["proxy_denominators"]==1
    assert entry["formal_flow_score"] is False
    assert "키움 수급 추정 발행주식수 대비 보기" in render_operations_overview(snapshot)
    snapshot["kr_marketwide_flow_diagnostics"]["href"]="../../../../evil"
    with pytest.raises(ValueError,match="Unsafe marketwide flow diagnostic"):
        render_operations_overview(snapshot)
    Path(published["index"]).write_bytes(b"fake")
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_flow_diagnostics"] is None


def test_operational_cli_opt_in_diagnostics_no_network_or_orders(tmp_path):
    src,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    command=[sys.executable,str(Path(__file__).resolve().parents[1]/
             "scripts"/"render_local_operations.py"),
             "--project",str(project),
             "--marketwide-source-root",str(src),
             "--marketwide-flow-diagnostics"]
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    out=json.loads(run.stdout)
    assert out["marketwide_flow_diagnostics_status"]=="PUBLISHED"
    assert out["marketwide_flow_diagnostics_stocks"]==1
    assert out["marketwide_flow_diagnostics_proxy_denominators"]==1
    assert out["marketwide_flow_diagnostics_orders"]==0
    assert out["external_api_calls"]==0
    assert "키움 수급 추정 발행주식수 대비 보기" in (
        project/"output"/"operations"/"site"/"index.html").read_text()
    repeat=subprocess.run(command,capture_output=True,text=True)
    assert repeat.returncode==0
    assert json.loads(repeat.stdout)["marketwide_flow_diagnostics_status"]=="ALREADY_PUBLISHED"


def test_cli_diagnostics_requires_explicit_source(tmp_path):
    _,project,_=sources(tmp_path)
    command=[sys.executable,str(Path(__file__).resolve().parents[1]/
             "scripts"/"render_local_operations.py"),
             "--project",str(project),"--marketwide-flow-diagnostics"]
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode!=0
    assert not (project/"output"/"marketwide_flow_diagnostics").exists()
