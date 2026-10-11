"""6_4/6_5: local-only DATA_FAILURE research outbox and artifact repair notices.

Input is a READ-ONLY audit of existing KR+US scheduler checkpoints, validated
backup ZIPs and local derived pages. No source PIT attestation, no live
notifications, no ordering, no external data or user contact information.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from typing import Any
import fcntl
import json
import os
import sqlite3
import uuid

from .delivery import BASE_CSS
from .local_backup import create_backup, verify_backup
from .operations_overview import (
    STATES, MODES, audit_local_operations, render_operations_overview,
)
from .watch_operating_reports import _atomic_text

DB_NAME="dry_run_alerts.sqlite"
REPORT_NAME="dry_run_alerts_research.json"
SCHEMA="eraleader.local_failure_outbox.v1"
ZERO="0"*64
CHANNEL="LOCAL_PREVIEW_ONLY"
DELIVERY="DRY_RUN_NEVER_SENT"
FAILED_STATES=STATES-{"NO_CHECKPOINT","SOURCE_NOT_RECHECKED"}
CONDITIONS={"UNCONFIGURED","BLOCKED","LOCAL_EVIDENCE_ONLY"}
TYPES={"DATA_FAILURE_LOCAL","LOCAL_ARTIFACTS_RESTORED"}
MAX_EVENTS_PER_PAGE=50


def _canonical(value:object) -> bytes:
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _hash(value:object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _check_sha(value:object) -> bool:
    return (type(value) is str and len(value)==64 and
            all(char in "0123456789abcdef" for char in value))


def _valid_snapshot(report:dict) -> None:
    # Reuse the existing 6_2 renderer's high-level fail-closed contract.
    render_operations_overview(report)
    for mode in MODES:
        row=report["modes"][mode]
        state=row["state"]
        matched=row["archive_live_bytes_matched"]
        if (state in {"SOURCE_NOT_RECHECKED","STALE_PRICE_OBSERVATIONS",
                      "OUTDATED_RESEARCH_SNAPSHOT"})!=matched:
            raise ValueError("Contradictory archive SHA/mode evidence in operations snapshot")
        if state not in STATES:
            raise ValueError("Unrecognized operations audit state")


def _paths(root:Path) -> tuple[Path,Path,Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Local outbox requires existing real project")
    out=root/"output"/"local_failure_outbox"
    control=root/"output"/"local_failure_outbox_control"
    backups=root/"output"/"local_failure_outbox_backups"
    for p in (root/"output",out,control,backups,out/"site",
              control/"batch.lock",control/"verified.json",
              out/DB_NAME,out/REPORT_NAME,out/"site"/"index.html"):
        if p.is_symlink() or p.parent.is_symlink():
            raise ValueError("Unsafe linked local failure outbox path")
    return out,control,backups


def _open_database(file:Path) -> sqlite3.Connection:
    if file.is_symlink() or file.parent.is_symlink():
        raise ValueError("Linked local alert ledger forbidden")
    fresh=not file.exists()
    if not fresh and (not file.is_file() or file.stat().st_size==0):
        raise ValueError("Corrupt local alert ledger file")
    mode="rwc" if fresh else "rw"
    db=sqlite3.connect(file.as_uri()+f"?mode={mode}",uri=True,timeout=3,
                       isolation_level=None)
    db.row_factory=sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=3000")
        if fresh:
            db.executescript("""
                CREATE TABLE meta (
                    name TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL
                );
                CREATE TABLE alert_events (
                    event_no INTEGER PRIMARY KEY,
                    event_id TEXT UNIQUE NOT NULL,
                    mode TEXT NOT NULL,
                    type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL,
                    previous_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    delivery_channel TEXT NOT NULL,
                    delivery_status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    sent_at_utc TEXT
                );
                CREATE TABLE mode_conditions (
                    mode TEXT PRIMARY KEY NOT NULL,
                    condition TEXT NOT NULL,
                    reason TEXT,
                    snapshot_sha256 TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL
                );
            """)
            db.executemany("INSERT INTO meta (name,value) VALUES (?,?)",(
                ("schema",SCHEMA),("event_count","0"),("event_head",ZERO),
                ("conditions_sha256",_hash([])),
            ))
        _audit_ledger(db)
        return db
    except Exception:
        db.close()
        raise


def _rows(db:sqlite3.Connection,table:str) -> list[dict]:
    return [dict(row) for row in db.execute(
        "SELECT * FROM alert_events ORDER BY event_no" if table=="alert_events"
        else "SELECT * FROM mode_conditions ORDER BY mode"
    )]


def _event_content(row:dict) -> dict:
    return {key:row[key] for key in (
        "event_no","event_id","mode","type","reason","recorded_at_utc",
        "snapshot_sha256","previous_sha256","delivery_channel",
        "delivery_status","attempt_count","sent_at_utc"
    )}


def _check_mode_rows(rows:list[dict]) -> None:
    if len(rows)>len(MODES) or len({r["mode"] for r in rows})!=len(rows):
        raise ValueError("Corrupt local alert conditions inventory")
    for row in rows:
        if (row["mode"] not in MODES or row["condition"] not in CONDITIONS or
            not _check_sha(row["snapshot_sha256"]) or
            not isinstance(row["observed_at_utc"],str) or
            not row["observed_at_utc"].endswith("+00:00") or
            (row["condition"]=="BLOCKED")!=(row["reason"] is not None)):
            raise ValueError("Corrupt local alert mode conditions")
        if row["reason"] is not None and row["reason"] not in (
            FAILED_STATES | {"NO_CHECKPOINT_AFTER_PRIOR_RUN"}):
            raise ValueError("Corrupt local alert blocked reason")


def _audit_ledger(db:sqlite3.Connection) -> tuple[list[dict],list[dict],str]:
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("Corrupt local alert SQLite pages")
        meta=dict(db.execute("SELECT name,value FROM meta").fetchall())
        if set(meta)!={"schema","event_count","event_head","conditions_sha256"}:
            raise ValueError("Corrupt local alert schema metadata")
        if meta["schema"]!=SCHEMA or not meta["event_count"].isdigit():
            raise ValueError("Corrupt local alert schema/version")
        recorded=_rows(db,"alert_events")
        conditions=_rows(db,"mode_conditions")
        _check_mode_rows(conditions)
        if (_hash(conditions)!=meta["conditions_sha256"] or
            len(recorded)!=int(meta["event_count"])):
            raise ValueError("Corrupt local alert count/state seal")
        previous=ZERO
        for number,row in enumerate(recorded,1):
            if (row["event_no"]!=number or row["mode"] not in MODES or
                row["type"] not in TYPES or
                row["reason"] not in (FAILED_STATES |
                    {"SOURCE_NOT_RECHECKED","NO_CHECKPOINT_AFTER_PRIOR_RUN"}) or
                row["delivery_channel"]!=CHANNEL or
                row["delivery_status"]!=DELIVERY or
                type(row["attempt_count"]) is not int or
                row["attempt_count"]!=0 or row["sent_at_utc"] is not None or
                not _check_sha(row["snapshot_sha256"]) or
                not _check_sha(row["event_id"]) or
                row["previous_sha256"]!=previous):
                raise ValueError("Corrupt/delivered local-only alert event")
            fields=_event_content(row)
            if (row["event_id"]!=_hash({k:v for k,v in fields.items()
                                       if k!="event_id"}) or
                row["event_sha256"]!=_hash(fields)):
                raise ValueError("Corrupt local alert SHA chain")
            previous=row["event_sha256"]
        if previous!=meta["event_head"]:
            raise ValueError("Corrupt local alert event head anchor")
        return recorded,conditions,previous
    except sqlite3.DatabaseError as exc:
        raise ValueError("Corrupt local alert SQLite schema or data") from exc


def read_local_failure_outbox(file:Path) -> dict:
    """Read and verify every event/delivery field and conditions SHA anchor."""
    path=Path(file).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked local alert outbox")
    db=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
    db.row_factory=sqlite3.Row
    try:
        events,states,head=_audit_ledger(db)
        return {"events":events,"conditions":states,"event_head_sha256":head}
    finally:
        db.close()


def _condition(mode:str,state:str,previous:dict|None) -> tuple[str,str|None]:
    if state=="NO_CHECKPOINT":
        if previous is None or previous["condition"]=="UNCONFIGURED":
            return "UNCONFIGURED",None
        # A once-observed operating record disappearing is a failure, not
        # a successful recovery and not a fresh unconfigured installation.
        return "BLOCKED","NO_CHECKPOINT_AFTER_PRIOR_RUN"
    if state=="SOURCE_NOT_RECHECKED":
        return "LOCAL_EVIDENCE_ONLY",None
    return "BLOCKED",state


def _append_event(db:sqlite3.Connection,*,number:int,mode:str,
                  type:str,reason:str,at:str,evidence:str,previous:str) -> str:
    body={
        "event_no":number,"mode":mode,"type":type,"reason":reason,
        "recorded_at_utc":at,"snapshot_sha256":evidence,
        "previous_sha256":previous,"delivery_channel":CHANNEL,
        "delivery_status":DELIVERY,"attempt_count":0,"sent_at_utc":None,
    }
    body["event_id"]=_hash(body)
    event_hash=_hash(body)
    db.execute("""
        INSERT INTO alert_events (
            event_no,event_id,mode,type,reason,recorded_at_utc,snapshot_sha256,
            previous_sha256,event_sha256,delivery_channel,delivery_status,
            attempt_count,sent_at_utc
        ) VALUES (:event_no,:event_id,:mode,:type,:reason,:recorded_at_utc,
                  :snapshot_sha256,:previous_sha256,:event_sha256,
                  :delivery_channel,:delivery_status,:attempt_count,:sent_at_utc)
    """,{**body,"event_sha256":event_hash})
    return event_hash


def _record_snapshot(db:sqlite3.Connection,report:dict,now:datetime) -> int:
    recorded,conditions,head=_audit_ledger(db)
    previous_modes={r["mode"]:r for r in conditions}
    at=now.isoformat()
    for row in conditions:
        if at < row["observed_at_utc"]:
            raise ValueError("Cannot backdate existing local alert clock")
    created=0
    for mode in MODES:
        state=report["modes"][mode]["state"]
        before=previous_modes.get(mode)
        condition,reason=_condition(mode,state,before)
        evidence=_hash(report["modes"][mode])
        kind=None
        if condition=="BLOCKED" and (
            before is None or before["condition"]!="BLOCKED" or
            before["reason"]!=reason
        ):
            kind="DATA_FAILURE_LOCAL"
        elif (condition=="LOCAL_EVIDENCE_ONLY" and before is not None and
              before["condition"]=="BLOCKED"):
            kind="LOCAL_ARTIFACTS_RESTORED"
        if kind:
            number=len(recorded)+created+1
            head=_append_event(
                db,number=number,mode=mode,type=kind,
                reason=reason if kind=="DATA_FAILURE_LOCAL" else state,
                at=at,evidence=evidence,previous=head,
            )
            created+=1
        db.execute("""
            INSERT INTO mode_conditions (mode,condition,reason,snapshot_sha256,observed_at_utc)
            VALUES (?,?,?,?,?)
            ON CONFLICT(mode) DO UPDATE SET
            condition=excluded.condition,reason=excluded.reason,
            snapshot_sha256=excluded.snapshot_sha256,
            observed_at_utc=excluded.observed_at_utc
        """,(mode,condition,reason,evidence,at))
    current=_rows(db,"mode_conditions")
    db.executemany("UPDATE meta SET value=? WHERE name=?",(
        (str(len(recorded)+created),"event_count"),
        (head,"event_head"),
        (_hash(current),"conditions_sha256"),
    ))
    _audit_ledger(db)
    return created


def _report(ledger:dict, snapshot:dict,created:int) -> dict:
    states={row["mode"]:{"condition":row["condition"],"reason":row["reason"]}
            for row in ledger["conditions"]}
    active=sum(row["condition"]=="BLOCKED" for row in ledger["conditions"])
    return {
        "schema_version":SCHEMA,
        "status":"LOCAL_DRY_RUN_ALERTS_NOT_SOURCE_CERTIFIED",
        "evaluated_at_utc":snapshot["evaluated_at_utc"],
        "mode_conditions":states,
        "active_local_faults":active,
        "not_configured_modes":sorted(m for m,v in states.items()
                                      if v["condition"]=="UNCONFIGURED"),
        "new_events_this_run":created,
        "historical_event_count":len(ledger["events"]),
        "historical_event_head_sha256":ledger["event_head_sha256"],
        "recent_events":[{
            "event_no":ev["event_no"],"event_id":ev["event_id"],
            "type":ev["type"],"mode":ev["mode"],"reason":ev["reason"],
            "recorded_at_utc":ev["recorded_at_utc"],
            "delivery_status":ev["delivery_status"],"attempt_count":ev["attempt_count"],
        } for ev in ledger["events"][-MAX_EVENTS_PER_PAGE:]],
        "research_only":True,"independent_market_pit_certified":False,
        "actual_future_leader_skill_certified":False,
        "official_leader_promotions":0,"live_notifications_sent":0,
        "messages_sent":0,"external_api_calls":0,"precision_at_k":None,
    }


def render_local_failure_outbox(report:dict) -> str:
    if (report.get("schema_version")!=SCHEMA or
        report.get("status")!="LOCAL_DRY_RUN_ALERTS_NOT_SOURCE_CERTIFIED" or
        report.get("research_only") is not True or
        report.get("independent_market_pit_certified") is not False or
        report.get("actual_future_leader_skill_certified") is not False or
        report.get("official_leader_promotions")!=0 or
        report.get("messages_sent")!=0 or
        report.get("live_notifications_sent")!=0 or
        report.get("external_api_calls")!=0 or report.get("precision_at_k") is not None):
        raise ValueError("Unsafe local outbox performance/delivery claim")
    entries=report.get("recent_events")
    states=report.get("mode_conditions")
    if (not isinstance(entries,list) or len(entries)>MAX_EVENTS_PER_PAGE or
        not isinstance(states,dict) or set(states)!=set(MODES) or
        type(report.get("historical_event_count")) is not int or
        type(report.get("active_local_faults")) is not int or
        report["active_local_faults"]!=sum(
            row["condition"]=="BLOCKED" for row in states.values())):
        raise ValueError("Invalid dry-run alert preview contents")
    lines=[]
    for item in entries:
        if (item["type"] not in TYPES or item["reason"] not in (
            FAILED_STATES | {"NO_CHECKPOINT_AFTER_PRIOR_RUN","SOURCE_NOT_RECHECKED"}) or
            item["mode"] not in MODES or item["delivery_status"]!=DELIVERY or
            item["attempt_count"]!=0):
            raise ValueError("A real delivery or fabricated local event cannot be shown")
        lines.append("<tr>"+"".join("<td>"+escape(str(item[k]))+"</td>" for k in (
            "event_no","type","mode","reason","recorded_at_utc","delivery_status"
        ))+"</tr>")
    rows="".join(lines) or "<tr><td colspan='6'>발송하지 않은 신규 오류 이벤트 없음</td></tr>"
    state_rows="".join(
        "<tr>"+"".join("<td>"+escape(str(value))+"</td>" for value in (
            mode,states[mode]["condition"],states[mode]["reason"] or "N/A"
        ))+"</tr>" for mode in MODES
    )
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader · 로컬 오류·복구 알림 원장</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 연구 오류 알림 미리보기</h1>
<div>한국·미국 로컬 관측 · 실제 전송 없는 dry-run 기록</div></header><main>
<div class="note"><strong>실전 적중률 N/A · 원천 PIT 미인증 · 공식 대장주 0</strong>
<p>오류(DATA_FAILURE_LOCAL)는 로컬 자료/보고서의 지연·무결성 문제만 의미합니다.
복구(LOCAL_ARTIFACTS_RESTORED)는 ZIP과 현재 페이지의 로컬 일치만 의미하며,
<strong>실제 시장 원천 복구 또는 PIT 인증 아님</strong>. 어떠한 주문·이메일·메시지도 보내지 않습니다.</p></div>
<div class="stats"><div class="stat">현재 로컬 오류 모드<br><strong>{report["active_local_faults"]}</strong></div>
<div class="stat">누적 dry-run 이벤트<br><strong>{report["historical_event_count"]}</strong></div>
<div class="stat">외부 발송<br><strong>0</strong></div></div>
<h2>현재 로컬 관측</h2><div class="wrap"><table><thead>
<tr><th>모드</th><th>조건</th><th>원인</th></tr></thead><tbody>{state_rows}</tbody></table></div>
<h2>최근 오류/로컬 파일 복구(최대 {MAX_EVENTS_PER_PAGE}건)</h2><div class="wrap">
<table><thead><tr><th>순번</th><th>이벤트</th><th>모드</th><th>원인</th>
<th>UTC 기록시각</th><th>전송 상태</th></tr></thead><tbody>{rows}</tbody></table></div>
<p><small>상태 점검 UTC {escape(str(report["evaluated_at_utc"]))}. 누적 이벤트는 내부 SQLite
체인 SHA/카운트 검증을 거친 로컬 연구 로그입니다. 외부 원본 공증·발견 성과·매매 신호 아님.</small></p>
</main><footer>EraLeader · DRY_RUN_NEVER_SENT · local-only</footer></body></html>"""


