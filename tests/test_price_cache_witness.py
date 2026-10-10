"""Synthetic cache-vs-screen rechecks; no historic market source certification."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd
import pytest

from eraleader.discovery import MODEL_VERSION, run_id_for
from eraleader.price_cache_witness import recheck_price_cache
from eraleader.rank_feature_bridge import build_rank_feature_inputs
from eraleader.cli import main
from test_rank_feature_ledger import setup as setup_pit, NOW, MODEL, TICKERS


def prepare_fixture(tmp_path, market="KR"):
    asof = ("2026-10-09T16:30:00+09:00" if market=="KR"
            else "2026-10-09T17:00:00-04:00")
    db, offline, price_file = setup_pit(tmp_path,market=market,as_of=asof)
    root=tmp_path/"readonly_cache"
    if market=="KR":
        dates=pd.bdate_range(end="2026-10-09",periods=160)
        lag3,lag6,lag12=60,130,250
        days=260
    else:
        dates=pd.date_range(end="2026-10-09",periods=36,freq="W-FRI")
        lag3,lag6,lag12=13,26,52
        days=350
    frame_rows, screen_rows=[], []
    for j,ticker in enumerate(TICKERS.values()):
        closes=[float(100+j*20 + i*(.4+j*.1)) for i in range(len(dates))]
        for dt,close in zip(dates,closes):
            if market=="KR":
                frame_rows.append({
                    "Code":ticker,"Name":ticker, "Date":dt,
                    "Market":"KOSPI", "Open":close, "High":close,
                    "Low":close, "Close":close, "Volume":1000,
                    "Amount":close*1000,"Marcap":1000000000,
                })
            else:
                frame_rows.append({
                    "ts":dt,"ticker":ticker,"open":close,
                    "high":close,"low":close,"close":close,"volume":1000,
                })
        screen_rows.append({
            "security_id":ticker, "observed_at":"2026-10-09",
            "last_price":round(closes[-1],6),
            "return_3m":round(closes[-1]/closes[-1-lag3]-1,6),
            "return_6m":round(closes[-1]/closes[-1-lag6]-1,6),
            "return_12m":(round(closes[-1]/closes[-1-lag12]-1,6)
                          if len(closes)>lag12 else None),
        })
    if market=="KR":
        parquet=root/"datasets/external_validation/marcap/data/marcap-2026.parquet"
    else:
        parquet=root/"datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    parquet.parent.mkdir(parents=True)
    pd.DataFrame(frame_rows).to_parquet(parquet,index=False)
    document=json.loads(price_file.read_text())
    document["rows"]=screen_rows
    document["shown"]=len(screen_rows)
    document["run_id"]=run_id_for(market,"2026-10-09",screen_rows)
    price_file.write_text(json.dumps(document,sort_keys=True))
    return db,offline,price_file,root,days,parquet


def strict(tmp_path, *, cache, days, db=None, target="features"):
    return build_rank_feature_inputs(
        tmp_path/"offline.json",tmp_path/"price.json",tmp_path/target,
        model_version=MODEL,clock=NOW,offline_ledger=db,
        price_cache_root=cache,price_cache_days=days)


@pytest.mark.parametrize("market",["KR","US"])
def test_recompute_selected_returns_from_readonly_local_cache(tmp_path,market):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path,market)
    before=parquet.read_bytes()
    result=strict(tmp_path,cache=root,days=days,db=db)
    assert result["eligible_documents"]==3
    assert result["recomputed_from_readonly_price_cache"] is True
    assert result["rechecked_price_rows"]==3
    report=json.loads((tmp_path/"features/_meta/source_manifest.json").read_text())
    assert len(report["selected_cached_price_returns_sha256"])==64
    assert report["recomputed_from_readonly_offline_ledger"] is True
    assert report["recomputed_from_readonly_price_cache"] is True
    assert report["price_adjustments_and_actions_certified"] is False
    assert parquet.read_bytes()==before
    assert result["real_leader_prediction_certified"] is False
    if market=="US":
        assert "survivor" in recheck_price_cache(json.loads(price.read_text()),
                legacy_root=root,days=days)["original_cache_source"]


@pytest.mark.parametrize("field,bad",[
    ("return_6m",.9), ("return_3m",.8),
    ("return_12m",.25),("last_price",123456.0),
])
def test_forged_screen_values_rehashed_run_id_still_blocked(tmp_path,field,bad):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    doc=json.loads(price.read_text())
    doc["rows"][0][field]=bad
    doc["run_id"]=run_id_for("KR","2026-10-09",doc["rows"])
    price.write_text(json.dumps(doc,sort_keys=True))
    with pytest.raises(ValueError,match="differs from|claimed without"):
        strict(tmp_path,cache=root,days=days,db=db)
    assert not (tmp_path/"features").exists()


def test_suspended_cached_security_cannot_be_momentum_candidate(tmp_path):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    frame=pd.read_parquet(parquet)
    idx=frame.index[(frame["Code"]=="100001") &
                    (frame["Date"]==pd.Timestamp("2026-10-08"))][0]
    frame.loc[idx,["Open","High","Low","Volume","Amount"]]=0
    frame.to_parquet(parquet,index=False)
    with pytest.raises(ValueError,match="recent market halt"):
        strict(tmp_path,cache=root,days=days,db=db)
    assert not (tmp_path/"features").exists()


def test_incomplete_local_six_month_history_fails_closed(tmp_path):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    frame=pd.read_parquet(parquet)
    chosen=frame[frame["Code"]=="100001"].sort_values("Date").tail(130)
    frame=pd.concat([frame[frame["Code"]!="100001"],chosen],ignore_index=True)
    frame.to_parquet(parquet,index=False)
    with pytest.raises(ValueError,match="missing local six-month"):
        strict(tmp_path,cache=root,days=days,db=db)
    assert not (tmp_path/"features").exists()


def test_original_cache_missing_or_symlink_refused(tmp_path):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    with pytest.raises(ValueError,match="cache directory missing"):
        strict(tmp_path,cache=tmp_path/"not-found",days=days)
    linked=tmp_path/"linked_root"
    linked.symlink_to(root)
    with pytest.raises(ValueError,match="symlinked"):
        strict(tmp_path,cache=linked,days=days)
    assert not (tmp_path/"features").exists()


@pytest.mark.parametrize("bad",[-1,199,1096,False,300.5])
def test_bad_cache_window_rejected(tmp_path,bad):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    with pytest.raises(ValueError,match="lookback days"):
        strict(tmp_path,cache=root,days=bad)
    assert not (tmp_path/"features").exists()


def test_legacy_mode_does_not_claim_original_cache_recomputation(tmp_path):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    result=strict(tmp_path,cache=None,days=550)
    assert result["recomputed_from_readonly_price_cache"] is False
    report=json.loads((tmp_path/"features/_meta/source_manifest.json").read_text())
    assert report["selected_cached_price_returns_sha256"] is None


def test_invalid_cache_days_without_cache_root_rejected(tmp_path):
    setup_pit(tmp_path)
    with pytest.raises(ValueError,match="require an original price cache root"):
        build_rank_feature_inputs(
            tmp_path/"offline.json",tmp_path/"price.json",tmp_path/"no_cache",
            model_version=MODEL,clock=NOW,price_cache_days=260)
    assert not (tmp_path/"no_cache").exists()


def test_cli_rechecks_both_original_research_inputs(tmp_path,capsys):
    db,offline,price,root,days,parquet=prepare_fixture(tmp_path)
    main(["prepare-rank-features","--offline",str(offline),
          "--price",str(price),"--offline-ledger",str(db),
          "--price-cache-root",str(root),"--cache-days",str(days),
          "--features-dir",str(tmp_path/"cli"),"--model-version",MODEL])
    result=json.loads(capsys.readouterr().out)
    assert result["recomputed_from_readonly_offline_ledger"] is True
    assert result["recomputed_from_readonly_price_cache"] is True
    assert result["eligible_documents"]==3
    assert result["official_leader_promotions"]==0
