"""Basic real-price+annual-earnings research shortlist has no invented 100 score."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import pytest

from test_official_factor_readiness import source
from eraleader.official_basic_candidates import (
    build_basic_candidate_research,render_basic_candidates,
    write_basic_candidate_screen,
)


def observed_two_companies():
    snap=source()
    snap["official_api_evidence"]["decision_at"]="2026-10-13T10:00:00Z"
    snap["official_financial_research_observations"][0]["source_first_received_at_utc"]=(
        "2026-10-12T11:00:00Z")
    snap["official_financial_research_observations"].append({
        **deepcopy(snap["official_financial_research_observations"][0]),
        "security_id":"000660","name":"Company 2",
        "research_metrics":{"revenue_yoy":-.05,
                            "operating_income_yoy":.10,
                            "net_income_yoy":None},
        "source_first_received_at_utc":"2026-10-12T14:30:00Z",
    })
    snap["research_candidate_price_factors"]=[
        {"security_id":"005930","return_3m":.14,"return_6m":.20,
         "price_strength_25":17.5,"price_market_rank":43,
         "observed_market_session":"2026-10-08",
         "historic_issuer_class_pit_certified":False},
        {"security_id":"000660","return_3m":-.04,"return_6m":.02,
         "price_strength_25":11.2,"price_market_rank":200,
         "observed_market_session":"2026-10-08",
         "historic_issuer_class_pit_certified":False}
    ]
    return snap


def test_candidates_basic_multi_company_earnings_and_market_direction():
    report=build_basic_candidate_research(observed_two_companies())
    assert report["financial_companies_observed"]==2
    assert report["direction_fully_evaluable"]==2
    assert report["jointly_improving_observations"]==1
    assert [x["security_id"] for x in report["comparisons"]]==["005930","000660"]
    assert report["comparisons"][0]["positive_concordance_of_three"]==3
    assert report["comparisons"][0]["comparison_order"]==1
    assert all(x["total_score_100"] is None and x["investable_price_rank"] is None
               for x in report["comparisons"])
    assert report["official_future_leaders"]==0
    assert report["future_leader_precision_certified"] is False
    assert report["full_ranked_investment_priority_available"] is False


def test_candidate_html_says_not_investment_priority_and_preserves_growth():
    doc=render_basic_candidates(build_basic_candidate_research(observed_two_companies()))
    assert "실제 매수 1~20위가 아닙니다" in doc
    assert "005930" in doc and "000660" in doc
    assert "+10.9%" in doc
    assert "산업·수급" in doc
    assert "종합 100점" in doc


def test_missing_factors_are_na_not_implicitly_zero():
    snap=observed_two_companies()
    snap["research_candidate_price_factors"][0]["return_3m"]=None
    obs=build_basic_candidate_research(snap)
    samsung=[r for r in obs["comparisons"] if r["security_id"]=="005930"][0]
    assert samsung["positive_concordance_of_three"] is None
    assert samsung["observed_direction"]=="DATA_INCOMPLETE"
    assert "N/A" in render_basic_candidates(obs)
    assert obs["direction_fully_evaluable"]==1


def test_ranked_rows_bound_to_real_first_observation_not_prior_market_session():
    snap=observed_two_companies()
    snap["official_financial_research_observations"][0]["source_first_received_at_utc"]=(
        "2026-10-14T11:00:00Z")
    with pytest.raises(ValueError,match="future collected"):
        build_basic_candidate_research(snap)


@pytest.mark.parametrize("target,value",[
    ("price_strength_25",33.0),
    ("historic_issuer_class_pit_certified",True),
    ("observed_market_session","2026-10-13"),
])
def test_bad_price_or_identity_proof_cannot_enter_candidate_screen(target,value):
    snap=observed_two_companies()
    snap["research_candidate_price_factors"][0][target]=value
    with pytest.raises(ValueError):
        build_basic_candidate_research(snap)


def test_duplicate_company_financial_cannot_be_included():
    snap=observed_two_companies()
    snap["official_financial_research_observations"][1]["security_id"]="005930"
    with pytest.raises(ValueError):
        build_basic_candidate_research(snap)


def test_basic_candidate_document_sha_sealed_and_exclusive(tmp_path):
    original=observed_two_companies()
    snap_before=json.dumps(original,sort_keys=True)
    report=build_basic_candidate_research(original)
    assert json.dumps(original,sort_keys=True)==snap_before
    site=tmp_path/"site";site.mkdir()
    html,meta=write_basic_candidate_screen(report,site)
    assert html.is_file() and meta.is_file()
    assert json.loads(meta.read_text())==report
    with pytest.raises(FileExistsError):
        write_basic_candidate_screen(report,site)
    changed=deepcopy(report)
    changed["comparisons"][0]["revenue_yoy"]=100
    with pytest.raises(ValueError,match="edited"):
        render_basic_candidates(changed)
