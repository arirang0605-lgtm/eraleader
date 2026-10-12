"""ER-NC-04 synthetic PIT theme lifecycle and episodic rotation boundaries."""
from copy import deepcopy
import pandas as pd
import pytest
from eraleader.theme_lifecycle import assess_theme_lifecycle


def case(kind="RISING", count=4):
    dates=pd.bdate_range(end="2026-10-09", periods=170)
    day=dates[-1].date().isoformat()
    records={}
    members=[]
    for sec_num in range(count):
        sec=f"class.KR.{sec_num}"
        members.append({"member_security_id":sec,
                        "member_issuer_id":f"issuer.KR.{sec_num}",
                        "member_first_known_at":"2026-01-01T12:00:00+09:00",
                        "relationship_type":"DIRECT_CONTRACT","evidence_ids":["fixture.evidence"]})
        items=[]
        for i,dt in enumerate(dates):
            if kind in {"RISING","REACTIVATING"}: price=100+i*(2.5+sec_num*0.05)
            elif kind=="DORMANT":price=500-i*2
            elif kind=="WEAKENING":price=500-i
            elif kind=="EMERGING":price=100+i*1.1
            else:price=100
            volume=2500 if kind in {"RISING","REACTIVATING"} and i>=165 else (
                200 if kind=="DORMANT" and i>=165 else (
                800 if kind=="WEAKENING" and i>=165 else (
                1200 if kind=="EMERGING" and i>=165 else 1000)))
            items.append({"session":dt.date().isoformat(),
                         "available_at":dt.date().isoformat()+"T18:00:00+09:00",
                         "close":price,"turnover":volume})
        records[sec]=items
    bench=[]
    for i,dt in enumerate(dates):
        val=100+i*0.15 if kind=="DORMANT" else (
            100+i*0.25 if kind in {"RISING","REACTIVATING"} else 100)
        bench.append({"session":dt.date().isoformat(),"close":val,
                      "turnover":100000,
                      "available_at":dt.date().isoformat()+"T18:00:00+09:00"})
    theme={"theme_id":"theme.ROBOTICS","available_at":"2026-01-02T10:00:00+09:00",
           "members":members,"member_count":count}
    return {"theme_record":theme,"decision_at":day+"T20:00:00+09:00",
            "market_session":day,"security_bars":records,"benchmark_bars":bench}


@pytest.mark.parametrize("scenario,expected", [
 ("RISING","RISING"),("DORMANT","DORMANT"),
 ("WEAKENING","WEAKENING"),("CONSOLIDATING","CONSOLIDATING"),
 ("EMERGING","EMERGING")
])
def test_theme_lifecycle_five_cases(scenario,expected):
    out=assess_theme_lifecycle(**case(scenario))
    assert out["state"]==expected
    assert out["episode_id"] and out["research_only"] is True
    assert out["official_leaders"]==0
    assert out["features"]["member_count"]==4
    assert out["features"]["turnover_top3_concentration"] is not None


def test_dormant_theme_does_not_invalidate_positive_news():
    args=case("DORMANT")
    out=assess_theme_lifecycle(**args,news_context={"catalyst_state":"CONFIRMED"})
    assert out["state"]=="DORMANT"
    assert out["catalyst_state"]=="CONFIRMED"
    assert out["catalyst_is_separate_from_price_state"] is True


def test_news_unavailable_does_not_override_price_state():
    args=case("RISING")
    prev=assess_theme_lifecycle(**args)
    got=assess_theme_lifecycle(**args,news_context=None)
    assert prev==got and got["catalyst_state"]=="UNKNOWN_NOT_COLLECTED"


def test_dormant_to_reactivation_retains_theme_new_episode():
    args=case("REACTIVATING")
    prior={"theme_id":"theme.ROBOTICS","state":"DORMANT",
           "as_of":"2026-10-08T20:00:00+09:00","episode_id":"old-episode"}
    new=assess_theme_lifecycle(**args,history=[prior])
    assert new["state"]=="REACTIVATING" and new["theme_id"]=="theme.ROBOTICS"
    assert new["episode_id"]!="old-episode" and new["episode_is_new"]


def test_old_episode_kept_in_consolidation():
    args=case("CONSOLIDATING")
    prior={"theme_id":"theme.ROBOTICS","state":"WEAKENING",
           "as_of":"2026-10-08T20:00:00+09:00","episode_id":"episode-X"}
    new=assess_theme_lifecycle(**args,history=[prior])
    assert new["episode_id"]=="episode-X" and not new["episode_is_new"]


