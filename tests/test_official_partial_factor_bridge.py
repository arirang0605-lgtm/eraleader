"""Real-source partial-factor derivation tests: no invented 5-factor selection."""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
from copy import deepcopy

import pytest
from eraleader.official_company_explorer import canonical
from eraleader.official_partial_factor_bridge import (
    derive_partial_factor_input,PROVIDER
)
from eraleader.factor_selection_pipeline import (
    _read_assessment,run_factor_selection,LEDGER
)
from eraleader.state_history import StateHistory
from test_marketwide_live_search import sample,repin
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,6,tzinfo=timezone.utc)


def source(root:Path, *,earnings=22.5, market_date="2026-10-13",
           observed_extra=0):
    report=sample()
    report["market_session"]=market_date
    report["source_decision_at_utc"]="2026-10-14T00:00:00+00:00"
    report["built_at_utc"]="2026-10-14T01:00:00+00:00"
    for item in report["securities"]:
        item["market_session"]=market_date
    report["securities"][0]["earnings_research_25"]=earnings
    report["securities"][1]["earnings_research_25"]=None
    report["securities"][2]["earnings_research_25"]=None
    for i in range(observed_extra):
        item=deepcopy(report["securities"][1])
        item["security_id"]=f"{600000+i:06d}"
        item["name"]="추가 연구기업"
        item["price_strength_25"]=13.0+i/1000
        report["securities"].append(item)
        report["local_price_lookback_evaluable"]+=1
    report["official_krx_observed"]=len(report["securities"])
    report=repin(report)
    f=root/"marketwide_kr.json"
    f.write_bytes(canonical(report)+b"\n")
    return f,report


def test_real_partial_marketwide_earnings_and_momentum_only(tmp_path):
    _,project=fixture(tmp_path)
    src,meta=source(project/"output")
    made=derive_partial_factor_input(
        marketwide=src,project=project,clock=NOW)
    assert made["status"]=="PARTIAL_FACTOR_DERIVED"
    assert made["research_candidates"]==2
    assert made["earnings_available"]==1
    assert made["momentum_available"]==2
    assert made["industry_growth_scored"]==0
    assert made["competitiveness_scored"]==0
    assert made["institutional_flow_scored"]==0
    assert made["formal_candidates"]==0
    input_file=Path(made["input_file"])
    payload=_read_assessment(input_file)
    assert payload["source_marketwide_sha256"]==meta["content_sha256"]
    assert payload["decision_at_utc"]=="2026-10-14T01:00:00+00:00"
    assert payload["market_session"]=="2026-10-13"
    assert [x["security_id"] for x in payload["factor_rows"]]==["005930","000660"]
    first=payload["factor_rows"][0]
    assert first["components"]=={
        "industry":None,"competitiveness":None,
        "earnings":22.5,"momentum":20.0,"flow":None,
    }
    assert not any(first["evidence"].values())
    assert first["issuer_id_validated_as_of"] is False
    assert first["factor_receipts"]["earnings"]["sha256"]==meta["content_sha256"]
    assert first["factor_receipts"]["earnings"]["provider"]==PROVIDER
    assert all(first["factor_receipts"][f] is None for f in
               ("industry","competitiveness","flow"))
    selected=run_factor_selection(
        marketwide=src,project=project,assessment_file=input_file,clock=NOW)
    assert selected["research_selected"]==0
    assert selected["formal_leader_certified"] is False
    db=StateHistory(project/"output"/LEDGER)
    try:
        assert db.db.execute("SELECT COUNT(*) FROM state_history").fetchone()[0]==2
        assert db.db.execute("SELECT DISTINCT current FROM state_history").fetchall()==[("WATCH",)]
    finally:
        db.close()


