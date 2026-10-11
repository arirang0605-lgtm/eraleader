"""Real local KR/US cache and PIT provider readiness cannot certify winners."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import sqlite3

import pandas as pd
import pytest

from eraleader.offline_pit import OfflineLedger
from eraleader.pit_provider_readiness import audit_pit_provider_readiness, STATUS
from eraleader.local_backup import create_backup, verify_backup, restore_backup

CUTOFF = "2026-10-11T12:00:00+09:00"
NOW = datetime(2026,10,11,12,tzinfo=timezone.utc)
FIXTURE=Path(__file__).parent/"fixtures/offline_synthetic.json"


def make_cache(tmp_path,*,kr="2026-10-10",us="2026-10-09",duplicate_kr=False):
    root=tmp_path/"cache"
    data=root/"datasets/external_validation/marcap/data"
    data.mkdir(parents=True)
    dates=[kr,kr] + ([kr] if duplicate_kr else [])
    codes=["111111","222222"]+(["111111"] if duplicate_kr else [])
    pd.DataFrame({"Date":pd.to_datetime(dates),
                  "Code":codes}).to_parquet(data/"marcap-2026.parquet",index=False)
    y=root/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT"
    y.mkdir(parents=True)
    pd.DataFrame({"ts":pd.to_datetime([us,us]),
                  "ticker":["AAPL","NVDA"]}).to_parquet(y/"bars.parquet",index=False)
    return root


def pit(tmp_path):
    f=tmp_path/"offline.sqlite"
    obj=OfflineLedger(f)
    try:obj.import_file(FIXTURE)
    finally:obj.close()
    return f


def call(root,*,kr=None,us=None,at=CUTOFF,age=7,clock=NOW):
    return audit_pit_provider_readiness(
        root,evaluated_at=at,kr_ledger=kr,us_ledger=us,
        max_price_age_days=age,clock=clock)


def test_true_price_cache_observations_without_vendor_pit_are_never_leaders(tmp_path):
    r=call(make_cache(tmp_path))
    assert r["status"]==STATUS
    assert r["official_leader_promotions"]==0
    assert r["independent_pit_verified"] is False
    assert r["issuer_identity_independently_verified"] is False
    assert r["future_leader_accuracy_certified"] is False
    assert r["markets"]["KR"]["price_observed_symbol_count_last_session"]==2
    assert r["markets"]["US"]["price_observed_symbol_count_last_session"]==2
    assert r["markets"]["KR"]["price_cache_last_market_day"]=="2026-10-10"
    assert "KR:PIT_LEDGER_MISSING" in r["blockers"]
    assert "US:PIT_LEDGER_MISSING" in r["blockers"]
    assert "KR:INDEPENDENT_SOURCE_AUTHENTICITY_MISSING" in r["blockers"]
    assert "US:INDEPENDENT_SOURCE_AUTHENTICITY_MISSING" in r["blockers"]
    assert r["actual_future_precision"] is None


def test_actual_synthetic_offline_ledger_cannot_be_called_official_listing(tmp_path):
    root=make_cache(tmp_path)
    ledger=pit(tmp_path)
    before=sha256(ledger.read_bytes()).hexdigest()
    result=call(root,kr=ledger,us=ledger)
    assert result["markets"]["KR"]["source_ledger_present"] is True
    assert result["markets"]["KR"]["source_provenances"]==["synthetic_fixture"]
    assert result["markets"]["KR"]["known_active_membership_count"]>0
    assert "KR:SELF_DECLARED_OR_SYNTHETIC_PIT_SOURCE" in result["blockers"]
    assert result["markets"]["US"]["known_active_membership_count"]==0
    assert "US:PIT_MEMBERSHIP_NOT_PRESENT" in result["blockers"]
    assert sha256(ledger.read_bytes()).hexdigest()==before


def test_stale_cache_periods_are_explicit_and_not_replaced_with_today(tmp_path):
    cache=make_cache(tmp_path,kr="2026-10-02",us="2026-02-26")
    r=call(cache)
    assert r["markets"]["KR"]["price_cache_age_calendar_days"]==9
    assert r["markets"]["US"]["price_cache_age_calendar_days"]>200
    assert "KR:PRICE_CACHE_STALE" in r["blockers"]
    assert "US:PRICE_CACHE_STALE" in r["blockers"]
    assert r["markets"]["US"]["price_cache_last_market_day"]=="2026-02-26"


def test_a_price_observation_does_not_prove_permanent_issuer_id_or_delist_cash(tmp_path):
    r=call(make_cache(tmp_path))
    assert r["markets"]["KR"]["price_symbols_not_permanent_issuer_ids"] is True
    assert r["markets"]["US"]["price_symbols_not_permanent_issuer_ids"] is True
    assert r["delisting_cash_settlement_certified"] is False
    assert r["corporate_action_completeness_certified"] is False


def test_wrong_pit_record_fingerprint_is_refused_before_producing_report(tmp_path):
    root=make_cache(tmp_path)
    ledger=pit(tmp_path)
    with sqlite3.connect(ledger) as conn:
        conn.execute("UPDATE offline_records SET payload='{}' WHERE kind='membership'")
    with pytest.raises(ValueError,match="fingerprint|integrity"):
        call(root,kr=ledger)
    assert ledger.exists()


def test_missing_us_cache_is_explicit_gap_not_fake_zero_price_observations(tmp_path):
    root=make_cache(tmp_path)
    path=root/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    path.unlink()
    r=call(root)
    assert r["markets"]["US"]["price_cache_last_market_day"] is None
    assert r["markets"]["US"]["price_observed_symbol_count_last_session"] is None
    assert "US:PRICE_CACHE_MISSING" in r["blockers"]


def test_absent_kr_year_archive_does_not_generate_fake_kr_coverage(tmp_path):
    root=make_cache(tmp_path)
    path=root/"datasets/external_validation/marcap/data/marcap-2026.parquet"
    path.unlink()
    r=call(root)
    assert r["markets"]["KR"]["price_cache_last_market_day"] is None
    assert "KR:PRICE_CACHE_MISSING" in r["blockers"]


def test_price_feed_duplicate_symbol_on_last_session_fails_closed(tmp_path):
    root=make_cache(tmp_path,duplicate_kr=True)
    with pytest.raises(ValueError,match="Duplicate|duplicat"):
        call(root)


def test_future_market_price_cannot_make_past_pit_ready(tmp_path):
    root=make_cache(tmp_path,us="2026-10-12")
    with pytest.raises(ValueError,match="Future|future"):
        call(root)


@pytest.mark.parametrize("value",[
    "2026-10-11T12:00:00","not-a-date",
])
def test_invalid_or_naive_cutoff_is_rejected(tmp_path,value):
    root=make_cache(tmp_path)
    with pytest.raises(ValueError,match="timestamp|timezone|ISO|date"):
        call(root,at=value)


def test_requested_audit_asof_after_wall_clock_is_not_accepted(tmp_path):
    with pytest.raises(ValueError,match="Future|future"):
        call(make_cache(tmp_path),at="2030-01-01T00:00:00+09:00")


@pytest.mark.parametrize("age",[-1,False,366])
def test_invalid_price_age_parameter_rejected(tmp_path,age):
    with pytest.raises(ValueError,match="age|day"):
        call(make_cache(tmp_path),age=age)


def test_symlink_price_market_source_not_trusted(tmp_path):
    root=make_cache(tmp_path)
    source=root/"datasets/external_validation/marcap/data/marcap-2026.parquet"
    real=source.with_name("real.parquet")
    source.rename(real)
    source.symlink_to(real)
    with pytest.raises(ValueError,match="symlink|Symlink"):
        call(root)


def test_symlink_source_ledger_not_followed(tmp_path):
    root=make_cache(tmp_path)
    f=pit(tmp_path)
    link=tmp_path/"linked.sqlite"
    link.symlink_to(f)
    with pytest.raises(ValueError,match="symlink|Existing"):
        call(root,kr=link)


def test_cli_actual_readiness_and_zip_only_derived_report(tmp_path,capsys):
    from eraleader.cli import main
    root=make_cache(tmp_path)
    ledger=pit(tmp_path)
    before=sha256(ledger.read_bytes()).hexdigest()
    output=tmp_path/"derived"
    main(["audit-pit-provider-readiness","--cache-root",str(root),
          "--kr-ledger",str(ledger),"--us-ledger",str(ledger),
          "--evaluated-at",CUTOFF,"--out",str(output)])
    response=json.loads(capsys.readouterr().out)
    assert response["official_leader_promotions"]==0
    report=output/"pit_provider_readiness_research.json"
    r=json.loads(report.read_text())
    assert r["independent_pit_verified"] is False
    assert "KR:SELF_DECLARED_OR_SYNTHETIC_PIT_SOURCE" in r["blockers"]
    assert sha256(ledger.read_bytes()).hexdigest()==before
    archive=tmp_path/"derived.zip"
    archived=create_backup(output,archive)
    assert archived["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipfile:
        assert zipfile.namelist()==["pit_provider_readiness_research.json","MANIFEST.json"]
        assert "offline.sqlite" not in zipfile.namelist()
    recovered=tmp_path/"recovered"
    restore_backup(archive,recovered)
    assert (recovered/report.name).read_bytes()==report.read_bytes()


def test_price_cache_timestamp_and_sector_does_not_create_real_alpha(tmp_path):
    r=call(make_cache(tmp_path))
    assert r["actual_future_precision"] is None
    assert r["future_leader_accuracy_certified"] is False
    assert r["independent_pit_verified"] is False
    assert r["official_leader_promotions"]==0
    assert r["market_raw_sources_are_not_official_membership"] is True


def test_partial_us_weekly_cache_latest_thursday_not_promoted_to_493_issuer_universe(tmp_path):
    root=make_cache(tmp_path)
    us=root/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    tickers=[f"SYMBOL-{i:04d}" for i in range(40)]
    rows=[{"ts":"2026-10-05","ticker":sec} for sec in tickers]
    rows.append({"ts":"2026-10-08","ticker":"SYMBOL-0000"})
    pd.DataFrame(rows).assign(ts=lambda f:pd.to_datetime(f.ts)).to_parquet(us,index=False)
    r=call(root)
    market=r["markets"]["US"]
    assert market["price_cache_last_market_day"]=="2026-10-08"
    assert market["price_observed_symbol_count_last_session"]==1
    assert market["price_breadth_reference_peak_symbols_trailing_30d"]==40
    assert market["last_broad_coverage_observation_day"]=="2026-10-05"
    assert market["last_broad_coverage_observed_symbols"]==40
    assert market["price_last_day_coverage_fraction_vs_recent_peak"]==0.025
    assert "US:PRICE_FEED_LATEST_DAY_SPARSE" in r["blockers"]
    assert market["price_symbols_not_permanent_issuer_ids"] is True


def test_small_fixture_does_not_require_40_symbols_for_a_fake_completeness_check(tmp_path):
    r=call(make_cache(tmp_path))
    us=r["markets"]["US"]
    assert us["price_breadth_reference_peak_symbols_trailing_30d"]==2
    assert us["last_broad_coverage_observation_day"]=="2026-10-09"
    assert "US:PRICE_FEED_LATEST_DAY_SPARSE" not in r["blockers"]
