"""Fail-closed local PIT ledger rederivation for ranking features.

Fixtures are deliberately synthetic and do not constitute verified issuer data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.offline_pit import OfflineLedger
from eraleader.offline_features import financial_snapshot
from eraleader.rank_feature_bridge import (
    build_rank_feature_inputs, check_offline_pit_ledger,
)
from eraleader.discovery import MODEL_VERSION, run_id_for
from eraleader.cli import main

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
ASOF = "2026-10-09T16:30:00+09:00"
MODEL = "ledger-recomputed-synthetic-v1"
TICKERS = {"A": "100001", "B": "100002", "C": "100003"}


def sample_records(market="KR"):
    membership = [
        {"security_id":sid, "ticker":ticker, "industry_id":"TECH",
         "market":market, "valid_from":"2025-01-01", "valid_to":None,
         "known_at":"2025-03-01T09:30:00+09:00",
         "source_id":"local-fixture-issuer", "revision":1}
        for sid,ticker in TICKERS.items()
    ]
    fundamentals = []
    for i,sid in enumerate(TICKERS):
        for metric,old,new in (("revenue",100,130+i*10),
                               ("operating_income",20,30+i*2)):
            for period,value,available in (
                ("2025-06-30",old,"2025-08-15T09:00:00+09:00"),
                ("2026-06-30",new,"2026-08-15T09:00:00+09:00")):
                fundamentals.append({
                    "security_id":sid, "metric":metric, "period_end":period,
                    "available_at":available, "value":value, "unit":"KRW",
                    "source_id":"local-fixture-filing", "revision":1,
                })
    industry=[]
    for period,value,available in (
        ("2025-06-30",500,"2025-08-15T09:00:00+09:00"),
        ("2026-06-30",650,"2026-08-15T09:00:00+09:00")):
        industry.append({
            "industry_id":"TECH", "metric":"revenue", "period_end":period,
            "available_at":available, "value":value, "unit":"KRW",
            "source_id":"local-fixture-industry", "revision":1,
        })
    return membership,fundamentals,industry


def setup(tmp_path, market="KR", as_of=ASOF):
    ledger_path=tmp_path/"offline.sqlite"
    ledger=OfflineLedger(ledger_path)
    try:
        members,fundamentals,industry=sample_records(market)
        ledger.import_rows("membership",members,"synthetic_fixture")
        ledger.import_rows("fundamentals",fundamentals,"synthetic_fixture")
        ledger.import_rows("industry",industry,"synthetic_fixture")
        offline=financial_snapshot(ledger.snapshot(as_of,market=market))
    finally:
        ledger.close()
    offline_file=tmp_path/"offline.json"
    offline_file.write_text(json.dumps(offline,sort_keys=True),encoding="utf-8")
    rows=[{"security_id":ticker,"observed_at":"2026-10-09",
           "return_6m":.1 + index*.1}
          for index,ticker in enumerate(TICKERS.values())]
    price={
        "source_market":market, "as_of_requested":"2026-10-09",
        "market_last_observation":"2026-10-09",
        "classification_quality":"PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
        "model_version":MODEL_VERSION, "shown":len(rows), "rows":rows,
        "quality_flags":{"price_only":True,
                         "price_adjustments_verified":False,
                         "historic_membership_verified":False},
        "run_id":run_id_for(market,"2026-10-09",rows),
    }
    price_file=tmp_path/"price.json"
    price_file.write_text(json.dumps(price,sort_keys=True),encoding="utf-8")
    return ledger_path,offline_file,price_file


def prepare(tmp_path, *, db=None, offline=None, price=None, out="features"):
    return build_rank_feature_inputs(
        offline or tmp_path/"offline.json",
        price or tmp_path/"price.json",tmp_path/out,
        model_version=MODEL, clock=NOW,offline_ledger=db)


def test_rederive_identical_pit_snapshot_without_touching_sqlite(tmp_path):
    db,src,price=setup(tmp_path)
    before=sha256(db.read_bytes()).hexdigest()
    digest=check_offline_pit_ledger(json.loads(src.read_text()),db)
    result=prepare(tmp_path,db=db)
    assert result["eligible_documents"]==3
    assert result["deferred"]==0
    assert result["recomputed_from_readonly_offline_ledger"] is True
    assert result["official_leader_promotions"]==0
    report=json.loads((tmp_path/"features/_meta/source_manifest.json").read_text())
    assert report["local_pit_ledger_snapshot_sha256"]==digest
    assert report["recomputed_from_readonly_offline_ledger"] is True
    assert report["financial_source_publication_independently_attested"] is False
    assert sha256(db.read_bytes()).hexdigest()==before


@pytest.mark.parametrize("mutation", [
    lambda x: x["companies"][0].__setitem__("revenue_yoy",3.0),
    lambda x: x["companies"][0].__setitem__("industry_revenue_yoy",.99),
    lambda x: x["companies"][0].__setitem__("ticker","999999"),
    lambda x: x["companies"][0].__setitem__("security_id","HIDDEN_REUSED"),
    lambda x: x["companies"][0].__setitem__("latest_revenue_period","2026-05-31"),
    lambda x: x["quality"].__setitem__("provenances",["external_public_file"]),
    lambda x: x["companies"].pop(),
])
def test_rehashed_forged_intermediate_growth_or_identity_rejected(tmp_path,mutation):
    db,source,price=setup(tmp_path)
    payload=json.loads(source.read_text())
    mutation(payload)
    payload["company_count"]=len(payload["companies"])
    source.write_text(json.dumps(payload,sort_keys=True))
    with pytest.raises(ValueError,match="differs from original"):
        prepare(tmp_path,db=db)
    assert not (tmp_path/"features").exists()


def test_historically_unavailable_new_revision_cannot_rewrite_old_snapshot(tmp_path):
    db,src,price=setup(tmp_path)
    led=OfflineLedger(db)
    try:
        late={
            "security_id":"A","metric":"revenue","period_end":"2026-06-30",
            "available_at":"2026-10-12T09:00:00+09:00",
            "source_id":"local-fixture-filing","revision":2,
            "value":20000,"unit":"KRW",
        }
        led.import_rows("fundamentals",[late],"synthetic_fixture")
    finally:led.close()
    assert prepare(tmp_path,db=db)["eligible_documents"]==3
    led=OfflineLedger(db)
    try:
        ontime={**late,"revision":3,
                "available_at":"2026-10-08T09:00:00+09:00"}
        led.import_rows("fundamentals",[ontime],"synthetic_fixture")
    finally:led.close()
    with pytest.raises(ValueError,match="differs from original"):
        prepare(tmp_path,db=db,out="revised_mismatch")
    assert not (tmp_path/"revised_mismatch").exists()


def test_original_ledger_opened_in_sqlite_query_only_mode(tmp_path):
    db,_,_=setup(tmp_path)
    reader=OfflineLedger.open_readonly(db)
    try:
        assert reader.db.execute("PRAGMA query_only").fetchone()[0]==1
        assert reader.db.execute("SELECT COUNT(*) FROM offline_records").fetchone()[0]>0
        with pytest.raises(sqlite3.OperationalError):
            reader.db.execute("DELETE FROM offline_records")
    finally:
        reader.close()


@pytest.mark.parametrize("path_kind",["missing","symlink"])
def test_missing_or_symlink_ledger_never_creates_or_overwrites_output(tmp_path,path_kind):
    db,_,_=setup(tmp_path)
    if path_kind=="missing":
        candidate=tmp_path/"missing.sqlite"
    else:
        candidate=tmp_path/"linked.sqlite"
        candidate.symlink_to(db)
    with pytest.raises(ValueError,match="non-symlink PIT ledger"):
        prepare(tmp_path,db=candidate)
    assert not (tmp_path/"features").exists()


def test_wrong_market_ledger_cannot_supply_other_market_snapshot(tmp_path):
    db,src,price=setup(tmp_path)
    # Source features may assert US; a KR-only original as-of ledger cannot support it.
    original=json.loads(src.read_text())
    original["market"]="US"
    for row in original["companies"]:
        row["market"]="US"
    src.write_text(json.dumps(original))
    with pytest.raises(ValueError,match="differs from original"):
        prepare(tmp_path,db=db)
    assert not (tmp_path/"features").exists()


def test_legacy_research_mode_still_allowed_but_explicitly_unverified(tmp_path):
    setup(tmp_path)
    result=prepare(tmp_path)
    report=json.loads((tmp_path/"features/_meta/source_manifest.json").read_text())
    assert result["eligible_documents"]==3
    assert result["recomputed_from_readonly_offline_ledger"] is False
    assert report["local_pit_ledger_snapshot_sha256"] is None
    assert report["financial_source_publication_independently_attested"] is False


def test_cli_strict_readonly_ledger_source_check(tmp_path,capsys):
    db,source,price=setup(tmp_path)
    start=sha256(db.read_bytes()).hexdigest()
    main(["prepare-rank-features","--offline",str(source),
          "--price",str(price),"--features-dir",str(tmp_path/"cli"),
          "--model-version",MODEL,"--offline-ledger",str(db)])
    receipt=json.loads(capsys.readouterr().out)
    assert receipt["recomputed_from_readonly_offline_ledger"] is True
    assert receipt["eligible_documents"]==3
    assert sha256(db.read_bytes()).hexdigest()==start
    assert not (tmp_path/"cli"/"_meta"/"source_manifest.json").is_symlink()


def test_asof_unverified_source_remains_uncertified_even_after_local_match(tmp_path):
    db,_,_=setup(tmp_path)
    assert prepare(tmp_path,db=db)["real_leader_prediction_certified"] is False
    feature=json.loads(next((tmp_path/"features").glob("*.json")).read_text())
    assert set(feature)=={"schema","market","model_version","security_id",
                          "available_at","features"}
