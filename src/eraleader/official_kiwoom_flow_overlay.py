"""Read-only Kiwoom flow overlay for the existing DART price/earnings/industry sample.

Missing or unobserved investor flow remains N/A. Never modifies current
PRICE WATCH20 ranking, first-received stock records or investment decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json

from .delivery import BASE_CSS
from .kiwoom_investor_flow import canonical, utc, verify_flow

BASIC = "eraleader.official_basic_discovery_candidates.v1"
INDUSTRY = "eraleader.official_dart_industry_peer_research.v1"
SCHEMA = "eraleader.official_kiwoom_flow_overlay.v1"


def _verify_report(obj: dict, schema: str) -> None:
    if type(obj) is not dict:
        raise ValueError("Research evidence must be a JSON object")
    data = dict(obj)
    pin = data.pop("content_sha256", None)
    if pin != sha256(canonical(data)).hexdigest() or data.get("schema") != schema:
        raise ValueError("Price/financial/sector original SHA invalid")


def build_overlay(basic: dict, industry: dict, *,
                  flows: dict[str, dict], decision_at: datetime | None = None) -> dict:
    _verify_report(basic, BASIC)
    _verify_report(industry, INDUSTRY)
    now = decision_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Flow sidecar requires aware decision timestamp")
    now = now.astimezone(timezone.utc)
    if (utc(basic["decision_at_utc"]) > now or utc(industry["as_of_utc"]) > now
            or industry["baseline_candidate_sha256"] != basic["content_sha256"]
            or basic.get("official_future_leaders") != 0
            or basic.get("full_ranked_investment_priority_available") is not False
            or industry.get("historic_sector_pit_certified") is not False
            or industry.get("official_leaders") != 0):
        raise ValueError("Cannot replace official investment ranks or backdate evidence")
    candidates = basic["comparisons"]
    peers = {r["stock_code"]: r for r in industry["companies"]}
    ids = {r["security_id"] for r in candidates}
    if (len(ids) != len(candidates) or set(peers) != ids or
            type(flows) is not dict or not set(flows).issubset(ids)):
        raise ValueError("Flow must cover a subset of the unchanged actual DART cohort")
    observed = []
    for firm in candidates:
        code = firm["security_id"]
        sector = peers[code]
        if sector["name"] != firm["name"] or sector["return_3m"] != firm["return_3m"]:
            raise ValueError("Sector/price issuer identity mismatch")
        report = flows.get(code)
        status = "NOT_CONFIGURED_OR_NOT_RECEIVED"
        w5 = {"foreign_net_shares": None, "institution_net_shares": None,
              "combined_net_shares": None}
        w20 = dict(w5)
        receipt = None
        if report is not None:
            verify_flow(report, decision_at=now)
            if report["security_id"] != code:
                raise ValueError("Investor flow cannot be applied to another issue")
            receipt = report["source_first_locally_received_at_utc"]
            # A different observed session must not be reported as today's flow.
            if report["requested_day"] != basic["market_session"]:
                status = "FLOW_SESSION_MISMATCH_NOT_USABLE"
            elif report["latest_observed_day"] != basic["market_session"]:
                status = "FLOW_MARKET_DAY_MISSING"
            else:
                status = "FLOW_PARTIAL_RESEARCH"
                w5 = report["flow_5_observed_sessions"]
                w20 = report["flow_20_observed_sessions"]
                if w20["combined_net_shares"] is not None:
                    status = "FLOW_20_OBSERVATIONS_RESEARCH_ONLY"
        observed.append({
            "security_id": code, "name": firm["name"],
            "existing_basic_comparison_order": firm["comparison_order"],
            "current_industry_division": sector["industry_division_code"],
            "price_strength_25": firm["price_strength_25"],
            "revenue_yoy": firm["revenue_yoy"],
            "operating_income_yoy": firm["operating_income_yoy"],
            "flow_status": status,
            "institution_net_5_observed_shares": w5["institution_net_shares"],
            "foreign_net_5_observed_shares": w5["foreign_net_shares"],
            "combined_net_5_observed_shares": w5["combined_net_shares"],
            "institution_net_20_observed_shares": w20["institution_net_shares"],
            "foreign_net_20_observed_shares": w20["foreign_net_shares"],
            "combined_net_20_observed_shares": w20["combined_net_shares"],
            "flow_first_locally_received_at_utc": receipt,
            "official_total_score_100": None,
            "investable_rank": None, "official_leader": False,
        })
    result = {
        "schema": SCHEMA, "market": "KR",
        "market_session": basic["market_session"],
        "research_decision_at_utc": now.isoformat(),
        "basic_candidates_sha256": basic["content_sha256"],
        "industry_peers_sha256": industry["content_sha256"],
        "selected_companies": len(observed),
        "kiwoom_flow_received_companies": len(flows),
        "usable_5_observation_flow_companies": sum(
            r["combined_net_5_observed_shares"] is not None for r in observed),
        "usable_20_observation_flow_companies": sum(
            r["combined_net_20_observed_shares"] is not None for r in observed),
        "comparisons": observed,
        "official_leaders": 0, "investment_priority_ranked": False,
        "historical_investor_flow_pit_certified": False,
        "limitations": [
            "5/20 counts refer to available dated observations, not independent exchange-calendar continuity.",
            "Kiwoom first local receipt is not historical public availability certification.",
            "Only selected DART CFS companies shown: not a full-market institution-flow census.",
            "Flow is net BUY quantity in SHARES, not KRW; no price-scaled percent or net value is inferred.",
            "Institution/foreign money can be a coincident or reversed signal; not independent buy advice.",
        ],
    }
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    return result


def render_overlay(report: dict) -> str:
    _verify_report(report, SCHEMA)
    if report.get("official_leaders") != 0 or report.get("investment_priority_ranked") is not False:
        raise ValueError("Sidecar cannot be portrayed as investment priority")
    x = lambda value: escape("N/A" if value is None else str(value), quote=True)
    num = lambda v: "N/A" if v is None else f"{v:+,d}"
    pct = lambda v: "N/A" if v is None else f"{v:+.1%}"
    rows = []
    for r in report["comparisons"]:
        cells = [
            r["existing_basic_comparison_order"], r["security_id"], r["name"],
            r["current_industry_division"], pct(r["revenue_yoy"]),
            pct(r["operating_income_yoy"]), x(r["price_strength_25"]),
            num(r["foreign_net_5_observed_shares"]),
            num(r["institution_net_5_observed_shares"]),
            num(r["foreign_net_20_observed_shares"]),
            num(r["institution_net_20_observed_shares"]),
            r["flow_status"],
        ]
        rows.append("<tr>" + "".join("<td>"+x(v)+"</td>" for v in cells)+"</tr>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 한국 후보 수급 검증</title><style>"+BASE_CSS+"</style></head>"
        "<body><header><h1>EraLeader · 기관·외국인 수급 비교</h1>"
        "<nav><a href='index.html'>메인</a> · <a href='basic_candidates_kr.html'>기존 실적·가격</a>"
        " · <a href='industry_peers_kr.html'>기존 업종 비교</a>"
        " · <a href='http://127.0.0.1:8782/'>키움 모의/실전 API 설정</a></nav></header>"
        "<main><div class='note'><b>연구용 참고 화면 — 투자 1~20위가 아닙니다.</b><br>"
        "키움증권 ka10059 공식 수급이 실제 수신된 종목만 주식 수량 기준으로 표시합니다."
        " 미수신/일자 불일치/5·20 관측행 결손은 N/A, 0으로 대체하지 않습니다.</div>"
        "<p>KRX 관측 거래일 "+x(report["market_session"])+" / 이 화면 판정 UTC "
        +x(report["research_decision_at_utc"])+"</p>"
        "<div class='stats'><div class='stat'>기존 재무 후보<br><strong>"+
        x(report["selected_companies"])+"</strong></div><div class='stat'>수급 수신 회사<br><strong>"+
        x(report["kiwoom_flow_received_companies"])+"</strong></div>"
        "<div class='stat'>20관측 수급 가능<br><strong>"+
        x(report["usable_20_observation_flow_companies"])+"</strong></div></div>"
        "<div class='wrap'><table><thead><tr><th>기존 비교순서</th><th>종목</th><th>회사</th>"
        "<th>업종</th><th>매출 YoY</th><th>영업익 YoY</th><th>주가강도 /25</th>"
        "<th>외국인 5관측(주)</th><th>기관 5관측(주)</th>"
        "<th>외국인 20관측(주)</th><th>기관 20관측(주)</th><th>수급 상태</th>"
        "</tr></thead><tbody>"+"".join(rows)+"</tbody></table></div>"
        "<p><small>개별 매매동향은 순매수 수량이며 금액이나 수익률이 아닙니다."
        " 5/20 관측은 거래소 독립 캘린더 인증 전 임시 연구 집계입니다."
        " 실물 키움 API 인증 및 20거래일 발굴 적중률은 별도 검증이 필요합니다.</small></p>"
        "</main><footer>EraLeader · 실전 주문 0 · 정식 대장주 판정 N/A</footer></body></html>"
    )
