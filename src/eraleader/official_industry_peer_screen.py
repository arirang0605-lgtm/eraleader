"""Current DART industry-code peer comparisons for real KR price+CFS research.

Never infer a full industry from a hand-picked small sample. Ranks only among
the same-industry companies actually captured, with >=2 observed metrics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from statistics import mean
import json
import math
import re

from .delivery import BASE_CSS
from .official_dart_industry import verify_company_profile

SCHEMA="eraleader.official_dart_industry_peer_research.v1"
COHORT="eraleader.dart_industry_profile_cohort.v1"
BASIC="eraleader.official_basic_discovery_candidates.v1"
FIELDS=("revenue_yoy","operating_income_yoy","return_3m")
HEX=re.compile(r"[a-f0-9]{64}\Z")


def _canonical(item: object) -> bytes:
    return json.dumps(item,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _time(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("Source first received timestamp is mandatory")
    when=datetime.fromisoformat(value.replace("Z","+00:00"))
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Naive source availability is not reliable")
    return when.astimezone(timezone.utc)


def _num(raw: object) -> float | None:
    if raw is None:return None
    if type(raw) not in (int,float) or not math.isfinite(raw):
        raise ValueError("Nonfinite/missing peer metric cannot create false comparison")
    return float(raw)


def build_industry_peers(basic: dict, profile_manifest: dict, *,
                         originals: dict[str,Path],
                         directory: tuple[Path,str],
                         decision_at: datetime | None=None) -> dict:
    if (type(basic) is not dict or basic.get("schema")!=BASIC or
            type(profile_manifest) is not dict or
            profile_manifest.get("schema")!=COHORT or
            basic.get("full_ranked_investment_priority_available") is not False or
            basic.get("official_future_leaders")!=0 or
            profile_manifest.get("official_leaders")!=0 or
            profile_manifest.get("historic_industry_pit_certified") is not False or
            profile_manifest.get("current_classification_only") is not True):
        raise ValueError("Historical sector or investment status cannot be certified")
    canonical=dict(basic)
    witnessed=canonical.pop("content_sha256",None)
    if witnessed!=sha256(_canonical(canonical)).hexdigest():
        raise ValueError("Basic financial candidate SHA witness invalid")
    raw_now=decision_at or datetime.now(timezone.utc)
    if raw_now.tzinfo is None or raw_now.utcoffset() is None:
        raise ValueError("Industry peer as-of requires timezone")
    now=raw_now.astimezone(timezone.utc)
    if (_time(basic["decision_at_utc"])>now or
            _time(profile_manifest["decision_at_utc"])>now or
            profile_manifest.get("source_directory_sha256")!=directory[1]):
        raise ValueError("Current DART profile evidence not yet observed")
    companies=basic.get("comparisons")
    profiles=profile_manifest.get("companies")
    if (type(companies) is not list or type(profiles) is not list or
            not 2<=len(companies)<=20 or len(companies)!=len(profiles) or
            profile_manifest.get("companies_requested")!=len(profiles)):
        raise ValueError("Industry grouping requires identical selected financial cohort")
    identity={row["security_id"]:row for row in companies}
    if len(identity)!=len(companies):
        raise ValueError("Duplicate basic company profile identity")
    seen=set()
    observations=[]
    for ref in profiles:
        if type(ref) is not dict:
            raise ValueError("Invalid profile cohort row")
        code=ref.get("stock_code")
        if code in seen or code not in identity:
            raise ValueError("DART current industry cohort no longer matches financial cohort")
        seen.add(code)
        company=identity[code]
        if (company.get("official_leader") is not False or
                company.get("total_score_100") is not None or
                company.get("historical_pit_certified") is not False or
                company.get("investable_price_rank") is not None):
            raise ValueError("Cannot promote uncensored research or investment ranks")
        if ref.get("pit_certified") is not False or ref.get("status") not in (
                "PROFILE_NOT_CAPTURED","CURRENT_DART_COMPANY_INDUSTRY_RESEARCH_ONLY"):
            raise ValueError("Industry profile missing first source status or false historical PIT claim")
        if ref.get("status")=="PROFILE_NOT_CAPTURED":
            if (ref.get("first_receipt_sha256") is not None or
                    ref.get("current_dart_industry_code") is not None):
                raise ValueError("Missing profile must have no invented industry")
            sector=None
            first=None
        else:
            pin=ref.get("first_receipt_sha256")
            if type(pin) is not str or not HEX.fullmatch(pin) or pin not in originals:
                raise ValueError("Missing privately verified first DART company receipt")
            actual=verify_company_profile(originals[pin],pin,
                          directory=directory,decision_at=now)
            if (_time(actual["first_local_received_at_utc"])>now or
                    actual["stock_code"]!=code or
                    actual["current_dart_industry_code"]!=ref.get("current_dart_industry_code") or
                    actual["corp_code"]!=ref.get("corp_code") or
                    actual["first_local_received_at_utc"]!=ref.get("first_local_received_at_utc")):
                raise ValueError("DART industry profile contradicts original SHA")
            expected_class={"KOSPI":"Y","KOSDAQ":"K"}.get(company["venue"])
            if expected_class is None or actual["current_dart_listed_class"]!=expected_class:
                raise ValueError("DART current issuer listed class disagrees with KRX")
            sector=actual["current_dart_industry_code"]
            first=actual["first_local_received_at_utc"]
        observations.append({
            "stock_code":code,"name":company["name"],
            "current_industry_code":sector,
            "profile_first_received_at_utc":first,
            "financial_first_received_at_utc":company["first_financial_locally_received_at_utc"],
            "revenue_yoy":_num(company["revenue_yoy"]),
            "operating_income_yoy":_num(company["operating_income_yoy"]),
            "return_3m":_num(company["return_3m"]),
            "price_strength_25":_num(company["price_strength_25"]),
            "basic_observation_order":company["comparison_order"],
            "historic_sector_membership_pit_certified":False,
            "official_leader":False,"total_score_100":None,
        })
    groups={}
    for row in observations:
        row["industry_division_code"]=(
            row["current_industry_code"][:2] if row["current_industry_code"] else None)
        if row["industry_division_code"] is not None:
            groups.setdefault(row["industry_division_code"],[]).append(row)
    for code,peers in groups.items():
        for field in FIELDS:
            available=[row for row in peers if row[field] is not None]
            ranks={row["stock_code"]:idx+1 for idx,row in enumerate(
                sorted(available,key=lambda r:(-r[field],r["stock_code"])))}
            for row in peers:
                row[field+"_peer_position"]=(
                    ranks.get(row["stock_code"]) if len(available)>=2 else None)
                row[field+"_peer_denominator"]=len(available)
        for row in peers:
            row["peer_cohort_size"]=len(peers)
    for row in observations:
        if row["current_industry_code"] is None:
            row["peer_cohort_size"]=0
            for field in FIELDS:
                row[field+"_peer_position"]=None
                row[field+"_peer_denominator"]=0
    grouped=[]
    for code,rows in sorted(groups.items()):
        sales=[row["revenue_yoy"] for row in rows if row["revenue_yoy"] is not None]
        grouped.append({
            "industry_division_code":code,
            "exact_dart_industry_codes":sorted({r["current_industry_code"] for r in rows}),
            "selected_company_count":len(rows),
            "verified_revenue_yoy_count":len(sales),
            "selected_cohort_mean_revenue_yoy":round(mean(sales),8)
               if len(sales)>=2 else None,
            "official_entire_industry_growth":None,
            "official_pit_sector_leadership":False,
        })
    observations.sort(key=lambda row:(
        row["industry_division_code"] is None,
        -(row["peer_cohort_size"]),
        row["industry_division_code"] or "~",row["basic_observation_order"],
    ))
    report={
        "schema":SCHEMA,"market":"KR",
        "market_session":basic["market_session"],
        "baseline_candidate_sha256":witnessed,
        "profile_directory_first_sha256":directory[1],
        "as_of_utc":now.isoformat(),
        "selected_companies":len(observations),
        "verified_current_industries":len({
            row["current_industry_code"] for row in observations
            if row["current_industry_code"] is not None}),
        "verified_industry_divisions":len(groups),
        "selected_multi_company_peer_groups":sum(g["selected_company_count"]>=2
                                                   for g in grouped),
        "companies_with_real_peer":sum(r["peer_cohort_size"]>=2 for r in observations),
        "current_industry_groups":grouped,
        "companies":observations,
        "comparison_scope":"ONLY_THE_SELECTED_DART_KRX_RECEIPT_COHORT_TWO_DIGIT_DIVISIONS",
        "current_classification_only":True,
        "historic_sector_pit_certified":False,
        "official_industry_full_market_growth_ready":False,
        "full_investment_priority_ranking_ready":False,
        "official_leaders":0,"real_candidate_precision_certified":False,
        "limitations":[
            "Current OpenDART induty_code is NOT a historical KSIC industry membership reconstruction.",
            "Only selected 10 companies have DART first-received CFS and current industry; cannot extrapolate to 2765 issues.",
            "Two-digit KSIC DIVISION is a broad classification; same division does not prove direct competitors or identical businesses.",
            "At least 2 observed division peers are required for a research within-sample position; 1 peer is N/A.",
            "Selected-sample mean YoY is NOT official full-industry growth.",
            "Price cache corporate actions, historical listed class, news, institution flows and first official publication are not fully PIT certified.",
        ],
    }
    report["content_sha256"]=sha256(_canonical(report)).hexdigest()
    return report


def render_industry_peers(report: dict) -> str:
    body=dict(report)
    proof=body.pop("content_sha256",None)
    if (proof!=sha256(_canonical(body)).hexdigest() or
            body.get("schema")!=SCHEMA or
            body.get("historic_sector_pit_certified") is not False or
            body.get("full_investment_priority_ranking_ready") is not False or
            body.get("official_leaders")!=0):
        raise ValueError("DART industry comparison evidence SHA/leader promotion invalid")
    def x(value):
        return escape("N/A" if value is None else str(value),quote=True)
    def pct(value):
        return "N/A" if value is None else f"{100*value:+.1f}%"
    sectors="".join(
        "<tr><td>"+x(g["industry_division_code"])+"</td>"
        "<td>"+x(",".join(g["exact_dart_industry_codes"]))+"</td>"
        "<td>"+x(g["selected_company_count"])+"</td><td>"+
        pct(g["selected_cohort_mean_revenue_yoy"])+"</td>"
        "<td>미확보</td></tr>"
        for g in report["current_industry_groups"])
    companies=[]
    for row in report["companies"]:
        columns=[
            row["industry_division_code"],row["current_industry_code"],
            row["peer_cohort_size"],row["stock_code"],row["name"],
            pct(row["revenue_yoy"]),
            f'{row["revenue_yoy_peer_position"]}/{row["revenue_yoy_peer_denominator"]}'
              if row["revenue_yoy_peer_position"] else "N/A",
            pct(row["operating_income_yoy"]),
            f'{row["operating_income_yoy_peer_position"]}/{row["operating_income_yoy_peer_denominator"]}'
              if row["operating_income_yoy_peer_position"] else "N/A",
            pct(row["return_3m"]),
            f'{row["return_3m_peer_position"]}/{row["return_3m_peer_denominator"]}'
              if row["return_3m_peer_position"] else "N/A",
            row["profile_first_received_at_utc"],
        ]
        companies.append("<tr>"+"".join("<td>"+x(item)+"</td>" for item in columns)+"</tr>")
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 공식 DART 업종 동종기업 비교</title><style>"+BASE_CSS+"</style></head>"
        "<body><header><h1>EraLeader · 실제 업종별 동종기업 비교</h1>"
        "<nav><a href='index.html'>메인</a> · <a href='basic_candidates_kr.html'>기존 가격·실적 후보</a> "
        "· <a href='kr.html'>한국 가격 WATCH20</a></nav></header>"
        "<main><div class='note'><b>현재 DART 업종코드 기반 연구입니다. 정식 대장주·매수순위가 아닙니다.</b>"
        "<br>기업 업종코드는 현재 처음 수신한 기업 정보이며, 과거의 업종 소속을 증명하지 않습니다."
        " 비교는 KSIC 산업 대분류 앞 두 자리 기준입니다. 대분류가 같아도 직접 경쟁사가 아닐 수 있습니다."
        " 이번 표본에서 같은 대분류 기업이 2개 이상일 때만 비교하며, 업종 전체 순위는 아닙니다.</div>"
        "<div class='stats'><div class='stat'>업종코드 확인 그룹<br><strong>"+
        x(report["verified_current_industries"])+"</strong></div>"
        "<div class='stat'>2개 이상 대분류 비교 가능한 그룹<br><strong>"+
        x(report["selected_multi_company_peer_groups"])+"</strong></div>"
        "<div class='stat'>대분류 비교 가능한 회사<br><strong>"+
        x(report["companies_with_real_peer"])+"</strong></div></div>"
        "<h2>선별 기업의 산업 대분류별 매출 증가율 (시장 전체 성장 아님)</h2>"
        "<div class='wrap'><table><thead><tr><th>산업 대분류(2자리)</th><th>실제 세부 업종코드</th><th>표본 기업 수</th>"
        "<th>표본 평균 매출 YoY</th><th>공식 산업전체 성장률</th></tr></thead><tbody>"+
        sectors+"</tbody></table></div>"
        "<h2>산업 대분류 내 실적·주가 연구 비교</h2>"
        "<div class='wrap'><table><thead><tr>"
        "<th>대분류(2자리)</th><th>세부 업종코드</th><th>대분류 표본</th><th>종목</th><th>회사</th>"
        "<th>매출 YoY</th><th>업종 내 매출순위</th><th>영업익 YoY</th><th>업종 내 영업익순위</th>"
        "<th>주가 3개월</th><th>업종 내 가격순위</th><th>업종 최초 로컬 수신 UTC</th>"
        "</tr></thead><tbody>"+"".join(companies)+"</tbody></table></div>"
        "<p><small>가격 관측일 "+x(report["market_session"])+
        " / 평가 첫 가능시각 "+x(report["as_of_utc"])+
        ". DART 현재 KSIC 코드와 첫 수신실적을 이용하며, 업종 내 비교 표본이 작습니다."
        " 외국인·기관 수급, 공식 업종 전체 성장 및 정식 투자 1~20위는 N/A.</small></p>"
        "</main><footer>EraLeader local-first · 투자 우선순위 N/A · PIT 인증 전</footer>"
        "</body></html>"
    )
