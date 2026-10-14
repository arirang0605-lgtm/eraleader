"""Real P2 factor coverage reports never promote incomplete official research."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import copy
import json
import pytest

from eraleader.official_marketwide_coverage import SCHEMA as MARKETWIDE
from eraleader.official_company_explorer import canonical
from eraleader.official_p2_readiness import (
    build_p2_readiness,publish_p2_readiness,SCHEMA,
)
from eraleader.state_history import StateHistory

NOW=datetime(2026,10,14,10,tzinfo=timezone.utc)

def original(tmp_path):
    content={
        "schema":MARKETWIDE,"market":"KR","market_session":"2026-10-13",
        "built_at_utc":"2026-10-13T07:00:00+00:00",
        "research_only":True,"official_leaders":0,
        "full_market_composite_rank_available":False,
        "official_krx_observed":4,
        "current_dart_directory_matched":3,
        "financial_factors_observed":3,
        "industry_factors_observed":3,
        "flow_factors_observed":0,
        "two_factor_research_evaluable":2,
        "securities":[
            {"security_id":"00104K","name":"우선주","price_strength_25":24.,
             "earnings_research_25":None,"two_factor_research_50":None,
             "industry_code":None,"institutional_flow":None},
            {"security_id":"005930","name":"삼성전자","price_strength_25":20.,
             "earnings_research_25":16.,"two_factor_research_50":36.,
             "industry_code":"261","institutional_flow":10000},
            {"security_id":"000660","name":"SK하이닉스","price_strength_25":21.,
             "earnings_research_25":15.,"two_factor_research_50":36.,
             "industry_code":"261","institutional_flow":None},
            {"security_id":"035420","name":"네이버","price_strength_25":None,
             "earnings_research_25":20.,"two_factor_research_50":None,
             "industry_code":"631","institutional_flow":None},
        ],
    }
    for rank,row in enumerate(content["securities"],1):
        row["price_top20_watch_rank"]=rank
        row["revenue_yoy"]=None
    content["content_sha256"]=sha256(canonical(content)).hexdigest()
    path=tmp_path/"observed.json"
    path.write_bytes(canonical(content)+b"\n")
    return path


def test_two_factors_observed_but_five_factor_leaders_still_zero(tmp_path):
    source=original(tmp_path)
    report=build_p2_readiness(source,clock=NOW)
    assert report["observed_market_securities"]==4
    assert report["observed_factor_counts"]=={
        "industry":0,"competitiveness":0,"earnings":3,"momentum":3,"flow":0}
    assert report["two_factor_research_evaluable"]==2
    assert [r["security_id"] for r in report["top20_for_factor_completion"]]==[
        "000660","005930"]
    assert report["selected_candidates"]==[]
    assert report["full_100_point_ranking_available"] is False
    assert report["total_candidates_eligible_for_verified_100_point_selection"]==0
    assert report["top20_for_factor_completion"][0]["component_scores_100"]["flow"] is None
    assert report["top20_for_factor_completion"][0]["formal_total_score_100"] is None
    assert report["top20_for_factor_completion"][1]["observed_institution_net_shares_20"]==10000
    assert report["top20_for_factor_completion"][1]["component_scores_100"]["flow"] is None
    dest=tmp_path/"published"
    first,site=publish_p2_readiness(report,dest)
    assert json.loads(first.read_bytes())==report
    assert "정식 100점 대장주" in site.read_text()
    with pytest.raises(ValueError,match="OUTPUT_MUST_BE_NEW"):
        publish_p2_readiness(report,dest)


def test_checksum_mismatch_false_selected_and_nonfinite_are_rejected(tmp_path):
    original_file=original(tmp_path)
    tamper=json.loads(original_file.read_bytes())
    tamper["securities"][0]["price_strength_25"]=100
    original_file.write_text(json.dumps(tamper))
    with pytest.raises(ValueError,match="UNTRUSTED"):
        build_p2_readiness(original_file,clock=NOW)
    ok=original(tmp_path)
    doc=json.loads(ok.read_bytes())
    doc["official_leaders"]=1
    doc.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    ok.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="UNTRUSTED"):
        build_p2_readiness(ok,clock=NOW)
    ok=original(tmp_path)
    doc=json.loads(ok.read_bytes())
    doc["securities"][0]["price_strength_25"]=30
    doc.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    ok.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="INVALID_OBSERVED_SCORE"):
        build_p2_readiness(ok,clock=NOW)
    ok=original(tmp_path)
    doc=json.loads(ok.read_bytes())
    doc["securities"][0]["verified_leader_state"]="CONFIRMED"
    doc["securities"][0]["formal_leader_score_100"]=99
    doc.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    ok.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="FALSE_LEADER"):
        build_p2_readiness(ok,clock=NOW)


def test_future_and_duplicate_company_fail_closed(tmp_path):
    ok=original(tmp_path)
    with pytest.raises(ValueError,match="FUTURE"):
        build_p2_readiness(ok,clock=NOW-timedelta(days=5))
    doc=json.loads(ok.read_bytes())
    doc["securities"][3]["security_id"]="000660"
    doc.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    ok.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="DUPLICATE"):
        build_p2_readiness(ok,clock=NOW)


def test_real_stage4_research_watch_count_readonly(tmp_path):
    source=original(tmp_path)
    p=tmp_path/"official_price_watch_state_history.sqlite"
    ledger=StateHistory(p)
    try:
        items=[]
        for code in ("005930","000660"):
            items.append({"security_id":"KR_PRICE_OBSERVED:"+code,
                          "components":{"momentum":20},
                          "evidence":{"financial_pit":False}})
        ledger.record("KR","2026-10-13",items)
    finally:ledger.close()
    info=build_p2_readiness(source,state_history=p,clock=NOW)
    assert info["research_state_history"]=={
        "observed_watch":2,"observed_potential":0,"observed_confirmed":0}
    assert info["selected_candidates"]==[]
    assert (tmp_path/"official_price_watch_state_history.sqlite").exists()


def test_cli_emits_private_json_and_html_without_strategy_orders(tmp_path,capsys):
    from scripts import publish_official_p2_readiness
    source=original(tmp_path)
    rc=publish_official_p2_readiness.main([
        "--marketwide-report",str(source),"--out",str(tmp_path/"results")])
    assert rc==0
    summary=json.loads(capsys.readouterr().out)
    assert summary["official_selected"]==0
    assert summary["research_two_factor"]==2
    assert (tmp_path/"results/index.html").exists()



def test_reuse_existing_snapshot_publishes_p2_without_new_api_or_rank(tmp_path,monkeypatch,capsys):
    from scripts import publish_official_marketwide_coverage as publisher
    saved=original(tmp_path)
    out=tmp_path/"output"
    out.mkdir(mode=0o700)
    monkeypatch.setattr(publisher,"ROOT",tmp_path)
    rc=publisher.main([
        "--reuse-marketwide-report",str(saved),
        "--p2-readiness-out",str(out/"p2"),
        "--out",str(out/"copied_market")])
    assert rc==0
    payload=json.loads(capsys.readouterr().out)
    assert payload["p2_readiness"]["research_two_factor"]==2
    assert payload["p2_readiness"]["official_selected"]==0
    assert payload["observed"]==4
    assert payload["handoff"] is None
    assert (out/"p2/index.html").exists()
    assert saved.exists()
    from eraleader.official_company_explorer import canonical
    stored=json.loads((out/"copied_market/marketwide_kr.json").read_bytes())
    assert stored==json.loads(saved.read_bytes())
    with pytest.raises(SystemExit):
        publisher.main([
            "--reuse-marketwide-report",str(saved),
            "--extra-cfs-manifest",str(saved),
            "--out",str(out/"blocked")])
    assert not (out/"blocked").exists()
