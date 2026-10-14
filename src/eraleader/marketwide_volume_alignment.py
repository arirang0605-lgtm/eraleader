"""Marketwide KR investor-flow and local price-volume freshness gate.

Reuse existing read-only marcap parquet. A stock's 5/20 observed investor
rows cannot be matched to volume until dated investor rows are captured,
and the cache must include the source's exact market session. No scores.
"""
from __future__ import annotations

from datetime import date,datetime,timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
from html import escape
import json
import math
import numbers
import os
import re
import shutil
import tempfile

from .data import LEGACY_DEFAULT,read_market_bars
from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source,prepare_search
from .marketwide_flow_coverage import summarize_flow_coverage

SCHEMA="eraleader.kr_investor_volume_alignment_v1"
FOLDER="marketwide_volume_alignment"
CACHE_FOLDER="datasets/external_validation/marcap/data"
NEEDED=20
MAX_PRICE_LOOKBACK=65


def audit_volume_alignment(*,marketwide:Path,project:Path,
                           legacy_root:Path=LEGACY_DEFAULT,
                           clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("VOLUME_ALIGNMENT_CLOCK_UNAWARE")
    now=now.astimezone(timezone.utc)
    if (not isinstance(legacy_root,Path) or not legacy_root.is_absolute()
            or legacy_root.is_symlink() or not legacy_root.is_dir()
            or any(p.is_symlink() for p in legacy_root.parents)):
        raise ValueError("VOLUME_ALIGNMENT_CACHE_ROOT_UNSAFE")
    _owned_output(project)
    source,_=_source(marketwide)
    from .data import validate_bars
    day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    view,_=prepare_search(source,request_day=day,clock=now)
    observed=date.fromisoformat(source["market_session"])
    coverage=summarize_flow_coverage(marketwide=marketwide,project=project,clock=now)
    if (coverage["source_marketwide_sha256"]!=source["content_sha256"]
            or coverage["source_market_session"]!=source["market_session"]
            or coverage["orders_enabled"] is not False
            or coverage["investment_flow_score_available"] is not False):
        raise ValueError("VOLUME_ALIGNMENT_SOURCE_MISMATCH")
    codes=[x["security_id"] for x in coverage["rows"]]
    if len(codes)!=len(set(codes)) or len(codes)>500:
        raise ValueError("VOLUME_ALIGNMENT_CODES_INVALID")
    cache=legacy_root/CACHE_FOLDER/("marcap-"+str(observed.year)+".parquet")
    if cache.is_symlink() or any(p.is_symlink() for p in cache.parents):
        raise ValueError("VOLUME_ALIGNMENT_CACHE_SYMLINK")
    if cache.exists() and not cache.is_file():
        raise ValueError("VOLUME_ALIGNMENT_CACHE_NOT_REGULAR")
    if cache.is_file():
        with cache.open("rb") as stream:
            digest=sha256()
            while block:=stream.read(1024*1024):
                digest.update(block)
        cache_hash=digest.hexdigest()
    else:
        cache_hash=None
    bars=None
    if codes and cache_hash is not None:
        try:
            bars,_=read_market_bars("KR",observed,days=MAX_PRICE_LOOKBACK,
                                   legacy_root=legacy_root,tickers=codes)
        except (ValueError,FileNotFoundError):
            bars=None
    by_code={r["security_id"]:r for r in source["securities"]}
    rows=[]
    for source_flow in coverage["rows"]:
        code=source_flow["security_id"]
        if code not in by_code:
            raise ValueError("VOLUME_ALIGNMENT_MISSING_SECURITY")
        sec=by_code[code]
        if bars is not None:
            subset=bars.loc[bars["security_id"]==code]
            subset=subset.sort_values("session")
        else:
            subset=None
        latest=(str(subset.iloc[-1]["session"].date()) if
                subset is not None and not subset.empty else None)
        fully_current=latest==source["market_session"]
        matched_volume=None
        if fully_current and subset is not None:
            # Not a denominator for 5/20 investor rows. These are ONLY the
            # observed volume sessions in this price cache.
            volumes=[v for v in subset["volume"].tail(NEEDED).tolist()
                     if isinstance(v,numbers.Real) and not isinstance(v,bool)
                     and math.isfinite(v) and v>=0]
            if len(volumes)==NEEDED:
                matched_volume={
                    "cache_last_5_volume_observations":int(sum(volumes[-5:])),
                    "cache_last_20_volume_observations":int(sum(volumes)),
                    "cache_volume_day":latest,
                    "denominator_is_investor_row_aligned":False,
                }
        status=("NO_DATED_INVESTOR_ROWS_TO_MATCH" if matched_volume is not None
                else "PRICE_CACHE_LATEST_SESSION_VOLUME_INCOMPLETE" if fully_current
                else "PRICE_CACHE_NOT_AT_KRX_SESSION" if latest is not None
                     else "PRICE_CACHE_MISSING_SECURITY")
        rows.append({
            "security_id":code,
            "name":sec["name"],
            "source_krx_market_session":source["market_session"],
            "cache_last_price_session":latest,
            "cache_matches_source_session":fully_current,
            "cache_20_observed_volume":matched_volume,
            "flow_has_20_observed_rows":source_flow["has_20_observed_sessions"],
            "flow_first_gateway_received_at_utc":
                source_flow["first_gateway_received_at_utc"],
            "exact_flow_volume_5_20_ratio":None,
            "valid_flow_score_10":None,
            "alignment_status":status,
        })
    result={
        "schema":SCHEMA,"market":"KR",
        "source_market_session":source["market_session"],
        "source_marketwide_sha256":source["content_sha256"],
        "source_built_at_utc":view["source_built_at_utc"],
        "flow_batch_sha256":coverage["batch_sha256"],
        "local_cache_file":str(cache),
        "local_cache_sha256":cache_hash,
        "price_cache_adjustments_pit_certified":False,
        "flow_daily_dates_persisted":False,
        "source_price_is_research":True,
        "flow_stocks":len(rows),
        "source_session_price_cache_matched":sum(
            x["cache_matches_source_session"] for x in rows),
        "flow_volume_fully_aligned_stocks":0,
        "flow_score_10_available":0,
        "formal_leaders":0,"orders_enabled":False,
        "rows":rows,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    return result


def _html(result:dict)->bytes:
    cells=[]
    for row in result["rows"]:
        parts=[row["security_id"],row["name"],
               row["source_krx_market_session"],
               row["cache_last_price_session"],
               row["cache_matches_source_session"],
               row["flow_has_20_observed_rows"],
               row["alignment_status"]]
        cells.append("<tr>"+''.join(
            "<td>"+escape("N/A" if x is None else str(x),quote=True)+"</td>"
            for x in parts)+"</tr>")
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader 수급·거래량 날짜 일치 여부</title>'
        '<style>body{font:14px system-ui;margin:24px auto;max-width:1080px;padding:0 16px}'
        'table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #aaa}</style>'
        '</head><body><h1>수급·거래량 관측시점 매칭</h1>'
        '<p>실제 키움 수급 5/20관측행의 날짜가 별도 보존되지 않은 상태입니다. '
        'marcap 캐시의 마지막 거래량 날짜가 같아도 정식 수급 대비 거래량 비율을 '
        '계산하지 않습니다. 매도/매수 신호 아님.</p>'
        '<p>KRX 거래일 '+escape(result["source_market_session"])+
        ' · 수급종목 '+str(result["flow_stocks"])+
        ' · 원거래일 시세캐시 일치 '+str(result["source_session_price_cache_matched"])+
        ' · 정식 수급-거래량 정합 '+str(result["flow_volume_fully_aligned_stocks"])+
        '</p><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in
        ("코드","종목명","KRX 거래일","캐시 최종거래일",
         "가격날짜 일치","수급20관측","정합상태"))+
        '</tr></thead><tbody>'+''.join(cells)+
        '</tbody></table><footer>연구용 · 조정주가/PIT 미인증 · 정식 flow10점 N/A · 주문0</footer></body></html>'
    ).encode("utf-8")


