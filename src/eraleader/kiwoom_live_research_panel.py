"""Read-only live Kiwoom research panel separate from earlier KRX/DART sessions.

The live selected-stock mock API can be fresher than the existing DART cohort.
The two are never joined into a leader score or backdated to earlier sessions.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re

from .kiwoom_investor_flow import canonical, utc, verify_flow
from .official_kiwoom_flow_overlay import build_overlay, BASE_CSS

SCHEMA = "eraleader.kiwoom_live_observation_sidecar.v1"

def clean_session(value: str) -> str:
    if type(value) is not str:
        raise ValueError("Invalid market session")
    if re.fullmatch(r"[0-9]{8}", value):
        d=date(int(value[:4]),int(value[4:6]),int(value[6:8]))
    elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        d=date.fromisoformat(value)
    else:
        raise ValueError("Invalid market session")
    return d.strftime("%Y%m%d")

def make_panel(basic: dict, industries: dict, *,
               flows: dict[str,dict], decision_at: datetime | None=None) -> dict:
    stamp=decision_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Timezone-aware decision timestamp required")
    stamp=stamp.astimezone(timezone.utc)
    # Validate original first SHA references and unchanged issuer ordering via
    # the existing official read-only overlay verifier (no flows joined).
    neutral=build_overlay(basic,industries,flows={},decision_at=stamp)
    base_session=clean_session(neutral["market_session"])
    if type(flows) is not dict:
        raise ValueError("Investor flow map required")
    candidates={x["security_id"]:x for x in neutral["comparisons"]}
    if len(candidates)!=len(neutral["comparisons"]) or not flows or not set(flows).issubset(candidates):
        raise ValueError("Flow issuer not in original fixed cohort")
    entries=[]
    for code,report in sorted(flows.items()):
        if type(report) is not dict:
            raise ValueError("Invalid original flow report")
        verify_flow(report, decision_at=stamp)
        if report.get("security_id")!=code or report.get("environment_mode")!="demo":
            raise ValueError("Identity or demo environment mismatch")
        source_session=clean_session(report.get("requested_day"))
        if source_session > stamp.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"):
            raise ValueError("Future live market session not yet available")
        latest=report.get("latest_observed_day")
        if latest is not None and clean_session(latest)>source_session:
            raise ValueError("Flow latest session after requested day")
        if utc(report["source_first_locally_received_at_utc"]) > stamp:
            raise ValueError("Flow not available at panel decision time")
        matched=source_session==base_session
        # Only selected live net SHARE counts; never baseline monetary flow
        # and never a backfilled 2026-10-08 price/earnings feature.
        w5=report.get("flow_5_observed_sessions",{})
        w20=report.get("flow_20_observed_sessions",{})
        valid=latest==report["requested_day"]
        entries.append({
            "security_id":code,"name":candidates[code]["name"],
            "environment_mode":"demo","baseline_market_session":base_session,
            "observed_flow_session":source_session,"baseline_session_equal":matched,
            "flow_status":("DEMO_FLOW_SESSION_MATCH_RESEARCH_ONLY" if matched
                           else "DEMO_FLOW_DIFFERENT_SESSION_NOT_JOINED"),
            "source_first_locally_received_at_utc":report["source_first_locally_received_at_utc"],
            "original_flow_sha256":report["content_sha256"],
            "provider_observations":report["observed_rows"],
            "historical_pagination_complete":report.get("historical_pagination_complete"),
            "foreign_net_5_shares":w5.get("foreign_net_shares") if valid else None,
            "institution_net_5_shares":w5.get("institution_net_shares") if valid else None,
            "foreign_net_20_shares":w20.get("foreign_net_shares") if valid else None,
            "institution_net_20_shares":w20.get("institution_net_shares") if valid else None,
            "score_eligible":False,"trade_signal":None,
        })
    obj={
        "schema":SCHEMA,"market":"KR","baseline_market_session":base_session,
        "decision_at_utc":stamp.isoformat(),
        "basic_candidates_sha256":basic["content_sha256"],
        "industry_peers_sha256":industries["content_sha256"],
        "baseline_candidate_count":len(candidates),
        "live_observed_security_count":len(entries),
        "observations":entries,
        "all_flow_same_session_as_baseline":all(e["baseline_session_equal"] for e in entries),
        "official_future_leaders":0,"investment_ranking_available":False,
        "historical_pit_certified":False,"orders_enabled":False,
        "mode":"demo","trade_signal":None,
        "disclaimer":"Mock server market response, research-only; no production-market confirmation.",
    }
    obj["content_sha256"]=sha256(canonical(obj)).hexdigest()
    return obj

def render_panel(report: dict) -> str:
    body=dict(report)
    pin=body.pop("content_sha256",None)
    if (pin!=sha256(canonical(body)).hexdigest() or
            body.get("schema")!=SCHEMA or
            body.get("mode")!="demo" or
            body.get("orders_enabled") is not False or
            body.get("official_future_leaders")!=0 or
            body.get("investment_ranking_available") is not False):
        raise ValueError("Research panel integrity/permissions invalid")
    name=lambda text:escape(str(text),quote=True)
    count=lambda x:"N/A" if x is None else f"{x:+,d}"
    cells=[]
    for line in report["observations"]:
        row=[line["security_id"],line["name"],line["observed_flow_session"],
             line["baseline_market_session"],line["environment_mode"],
             count(line["foreign_net_5_shares"]),count(line["institution_net_5_shares"]),
             count(line["foreign_net_20_shares"]),count(line["institution_net_20_shares"]),
             line["flow_status"]]
        cells.append("<tr>"+"".join("<td>"+name(v)+"</td>" for v in row)+"</tr>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader · 키움 당일 수급 연구</title><style>"+BASE_CSS+"</style></head>"
        "<body><header><h1>키움 모의투자 수급 · 실수신 연구</h1>"
        "<nav><a href='../index.html'>EraLeader 메인</a> · "
        "<a href='../investor_flow_kr.html'>기존 수급 N/A 연구</a></nav></header>"
        "<main><div class='note'><b>모의투자 서버 자료 · 매매/대장주 점수 사용 금지.</b>"
        "<br>KRX·DART 기존 가격/실적 기준일과 다를 경우 별도 관측치로만 보여줍니다."
        "<br>원시 수량은 주(share)이며 원화 금액이 아닙니다.</div>"
        "<p>기존 KRX·DART 기준일: "+name(report["baseline_market_session"])
        +" / 확인 시각(UTC): "+name(report["decision_at_utc"])+"</p>"
        "<div class='wrap'><table><thead><tr><th>주권</th><th>기존 기업명</th>"
        "<th>키움 수급일</th><th>기존 분석일</th><th>환경</th>"
        "<th>외국인 5관측(주)</th><th>기관 5관측(주)</th>"
        "<th>외국인 20관측(주)</th><th>기관 20관측(주)</th><th>연결 상태</th>"
        "</tr></thead><tbody>"+"".join(cells)+"</tbody></table></div>"
        "<p><small>서로 다른 기준일의 수급과 가격·실적을 합산하지 않았습니다. "
        "수급 데이터의 원래 최초 공개시각/PIT 인증·생산거래소 교차확인은 별도로 필요합니다. "
        "공식 대장주 0 · 거래/주문 0.</small></p></main></body></html>"
    )