def test_repeat_is_idempotent_and_reuses_unchanged_original(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output")
    first=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    path=Path(first["input_file"])
    raw=path.read_bytes()
    second=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    assert second["status"]=="ALREADY_DERIVED"
    assert second["input_file"]==first["input_file"]
    assert path.read_bytes()==raw
    assert len(list(path.parent.glob("KR_*.json")))==1


def test_selected_rows_limit_never_invents_scores(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output",observed_extra=8)
    result=derive_partial_factor_input(
        marketwide=src,project=project,clock=NOW,limit=5)
    assert result["research_candidates"]==5
    assert result["earnings_available"]==1
    assert result["unscored_price_observations"]==5
    payload=_read_assessment(Path(result["input_file"]))
    assert len(payload["factor_rows"])==5
    assert all(x["components"]["industry"] is None
               and x["components"]["flow"] is None for x in payload["factor_rows"])


@pytest.mark.parametrize("issue",["wrong_earnings","negative","future_source","bad_source_sha"])
def test_bad_source_cannot_publish_partial_factors(tmp_path,issue):
    _,project=fixture(tmp_path)
    src,raw=source(project/"output")
    if issue=="wrong_earnings":
        raw["securities"][0]["earnings_research_25"]=10
    elif issue=="negative":
        raw["securities"][0]["earnings_research_25"]=-1
    elif issue=="future_source":
        raw["built_at_utc"]="2026-10-15T01:00:00+00:00"
    else:
        raw["securities"][0]["name"]="TAMPER"
    if issue!="bad_source_sha":
        raw=repin(raw)
    src.write_bytes(canonical(raw)+b"\n")
    with pytest.raises(ValueError):
        derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    assert not list((project/"output").glob("partial_factor_inputs/KR_*.json"))


def test_stale_market_does_not_create_new_assessment(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output",market_date="2026-10-08")
    result=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    assert result["status"]=="PARTIAL_FACTOR_STALE_MARKET_HOLD"
    assert result["formal_candidates"]==0
    assert not list((project/"output").glob("partial_factor_inputs/KR_*.json"))


def test_tampered_existing_output_is_rejected_not_replaced(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output")
    first=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    f=Path(first["input_file"])
    f.write_bytes(f.read_bytes()+b"TAMPER")
    with pytest.raises(ValueError):
        derive_partial_factor_input(marketwide=src,project=project,clock=NOW)


def test_unknown_alpha_code_from_real_market_can_be_research_watch(tmp_path):
    _,project=fixture(tmp_path)
    src,report=source(project/"output")
    report["securities"][1]["security_id"]="123A56"
    report=repin(report)
    src.write_bytes(canonical(report)+b"\n")
    item=derive_partial_factor_input(marketwide=src,project=project,clock=NOW)
    selection=run_factor_selection(
        marketwide=src,project=project,
        assessment_file=Path(item["input_file"]),clock=NOW)
    assert selection["research_selected"]==0
    assert selection["states_in_observation"]==2


def test_cli_derives_source_only_and_does_not_use_broker(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output")
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_factor_selection.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-report",str(src),"--derive-official-partial"]
    run=subprocess.run(cmd,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    payload=json.loads(run.stdout)
    assert payload["research_selected"]==0
    assert payload["partial_factor_derivation"]["research_candidates"]==2
    assert payload["partial_factor_derivation"]["formal_candidates"]==0
    assert payload["orders_enabled"] is False
    repeat=subprocess.run(cmd,capture_output=True,text=True)
    assert repeat.returncode==0,repeat.stderr
    assert json.loads(repeat.stdout)["partial_factor_derivation"]["status"]=="ALREADY_DERIVED"


def test_cli_disallows_conflicting_or_out_of_range_options(tmp_path):
    _,project=fixture(tmp_path)
    src,_=source(project/"output")
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_factor_selection.py"
    cmd=[sys.executable,str(script),"--project",str(project),"--marketwide-report",str(src)]
    for options in (
        ["--derive-official-partial","--max-research-rows","0"],
        ["--derive-official-partial","--max-research-rows","501"],
        ["--max-research-rows","2"],
    ):
        proc=subprocess.run(cmd+options,capture_output=True,text=True)
        assert proc.returncode!=0


def test_operations_dashboard_opt_in_derives_partial_without_order_or_leader(tmp_path):
    sources,project=fixture(tmp_path)
    folder=sources/"market_1014"
    folder.mkdir()
    source(folder)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    command=[sys.executable,str(script),"--project",str(project),
             "--marketwide-source-root",str(sources),
             "--marketwide-derive-partial-factors"]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert output["marketwide_partial_factor_rows"]==2
    assert output["marketwide_partial_factor_selected"]==0
    assert output["marketwide_partial_factor_orders"]==0
    assert output["official_leader_promotions"]==0
    assert (project/"output"/LEDGER).is_file()
    assert not (project/"output"/"strategy_outbox").exists()
    second=subprocess.run(command,capture_output=True,text=True)
    assert second.returncode==0,second.stderr
    assert json.loads(second.stdout)["marketwide_partial_factor_status"]=="ALREADY_DERIVED"


def test_operations_partial_requires_source_root_and_is_off_by_default(tmp_path):
    sources,project=fixture(tmp_path)
    folder=sources/"market_1014"
    folder.mkdir()
    source(folder)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    base=[sys.executable,str(script),"--project",str(project)]
    baseline=subprocess.run(base,capture_output=True,text=True)
    assert baseline.returncode==0,baseline.stderr
    assert not (project/"output"/LEDGER).exists()
    assert "marketwide_partial_factor_rows" not in json.loads(baseline.stdout)
    bad=subprocess.run(base+["--marketwide-derive-partial-factors"],
                       capture_output=True,text=True)
    assert bad.returncode!=0
    assert not (project/"output"/LEDGER).exists()
