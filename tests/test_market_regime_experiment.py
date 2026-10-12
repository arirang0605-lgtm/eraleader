"""ER-NC-02 synthetic PIT market regime + independent research new-buy permission."""
from datetime import datetime,timedelta
from pathlib import Path

import pandas as pd
import pytest

from eraleader.market_regime_experiment import (
    market_regime_snapshot,entry_permission,
)


def make_case(kind="RISING",market="KR_KOSPI", *, members_count=4):
    days=pd.bdate_range("2026-01-05",periods=180)
    first=days[0].date().isoformat()
    final=days[-1].date().isoformat()
    offset="+09:00" if market.startswith("KR") else "-04:00"
    prices=[]
    def close(i):
        if kind in ("RISING","TRANSITION"):return 100+i*1.25
        if kind=="FALLING":return 500-i*1.4
        return 100.
    for i,day in enumerate(days):
        v=close(i)
        prices.append({"session":day.date().isoformat(),
            "close":v,"high":v+1,"low":v-1,
            "finalized_at":day.date().isoformat()+"T16:30:00"+offset})
    listing=[]
    for j in range(members_count):
        mbars=[]
        for i,day in enumerate(days):
            if kind in ("RISING",):
                val=100+i*(0.8+j*0.2)
            elif kind in ("FALLING","TRANSITION"):
                val=500-i*(0.8+j*0.2)
            elif j<2:
                val=100+i*0.1
            else:
                val=500-i*0.1
            mbars.append({"session":day.date().isoformat(),"close":val,
                         "available_at":day.date().isoformat()+"T17:00:00"+offset})
        listing.append({"security_id":f"synthetic_{j:03d}",
                        "member_first_known_at":"2025-10-01T10:00:00+09:00",
                        "effective_from":first,"effective_to":None,"bars":mbars})
    return {"market":market,"decision_at":final+"T19:00:00"+offset,
            "index_bars":prices,
            "pit_universe":{"session":final,"universe_pit_certified":True,
                            "constituents":listing}}


@pytest.mark.parametrize("kind,expected",[
    ("RISING","RISING"),("FALLING","FALLING"),
    ("SIDEWAYS","SIDEWAYS"),("TRANSITION","TRANSITION"),
])
def test_four_research_regimes(kind,expected):
    r=market_regime_snapshot(**make_case(kind))
    assert r["state"]==expected and r["research_only"] is True
    assert r["quality_status"]=="RESEARCH_PIT_INPUTS_PRESENT_NOT_PERFORMANCE_VERIFIED"
    assert r["features"]["adx14"]>=0
    assert r["features"]["breadth_above_ma60"] is not None


@pytest.mark.parametrize("market",["KR_KOSPI","KR_KOSDAQ","US_SP500","US_NASDAQ100"])
def test_country_market_clocks_and_independent_state(market):
    r=market_regime_snapshot(**make_case("RISING",market))
    assert r["state"]=="RISING"
    assert r["market_timezone"]==("Asia/Seoul" if market.startswith("KR")
                                  else "America/New_York")


def test_unknown_if_history_shorter_than_150plus_slope():
    item=make_case()
    item["index_bars"]=item["index_bars"][-120:]
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert "INDEX_HISTORY_LT_170_FINAL_SESSIONS" in r["reason_codes"]


def test_unverified_current_day_universe_is_not_historic_pit():
    item=make_case()
    item["pit_universe"]["universe_pit_certified"]=False
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert r["features"]["breadth_above_ma60"] is None


def test_future_member_added_to_past_breadth_blocks():
    item=make_case()
    item["pit_universe"]["constituents"][0]["member_first_known_at"]="2027-01-01T09:00:00+09:00"
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert "MEMBERSHIP_FUTURE_OR_NOT_EFFECTIVE" in r["reason_codes"]


def test_future_market_bar_cannot_change_older_regime():
    item=make_case()
    expected=market_regime_snapshot(**item)
    future_day=(pd.Timestamp(item["index_bars"][-1]["session"])+pd.Timedelta(days=1)).date().isoformat()
    item["index_bars"].append({"session":future_day,"close":1e7,
             "high":1e7+2,"low":1e7-2,
             "finalized_at":future_day+"T16:30:00+09:00"})
    got=market_regime_snapshot(**item)
    assert got["state"]==expected["state"]
    assert got["features"]==expected["features"]


