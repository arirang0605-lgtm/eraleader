"""Market-local trade-day alignment across PIT issuer state and price join.

All source rows are synthetic. No external data or certified equity leaders.
"""
from datetime import datetime
from pathlib import Path

import pytest

from eraleader.offline_pit import OfflineLedger
from eraleader.research import integrated_snapshot


def ledger_snapshot(tmp_path, *, market: str, cutoff: str) -> dict:
    ledger=OfflineLedger(tmp_path/"offline.sqlite")
    try:
        old={"security_id":"OLD","ticker":"OLD","industry_id":"SYN",
             "market":market,"valid_from":"2026-04-01","valid_to":None,
             "known_at":"2026-04-28T00:00:00Z","source_id":"SYN","revision":1}
        new={**old,"security_id":"NEW","ticker":"NEW","valid_from":"2026-05-01"}
        if market=="KR":
            new["valid_from"]="2026-05-02"
        ledger.import_rows("membership",[old,new],"synthetic_fixture")
        return ledger.snapshot(cutoff,market=market)
    finally:
        ledger.close()


def local_prices(market, day):
    return {"source_market":market,"as_of_requested":day,
            "market_last_observation":day,"rows":[],
            "run_id":"synthetic-research-join"}


def test_us_midnight_korean_offset_must_join_april_30_not_may_1(tmp_path):
    # May 1 00:30 KST is still Apr 30 New York local.
    at="2026-05-01T00:30:00+09:00"
    snap=ledger_snapshot(tmp_path,market="US",cutoff=at)
    assert snap["trading_day"]=="2026-04-30"
    result=integrated_snapshot(snap,local_prices("US","2026-04-30"),at)
    assert result["company_count"]==1
    assert {r["security_id"] for r in result["company_rows"]}=={"OLD"}
    assert result["pit_certified"] is False
    assert result["confirmed_leaders"]==0
    with pytest.raises(ValueError,match="decision date"):
        integrated_snapshot(snap,local_prices("US","2026-05-01"),at)


def test_us_market_may_1_after_new_york_date_rollover(tmp_path):
    at="2026-05-01T23:30:00+09:00"  # 10:30 EDT May 1
    snap=ledger_snapshot(tmp_path,market="US",cutoff=at)
    assert snap["trading_day"]=="2026-05-01"
    result=integrated_snapshot(snap,local_prices("US","2026-05-01"),at)
    assert {r["security_id"] for r in result["company_rows"]}=={"OLD","NEW"}


def test_kr_market_may_2_even_with_new_york_input_offset(tmp_path):
    at="2026-05-01T12:30:00-04:00"  # 01:30 KST May 2
    snap=ledger_snapshot(tmp_path,market="KR",cutoff=at)
    assert snap["trading_day"]=="2026-05-02"
    accepted=integrated_snapshot(snap,local_prices("KR","2026-05-02"),at)
    assert {r["security_id"] for r in accepted["company_rows"]}=={"OLD","NEW"}
    with pytest.raises(ValueError,match="decision date"):
        integrated_snapshot(snap,local_prices("KR","2026-05-01"),at)


def test_offline_market_day_tampering_rejected(tmp_path):
    at="2026-05-01T00:30:00+09:00"
    snap=ledger_snapshot(tmp_path,market="US",cutoff=at)
    snap["trading_day"]="2026-05-01"
    with pytest.raises(ValueError,match="market day"):
        integrated_snapshot(snap,local_prices("US","2026-04-30"),at)


def test_different_offset_same_instant_accepted_with_same_price_day(tmp_path):
    at="2026-05-01T00:30:00+09:00"
    equivalent="2026-04-30T11:30:00-04:00"
    snap=ledger_snapshot(tmp_path,market="US",cutoff=at)
    result=integrated_snapshot(snap,local_prices("US","2026-04-30"),equivalent)
    assert result["company_count"]==1
    assert result["pit_certified"] is False


def test_us_integrated_cli_accepts_exchange_local_day_at_korean_midnight(tmp_path,capsys):
    import json
    from eraleader.cli import main
    cutoff="2026-05-01T00:30:00+09:00"
    ledger=OfflineLedger(tmp_path/"offline.sqlite")
    try:
        ledger.import_rows("membership",[
            {"security_id":"US-OLD","ticker":"OLD","industry_id":"TECH",
             "market":"US","valid_from":"2026-04-01","valid_to":None,
             "known_at":"2026-04-28T00:00:00Z","source_id":"SYNTHETIC",
             "revision":1}], "synthetic_fixture")
    finally:
        ledger.close()
    prices=local_prices("US","2026-04-30")
    fixture=tmp_path/"price.json"
    fixture.write_text(json.dumps(prices))
    main(["offline-integrated","--market","US","--as-of",cutoff,
          "--price-json",str(fixture),"--out",str(tmp_path)])
    result=json.loads(capsys.readouterr().out)
    report=json.loads(Path(result["path"]).read_text())
    assert report["company_count"]==1
    assert report["market"]=="US"
    assert report["company_rows"][0]["security_id"]=="US-OLD"
    assert result["official_leaders"]==0
    assert result["pit_certified"] is False


def test_us_integrated_cli_rejects_next_market_day_price_header(tmp_path,capsys):
    import json
    from eraleader.cli import main
    cutoff="2026-05-01T00:30:00+09:00"
    ledger=OfflineLedger(tmp_path/"offline.sqlite")
    try:
        ledger.import_rows("membership",[
            {"security_id":"US-OLD","ticker":"OLD","industry_id":"TECH",
             "market":"US","valid_from":"2026-04-01","valid_to":None,
             "known_at":"2026-04-28T00:00:00Z","source_id":"SYNTHETIC",
             "revision":1}], "synthetic_fixture")
    finally: ledger.close()
    fixture=tmp_path/"wrong_price.json"
    fixture.write_text(json.dumps(local_prices("US","2026-05-01")))
    with pytest.raises(SystemExit) as failure:
        main(["offline-integrated","--market","US","--as-of",cutoff,
              "--price-json",str(fixture),"--out",str(tmp_path)])
    assert failure.value.code==2
    assert not list((tmp_path/"runs").glob("joined_*.json")) if (tmp_path/"runs").exists() else True
