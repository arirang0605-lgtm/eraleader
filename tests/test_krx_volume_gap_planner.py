"""Only missing KRX original captures are proposed (bounded, zero network)."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess
import sys
import pandas as pd
import pytest

from eraleader import krx_volume_gap_planner as planner
from test_marketwide_dated_volume import arranged,cached,CODE
from test_marketwide_flow_batch import sources,NOW

def setup(tmp_path,missing=(0,5)):
    project,market=arranged(tmp_path)
    vault=cached(tmp_path,no=missing)
    capture=tmp_path/"private_capture"
    capture.mkdir()
    return project,market,vault,capture

def ask(project,market,vault,capture,limit=6):
    return planner.plan_dated_krx_volume_gaps(
        marketwide=market,project=project,capture_root=capture,
        stock_code=CODE,legacy_root=vault,clock=NOW,max_requests=limit)

def test_empty_original_captures_lists_only_dates_missing_from_price_cache(tmp_path):
    project,market,vault,capture=setup(tmp_path)
    doc=ask(project,market,vault,capture)
    assert doc["status"]=="KRX_VOLUME_GAP_REQUESTS_READY"
    assert doc["marcap_missing_dates"]==["2026-10-08","2026-10-13"]
    assert doc["planned_requests"]==[
        {"market_day":"2026-10-08","source":"krx-kospi"},
        {"market_day":"2026-10-08","source":"krx-kosdaq"},
        {"market_day":"2026-10-13","source":"krx-kospi"},
        {"market_day":"2026-10-13","source":"krx-kosdaq"},
    ]
    assert doc["api_calls"]==0 and doc["orders_enabled"] is False
    assert doc["market_pit_independently_certified"] is False

def test_bounded_capture_queue_caps_at_two_without_api(tmp_path):
    project,market,vault,capture=setup(tmp_path)
    doc=ask(project,market,vault,capture,limit=2)
    assert len(doc["planned_requests"])==2
    assert doc["requests_held_by_maximum"]==2
    for invalid in (0,7,True,-1):
        with pytest.raises(ValueError,match="CAP"):
            ask(project,market,vault,capture,limit=invalid)

def test_existing_two_venue_original_captures_are_not_requested_again(tmp_path,monkeypatch):
    project,market,vault,capture=setup(tmp_path)
    archive={}
    for day in ("2026-10-08","2026-10-13"):
        for kind in planner.SOURCES:
            archive[(day,kind)]=(NOW,capture,"a"*64)
    monkeypatch.setattr(planner,"_receipt_index",lambda *_:archive)
    def verify(_folder,kind,_pin,_now):
        return {"source":kind,"request_value":current_day[0]},{}
    current_day=["2026-10-08"]
    def frame(kind,meta,_raw):
        return pd.DataFrame([{
            "security_id":CODE,"volume":1000,
        }]) if kind=="krx-kospi" else pd.DataFrame(columns=["security_id","volume"])
    # Pretend each first-pinned folder is decoded for its respective date.
    # Distinct date capture IDs matter to first-observed PIT, not rank logic.
    monkeypatch.setattr(planner,"verified_capture",verify)
    monkeypatch.setattr(planner,"_krx_frame",frame)
    # The planning path must validate day from each actual receipt. Model
    # the metadata per date via unique capture paths.
    monkeypatch.setattr(planner,"_receipt_index",lambda *_:{
        (day,kind):(NOW,Path(day),("a" if kind=="krx-kospi" else "b")*64)
        for day in ("2026-10-08","2026-10-13")
        for kind in planner.SOURCES
    })
    monkeypatch.setattr(planner,"verified_capture",lambda folder,kind,pin,now:
                        ({"source":kind,"request_value":folder.name},{}))
    plan=ask(project,market,vault,capture)
    assert plan["already_receipted_dates"]==["2026-10-08","2026-10-13"]
    assert plan["planned_requests"]==[]
    assert plan["all_missing_receipt_requests"]==0
    assert plan["status"]=="KRX_VOLUME_GAP_EXISTING_RECEIPTS_READY"

def test_missing_one_exchange_only_plans_one_request(tmp_path,monkeypatch):
    project,market,vault,capture=setup(tmp_path)
    monkeypatch.setattr(planner,"_receipt_index",lambda *_:{
        ("2026-10-08","krx-kospi"):(NOW,capture,"a"*64)
    })
    monkeypatch.setattr(planner,"verified_capture",lambda f,k,s,n:
                        ({"source":k,"request_value":"2026-10-08"},{}))
    monkeypatch.setattr(planner,"_krx_frame",lambda k,meta,r:
                        pd.DataFrame([{"security_id":CODE,"volume":1000}]))
    result=ask(project,market,vault,capture)
    assert result["all_missing_receipt_requests"]==3
    assert {"market_day":"2026-10-08","source":"krx-kospi"} not in result["planned_requests"]
    assert {"market_day":"2026-10-08","source":"krx-kosdaq"} in result["planned_requests"]

def test_unchanged_complete_20_volume_cache_requires_no_new_request(tmp_path):
    project,market,vault,capture=setup(tmp_path,missing=())
    result=ask(project,market,vault,capture)
    assert result["marcap_missing_dates"]==[]
    assert result["status"]=="KRX_VOLUME_GAP_EXISTING_RECEIPTS_READY"
    assert result["api_calls"]==0

def test_no_existing_dated_flow_receipt_not_a_reason_to_fetch(tmp_path):
    _,project,market=sources(tmp_path)
    vault=tmp_path/"vault";vault.mkdir()
    capture=tmp_path/"captures";capture.mkdir()
    result=planner.plan_dated_krx_volume_gaps(
        marketwide=market,project=project,
        capture_root=capture,stock_code=CODE,legacy_root=vault,clock=NOW)
    assert result["status"]=="KRX_VOLUME_GAP_NO_DATED_FLOW"
    assert result["planned_requests"]==[]

def test_cli_plan_only_never_creates_capture(tmp_path):
    project,market,vault,capture=setup(tmp_path)
    runner=Path(__file__).resolve().parents[1]/"scripts"/"plan_krx_volume_gaps.py"
    cmd=[sys.executable,str(runner),"--project",str(project),
         "--marketwide-report",str(market),"--capture-root",str(capture),
         "--legacy-root",str(vault),"--code",CODE,"--max-requests","2"]
    got=subprocess.run(cmd,capture_output=True,text=True)
    assert got.returncode==0,got.stderr
    status=json.loads(got.stdout)
    assert status["api_calls"]==0 and status["orders_enabled"] is False
    assert len(status["planned_requests"])==2
    assert not list(capture.iterdir())
