"""KR five-factor operator-attested research candidates: state + neutral feed."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from eraleader import factor_selection_pipeline as fp
from eraleader.official_company_explorer import canonical
from eraleader.state_history import StateHistory
from eraleader.strategy_handoff import verify_handoff
from test_marketwide_live_search import sample, repin
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,6,tzinfo=timezone.utc)
FLAGS={k:True for k in fp.EVIDENCE}


def source(project:Path,day="2026-10-14"):
    raw=sample()
    raw["market_session"]=day
    raw["built_at_utc"]=f"{day}T00:10:00+00:00"
    raw["source_decision_at_utc"]=f"{day}T00:00:00+00:00"
    for item in raw["securities"]:
        item["market_session"]=day
    raw=repin(raw)
    dest=project/"output"/("source_"+day+".json")
    dest.write_bytes(canonical(raw)+b"\n")
    return dest,raw


def factors(project:Path,report:dict,*,day="2026-10-14",kind="high",
            missing=None,source_file=None):
    components={"industry":18,"competitiveness":18,"earnings":23,
                "momentum":20.0,"flow":8}
    if kind=="weak":
        components.update(industry=9,competitiveness=10,earnings=10,flow=5)
    if missing is not None:
        components[missing]=None
    receipts={
        name:({
            "sha256":sha256((name+day).encode()).hexdigest(),
            "available_at_utc":f"{day}T00:30:00+00:00",
            "provider":"local-research-capture",
        } if value is not None else None)
        for name,value in components.items()
    }
    body={
        "schema":fp.SCHEMA,"market":"KR","market_session":day,
        "source_marketwide_sha256":report["content_sha256"],
        "decision_at_utc":f"{day}T01:00:00+00:00",
        "certification_level":fp.ASSESSMENT,
        "factor_rows":[{
            "security_id":"005930","ticker":"005930",
            "issuer_id_validated_as_of":True,
            "components":components,"evidence":dict(FLAGS),
            "factor_receipts":receipts,
        }]
    }
    body["content_sha256"]=sha256(canonical(body)).hexdigest()
    dest=source_file or (project/"output"/("attested_"+day+".json"))
    dest.write_bytes(canonical(body)+b"\n")
    return dest,body


def run(project,market,assessment=None,clock=NOW):
    return fp.run_factor_selection(
        marketwide=market,project=project,
        assessment_file=assessment,clock=clock)


def test_realistic_missing_factor_mode_reports_coverage_without_inventing_leader(tmp_path):
    _,project=fixture(tmp_path)
    path,report=source(project)
    result=run(project,path)
    assert result["status"]=="FIVE_FACTOR_INPUT_NOT_AVAILABLE"
    assert result["coverage"]["krx_observed"]==3
    assert result["coverage"]["financial_observed"]==2
    assert result["coverage"]["certified_100_point_leaders"]==0
    assert result["research_selected"]==0 and result["state_events"]==0
    assert result["formal_leader_certified"] is False
    assert not (project/"output"/fp.LEDGER).exists()
    assert not (project/"output"/fp.CANDIDATE_OUTBOX).exists()


def test_complete_attested_input_potential_confirmed_weakening_and_neutral_feed(tmp_path):
    _,project=fixture(tmp_path)
    snapshots=[]
    for date,kind,time in [
        ("2026-10-14","high",NOW),
        ("2026-10-15","high",datetime(2026,10,15,6,tzinfo=timezone.utc)),
        ("2026-10-16","weak",datetime(2026,10,16,6,tzinfo=timezone.utc)),
    ]:
        market,meta=source(project,date)
        inp,_=factors(project,meta,day=date,kind=kind)
        result=run(project,market,inp,clock=time)
        payload=verify_handoff(Path(result["neutral_outbox_file"]),expected_market="KR")
        assert result["status"]=="FIVE_FACTOR_LOCAL_RESEARCH_STATES_PUBLISHED"
        assert result["historical_independent_pit_certified"] is False
        assert result["formal_leader_certified"] is False
        assert payload["execution_authority"] is False
        assert payload["order_instruction"] is False
        assert payload["research_only"] is True
        snapshots.append((result,payload))
    first,second,third=[x[1] for x in snapshots]
    assert first["selected_candidates"][0]["selection_state"]=="POTENTIAL"
    assert first["selected_candidates"][0]["score_100"]==87
    assert second["selected_candidates"][0]["selection_state"]=="CONFIRMED"
    assert second["selected_candidates"][0]["first_candidate_at"]=="2026-10-14"
    assert second["state_changes"][0]["event_type"]=="LEADER_CONFIRMED"
    assert third["selection_count"]==0
    assert third["state_changes"][0]["event_type"]=="LEADER_WEAKENING"
    db=StateHistory(project/"output"/fp.LEDGER)
    try:
        assert [x["state"] for x in db.history("KR","005930")]==[
            "POTENTIAL","CONFIRMED","WEAKENING"]
        assert db.db.execute("SELECT COUNT(*) FROM state_events").fetchone()[0]==3
    finally: db.close()


def test_replay_same_assessment_no_duplicate_state_or_outbox(tmp_path):
    _,project=fixture(tmp_path)
    src,meta=source(project)
    inp,_=factors(project,meta)
    first=run(project,src,inp)
    raw=Path(first["neutral_outbox_file"]).read_bytes()
    again=run(project,src,inp)
    assert again["delivery_status"]=="ALREADY_DELIVERED"
    assert Path(first["neutral_outbox_file"]).read_bytes()==raw
    db=StateHistory(project/"output"/fp.LEDGER)
    try:assert len(db.history("KR","005930"))==1
    finally:db.close()


def test_missing_component_never_promoted_and_not_imputed(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project)
    inp,_=factors(project,meta,missing="competitiveness")
    result=run(project,market,inp)
    assert result["research_selected"]==0
    assert result["state_events"]==0
    db=StateHistory(project/"output"/fp.LEDGER)
    try:
        last=db.history("KR","005930")[-1]
        assert last["state"]=="WATCH"
        assert last["score"] is None
    finally:db.close()


def test_claimed_false_pit_gate_blocks_promotion(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project)
    inp,body=factors(project,meta)
    body["factor_rows"][0]["evidence"]["historic_universe_pit"]=False
    body=repin(body)
    inp.write_bytes(canonical(body)+b"\n")
    result=run(project,market,inp)
    assert result["research_selected"]==0
    assert result["formal_leader_certified"] is False


@pytest.mark.parametrize("change",[
    "sha","unknown","momentum","future","stale","negative",
    "replay_conflict","unmatched_issuer","receipt_missing","duplicate_row",
    "issuer_not_attested"
])
def test_bad_5factor_inputs_rejected_without_new_selected_files(tmp_path,change):
    _,project=fixture(tmp_path)
    market,meta=source(project)
    inp,body=factors(project,meta)
    row=body["factor_rows"][0]
    if change=="sha":
        row["components"]["earnings"]=9
    elif change=="unknown":
        row["security_id"]="999999"
    elif change=="momentum":
        row["components"]["momentum"]=24.0
    elif change=="future":
        row["factor_receipts"]["earnings"]["available_at_utc"]="2026-10-16T00:00:00+00:00"
    elif change=="stale":
        body["market_session"]="2026-10-13"
    elif change=="negative":
        row["components"]["flow"]=-1
    elif change=="replay_conflict":
        body["source_marketwide_sha256"]="f"*64
    elif change=="unmatched_issuer":
        row["security_id"]="000660"
        row["ticker"]="000660"
    elif change=="receipt_missing":
        row["factor_receipts"]["earnings"]=None
    elif change=="duplicate_row":
        body["factor_rows"].append(deepcopy(row))
    elif change=="issuer_not_attested":
        row["issuer_id_validated_as_of"]=False
    if change!="sha":
        body=repin(body)
    inp.write_bytes(canonical(body)+b"\n")
    with pytest.raises((ValueError,TypeError,KeyError)):
        run(project,market,inp)
    assert not list((project/"output").glob("qualified_research_outbox/*.json"))


def test_current_market_attestation_cannot_rewrite_history_same_day(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project)
    inp,body=factors(project,meta)
    first=run(project,market,inp)
    body["factor_rows"][0]["components"]["earnings"]=20
    body["factor_rows"][0]["factor_receipts"]["earnings"]["sha256"]="a"*64
    inp.write_bytes(canonical(repin(body))+b"\n")
    with pytest.raises(ValueError,match="mutation"):
        run(project,market,inp)
    assert verify_handoff(Path(first["neutral_outbox_file"]))["selection_count"]==1


def test_full_selection_cli_receipts_and_readonly_default(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project)
    inp,_=factors(project,meta)
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_factor_selection.py"
    command=[sys.executable,str(script),"--project",str(project),
             "--marketwide-report",str(market)]
    preview=subprocess.run(command,capture_output=True,text=True)
    assert preview.returncode==0,preview.stderr
    assert json.loads(preview.stdout)["status"]=="FIVE_FACTOR_INPUT_NOT_AVAILABLE"
    assert not (project/"output"/fp.LEDGER).exists()
    actual=subprocess.run(command+["--factor-input",str(inp)],capture_output=True,text=True)
    assert actual.returncode==0,actual.stderr
    body=json.loads(actual.stdout)
    assert body["research_selected"]==1
    assert body["orders_enabled"] is False
    assert verify_handoff(Path(body["neutral_outbox_file"]))["selection_count"]==1


def test_prior_session_data_uses_first_decision_day_not_backdated(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project,"2026-10-13")
    inp,payload=factors(project,meta,day="2026-10-14")
    payload["market_session"]="2026-10-13"
    inp.write_bytes(canonical(repin(payload))+b"\n")
    result=run(project,market,inp)
    assert result["source_market_session"]=="2026-10-13"
    feed=verify_handoff(Path(result["neutral_outbox_file"]))
    assert feed["source_observed_as_of"]=="2026-10-14"
    assert feed["source_market_session"]=="2026-10-13"
    assert feed["first_local_decision_at_utc"]=="2026-10-14T01:00:00+00:00"
    assert feed["factor_assurance"]==fp.ASSESSMENT
    assert feed["formal_leader_certified"] is False
    assert feed["historical_independent_pit_certified"] is False


def test_stale_market_data_does_not_emit_new_research_state(tmp_path):
    _,project=fixture(tmp_path)
    market,meta=source(project,"2026-10-08")
    inp,payload=factors(project,meta,day="2026-10-14")
    payload["market_session"]="2026-10-08"
    inp.write_bytes(canonical(repin(payload))+b"\n")
    with pytest.raises(ValueError,match="STALE_MARKET"):
        run(project,market,inp)
    assert not (project/"output"/fp.LEDGER).exists()


def test_prior_candidate_without_today_factor_update_not_transmitted(tmp_path):
    _,project=fixture(tmp_path)
    first_market,first_source=source(project,"2026-10-14")
    first_input,_=factors(project,first_source,day="2026-10-14")
    first=run(project,first_market,first_input)
    assert first["research_selected"]==1

    second_market,second_source=source(project,"2026-10-15")
    other_input,doc=factors(project,second_source,day="2026-10-15")
    other=doc["factor_rows"][0]
    other["security_id"]="000660"
    other["ticker"]="000660"
    other["components"]["momentum"]=14.0
    # Missing same-day revalidation of 005930 must not keep it in the
    # exported selected universe even though its historical state remains.
    other_input.write_bytes(canonical(repin(doc))+b"\n")
    second=run(project,second_market,other_input,
               clock=datetime(2026,10,15,6,tzinfo=timezone.utc))
    data=verify_handoff(Path(second["neutral_outbox_file"]))
    assert data["stale_prior_candidates_suppressed"]==1
    assert data["selection_count"]==1
    assert [r["security_id"] for r in data["selected_candidates"]]==["000660"]
    assert data["order_instruction"] is False
    db=StateHistory(project/"output"/fp.LEDGER)
    try:
        # Historical evidence stays immutable, no unobserved EXIT event.
        assert db.history("KR","005930")[-1]["state"]=="POTENTIAL"
        assert db.db.execute("SELECT COUNT(*) FROM state_events").fetchone()[0]==2
    finally:db.close()
