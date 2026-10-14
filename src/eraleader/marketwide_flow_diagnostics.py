"""Liquidity-independent share-supply proxy diagnostics for verified KR flow.

No trade, rank, normalized 10-point flow score or historic PIT claims.
Market capitalization / same-session close is only an *implied* total-share
denominator, not float, adjusted holdings, or matching 5/20 trading volumes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os
import shutil
import tempfile

from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source
from .marketwide_flow_coverage import summarize_flow_coverage
from .official_company_explorer import canonical

SCHEMA="eraleader.kr_selected_flow_implied_share_proxy.v1"
FOLDER="marketwide_flow_diagnostics"
PROXY="KRX_MARKETCAP_DIVIDED_BY_SAME_SESSION_CLOSE_NOT_ACTUAL_FLOAT"
PERCENTAGE_FIELDS=(
    "foreign_net_5_shares","institution_net_5_shares",
    "foreign_net_20_shares","institution_net_20_shares"
)


def _pct(shares, *, close, cap):
    if shares is None or close is None or cap is None:
        return None
    if (type(shares) is not int or type(close) not in (int,float)
            or type(cap) not in (int,float) or not math.isfinite(close)
            or not math.isfinite(cap) or close<=0 or cap<=0):
        raise ValueError("FLOW_DIAGNOSTIC_DENOMINATOR_INVALID")
    return round(100*shares*close/cap,6)


def _direction(five,twenty):
    if five is None or twenty is None:
        return None
    if type(five) is not int or type(twenty) is not int:
        raise ValueError("FLOW_DIAGNOSTIC_SHARES_NOT_INTEGER")
    if five>0 and twenty>0:
        return "BOTH_POSITIVE"
    if five<0 and twenty<0:
        return "BOTH_NEGATIVE"
    return "MIXED_OR_ZERO"


def inspect_flow_share_proxy(*,marketwide:Path,project:Path,
                             clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if (not isinstance(now,datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("FLOW_DIAGNOSTIC_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    source,_=_source(marketwide)
    coverage=summarize_flow_coverage(
        marketwide=marketwide,project=project,clock=now)
    if (coverage["source_marketwide_sha256"]!=source["content_sha256"]
            or coverage["source_market_session"]!=source["market_session"]
            or coverage["mode"]!="demo" or coverage["orders_enabled"] is not False
            or coverage["investment_flow_score_available"] is not False):
        raise ValueError("FLOW_DIAGNOSTIC_SOURCE_MISMATCH")
    lookup={x["security_id"]:x for x in source["securities"]}
    if len(lookup)!=len(source["securities"]):
        raise ValueError("FLOW_DIAGNOSTIC_DUPLICATE_SECURITIES")
    items=[]
    denominator_available=0
    for flow in coverage["rows"]:
        code=flow["security_id"]
        sec=lookup.get(code)
        if sec is None or sec["market_session"]!=coverage["source_market_session"]:
            raise ValueError("FLOW_DIAGNOSTIC_IDENTITY_DATE_INVALID")
        close,cap=sec["close"],sec["market_cap"]
        if (close is not None and cap is not None
                and type(close) in (float,int) and type(cap) in (float,int)
                and math.isfinite(close) and math.isfinite(cap)
                and close>0 and cap>0 and sec["market_traded"] is True):
            implied=cap/close
            if not math.isfinite(implied) or implied<=0:
                raise ValueError("FLOW_DIAGNOSTIC_IMPLIED_SHARES_INVALID")
            denominator_available+=1
        else:
            implied=None
            close=cap=None
        values={field.replace("_shares","_pct_of_implied_total_shares"):
                    _pct(flow[field],close=close,cap=cap)
                for field in PERCENTAGE_FIELDS}
        items.append({
            "security_id":code,
            "name":sec["name"],
            "source_market_session":sec["market_session"],
            "source_krx_close":close,
            "source_krx_market_cap":cap,
            "implied_total_shares_proxy":round(implied,2) if implied is not None else None,
            "denominator_kind":PROXY if implied is not None else None,
            "raw_net_shares":{f:flow[f] for f in PERCENTAGE_FIELDS},
            **values,
            "foreign_5_20_direction":_direction(
                flow["foreign_net_5_shares"],flow["foreign_net_20_shares"]),
            "institution_5_20_direction":_direction(
                flow["institution_net_5_shares"],flow["institution_net_20_shares"]),
            "flow_first_gateway_received_at_utc":flow["first_gateway_received_at_utc"],
            "flow_decision_at_utc":flow["decision_at_utc"],
            "flow_research_sha256":flow["original_research_sha256"],
            "flow_score_10":None,
        })
    payload={
        "schema":SCHEMA,"market":"KR","mode":"demo",
        "source_market_session":coverage["source_market_session"],
        "source_marketwide_sha256":coverage["source_marketwide_sha256"],
        "source_built_at_utc":coverage["source_built_at_utc"],
        "source_flow_batch_sha256":coverage["batch_sha256"],
        "stocks_with_flow":len(items),
        "stocks_with_usable_denominator":denominator_available,
        "shares_proxy_method":PROXY,
        "units":"PERCENT_OF_MARKETCAP_IMPLIED_TOTAL_SHARES",
        "measure_is_5_20_observed_rows_not_exchange_calendar_days":True,
        "turnover_or_volume_matched_by_each_observation":False,
        "free_float_independently_verified":False,
        "is_change_in_actual_ownership":False,
        "independent_historical_pit_certified":False,
        "investable_priority_rank_available":False,
        "formal_flow_score_10_available":False,
        "formal_leaders":0,
        "orders_enabled":False,
        "rows":items,
    }
    payload["content_sha256"]=sha256(canonical(payload)).hexdigest()
    return payload


def _html(doc:dict)->bytes:
    def val(x):
        return "N/A" if x is None else str(x)
    rows=[]
    for r in doc["rows"]:
        cells=[r["security_id"],r["name"],r["source_krx_close"],
            r["implied_total_shares_proxy"],
            r["foreign_net_5_pct_of_implied_total_shares"],
            r["institution_net_5_pct_of_implied_total_shares"],
            r["foreign_net_20_pct_of_implied_total_shares"],
            r["institution_net_20_pct_of_implied_total_shares"],
            r["foreign_5_20_direction"],r["institution_5_20_direction"]]
        rows.append('<tr>'+''.join(
            '<td>'+escape(val(c),quote=True)+'</td>' for c in cells)+'</tr>')
    content=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader · 수급 추정주식수 기준 관찰</title>'
        '<style>body{font:14px system-ui;margin:24px auto;padding:0 12px;max-width:1180px}'
        'table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #aaa}'
        '.scroll{overflow-x:auto}.notice{padding:14px;background:#aaa2;border-left:4px solid #b87}</style>'
        '</head><body><h1>KR 기관·외국인 수급 — 추정 발행주식수 대비 관측</h1>'
        '<div class="notice">종가와 시가총액으로 추정한 전체 발행주식수 대비 순매매 주수입니다. '
        '유통주식수·주주 실제 지분변화·거래량 기반 매집률이 아닙니다. '
        '최근 5·20개는 모의 키움 API 관측행 수이며, 거래소 5·20거래일 검증이 아닙니다. '
        '단독 10점 수급 신호, 매수/매도, 정식 대장주 확정에 사용하지 않습니다.</div>'
        '<p>KRX 시장일 '+escape(doc["source_market_session"])+
        ' · 키움 모의 종목 '+str(doc["stocks_with_flow"])+
        ' · 분모 가용 '+str(doc["stocks_with_usable_denominator"])+
        ' · 시세 SHA '+doc["source_marketwide_sha256"][:16]+'</p>'
        '<div class="scroll"><table><thead><tr>'+
        ''.join('<th>'+escape(h)+'</th>' for h in (
            '종목코드','종목명','종가','추정 전체주식수','외국인5(%)','기관5(%)',
            '외국인20(%)','기관20(%)','외국인 5/20 방향','기관 5/20 방향'))+
        '</tr></thead><tbody>'+''.join(rows)+
        '</tbody></table></div><footer>Research only · PIT 미인증 · 주문 0</footer></body></html>'
    )
    return content.encode("utf-8")


def publish_flow_share_proxy(*,marketwide:Path,project:Path,
                             clock:datetime|None=None)->dict:
    output=_owned_output(project)
    report=inspect_flow_share_proxy(
        marketwide=marketwide,project=project,clock=clock)
    folder=output/FOLDER
    if folder.is_symlink():
        raise ValueError("FLOW_DIAGNOSTIC_OUTPUT_SYMLINK")
    folder.mkdir(mode=0o700,exist_ok=True)
    if folder.is_symlink() or folder.stat().st_uid!=os.geteuid():
        raise ValueError("FLOW_DIAGNOSTIC_OUTPUT_UNSAFE")
    version=sha256(canonical({
        "source":report["source_marketwide_sha256"],
        "batches":report["source_flow_batch_sha256"],
        "method":SCHEMA,
    })).hexdigest()[:12]
    target=folder/("KR_"+report["source_market_session"].replace("-","")
                   +"_"+report["source_marketwide_sha256"][:16]+"_"+version)
    doc=canonical(report)+b"\n"
    html=_html(report)
    if target.is_symlink():
        raise ValueError("FLOW_DIAGNOSTIC_VERSION_SYMLINK")
    if target.exists():
        if (not target.is_dir() or
                (target/"manifest.json").is_symlink() or
                (target/"index.html").is_symlink() or
                (target/"manifest.json").read_bytes()!=doc or
                (target/"index.html").read_bytes()!=html):
            raise ValueError("FLOW_DIAGNOSTIC_EXISTING_VERSION_CONFLICT")
        status="ALREADY_PUBLISHED"
    else:
        stage=Path(tempfile.mkdtemp(prefix=".flowdiagnostics_",dir=folder))
        try:
            os.chmod(stage,0o700)
            for name,body in (("manifest.json",doc),("index.html",html)):
                fd=os.open(stage/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"wb") as out:
                    out.write(body)
                    out.flush()
                    os.fsync(out.fileno())
            if target.exists() or target.is_symlink():
                raise ValueError("FLOW_DIAGNOSTIC_PUBLICATION_RACE")
            os.rename(stage,target)
        finally:
            if stage.exists():shutil.rmtree(stage)
        status="PUBLISHED"
    return {
        "status":status,"market_session":report["source_market_session"],
        "observed_stocks":report["stocks_with_flow"],
        "stocks_with_usable_denominator":report["stocks_with_usable_denominator"],
        "index":str(target/"index.html"),
        "manifest":str(target/"manifest.json"),
        "formal_flow_score_available":False,
        "orders":0,
    }