def test_malformed_daily_close_prohibited():
    item=make_case()
    item["index_bars"][-1]["close"]=item["index_bars"][-1]["high"]+1
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN" and r["reason_codes"]==["OHLC_INCONSISTENT"]


def test_missing_member_sessions_does_not_fake_low_breadth():
    item=make_case()
    item["pit_universe"]["constituents"][1]["bars"]=item["pit_universe"]["constituents"][1]["bars"][:59]
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert r["reason_codes"]==["INCOMPLETE_60_SESSION_BREADTH"]


def test_duplicate_historic_constituent_refused_as_breadth():
    item=make_case()
    item["pit_universe"]["constituents"][1]["security_id"]=item["pit_universe"]["constituents"][0]["security_id"]
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert r["reason_codes"]==["DUPLICATE_OR_UNKNOWN_PIT_SECURITY"]


def test_original_author_signal_and_exit_unchanged_by_new_buy_gate():
    r=market_regime_snapshot(**make_case("FALLING"))
    before={"author_signal":"BUY_ORIGINAL","stop_signal":"STOP_AUTHOR","exit_signal":"EXIT_AUTHOR"}
    gated=entry_permission(r,policy="GATE_STRICT_UPTREND_V1",action="NEW_BUY")
    author=entry_permission(r,policy="BASE_AUTHOR_ORIGINAL",action="NEW_BUY")
    stop=entry_permission(r,policy="GATE_STRICT_UPTREND_V1",action="STOP")
    assert gated["blocked_by_new_entry_gate"] is True
    assert author["permission"]=="AUTHOR_ORIGINAL_ONLY"
    assert stop["permission"]=="AUTHOR_OR_RISK_RULE"
    assert before["author_signal"]=="BUY_ORIGINAL"
    assert before["stop_signal"]=="STOP_AUTHOR"


@pytest.mark.parametrize("action",["STOP","EXIT","RISK_REDUCE"])
def test_negative_new_entry_gate_never_disables_exit(action):
    r=market_regime_snapshot(**make_case("SIDEWAYS"))
    assert entry_permission(r,action=action)["blocked_by_new_entry_gate"] is False


def test_rising_new_buy_is_research_permission_not_order():
    r=market_regime_snapshot(**make_case("RISING"))
    gate=entry_permission(r)
    assert gate["blocked_by_new_entry_gate"] is False
    assert gate["permission"]=="ALLOW_NEW_BUY_RESEARCH_ONLY"
    assert gate["research_only"] is True


def test_unknown_new_buy_blocks_unverified_data():
    item=make_case()
    item["pit_universe"]=None
    gate=entry_permission(market_regime_snapshot(**item))
    assert gate["blocked_by_new_entry_gate"] is True


def test_timezone_naive_rejected():
    item=make_case()
    item["decision_at"]="2026-10-13T18:00:00"
    with pytest.raises(ValueError,match="timezone"):
        market_regime_snapshot(**item)


def test_non_monotonic_duplicate_exchange_session_unknown():
    item=make_case()
    item["index_bars"].append(item["index_bars"][-1])
    assert market_regime_snapshot(**item)["state"]=="UNKNOWN"


def test_stale_market_prices_do_not_trigger_rising_permission():
    item=make_case("RISING")
    item["decision_at"]="2026-10-20T19:00:00+09:00"
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert r["reason_codes"]==["STALE_INDEX_SESSION_GT_7_CALENDAR_DAYS"]
    assert entry_permission(r)["blocked_by_new_entry_gate"] is True

def test_exchange_timezone_close_date_mismatch_blocks():
    item=make_case("RISING")
    item["index_bars"][-1]["finalized_at"]=item["index_bars"][-1]["session"]+"T01:00:00+14:00"
    r=market_regime_snapshot(**item)
    assert r["state"]=="UNKNOWN"
    assert r["reason_codes"]==["INDEX_CLOSE_SESSION_TIMEZONE_MISMATCH"]
