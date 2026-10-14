"""Research-only sector peer and raw broker-flow evidence from pinned KR reports.

Industry-code/current cross-section ≠ a full-industry growth score.
Relative peer rank ≠ validated corporate competitiveness.
Net shares ≠ a normalized institutional flow score.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from statistics import median
import json
import math
import os
import re
import shutil
import tempfile

from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search
from .official_company_explorer import canonical

SCHEMA="eraleader.kr_sector_peer_flow_research.v1"
SUBDIR="sector_peer_flow"
TYPES=(("revenue","revenue_yoy","peer_revenue_yoy_rank",
        "peer_revenue_yoy_denominator"),
       ("operating","operating_income_yoy","peer_operating_yoy_rank",
        "peer_operating_yoy_denominator"))


def analyze_marketwide_peer_flow(path:Path, *, clock:datetime|None=None) -> dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("PEER_FLOW_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    report,_=_source(path)
    from zoneinfo import ZoneInfo
    day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    manifest,_=prepare_search(report,request_day=day,clock=now)
    groups=defaultdict(list)
    rows=[]
    for item in report["securities"]:
        sector=item["industry_code"]
        if sector is not None:
            groups[sector].append(item)
    # The source already pins 49 current DART profiles and KRX observations;
    # the following peer-ranked fields are *additional* unvalidated fields.
    # Validate their group denominator, unique rank, value ordering first.
    validated={}
    for sector,members in groups.items():
        for label,value_key,rank_key,n_key in TYPES:
            quantified=[x for x in members if x.get(value_key) is not None]
            ranked=[x for x in members if x.get(rank_key) is not None or
                    x.get(n_key) is not None]
            if not ranked:
                continue
            n=len(quantified)
            if len(ranked)!=n or n<2:
                raise ValueError("PEER_FLOW_PARTIAL_RANK_COHORT")
            got=set()
            for row in ranked:
                rank=row.get(rank_key)
                den=row.get(n_key)
                val=row.get(value_key)
                if (type(rank) is not int or type(den) is not int or
                        den!=n or not 1<=rank<=n or rank in got or
                        type(val) not in (int,float) or not math.isfinite(val)):
                    raise ValueError("PEER_FLOW_RANK_DENOMINATOR_INVALID")
                got.add(rank)
            if got!=set(range(1,n+1)):
                raise ValueError("PEER_FLOW_RANKS_NOT_CONTIGUOUS")
            sorted_values=sorted(quantified,key=lambda r:r[value_key],reverse=True)
            for index,row in enumerate(sorted_values,1):
                if row[rank_key]!=index:
                    raise ValueError("PEER_FLOW_RANK_ORDER_NOT_SOURCE_CONSISTENT")
            validated[(sector,label)]=n
    for item in report["securities"]:
        industry=item["industry_code"]
        flow_i=item.get("institutional_flow")
        flow_f=item.get("foreign_flow")
        if (flow_i is None)!=(flow_f is None):
            raise ValueError("PEER_FLOW_HALF_BROKER_DATA")
        if flow_i is not None and (type(flow_i) is not int or type(flow_f) is not int):
            raise ValueError("PEER_FLOW_RAW_NOT_INTEGER")
        if (industry is None and flow_i is None):
            continue
        partial={
            "security_id":item["security_id"],"name":item["name"],
            "industry_code":industry,
            "revenue_yoy":item.get("revenue_yoy"),
            "operating_income_yoy":item.get("operating_income_yoy"),
            "sector_observed_company_count":len(groups[industry]) if industry is not None else 0,
            "revenue_peer_rank":item.get("peer_revenue_yoy_rank"),
            "revenue_peer_denominator":item.get("peer_revenue_yoy_denominator"),
            "operating_peer_rank":item.get("peer_operating_yoy_rank"),
            "operating_peer_denominator":item.get("peer_operating_yoy_denominator"),
            "institutional_net_shares":flow_i,
            "foreign_net_shares":flow_f,
            "industry_growth_score_20":None,
            "competitiveness_score_20":None,
            "investor_flow_score_10":None,
        }
        # One rank with n>=3 is an observed small-sample peer comparison,
        # *not* an industry-wide or company-moat score.
        partial["peer_revenue_relative_position"]=(
            round((item["peer_revenue_yoy_denominator"]-item["peer_revenue_yoy_rank"])/
                  (item["peer_revenue_yoy_denominator"]-1),4)
            if industry is not None and
               validated.get((industry,"revenue"),0)>=3 and
               item.get("peer_revenue_yoy_rank") is not None else None)
        partial["peer_operating_relative_position"]=(
            round((item["peer_operating_yoy_denominator"]-item["peer_operating_yoy_rank"])/
                  (item["peer_operating_yoy_denominator"]-1),4)
            if industry is not None and
               validated.get((industry,"operating"),0)>=3 and
               item.get("peer_operating_yoy_rank") is not None else None)
        rows.append(partial)
    sectors=[]
    for sector,members in sorted(groups.items()):
        rev=[x["revenue_yoy"] for x in members if x.get("revenue_yoy") is not None]
        op=[x["operating_income_yoy"] for x in members
            if x.get("operating_income_yoy") is not None]
        if len(members)<3:
            continue
        sectors.append({
            "industry_code":sector,"observed_companies":len(members),
            "revenue_observations":len(rev),
            "operating_observations":len(op),
            # Median only among the actually observed issuers, NOT the full
            # economy-wide industry. Missing peer earnings stay null.
            "sample_revenue_yoy_median":round(median(rev),6) if len(rev)>=3 else None,
            "sample_operating_yoy_median":round(median(op),6) if len(op)>=3 else None,
            "independent_industry_growth_score_20":None,
        })
    rows.sort(key=lambda r:(
        r["peer_revenue_relative_position"] is None,
        -(r["peer_revenue_relative_position"] or 0),
        r["security_id"]))
    result={
        "schema":SCHEMA,"market":"KR",
        "source_market_session":manifest["source_market_session"],
        "source_marketwide_sha256":manifest["source_marketwide_sha256"],
        "source_built_at_utc":manifest["source_built_at_utc"],
        "stale_warning_at_generation":manifest["stale_warning"],
        "source_is_research_only":True,
        "sector_profile_count":manifest["industry_available"],
        "sector_groups_with_at_least_three_observed":len(sectors),
        "observed_revenue_peer_ranks":sum(x["revenue_peer_rank"] is not None for x in rows),
        "observed_operating_peer_ranks":sum(x["operating_peer_rank"] is not None for x in rows),
        "relative_revenue_sample_ge3":sum(
            x["peer_revenue_relative_position"] is not None for x in rows),
        "relative_operating_sample_ge3":sum(
            x["peer_operating_relative_position"] is not None for x in rows),
        "same_session_raw_broker_flow":sum(
            x["institutional_net_shares"] is not None for x in rows),
        "partial_sector_medians":sectors,
        "companies":rows,
        "industry_growth_score_20_available":0,
        "competitiveness_score_20_available":0,
        "flow_score_10_available":0,
        "formal_leaders":0,
        "historical_independent_pit_certified":False,
        "execution_authority":False,
        "orders_enabled":False,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    return result


def _html(report:dict) -> bytes:
    def fmt(v):
        return "N/A" if v is None else str(v)
    header=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader · KR 산업 동종기업 비교</title>'
        '<style>body{font:15px system-ui,sans-serif;margin:24px auto;padding:0 16px;max-width:1200px;line-height:1.5}'
        'table{border-collapse:collapse;min-width:850px}th,td{padding:8px;border-bottom:1px solid #aaa;text-align:left}'
        '.scroll{overflow-x:auto}.warn{border-left:4px solid #a86;padding:12px;background:#8881}</style>'
        '</head><body><h1>KR 산업·동종기업 성장 비교 (연구용)</h1>'
        '<div class="warn">실제 전체 산업 성장성/기업 경쟁력 점수 아님. '
        '현재 DART 산업코드·부분기업 표본의 매출·영업 성장 비교이며 '
        '기관·외국인 순매매는 주수 관측값으로만 표시. '
        '정식 대장주·실거래 신호 없음.</div>'
        '<p>KRX 시장 관측일 '+escape(report["source_market_session"]) +
        ' · 보고서 생성기준 '+escape(report["source_built_at_utc"]) +
        ' · 시장 원본 SHA '+escape(report["source_marketwide_sha256"][:16])+'</p>'
        '<p>산업 프로필 '+str(report["sector_profile_count"])+
        '사, 동종 매출 성장 순위 '+str(report["observed_revenue_peer_ranks"])+
        '사, 동종 영업성장 순위 '+str(report["observed_operating_peer_ranks"])+
        '사, 같은 세션 기관·외국인 원시 수급 '+str(report["same_session_raw_broker_flow"])+
        '사. 표본 3개 미만 업종은 비교지표 N/A.</p>'
        '<h2>관측된 일부 업종의 성장 중앙값</h2>'
        '<div class="scroll"><table><thead><tr><th>산업코드</th><th>회사수</th>'
        '<th>매출 관측</th><th>매출 YoY 중앙값(비율)</th>'
        '<th>영업이익 YoY 중앙값(비율)</th></tr></thead><tbody>')
    sector_rows=''.join('<tr>'+''.join(
        '<td>'+escape(fmt(v))+'</td>' for v in (
            s["industry_code"],s["observed_companies"],s["revenue_observations"],
            s["sample_revenue_yoy_median"],s["sample_operating_yoy_median"]))+'</tr>'
        for s in report["partial_sector_medians"])
    mid='</tbody></table></div><h2>기업별 관측 비교</h2><div class="scroll"><table><thead><tr>'+''.join(
        '<th>'+x+'</th>' for x in (
            "종목","코드","산업코드","매출 YoY","매출 동종 순위","매출 상대위치(0~1)",
            "영업이익 YoY","영업성장 동종 순위","기관 순매매(주)","외국인 순매매(주)"))
    mid+='</tr></thead><tbody>'
    items=[]
    for x in report["companies"]:
        labels=(x["name"],x["security_id"],x["industry_code"],x["revenue_yoy"],
                f'{x["revenue_peer_rank"]}/{x["revenue_peer_denominator"]}'
                    if x["revenue_peer_rank"] is not None else None,
                x["peer_revenue_relative_position"],x["operating_income_yoy"],
                f'{x["operating_peer_rank"]}/{x["operating_peer_denominator"]}'
                    if x["operating_peer_rank"] is not None else None,
                x["institutional_net_shares"],x["foreign_net_shares"])
        items.append('<tr>'+''.join('<td>'+escape(fmt(v))+'</td>' for v in labels)+'</tr>')
    return (header+sector_rows+mid+''.join(items)+
            '</tbody></table></div><p>발행시점과 역사적 PIT 독립 인증은 별도. '
            '표본 비교는 정식 100점 대장주 판단 근거가 아닙니다.</p></body></html>').encode("utf-8")


def publish_marketwide_peer_flow(*,marketwide:Path,project:Path,
                                 clock:datetime|None=None)->dict:
    root=_owned_output(project)
    result=analyze_marketwide_peer_flow(marketwide,clock=clock)
    store=root/SUBDIR
    if store.is_symlink():
        raise ValueError("PEER_FLOW_DESTINATION_LINKED")
    store.mkdir(mode=0o700,exist_ok=True)
    if store.is_symlink() or store.stat().st_uid!=os.geteuid():
        raise ValueError("PEER_FLOW_DESTINATION_UNSAFE")
    directory=store/("KR_"+result["source_market_session"].replace("-","")
                     +"_"+result["source_marketwide_sha256"][:16])
    data=canonical(result)+b"\n"
    page=_html(result)
    if directory.is_symlink():
        raise ValueError("PEER_FLOW_PUBLICATION_LINKED")
    if directory.exists():
        if ((directory/"peer_flow.json").is_symlink() or
                (directory/"index.html").is_symlink() or
                not directory.is_dir() or
                (directory/"peer_flow.json").read_bytes()!=data or
                (directory/"index.html").read_bytes()!=page):
            raise ValueError("PEER_FLOW_PUBLICATION_CONFLICT")
        status="ALREADY_PUBLISHED"
    else:
        staged=Path(tempfile.mkdtemp(prefix=".peerflow_",dir=store))
        try:
            os.chmod(staged,0o700)
            for filename,payload in (("peer_flow.json",data),("index.html",page)):
                fd=os.open(staged/filename,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,"wb") as out:
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
            # The original pinned source cannot change during publication.
            latest,_=_source(marketwide)
            if latest["content_sha256"]!=result["source_marketwide_sha256"]:
                raise ValueError("PEER_FLOW_SOURCE_REVISED")
            if directory.exists() or directory.is_symlink():
                raise ValueError("PEER_FLOW_PUBLICATION_RACE")
            os.rename(staged,directory)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
        status="PUBLISHED"
    return {
        "status":status,
        "source_market_session":result["source_market_session"],
        "source_marketwide_sha256":result["source_marketwide_sha256"],
        "industry_profiles":result["sector_profile_count"],
        "sector_groups_observed":result["sector_groups_with_at_least_three_observed"],
        "revenue_peer_ranked":result["observed_revenue_peer_ranks"],
        "operating_peer_ranked":result["observed_operating_peer_ranks"],
        "flow_raw_observed":result["same_session_raw_broker_flow"],
        "industry_growth_scores":0,"competitiveness_scores":0,"flow_scores":0,
        "site":str(directory/"index.html"),
        "manifest":str(directory/"peer_flow.json"),
        "orders":0,"formal_leaders":0,
    }