def publish_volume_alignment(*,marketwide:Path,project:Path,
                             legacy_root:Path=LEGACY_DEFAULT,
                             clock:datetime|None=None)->dict:
    data=audit_volume_alignment(marketwide=marketwide,project=project,
                                legacy_root=legacy_root,clock=clock)
    target=_owned_output(project)/FOLDER
    if target.is_symlink():
        raise ValueError("VOLUME_ALIGNMENT_OUTPUT_SYMLINK")
    target.mkdir(mode=0o700,exist_ok=True)
    fingerprint=sha256(canonical({
        "source":data["source_marketwide_sha256"],
        "flow":data["flow_batch_sha256"],
        "cache":data["local_cache_sha256"],
    })).hexdigest()[:12]
    folder=target/("KR_"+data["source_market_session"].replace("-","")
                   +"_"+data["source_marketwide_sha256"][:16]+"_"+fingerprint)
    expected=canonical(data)+b"\n"
    html=_html(data)
    if folder.is_symlink():
        raise ValueError("VOLUME_ALIGNMENT_PUBLISH_SYMLINK")
    if folder.exists():
        if (not folder.is_dir() or
                (folder/"manifest.json").is_symlink() or
                (folder/"index.html").is_symlink() or
                (folder/"manifest.json").read_bytes()!=expected or
                (folder/"index.html").read_bytes()!=html):
            raise ValueError("VOLUME_ALIGNMENT_EXISTING_CONFLICT")
        state="ALREADY_PUBLISHED"
    else:
        stage=Path(tempfile.mkdtemp(prefix=".volume_align_",dir=target))
        try:
            os.chmod(stage,0o700)
            for name,bytes_ in (("manifest.json",expected),("index.html",html)):
                fd=os.open(stage/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,"wb") as f:
                    f.write(bytes_);f.flush();os.fsync(f.fileno())
            if folder.exists() or folder.is_symlink():
                raise ValueError("VOLUME_ALIGNMENT_VERSION_RACE")
            os.rename(stage,folder)
        finally:
            if stage.exists():shutil.rmtree(stage)
        state="PUBLISHED"
    return {
        "status":state,"market_session":data["source_market_session"],
        "flow_stocks":data["flow_stocks"],
        "price_cache_matched":data["source_session_price_cache_matched"],
        "flow_volume_aligned":0,
        "flow_score_available":False,
        "file":str(folder/"manifest.json"),
        "site":str(folder/"index.html"),
        "orders":0,
    }
