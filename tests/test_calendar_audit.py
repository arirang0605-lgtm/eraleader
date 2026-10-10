"""Offline user-declared exchange calendar contract; never official PIT certification."""
from datetime import date
from hashlib import sha256
import json

import pandas as pd
import pytest

from eraleader.calendar_audit import (
    SCHEMA, audit_exchange_calendar, compare_calendar_periods, load_calendar_manifest
)
from eraleader.cli import main


def fixture(tmp_path, market="KR", trading=None, **changes):
    if trading is None:
        trading=["2026-10-05","2026-10-06","2026-10-07","2026-10-08","2026-10-09"]
    doc={"schema_version":SCHEMA,"market":market,"source_id":"SYN-CAL-1",
         "publisher_id_claimed":"SYNTHETIC_UNVERIFIED",
         "coverage_start":"2026-10-05","coverage_end":"2026-10-09",
         "retrieved_at":"2026-10-10T09:00:00+09:00",
         "asserted_complete":True,"trading_sessions":trading,"closed_sessions":[]}
    doc.update(changes)
    path=tmp_path/"calendar.json"
    path.write_text(json.dumps(doc))
    return path


def bars(days,security="A"):
    return pd.DataFrame({"security_id":[security]*len(days),
                         "session":pd.to_datetime(days)})


def evaluate(path,frame,market="KR"):
    return audit_exchange_calendar(path,frame,market=market,as_of=date(2026,10,10))


def test_whole_market_day_missing_even_when_all_security_bars_absent(tmp_path):
    ref=fixture(tmp_path)
    out=evaluate(ref,bars(["2026-10-05","2026-10-06","2026-10-08","2026-10-09"]))
    assert out["reference_only_missing_market_periods"]==1
    assert out["missing_period_samples"]==["2026-10-07"]
    assert out["calendar_file_sha256"]==sha256(ref.read_bytes()).hexdigest()
    assert out["calendar_pit_certified"] is False
    assert out["calendar_retrospectively_retrieved"] is False


def test_declared_closure_not_missing_bar(tmp_path):
    ref=fixture(tmp_path,trading=["2026-10-05","2026-10-06","2026-10-08","2026-10-09"],
                closed_sessions=["2026-10-07"])
    out=evaluate(ref,bars(["2026-10-05","2026-10-06","2026-10-08","2026-10-09"]))
    assert out["reference_only_missing_market_periods"]==0
    assert out["feed_only_unexpected_periods"]==0


def test_feed_only_period_audit_not_official_exchange_assertion(tmp_path):
    ref=fixture(tmp_path,trading=["2026-10-05","2026-10-06","2026-10-09"])
    out=evaluate(ref,bars(["2026-10-05","2026-10-06","2026-10-08","2026-10-09"]))
    assert out["feed_only_unexpected_periods"]==1
    assert out["unexpected_period_samples"]==["2026-10-08"]
    assert out["calendar_independently_attested"] is False


def test_us_vendor_weekday_stamps_are_grouped_weekly(tmp_path):
    ref=fixture(tmp_path,market="US",coverage_start="2026-09-21",
                trading=["2026-09-21","2026-09-28","2026-10-05"])
    frame=pd.concat([
        bars(["2026-09-22","2026-09-29","2026-10-06"],"A"),
        bars(["2026-09-24","2026-10-01","2026-10-08"],"B")
    ],ignore_index=True)
    report=evaluate(ref,frame,market="US")
    assert report["observation_cadence"]=="weekly"
    assert report["reference_expected_periods"]==3
    assert report["observed_periods"]==3
    assert report["reference_only_missing_market_periods"]==0


def test_us_whole_market_missing_week(tmp_path):
    ref=fixture(tmp_path,market="US",coverage_start="2026-09-21",
                trading=["2026-09-21","2026-09-28","2026-10-05"])
    result=evaluate(ref,bars(["2026-09-24","2026-10-08"]),"US")
    assert result["missing_period_samples"]==["2026-09-28"]


@pytest.mark.parametrize("change,error",[
    ({"market":"US"},"market mismatch"),
    ({"retrieved_at":"2026-10-10T09:00:00"},"Timezone"),
    ({"asserted_complete":"true"},"boolean"),
    ({"trading_sessions":["2026-10-05","2026-10-05"]},"Duplicate"),
    ({"trading_sessions":["2026-10-06","2026-10-05"]},"Unsorted"),
    ({"coverage_end":"2026-10-12"},"cutoff"),
    ({"closed_sessions":["2026-10-05"]},"open and closed"),
    ({"source_id":""},"source_id"),
    ({"trading_sessions":["2026-10-05","2030-10-05"]},"outside declared")
])
def test_invalid_source_contract_is_rejected(tmp_path,change,error):
    with pytest.raises(ValueError,match=error):
        evaluate(fixture(tmp_path,**change),
                 bars(["2026-10-05","2026-10-06","2026-10-09"]))


def test_insufficient_calendar_coverage_rejected(tmp_path):
    ref=fixture(tmp_path,coverage_start="2026-10-06",
                trading=["2026-10-06","2026-10-07","2026-10-08","2026-10-09"])
    with pytest.raises(ValueError,match="does not cover"):
        evaluate(ref,bars(["2026-10-05","2026-10-07","2026-10-09"]))


def test_future_and_duplicate_price_data_rejected(tmp_path):
    ref=fixture(tmp_path)
    with pytest.raises(ValueError,match="Future"):
        evaluate(ref,bars(["2026-10-05","2026-10-12"]))
    with pytest.raises(ValueError,match="Duplicate"):
        evaluate(ref,bars(["2026-10-05","2026-10-05","2026-10-09"]))


def test_post_cutoff_retrieval_not_treated_as_pit(tmp_path):
    ref=fixture(tmp_path,retrieved_at="2026-10-11T09:00:00+09:00")
    out=evaluate(ref,bars(["2026-10-05","2026-10-09"]))
    assert out["calendar_retrospectively_retrieved"] is True
    assert out["calendar_pit_certified"] is False


def test_continuity_optional_calendar_bridge(tmp_path):
    ref=fixture(tmp_path)
    dates=[date(2026,10,5),date(2026,10,6),date(2026,10,9)]
    via=compare_calendar_periods(load_calendar_manifest(ref),market="KR",
        as_of=date(2026,10,10),observed_period_dates=dates,
        raw_observation_dates=dates,price_source="SYNTHETIC")
    assert via["whole_market_missing_period_count"]==2
    assert via["calendar_pit_certified"] is False


def test_cli_offline_file_creates_uncertified_derived_json(tmp_path,monkeypatch,capsys):
    ref=fixture(tmp_path)
    def fake_reader(market,asof,**kwargs):
        assert market=="KR" and asof==date(2026,10,10)
        return bars(["2026-10-05","2026-10-06","2026-10-09"]),{
            "source":"SYNTHETIC_CACHE","historic_membership_verified":False}
    monkeypatch.setattr("eraleader.cli.read_market_bars",fake_reader)
    main(["audit-calendar","--file",str(ref),"--market","KR",
          "--as-of","2026-10-10","--out",str(tmp_path/"output")])
    data=json.loads(capsys.readouterr().out)
    assert data["calendar_pit_certified"] is False
    saved=json.loads((tmp_path/"output"/"calendar_kr_research.json").read_text())
    assert saved["reference_only_missing_market_periods"]==2
    assert saved["cached_price_quality"]["historic_membership_verified"] is False