def run_local_failure_outbox(
    project:Path, *,clock:datetime|None=None,
) -> dict:
    """Capture exactly one observed state transition per mode; never send.

    The archive is made only from an allowlisted SQLite snapshot, sanitized
    research JSON and static HTML. Checkpoint commits AFTER a verified backup.
    """
    root=Path(project).absolute()
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Local outbox requires timezone-aware observation clock")
    now=now.astimezone(timezone.utc)
    out,control,backup_dir=_paths(root)
    first=audit_local_operations(root,clock=now)
    _valid_snapshot(first)
    if audit_local_operations(root,clock=now)!=first:
        raise RuntimeError("Operations evidence changed during initial audit")
    control.mkdir(parents=True,exist_ok=True)
    with (control/"batch.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_ALREADY_RUNNING","new_events":0,
                    "messages_sent":0,"external_api_calls":0}
        # Lock serializes both SQLite writes and derived backup publication.
        out.mkdir(parents=True,exist_ok=True)
        db=_open_database(out/DB_NAME)
        try:
            db.execute("BEGIN IMMEDIATE")
            try:
                if audit_local_operations(root,clock=now)!=first:
                    raise RuntimeError("Operations evidence revised while event transaction open")
                created=_record_snapshot(db,first,now)
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()
        ledger=read_local_failure_outbox(out/DB_NAME)
        report=_report(ledger,first,created)
        page=render_local_failure_outbox(report)
        _atomic_text(out/"site"/"index.html",page)
        _atomic_text(out/REPORT_NAME,json.dumps(
            report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
        backup_dir.mkdir(parents=True,exist_ok=True)
        archive=backup_dir/(
            "dry_run_alerts_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            +"_"+uuid.uuid4().hex[:8]+".zip"
        )
        create_backup(out,archive)
        verified=verify_backup(archive)
        if verified["status"]!="LOCAL_BACKUP_VERIFIED":
            raise RuntimeError("Local failure outbox backup not verified")
        if audit_local_operations(root,clock=now)!=first:
            raise RuntimeError("Operations evidence changed during dry-run backup")
        if read_local_failure_outbox(out/DB_NAME)["event_head_sha256"]!=ledger["event_head_sha256"]:
            raise RuntimeError("Local failure outbox ledger changed during backup")
        result={
            "status":"LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP",
            "new_events":created,
            "total_events":len(ledger["events"]),
            "active_local_faults":report["active_local_faults"],
            "not_configured_modes":report["not_configured_modes"],
            "archive":str(archive),
            "derived_pages":2,
            "messages_sent":0,"external_api_calls":0,
            "official_leaders_confirmed":0,
            "actual_future_leader_skill_certified":False,
            "local_artifacts_only":True,
        }
        _atomic_text(control/"verified.json",json.dumps(
            result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
        return result
