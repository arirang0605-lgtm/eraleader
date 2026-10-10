from datetime import date
from pathlib import Path
import json

import pandas as pd
import pytest

from eraleader.continuity_audit import audit_observation_continuity
from eraleader.cli import main


def sample_bars():
    rows = []
    for session, symbols in [
        ("2024-04-01", ("A", "B", "H")),
        ("2024-04-02", ("A", "B", "H")),
        ("2024-04-03", ("A", "C", "H")),
        ("2024-04-04", ("A", "B", "C", "H")),
        ("2024-04-05", ("A", "C", "H")),
    ]:
        for sec in symbols:
            rows.append({"security_id": sec, "session": pd.Timestamp(session),
                         "is_suspended": sec == "H"})
    return pd.DataFrame(rows)


def test_internal_gaps_boundary_censoring_and_suspended_bars():
    report = audit_observation_continuity(sample_bars(), market="KR",
                                          as_of=date(2024, 4, 5))
    assert report["observed_market_session_count"] == 5
    assert report["observed_security_count"] == 4
    assert report["internal_gap_event_count"] == 1
    assert report["internal_missing_bar_slots"] == 1
    assert report["securities_with_internal_gaps"] == 1
    assert report["left_boundary_first_observations"] == 1   # C
    assert report["right_boundary_last_observations"] == 1  # B
    assert report["suspended_bar_observations"] == 5
    assert report["securities_ever_suspended"] == 1
    assert report["gap_samples"][0] == {
        "security_id": "B", "last_seen_before_gap": "2024-04-02",
        "first_seen_after_gap": "2024-04-04",
        "missing_observed_market_sessions": 1}
    assert report["right_boundary_samples"] == ["B"]
    assert report["historic_universe_pit_certified"] is False
    assert report["suspected_delistings_certified"] is False


def test_first_and_last_observation_are_not_interior_gaps():
    frame = sample_bars().query("security_id != 'B'")
    result = audit_observation_continuity(frame, market="KR",
                                          as_of=date(2024, 4, 5))
    assert result["internal_gap_event_count"] == 0
    assert result["left_boundary_first_observations"] == 1
    assert result["right_boundary_last_observations"] == 0


def test_sample_cap_does_not_change_aggregate_counts():
    result = audit_observation_continuity(sample_bars(), market="KR",
                                          as_of=date(2024, 4, 5), sample_limit=1)
    assert len(result["gap_samples"]) == 1
    assert result["internal_gap_event_count"] == 1


@pytest.mark.parametrize("update,match", [
    (lambda d: pd.concat([d,d.iloc[[0]]],ignore_index=True), "Duplicate"),
    (lambda d: d.assign(session=pd.Timestamp("2024-04-07")), "Future"),
    (lambda d: d.drop(columns=["is_suspended"]), "Missing"),
    (lambda d: d.assign(is_suspended="False"), "Invalid suspension"),
    (lambda d: d.assign(security_id=""), "security identity"),
    (lambda d: d.assign(session="not a date"), "Invalid session"),
])
def test_bad_bars_fail_closed(update,match):
    with pytest.raises(ValueError,match=match):
        audit_observation_continuity(update(sample_bars()),market="KR",
                                     as_of=date(2024,4,5))


@pytest.mark.parametrize("market,cap", [("XX",20),("KR",0),("KR",101),("KR",True)])
def test_invalid_market_or_sample_limit_rejected(market,cap):
    with pytest.raises(ValueError):
        audit_observation_continuity(sample_bars(),market=market,
                                     as_of=date(2024,4,5),sample_limit=cap)


def test_underspecified_sessions_fail_closed():
    sample=sample_bars()
    with pytest.raises(ValueError,match="three"):
        audit_observation_continuity(sample.loc[sample["session"] <
            pd.Timestamp("2024-04-03")],market="KR",as_of=date(2024,4,5))


def test_cli_continuity_uses_supplied_cached_bars_without_api(tmp_path,monkeypatch,capsys):
    def fake_reader(market,asof,**kwargs):
        assert market=="KR" and asof==date(2024,4,5)
        return sample_bars(),{"source":"SYNTHETIC_LOCAL","historic_membership_verified":False}
    monkeypatch.setattr("eraleader.cli.read_market_bars",fake_reader)
    main(["audit-continuity","--market","KR","--as-of","2024-04-05",
          "--out",str(tmp_path)])
    printed=json.loads(capsys.readouterr().out)
    report=json.loads((tmp_path/"continuity_kr_research.json").read_text())
    assert printed["internal_gap_event_count"]==1
    assert report["cached_price_quality"]["source"]=="SYNTHETIC_LOCAL"
    assert report["historic_universe_pit_certified"] is False

def test_us_weekly_observation_buckets_prevent_false_daily_gaps():
    # Weekly closes for separate US tickers have different weekday dates.
    rows = []
    for i, week in enumerate(pd.date_range("2024-04-01", periods=4, freq="7D")):
        rows.append({"security_id":"US-A","session":week,
                     "is_suspended":False})
        rows.append({"security_id":"US-C","session":week+pd.Timedelta(days=3),
                     "is_suspended":False})
        if i != 1:
            rows.append({"security_id":"US-B","session":week+pd.Timedelta(days=1),
                         "is_suspended":False})
    out=audit_observation_continuity(pd.DataFrame(rows),market="US",
                                    as_of=date(2024,4,25))
    assert out["observation_cadence"]=="weekly"
    assert out["observed_market_session_count"]==4
    assert out["observed_raw_timestamp_count"]==11
    assert out["internal_gap_event_count"]==1  # only B's actually missing WEEK
    assert out["internal_missing_bar_slots"]==1
    assert out["last_raw_observation"]=="2024-04-25"
    assert out["gap_samples"][0]["security_id"]=="US-B"
    assert out["gap_samples"][0]["first_seen_after_gap"]=="2024-04-15"
    assert out["historic_universe_pit_certified"] is False


def test_us_multiple_observations_same_week_rejected():
    frame=pd.DataFrame([
        {"security_id":"A","session":pd.Timestamp(d),"is_suspended":False}
        for d in ["2024-04-01","2024-04-04","2024-04-08","2024-04-15"]])
    with pytest.raises(ValueError,match="observation period"):
        audit_observation_continuity(frame,market="US",as_of=date(2024,4,15))
