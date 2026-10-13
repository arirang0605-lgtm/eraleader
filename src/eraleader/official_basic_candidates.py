"""Price+earnings two-factor discovery shortlist from real KRX/DART receipts.

An observed cross-factor *research order*, never a full leader/investment rank.
Unavailable earnings, flow, industry or legal PIT data stay N/A. No zero fill.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os

from .delivery import BASE_CSS

SCHEMA="eraleader.official_basic_discovery_candidates.v1"


def _canonical(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode()


def _time(value):
    if type(value) is not str:
        raise ValueError("Original first-received evidence clock absent")
    obj=datetime.fromisoformat(value.replace("Z","+00:00"))
    if obj.tzinfo is None or obj.utcoffset() is None:
        raise ValueError("Unaware source receipt timestamp rejected")
    return obj.astimezone(timezone.utc)


def _number(value):
    if value is None:return None
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("Cannot interpret missing/nonfinite price or financial values")
    return float(value)


def build_basic_candidate_research(snapshot: dict, *, limit: int=20) -> dict:
    """Compare the real observed evidence population, never official 100 points."""
    if type(limit) is not int or not 1<=limit<=20:
        raise ValueError("Research candidate publication bounded to 20")
    if (snapshot.get("source_market")!="KR" or
            snapshot.get("classification_quality")!="PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("Only approved KR research-only snapshot input")
    ev=snapshot.get("official_api_evidence",{})
    if (ev.get("historic_universe_pit_verified") is not False or
            ev.get("issuer_share_class_verified") is not False or
            ev.get("official_leaders")!=0):
        raise ValueError("Uncertified leader promotion prohibited")
    decision=_time(ev["decision_at"])
    prices=snapshot.get("research_candidate_price_factors")
    finance=snapshot.get("official_financial_research_observations")
    if type(prices) is not list or type(finance) is not list or not finance:
        raise ValueError("Verified full-universe price and multi-company annual CFS required")
    if len(finance)>50 or len(prices)!=len(finance):
        raise ValueError("Financial/price observation list count mismatch")
    grouped={}
    for row in prices:
        key=row.get("security_id")
        if key in grouped or row.get("historic_issuer_class_pit_certified") is not False:
            raise ValueError("Duplicate/unverified source price identity")
        if row.get("observed_market_session")!=ev["api_observation_day"]:
            raise ValueError("Price session inconsistent with official trading day")
        grouped[key]=row
    out=[]
    seen=set()
    for firm in finance:
        code=firm.get("security_id")
        if code in seen or code not in grouped or not firm.get("name"):
            raise ValueError("Missing current DART annual evidence or price reference")
        seen.add(code)
        if (firm.get("formal_score_100") is not None or
                firm.get("official_leader") is not False or
                firm.get("historic_issuer_class_pit_certified") is not False):
            raise ValueError("Official rank not yet allowed")
        first=_time(firm["source_first_received_at_utc"])
        if first>decision:
            raise ValueError("Cannot publish future collected DART CFS")
        facts=firm.get("research_metrics")
        if type(facts) is not dict or set(facts)!={
                "revenue_yoy","operating_income_yoy","net_income_yoy"}:
            raise ValueError("Original financial YoY metrics must be explicit")
        p=grouped[code]
        sales=_number(facts["revenue_yoy"])
        operating=_number(facts["operating_income_yoy"])
        prev3m=_number(p.get("return_3m"))
        prev6m=_number(p.get("return_6m"))
        price25=_number(p.get("price_strength_25"))
        if price25 is not None and not 0<=price25<=25:
            raise ValueError("Price partial strength outside 25-point original scale")
        available=all(item is not None for item in (sales,operating,prev3m,price25))
        positive_count=sum((sales>0,operating>0,prev3m>0)) if available else None
        if positive_count is None:
            diagnosis="DATA_INCOMPLETE"
        elif positive_count==3:
            diagnosis="가격·매출·영업이익 동시 개선 관찰"
        else:
            diagnosis="세 지표 방향 불일치"
        obs={
            "security_id":code,"name":firm["name"],"venue":firm["venue"],
            "market_session":ev["api_observation_day"],
            "financial_year":firm["reported_financial_year"],
            "return_3m":prev3m,"return_6m":prev6m,
            "price_strength_25":price25,
            "all_observed_price_rank":p.get("price_market_rank"),
            "revenue_yoy":sales,"operating_income_yoy":operating,
            "net_income_yoy":_number(facts["net_income_yoy"]),
            "revenue_yoy_acceleration":(_number(
                (firm.get("research_acceleration") or {}).get("revenue_yoy_acceleration"))),
            "positive_concordance_of_three":positive_count,
            "observed_direction":diagnosis,
            "first_financial_locally_received_at_utc":first.isoformat(),
            "official_leader":False,"total_score_100":None,
            "investable_price_rank":None,"historical_pit_certified":False,
            "evidence_coverage":"PRICE_AND_CFS_RESEARCH_ONLY",
        }
        out.append(obs)
    ordered=sorted(out,key=lambda r:(
        r["positive_concordance_of_three"] is None,
        -(r["positive_concordance_of_three"] or 0),
        -(r["price_strength_25"] if r["price_strength_25"] is not None else -1),
        -(r["revenue_yoy"] if r["revenue_yoy"] is not None else -100),
        r["security_id"],
    ))
    for idx,row in enumerate(ordered,1):
        row["comparison_order"]=idx if idx<=limit else None
        row["eligible_for_official_100_point_model"]=False
    report={
        "schema":SCHEMA,"decision_at_utc":decision.isoformat(),
        "market_session":ev["api_observation_day"],
        "source_watch_run_id":snapshot.get("run_id"),
        "financial_companies_observed":len(out),
        "direction_fully_evaluable":sum(
            x["positive_concordance_of_three"] is not None for x in ordered),
        "jointly_improving_observations":sum(
            x["positive_concordance_of_three"]==3 for x in ordered),
        "display_limit":limit,
        "comparisons":ordered[:limit],
        "comparison_sorting":(
            "available sign concordance of 3 independent observations; "
            "then existing 25-point price strength; then annual revenue YoY"),
        "partial_research_screen_only":True,
        "full_ranked_investment_priority_available":False,
        "official_future_leaders":0,
        "future_leader_precision_certified":False,
        "limitations":[
            "Observed KRX trading day and downloaded financials have DIFFERENT availability times.",
            "Historical price cache and current DART corporate mapping are NOT issuer/class PIT certified.",
            "Not a full market census: only specifically captured companies can appear.",
            "Industry, institutional foreign flow, valuation and corporate-action PIT are N/A.",
            "No buy priority; sign direction is a hypothesis not statistically validated investment alpha.",
        ],
    }
    report["content_sha256"]=sha256(_canonical(report)).hexdigest()
    return report


def render_basic_candidates(report: dict) -> str:
    payload=dict(report)
    digest=payload.pop("content_sha256",None)
    if (payload.get("schema")!=SCHEMA or payload.get("official_future_leaders")!=0 or
            payload.get("full_ranked_investment_priority_available") is not False or
            payload.get("partial_research_screen_only") is not True or
            digest!=sha256(_canonical(payload)).hexdigest()):
        raise ValueError("Candidate research summary edited or improperly promoted")
    def x(s):
        return escape("N/A" if s is None else str(s),quote=True)
    def pct(s):
        return "N/A" if s is None else f"{100*s:+.1f}%"
    rows=[]
    for firm in report["comparisons"]:
        cells=[
            firm["comparison_order"],firm["security_id"],firm["name"],
            pct(firm["return_3m"]),pct(firm["return_6m"]),
            x(firm["price_strength_25"])+"/25" if firm["price_strength_25"] is not None else "N/A",
            pct(firm["revenue_yoy"]),pct(firm["operating_income_yoy"]),
            pct(firm["revenue_yoy_acceleration"]),
            firm["positive_concordance_of_three"],firm["observed_direction"],
        ]
        rows.append("<tr>"+"".join("<td>"+x(item)+"</td>" for item in cells)+"</tr>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 실제 실적·가격 후보 관찰</title><style>"+BASE_CSS+"</style>"
        "</head><body><header><h1>EraLeader · 기본 후보 관찰</h1>"
        "<nav><a href='index.html'>메인</a> · <a href='kr.html'>기존 가격 TOP20</a> "
        "· <a href='factor_readiness_kr.html'>실적 원본 데이터</a></nav></header>"
        "<main><div class='note'><b>실제 매수 1~20위가 아닙니다.</b><br>"
        "공식 DART 연간 실적과 KRX 가격을 동시에 가진 기업만 연구용으로 정렬합니다."
        " 산업·수급·기업행동/상폐 PIT·전시장 재무 확보 전에는 종합 100점/대장주 확정 N/A.</div>"
        "<p>가격 자료 거래일 "+x(report["market_session"])+" · 분석 판단시각 UTC "+
        x(report["decision_at_utc"])+"</p>"
        "<div class='stats'><div class='stat'>자료 연결 기업<br><strong>"+
        x(report["financial_companies_observed"])+"</strong></div>"
        "<div class='stat'>세 지표 비교 가능<br><strong>"+
        x(report["direction_fully_evaluable"])+"</strong></div>"
        "<div class='stat'>가격·매출·영업익 동시개선 관찰<br><strong>"+
        x(report["jointly_improving_observations"])+"</strong></div></div>"
        "<h2>다수 기업의 가격+실적 근거 비교 (연구용 관찰 순서)</h2>"
        "<div class='wrap'><table><thead><tr>"
        "<th>관찰 순서</th><th>종목</th><th>회사</th><th>3개월 주가</th>"
        "<th>6개월 주가</th><th>상대강도</th><th>매출 YoY</th>"
        "<th>영업익 YoY</th><th>매출성장 가속</th>"
        "<th>동일방향 신호 수</th><th>연구 판정</th>"
        "</tr></thead><tbody>"+"".join(rows)+"</tbody></table></div>"
        "<p><small>상대강도는 검증되지 않은 과거 로컬 가격 캐시가 포함됩니다."
        " 직전 연도 실적은 이번에 로컬 수신된 DART 원본이며, 거래일 당시 예측으로 소급하지 않습니다."
        " 이 목록은 일부 기업의 비교 표본이고 미래 대장주 적중률 N/A입니다.</small></p>"
        "</main><footer>EraLeader research only · 실거래 0 · 투자 우선순위 N/A</footer></body></html>"
    )


def write_basic_candidate_screen(report: dict, site: Path) -> tuple[Path,Path]:
    folder=Path(site)
    if folder.is_symlink() or not folder.is_dir() or any(p.is_symlink() for p in folder.parents):
        raise ValueError("Only existing nonlinked local site")
    content=render_basic_candidates(report).encode("utf-8")
    evidence=json.dumps(report,ensure_ascii=False,sort_keys=True,
                        indent=2,allow_nan=False).encode("utf-8")+b"\n"
    paths=[folder/"basic_candidates_kr.html",folder.parent/"basic_candidates_kr.json"]
    created=[]
    try:
        for path,data in zip(paths,[content,evidence]):
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            created.append(path)
            with os.fdopen(fd,"wb") as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
    except BaseException:
        for file in created:file.unlink(missing_ok=True)
        raise
    return tuple(paths)
