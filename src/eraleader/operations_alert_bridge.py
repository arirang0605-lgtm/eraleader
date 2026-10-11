"""6_2/6_5: combine VERIFIED local dry-run incident evidence with operations view.

Opt-in, read-only source inspection. No market/PIT provider calls, alerts,
daemons, or official leader/precision claims. The existing overview remains
unchanged; the joined page is published into a separate derived folder.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import json
import sqlite3

from .local_backup import verify_backup
from .local_failure_outbox import (
    MODES, SCHEMA as ALERT_SCHEMA, TYPES, DELIVERY, _audit_ledger,
    _hash, _report, read_local_failure_outbox, render_local_failure_outbox,
)
from .operations_overview import (
    audit_local_operations, render_operations_overview, _unique,
)
from .watch_operating_reports import _atomic_text

SCHEMA="eraleader.operations_alert_dashboard.v1"
ALERT_STATES={
    "OUTBOX_NOT_CONFIGURED","OUTBOX_UNVERIFIED",
    "VERIFIED_LOCAL_SNAPSHOT","OUTBOX_STALE_VS_SCHEDULER",
}
PAGES={"dry_run_alerts.sqlite","dry_run_alerts_research.json","site/index.html"}
MAX_RECORD_BYTES=65536
MAX_TEXT_BYTES=2*1024*1024
MAX_DATABASE_BYTES=8*1024*1024


def _blank(state: str) -> dict:
    return {
        "evidence_state":state, "verified_local_backup":False,
        "matches_current_scheduler":None, "historical_event_count":None,
        "active_local_faults":None, "not_configured_modes":[],
        "recent_events":[], "last_observed_at_utc":None,
        "local_snapshot_only":True, "messages_sent":0,
    }


def _safe_json(path:Path,limit:int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
        raise ValueError("Missing/unsafe local outbox JSON")
    value=json.loads(path.read_bytes(),object_pairs_hook=_unique)
    if not isinstance(value,dict):
        raise ValueError("Malformed local outbox JSON")
    return value


def _safe_folder(root:Path, path:Path) -> None:
    if root.is_symlink() or (root/"output").is_symlink():
        raise ValueError("Unsafe linked operations root")
    for parent in (path,path.parent):
        if parent.is_symlink():
            raise ValueError("Unsafe linked local outbox evidence")


def _archive_sqlite_ledger(data:bytes) -> dict:
    if not 0<len(data)<=MAX_DATABASE_BYTES:
        raise ValueError("Oversized local alert SQLite snapshot")
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory=sqlite3.Row
        connection.deserialize(data)
        events,conditions,head=_audit_ledger(connection)
        return {"events":events,"conditions":conditions,"event_head_sha256":head}


def _strict_time(value:object, now:datetime) -> str:
    if not isinstance(value,str):
        raise ValueError("Missing alert snapshot UTC time")
    observed=datetime.fromisoformat(value)
    if (observed.tzinfo is None or observed.utcoffset() is None or
            observed.utcoffset()!=timedelta(0) or
            observed>now+timedelta(minutes=5)):
        raise ValueError("Invalid/future local outbox audit time")
    return observed.astimezone(timezone.utc).isoformat()


def _verified_outbox(root:Path, operations:dict, now:datetime) -> dict:
    root=root.absolute()
    parent=root/"output"
    cp=parent/"local_failure_outbox_control"/"verified.json"
    db=parent/"local_failure_outbox"/"dry_run_alerts.sqlite"
    report_file=db.parent/"dry_run_alerts_research.json"
    html_file=db.parent/"site"/"index.html"
    backup_folder=parent/"local_failure_outbox_backups"
    originals=(cp,db,report_file,html_file)
    if not any(p.exists() or p.is_symlink() for p in originals):
        return _blank("OUTBOX_NOT_CONFIGURED")
    try:
        for p in (*originals,backup_folder,html_file.parent):
            _safe_folder(root,p)
        cp_data=_safe_json(cp,MAX_RECORD_BYTES)
        if (cp_data.get("status")!="LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP" or
            type(cp_data.get("messages_sent")) is not int or cp_data["messages_sent"]!=0 or
            type(cp_data.get("external_api_calls")) is not int or cp_data["external_api_calls"]!=0 or
            cp_data.get("official_leaders_confirmed")!=0 or
            cp_data.get("actual_future_leader_skill_certified") is not False or
            cp_data.get("local_artifacts_only") is not True or
            cp_data.get("derived_pages")!=2 or
            type(cp_data.get("total_events")) is not int or
            type(cp_data.get("active_local_faults")) is not int or
            type(cp_data.get("new_events")) is not int or
            cp_data["total_events"]<0 or cp_data["active_local_faults"] not in range(4) or
            not 0<=cp_data["new_events"]<=cp_data["total_events"] or
            not isinstance(cp_data.get("not_configured_modes"),list)):
            raise ValueError("Untrusted local-only outbox completion claim")
        location=cp_data.get("archive")
        if not isinstance(location,str) or len(location)>4096:
            raise ValueError("Missing archive reference")
        archive=Path(location)
        if (not archive.is_absolute() or ".." in archive.parts or
            archive.parent!=backup_folder or archive.is_symlink() or
            not archive.is_file() or
            not archive.name.startswith("dry_run_alerts_") or archive.suffix!=".zip"):
            raise ValueError("Outbox backup path escaped approved folder")
        if verify_backup(archive).get("status")!="LOCAL_BACKUP_VERIFIED":
            raise ValueError("Unverified local outbox backup")
        with ZipFile(archive,"r") as z:
            manifest=json.loads(z.read("MANIFEST.json"),object_pairs_hook=_unique)
            if {r["path"] for r in manifest["files"]}!=PAGES or len(manifest["files"])!=3:
                raise ValueError("Unexpected local outbox archive content")
            for file,name in ((report_file,"dry_run_alerts_research.json"),
                              (html_file,"site/index.html")):
                if not file.is_file() or file.stat().st_size>MAX_TEXT_BYTES:
                    raise ValueError("Missing/oversized live outbox page")
                if file.read_bytes()!=z.read(name):
                    raise ValueError("Live incident report changed after verified backup")
            archived=_archive_sqlite_ledger(z.read("dry_run_alerts.sqlite"))
        live=read_local_failure_outbox(db)
        if live!=archived:
            raise ValueError("Live local incident chain differs from verified archive")
        report=_safe_json(report_file,MAX_TEXT_BYTES)
        report_time=_strict_time(report.get("evaluated_at_utc"),now)
        if report!=_report(live,{"evaluated_at_utc":report_time},cp_data["new_events"]):
            raise ValueError("Local alert preview contradicts sealed SQLite")
        if html_file.read_bytes()!=render_local_failure_outbox(report).encode("utf-8"):
            raise ValueError("Forged HTML local incident preview")
        conditions={r["mode"]:r for r in live["conditions"]}
        if set(conditions)!=set(MODES):
            raise ValueError("Incomplete local failure conditions")
        for row in conditions.values():
            _strict_time(row["observed_at_utc"],now)
        if (report["historical_event_count"]!=cp_data["total_events"] or
            report["active_local_faults"]!=cp_data["active_local_faults"] or
            report["not_configured_modes"]!=cp_data["not_configured_modes"]):
            raise ValueError("Outbox checkpoint disagrees with source events")
        matching=all(conditions[mode]["snapshot_sha256"]==_hash(operations["modes"][mode])
                     for mode in MODES)
        result=_blank("VERIFIED_LOCAL_SNAPSHOT" if matching else "OUTBOX_STALE_VS_SCHEDULER")
        result.update({
            "verified_local_backup":True,
            "matches_current_scheduler":matching,
            "historical_event_count":report["historical_event_count"],
            "active_local_faults":report["active_local_faults"],
            "not_configured_modes":report["not_configured_modes"],
            "last_observed_at_utc":report_time,
            "recent_events":[{
                "event_no":ev["event_no"],"mode":ev["mode"],
                "type":ev["type"],"reason":ev["reason"],
                "recorded_at_utc":ev["recorded_at_utc"],
                "delivery_status":ev["delivery_status"],
            } for ev in live["events"][-10:]],
        })
        return result
    except (OSError,ValueError,TypeError,KeyError,IndexError,RuntimeError,
            BadZipFile,sqlite3.DatabaseError,UnicodeError):
        # Preserve the independently verified scheduler view; NEVER trust
        # incident counts or success state from an unverified outbox.
        return _blank("OUTBOX_UNVERIFIED")


def audit_operations_alert_dashboard(project:Path, *,clock:datetime|None=None) -> dict:
    base=Path(project)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Operations alert dashboard requires a real project folder")
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Naive dashboard audit time")
    now=now.astimezone(timezone.utc)
    operations=audit_local_operations(base,clock=now)
    alerts=_verified_outbox(base,operations,now)
    return {
        "schema_version":SCHEMA,"evaluated_at_utc":now.isoformat(),
        "operations":operations,"local_failure_outbox":alerts,
        "actual_future_leader_skill_certified":False,
        "official_leader_promotions":0,"real_precision_at_k":None,
        "live_notifications_sent":0,"external_api_calls":0,
        "local_research_only":True,
    }


def render_operations_alert_dashboard(report:dict) -> str:
    if (report.get("schema_version")!=SCHEMA or
        report.get("local_research_only") is not True or
        report.get("actual_future_leader_skill_certified") is not False or
        report.get("official_leader_promotions")!=0 or
        report.get("real_precision_at_k") is not None or
        report.get("live_notifications_sent")!=0 or
        report.get("external_api_calls")!=0):
        raise ValueError("Unsafe official/live operations alert dashboard claim")
    ops=render_operations_overview(report["operations"])
    alerts=report["local_failure_outbox"]
    state=alerts.get("evidence_state")
    if (state not in ALERT_STATES or
        alerts.get("local_snapshot_only") is not True or
        alerts.get("messages_sent")!=0 or
        type(alerts.get("verified_local_backup")) is not bool):
        raise ValueError("Unsafe dry-run alert evidence state")
    if state in {"OUTBOX_NOT_CONFIGURED","OUTBOX_UNVERIFIED"}:
        if (alerts["verified_local_backup"] or
            alerts.get("historical_event_count") is not None or
            alerts.get("active_local_faults") is not None or
            alerts.get("matches_current_scheduler") is not None or
            alerts.get("recent_events")):
            raise ValueError("Unverified incident claims cannot display local counts")
        paragraph=("로컬 알림 원장 미설정" if state=="OUTBOX_NOT_CONFIGURED" else
                   "로컬 알림 원장·백업 검증 실패 · 장애 건수 미확인")
        body="<p>"+escape(paragraph)+" · 이벤트/장애 수 N/A</p>"
    else:
        if (alerts["verified_local_backup"] is not True or
            alerts.get("matches_current_scheduler") is not
                (state=="VERIFIED_LOCAL_SNAPSHOT") or
            type(alerts.get("historical_event_count")) is not int or
            type(alerts.get("active_local_faults")) is not int or
            not 0<=alerts["active_local_faults"]<=3 or
            not 0<=alerts["historical_event_count"] or
            not isinstance(alerts.get("recent_events"),list) or
            len(alerts["recent_events"])>10):
            raise ValueError("Invalid locally verified incident inventory")
        sync="현재 예약 근거와 일치" if alerts["matches_current_scheduler"] else (
            "예약 근거 변경됨 · 오류원장 재점검 필요")
        lines=[]
        for ev in alerts["recent_events"]:
            if (ev.get("type") not in TYPES or ev.get("mode") not in MODES or
                ev.get("delivery_status")!=DELIVERY or
                type(ev.get("event_no")) is not int):
                raise ValueError("Unsupported incident or live notification")
            lines.append("<tr>"+"".join(
                "<td>"+escape(str(ev.get(k,"N/A")))+"</td>"
                for k in ("event_no","type","mode","reason","recorded_at_utc")
            )+"</tr>")
        body=(f"<p>{escape(sync)} · 로컬 장애 모드 <strong>{alerts['active_local_faults']}</strong>"
              f" · 누적 DRY-RUN 이벤트 <strong>{alerts['historical_event_count']}</strong></p>"
              "<div class='wrap'><table><thead><tr><th>번호</th><th>유형</th>"
              "<th>모드</th><th>원인</th><th>기록(UTC)</th></tr></thead><tbody>"
              +("".join(lines) or "<tr><td colspan='5'>이벤트 없음</td></tr>")
              +"</tbody></table></div>")
    extra=("<section><h2>로컬 오류·복구 DRY-RUN 원장 (읽기 전용)</h2>"
           "<p>실제 발송 0 · 공식 대장주 0 · 실전 정밀도 N/A. "
           "오류는 로컬 백업/자료 신선도 문제이며 실제 시장 공급자 인증이 아닙니다.</p>"
           +body+"</section>")
    if ops.count("</main>")!=1:
        raise ValueError("Unrecognized safe operations HTML shell")
    return ops.replace("</main>",extra+"</main>")


def publish_operations_alert_dashboard(project:Path, *,clock:datetime|None=None) -> dict:
    base=Path(project)
    target=base/"output"/"operations_alerts"
    index=target/"site"/"index.html"
    result_path=target/"operations_alerts_research.json"
    for p in (target,target/"site",index,result_path):
        _safe_folder(base,p)
    now=clock or datetime.now(timezone.utc)
    first=audit_operations_alert_dashboard(base,clock=now)
    html=render_operations_alert_dashboard(first)
    serialized=json.dumps(first,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if audit_operations_alert_dashboard(base,clock=now)!=first:
        raise RuntimeError("Operations alerts evidence changed during read-only audit")
    _atomic_text(index,html)
    _atomic_text(result_path,serialized)
    info=first["local_failure_outbox"]
    return {
        "status":"LOCAL_OPERATIONS_ALERT_DASHBOARD_RESEARCH_ONLY",
        "alert_evidence_state":info["evidence_state"],
        "verified_alerts":info["verified_local_backup"],
        "historical_local_events":info["historical_event_count"],
        "published_derived_pages":2,
        "actual_future_leader_skill_certified":False,
        "official_leader_promotions":0,
        "live_notifications_sent":0,"external_api_calls":0,
    }
