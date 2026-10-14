"""Operational P2 five-factor coverage and priority-to-complete from real KRX.

Reuses source-pinned marketwide research and existing Stage4 evidence gates.
P2 identifies the closest observed candidates *without* claiming unavailable
industry growth, competitive moats, historical issuer PIT, or scalable flow.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os
import re
import sqlite3

from .official_company_explorer import canonical
from .official_marketwide_coverage import SCHEMA as MARKETWIDE
from .states import SCORE_MAX, evaluate_leader_state
from .delivery import BASE_CSS

SCHEMA = "eraleader.official_p2_five_factor_readiness.v1"
FIELDS = {"industry":"industry_growth","competitiveness":"competitiveness",
          "earnings":"earnings_research_25","momentum":"price_strength_25",
          "flow":"institutional_flow"}
MISSING_REASONS = {
    "industry":"NO_SECTORWIDE_GROWTH_SCORE_20",
    "competitiveness":"NO_INDEPENDENT_COMPETITIVENESS_SCORE_20",
    "earnings":"NO_COMPLETE_COMPANY_ANNUAL_GROWTH",
    "momentum":"NO_VERIFIED_3M_6M_RELATIVE_MOMENTUM",
    "flow":"NO_NORMALIZED_INSTITUTION_FOREIGN_SCORE_10",
}
CODE = re.compile(r"[A-Za-z0-9]{6}\Z")


def _load(path: Path) -> dict:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file() or
            any(x.is_symlink() for x in path.parents) or path.stat().st_uid!=os.geteuid() or
            not 0<path.stat().st_size<=8_000_000):
        raise ValueError("P2_SOURCE_UNSAFE")
    def unique(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError("P2_DUPLICATE_JSON_FIELD")
            result[key]=value
        return result
    source=json.loads(path.read_bytes(),object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("P2_NONFINITE_SOURCE")))
    if type(source) is not dict:
        raise ValueError("P2_SOURCE_NOT_OBJECT")
    proof=source.get("content_sha256")
    original=dict(source);original.pop("content_sha256",None)
    if (source.get("schema")!=MARKETWIDE or proof != sha256(canonical(original)).hexdigest() or
            source.get("research_only") is not True or
            source.get("official_leaders")!=0 or
            source.get("full_market_composite_rank_available") is not False or
            source.get("market")!="KR"):
        raise ValueError("P2_UNTRUSTED_OR_PROMOTED_MARKET_DATA")
    return source


def _observed_state_counts(dbfile: Path | None, session: str) -> dict:
    if dbfile is None:
        return {"observed_watch":None,"observed_potential":None,"observed_confirmed":None}
    if (not dbfile.is_absolute() or dbfile.is_symlink() or not dbfile.is_file() or
            any(x.is_symlink() for x in dbfile.parents) or dbfile.stat().st_uid!=os.geteuid() or
            dbfile.name!="official_price_watch_state_history.sqlite"):
        raise ValueError("P2_RESEARCH_STATE_UNSAFE")
    connection=sqlite3.connect(dbfile.as_uri()+"?mode=ro",uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        rows=connection.execute("""SELECT current,COUNT(*)
                FROM state_history WHERE market='KR' AND as_of=?
                GROUP BY current""",(session,)).fetchall()
    finally:
        connection.close()
    by_state=dict(rows)
    if any(k!="WATCH" for k in by_state):
        raise ValueError("P2_PRICE_WATCH_LEDGER_UNEXPECTED_SELECTION")
    return {"observed_watch":by_state.get("WATCH",0),
            "observed_potential":0,"observed_confirmed":0}


def build_p2_readiness(marketwide: Path, *, state_history: Path | None = None,
                       clock: datetime | None = None) -> dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("P2_AWARE_DECISION_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    doc=_load(marketwide)
    source_day=date.fromisoformat(doc["market_session"])
    if (datetime.fromisoformat(doc["built_at_utc"])>now or
            source_day>now.date() or
            type(doc.get("securities")) is not list or
            len(doc["securities"])!=doc.get("official_krx_observed")):
        raise ValueError("P2_FUTURE_OR_INCOMPLETE_SOURCE")
    counts={k:0 for k in SCORE_MAX}
    ready=[]
    all_codes=set()
    with_price=0
    for sec in doc["securities"]:
        code=sec["security_id"]
        if type(code) is not str or CODE.fullmatch(code) is None or code in all_codes:
            raise ValueError("P2_DUPLICATE_OR_INVALID_SECURITY")
        if (sec.get("formal_leader_score_100") is not None or
                sec.get("verified_leader_state") is not None):
            raise ValueError("P2_RESEARCH_SOURCE_FALSE_LEADER")
        all_codes.add(code)
        # DART industry codes and peer ranks do not measure sector growth or
        # an independent moat. Kiwoom share-count flow has no calibrated
        # normalized 0..10 cross-sectional factor score.
        raw={
            "industry":None,"competitiveness":None,
            "earnings":sec.get("earnings_research_25"),
            "momentum":sec.get("price_strength_25"),
            "flow":None,
        }
        for k,v in raw.items():
            if v is not None:
                if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=SCORE_MAX[k]:
                    raise ValueError("P2_INVALID_OBSERVED_SCORE_FACTOR")
                counts[k]+=1
        if raw["momentum"] is not None:
            with_price+=1
        # Do not write these partial diagnostics to the verified state
        # registry. The existing state model is invoked to prove the gate
        # remains WATCH under actual incomplete evidence.
        assessment=evaluate_leader_state(
            raw,{"financial_pit":False,"historic_universe_pit":False,
                 "corporate_actions_pit":False},
            previous="WATCH")
        if assessment["state"]!="WATCH" or assessment["total"] is not None:
            raise ValueError("P2_PARTIAL_FACTORS_PROMOTED")
        if raw["momentum"] is None or raw["earnings"] is None:
            continue
        score=sec.get("two_factor_research_50")
        if (type(score) not in (float,int) or not math.isfinite(score) or
                abs(float(score)-float(raw["momentum"]+raw["earnings"]))>0.000002):
            raise ValueError("P2_TWO_FACTOR_SOURCE_SCORE_CONFLICT")
        ready.append({
            "security_id":code,"name":sec["name"],
            "market_session":doc["market_session"],
            "observed_50_point_score":float(score),
            "candidate_research_rank":None,
            "component_scores_100":raw,
            "required_missing_factors":[MISSING_REASONS[k] for k in SCORE_MAX if raw[k] is None],
            "known_current_industry_code":sec.get("industry_code"),
            "observed_institution_net_shares_20":sec.get("institutional_flow"),
            "observed_foreign_net_shares_20":sec.get("foreign_flow"),
            "formal_total_score_100":None,
            "verified_leader_state":None,
            "selection_state":"WATCH",
            "eligible_for_verified_potential":False,
            "eligible_for_verified_confirmation":False,
            "source_sha256":doc["content_sha256"],
        })
    ready.sort(key=lambda r:(-r["observed_50_point_score"],r["security_id"]))
    for rank,row in enumerate(ready,1):
        row["candidate_research_rank"]=rank
    saved_states=_observed_state_counts(state_history,doc["market_session"])
    result={
        "schema":SCHEMA,"market":"KR","market_session":doc["market_session"],
        "evaluated_at_utc":now.isoformat(),
        "source_marketwide_sha256":doc["content_sha256"],
        "observed_market_securities":len(doc["securities"]),
        "five_factor_max_points":dict(SCORE_MAX),
        "observed_factor_counts":counts,
        "two_factor_research_evaluable":len(ready),
        "top20_for_factor_completion":ready[:20],
        "total_candidates_eligible_for_verified_100_point_selection":0,
        "selected_candidates":[],"official_leaders":0,
        "full_100_point_ranking_available":False,
        "research_only":True,"order_instruction":False,
        "observed_price_strength_securities":with_price,
        "research_state_history":saved_states,
        "data_age_calendar_days":(now.date()-source_day).days,
        "known_absent_data":[MISSING_REASONS[k] for k in SCORE_MAX if counts[k]==0],
        "missing_policy":"N_A_NEVER_ZERO_FOR_UNOBSERVED_FACTORS",
        "warning":"50pt two-factor comparison is not a full-universe investment priority; "
                  "industry-code and flows in shares do not prove 20/20/10 scores, "
                  "and historical PIT requirements remain unavailable.",
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    return result


def publish_p2_readiness(report: dict, destination: Path) -> tuple[Path,Path]:
    original=dict(report);digest=original.pop("content_sha256",None)
    if (report.get("schema")!=SCHEMA or digest!=sha256(canonical(original)).hexdigest() or
            report.get("selected_candidates")!=[] or report.get("official_leaders")!=0 or
            report.get("full_100_point_ranking_available") is not False):
        raise ValueError("P2_REPORT_MUST_REMAIN_NON_PROMOTED")
    if (not destination.is_absolute() or destination.is_symlink() or destination.exists() or
            not destination.parent.is_dir() or destination.parent.is_symlink() or
            any(x.is_symlink() for x in destination.parents)):
        raise ValueError("P2_OUTPUT_MUST_BE_NEW_PRIVATE_PATH")
    header="".join("<th>"+escape(k)+"</th>" for k in ("연구 순서","종목","기업","50점 연구점수","100점 미충족 이유"))
    rows="".join("<tr>"+"".join("<td>"+escape(str(value))+"</td>" for value in (
        row["candidate_research_rank"],row["security_id"],row["name"],
        row["observed_50_point_score"],", ".join(row["required_missing_factors"])))+
        "</tr>" for row in report["top20_for_factor_completion"])
    counts="".join("<li>"+escape(k)+": "+str(v)+"종목 / "+str(report["observed_market_securities"])+"</li>"
                   for k,v in report["observed_factor_counts"].items())
    page=(
        "<!doctype html><html lang='ko'><meta charset='utf-8'><title>EraLeader P2 준비도</title>"
        "<style>"+BASE_CSS+"</style><main><h1>EraLeader · 대장주 5요소 준비도</h1>"
        "<p><strong>현재 거래일 "+escape(report["market_session"])+
        " · 과거 관측 경과 "+str(report["data_age_calendar_days"])+"일</strong></p>"
        "<p>정식 100점 대장주 <strong>0종목</strong>. 50점 연구순위를 실제 대장주 TOP20으로 "
        "승격하지 않습니다. 검증된 산업 성장·경쟁력·정규화 기관외국인 수급이 부족합니다.</p>"
        "<h2>각 요소 관측 수</h2><ul>"+counts+"</ul>"
        "<h2>우선 자료 확보 대상 (현재 2요소 연구 순위)</h2>"
        "<table><thead><tr>"+header+"</tr></thead><tbody>"+rows+"</tbody></table>"
        "<p>목록은 매수·매도 권고가 아닙니다. 이력 원장과 전략 송신은 기존 코드가 별도 담당합니다.</p>"
        "</main></html>")
    destination.mkdir(mode=0o700)
    a,b=destination/"p2_readiness.json",destination/"index.html"
    try:
        for path,payload in ((a,canonical(report)+b"\n"),(b,page.encode("utf-8"))):
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(payload);out.flush();os.fsync(out.fileno())
    except BaseException:
        a.unlink(missing_ok=True);b.unlink(missing_ok=True)
        destination.rmdir()
        raise
    return a,b
