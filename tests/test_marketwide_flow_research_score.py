"""Fixed, signed, local-only investor flow research heuristic (not official 10pt)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from hashlib import sha256
import json
from copy import deepcopy

import pytest

from eraleader import marketwide_flow_research_score as scoring
from eraleader.official_company_explorer import canonical
from eraleader.factor_selection_pipeline import _read_assessment, _validate
from eraleader.official_partial_factor_bridge import derive_partial_factor_input
from eraleader.marketwide_live_search import _source
from test_official_partial_factor_bridge import source
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,6,tzinfo=timezone.utc)
PROOF="a"*64
DATE="2026-10-13"


def facts(*,foreign5=2.0,institution5=1.0,foreign20=1.0,institution20=1.0,
          five_match=5,twenty_match=20):
    periods={}
    for name,limit,foreign,institution in (
        ("5",five_match,foreign5,institution5),
        ("20",twenty_match,foreign20,institution20),
    ):
        denom=10_000_000
        # Exact 6dp integer share amounts to avoid floating rounding ambiguity.
        periods[name]={
            "all_observation_dates_matched":limit==int(name),
            "matched_price_volume_days":limit,
            "missing_price_volume_dates":[] if limit==int(name) else ["2026-10-12"],
            "exact_matched_daily_volume_total_shares":denom if limit==int(name) else None,
            "foreign_net_shares":int(foreign*denom/100),
            "institution_net_shares":int(institution*denom/100),
            "foreign_pct_of_matched_daily_volume":foreign,
            "institution_pct_of_matched_daily_volume":institution,
        }
    return {
        "stock_code":"005930","source_marketwide_sha256":PROOF,
        "dated_flow_sha256":"b"*64,"official_volume_overlay_sha256":"c"*64,
        "cache_file_sha256":"d"*64,"formal_flow_score_10":None,
        "orders_enabled":False,"periods":periods,
    }


def prepared(tmp_path,monkeypatch,*,limit=500):
    _,project=fixture(tmp_path)
    market,metadata=source(project/"output")
    base=derive_partial_factor_input(marketwide=market,project=project,clock=NOW,limit=limit)
    original=Path(base["input_file"])
    before=original.read_bytes()
    available={"005930":facts(),"000660":facts(foreign5=-4,institution5=-2,
                                                   foreign20=-2,institution20=-2)}
    def fake(*,marketwide,project,code,official_volume_overlay,clock):
        row=deepcopy(available[code])
        row["stock_code"]=code
        row["source_marketwide_sha256"]=metadata["content_sha256"]
        return row
    monkeypatch.setattr(scoring,"evaluate_exact_volume",fake)
    return project,market,metadata,original,before


def build(project,market,codes=("005930","000660"),clock=NOW):
    return scoring.build_flow_research(
        marketwide=market,project=project,
        sources={code:Path("/absolute/"+code+".json") for code in codes},
        clock=clock)


def test_fixed_rule_does_not_claim_formal_signal_or_trade():
    score,sums,weighted=scoring._component(facts())
    assert sums==[3.0,2.0]
    assert weighted==2.6
    assert score==6.3
    assert scoring._component(facts(foreign5=-100,institution5=-100,
                                    foreign20=-100,institution20=-100))[0]==0
    assert scoring._component(facts(foreign5=100,institution5=100,
                                    foreign20=100,institution20=100))[0]==10


def test_non_matching_or_inconsistent_observed_days_blocked():
    with pytest.raises(ValueError,match="NOT_EXACTLY_MATCHED"):
        scoring._component(facts(twenty_match=19))
    altered=facts()
    altered["periods"]["5"]["foreign_pct_of_matched_daily_volume"]=25.0
    with pytest.raises(ValueError,match="CALC_MISMATCH"):
        scoring._component(altered)


def test_signed_research_and_join_retains_existing_source_and_resets_pit(tmp_path,monkeypatch):
    project,market,meta,base,original=prepared(tmp_path,monkeypatch)
    published=build(project,market)
    assert published["status"]=="PUBLISHED"
    assert published["scores"]=={"005930":6.3,"000660":2.4}
    evidence=scoring.read_flow_research(
        Path(published["file"]),expected_market_sha=meta["content_sha256"],clock=NOW)
    assert evidence["formal_flow_score_10_available"] is False
    assert evidence["orders_enabled"] is False
    joined=scoring.join_flow_into_partial(
        base_assessment=base,flow_file=Path(published["file"]),
        project=project,clock=NOW)
    assert joined["status"]=="FLOW_RESEARCH_JOINED"
    assert joined["scored_in_partial"]==2
    assert joined["existing_state_history_modified"] is False
    assert base.read_bytes()==original
    modified=_read_assessment(Path(joined["file"]))
    assert modified["decision_at_utc"]==NOW.isoformat()
    assert len(modified["factor_rows"])==2
    rows={r["security_id"]:r for r in modified["factor_rows"]}
    assert rows["005930"]["components"]["flow"]==6.3
    assert rows["000660"]["components"]["flow"]==2.4
    assert rows["005930"]["factor_receipts"]["flow"]["sha256"]==evidence["content_sha256"]
    assert rows["005930"]["components"]["industry"] is None
    assert rows["005930"]["components"]["competitiveness"] is None
    assert rows["005930"]["issuer_id_validated_as_of"] is False
    assert all(v is False for v in rows["005930"]["evidence"].values())
    raw,_=_source(market)
    observations,day=_validate(raw,modified,now=NOW)
    assert day=="2026-10-14"
    assert len(observations)==2
    assert not (project/"output"/"five_factor_local_state_history.sqlite").exists()
    assert scoring.join_flow_into_partial(
        base_assessment=base,flow_file=Path(published["file"]),
        project=project,clock=NOW)["status"]=="ALREADY_JOINED"
    assert base.read_bytes()==original


def test_duplicate_replay_only_reuses_same_clock_snapshot(tmp_path,monkeypatch):
    project,market,meta,base,original=prepared(tmp_path,monkeypatch)
    first=build(project,market)
    saved=Path(first["file"])
    text=saved.read_bytes()
    same=build(project,market)
    assert same["status"]=="ALREADY_PUBLISHED"
    assert saved.read_bytes()==text
    later=build(project,market,clock=NOW+timedelta(minutes=5))
    assert later["status"]=="PUBLISHED"
    assert later["file"]!=first["file"]
    assert saved.read_bytes()==text


def test_tampered_saved_research_never_accepted_or_applied(tmp_path,monkeypatch):
    project,market,meta,base,_=prepared(tmp_path,monkeypatch)
    first=build(project,market)
    f=Path(first["file"])
    f.write_bytes(f.read_bytes()+b"forged")
    with pytest.raises(ValueError):
        scoring.read_flow_research(f,expected_market_sha=meta["content_sha256"],clock=NOW)
    with pytest.raises(ValueError):
        scoring.join_flow_into_partial(
            base_assessment=base,flow_file=f,project=project,clock=NOW)
    assert not list((project/"output"/"partial_factor_inputs").glob("*FLOWV1*"))


def test_mismatched_marketwide_receipt_or_future_clock_denied(tmp_path,monkeypatch):
    project,market,meta,base,_=prepared(tmp_path,monkeypatch)
    first=build(project,market)
    f=Path(first["file"])
    with pytest.raises(ValueError,match="CONTRACT"):
        scoring.read_flow_research(f,expected_market_sha="f"*64,clock=NOW)
    with pytest.raises(ValueError,match="FUTURE"):
        scoring.read_flow_research(f,expected_market_sha=meta["content_sha256"],
                                   clock=NOW-timedelta(hours=1))


def test_unrecognized_code_stops_before_writing_output(tmp_path,monkeypatch):
    project,market,meta,base,_=prepared(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="SECURITY_INVALID"):
        build(project,market,codes=("999999",))
    assert not list((project/"output").glob("research_flow10_assessments/KR_*.json"))


def test_explicit_cli_rejects_unavailable_file_without_modifying_old(tmp_path):
    from subprocess import run
    from sys import executable
    project=tmp_path/"project";project.mkdir();(project/"output").mkdir()
    script=Path(__file__).resolve().parents[1]/"scripts"/"derive_marketwide_flow_research.py"
    command=[executable,str(script),"--project",str(project),
             "--marketwide-report",str(project/"missing.json"),
             "--base-partial-assessment",str(project/"old.json"),
             "--code-overlay","005930=/unknown/overlay"]
    action=run(command,capture_output=True,text=True)
    assert action.returncode==2
    assert not list((project/"output").glob("research_flow10_assessments/*"))


def test_operational_dashboard_shows_3_research_scores_and_never_formal(tmp_path,monkeypatch):
    from eraleader.operations_overview import audit_local_operations,render_operations_overview
    project,market,meta,base,_=prepared(tmp_path,monkeypatch)
    r=build(project,market)
    snap=audit_local_operations(project,clock=NOW)
    shown=snap["kr_flow10_heuristic_research"]
    assert shown["formal_scores_available"] is False
    assert shown["orders"]==0
    assert [x["code"] for x in shown["research_scores"]]==["000660","005930"]
    html=render_operations_overview(snap)
    assert "정식 10점 아님" in html
    assert html.count("(연구용)")>=2
    shown["research_scores"][0]["research_score_10"]=100
    with pytest.raises(ValueError,match="Unsafe flow research score"):
        render_operations_overview(snap)
    Path(r["file"]).write_bytes(Path(r["file"]).read_bytes()+b"tamper")
    assert audit_local_operations(project,clock=NOW)["kr_flow10_heuristic_research"] is None


def test_rule_metadata_with_recomputed_sha_does_not_override_fixed_heuristic(tmp_path,monkeypatch):
    project,market,meta,base,_=prepared(tmp_path,monkeypatch)
    r=build(project,market)
    f=Path(r["file"])
    doc=json.loads(f.read_bytes())
    doc["component_weight_5"]=0.8
    unsigned=dict(doc)
    unsigned.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(unsigned)).hexdigest()
    f.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="CONTRACT"):
        scoring.read_flow_research(
            f,expected_market_sha=meta["content_sha256"],clock=NOW)
