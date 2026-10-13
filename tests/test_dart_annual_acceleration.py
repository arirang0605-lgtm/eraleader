"""3 original DART CFS annual receipts -> research-only acceleration.

Every report retains fiscal-year own first receipt; no backfilled leader claims.
"""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from eraleader.official_dart_financials import annual_acceleration_diagnostic

NOW=datetime(2026,10,13,4,tzinfo=timezone.utc)


def report(year, *, revenue, operating, net):
    return {"stock_code":"005930","corp_code":"00126380",
            "report_code":"11011","statement":"CFS","year":year,
            "metrics":{"revenue":{"value":revenue},
                       "operating_income":{"value":operating},
                       "net_income":{"value":net}},
            "report_accessions":[f"{year+1}0315000001"],
            "first_local_received_at_utc":"2026-10-12T12:00:00+00:00",
            "pit_certified":False}


def years():
    return (
        report(2023,revenue=100,operating=20,net=10),
        report(2024,revenue=120,operating=30,net=15),
        report(2025,revenue=156,operating=48,net=30),
    )


def test_three_year_growth_acceleration_with_two_separate_yoy():
    a,b,c=years()
    result=annual_acceleration_diagnostic(a,b,c,decision_at=NOW)
    assert result["annual_comparison_years"] == [2023,2024,2025]
    assert result["previous_yoy"]["revenue_yoy"] == pytest.approx(.2)
    assert result["research_metrics"]["revenue_yoy"] == pytest.approx(.3)
    assert result["research_acceleration"]["revenue_yoy_acceleration"] == pytest.approx(.1)
    assert result["research_acceleration"]["operating_income_yoy_acceleration"] == pytest.approx(.1)
    assert result["research_acceleration"]["net_income_yoy_acceleration"] == pytest.approx(.5)
    assert result["official_leader"] is False
    assert result["historic_publication_time_certified"] is False
    assert result["original_report_revision_history_certified"] is False
    assert result["prospective_backtest_eligible"] is False


@pytest.mark.parametrize("field,value",[
    ("stock_code","999999"),
    ("corp_code","00000000"),
    ("report_code","11012"),
    ("statement","OFS"),
    ("pit_certified",True),
    ("report_accessions",["20260315000001","20260316000001"]),
    ("report_accessions",["not_a_filing"]),
    ("first_local_received_at_utc","2026-10-15T01:00:00+00:00"),
    ("first_local_received_at_utc","2026-10-12T12:00:00"),
    ("year",2027),
])
def test_bad_third_report_cannot_be_credited_as_historic_prediction(field,value):
    a,b,c=deepcopy(years())
    c[field]=value
    with pytest.raises((ValueError,TypeError)):
        annual_acceleration_diagnostic(a,b,c,decision_at=NOW)


def test_duplicate_filing_accessions_across_years_forbidden():
    a,b,c=deepcopy(years())
    b["report_accessions"] = a["report_accessions"]
    with pytest.raises(ValueError,match="repeated"):
        annual_acceleration_diagnostic(a,b,c,decision_at=NOW)


def test_no_acceleration_if_previous_revenue_zero_or_negative():
    a,b,c=deepcopy(years())
    a["metrics"]["revenue"]["value"] = 0
    result=annual_acceleration_diagnostic(a,b,c,decision_at=NOW)
    assert result["previous_yoy"]["revenue_yoy"] is None
    assert result["research_acceleration"]["revenue_yoy_acceleration"] is None
    assert result["research_metrics"]["revenue_yoy"] == pytest.approx(.3)


def test_no_acceleration_for_nonconsecutive_years():
    a,b,c=deepcopy(years())
    a["year"]=2022
    with pytest.raises(ValueError,match="consecutive"):
        annual_acceleration_diagnostic(a,b,c,decision_at=NOW)


def test_future_evaluation_time_does_not_bypass_first_local_received():
    a,b,c=deepcopy(years())
    c["first_local_received_at_utc"]="2026-10-13T02:00:00Z"
    with pytest.raises(ValueError,match="Future"):
        annual_acceleration_diagnostic(a,b,c,decision_at=datetime(2026,10,12,23,tzinfo=timezone.utc))
