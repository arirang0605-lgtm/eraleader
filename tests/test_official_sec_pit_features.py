"""SEC first-received XBRL diagnostics: all HTTP transport mocked."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from eraleader.official_api_capture import capture_official_api
from eraleader.official_sec_pit_features import audit_sec_financial_asof,save_sec_research

NOW=datetime(2026,10,12,11,11,tzinfo=timezone.utc)
LATER="2026-10-12T12:00:00+00:00"
CREDS={"ERALEADER_SEC_USER_AGENT":"EraLeader Research contact@example.org"}
ACC="0000320193-26-000004"


def _capture(root,source,payload,cik="320193"):
    result=capture_official_api(
        source,root,cik=cik,creds=CREDS,
        fetch=lambda _u,_h:json.dumps(payload).encode(),clock=lambda:NOW)
    return root/result["capture_id"],result["first_receipt_sha256"]


def sec_data():
    sub={"cik":320193,"filings":{"recent":{
        "accessionNumber":[ACC],"acceptanceDateTime":["2026-10-09T16:40:00.000Z"],
        "form":["10-Q"],"filingDate":["2026-10-09"]}}}
    def fact(value,*,accn=ACC,form="10-Q"):
        return {"accn":accn,"filed":"2026-10-09","form":form,
                "start":"2026-07-01","end":"2026-09-30","val":value,
                "fy":2026,"fp":"Q3"}
    company={"cik":320193,"facts":{"us-gaap":{
        "RevenueFromContractWithCustomerExcludingAssessedTax":
            {"units":{"USD":[fact(1200000000)]}},
        "OperatingIncomeLoss":{"units":{"USD":[fact(230000000)]}},
        "NetIncomeLoss":{"units":{"USD":[fact(150000000)]}},
        "EarningsPerShareDiluted":{"units":{"USD/shares":[fact(0.6)]}},
        "Revenues":{"units":{"USD":[fact(1200000000)]}}
    }}}
    return sub,company


@pytest.fixture
def captures(tmp_path):
    root=tmp_path/"private";root.mkdir(mode=0o700);root.chmod(0o700)
    sub,company=sec_data()
    return root,_capture(root,"sec-submissions",sub),_capture(root,"sec-companyfacts",company)


def test_realistic_sec_join_asof_keeps_metric_revisions_and_no_promotion(captures,tmp_path):
    _,sub,facts=captures
    report=audit_sec_financial_asof(sub,facts,decision_at=LATER)
    assert report["derived_fact_rows"]==4
    assert set(x["metric"] for x in report["financial_rows"])=={
        "revenue_usd","operating_income_usd","net_income_usd","diluted_eps_usd_per_share"}
    assert all(x["effective_available_at_utc"]>=NOW.isoformat() and
               x["prospective_backtest_eligible"] is False for x in report["financial_rows"])
    assert report["pit_certified"] is False and report["official_leaders"]==0
    published=save_sec_research(report,(tmp_path/"us_report").absolute())
    assert published["metric_observations"]==4
    assert "SEC" in (tmp_path/"us_report"/"index.html").read_text()
    with pytest.raises(ValueError,match="new absolute"):
        save_sec_research(report,(tmp_path/"us_report").absolute())


def test_first_receipt_clock_excludes_historical_asof(captures):
    _,sub,facts=captures
    with pytest.raises(ValueError,match="not locally available"):
        audit_sec_financial_asof(sub,facts,decision_at="2026-10-08T12:00:00Z")


def test_fact_source_sha_tamper_rejected(captures):
    _,sub,facts=captures
    raw=facts[0]/"raw_response.json"
    raw.write_bytes(raw.read_bytes()+b" ")
    with pytest.raises(ValueError,match="evidence invalid"):
        audit_sec_financial_asof(sub,facts,decision_at=LATER)


@pytest.mark.parametrize("mode",["cik","no_matching_accn","bad_form","future"])
def test_validation_and_missing_filing_do_not_invent_evidence(tmp_path,mode):
    root=tmp_path/"private";root.mkdir(mode=0o700);root.chmod(0o700)
    sub,facts=sec_data()
    if mode=="cik":facts["cik"]=1001
    if mode=="no_matching_accn":
        x=facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]
        x["accn"]="9999999999-99-999999"
    if mode=="bad_form":
        x=facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]
        x["form"]="8-K"
    if mode=="future":
        sub["filings"]["recent"]["acceptanceDateTime"][0]="2026-10-15T01:00:00Z"
        sub["filings"]["recent"]["filingDate"][0]="2026-10-15"
    a=_capture(root,"sec-submissions",sub)
    b=_capture(root,"sec-companyfacts",facts,cik="1001" if mode=="cik" else "320193")
    if mode=="cik":
        with pytest.raises(ValueError,match="CIK mismatch"):
            audit_sec_financial_asof(a,b,decision_at=LATER)
    elif mode=="bad_form":
        with pytest.raises(ValueError,match="metadata disagrees"):
            audit_sec_financial_asof(a,b,decision_at=LATER)
    else:
        audit=audit_sec_financial_asof(a,b,decision_at=LATER)
        if mode=="future":assert audit["derived_fact_rows"]==0
        if mode=="no_matching_accn":
            assert audit["derived_fact_rows"]==3
            assert audit["fact_rows_unmatched_to_recent_submissions"]>0
