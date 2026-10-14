"""Daily local WATCH business brief from an immutable verified WATCH queue.

Annual earnings growth signals are observations, never daily leader transitions.
No portfolio state/strategy recipient/orders, source API or prospective write.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import shutil
import tempfile
from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .early_leader_watch_queue import _validated as verified_watch

SCHEMA="eraleader.kr_annual_profit_watch_daily_brief.v1"
FOLDER="early_watch_daily_briefs"
LABELS=("MARGIN_IMPROVING_FY","MARGIN_WEAKENING_FY",
        "MARGIN_UNCHANGED_FY","MARGIN_NOT_COMPARABLE")


def _now(clock):
    moment=clock or datetime.now(timezone.utc)
    if not isinstance(moment,datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("DAILY_WATCH_CLOCK_INVALID")
    return moment.astimezone(timezone.utc)


def build_daily_brief(source:dict,*,clock:datetime|None=None)->dict:
    now=_now(clock)
    if (source.get("watch_only") is not True or
            source.get("receiver_neutral") is not True or
            source.get("selected_candidates")!=[] or
            source.get("orders_enabled") is not False):
        raise ValueError("DAILY_WATCH_SOURCE_NOT_WATCH_ONLY")
    rows=[]
    counts={label:0 for label in LABELS}
    for candidate in source["review_queue"]:
        delta=candidate.get("dart_cfs_operating_margin_change_pp")
        if delta is None:
            status="MARGIN_NOT_COMPARABLE"
        elif type(delta) not in (int,float):
            raise ValueError("DAILY_WATCH_MARGIN_CHANGE_INVALID")
        elif delta>0:
            status="MARGIN_IMPROVING_FY"
        elif delta<0:
            status="MARGIN_WEAKENING_FY"
        else:
            status="MARGIN_UNCHANGED_FY"
        counts[status]+=1
        rows.append({
            "security_id":candidate["security_id"],
            "name":candidate["name"],
            "watch_tier":candidate["watch_tier"],
            "watch_review_position":candidate["review_priority_position"],
            "annual_margin_observation":status,
            "fiscal_year":candidate.get("dart_latest_cfs_business_year"),
            "previous_fiscal_year":candidate.get("dart_previous_cfs_business_year"),
            "operating_margin_change_pp":delta,
            "net_margin_change_pp":candidate.get("dart_cfs_net_margin_change_pp"),
            "two_year_positive_operating_margin":candidate.get(
                "dart_cfs_operating_margin_positive_two_years"),
            "flow_research_10_not_formal":candidate.get("flow_research_10"),
            "full_leader_score_100":None,
            "leader_state_change":None,
            "order_instruction":False,
        })
    if not rows:
        raise ValueError("DAILY_WATCH_EMPTY_QUEUE")
    local_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    summary={
        "schema":SCHEMA,
        "market":"KR","report_local_day":local_day,
        "source_market_session":source["source_market_session"],
        "source_watch_content_sha256":source["content_sha256"],
        "source_watch_first_published_at_utc":source["watch_published_at_utc"],
        "first_report_generated_at_utc":now.isoformat(),
        "report_is_same_session_market_update":local_day==source["source_market_session"],
        "annual_comparison_only":True,
        "report_kind":"ANNUAL_CFS_MARGIN_SNAPSHOT_NOT_DAILY_STATUS_TRANSITION",
        "watch_rows":len(rows),"annual_margin_counts":counts,
        "entries":rows,
        "receiver_project":None,
        "research_only":True,
        "official_leader_confirmations":0,"leader_state_events":[],
        "orders_enabled":False,"external_api_calls":0,
    }
    summary["content_sha256"]=sha256(canonical(summary)).hexdigest()
    return summary


def _html(report:dict)->bytes:
    stats=report["annual_margin_counts"]
    body=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>EraLeader · WATCH 일일 실적 관찰 보고서</title>'
        '<style>body{max-width:1300px;margin:20px auto;padding:0 15px;'
        'font:14px system-ui,sans-serif;line-height:1.6}'
        'table{border-collapse:collapse;width:100%}td,th{border-bottom:'
        '1px solid #ccc;padding:7px;text-align:left}.wrap{overflow:auto}</style>'
        '</head><body><h1>WATCH 일일 실적 관찰 보고서</h1>'
        '<p>보고일 '+escape(report["report_local_day"])+' · 원시장 관측일 '
        +escape(report["source_market_session"])
        +' · 수익성 비교는 과거 2개 회계연도 간 변화입니다. '
        '오늘 발생한 대장주 강화·약화 이벤트가 아닙니다.</p>'
        '<p>관찰 '+str(report["watch_rows"])+'종목 · 연간 수익성 개선 '
        +str(stats["MARGIN_IMPROVING_FY"])+' · 악화 '
        +str(stats["MARGIN_WEAKENING_FY"])+' · 변화 없음 '
        +str(stats["MARGIN_UNCHANGED_FY"])+' · 비교 불가 '
        +str(stats["MARGIN_NOT_COMPARABLE"])+'</p>'
        '<p>공식 산업/기업 경쟁력 20점 N/A · 대장주 확정 0 · 주문 0. '
        'Kiwoom 수급 점수는 연구 관측치이며 매수 추천이 아닙니다.</p>'
        '<div class="wrap"><table><thead><tr><th>검토순</th><th>종목</th>'
        '<th>관찰그룹</th><th>연간 실적 변화</th><th>회계연도</th>'
        '<th>영업이익률 변동(pp)</th><th>순이익률 변동(pp)</th>'
        '<th>연속 영업흑자율</th><th>수급 연구10</th>'
        '</tr></thead><tbody>'
    )
    for row in report["entries"]:
        values=(row["watch_review_position"],row["name"],row["watch_tier"],
                row["annual_margin_observation"],row["fiscal_year"],
                row["operating_margin_change_pp"],row["net_margin_change_pp"],
                row["two_year_positive_operating_margin"],row["flow_research_10_not_formal"])
        body+='<tr>'+''.join('<td>'+escape("N/A" if v is None else str(v))+'</td>'
                                  for v in values)+'</tr>'
    return (body+'</tbody></table></div></body></html>').encode()


def read_daily_brief(path:Path,*,clock:datetime|None=None)->dict:
    now=_now(clock)
    if (not path.is_absolute() or path.is_symlink() or
            any(p.is_symlink() for p in path.parents) or
            not path.is_file() or path.stat().st_size>300_000):
        raise ValueError("DAILY_WATCH_FILE_UNSAFE")
    original=path.read_bytes()
    doc=json.loads(original)
    unsigned=dict(doc);stored=unsigned.pop("content_sha256",None)
    when=datetime.fromisoformat(doc["first_report_generated_at_utc"])
    if (original!=canonical(doc)+b"\n" or
            stored!=sha256(canonical(unsigned)).hexdigest() or
            doc.get("schema")!=SCHEMA or doc.get("market")!="KR" or
            doc.get("annual_comparison_only") is not True or
            doc.get("receiver_project") is not None or
            doc.get("official_leader_confirmations")!=0 or
            doc.get("leader_state_events")!=[] or
            doc.get("orders_enabled") is not False or
            when.tzinfo is None or when.astimezone(timezone.utc)>now or
            len(doc.get("entries",[]))!=doc.get("watch_rows") or
            sum(doc["annual_margin_counts"].values())!=doc["watch_rows"]):
        raise ValueError("DAILY_WATCH_SNAPSHOT_CONTRACT")
    return doc


def publish_daily_brief(*,watch_manifest:Path,project:Path,
                        clock:datetime|None=None)->dict:
    now=_now(clock)
    watch=verified_watch(watch_manifest,clock=now)
    output=_owned_output(project)/FOLDER
    if output.is_symlink():raise ValueError("DAILY_WATCH_OUTBOX_SYMLINK")
    output.mkdir(mode=0o700,exist_ok=True)
    local_day=now.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    slug="KR_"+local_day+"_"+watch["content_sha256"][:16]
    dest=output/slug
    manifest=dest/"brief.json";index=dest/"index.html"
    if dest.is_symlink():raise ValueError("DAILY_WATCH_VERSION_SYMLINK")
    if dest.exists():
        doc=read_daily_brief(manifest,clock=now)
        if (doc["source_watch_content_sha256"]!=watch["content_sha256"] or
                doc["report_local_day"]!=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
                or index.is_symlink() or index.read_bytes()!=_html(doc)):
            raise ValueError("DAILY_WATCH_REPLAY_SOURCE_CHANGED")
        state="ALREADY_PUBLISHED"
    else:
        doc=build_daily_brief(watch,clock=now)
        stage=Path(tempfile.mkdtemp(prefix=".watch_brief_",dir=output))
        try:
            os.chmod(stage,0o700)
            for name,b in (("brief.json",canonical(doc)+b"\n"),
                           ("index.html",_html(doc))):
                fd=os.open(stage/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,"wb") as target:
                    target.write(b);target.flush();os.fsync(target.fileno())
            # Same immutable source reread; no silent later revision.
            again=verified_watch(watch_manifest,clock=now)
            if again["content_sha256"]!=watch["content_sha256"] or dest.exists():
                raise ValueError("DAILY_WATCH_SOURCE_CHANGED_BEFORE_PUBLISH")
            os.rename(stage,dest)
        finally:
            if stage.exists():shutil.rmtree(stage)
        state="PUBLISHED"
    return {
        "status":state,"report_day":doc["report_local_day"],
        "market_session":doc["source_market_session"],
        "watch_rows":doc["watch_rows"],"annual_margin_counts":doc["annual_margin_counts"],
        "manifest":str(manifest),"site":str(index),
        "source_sha256":doc["source_watch_content_sha256"],
        "official_leaders":0,"orders":0,"external_api_calls":0}
