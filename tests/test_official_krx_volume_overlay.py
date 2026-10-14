"""Marketwide official KRX original SHA daily volume supplement tests."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json

import pandas as pd
import pytest

from eraleader import official_krx_volume_overlay as module
from eraleader.marketwide_dated_volume import (
    evaluate_exact_volume,publish_exact_dated_volume
)
from eraleader.official_company_explorer import canonical
from eraleader.marketwide_live_search import _source
from test_marketwide_dated_volume import arranged,cached,CODE
from test_marketwide_flow_batch import NOW


def overlay(project,market,*,rows,day="2026-10-13"):
    source,_=_source(market)
    prior=next((project/"output"/"marketwide_dated_flow").glob("KR_*.json"))
    before=json.loads(prior.read_bytes())
    report={
        "schema":module.SCHEMA,"market":"KR",
        "source_market_session":day,
        "source_marketwide_sha256":source["content_sha256"],
        "stock_code":CODE,
        "dated_kiwoom_sha256":before["content_sha256"],
        "capture_root":str(project/"captures"),
        "source_first_receipts_verified":True,
        "capture_dates":sorted(r["session"] for r in rows),
        "rows":rows,
        "source_volume_is_official_observation":True,
        "historical_pit_independently_certified":False,
        "corporate_actions_verified":False,
        "normalised_flow_score_10":None,
        "orders_enabled":False,"formal_leaders":0,
    }
    report["content_sha256"]=sha256(canonical(report)).hexdigest()
    folder=project/"output"/module.SUBDIR
    folder.mkdir()
    path=folder/"manual_original_pinned.json"
    path.write_bytes(canonical(report)+b"\n")
    return path


def observation(day,volume=1000):
    return {
        "session":day,"stock_code":CODE,"volume":volume,
        "close":100.,"market_cap":10000000.,
        "market":"krx-kospi","first_receipt_sha256":"a"*64,
        "first_locally_received_at_utc":"2026-10-14T01:00:00+00:00",
    }


def test_supplement_exact_original_days_without_making_up_others(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path,no=(0,5))
    before=evaluate_exact_volume(marketwide=market,project=project,
                                 code=CODE,legacy_root=root,clock=NOW)
    assert before["periods"]["20"]["matched_price_volume_days"]==18
    path=overlay(project,market,rows=[
        observation("2026-10-08"),observation("2026-10-13")])
    updated=evaluate_exact_volume(
        marketwide=market,project=project,code=CODE,
        legacy_root=root,clock=NOW,official_volume_overlay=path)
    assert updated["periods"]["5"]["matched_price_volume_days"]==5
    assert updated["periods"]["20"]["matched_price_volume_days"]==20
    assert updated["periods"]["20"]["foreign_pct_of_matched_daily_volume"]==10.95
    assert updated["periods"]["5"]["foreign_pct_of_matched_daily_volume"]==10.2
    assert updated["official_source_added_price_days"]==["2026-10-08","2026-10-13"]
    assert updated["formal_flow_score_10"] is None
    assert updated["orders_enabled"] is False
    result=publish_exact_dated_volume(
        marketwide=market,project=project,code=CODE,
        legacy_root=root,clock=NOW,official_volume_overlay=path)
    assert result["fully_aligned_20"] is True
    assert publish_exact_dated_volume(
        marketwide=market,project=project,code=CODE,
        legacy_root=root,clock=NOW,official_volume_overlay=path)["status"]=="ALREADY_PUBLISHED"


def test_legacy_volume_conflicting_official_source_is_blocked(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path)
    path=overlay(project,market,rows=[observation("2026-10-13",volume=1200)])
    with pytest.raises(ValueError,match="VOLUME_CONFLICT"):
        evaluate_exact_volume(marketwide=market,project=project,code=CODE,
                              legacy_root=root,clock=NOW,official_volume_overlay=path)


def test_forged_or_future_receipts_rejected(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path)
    path=overlay(project,market,rows=[observation("2026-10-13")])
    path.write_bytes(path.read_bytes()+b"tamper")
    with pytest.raises(ValueError,match="PIN_INVALID"):
        module.read_volume_overlay(path,expected_code=CODE,
                                   expected_source=_source(market)[0]["content_sha256"],
                                   clock=NOW)
    report=json.loads(path.read_bytes().removesuffix(b"tamper"))
    report["rows"][0]["first_locally_received_at_utc"]="2026-10-15T01:00:00+00:00"
    unsigned=dict(report);unsigned.pop("content_sha256")
    report["content_sha256"]=sha256(canonical(unsigned)).hexdigest()
    path.write_bytes(canonical(report)+b"\n")
    with pytest.raises(ValueError,match="ROW_INVALID"):
        module.read_volume_overlay(path,expected_code=CODE,
                                   expected_source=_source(market)[0]["content_sha256"],
                                   clock=NOW)


def test_verified_original_krx_source_both_venues_required(tmp_path,monkeypatch):
    project,market=arranged(tmp_path)
    source,_=_source(market)
    root=project/"mock_first_receipts"
    root.mkdir()
    left=root/"cospi"
    right=root/"cosdaq"
    left.mkdir();right.mkdir()
    moments={}
    for day in ("2026-10-08","2026-10-13"):
        for name,folder in (("krx-kospi",left),("krx-kosdaq",right)):
            moments[(day,name)]=(datetime(2026,10,14,1,tzinfo=timezone.utc),
                                 folder,"a"*64)
    def fake_index(root,now):
        return moments
    def fake_verify(folder,name,pin,now):
        if name=="krx-kospi":assert folder==left
        else:assert folder==right
        return ({"source":name,"request_value":current_day[0],
                 "first_local_received_at_utc":"2026-10-14T01:00:00+00:00"}, {})
    current_day=["2026-10-13"]
    original_frame=module._krx_frame
    def fake_frame(name,meta,raw):
        day=meta["request_value"]
        if day=="2026-10-08":
            if name=="krx-kospi":
                return pd.DataFrame([{"security_id":CODE,"name":"sample",
                     "venue":"KOSPI","session":pd.Timestamp(day),
                     "close":100.,"market_cap":10000000.,
                     "turnover":500000.,"volume":1500}])
            return pd.DataFrame(columns=[
                "security_id","name","venue","session","close",
                "market_cap","turnover","volume"])
        by=[]
        for row in source["securities"]:
            venue="krx-kospi" if row["venue"]=="KOSPI" else "krx-kosdaq"
            if venue==name:
                by.append({"security_id":row["security_id"],"name":row["name"],
                           "venue":row["venue"],"session":pd.Timestamp(day),
                           "close":row["close"],"market_cap":row["market_cap"],
                           "turnover":row["turnover"],"volume":1000})
        return pd.DataFrame(by)
    monkeypatch.setattr(module,"_receipt_index",fake_index)
    def fake_capture(folder,name,pin,now):
        return fake_verify(folder,name,pin,now)
    monkeypatch.setattr(module,"verified_capture",fake_capture)
    monkeypatch.setattr(module,"_krx_frame",fake_frame)
    # Dynamic day metadata is supplied by the indexed first receipt, not
    # regenerated according to current local time.
    current_day[0]="2026-10-08"
    # Validate the older day if only its two original KRX receipts exist.
    subset=dict(moments)
    for key in list(subset):
        if key[0]=="2026-10-13":
            subset.pop(key)
    monkeypatch.setattr(module,"_receipt_index",lambda *_: subset)
    result=module.construct_volume_overlay(
        marketwide=market,project=project,capture_root=root,
        stock_code=CODE,clock=NOW)
    assert result["capture_dates"]==["2026-10-08"]
    assert result["orders_enabled"] is False


def test_missing_capture_root_is_rejected_without_writes(tmp_path):
    project,market=arranged(tmp_path)
    with pytest.raises(ValueError,match="CAPTURE_ROOT_UNSAFE"):
        module.publish_volume_overlay(
            marketwide=market,project=project,
            capture_root=tmp_path/"missing",stock_code=CODE,clock=NOW)
    assert not list((project/"output").glob("official_krx_volume_overlay/KR_*"))


def test_operations_prefers_verified_more_complete_volume_days(tmp_path):
    from eraleader.operations_overview import audit_local_operations
    project,market=arranged(tmp_path)
    root=cached(tmp_path,no=(0,5))
    old=publish_exact_dated_volume(
        marketwide=market,project=project,code=CODE,legacy_root=root,clock=NOW)
    assert old["matched_20"]==18
    latest=overlay(project,market,rows=[
        observation("2026-10-08"),observation("2026-10-13")])
    improved=publish_exact_dated_volume(
        marketwide=market,project=project,code=CODE,
        legacy_root=root,clock=NOW,official_volume_overlay=latest)
    assert improved["matched_20"]==20 and improved["matched_5"]==5
    chosen=audit_local_operations(project,clock=NOW)["kr_marketwide_dated_exact_volume"]
    assert chosen["volume_days_20"]==20
    assert chosen["href"].endswith(Path(improved["site"]).parent.name+"/index.html")


def test_missing_official_overlay_never_assumed_valid(tmp_path):
    project,market=arranged(tmp_path)
    root=cached(tmp_path,no=(0,))
    with pytest.raises(ValueError):
        evaluate_exact_volume(
            marketwide=market,project=project,code=CODE,legacy_root=root,
            official_volume_overlay=project/"missing_overlay.json",clock=NOW)
