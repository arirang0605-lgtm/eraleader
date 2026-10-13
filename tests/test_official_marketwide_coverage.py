"""Scoped tests for actual whole-market evidence join and partial coverage."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import copy
import json

import pandas as pd
import pytest
from eraleader import official_marketwide_coverage as module

NOW=datetime(2026,10,14,12,tzinfo=timezone.utc)
CODE_A="005930"
CODE_B="00104K"
CODE_C="000660"


def fixture(tmp_path, monkeypatch):
    cohort=tmp_path/"cohort"
    cohort.mkdir()
    originals=tmp_path/"official"
    originals.mkdir()
    basic={
        "market_session":"2026-10-08","source_watch_run_id":"tracked",
        "comparisons":[{
            "security_id":CODE_A,"name":"삼성전자","revenue_yoy":0.1,
            "operating_income_yoy":0.2,"revenue_yoy_acceleration":0.05,
            "comparison_order":1,
            "first_financial_locally_received_at_utc":"2026-10-13T12:00:00+00:00",
        }],
    }
    basic["content_sha256"]=sha256(module.canonical(basic)).hexdigest()
    peers={
        "market_session":"2026-10-08",
        "baseline_candidate_sha256":basic["content_sha256"],
        "companies":[{"stock_code":CODE_A,"current_industry_code":"264"}],
        "selected_companies":1,
    }
    peers["content_sha256"]=sha256(module.canonical(peers)).hexdigest()
    evidence={
        "api_observation_day":"2026-10-08","decision_at":"2026-10-13T12:01:00+00:00",
        "historic_universe_pit_verified":False,"official_leaders":0,
        "sources":[
            {"source":"krx-kospi","first_receipt_sha256":"p1","row_count":2},
            {"source":"krx-kosdaq","first_receipt_sha256":"p2","row_count":1},
        ],
    }
    snapshot={"official_api_evidence":evidence,
        "run_id":"tracked",
        "classification_quality":"PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
        "rows":[{"security_id":CODE_B,"rank":1},{"security_id":CODE_A,"rank":2}]}
    from eraleader.discovery import run_id_for
    snapshot["as_of_requested"]="2026-10-13"
    snapshot["run_id"]=run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
    basic["source_watch_run_id"]=snapshot["run_id"]
    old_sha=basic["content_sha256"]
    basic.pop("content_sha256")
    basic["content_sha256"]=sha256(module.canonical(basic)).hexdigest()
    peers["baseline_candidate_sha256"]=basic["content_sha256"]
    peers.pop("content_sha256")
    peers["content_sha256"]=sha256(module.canonical(peers)).hexdigest()
    (cohort/"kr_latest.json").write_text(json.dumps(snapshot))
    (cohort/"official_api_pit_research.json").write_text("{}")
    monkeypatch.setattr(module,"_verified",lambda path,schema: (
        (basic if schema==module.BASIC else peers),b"test"))
    monkeypatch.setattr(module,"source_eligible_universe",lambda *a,**kw: (
        {CODE_A:{"name":"삼성전자"},CODE_C:{"name":"SK하이닉스"}},
        (originals/"directory","d"*64),{"market_session":"2026-10-08","krx_rows":3}))
    monkeypatch.setattr(module,"_all_pinned",lambda root:{
        "p1":originals/"p1","p2":originals/"p2"})
    monkeypatch.setattr(module,"verified_capture",
        lambda path,source,pin,clock: (
            {"row_count":2 if source=="krx-kospi" else 1},{}))
    def frame(source,meta,raw):
        codes=[(CODE_A,"삼성전자"),(CODE_B,"CJ4우(전환)")] if (
            source=="krx-kospi") else [(CODE_C,"SK하이닉스")]
        return pd.DataFrame([{
            "security_id":code,"name":name,
            "venue":"KOSPI" if source=="krx-kospi" else "KOSDAQ",
            "session":pd.Timestamp("2026-10-08"),"close":100.0,
            "turnover":100000.0,"market_cap":1000000.0,"volume":100.0,
        } for code,name in codes])
    monkeypatch.setattr(module,"_krx_frame",frame)
    return cohort,originals,basic,peers,evidence


def test_marketwide_joins_all_krx_even_without_financial_or_industry(tmp_path,monkeypatch):
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    assert report["official_krx_observed"]==3
    assert report["current_dart_directory_matched"]==2
    assert report["financial_factors_observed"]==1
    assert report["industry_factors_observed"]==1
    assert report["flow_factors_observed"]==0
    assert report["official_leaders"]==0
    assert report["full_market_composite_rank_available"] is False
    securities={row["security_id"]:row for row in report["securities"]}
    assert securities[CODE_A]["revenue_yoy"]==0.1
    assert securities[CODE_A]["industry_code"]=="264"
    assert securities[CODE_B]["current_dart_directory_matched"] is False
    assert securities[CODE_B]["revenue_yoy"] is None
    assert securities[CODE_B]["price_top20_watch_rank"]==1
    assert securities[CODE_B]["verified_leader_state"] is None
    path,page=module.publish_marketwide_coverage(report,tmp_path/"publish")
    assert path.is_file() and page.is_file()
    assert json.loads(path.read_bytes())==report
    assert "N/A" in page.read_text()


def test_marketwide_rejects_issuer_mismatch(tmp_path,monkeypatch):
    cohort,root,basic,*_=fixture(tmp_path,monkeypatch)
    basic["comparisons"][0]["name"]="다른종목"
    with pytest.raises(ValueError,match="ISSUER_MISMATCH"):
        module.build_marketwide_coverage(cohort,root,clock=NOW)


def test_marketwide_rejects_future_source_and_conflicting_session(tmp_path,monkeypatch):
    cohort,root,basic,peers,evidence=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="SOURCE_FUTURE"):
        module.build_marketwide_coverage(cohort,root,clock=NOW-timedelta(days=3))
    peers["market_session"]="2026-10-09"
    with pytest.raises(ValueError,match="COHORT_SOURCE_MISMATCH"):
        module.build_marketwide_coverage(cohort,root,clock=NOW)


def test_marketwide_rejects_duplicate_and_report_tampering(tmp_path,monkeypatch):
    cohort,root,basic,*_=fixture(tmp_path,monkeypatch)
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    report["securities"][0]["formal_leader_score_100"]=99
    with pytest.raises(ValueError,match="REPORT_INVALID"):
        module.publish_marketwide_coverage(report,tmp_path/"bad")
    data=json.loads((cohort/"kr_latest.json").read_bytes())
    data["rows"].append(copy.deepcopy(data["rows"][0]))
    (cohort/"kr_latest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError,match="PRICE_SNAPSHOT_TAMPERED"):
        module.build_marketwide_coverage(cohort,root,clock=NOW)


def test_price_watch_cfs_auto_selection_uses_exact_company_and_order():
    from eraleader.official_dart_multi_company import choose_price_watch_company_batch
    official={"historic_universe_pit_verified":False,"official_leaders":0}
    snapshot={"official_api_evidence":official,
              "as_of_requested":"2026-10-13",
              "classification_quality":"PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
              "rows":[
                  {"rank":1,"security_id":"00104K","name":"CJ우","venue":"KOSPI"},
                  {"rank":2,"security_id":"005930","name":"삼성전자","venue":"KOSPI"},
                  {"rank":3,"security_id":"000660","name":"SK하이닉스","venue":"KOSPI"},
              ]}
    from eraleader.discovery import run_id_for
    snapshot["run_id"]=run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
    eligible={"005930":{"name":"삼성전자","venue":"KOSPI"},
              "000660":{"name":"SK하이닉스","venue":"KOSPI"}}
    assert choose_price_watch_company_batch(snapshot,official,eligible,limit=1)==("005930",)
    assert choose_price_watch_company_batch(snapshot,official,eligible,start_rank=3)==("000660",)
    wrong={**eligible,"000660":{"name":"다른종목","venue":"KOSPI"}}
    with pytest.raises(ValueError,match="identity mismatch"):
        choose_price_watch_company_batch(snapshot,official,wrong,start_rank=3)
    with pytest.raises(ValueError,match="not backed"):
        choose_price_watch_company_batch(snapshot,{"other":True},eligible)


def test_marketwide_additional_real_finance_receipt_joins_without_industry(tmp_path,monkeypatch):
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    original=module._all_pinned(root)
    pins={"a"*64:root/"fy2024","b"*64:root/"fy2025",**original}
    monkeypatch.setattr(module,"_all_pinned",lambda _:pins)
    monkeypatch.setattr(module,"verify_dart_financial",
        lambda folder,pin,**k:{"stock_code":CODE_C,
          "year":2024 if pin=="a"*64 else 2025,
          "statement":"CFS","report_code":"11011"})
    monkeypatch.setattr(module,"annual_growth_diagnostic",
        lambda a,b:{"research_metrics":{
            "revenue_yoy":0.42,"operating_income_yoy":0.11}})
    manifest={"schema":"eraleader.dart_bounded_multi_company_cfs.v1",
              "official_market":{"market_session":"2026-10-08"},
              "research_only":True,"real_investment_leader_ranked":False,
              "companies":[{"stock_code":CODE_C,"name":"SK하이닉스",
                 "research_annual_cfs_complete":True,
                 "annual_reports":[{"fiscal_year":2024,"first_receipt_sha256":"a"*64},
                                   {"fiscal_year":2025,"first_receipt_sha256":"b"*64}]}]}
    file=tmp_path/"manifest.json"
    file.write_text(json.dumps(manifest))
    report=module.build_marketwide_coverage(cohort,root,clock=NOW,
                                            extra_cfs_manifests=(file,))
    assert report["financial_factors_observed"]==2
    row=next(x for x in report["securities"] if x["security_id"]==CODE_C)
    assert row["revenue_yoy"]==0.42
    assert row["industry_code"] is None
    assert row["institutional_flow"] is None


def test_marketwide_incomplete_extra_financials_are_na_not_zero(tmp_path,monkeypatch):
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    manifest={"schema":"eraleader.dart_bounded_multi_company_cfs.v1",
              "official_market":{"market_session":"2026-10-08"},
              "research_only":True,"real_investment_leader_ranked":False,
              "companies":[{"stock_code":CODE_C,"name":"SK하이닉스",
                 "research_annual_cfs_complete":False,"annual_reports":[
                     {"fiscal_year":2024,"status":"NOT_CAPTURED"},
                     {"fiscal_year":2025,"status":"NOT_CAPTURED"}]}]}
    file=tmp_path/"incomplete.json"
    file.write_text(json.dumps(manifest))
    report=module.build_marketwide_coverage(cohort,root,clock=NOW,
                                            extra_cfs_manifests=(file,))
    assert report["incomplete_additional_financial_companies"]==1
    assert report["financial_factors_observed"]==1
    row=next(x for x in report["securities"] if x["security_id"]==CODE_C)
    assert row["revenue_yoy"] is None



def test_marketwide_handoff_exports_research_watch_not_selected(tmp_path,monkeypatch):
    from eraleader.strategy_handoff import (
        marketwide_research_handoff,publish_handoff,verify_handoff,
    )
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    jsonfile,_=module.publish_marketwide_coverage(report,tmp_path/"coverage")
    feed=marketwide_research_handoff(jsonfile,request_day="2026-10-14",clock=NOW)
    assert feed["watchlist_count"]==2
    assert feed["selection_count"]==0 and not feed["selected_candidates"]
    assert [r["security_id"] for r in feed["research_watchlist"]]==[CODE_B,CODE_A]
    assert all(r["score_100"] is None for r in feed["research_watchlist"])
    assert feed["data_stale"] is True
    assert feed["order_instruction"] is False
    out=tmp_path/"handoff.json"
    assert publish_handoff(feed,out)["status"]=="DELIVERED_TO_INBOX"
    assert verify_handoff(out,expected_market="KR")==feed
    assert publish_handoff(feed,out)["status"]=="ALREADY_DELIVERED"


def test_marketwide_handoff_fails_on_modified_source_and_future(tmp_path,monkeypatch):
    from eraleader.strategy_handoff import marketwide_research_handoff
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    jsonfile,_=module.publish_marketwide_coverage(report,tmp_path/"coverage")
    source=json.loads(jsonfile.read_text())
    source["securities"][0]["formal_leader_score_100"]=100
    jsonfile.write_text(json.dumps(source))
    with pytest.raises(ValueError,match="SOURCE_INVALID"):
        marketwide_research_handoff(jsonfile,request_day="2026-10-14",clock=NOW)


def test_marketwide_extra_industry_only_on_verified_financial_issuer(tmp_path,monkeypatch):
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    base=module._all_pinned(root)
    monkeypatch.setattr(module,"_all_pinned",lambda _:{
        **base,"a"*64:root/"fy2024","b"*64:root/"fy2025","c"*64:root/"industry"})
    monkeypatch.setattr(module,"verify_dart_financial",
        lambda folder,pin,**kw:{"stock_code":CODE_C,
          "year":2024 if pin=="a"*64 else 2025,
          "statement":"CFS","report_code":"11011"})
    monkeypatch.setattr(module,"annual_growth_diagnostic",
        lambda a,b:{"research_metrics":{"revenue_yoy":0.18,"operating_income_yoy":0.12}})
    monkeypatch.setattr(module,"verify_company_profile",
        lambda folder,pin,**kw:{"stock_code":CODE_C,"current_dart_industry_code":"261"})
    financial={"schema":"eraleader.dart_bounded_multi_company_cfs.v1",
               "official_market":{"market_session":"2026-10-08"},
               "research_only":True,"real_investment_leader_ranked":False,
               "companies":[{"stock_code":CODE_C,"name":"SK하이닉스",
                              "research_annual_cfs_complete":True,
                              "annual_reports":[
                                 {"fiscal_year":2024,"first_receipt_sha256":"a"*64},
                                 {"fiscal_year":2025,"first_receipt_sha256":"b"*64}]}]}
    financial_file=tmp_path/"extra_cfs.json"
    financial_file.write_text(json.dumps(financial))
    industry={"schema":"eraleader.dart_industry_profile_cohort.v1",
              "source_directory_sha256":"d"*64,
              "historic_industry_pit_certified":False,
              "companies_requested":1,
              "companies":[{"stock_code":CODE_C,"first_receipt_sha256":"c"*64,
                            "current_dart_industry_code":"261"}]}
    # Fixture returns a directory PIN of None. It remains stable across joins.
    industry_file=tmp_path/"extra_industry.json"
    industry_file.write_text(json.dumps(industry))
    joined=module.build_marketwide_coverage(
        cohort,root,clock=NOW,extra_cfs_manifests=(financial_file,),
        extra_industry_manifests=(industry_file,))
    assert joined["financial_factors_observed"]==2
    assert joined["industry_factors_observed"]==2
    row=next(x for x in joined["securities"] if x["security_id"]==CODE_C)
    assert row["industry_code"]=="261"
    # Industry without a matching verified two-year CFS must not be attached.
    with pytest.raises(ValueError,match="COMPANY_NOT_FINANCIAL"):
        module.build_marketwide_coverage(
            cohort,root,clock=NOW,extra_industry_manifests=(industry_file,))


def test_two_factor_research_order_uses_actual_price_and_finance_only(tmp_path,monkeypatch):
    cohort,root,basic,peers,evidence=fixture(tmp_path,monkeypatch)
    snapshot=json.loads((cohort/"kr_latest.json").read_text())
    snapshot["rows"][0]["price_strength_25"]=23.5
    snapshot["rows"][1]["price_strength_25"]=19.0
    from eraleader.discovery import run_id_for
    snapshot["run_id"]=run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
    (cohort/"kr_latest.json").write_text(json.dumps(snapshot))
    basic["source_watch_run_id"]=snapshot["run_id"]
    basic["comparisons"][0]["price_strength_25"]=19.0
    basic.pop("content_sha256")
    basic["content_sha256"]=sha256(module.canonical(basic)).hexdigest()
    peers["baseline_candidate_sha256"]=basic["content_sha256"]
    peers.pop("content_sha256")
    peers["content_sha256"]=sha256(module.canonical(peers)).hexdigest()
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    assert report["two_factor_research_evaluable"]==1
    assert report["two_factor_research_top20"][0]["security_id"]==CODE_A
    assert report["two_factor_research_top20"][0]["official_leader"] is False
    stock={row["security_id"]:row for row in report["securities"]}
    assert stock[CODE_A]["two_factor_research_50"] > 19
    assert stock[CODE_B]["two_factor_research_50"] is None
    assert stock[CODE_B]["two_factor_research_rank"] is None
    assert stock[CODE_A]["formal_leader_score_100"] is None
    _,page=module.publish_marketwide_coverage(report,tmp_path/"rankpage")
    assert "연구 비교 TOP20" in page.read_text()


def test_marketwide_turnover_auto_batch_skips_observed_financial_and_reuses_issuer():
    from eraleader.official_dart_multi_company import choose_marketwide_turnover_cfs_batch
    evidence={"api_observation_day":"2026-10-08",
              "historic_universe_pit_verified":False}
    rows=[
        {"security_id":"005930","name":"삼성전자","venue":"KOSPI",
         "current_dart_directory_matched":True,"turnover":500,"market_cap":1000,
         "market_traded":True,"revenue_yoy":0.15},
        {"security_id":"000660","name":"SK하이닉스","venue":"KOSPI",
         "current_dart_directory_matched":True,"turnover":400,"market_cap":900,
         "market_traded":True,"revenue_yoy":None},
        {"security_id":"035420","name":"NAVER","venue":"KOSPI",
         "current_dart_directory_matched":True,"turnover":300,"market_cap":900,
         "market_traded":True,"revenue_yoy":None},
        {"security_id":"005935","name":"삼성전자우","venue":"KOSPI",
         "current_dart_directory_matched":False,"turnover":800,"market_cap":800,
         "market_traded":True,"revenue_yoy":None},
        {"security_id":"035720","name":"카카오","venue":"KOSPI",
         "current_dart_directory_matched":True,"turnover":0,"market_cap":800,
         "market_traded":False,"revenue_yoy":None},
    ]
    eligible={
        "005930":{"name":"삼성전자","venue":"KOSPI"},
        "000660":{"name":"SK하이닉스","venue":"KOSPI"},
        "035420":{"name":"NAVER","venue":"KOSPI"},
        "035720":{"name":"카카오","venue":"KOSPI"},
    }
    data={"schema":module.SCHEMA,"market":"KR",
          "market_session":"2026-10-08","research_only":True,
          "full_market_composite_rank_available":False,"official_leaders":0,
          "official_krx_observed":len(rows),"securities":rows}
    data["content_sha256"]=sha256(module.canonical(data)).hexdigest()
    assert choose_marketwide_turnover_cfs_batch(data,evidence,eligible)==(
        "000660","035420")
    assert choose_marketwide_turnover_cfs_batch(
        data,evidence,eligible,offset=1,limit=1)==("035420",)
    amended=copy.deepcopy(data)
    amended["securities"][1]["turnover"]=1000
    with pytest.raises(ValueError,match="pinned"):
        choose_marketwide_turnover_cfs_batch(amended,evidence,eligible)
    wrong=dict(eligible)
    wrong["000660"]={"name":"잘못된 이름","venue":"KOSPI"}
    with pytest.raises(ValueError,match="name/venue"):
        choose_marketwide_turnover_cfs_batch(data,evidence,wrong)


def test_marketwide_full_price_reuses_original_ranking_without_promoting(tmp_path,monkeypatch):
    cohort,root,basic,peers,_=fixture(tmp_path,monkeypatch)
    snapshot=json.loads((cohort/"kr_latest.json").read_text())
    snapshot["rows"][0]["price_strength_25"]=24.0
    snapshot["rows"][1]["price_strength_25"]=22.0
    from eraleader.discovery import run_id_for
    snapshot["run_id"]=run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
    (cohort/"kr_latest.json").write_text(json.dumps(snapshot))
    basic["source_watch_run_id"]=snapshot["run_id"]
    basic["comparisons"][0]["price_strength_25"]=22.0
    basic.pop("content_sha256")
    basic["content_sha256"]=sha256(module.canonical(basic)).hexdigest()
    peers["baseline_candidate_sha256"]=basic["content_sha256"]
    peers.pop("content_sha256")
    peers["content_sha256"]=sha256(module.canonical(peers)).hexdigest()
    monkeypatch.setattr(module,"read_market_bars",lambda *a,**kw: (
        pd.DataFrame({"session":pd.to_datetime([])}),{}))
    monkeypatch.setattr(module,"validate_bars",lambda data,asof,quarantine=False:data)
    original_scores=[
        {"security_id":CODE_B,"name":"CJ4우(전환)","price_strength_25":24.0},
        {"security_id":CODE_A,"name":"삼성전자","price_strength_25":22.0},
        {"security_id":CODE_C,"name":"SK하이닉스","price_strength_25":20.0},
    ]
    monkeypatch.setattr(module,"score_price_observations",
        lambda *a,**kw:{"market_last_observation":"2026-10-08",
                         "rows":original_scores})
    report=module.build_marketwide_coverage(
        cohort,root,clock=NOW,full_price_lookback=True,
        legacy_root=tmp_path)
    assert report["local_price_lookback_evaluable"]==3
    assert report["two_factor_research_evaluable"]==1
    matched={row["security_id"]:row for row in report["securities"]}
    assert matched[CODE_C]["price_strength_25"]==20.0
    assert matched[CODE_C]["two_factor_research_50"] is None
    assert report["official_leaders"]==0
    original_scores[0]["price_strength_25"]=24.5
    with pytest.raises(ValueError,match="NOT_SAME_AS_WATCH"):
        module.build_marketwide_coverage(
            cohort,root,clock=NOW,full_price_lookback=True,legacy_root=tmp_path)


def test_current_industry_peer_diagnostics_keep_sample_rank_not_leader():
    companies={
        "A":{"security_id":"000001","current_dart_directory_matched":True,
             "industry_code":"29271","revenue_yoy":0.20,
             "operating_income_yoy":0.09},
        "B":{"security_id":"000002","current_dart_directory_matched":True,
             "industry_code":"29271","revenue_yoy":0.20,
             "operating_income_yoy":None},
        "C":{"security_id":"000003","current_dart_directory_matched":True,
             "industry_code":"29271","revenue_yoy":0.10,
             "operating_income_yoy":0.24},
        "D":{"security_id":"000004","current_dart_directory_matched":True,
             "industry_code":"582","revenue_yoy":0.50,
             "operating_income_yoy":0.12},
        "E":{"security_id":"000005","current_dart_directory_matched":False,
             "industry_code":"29271","revenue_yoy":0.60,
             "operating_income_yoy":0.20}
    }
    audit=module.attach_observed_industry_peers(companies)
    assert audit["same_industry_sample_company_count"]==3
    assert len(audit["same_industry_sample_groups"])==1
    assert audit["revenue_yoy_peer_evaluable"]==3
    assert audit["operating_income_yoy_peer_evaluable"]==2
    assert companies["A"]["peer_revenue_yoy_rank"]==1
    assert companies["B"]["peer_revenue_yoy_rank"]==1
    assert companies["C"]["peer_revenue_yoy_rank"]==3
    assert companies["C"]["peer_operating_yoy_rank"]==1
    assert companies["B"]["peer_operating_yoy_rank"] is None
    assert companies["D"]["peer_revenue_yoy_rank"] is None
    assert companies["E"]["peer_revenue_yoy_rank"] is None
    with pytest.raises(ValueError,match="PEER_NONFINITE"):
        module.attach_observed_industry_peers({
            "A":dict(companies["A"],revenue_yoy=float("nan")),
            "B":dict(companies["B"])})


def test_saved_verified_marketwide_flow_join_is_session_exact(tmp_path,monkeypatch):
    from eraleader.kiwoom_investor_flow import canonical as flow_canonical
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    original=module.build_marketwide_coverage(cohort,root,clock=NOW)
    source,_=module.publish_marketwide_coverage(original,tmp_path/"original_marketwide")
    flow_folder=tmp_path/"kiwoom_flow"
    flow_folder.mkdir(mode=0o700)
    report={
        "security_id":CODE_A,"requested_day":"20261008",
        "latest_observed_day":"20261008","environment_mode":"demo",
        "observed_rows":20,
        "flow_20_observed_sessions":{"foreign_net_shares":14,
                                      "institution_net_shares":-9}
    }
    report["content_sha256"]=sha256(flow_canonical(report)).hexdigest()
    flow_raw=flow_canonical(report)+b"\n"
    (flow_folder/f"{CODE_A}.json").write_bytes(flow_raw)
    manifest={"schema":"eraleader.kiwoom_selected_flow_capture_manifest.v1",
              "provider":"KIWOOM_REST_KA10059","unit":"shares",
              "environment_mode":"demo","trading_enabled":False,
              "requested_day":"20261008","companies":1,
              "files":[{"security_id":CODE_A,"filename":f"{CODE_A}.json",
                        "rows":20,"sha256":sha256(flow_raw).hexdigest()}]}
    manifest["content_sha256"]=sha256(flow_canonical(manifest)).hexdigest()
    (flow_folder/"manifest.json").write_bytes(flow_canonical(manifest)+b"\n")
    monkeypatch.setattr(module,"verify_flow",lambda obj,**kw:obj)
    later=NOW+timedelta(minutes=4)
    joined=module.refresh_saved_marketwide_flow(
        source,flow_folder,clock=later)
    actual=next(x for x in joined["securities"] if x["security_id"]==CODE_A)
    assert actual["foreign_flow"]==14
    assert actual["institutional_flow"]==-9
    assert joined["flow_factors_observed"]==1
    assert joined["flow_mismatched_session_companies"]==0
    assert joined["previous_research_sha256"]==original["content_sha256"]
    assert json.loads(source.read_bytes())==original
    # Simulate a newer valid capture with an observed day that doesn't match KRX.
    report["latest_observed_day"]="20261009"
    report["requested_day"]="20261009"
    report.pop("content_sha256")
    report["content_sha256"]=sha256(flow_canonical(report)).hexdigest()
    newer=flow_canonical(report)+b"\n"
    (flow_folder/f"{CODE_A}.json").write_bytes(newer)
    manifest["requested_day"]="20261009"
    manifest["files"][0]["sha256"]=sha256(newer).hexdigest()
    manifest.pop("content_sha256")
    manifest["content_sha256"]=sha256(flow_canonical(manifest)).hexdigest()
    (flow_folder/"manifest.json").write_bytes(flow_canonical(manifest)+b"\n")
    stale=module.refresh_saved_marketwide_flow(
        source,flow_folder,clock=later)
    row=next(x for x in stale["securities"] if x["security_id"]==CODE_A)
    assert stale["flow_factors_observed"]==0
    assert stale["flow_mismatched_session_companies"]==1
    assert row["foreign_flow"] is None and row["institutional_flow"] is None
    # A file tamper must not be rendered or rewritten into a new report.
    (flow_folder/f"{CODE_A}.json").write_bytes(b'{"tampered":true}')
    with pytest.raises(ValueError,match="FLOW_RECEIPT_SHA_INVALID"):
        module.refresh_saved_marketwide_flow(source,flow_folder,clock=later)


def test_marketwide_two_factor_comparison_passes_only_as_nontrading_research(tmp_path,monkeypatch):
    from eraleader.strategy_handoff import (
        marketwide_research_handoff,publish_handoff,verify_handoff
    )
    cohort,root,*_=fixture(tmp_path,monkeypatch)
    report=module.build_marketwide_coverage(cohort,root,clock=NOW)
    company=next(r for r in report["securities"] if r["security_id"]==CODE_A)
    company["two_factor_research_rank"]=1
    company["two_factor_research_50"]=35.5
    report["two_factor_research_evaluable"]=1
    report["two_factor_research_top20"]=[{
        "research_order":1,"security_id":CODE_A,
        "name":company["name"],"observed_score_50":35.5,
        "official_leader":False,
    }]
    report.pop("content_sha256")
    report["content_sha256"]=sha256(module.canonical(report)).hexdigest()
    source,_=module.publish_marketwide_coverage(report,tmp_path/"source_rank")
    handoff=marketwide_research_handoff(
        source,request_day="2026-10-14",clock=NOW)
    assert handoff["two_factor_research_count"]==1
    assert handoff["selection_count"]==0
    assert handoff["two_factor_research_watchlist"][0]["selection_state"]=="WATCH"
    assert handoff["two_factor_research_watchlist"][0]["strategy_research_allowed"] is False
    assert handoff["two_factor_research_watchlist"][0]["score_100"] is None
    dest=tmp_path/"out.json"
    publish_handoff(handoff,dest)
    assert verify_handoff(dest,expected_market="KR")==handoff
    # A validly re-hashed but falsely promoted observation is still rejected.
    invalid=copy.deepcopy(handoff)
    invalid["two_factor_research_watchlist"][0]["selection_state"]="CONFIRMED"
    invalid.pop("content_sha256")
    invalid["content_sha256"]=sha256(module.canonical(invalid)).hexdigest()
    second=tmp_path/"invalid.json"
    second.write_bytes(module.canonical(invalid)+b"\n")
    with pytest.raises(ValueError,match="HANDOFF_50_RESEARCH_ROW_INVALID"):
        verify_handoff(second)
