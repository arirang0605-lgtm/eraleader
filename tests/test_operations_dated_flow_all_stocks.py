"""Operations view groups source-verified dated flow by stock, not by batch.

Research-only local output; never uses a broker, API call, or order engine.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re

import pytest

from eraleader.official_company_explorer import canonical
from eraleader.marketwide_dated_volume import SCHEMA,_html
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,10,tzinfo=timezone.utc)


def publish_fixture(project:Path,code:str,matched20:int,matched5:int=5):
    base=project/"output"/"marketwide_dated_volume"
    base.mkdir(exist_ok=True)
    assert 0<=matched5<=5 and 0<=matched20<=20
    source_sha="a"*64
    flow_sha=sha256(code.encode()).hexdigest()
    part={}
    for length,count in ((5,matched5),(20,matched20)):
        part[str(length)]={
            "dated_flow_observations":length,
            "matched_price_volume_days":count,
            "missing_price_volume_dates":[],
            "all_observation_dates_matched":count==length,
            "exact_matched_daily_volume_total_shares":None,
            "foreign_net_shares":100,
            "foreign_pct_of_matched_daily_volume":None,
            "institution_net_shares":60,
            "institution_pct_of_matched_daily_volume":None,
        }
    doc={
        "schema":SCHEMA,"market":"KR","mode":"demo",
        "source_market_session":"2026-10-13",
        "source_marketwide_sha256":source_sha,
        "stock_code":code,"dated_flow_sha256":flow_sha,
        "kiwoom_first_gateway_received_at_utc":"2026-10-14T01:00:00+00:00",
        "cache_file_sha256":"b"*64,
        "official_volume_overlay_sha256":(
            sha256(str(matched20).encode()).hexdigest() if matched20>0 else None),
        "price_volume_cache_independently_pit_certified":False,
        "exchange_trading_calendar_certified":False,
        "corporate_actions_issuer_pit_certified":False,
        "investor_trade_dates_covered_from_saved_receipts":True,
        "periods":part,
        "formal_flow_score_10":None,
        "order_instructions":False,"orders_enabled":False,"formal_leaders":0,
    }
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    pinned={"market":source_sha,"flow":flow_sha,"cache":doc["cache_file_sha256"]}
    if doc["official_volume_overlay_sha256"]:
        pinned["official_volume_overlay"]=doc["official_volume_overlay_sha256"]
    version=sha256(canonical(pinned)).hexdigest()[:12]
    folder=base/("KR_20261013_"+code+"_"+version)
    folder.mkdir()
    (folder/"manifest.json").write_bytes(canonical(doc)+b"\n")
    (folder/"index.html").write_bytes(_html(doc))
    return folder


def test_all_three_have_distinct_verified_readonly_links(tmp_path):
    _,project=fixture(tmp_path)
    for code in ("006110","417840","446540"):
        publish_fixture(project,code,20)
    report=audit_local_operations(project,clock=NOW)
    selections=report["kr_marketwide_dated_all_stocks"]
    assert [r["code"] for r in selections]==["006110","417840","446540"]
    assert all(r["volume_days_5"]==5 and r["volume_days_20"]==20 and r["orders"]==0
               for r in selections)
    page=render_operations_overview(report)
    assert "수급·거래량 검증 종목 전체" in page
    assert page.count("날짜별 수급·거래량 보기")==3
    assert "대장주 순위·정식 수급10점이 아닙니다" in page
    assert report["kr_marketwide_dated_exact_volume"]["code"] in ("006110","417840","446540")


def test_per_company_favors_highest_verified_observation_coverage(tmp_path):
    _,project=fixture(tmp_path)
    publish_fixture(project,"417840",15,0)
    complete=publish_fixture(project,"417840",20,5)
    publish_fixture(project,"006110",20,5)
    got=audit_local_operations(project,clock=NOW)["kr_marketwide_dated_all_stocks"]
    assert len(got)==2
    x=next(v for v in got if v["code"]=="417840")
    assert x["volume_days_20"]==20
    assert complete.name in x["href"]


def test_corrupted_best_version_falls_back_to_previous_verified(tmp_path):
    _,project=fixture(tmp_path)
    older=publish_fixture(project,"417840",17,2)
    best=publish_fixture(project,"417840",20,5)
    (best/"index.html").write_bytes(b"TAMPER")
    observed=audit_local_operations(project,clock=NOW)["kr_marketwide_dated_all_stocks"]
    assert len(observed)==1
    assert observed[0]["volume_days_20"]==17
    assert older.name in observed[0]["href"]


def test_renderer_rejects_injected_link_and_duplicate_codes(tmp_path):
    _,project=fixture(tmp_path)
    publish_fixture(project,"417840",20,5)
    report=audit_local_operations(project,clock=NOW)
    report["kr_marketwide_dated_all_stocks"][0]["href"]="../../../../private"
    with pytest.raises(ValueError,match="Unsafe multi-stock"):
        render_operations_overview(report)
    report=audit_local_operations(project,clock=NOW)
    report["kr_marketwide_dated_all_stocks"]*=2
    with pytest.raises(ValueError,match="Unsafe multi-stock"):
        render_operations_overview(report)


def test_no_dated_flow_reports_empty_list_not_invalid_none(tmp_path):
    _,project=fixture(tmp_path)
    report=audit_local_operations(project,clock=NOW)
    assert report["kr_marketwide_dated_all_stocks"]==[]
    page=render_operations_overview(report)
    assert "종목별 검증된 날짜별 수급 보고서가 없습니다" in page
