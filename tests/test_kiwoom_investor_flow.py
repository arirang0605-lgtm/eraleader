"""Read-only Kiwoom official ka10059 quantity semantics and strict evidence."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from eraleader.kiwoom_investor_flow import (
    access_token, fetch_ka10059, shares, verify_flow, canonical,
)
from eraleader.official_kiwoom_flow_overlay import build_overlay, render_overlay

NOW = datetime(2026, 10, 13, 8, tzinfo=timezone.utc)


def fake_pages(rows=20):
    dates = [(datetime(2026, 10, 8) - timedelta(days=i)).strftime("%Y%m%d")
             for i in range(rows)]
    def record(d):
        return {"dt": d, "frgnr_invsr": "+20", "orgn": "-10"}
    return [record(d) for d in dates]


def fake_post(records, *, split=False):
    calls = []
    def post(path, body, headers):
        assert path == "/api/dostk/stkinfo"
        assert body == {"dt":"20261008", "stk_cd":"005930",
                        "amt_qty_tp":"2", "trde_tp":"0", "unit_tp":"1"}
        assert headers["api-id"] == "ka10059"
        calls.append((body, headers))
        if split and len(calls) == 1:
            return {"return_code":0, "stk_invsr_orgn": records[:10]}, {
                "cont-yn":"Y", "next-key":"opaque_next"}
        if split:
            assert headers["next-key"] == "opaque_next"
            return {"return_code":0, "stk_invsr_orgn": records[10:]}, {"cont-yn":"N"}
        return {"return_code":0, "stk_invsr_orgn": records}, {"cont-yn":"N"}
    return post


def flow(rows=20, post=None):
    return fetch_ka10059(
        code="005930", as_of="20261008", token="TEST_LOCAL_TOKEN",
        received_at=NOW, post=post or fake_post(fake_pages(rows)))


def seal(d):
    d.pop("content_sha256", None)
    d["content_sha256"] = sha256(canonical(d)).hexdigest()
    return d


def fixtures():
    first = {
        "schema":"eraleader.official_basic_discovery_candidates.v1",
        "decision_at_utc":"2026-10-13T07:00:00+00:00",
        "market_session":"20261008", "official_future_leaders":0,
        "full_ranked_investment_priority_available":False,
        "comparisons":[
            {"security_id":"005930","name":"삼성전자","comparison_order":1,
             "return_3m":0.1, "revenue_yoy":0.15,
             "operating_income_yoy":0.2,"price_strength_25":18},
            {"security_id":"000660","name":"SK하이닉스","comparison_order":2,
             "return_3m":0.2,"revenue_yoy":0.3,
             "operating_income_yoy":0.1,"price_strength_25":19},
        ],
    }
    seal(first)
    industry = {
        "schema":"eraleader.official_dart_industry_peer_research.v1",
        "as_of_utc":"2026-10-13T07:30:00+00:00",
        "market_session":"20261008","official_leaders":0,
        "historic_sector_pit_certified":False,
        "baseline_candidate_sha256": first["content_sha256"],
        "companies":[
            {"stock_code":"005930","name":"삼성전자","return_3m":0.1,
             "industry_division_code":"26"},
            {"stock_code":"000660","name":"SK하이닉스","return_3m":0.2,
             "industry_division_code":"26"},
        ]
    }
    return first, seal(industry)


def test_actual_quantity_contract_20_rows_with_valid_signed_shares():
    result = flow(post=fake_post(fake_pages(),split=True))
    assert result["page_count"] == 2
    assert result["flow_5_observed_sessions"]["foreign_net_shares"] == 100
    assert result["flow_20_observed_sessions"]["institution_net_shares"] == -200
    assert result["flow_20_observed_sessions"]["combined_net_shares"] == 200
    assert result["unit"] == "shares" and result["investment_rank"] is None
    assert verify_flow(result, decision_at=NOW) == result


@pytest.mark.parametrize("raw,want", [("+100",100),("-200",-200),
                                         ("--40142",-40142),("0",0),("",None),(None,None)])
def test_quantity_values(raw,want):
    assert shares(raw) == want


@pytest.mark.parametrize("raw", ["-+1","nan","1.25","정수","1e6",True,100, "++-12"])
def test_bogus_amounts_rejected(raw):
    with pytest.raises(ValueError):
        shares(raw)


def test_no_zeros_for_missing_or_short_windows():
    r = flow(4)
    assert r["flow_5_observed_sessions"]["foreign_net_shares"] is None
    assert r["flow_20_observed_sessions"]["combined_net_shares"] is None
    data = fake_pages()
    data[3]["orgn"] = None
    r = flow(post=fake_post(data))
    assert r["flow_5_observed_sessions"]["institution_net_shares"] is None
    assert r["flow_20_observed_sessions"]["foreign_net_shares"] == 400
    assert r["flow_20_observed_sessions"]["combined_net_shares"] is None


def test_future_row_duplicate_day_and_incomplete_page_rejected():
    inputs = [
        [dict(fake_pages()[0],dt="20261009")],
        [fake_pages()[0],fake_pages()[0]],
    ]
    for rows in inputs:
        with pytest.raises(ValueError):
            flow(post=fake_post(rows))
    def loop(path, body, headers):
        return {"return_code":0,"stk_invsr_orgn":[]},{"cont-yn":"Y","next-key":"again"}
    with pytest.raises(ValueError):
        flow(post=loop)


def test_no_oauth_credentials_or_bad_response():
    with pytest.raises(ValueError):
        access_token(appkey="",secretkey="")
    def authorized(path, body, headers):
        assert path == "/oauth2/token"
        assert body["grant_type"] == "client_credentials"
        return {"return_code":0,"token_type":"bearer","token":"SENSITIVE"},{}
    assert access_token(appkey="k",secretkey="s",post=authorized) == "SENSITIVE"
    with pytest.raises(ValueError):
        access_token(appkey="k",secretkey="s",post=lambda *args: (
            {"return_code":-1,"token":"exposed"},{}))
    with pytest.raises(ValueError):
        flow(post=lambda *args: ({"return_code":-1, "return_msg":"secret"},{}))


def test_overlay_waiting_and_real_flow_preserves_price_rank_and_NA():
    basic,industry=fixtures()
    waiting = build_overlay(basic,industry,flows={},decision_at=NOW)
    assert waiting["selected_companies"] == 2
    assert waiting["kiwoom_flow_received_companies"] == 0
    assert all(row["foreign_net_5_observed_shares"] is None
               and row["official_total_score_100"] is None for row in waiting["comparisons"])
    assert "N/A" in render_overlay(waiting)
    real = build_overlay(basic,industry,flows={"005930":flow()},decision_at=NOW)
    assert real["usable_20_observation_flow_companies"] == 1
    assert [x["existing_basic_comparison_order"] for x in real["comparisons"]]==[1,2]
    assert real["comparisons"][1]["institution_net_20_observed_shares"] is None
    assert real["comparisons"][0]["institution_net_20_observed_shares"] == -200
    assert real["investment_priority_ranked"] is False


def test_flow_cannot_be_asof_backfilled_or_reassigned_or_tampered():
    basic,industry=fixtures()
    real=flow()
    with pytest.raises(ValueError):
        build_overlay(basic,industry,flows={"000660":real},decision_at=NOW)
    with pytest.raises(ValueError):
        build_overlay(basic,industry,flows={"005930":real},
                      decision_at=datetime(2026,10,12,tzinfo=timezone.utc))
    broken=deepcopy(real);broken["rows"][0]["foreign_net_shares"]=999
    with pytest.raises(ValueError):
        build_overlay(basic,industry,flows={"005930":broken},decision_at=NOW)
    broken=deepcopy(basic);broken["comparisons"][0]["name"]="<script>"
    with pytest.raises(ValueError):
        build_overlay(broken,industry,flows={},decision_at=NOW)


def test_mismatched_trading_session_keeps_flow_na():
    basic, industry=fixtures()
    r=flow()
    r["requested_day"]="20261009"
    seal(r)
    side=build_overlay(basic,industry,flows={"005930":r},decision_at=NOW)
    assert side["comparisons"][0]["flow_status"]=="FLOW_SESSION_MISMATCH_NOT_USABLE"
    assert side["comparisons"][0]["combined_net_5_observed_shares"] is None
