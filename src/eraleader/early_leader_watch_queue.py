"""KR early-leader WATCH worklist assembled from actually observed factors.

Operational functions: prioritise the NEXT review/data-acquisition queue,
publish receiver-neutral JSON and clickable HTML, never claim certified 100pt
leader or send order instructions. No speculative filling of missing factors.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
import json
import math
import os
import re
import shutil
import tempfile

from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search
from .factor_selection_pipeline import _read_assessment, _validate

SCHEMA="eraleader.kr_early_watch_queue.v1"
FOLDER="early_leader_watch_queue"
MAX_WATCH=100
SECTOR_CONTEXT="CURRENT_DART_EXACT_CODE_OBSERVED_PEER_MEDIAN_V1_NOT_INDUSTRY_GROWTH_OR_MOAT"
TIERS=(
    "A_PRICE_EARNINGS_OBSERVED",
    "B_PRICE_FLOW_OBSERVED",
    "C_KRX_PRICE_TOP20",
    "D_PRICE_STRENGTH_OBSERVED",
)


def _observed_peer_context(market:dict)->dict[str,dict]:
    """Exact current DART industry peers only, not the whole listed industry.

    Return actual sample revenue/operating YoY observation and company-relative
    spreads (percentage points). Neither is an approved 20pt factor score.
    """
    groups={}
    for row in market["securities"]:
        kind=row.get("industry_code")
        revenue=row.get("revenue_yoy")
        if (not kind or row.get("current_dart_directory_matched") is not True
                or revenue is None):
            continue
        if (type(kind) is not str or type(revenue) not in (float,int)
                or not math.isfinite(revenue)):
            raise ValueError("EARLY_WATCH_DART_REVENUE_INVALID")
        operating=row.get("operating_income_yoy")
        if operating is not None and (type(operating) not in (int,float)
                                       or not math.isfinite(operating)):
            raise ValueError("EARLY_WATCH_DART_OPERATING_INVALID")
        groups.setdefault(kind,[]).append(row)
    context={}
    for peers in groups.values():
        if len(peers)<2:
            continue
        rev_med=median([r["revenue_yoy"] for r in peers])
        operating_values=[r["operating_income_yoy"] for r in peers
                          if r["operating_income_yoy"] is not None]
        operating_med=median(operating_values) if len(operating_values)>=2 else None
        for company in peers:
            own_operating=company["operating_income_yoy"]
            context[company["security_id"]]={
                "industry_sample_peer_count":len(peers),
                "industry_sample_revenue_growth_median_pct":round(100*rev_med,4),
                "company_revenue_growth_pct":round(100*company["revenue_yoy"],4),
                "company_revenue_growth_vs_peers_pp":
                    round(100*(company["revenue_yoy"]-rev_med),4),
                "industry_sample_operating_growth_median_pct":
                    round(100*operating_med,4) if operating_med is not None else None,
                "company_operating_growth_pct":
                    round(100*own_operating,4) if own_operating is not None else None,
                "company_operating_growth_vs_peers_pp":
                    round(100*(own_operating-operating_med),4)
                    if own_operating is not None and operating_med is not None else None,
            }
    return context


def _clock(clock):
    dt=clock or datetime.now(timezone.utc)
    if not isinstance(dt,datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("EARLY_WATCH_CLOCK_WITH_ZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def create_early_watch(*,marketwide:Path,project:Path,
                       factor_input:Path,top:int=50,
                       clock:datetime|None=None,
                       dart_cfs_capture_root:Path|None=None)->dict:
    now=_clock(clock)
    if type(top) is not int or not 1<=top<=MAX_WATCH:
        raise ValueError("EARLY_WATCH_TOP_OUT_OF_RANGE")
    _owned_output(project)
    market,_=_source(marketwide)
    viewed,_=prepare_search(
        market,request_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),
        clock=now)
    if viewed["stale_warning"]:
        return {"status":"EARLY_WATCH_STALE_MARKET_HOLD",
                "watch_candidates":0,"orders_enabled":False,
                "external_api_calls":0}
    factor=_read_assessment(factor_input)
    verified,_first_review_day=_validate(market,factor,now=now)
    if factor["source_marketwide_sha256"]!=market["content_sha256"]:
        raise ValueError("EARLY_WATCH_SOURCE_PIN_MISMATCH")
    asof=datetime.fromisoformat(factor["decision_at_utc"].replace("Z","+00:00"))
    original={r["security_id"]:r for r in market["securities"]}
    if len(original)!=len(market["securities"]):
        raise ValueError("EARLY_WATCH_DUPLICATE_SOURCE_CODE")
    peer_context=_observed_peer_context(market)
    if dart_cfs_capture_root is None:
        profitability={}
    else:
        from .dart_profitability_watch import dart_annual_margin_context
        profitability=dart_annual_margin_context(
            market=market,capture_root=dart_cfs_capture_root,now=now)
    entries=[]
    tier_counts=dict.fromkeys(TIERS,0)
    for item in verified:
        code=item["security_id"]
        observed=original[code]
        values=item["components"]
        price=values["momentum"]
        earnings=values["earnings"]
        flow=values["flow"]
        if price is None or observed["market_traded"] is not True:
            continue
        if earnings is not None and (
                observed.get("earnings_research_25") is None or
                observed.get("two_factor_research_50") is None or
                not math.isclose(earnings,observed["earnings_research_25"],
                                 abs_tol=0.000003) or
                not math.isclose(price+earnings,observed["two_factor_research_50"],
                                 abs_tol=0.000003)):
            raise ValueError("EARLY_WATCH_FINANCIAL_NOT_MARKET_VERIFIED")
        # Independent sector comparison ≠ business moat nor 20pt industry score.
        if earnings is not None:
            tier=TIERS[0]
        elif flow is not None:
            tier=TIERS[1]
        elif observed["price_top20_watch_rank"] is not None:
            tier=TIERS[2]
        else:
            tier=TIERS[3]
        quality=sum(values[k] is not None for k in values)
        if any(values[k] is not None for k in ("industry","competitiveness")):
            # This queue explicitly cannot treat unreviewed industry and moat
            # research as certified full evidence.
            raise ValueError("EARLY_WATCH_UNSUPPORTED_SECTOR_SCORE")
        tier_counts[tier]+=1
        sort_signal=(price+earnings if earnings is not None
                     else price+flow if flow is not None else price)
        if not math.isfinite(sort_signal):
            raise ValueError("EARLY_WATCH_SIGNAL_NONFINITE")
        rows={
            "security_id":code,
            "name":observed["name"],
            "venue":observed["venue"],
            "market_session":market["market_session"],
            "watch_tier":tier,
            "price_strength_25":price,
            "earnings_research_25":earnings,
            "flow_research_10":flow,
            "partial_observed_total":round(sum(v for v in values.values()
                                               if v is not None),6),
            "observed_component_count":quality,
            "observed_industry_code":observed["industry_code"],
            "industry_and_competitive_score_20_available":False,
            "industry_sample_growth_is_entire_industry":False,
            "independent_competitive_moat_verified":False,
            **{field:(peer_context.get(code) or {}).get(field) for field in (
                "industry_sample_peer_count",
                "industry_sample_revenue_growth_median_pct",
                "company_revenue_growth_pct",
                "company_revenue_growth_vs_peers_pp",
                "industry_sample_operating_growth_median_pct",
                "company_operating_growth_pct",
                "company_operating_growth_vs_peers_pp")},
            "observed_same_industry_revenue_rank":
                observed.get("peer_revenue_yoy_rank"),
            "observed_same_industry_revenue_denominator":
                observed.get("peer_revenue_yoy_denominator"),
            "missing_for_5factor":[k for k in
                ("industry","competitiveness","earnings","momentum","flow")
                if values[k] is None],
            "historically_certified_industry":False,
            "issuer_pit_certified":False,
            "investment_rank":None,
            "eligible_to_order":False,
        }
        if dart_cfs_capture_root is not None:
            from .dart_profitability_watch import RESEARCH_SOURCE
            # Actual annual consolidated statement source only; N/A remains
            # when the original is not available for this exact company.
            cfs=profitability.get(code)
            if cfs is not None:
                cfs_first=datetime.fromisoformat(cfs["dart_cfs_first_received_at_utc"])
                if (cfs_first.tzinfo is None or
                        cfs_first.astimezone(timezone.utc)>now or
                        cfs["dart_cfs_independent_pit_certified"] is not False):
                    raise ValueError("EARLY_WATCH_DART_FUTURE_OR_UNVERIFIED")
            for key in ("dart_latest_cfs_business_year","dart_cfs_revenue_krw",
                        "dart_cfs_operating_income_krw","dart_cfs_net_income_krw",
                        "dart_cfs_operating_margin_pct","dart_cfs_net_margin_pct",
                        "dart_cfs_first_receipt_sha256","dart_cfs_first_received_at_utc",
                        "dart_cfs_issuer_corp_code","dart_cfs_margin_source",
                        "dart_previous_cfs_business_year",
                        "dart_previous_cfs_operating_margin_pct",
                        "dart_previous_cfs_net_margin_pct",
                        "dart_cfs_operating_margin_change_pp",
                        "dart_cfs_net_margin_change_pp",
                        "dart_cfs_operating_margin_positive_two_years",
                        "dart_cfs_previous_first_receipt_sha256",
                        "dart_cfs_previous_first_received_at_utc",
                        "dart_cfs_two_year_comparable"):
                rows[key]=cfs.get(key) if cfs is not None else None
            rows["dart_cfs_independent_pit_certified"]=False
            rows["competitive_advantage_score_20"]=None
        entries.append((TIERS.index(tier),-sort_signal,-price,code,rows))
    entries.sort(key=lambda x:x[:4])
    selections=[entry[-1] for entry in entries[:top]]
    for index,record in enumerate(selections,1):
        record["review_priority_position"]=index
    if not selections:
        return {"status":"EARLY_WATCH_NO_OBSERVABLE_STOCKS",
                "watch_candidates":0,"orders_enabled":False,
                "external_api_calls":0}
    payload={
        "schema":SCHEMA,"market":"KR",
        "source_market_session":market["market_session"],
        "source_marketwide_sha256":market["content_sha256"],
        "source_factor_assessment_sha256":factor["content_sha256"],
        "source_first_assessed_at_utc":asof.isoformat(),
        "watch_published_at_utc":now.isoformat(),
        "candidate_tiers_order":list(TIERS),
        "sector_peer_context_method":SECTOR_CONTEXT,
        "tier_available_counts":tier_counts,
        "eligible_price_factor_candidates":len(entries),
        "review_candidates":len(selections),
        "requested_top":top,
        "sector_peer_comparable_in_watch":sum(
            r["industry_sample_peer_count"] is not None for r in selections),
        "company_operating_peer_comparable_in_watch":sum(
            r["company_operating_growth_vs_peers_pp"] is not None for r in selections),
        "review_queue":selections,
        "receiver_project":None,
        "receiver_neutral":True,
        "watch_only":True,
        "formal_leader_selection_count":0,
        "selected_candidates":[],
        "state_changes":[],
        "historical_independent_pit_certified":False,
        "investment_priority_certified":False,
        "external_api_calls":0,
        "order_instruction":False,
        "execution_authority":False,
        "orders_enabled":False,
    }
    if market.get("financial_cache_refreshed") is False:
        payload["cached_financial_source_market_session"]=market["cached_financial_source_market_session"]
        payload["cached_financial_available_at_utc"]=market["cached_financial_available_at_utc"]
        payload["financial_cache_refreshed"]=False
    if dart_cfs_capture_root is not None:
        from .dart_profitability_watch import RESEARCH_SOURCE
        payload["dart_profitability_method"]=RESEARCH_SOURCE
        payload["dart_profitability_companies_in_watch"]=sum(
            r["dart_cfs_operating_margin_pct"] is not None or
            r["dart_cfs_net_margin_pct"] is not None for r in selections)
        payload["dart_profitability_originals_available"]=len(profitability)
        payload["dart_two_year_margin_comparable_in_watch"]=sum(
            r["dart_cfs_operating_margin_change_pp"] is not None
            for r in selections)
    payload["content_sha256"]=sha256(canonical(payload)).hexdigest()
    return payload


def _html(doc:dict)->bytes:
    head=('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1">'
          '<title>EraLeader · 대장주 후보 관찰 우선목록</title>'
          '<style>body{max-width:1280px;margin:20px auto;padding:0 14px;'
          'font:14px system-ui,sans-serif;line-height:1.5}'
          'table{border-collapse:collapse;min-width:850px}th,td{padding:8px;'
          'border-bottom:1px solid #aaa;text-align:left}.scroll{overflow-x:auto}'
          '.note{padding:12px;border-left:4px solid #986;background:#aaa1}</style>'
          '</head><body><h1>한국 대장주 후보 관찰 작업목록</h1>'
          '<p class="note">실제 확보된 가격·실적·수급 관측자료의 검토 순서입니다. '
          'A/B/C/D 그룹 간 점수·순위는 직접 비교되지 않으며 시장의 '
          '투자1~50위나 공식 대장주 확정이 아닙니다. 산업 성장·경쟁력 '
          '성장률은 확인된 일부 DART 기업의 세부업종 표본 중간값일 뿐 업종 전체가 아닙니다. '
          '회사 실적 우위는 경쟁우위·해자 인증이 아닙니다. '
          '역사 PIT·기업행동 미인증. 직접 매매주문과 연결하지 않습니다.</p>'
          '<p>KRX 기준일 '+escape(doc["source_market_session"])
          +' · 우선 검토 '+str(doc["review_candidates"])
          +'종목 · 관측 가능 '+str(doc["eligible_price_factor_candidates"])
          +'종목 · 5요소 정식 선정 0 · 주문 0</p>'
          '<div class="scroll"><table><thead><tr>'+''.join(
              "<th>"+x+"</th>" for x in (
                  "검토순","종목","코드","그룹","가격25","실적25",
                  "수급연구10","동업종 매출순위","업종표본 수",
                  "업종표본 매출성장 중간(%)","회사 매출성장(%)",
                  "동업종표본 대비 매출(pp)","동업종표본 대비 영업익(pp)",
                  "미확보 요소"))+
          '</tr></thead><tbody>')
    cells=[]
    for row in doc["review_queue"]:
        peer= (f'{row["observed_same_industry_revenue_rank"]}/'
               f'{row["observed_same_industry_revenue_denominator"]}'
               if row["observed_same_industry_revenue_rank"] is not None
               else "N/A")
        vals=(row["review_priority_position"],row["name"],row["security_id"],
              row["watch_tier"],row["price_strength_25"],
              row["earnings_research_25"],row["flow_research_10"],
              peer,row["industry_sample_peer_count"],
              row["industry_sample_revenue_growth_median_pct"],
              row["company_revenue_growth_pct"],
              row["company_revenue_growth_vs_peers_pp"],
              row["company_operating_growth_vs_peers_pp"],
              ",".join(row["missing_for_5factor"]))
        cells.append('<tr>'+''.join(
            '<td>'+escape("N/A" if v is None else str(v))+'</td>'
            for v in vals)+'</tr>')
    profitability_html=""
    if doc.get("dart_profitability_method") is not None:
        profitability_html=(
            '<h2>DART 연결재무 실적 수익성 관찰 (경쟁력 점수 아님)</h2>'
            '<p>연결재무제표의 최근 연간 매출액 대비 영업이익·순이익 비율입니다. '
            'ROIC·시장점유율·지속적 경쟁우위/기업해자 점수가 아닙니다. '
            '최초 로컬 수신시각 이전 판단에 소급 사용하지 않습니다.</p>'
            '<div class="scroll"><table><thead><tr><th>종목</th><th>회계연도</th>'
            '<th>영업이익률(%)</th><th>전년도 영업이익률(%)</th>'
            '<th>영업이익률 변화(pp)</th><th>2년 연속 영업흑자율</th>'
            '<th>순이익률(%)</th><th>순이익률 변화(pp)</th><th>원본 수신 UTC</th>'
            '</tr></thead><tbody>'+''.join(
                '<tr>'+''.join('<td>'+escape("N/A" if x is None else str(x))+'</td>'
                for x in (r["security_id"],r["dart_latest_cfs_business_year"],
                          r["dart_cfs_operating_margin_pct"],
                          r.get("dart_previous_cfs_operating_margin_pct"),
                          r.get("dart_cfs_operating_margin_change_pp"),
                          r.get("dart_cfs_operating_margin_positive_two_years"),
                          r["dart_cfs_net_margin_pct"],
                          r.get("dart_cfs_net_margin_change_pp"),
                          r["dart_cfs_first_received_at_utc"]))+'</tr>'
                for r in doc["review_queue"])+'</tbody></table></div>')
    cache_note=""
    if doc.get("financial_cache_refreshed") is False:
        cache_note=('<p>가격은 KRX 기준일로 갱신했습니다. 재무·업종은 기존 검증 캐시 '
                    +escape(doc["cached_financial_source_market_session"])
                    +' 관측본을 재사용하며 신규 공시 반영은 아닙니다. 다른 날짜 수급은 N/A입니다.</p>')
    return (head+''.join(cells)+'</tbody></table></div>'+cache_note+profitability_html+
            '<p>후속 매매전략에 보내는 자료도 WATCH 연구 전용이며 '
            '선정·주문권한·실거래 매수가·매도가를 포함하지 않습니다.</p>'
            '</body></html>').encode("utf-8")


def _validated(path:Path,*,clock=None)->dict:
    now=_clock(clock)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not path.is_file() or path.stat().st_size>4_000_000):
        raise ValueError("EARLY_WATCH_UNSAFE_SAVED_FILE")
    b=path.read_bytes()
    doc=json.loads(b)
    if type(doc) is not dict or b!=canonical(doc)+b"\n":
        raise ValueError("EARLY_WATCH_NONCANONICAL")
    unsigned=dict(doc)
    witness=unsigned.pop("content_sha256",None)
    instant=datetime.fromisoformat(doc["watch_published_at_utc"])
    if (witness!=sha256(canonical(unsigned)).hexdigest()
            or doc.get("schema")!=SCHEMA or doc.get("market")!="KR"
            or doc.get("receiver_project") is not None
            or doc.get("receiver_neutral") is not True
            or doc.get("watch_only") is not True
            or doc.get("formal_leader_selection_count")!=0
            or doc.get("selected_candidates")!=[]
            or doc.get("state_changes")!=[]
            or doc.get("orders_enabled") is not False
            or doc.get("order_instruction") is not False
            or doc.get("execution_authority") is not False
            or doc.get("investment_priority_certified") is not False
            or doc.get("sector_peer_context_method")!=SECTOR_CONTEXT
            or doc.get("dart_profitability_method") not in (None,
                 "DART_CFS_ANNUAL_ORIGINAL_PROFIT_MARGIN_NOT_MOAT_V1",
                 "DART_CFS_ANNUAL_TWO_YEAR_MARGIN_TREND_NOT_MOAT_V2")
            or instant.tzinfo is None or instant.astimezone(timezone.utc)>now):
        raise ValueError("EARLY_WATCH_VERSION_TAMPER_OR_AUTHORITY")
    rows=doc.get("review_queue")
    if (type(rows) is not list or
            not 1<=len(rows)<=MAX_WATCH
            or len(rows)!=doc.get("review_candidates") or
            len({r["security_id"] for r in rows})!=len(rows)):
        raise ValueError("EARLY_WATCH_WRONG_ROWS")
    for i,row in enumerate(rows,1):
        if (row.get("review_priority_position")!=i or
                row.get("investment_rank") is not None or
                row.get("eligible_to_order") is not False or
                type(row.get("security_id")) is not str or
                not re.fullmatch(r"[A-Z0-9]{6}",row["security_id"]) or
                row.get("watch_tier") not in TIERS or
                row.get("industry_and_competitive_score_20_available") is not False or
                row.get("industry_sample_growth_is_entire_industry") is not False or
                row.get("independent_competitive_moat_verified") is not False):
            raise ValueError("EARLY_WATCH_ROW_AUTHORITY_INVALID")
    if doc.get("dart_profitability_method") is not None:
        cfs_count=0
        for row in rows:
            if (row.get("competitive_advantage_score_20") is not None or
                    row.get("dart_cfs_independent_pit_certified") is not False):
                raise ValueError("EARLY_WATCH_DART_MOAT_UNVERIFIED")
            if row.get("dart_cfs_operating_margin_pct") is not None or row.get("dart_cfs_net_margin_pct") is not None:
                cfs_count+=1
                if (type(row.get("dart_latest_cfs_business_year")) is not int or
                        type(row.get("dart_cfs_issuer_corp_code")) is not str or
                        not re.fullmatch(r"[0-9]{8}",row["dart_cfs_issuer_corp_code"]) or
                        type(row.get("dart_cfs_first_receipt_sha256")) is not str or
                        not re.fullmatch(r"[a-f0-9]{64}",row["dart_cfs_first_receipt_sha256"])):
                    raise ValueError("EARLY_WATCH_DART_EVIDENCE_INVALID")
                observed=datetime.fromisoformat(row["dart_cfs_first_received_at_utc"])
                if observed.tzinfo is None or observed.astimezone(timezone.utc)>instant:
                    raise ValueError("EARLY_WATCH_DART_FUTURE_RECEIPT")
        if cfs_count!=doc.get("dart_profitability_companies_in_watch"):
            raise ValueError("EARLY_WATCH_DART_COMPANY_COUNT_MISMATCH")
        if doc["dart_profitability_method"].endswith("_V2"):
            two_years=0
            for row in rows:
                previous_pin=row.get("dart_cfs_previous_first_receipt_sha256")
                current_margin=row.get("dart_cfs_operating_margin_pct")
                previous_margin=row.get("dart_previous_cfs_operating_margin_pct")
                delta=row.get("dart_cfs_operating_margin_change_pp")
                if previous_pin is not None:
                    if (type(previous_pin) is not str
                            or not re.fullmatch(r"[a-f0-9]{64}",previous_pin)
                            or row.get("dart_previous_cfs_business_year")
                               !=row.get("dart_latest_cfs_business_year",0)-1
                            or row.get("dart_cfs_two_year_comparable") is not True):
                        raise ValueError("EARLY_WATCH_DART_PREVIOUS_RECEIPT_INVALID")
                    available=datetime.fromisoformat(
                        row["dart_cfs_previous_first_received_at_utc"])
                    if available.tzinfo is None or available.astimezone(timezone.utc)>instant:
                        raise ValueError("EARLY_WATCH_DART_PREVIOUS_FUTURE")
                elif row.get("dart_cfs_two_year_comparable") not in (False,None):
                    raise ValueError("EARLY_WATCH_DART_PREVIOUS_MISSING")
                if delta is not None:
                    if (type(delta) not in (float,int) or
                            type(previous_margin) not in (float,int) or
                            type(current_margin) not in (float,int) or
                            round(current_margin-previous_margin,4)!=delta):
                        raise ValueError("EARLY_WATCH_DART_MARGIN_CHANGE_INVALID")
                    two_years+=1
            if doc.get("dart_two_year_margin_comparable_in_watch")!=two_years:
                raise ValueError("EARLY_WATCH_DART_TWO_YEAR_COUNT")
    return doc


def publish_early_watch(*,marketwide:Path,project:Path,
                        factor_input:Path,top:int=50,
                        clock:datetime|None=None,
                        dart_cfs_capture_root:Path|None=None)->dict:
    now=_clock(clock)
    payload=create_early_watch(
        marketwide=marketwide,project=project,
        factor_input=factor_input,top=top,clock=clock,
        dart_cfs_capture_root=dart_cfs_capture_root)
    if payload.get("status") in (
            "EARLY_WATCH_STALE_MARKET_HOLD",
            "EARLY_WATCH_NO_OBSERVABLE_STOCKS"):
        return payload
    output=_owned_output(project)
    folder=output/FOLDER
    if folder.is_symlink():
        raise ValueError("EARLY_WATCH_OUTPUT_LINKED")
    folder.mkdir(mode=0o700,exist_ok=True)
    version=sha256(canonical({
        "market":payload["source_marketwide_sha256"],
        "factor":payload["source_factor_assessment_sha256"],
        "top":payload["requested_top"],
        "peer_method":SECTOR_CONTEXT,
        **({"profitability_method":payload["dart_profitability_method"],
            "receipts":[((r["security_id"],r["dart_cfs_first_receipt_sha256"],
                          r.get("dart_cfs_previous_first_receipt_sha256"))
                         if payload["dart_profitability_method"].endswith("_V2")
                         else (r["security_id"],r["dart_cfs_first_receipt_sha256"]))
                        for r in payload["review_queue"]]}
           if payload.get("dart_profitability_method") is not None else {}),
    })).hexdigest()[:16]
    destination=folder/("KR_"+payload["source_market_session"].replace("-","")
                        +"_"+version)
    manifest=canonical(payload)+b"\n"
    html=_html(payload)
    if destination.is_symlink():
        raise ValueError("EARLY_WATCH_VERSION_LINKED")
    if destination.exists():
        if (not destination.is_dir() or
                (destination/"watch_queue.json").is_symlink() or
                (destination/"index.html").is_symlink()):
            raise ValueError("EARLY_WATCH_VERSION_CONFLICT")
        earlier=_validated(destination/"watch_queue.json",clock=now)
        new_core=dict(payload)
        previous_core=dict(earlier)
        for candidate in (new_core,previous_core):
            candidate.pop("content_sha256",None)
            candidate.pop("watch_published_at_utc",None)
        if (new_core!=previous_core or
                (destination/"index.html").read_bytes()!=_html(earlier)):
            raise ValueError("EARLY_WATCH_VERSION_CONFLICT")
        state="ALREADY_PUBLISHED"
    else:
        stage=Path(tempfile.mkdtemp(prefix=".earlywatch_",dir=folder))
        try:
            os.chmod(stage,0o700)
            for file,b in (("watch_queue.json",manifest),("index.html",html)):
                fd=os.open(stage/file,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,"wb") as stream:
                    stream.write(b);stream.flush();os.fsync(stream.fileno())
            # Do not re-label a revised original or factor input as one
            # unchanged research edition after publication.
            source_again,_=_source(marketwide)
            factors_again=_read_assessment(factor_input)
            if (source_again["content_sha256"]!=payload["source_marketwide_sha256"]
                    or factors_again["content_sha256"]!=payload["source_factor_assessment_sha256"]):
                raise ValueError("EARLY_WATCH_SOURCE_CHANGED")
            if destination.exists() or destination.is_symlink():
                raise ValueError("EARLY_WATCH_PUBLICATION_RACE")
            os.rename(stage,destination)
        finally:
            if stage.exists():shutil.rmtree(stage)
        state="PUBLISHED"
    return {
        "status":state,
        "source_market_session":payload["source_market_session"],
        "observed_candidates":payload["eligible_price_factor_candidates"],
        "watch_queue_count":payload["review_candidates"],
        "tier_counts":payload["tier_available_counts"],
        "manifest":str(destination/"watch_queue.json"),
        "site":str(destination/"index.html"),
        "consumer_project":None,
        "receiver_neutral":True,
        "official_leaders":0,"orders":0,"external_api_calls":0,
    }
