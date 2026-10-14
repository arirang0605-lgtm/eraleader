"""Cumulative selected-stock flow display from immutable shared DEMO receipts."""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess
import sys

import pytest

from test_marketwide_flow_batch import sources,FakeClient,capture,NOW
from eraleader.marketwide_flow_coverage import summarize_flow_coverage,publish_flow_coverage
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from eraleader.official_company_explorer import canonical
from hashlib import sha256


def test_empty_flow_coverage_is_not_conflated_with_marketwide_flow(tmp_path):
    _,project,market=sources(tmp_path)
    doc=summarize_flow_coverage(marketwide=market,project=project,clock=NOW)
    assert doc["collected_stocks"]==0
    assert doc["eligible_krx_stock_observations"]==20
    assert doc["complete_20_observed_sessions"]==0
    assert doc["whole_market_investor_flow"] is False
    assert doc["investment_flow_score_available"] is False
    assert doc["formal_leaders"]==0
    assert doc["orders_enabled"] is False


def test_two_verified_batches_publish_separate_cumulative_view(tmp_path):
    _,project,market=sources(tmp_path)
    client=FakeClient()
    capture(project,market,client,limit=2)
    a=publish_flow_coverage(marketwide=market,project=project,clock=NOW)
    assert a["collected_stocks"]==2
    assert a["complete_20_observed_sessions"]==2
    assert a["published_batches"]==1
    old=Path(a["manifest"]).read_bytes()
    b=capture(project,market,client,limit=3)
    assert b["published_count"]==3
    newest=publish_flow_coverage(marketwide=market,project=project,clock=NOW)
    assert newest["collected_stocks"]==5
    assert newest["complete_20_observed_sessions"]==5
    assert newest["published_batches"]==2
    assert newest["site"]!=a["site"]
    assert Path(a["manifest"]).read_bytes()==old
    doc=json.loads(Path(newest["manifest"]).read_bytes())
    unsigned=dict(doc);pin=unsigned.pop("content_sha256")
    assert pin==sha256(canonical(unsigned)).hexdigest()
    assert len(doc["rows"])==5
    assert all(x["flow_score_10"] is None for x in doc["rows"])
    assert all(x["first_gateway_received_at_utc"] for x in doc["rows"])
    assert doc["source_market_session"]=="2026-10-13"
    assert "실제 자금" in Path(newest["site"]).read_text()
    assert publish_flow_coverage(marketwide=market,project=project,clock=NOW)["status"]=="ALREADY_PUBLISHED"


def test_tampered_saved_flow_cannot_publish_coverage(tmp_path):
    _,project,market=sources(tmp_path)
    delivered=capture(project,market,FakeClient(),limit=1)
    manifest=Path(delivered["manifest"])
    receipt=manifest.parent/"000100.json"
    receipt.write_bytes(receipt.read_bytes()+b"FORGED")
    with pytest.raises(ValueError):
        publish_flow_coverage(marketwide=market,project=project,clock=NOW)
    assert not list((project/"output").glob("marketwide_flow_coverage/KR_*"))


def test_tampered_cumulative_manifest_and_html_refuses_replay(tmp_path):
    _,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    first=publish_flow_coverage(marketwide=market,project=project,clock=NOW)
    f=Path(first["site"])
    f.write_bytes(f.read_bytes()+b"bad")
    with pytest.raises(ValueError,match="EXISTING_VERSION_CONFLICT"):
        publish_flow_coverage(marketwide=market,project=project,clock=NOW)


def test_operations_link_verified_cumulative_flow_only(tmp_path):
    _,project,market=sources(tmp_path)
    before=audit_local_operations(project,clock=NOW)
    assert before["kr_marketwide_flow_coverage"] is None
    capture(project,market,FakeClient(),limit=1)
    first=publish_flow_coverage(marketwide=market,project=project,clock=NOW)
    snapshot=audit_local_operations(project,clock=NOW)
    x=snapshot["kr_marketwide_flow_coverage"]
    assert x["collected_stocks"]==1 and x["complete_20"]==1
    assert x["market_session"]=="2026-10-13" and x["orders"]==0
    assert "키움 기관·외국인 누적 관찰 보기" in render_operations_overview(snapshot)
    snapshot["kr_marketwide_flow_coverage"]["href"]="../../../../account.txt"
    with pytest.raises(ValueError,match="Unsafe marketwide"):
        render_operations_overview(snapshot)
    Path(first["site"]).write_bytes(b"ATTACK")
    assert audit_local_operations(project,clock=NOW)["kr_marketwide_flow_coverage"] is None


def test_operations_cli_opt_in_no_api_or_orders(tmp_path):
    root,project,market=sources(tmp_path)
    capture(project,market,FakeClient(),limit=1)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    args=[sys.executable,str(script),"--project",str(project),
          "--marketwide-source-root",str(root),"--marketwide-flow-coverage"]
    first=subprocess.run(args,capture_output=True,text=True)
    assert first.returncode==0,first.stderr
    data=json.loads(first.stdout)
    assert data["marketwide_flow_coverage_stocks"]==1
    assert data["marketwide_flow_coverage_orders"]==0
    assert data["external_api_calls"]==0
    assert "키움 기관·외국인 누적 관찰 보기" in (
        project/"output"/"operations"/"site"/"index.html").read_text()
    repeated=subprocess.run(args,capture_output=True,text=True)
    assert repeated.returncode==0
    assert json.loads(repeated.stdout)["marketwide_flow_coverage_status"]=="ALREADY_PUBLISHED"


def test_optional_operations_flag_without_source_refused(tmp_path):
    _,project,_=sources(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    run=subprocess.run([sys.executable,str(script),"--project",str(project),
                        "--marketwide-flow-coverage"],capture_output=True,text=True)
    assert run.returncode!=0
    assert not (project/"output"/"marketwide_flow_coverage").exists()
