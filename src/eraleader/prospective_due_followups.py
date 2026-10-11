"""5_5: follow up every FIRST-WRITTEN prospective Top-K cohort at its due date.

Strictly reuses indexed/native censuses and original ranked source receipts.
This is a local evidence-collection queue, not a new success label, a market
data source, or an independently attested time/performance certification.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from html import escape
from math import ceil, floor
from pathlib import Path
import json

from .delivery import BASE_CSS
from .native_census_gate import audit_native_census, native_gate_marker
from .prospective_census import (
    SPEC_KEYS, _due, _root, _sources, _validate_registry,
)
from .prospective_census_seal import (
    _inventory, _index_path, indexed_audit_censuses,
)
from .ranked_discovery import _now, _time
from .ranked_outcome_receipts import audit_ranked_outcome_receipts
from .watch_operating_reports import _atomic_text

SCHEMA="eraleader.prospective_outcome_followup.v1"
MAX_DISPLAY_ROWS=500
STATUSES={
    "AWAITING_HORIZON",
    "AWAITING_HORIZON_WITH_LOCAL_PAIR",
    "DUE_BOTH_SOURCES_MISSING",
    "DUE_OUTCOMES_MISSING",
    "DUE_RECEIPTS_MISSING",
    "DUE_PAIRED_CENSORED",
    "DUE_PAIRED_LOCALLY_KNOWN_NOT_CERTIFIED",
}
FOLLOWUP_REQUIRED={
    "DUE_BOTH_SOURCES_MISSING","DUE_OUTCOMES_MISSING",
    "DUE_RECEIPTS_MISSING","DUE_PAIRED_CENSORED",
}


def _verified_census(registry:Path, assessed:datetime, now:datetime,
                     native_config:Path|None) -> dict:
    # Downgrade prevention: never treat native or unindexed registries as
    # equivalent proof of a complete first-write cohort population.
    marker=native_gate_marker(registry)
    if marker.is_symlink():
        raise ValueError("Unsafe prospective native requirement marker")
    if (marker.exists()) != (native_config is not None):
        raise ValueError("Native first-write cohort requires exact native source config")
    if native_config is not None:
        return audit_native_census(
            registry,native_config=Path(native_config),
            evaluated_at=assessed.isoformat(),clock=now)
    return indexed_audit_censuses(
        registry,evaluated_at=assessed.isoformat(),clock=now)


def _present(path:Path) -> tuple[bool,str]:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Unsafe/linked prospective outcome evidence")
    if not path.exists():
        return False,"0"*64
    if not path.is_file() or not 0<path.stat().st_size<=1_000_000:
        raise ValueError("Invalid or oversized prospective outcome evidence")
    return True,sha256(path.read_bytes()).hexdigest()


def _build_queue(registry:Path, assessed:datetime,now:datetime
                 ) -> tuple[list[dict],dict,tuple]:
    rows=[]
    signatures=[]
    totals=Counter()
    seen=set()
    for manifest in sorted(_inventory(registry).values()):
        registered,source,entries=_validate_registry(manifest,assessed)
        manifest_sha=sha256(manifest.read_bytes()).hexdigest()
        signatures.append((manifest.name,manifest_sha))
        for number,row in enumerate(entries,1):
            if not isinstance(row,dict) or not SPEC_KEYS.issubset(row):
                raise ValueError("Malformed first-write cohort follow-up manifest")
            names,frozen=_sources(source,{key:row[key] for key in SPEC_KEYS})
            identity=(frozen["market"],frozen["model_version"],frozen["snapshot_at_utc"])
            if identity in seen:
                raise ValueError("Duplicate prospective cohort follow-up identity")
            seen.add(identity)
            f=source/names["frozen"]
            d=source/names["definition"]
            frozen_hash=sha256(f.read_bytes()).hexdigest()
            due=_due(frozen)
            k=min(frozen["requested_k"],len(frozen["ranked_candidates"]))
            if (row.get("frozen_sha256")!=frozen_hash or
                    row.get("label_definition_sha256")!=frozen["label_definition_sha256"] or
                    row.get("market")!=frozen["market"] or
                    row.get("model_version")!=frozen["model_version"] or
                    row.get("snapshot_at_utc")!=frozen["snapshot_at_utc"] or
                    row.get("frozen_at_utc")!=frozen["frozen_at_utc"] or
                    row.get("horizon_due_utc")!=due.isoformat() or
                    type(row.get("top_k_selected_count")) is not int or
                    row["top_k_selected_count"]!=k or
                    registered<_time(frozen["frozen_at_utc"])):
                raise ValueError("First-sealed cohort follow-up evidence revised")
            outcome=source/names["outcomes"]
            receipt=source/names["receipts"]
            has_out,out_sha=_present(outcome)
            has_receipt,receipts_sha=_present(receipt)
            signatures.append((manifest.name,number,frozen_hash,
                               sha256(d.read_bytes()).hexdigest(),out_sha,receipts_sha))
            known_hits=known_failures=0
            unknown=k
            if has_out and has_receipt:
                strict=audit_ranked_outcome_receipts(
                    f,outcome,receipt,evaluated_at=assessed.isoformat(),
                    label_definition_file=d,clock=now,sample_limit=1)
                if (strict["retrospective_freeze"] is not False or
                        strict["ranked_snapshot_sha256"]!=frozen["content_sha256"] or
                        strict["top_k_selected_count"]!=k):
                    raise ValueError("Prospective follow-up source audit mismatch")
                known_hits=strict["source_document_matched_early_hits"]
                known_failures=strict["source_document_matched_known_failures"]
                unknown=strict["unknown_or_source_censored_count"]
            if known_hits+known_failures+unknown!=k:
                raise ValueError("Prospective follow-up changed frozen denominator")
            expired=assessed>=due
            if not expired:
                state=("AWAITING_HORIZON_WITH_LOCAL_PAIR" if has_out and has_receipt
                       else "AWAITING_HORIZON")
            elif not has_out and not has_receipt:
                state="DUE_BOTH_SOURCES_MISSING"
            elif not has_out:
                state="DUE_OUTCOMES_MISSING"
            elif not has_receipt:
                state="DUE_RECEIPTS_MISSING"
            elif unknown:
                state="DUE_PAIRED_CENSORED"
            else:
                state="DUE_PAIRED_LOCALLY_KNOWN_NOT_CERTIFIED"
            due_days=floor((assessed-due).total_seconds()/86400) if expired else None
            until_days=ceil((due-assessed).total_seconds()/86400) if not expired else 0
            # Stable local reference only; never publish original source paths,
            # ticker, CIK, security ID, or label definition body.
            key=sha256((manifest_sha+"|"+str(number)+"|"+frozen_hash).encode()).hexdigest()[:16]
            rows.append({
                "cohort_ref":frozen["market"]+"-"+key,
                "registry_ref":"REG-"+manifest_sha[:16],
                "cohort_position":number,
                "market":frozen["market"],
                "horizon_due_utc":due.isoformat(),
                "top_k_selected_count":k,
                "known_hits_claimed_only":known_hits,
                "known_failures_claimed_only":known_failures,
                "unknown_or_censored":unknown,
                "followup_state":state,
                "days_overdue":due_days,
                "days_until_due":until_days,
                "source_pair_present":has_out and has_receipt,
            })
            totals["cohorts"]+=1
            totals["k"]+=k
            totals["hits"]+=known_hits
            totals["failures"]+=known_failures
            totals["unknown"]+=unknown
            if expired:
                totals["due_cohorts"]+=1
                totals["due_k"]+=k
                totals["due_unknown"]+=unknown
            if state in FOLLOWUP_REQUIRED:
                totals["due_gaps"]+=1
                totals["due_gap_k"]+=k
                totals["due_gap_unknown"]+=unknown
    return rows,dict(totals),tuple(signatures)


def _report(rows:list[dict],totals:dict,strict:dict,
            assessed:datetime) -> dict:
    if (totals.get("cohorts",0)!=strict["registered_cohort_count"] or
            totals.get("k",0)!=strict["frozen_selected_denominator"] or
            totals.get("hits",0)!=strict["locally_documented_early_hits"] or
            totals.get("failures",0)!=strict["locally_documented_known_failures"] or
            totals.get("unknown",0)!=strict["unknown_or_censored"]):
        raise ValueError("Follow-up queue does not match exhaustive indexed census audit")
    statuses=dict(sorted(Counter(row["followup_state"] for row in rows).items()))
    # Urgent missing/censored source evidence first, then time-to-maturity.
    priority={name:i for i,name in enumerate((
        "DUE_BOTH_SOURCES_MISSING","DUE_OUTCOMES_MISSING",
        "DUE_RECEIPTS_MISSING","DUE_PAIRED_CENSORED",
        "AWAITING_HORIZON","AWAITING_HORIZON_WITH_LOCAL_PAIR",
        "DUE_PAIRED_LOCALLY_KNOWN_NOT_CERTIFIED",
    ))}
    ordered=sorted(rows,key=lambda r:(
        priority[r["followup_state"]],r["horizon_due_utc"],
        r["market"],r["registry_ref"],r["cohort_position"]))
    due_gaps=totals.get("due_gaps",0)
    # Stable across clock advancement and presentation truncation. The digest
    # covers every unresolved cohort, including rows beyond the 500 displayed.
    # No security ID, source path, mutable due-days or outcome label enters it.
    unresolved=[(row["cohort_ref"],row["followup_state"],
                 row["top_k_selected_count"],row["unknown_or_censored"])
                for row in rows if row["followup_state"] in FOLLOWUP_REQUIRED]
    due_digest=sha256(json.dumps(sorted(unresolved),sort_keys=True,
                           separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return {
        "schema_version":SCHEMA,
        "status":"LOCAL_DUE_EVIDENCE_GAPS_NOT_CERTIFIED" if due_gaps
                 else "LOCAL_DUE_EVIDENCE_QUEUE_NOT_CERTIFIED",
        "evaluated_at_utc":assessed.isoformat(),
        "first_write_index_verified":strict.get("first_write_receipts_verified") is True,
        "native_watch_score_rechecked":strict.get("local_native_score_provenance_complete") is True,
        "strict_registry_count":strict["registry_manifest_count"],
        "cohorts_evaluated_all":totals.get("cohorts",0),
        "original_frozen_k_denominator":totals.get("k",0),
        "horizon_elapsed_cohorts":totals.get("due_cohorts",0),
        "horizon_elapsed_frozen_k":totals.get("due_k",0),
        "due_evidence_followups":due_gaps,
        "due_evidence_followup_k":totals.get("due_gap_k",0),
        "due_evidence_state_sha256":due_digest,
        "due_unknown_or_censored_k":totals.get("due_unknown",0),
        "all_unknown_or_censored_k":totals.get("unknown",0),
        "followup_state_counts":statuses,
        "followup_rows":ordered[:MAX_DISPLAY_ROWS],
        "displayed_followup_rows":min(len(ordered),MAX_DISPLAY_ROWS),
        "followup_rows_truncated":len(ordered)>MAX_DISPLAY_ROWS,
        "local_first_write_index_head_sha256":strict["receipt_index_head_sha256"],
        "publisher_independently_authenticated":False,
        "future_leader_accuracy_certified":False,
        "real_precision_at_k":None,"official_leader_promotions":0,
        "messages_sent":0,"external_api_calls":0,
        "warning":"Every first-written cohort is counted, even if rows are display-limited. No source issuer/clock notarization or certified outcome; missing/censored never counts as a loss.",
    }


def render_due_followups(report:dict) -> str:
    if (not isinstance(report,dict) or report.get("schema_version")!=SCHEMA or
            report.get("status") not in (
                "LOCAL_DUE_EVIDENCE_GAPS_NOT_CERTIFIED",
                "LOCAL_DUE_EVIDENCE_QUEUE_NOT_CERTIFIED") or
            report.get("first_write_index_verified") is not True or
            report.get("publisher_independently_authenticated") is not False or
            report.get("future_leader_accuracy_certified") is not False or
            report.get("real_precision_at_k") is not None or
            report.get("official_leader_promotions")!=0 or
            report.get("messages_sent")!=0 or report.get("external_api_calls")!=0 or
            type(report.get("cohorts_evaluated_all")) is not int or
            type(report.get("original_frozen_k_denominator")) is not int or
            type(report.get("due_evidence_followups")) is not int or
            not isinstance(report.get("followup_rows"),list) or
            len(report["followup_rows"])>MAX_DISPLAY_ROWS):
        raise ValueError("Unsafe prospective maturity follow-up claims")
    s=lambda x:escape(str(x),quote=True)
    html_rows=[]
    for row in report["followup_rows"]:
        if (not isinstance(row,dict) or row.get("followup_state") not in STATUSES or
                row.get("market") not in ("KR","US") or
                type(row.get("cohort_position")) is not int or
                not isinstance(row.get("registry_ref"),str) or
                not isinstance(row.get("cohort_ref"),str)):
            raise ValueError("Unsafe due follow-up row")
        columns=[row["market"],row["registry_ref"],row["cohort_position"],
                 row["horizon_due_utc"],row["followup_state"],
                 row["unknown_or_censored"],
                 row["days_overdue"] if row["days_overdue"] is not None else "미만기"]
        html_rows.append("<tr>"+"".join("<td>"+s(cell)+"</td>" for cell in columns)+"</tr>")
    if not html_rows:
        html_rows=["<tr><td colspan='7'>기록된 코호트 없음</td></tr>"]
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader 전향 Top-K 결과 증빙 후속조치</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 미래 후보 만기·결과 원천 후속점검</h1></header><main>
<div class="note"><strong>로컬 연구 전용 · 공식 대장주 0 · 실제 발굴 정확도 N/A</strong>
<p>등록한 최초 Top-K 전체를 고정 분모에 보존합니다. 결과자료 누락·검열은 실패 또는 성과로
간주하지 않습니다. SHA·원천 출처 주장 일치는 외부 기관/시각 공증이 아닙니다.
실전 알림·주문·API 호출 모두 0.</p></div>
<div class="stats"><div class="stat">전체 등록 코호트<br><strong>{report["cohorts_evaluated_all"]}</strong></div>
<div class="stat">최초 선택 Top-K 분모<br><strong>{report["original_frozen_k_denominator"]}</strong></div>
<div class="stat">만기 후 증빙 후속점검<br><strong>{report["due_evidence_followups"]}</strong></div></div>
<h2>결과증빙 만기 및 누락 상태 (상위 {MAX_DISPLAY_ROWS}개 표시)</h2>
<table><thead><tr><th>시장</th><th>최초등록 SHA 참조</th><th>코호트</th><th>만기 UTC</th>
<th>증빙 상태</th><th>검열 K</th><th>만기 경과일</th></tr></thead>
<tbody>{''.join(html_rows)}</tbody></table>
<p><small>보이는 행 {report["displayed_followup_rows"]}개 · 전체 코호트 {report["cohorts_evaluated_all"]}개
· 행 제한 시에도 전체 K/누락 집계는 유지 · 검열을 성공/실패로 오인 금지.</small></p>
</main></body></html>"""


