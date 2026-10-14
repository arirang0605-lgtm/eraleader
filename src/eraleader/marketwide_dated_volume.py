"""Exact-date selected-security Kiwoom investor shares / cached KRX volume.

No guesswork: each 5/20 investor session must have a positive, matching
daily volume. Historic PIT, corporate actions and official flow score remain N/A.
"""
from __future__ import annotations
from datetime import date,datetime,timezone
from hashlib import sha256
from pathlib import Path
from html import escape
from zoneinfo import ZoneInfo
import json
import os
import shutil
import tempfile

from .data import read_market_bars, LEGACY_DEFAULT
from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source,prepare_search
from .marketwide_dated_flow import (
    read_dated_flow, plan_dated_capture, FOLDER as DATED_FOLDER,
)

SCHEMA="eraleader.kr_kiwoom_volume_exact_dated_v1"
FOLDER="marketwide_dated_volume"
PERIODS=(5,20)


def evaluate_exact_volume(*,marketwide:Path,project:Path,code:str,
                          legacy_root:Path=LEGACY_DEFAULT,
                          clock:datetime|None=None,
                          official_volume_overlay:Path|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("EXACT_VOLUME_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    if not legacy_root.is_absolute() or legacy_root.is_symlink() or not legacy_root.is_dir():
        raise ValueError("EXACT_VOLUME_CACHE_ROOT_UNSAFE")
    source,_=_source(marketwide)
    prepare_search(source,request_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),
                   clock=now)
    pin=plan_dated_capture(marketwide=marketwide,project=project,
                           stock_code=code,clock=now)
    if pin["status"]!="DATED_FLOW_ALREADY_CAPTURED":
        return {
            "status":"EXACT_VOLUME_DATED_EVIDENCE_NOT_AVAILABLE",
            "code":code,"flow_5_20_aligned":False,
            "formal_flow_score_available":False,"orders_enabled":False,
        }
    witness=read_dated_flow(Path(pin["file"]),expected_code=code,
                           expected_source=source["content_sha256"],clock=now)
    market_date=date.fromisoformat(source["market_session"])
    cache=legacy_root/"datasets/external_validation/marcap/data"/(
        "marcap-"+str(market_date.year)+".parquet")
    if cache.is_symlink() or any(p.is_symlink() for p in cache.parents):
        raise ValueError("EXACT_VOLUME_CACHE_SYMLINK")
    cache_sha=None
    daily={}
    if cache.is_file():
        # One existing local year, entirely read-only. Reuse price-validator.
        with cache.open("rb") as stream:
            checksum=sha256()
            while data:=stream.read(1024*1024):checksum.update(data)
            cache_sha=checksum.hexdigest()
        try:
            bars,_=read_market_bars("KR",market_date,days=65,
                                    legacy_root=legacy_root,tickers=[code])
            for row in bars.loc[bars["security_id"]==code].itertuples():
                key=row.session.date().isoformat()
                if key in daily:
                    raise ValueError("EXACT_VOLUME_DUPLICATE_DAY")
                v=row.volume
                if row.is_suspended or v<=0:
                    continue
                daily[key]=int(v) if int(v)==v else float(v)
        except (ValueError,FileNotFoundError):
            daily={}
    added_official=set()
    overlay_sha=None
    if official_volume_overlay is not None:
        from .official_krx_volume_overlay import read_volume_overlay
        official=read_volume_overlay(
            official_volume_overlay,expected_code=code,
            expected_source=source["content_sha256"],clock=now)
        if (official["source_market_session"]!=source["market_session"]
                or official["dated_kiwoom_sha256"]!=witness["content_sha256"]
                or official["orders_enabled"] is not False):
            raise ValueError("EXACT_VOLUME_OFFICIAL_OVERLAY_IDENTITY_MISMATCH")
        overlay_sha=official["content_sha256"]
        for observed in official["rows"]:
            day=observed["session"]
            volume=observed["volume"]
            if day in daily:
                if daily[day]!=volume:
                    raise ValueError("EXACT_VOLUME_KRX_LEGACY_VOLUME_CONFLICT")
                continue
            if volume>0:
                daily[day]=volume
                added_official.add(day)
    first=witness["rows"][0]["session"]
    if first!=source["market_session"]:
        raise ValueError("EXACT_VOLUME_MARKET_SESSION_MISMATCH")
    periods={}
    for n in PERIODS:
        observed=witness["rows"][:n]
        expected_dates=[r["session"] for r in observed]
        volumes=[daily.get(day) for day in expected_dates]
        missing=[date_ for date_,volume in zip(expected_dates,volumes)
                 if volume is None]
        full=not missing and len(expected_dates)==n
        denominator=(sum(volumes) if full else None)
        assert denominator is None or denominator>0
        normalized={}
        for field in ("foreign","institution"):
            values=[row[field+"_net_shares"] for row in observed]
            quantity=sum(values) if all(type(v) is int for v in values) else None
            normalized[field+"_net_shares"]=quantity
            normalized[field+"_pct_of_matched_daily_volume"]=(
                round(100*quantity/denominator,6)
                if denominator is not None and quantity is not None else None)
        periods[str(n)]={
            "official_first_receipt_added_days":sorted(added_official.intersection(expected_dates)),
            "dated_flow_observations":n,
            "matched_price_volume_days":n-len(missing),
            "missing_price_volume_dates":missing,
            "exact_matched_daily_volume_total_shares":denominator,
            "all_observation_dates_matched":full,
            **normalized,
        }
    payload={
        "schema":SCHEMA,"market":"KR","mode":"demo",
        "source_market_session":source["market_session"],
        "source_marketwide_sha256":source["content_sha256"],
        "stock_code":code,"dated_flow_sha256":witness["content_sha256"],
        "kiwoom_first_gateway_received_at_utc":
            witness["first_gateway_received_at_utc"],
        "cache_file_sha256":cache_sha,
        "official_volume_overlay_sha256":overlay_sha,
        "official_source_added_price_days":sorted(added_official),
        "price_volume_cache_independently_pit_certified":False,
        "exchange_trading_calendar_certified":False,
        "corporate_actions_issuer_pit_certified":False,
        "investor_trade_dates_covered_from_saved_receipts":True,
        "periods":periods,
        "formal_flow_score_10":None,
        "order_instructions":False,"orders_enabled":False,
        "formal_leaders":0,
    }
    payload["content_sha256"]=sha256(canonical(payload)).hexdigest()
    return payload


def _html(report:dict)->bytes:
    rows=[]
    for n in PERIODS:
        r=report["periods"][str(n)]
        values=[n,r["matched_price_volume_days"],len(r["missing_price_volume_dates"]),
                r["exact_matched_daily_volume_total_shares"],
                r["foreign_net_shares"],
                r["foreign_pct_of_matched_daily_volume"],
                r["institution_net_shares"],
                r["institution_pct_of_matched_daily_volume"]]
        rows.append("<tr>"+''.join(
            "<td>"+escape("N/A" if x is None else str(x))+"</td>" for x in values)+
            "</tr>")
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader · 정확한 수급 날짜·거래량 대조</title>'
        '<style>body{font:14px system-ui;margin:24px auto;max-width:1100px;padding:0 16px}'
        'table{border-collapse:collapse}td,th{border-bottom:1px solid #aaa;padding:8px}</style>'
        '</head><body><h1>날짜가 일치하는 수급·거래량 비교 (연구용)</h1>'
        '<p>키움 모의 수급 개별 관측일과 로컬 marcap 거래량 바 날짜를 '
        '정확히 대조합니다. 결측된 일자가 하나라도 있으면 그 구간 비율은 N/A. '
        '거래소 영업일/기업행동/PIT는 독립 확인 전이며 매수 신호·수급10점·자동주문에 미사용.</p>'
        '<p>KRX 관측일 '+escape(report["source_market_session"])+
        ' · 종목 '+escape(report["stock_code"])+
        '</p><table><thead><tr>'+
        ''.join("<th>"+x+"</th>" for x in (
            "관측행","일치 거래량 바","결측 거래일 수","해당일 거래량 합계(주)",
            "외국인 순매매(주)","외국인 거래량 대비(%)",
            "기관 순매매(주)","기관 거래량 대비(%)"))+
        '</tr></thead><tbody>'+''.join(rows)+
        '</tbody></table><footer>Read only · 정식 대장주0 · 실전주문0</footer></body></html>'
        ).encode("utf-8")


