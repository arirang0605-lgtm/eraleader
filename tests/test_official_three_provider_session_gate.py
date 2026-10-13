"""Synthetic PIT and real-file receipt contracts for the three-provider gate."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import pytest

from eraleader.official_api_capture import capture_official_api
from eraleader.official_three_provider_session_gate import (
    evaluate, verify_live_captures, verified_local_capture, render
)
from eraleader.kiwoom_investor_flow import canonical
from test_kiwoom_live_research_panel import sample_flow

STAMP=datetime(2026,10,13,11,tzinfo=timezone.utc)
CREDS={"ERALEADER_KRX_AUTH_KEY":"A"*40,"ERALEADER_DART_API_KEY":"B"*40}
DAY="2026-10-13"

def originals(*,krx_rows=True,dart_all=True):
    day="20261013"
    market=[
        {"BAS_DD":day,"ISU_CD":"005930","ISU_NM":"삼성전자",
         "TDD_CLSPRC":"71,000"},
    ] if krx_rows else []
    kosdaq=[{"BAS_DD":day,"ISU_CD":"000660","ISU_NM":"SK하이닉스",
             "TDD_CLSPRC":"180,000"}] if krx_rows else []
    def package(src,rows,body,quality):
        return {"schema":"eraleader.official_api_first_received_raw.v1",
                "source":src,"request_value":DAY,
                "provider_row_count":rows,"quality":quality,
                "full_historic_universe_pit_certified":False,
                "first_local_received_at_utc":"2026-10-13T10:00:00+00:00",
                "first_receipt_sha256":sha256(src.encode()).hexdigest(),"body":body}
    dart_rows=[{"rcept_no":"20261013000001","rcept_dt":day}]
    return {
        "krx-kospi":package("krx-kospi",len(market),{"OutBlock_1":market},
                            "ROWS_RECEIVED_NOT_PIT_CERTIFIED" if market else "NO_DAILY_ROWS"),
        "krx-kosdaq":package("krx-kosdaq",len(kosdaq),{"OutBlock_1":kosdaq},
                             "ROWS_RECEIVED_NOT_PIT_CERTIFIED" if kosdaq else "NO_DAILY_ROWS"),
        "dart-disclosures":package("dart-disclosures",1 if dart_all else 100,
                                  {"status":"000","list":dart_rows},
                                  "ROWS_RECEIVED_NOT_PIT_CERTIFIED" if dart_all else "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY"),
    }

def calc(sources=None,flow=None):
    return evaluate(requested_day=DAY,security_id="005930",
                    originals=sources if sources is not None else originals(),
                    flow=flow if flow is not None else sample_flow(),
                    decision_at=STAMP)

def test_three_sources_same_day_can_observe_but_never_rank():
    result=calc()
    assert result["readiness"]=="SAME_DAY_RESEARCH_OBSERVABLE_NOT_CERTIFIED"
    assert result["can_compare_same_session_research"] is True
    assert result["historical_source_publication_pit_certified"] is False
    assert result["issuer_share_class_independently_certified"] is False
    assert result["production_kiwoom_flow_certified"] is False
    assert result["investment_leader_score_available"] is False
    assert result["trade_signal"] is None and result["orders_enabled"] is False
    assert result["official_leaders"]==0
    assert "공식" in render(result)

def test_provider_empty_day_and_incomplete_dart_fail_closed():
    status=calc(originals(krx_rows=False,dart_all=False))
    assert status["readiness"]=="PAUSED_MISSING_OR_INCOMPLETE_OFFICIAL_EVIDENCE"
    assert status["can_compare_same_session_research"] is False
    assert set(status["blockers"])=={
        "KRX_ONE_OR_BOTH_MARKETS_EMPTY","SELECTED_ISSUE_NOT_IN_SAME_DAY_KRX",
        "DART_DAY_NOT_COMPLETE_OR_PROVIDER_NO_DATA"}

def test_dart_first_page_incomplete_is_not_admissible_even_if_market_ok():
    result=calc(originals(dart_all=False))
    assert result["blockers"]==["DART_DAY_NOT_COMPLETE_OR_PROVIDER_NO_DATA"]

def test_no_selected_security_in_same_day_exchange_blocks():
    originals1=originals()
    originals1["krx-kospi"]["body"]["OutBlock_1"][0]["ISU_CD"]="005380"
    result=calc(originals1)
    assert "SELECTED_ISSUE_NOT_IN_SAME_DAY_KRX" in result["blockers"]

def test_market_duplicate_issuer_denied():
    originals1=originals()
    originals1["krx-kosdaq"]["body"]["OutBlock_1"][0]["ISU_CD"]="005930"
    with pytest.raises(ValueError,match="multiple"):
        calc(originals1)

@pytest.mark.parametrize("key",("krx-kospi","krx-kosdaq","dart-disclosures"))
def test_wrong_source_day_refused(key):
    originals1=originals()
    originals1[key]["request_value"]="2026-10-12"
    with pytest.raises(ValueError):
        calc(originals1)

def test_future_first_receipt_denied():
    origins=originals()
    origins["krx-kospi"]["first_local_received_at_utc"]="2026-10-13T12:30:00Z"
    with pytest.raises(ValueError,match="not available"):
        calc(origins)

def test_simulated_production_flow_refused():
    flow=sample_flow()
    flow["environment_mode"]="real"
    flow.pop("content_sha256")
    flow["content_sha256"]=sha256(canonical(flow)).hexdigest()
    with pytest.raises(ValueError,match="market/issuer mismatch"):
        calc(flow=flow)

def test_flow_not_available_at_historical_decision_refused():
    with pytest.raises(ValueError):
        evaluate(requested_day=DAY,security_id="005930",
                 originals=originals(),flow=sample_flow(),
                 decision_at=STAMP-timedelta(hours=5))

def test_research_html_checksum_tamper_denied():
    report=calc()
    report["blockers"].append("FAKE")
    with pytest.raises(ValueError):
        render(report)

def capture_triplet(tmp_path):
    root=tmp_path/"private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    raws={
        "krx-kospi":{"OutBlock_1":[{"BAS_DD":"20261013","ISU_CD":"005930",
                                     "ISU_NM":"삼성전자","TDD_CLSPRC":"71000"}]},
        "krx-kosdaq":{"OutBlock_1":[{"BAS_DD":"20261013","ISU_CD":"000660",
                                      "ISU_NM":"SK하이닉스","TDD_CLSPRC":"181000"}]},
        "dart-disclosures":{"status":"000","total_count":"1",
                            "list":[{"rcept_dt":"20261013","rcept_no":"20261013000001"}]},
    }
    sources={}
    for name,blob in raws.items():
        out=capture_official_api(
            name,root,day=DAY,creds=CREDS,
            fetch=lambda url,headers,doc=blob: json.dumps(doc).encode(),
            clock=lambda: STAMP-timedelta(minutes=2))
        sources[name]=(root/out["capture_id"],out["first_receipt_sha256"])
    return sources

def test_cryptographically_verified_official_files_pit(tmp_path):
    s=capture_triplet(tmp_path)
    result=verify_live_captures(
        krx_kospi=s["krx-kospi"],krx_kosdaq=s["krx-kosdaq"],
        dart_disclosures=s["dart-disclosures"],
        market_day=DAY,security_id="005930",flow=sample_flow(),
        decision_at=STAMP)
    assert result["can_compare_same_session_research"] is True
    assert result["orders_enabled"] is False
    root,pin=s["krx-kospi"]
    assert verified_local_capture(root,"krx-kospi",pin,STAMP)[0]["provider_row_count"]==1
    with pytest.raises(ValueError,match="PIN"):
        verified_local_capture(root,"krx-kospi","0"*64,STAMP)
    with pytest.raises(ValueError,match="arrived after"):
        verified_local_capture(root,"krx-kospi",pin,STAMP-timedelta(hours=2))

def test_immutable_original_raw_tamper_blocks_verification(tmp_path):
    s=capture_triplet(tmp_path)
    folder,pin=s["dart-disclosures"]
    p=folder/"raw_response.json"
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError):
        verified_local_capture(folder,"dart-disclosures",pin,STAMP)

def test_end_to_end_cli_publish_from_pinned_synthetic_sources(tmp_path):
    from scripts.capture_kiwoom_investor_flow import capture
    from scripts.publish_three_provider_session_gate import publish
    s=capture_triplet(tmp_path)
    private=tmp_path/"private"
    flows=private/"captured_kiwoom"
    captured=sample_flow()
    capture(
        codes=["005930"],market_day="20261013",out=flows,
        token="SYNTHETIC_LOCAL_READ_ONLY",environment_mode="demo",
        fetch=lambda **kwargs:captured,post=lambda *args: ({},{}))
    site=tmp_path/"site"
    site.mkdir()
    index=site/"index.html"
    index.write_text("<!doctype html><html><body>ORIGINAL_RESEARCH</body></html>")
    result=publish(
        kospi=s["krx-kospi"],kosdaq=s["krx-kosdaq"],
        dart=s["dart-disclosures"],manifest=flows/"manifest.json",
        day=DAY,code="005930",site=site,decision=STAMP)
    assert result["can_compare_same_session_research"] is True
    assert result["official_leaders"]==0 and result["orders"]==0
    assert result["status"]=="SAME_DAY_RESEARCH_OBSERVABLE_NOT_CERTIFIED"
    assert (site/result["dashboard"]).is_file()
    assert "ORIGINAL_RESEARCH" in index.read_text()
    assert index.read_text().count("provider_session_20261013")==1
    receipt=json.loads((site/"provider_session_20261013"/"report.json").read_text())
    orig=receipt.copy()
    pin=orig.pop("content_sha256")
    assert sha256(canonical(orig)).hexdigest()==pin
    with pytest.raises(FileExistsError):
        publish(kospi=s["krx-kospi"],kosdaq=s["krx-kosdaq"],
                dart=s["dart-disclosures"],manifest=flows/"manifest.json",
                day=DAY,code="005930",site=site,decision=STAMP)

def test_wrong_pinned_dart_receipt_cannot_publish(tmp_path):
    from scripts.capture_kiwoom_investor_flow import capture
    from scripts.publish_three_provider_session_gate import publish
    s=capture_triplet(tmp_path)
    flows=tmp_path/"private"/"kiwoom"
    capture(codes=["005930"],market_day="20261013",out=flows,
            token="SYNTHETIC",environment_mode="demo",
            fetch=lambda **kwargs:sample_flow(),post=lambda *args: ({},{}))
    site=tmp_path/"site"
    site.mkdir()
    index=site/"index.html"
    original="<!doctype html><html><body>UNCHANGED</body></html>"
    index.write_text(original)
    folder,_=s["dart-disclosures"]
    s["dart-disclosures"]=(folder,"0"*64)
    with pytest.raises(ValueError,match="PIN"):
        publish(kospi=s["krx-kospi"],kosdaq=s["krx-kosdaq"],
                dart=s["dart-disclosures"],manifest=flows/"manifest.json",
                day=DAY,code="005930",site=site,decision=STAMP)
    assert index.read_text()==original
    assert sorted(file.name for file in site.iterdir())==["index.html"]