def audit_prospective_due_followups(
    registry_dir:Path, *,evaluated_at:str,
    native_config:Path|None=None, clock:datetime|None=None,
) -> dict:
    """Fail closed on any missing indexed/native source before issuing a queue."""
    now=_now(clock)
    assessed=_time(evaluated_at)
    if assessed>now:
        raise ValueError("Future prospective due follow-up cutoff forbidden")
    registry=_root(Path(registry_dir))
    if not _index_path(registry).exists():
        raise ValueError("Prospective due follow-ups require the original receipt index")
    summary=_verified_census(registry,assessed,now,native_config)
    rows,totals,first_signatures=_build_queue(registry,assessed,now)
    # Re-audit after scanning. No partially checked/rewritten first-write
    # rank, native score or outcome document can produce a "healthy" queue.
    again=_verified_census(registry,assessed,now,native_config)
    _,again_totals,second_signatures=_build_queue(registry,assessed,now)
    if (summary!=again or totals!=again_totals or
            first_signatures!=second_signatures):
        raise RuntimeError("Prospective outcome evidence revised during due follow-up audit")
    return _report(rows,totals,summary,assessed)


def publish_due_followups(report:dict, out:Path) -> dict:
    page=render_due_followups(report)
    out=Path(out).absolute()
    if out.is_symlink() or out.parent.is_symlink():
        raise ValueError("Unsafe prospective due report output folder")
    dest=out/"prospective_due_followups_research.json"
    html=out/"site"/"prospective_due_followups.html"
    if dest.is_symlink() or html.is_symlink() or html.parent.is_symlink():
        raise ValueError("Unsafe linked prospective due report path")
    _atomic_text(dest,json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    _atomic_text(html,page)
    return {"report_path":str(dest),"html_path":str(html),"messages_sent":0}