def test_replay_deterministic_episode_and_source_sha():
    args=case("RISING")
    assert assess_theme_lifecycle(**args)==assess_theme_lifecycle(**deepcopy(args))


def test_one_winner_only_is_not_a_theme():
    result=assess_theme_lifecycle(**case("RISING",count=1))
    assert result["state"]=="UNKNOWN"
    assert result["reason_codes"]==["TOO_FEW_PIT_CLASS_MEMBERS"]


def test_all_trading_halted_not_dormant():
    args=case("DORMANT")
    for bars in args["security_bars"].values():
        bars[-1]["turnover"]=0
    result=assess_theme_lifecycle(**args)
    assert result["state"]=="UNKNOWN" and result["reason_codes"]==["FULL_THEME_TRADING_HALT"]


def test_missing_asof_security_bars_unknown():
    args=case()
    args["security_bars"].pop("class.KR.1")
    out=assess_theme_lifecycle(**args)
    assert out["state"]=="UNKNOWN" and out["reason_codes"]==["MISSING_MEMBER_PRICE_ASOF"]


def test_future_ticker_member_not_backfilled():
    args=case()
    args["theme_record"]["members"][0]["member_first_known_at"]="2026-12-01T10:00:00+09:00"
    result=assess_theme_lifecycle(**args)
    assert result["state"]=="UNKNOWN"
    assert result["reason_codes"]==["FUTURE_THEME_MEMBER"]


def test_future_candle_does_not_change_current_theme_state():
    args=case()
    before=assess_theme_lifecycle(**args)
    args["security_bars"]["class.KR.0"].append({
        "session":"2026-10-12","available_at":"2026-10-12T20:00:00+09:00",
        "close":9999,"turnover":10000000})
    assert assess_theme_lifecycle(**args)==before


def test_missing_member_exchange_session_cannot_use_outdated_price():
    args=case()
    args["security_bars"]["class.KR.2"].pop(80)
    result=assess_theme_lifecycle(**args)
    assert result["state"]=="UNKNOWN"
    assert result["reason_codes"]==["MEMBER_BENCHMARK_SESSIONS_NOT_ALIGNED"]


def test_future_theme_catalog_cannot_generate_past_price_episodes():
    args=case()
    args["theme_record"]["available_at"]="2027-01-01T10:00:00+09:00"
    with pytest.raises(ValueError,match="Future PIT theme"):
        assess_theme_lifecycle(**args)


def test_cannot_reverse_episode_asof_or_pretend_known_previous():
    args=case()
    bad={"theme_id":"theme.ROBOTICS","state":"DORMANT",
         "as_of":"2027-10-08T20:00:00+09:00","episode_id":"e"}
    with pytest.raises(ValueError,match="episode provenance"):
        assess_theme_lifecycle(**args,history=[bad])


def test_insufficient_reference_series_stays_unknown():
    args=case()
    args["benchmark_bars"]=args["benchmark_bars"][-60:]
    out=assess_theme_lifecycle(**args)
    assert out["state"]=="UNKNOWN"
    assert out["reason_codes"]==["BENCHMARK_PIT_PRICE_HISTORY_INCOMPLETE"]


def test_theme_episode_sqlite_append_only_idempotent_and_restore(tmp_path):
    from eraleader.theme_lifecycle import ThemeEpisodeStore
    p=(tmp_path/'episode.sqlite').absolute()
    observation=assess_theme_lifecycle(**case('DORMANT'))
    record=ThemeEpisodeStore(p)
    try:
        assert record.append(observation) is True
        assert record.append(observation) is False
        assert record.history(observation['theme_id'],as_of=observation['as_of'])==[observation]
        corrupted=deepcopy(observation);corrupted['state']='RISING'
        with pytest.raises(ValueError,match='immutable'):
            record.append(corrupted)
        next_=deepcopy(observation)
        next_['as_of']='2026-10-12T20:00:00+09:00'
        next_['state']='REACTIVATING';next_['episode_id']='new-episode-id'
        next_['source_sha256']='f'*64
        assert record.append(next_)
        assert record.history(observation['theme_id'],as_of=observation['as_of'])==[observation]
        old=deepcopy(observation);old['as_of']='2026-10-08T19:00:00+09:00'
        with pytest.raises(ValueError,match='backfill'):
            record.append(old)
    finally:
        record.close()
    restored=ThemeEpisodeStore(p)
    try:
        rows=restored.history(observation['theme_id'],as_of='2026-10-13T20:00:00+09:00')
        assert len(rows)==2 and rows[0]['episode_id']!=rows[1]['episode_id']
    finally:
        restored.close()