def publish_exact_dated_volume(*,marketwide:Path,project:Path,code:str,
                               legacy_root:Path=LEGACY_DEFAULT,
                               clock:datetime|None=None,
                               official_volume_overlay:Path|None=None)->dict:
    report=evaluate_exact_volume(marketwide=marketwide,project=project,
                                 code=code,legacy_root=legacy_root,clock=clock,
                                 official_volume_overlay=official_volume_overlay)
    if report.get("status")=="EXACT_VOLUME_DATED_EVIDENCE_NOT_AVAILABLE":
        return report
    base=_owned_output(project)/FOLDER
    if base.is_symlink():raise ValueError("EXACT_VOLUME_OUTPUT_SYMLINK")
    base.mkdir(mode=0o700,exist_ok=True)
    pinned={
        "market":report["source_marketwide_sha256"],
        "flow":report["dated_flow_sha256"],
        "cache":report["cache_file_sha256"],
    }
    if official_volume_overlay is not None:
        pinned["official_volume_overlay"]=report["official_volume_overlay_sha256"]
    version=sha256(canonical(pinned)).hexdigest()[:12]
    target=base/("KR_"+report["source_market_session"].replace("-","")
                 +"_"+report["stock_code"]+"_"+version)
    manifest=canonical(report)+b"\n"
    html=_html(report)
    if target.is_symlink():raise ValueError("EXACT_VOLUME_TARGET_SYMLINK")
    if target.exists():
        if (not target.is_dir() or
                (target/"manifest.json").is_symlink() or
                (target/"index.html").is_symlink() or
                (target/"manifest.json").read_bytes()!=manifest or
                (target/"index.html").read_bytes()!=html):
            raise ValueError("EXACT_VOLUME_EXISTING_CONFLICT")
        state="ALREADY_PUBLISHED"
    else:
        staged=Path(tempfile.mkdtemp(prefix=".exactflow_",dir=base))
        try:
            os.chmod(staged,0o700)
            for name,data in (("manifest.json",manifest),("index.html",html)):
                fd=os.open(staged/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,"wb") as out:
                    out.write(data);out.flush();os.fsync(out.fileno())
            if target.exists() or target.is_symlink():
                raise ValueError("EXACT_VOLUME_PUBLICATION_RACE")
            os.rename(staged,target)
        finally:
            if staged.exists():shutil.rmtree(staged)
        state="PUBLISHED"
    return {
        "status":state,"stock_code":report["stock_code"],
        "market_session":report["source_market_session"],
        "matched_5":report["periods"]["5"]["matched_price_volume_days"],
        "matched_20":report["periods"]["20"]["matched_price_volume_days"],
        "fully_aligned_5":report["periods"]["5"]["all_observation_dates_matched"],
        "fully_aligned_20":report["periods"]["20"]["all_observation_dates_matched"],
        "site":str(target/"index.html"),
        "manifest":str(target/"manifest.json"),
        "flow_score_10":None,"orders_enabled":False,
    }
