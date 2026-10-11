"""6_5: optional local DRY-RUN warnings for due prospective Top-K evidence.

Only strict, first-write-indexed (and where required native-WATCH-verified)
5_5 cohort audits can create a healthy checkpoint. Missing/untrusted sources
create LOCAL audit-blocked warnings, never invented negative labels.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import json
import os
import re
import sqlite3
import uuid

from .delivery import BASE_CSS
from .local_backup import create_backup, verify_backup
from .prospective_due_followups import audit_prospective_due_followups
from .prospective_census_seal import _index_path
from .ranked_discovery import _now
from .watch_operating_reports import _atomic_text

SCHEMA="eraleader.prospective_due_alerts.v1"
DB_NAME="prospective_due_alerts.sqlite"
SEAL_NAME="prospective_due_alerts_genesis.json"
REPORT_NAME="prospective_due_alerts_research.json"
ZERO="0"*64
SHA=re.compile(r"[0-9a-f]{64}\Z")
CONDITIONS={"VERIFIED_LOCAL","SOURCE_AUDIT_BLOCKED"}
WARNINGS={
    "PROSPECTIVE_DUE_EVIDENCE_GAP_LOCAL",
    "PROSPECTIVE_DUE_EVIDENCE_CHANGED_LOCAL",
    "PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL",
    "PROSPECTIVE_SOURCE_AUDIT_BLOCKED_LOCAL",
    "PROSPECTIVE_SOURCE_AUDIT_RESTORED_LOCAL",
}
FIELDS={
    "observed_at_utc","condition","binding_sha256",
    "trusted_receipt_count","trusted_receipt_head_sha256",
    "last_verified_frozen_k","last_verified_due_gaps",
    "last_verified_gap_k","last_verified_unknown_k",
    "last_verified_gap_sha256","warnings",
    "delivery_status","messages_sent","external_api_calls",
    "official_leader_promotions","real_precision_at_k",
}


def _json(obj:object) -> bytes:
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _sha(obj:object) -> str:
    return sha256(_json(obj)).hexdigest()


def _time(value:object) -> datetime:
    if type(value) is not str:
        raise ValueError("Missing due-watch UTC timestamp")
    try:
        at=datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid due-watch UTC timestamp") from exc
    if at.tzinfo is None or at.utcoffset() is None or at.utcoffset().total_seconds()!=0:
        raise ValueError("Due-watch timestamp must be UTC")
    return at


def _safe_roots(project:Path) -> tuple[Path,Path,Path]:
    root=Path(project).absolute()
    output=root/"output"
    out=output/"prospective_due_alerts"
    backup=output/"prospective_due_alerts_backups"
    control=output/"prospective_due_alerts_control"
    if root.is_symlink() or not root.is_dir() or output.is_symlink() or not output.is_dir():
        raise ValueError("Due-watch requires a real local EraLeader project")
    for p in (out,backup,control,out/"site",out/DB_NAME,out/SEAL_NAME,
              out/REPORT_NAME,out/"site"/"index.html",control/"batch.lock"):
        if p.is_symlink() or p.parent.is_symlink():
            raise ValueError("Unsafe linked local due-watch path")
    return out,backup,control


def _binding(registry_dir:Path,native_config:Path|None) -> str:
    registry=Path(registry_dir).absolute()
    proof=Path(native_config).absolute() if native_config is not None else None
    if (registry.is_symlink() or registry.parent.is_symlink() or
            (proof is not None and (proof.is_symlink() or proof.parent.is_symlink()))):
        raise ValueError("Unsafe linked due-watch first-write source")
    return _sha({"registry_dir":str(registry),"native_config":str(proof) if proof else None})


def _open(dbfile:Path,seal:Path,binding:str) -> sqlite3.Connection:
    fresh=not dbfile.exists()
    if fresh:
        marker=_json({"schema":SCHEMA,"binding_sha256":binding,
                      "first_write_nonce":os.urandom(16).hex()})
        fd=os.open(seal,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(marker)
            f.flush()
            os.fsync(f.fileno())
    db=sqlite3.connect(dbfile.as_uri()+("?mode=rwc" if fresh else "?mode=rw"),
                       uri=True,isolation_level=None,timeout=8)
    db.row_factory=sqlite3.Row
    try:
        db.execute("PRAGMA busy_timeout=8000")
        if fresh:
            db.executescript("""
                CREATE TABLE alert_meta (name TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);
                CREATE TABLE alert_checks (
                    seq INTEGER PRIMARY KEY NOT NULL,
                    payload_json TEXT NOT NULL, previous_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL
                );
            """)
            db.executemany("INSERT INTO alert_meta(name,value) VALUES (?,?)",[
                ("schema",SCHEMA),("count","0"),("head",ZERO),
                ("marker_sha256",sha256(seal.read_bytes()).hexdigest()),
                ("binding_sha256",binding),
            ])
        return db
    except Exception:
        db.close()
        raise


def _verified(db:sqlite3.Connection,seal:Path,binding:str) -> list[dict]:
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("Corrupt local due-watch SQLite pages")
        raw=seal.read_bytes()
        if not 0<len(raw)<=4096:
            raise ValueError("Invalid due-watch marker bytes")
        marker=json.loads(raw)
        if (type(marker) is not dict or
                set(marker)!={"schema","binding_sha256","first_write_nonce"} or
                marker["schema"]!=SCHEMA or marker["binding_sha256"]!=binding or
                not isinstance(marker["first_write_nonce"],str) or
                not re.fullmatch(r"[0-9a-f]{32}",marker["first_write_nonce"]) or
                raw!=_json(marker)):
            raise ValueError("Tampered due-watch genesis/binding marker")
        meta=dict(db.execute("SELECT name,value FROM alert_meta"))
        if (set(meta)!={"schema","count","head","marker_sha256","binding_sha256"} or
                meta["schema"]!=SCHEMA or meta["binding_sha256"]!=binding or
                meta["marker_sha256"]!=sha256(raw).hexdigest() or
                not re.fullmatch(r"(0|[1-9][0-9]*)",meta["count"]) or
                int(meta["count"])>50000 or not SHA.fullmatch(meta["head"])):
            raise ValueError("Corrupt due-watch head/genesis/count metadata")
        rows=[dict(row) for row in db.execute("SELECT * FROM alert_checks ORDER BY seq")]
        if len(rows)!=int(meta["count"]):
            raise ValueError("Missing/deleted due-watch receipts")
        previous=ZERO
        prior_at=None
        last=None
        for seq,row in enumerate(rows,1):
            if (set(row)!={"seq","payload_json","previous_sha256","event_sha256"} or
                    type(row["seq"]) is not int or row["seq"]!=seq or
                    type(row["payload_json"]) is not str or
                    len(row["payload_json"].encode())>20000 or
                    row["previous_sha256"]!=previous or
                    not isinstance(row["event_sha256"],str) or
                    not SHA.fullmatch(row["event_sha256"])):
                raise ValueError("Malformed local due-watch receipt")
            value=json.loads(row["payload_json"])
            if (type(value) is not dict or set(value)!=FIELDS or
                    _json(value).decode()!=row["payload_json"] or
                    value["binding_sha256"]!=binding or
                    value["condition"] not in CONDITIONS or
                    value["delivery_status"]!="DRY_RUN_NEVER_SENT" or
                    value["messages_sent"]!=0 or value["external_api_calls"]!=0 or
                    value["official_leader_promotions"]!=0 or
                    value["real_precision_at_k"] is not None or
                    type(value["warnings"]) is not list or
                    len(value["warnings"])!=len(set(value["warnings"])) or
                    set(value["warnings"])-WARNINGS):
                raise ValueError("Untrusted/fake delivered local due-watch claim")
            at=_time(value["observed_at_utc"])
            if prior_at is not None and at<prior_at:
                raise ValueError("Backdated due-watch event")
            prior_at=at
            for key in ("trusted_receipt_head_sha256","last_verified_gap_sha256"):
                if type(value[key]) is not str or not SHA.fullmatch(value[key]):
                    raise ValueError("Invalid due-watch evidence digest")
            for key in ("trusted_receipt_count","last_verified_frozen_k",
                        "last_verified_due_gaps","last_verified_gap_k",
                        "last_verified_unknown_k"):
                if type(value[key]) is not int or value[key]<0:
                    raise ValueError("Invalid due-watch fixed denominator")
            if (value["last_verified_gap_k"]>value["last_verified_frozen_k"] or
                    value["last_verified_unknown_k"]>value["last_verified_frozen_k"] or
                    value["trusted_receipt_count"]==0 and
                    value["trusted_receipt_head_sha256"]!=ZERO):
                raise ValueError("Inconsistent local due-watch evidence counts")
            if last is not None:
                if (value["trusted_receipt_count"]<last["trusted_receipt_count"] or
                        (value["trusted_receipt_count"]==last["trusted_receipt_count"] and
                         value["trusted_receipt_head_sha256"]!=last["trusted_receipt_head_sha256"])):
                    raise ValueError("Local due-watch receipt index head rolled back")
                if value["condition"]=="SOURCE_AUDIT_BLOCKED":
                    for key in ("trusted_receipt_count","trusted_receipt_head_sha256",
                                "last_verified_frozen_k","last_verified_due_gaps",
                                "last_verified_gap_k","last_verified_unknown_k",
                                "last_verified_gap_sha256"):
                        if value[key]!=last[key]:
                            raise ValueError("Untrusted due-watch audit revised trusted checkpoint")
            if value["condition"]=="SOURCE_AUDIT_BLOCKED":
                if "PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL" in value["warnings"]:
                    raise ValueError("Unverified due-watch recovery claimed")
            if _sha([seq,row["payload_json"],previous])!=row["event_sha256"]:
                raise ValueError("Broken local due-watch event SHA chain")
            previous=row["event_sha256"]
            last=value
        if previous!=meta["head"]:
            raise ValueError("Due-watch event-head mismatch")
        return rows
    except (sqlite3.DatabaseError,json.JSONDecodeError,KeyError,TypeError) as exc:
        raise ValueError("Corrupt local due-watch receipts") from exc


def _source_prefix_ok(registry:Path,expected_count:int,expected_head:str) -> bool:
    if not expected_count:
        return True
    index=_index_path(registry)
    if index.is_symlink() or not index.is_file():
        return False
    with closing(sqlite3.connect(index.as_uri()+"?mode=ro",uri=True)) as db:
        row=db.execute("SELECT event_sha256 FROM receipts WHERE seq=?",
                       (expected_count,)).fetchone()
    return bool(row and row[0]==expected_head)


def _validate_evidence(report:dict) -> None:
    # A sanitized summary still cannot be mistaken for independent PIT or
    # a complete security-level performance label.
    if (type(report) is not dict or
            report.get("first_write_index_verified") is not True or
            report.get("publisher_independently_authenticated") is not False or
            report.get("future_leader_accuracy_certified") is not False or
            report.get("official_leader_promotions")!=0 or
            report.get("messages_sent")!=0 or report.get("external_api_calls")!=0 or
            report.get("real_precision_at_k") is not None):
        raise ValueError("Untrusted prospective follow-up summary")
    for key in ("strict_registry_count","original_frozen_k_denominator",
                "due_evidence_followups","due_evidence_followup_k",
                "due_unknown_or_censored_k"):
        if type(report.get(key)) is not int or report[key]<0:
            raise ValueError("Invalid original Top-K due summary")
    if (report["due_evidence_followup_k"]>report["original_frozen_k_denominator"] or
            report["due_unknown_or_censored_k"]>report["original_frozen_k_denominator"] or
            report["strict_registry_count"]<1):
        raise ValueError("Due follow-up evidence cannot exceed first-frozen K")
    for key in ("local_first_write_index_head_sha256","due_evidence_state_sha256"):
        if type(report.get(key)) is not str or not SHA.fullmatch(report[key]):
            raise ValueError("Missing full-cohort evidence SHA")
    if report.get("status")!=(
        "LOCAL_DUE_EVIDENCE_GAPS_NOT_CERTIFIED" if report["due_evidence_followups"]
        else "LOCAL_DUE_EVIDENCE_QUEUE_NOT_CERTIFIED"):
        raise ValueError("Inconsistent prospective due status")


def _observe(now:datetime,report:dict|None,last:dict|None,binding:str,
             *,audit_failed:bool) -> dict:
    trusted_count=last["trusted_receipt_count"] if last else 0
    trusted_head=last["trusted_receipt_head_sha256"] if last else ZERO
    frozen_k=last["last_verified_frozen_k"] if last else 0
    gaps=last["last_verified_due_gaps"] if last else 0
    gap_k=last["last_verified_gap_k"] if last else 0
    unknown_k=last["last_verified_unknown_k"] if last else 0
    gap_sha=last["last_verified_gap_sha256"] if last else ZERO
    alerts=[]
    condition="SOURCE_AUDIT_BLOCKED" if audit_failed else "VERIFIED_LOCAL"
    if audit_failed:
        if last is None or last["condition"]!="SOURCE_AUDIT_BLOCKED":
            alerts.append("PROSPECTIVE_SOURCE_AUDIT_BLOCKED_LOCAL")
    else:
        assert report is not None
        if last and last["condition"]=="SOURCE_AUDIT_BLOCKED":
            alerts.append("PROSPECTIVE_SOURCE_AUDIT_RESTORED_LOCAL")
        next_gaps=report["due_evidence_followups"]
        next_gap_sha=report["due_evidence_state_sha256"]
        if next_gaps and (last is None or gap_sha!=next_gap_sha):
            alerts.append(
                "PROSPECTIVE_DUE_EVIDENCE_GAP_LOCAL" if not gaps
                else "PROSPECTIVE_DUE_EVIDENCE_CHANGED_LOCAL")
        if last and gaps and not next_gaps:
            alerts.append("PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL")
        trusted_count=report["strict_registry_count"]
        trusted_head=report["local_first_write_index_head_sha256"]
        frozen_k=report["original_frozen_k_denominator"]
        gaps=next_gaps
        gap_k=report["due_evidence_followup_k"]
        unknown_k=report["due_unknown_or_censored_k"]
        gap_sha=next_gap_sha
    return {
        "observed_at_utc":now.isoformat(),"condition":condition,
        "binding_sha256":binding,"trusted_receipt_count":trusted_count,
        "trusted_receipt_head_sha256":trusted_head,
        "last_verified_frozen_k":frozen_k,
        "last_verified_due_gaps":gaps,"last_verified_gap_k":gap_k,
        "last_verified_unknown_k":unknown_k,"last_verified_gap_sha256":gap_sha,
        "warnings":alerts,"delivery_status":"DRY_RUN_NEVER_SENT",
        "messages_sent":0,"external_api_calls":0,"official_leader_promotions":0,
        "real_precision_at_k":None,
    }


def _publish_view(rows:list[dict],new_warnings:int,out:Path) -> dict:
    last=json.loads(rows[-1]["payload_json"])
    recent=[]
    for item in rows[-30:]:
        body=json.loads(item["payload_json"])
        recent.append({
            "sequence":item["seq"],"recorded_at_utc":body["observed_at_utc"],
            "condition":body["condition"],"warning_codes":body["warnings"],
            "locally_due_followups":body["last_verified_due_gaps"],
            "locally_unknown_k":body["last_verified_unknown_k"],
        })
    result={
        "schema_version":SCHEMA,"status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_NOT_CERTIFIED",
        "condition":last["condition"],
        "last_verified_due_followups":last["last_verified_due_gaps"],
        "last_verified_due_k":last["last_verified_gap_k"],
        "last_verified_unknown_k":last["last_verified_unknown_k"],
        "original_frozen_k_last_verified":last["last_verified_frozen_k"],
        "first_write_registry_entries_last_verified":last["trusted_receipt_count"],
        "new_warnings_this_run":new_warnings,
        "historical_event_count":len(rows),
        "last_event_sha256":rows[-1]["event_sha256"],
        "recent_checks":recent,
        "delivery_status":"DRY_RUN_NEVER_SENT",
        "official_leader_promotions":0,"real_precision_at_k":None,
        "source_pit_independently_verified":False,
        "messages_sent":0,"external_api_calls":0,
        "warning":"Local verified registry only. SOURCE_AUDIT_BLOCKED retains last-known figures; do not call them current performance or assume censored outcomes are failures.",
    }
    page=render_due_alerts(result)
    _atomic_text(out/REPORT_NAME,json.dumps(
        result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    _atomic_text(out/"site"/"index.html",page)
    return result


def render_due_alerts(report:dict) -> str:
    if (type(report) is not dict or report.get("schema_version")!=SCHEMA or
            report.get("status")!="LOCAL_PROSPECTIVE_DUE_DRY_RUN_NOT_CERTIFIED" or
            report.get("condition") not in CONDITIONS or
            report.get("delivery_status")!="DRY_RUN_NEVER_SENT" or
            report.get("source_pit_independently_verified") is not False or
            report.get("official_leader_promotions")!=0 or
            report.get("real_precision_at_k") is not None or
            report.get("messages_sent")!=0 or report.get("external_api_calls")!=0 or
            not isinstance(report.get("recent_checks"),list) or
            len(report["recent_checks"])>30 or
            type(report.get("historical_event_count")) is not int):
        raise ValueError("Unsafe prospective due-alert renderer claim")
    def safe(x):return escape(str(x),quote=True)
    entries=[]
    for item in report["recent_checks"]:
        if (type(item) is not dict or item.get("condition") not in CONDITIONS or
                not isinstance(item.get("warning_codes"),list) or
                set(item["warning_codes"])-WARNINGS or
                type(item.get("sequence")) is not int):
            raise ValueError("Unsafe due-alert HTML event")
        _time(item["recorded_at_utc"])
        values=(item["sequence"],item["recorded_at_utc"],item["condition"],
                ",".join(item["warning_codes"]) or "NONE",
                item["locally_due_followups"],item["locally_unknown_k"])
        entries.append("<tr>"+"".join("<td>"+safe(v)+"</td>" for v in values)+"</tr>")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader 미래 후보 결과 증빙 DRY-RUN</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 후보 결과증빙 만기 로컬 경고</h1></header><main>
<div class="note"><strong>실전 전송 0 · 공식 대장주 0 · 미래 적중률 N/A</strong>
<p>최초 등록 코호트의 만기 뒤 부족한 자료를 추적하는 연구용 dry-run입니다.
SOURCE_AUDIT_BLOCKED인 경우 숫자는 마지막 확인 자료로 현재 정상 상태가 아닙니다.
원천 공인 PIT/시장 라벨 인증 없이는 결측·검열을 실패나 적중으로 분류하지 않습니다.</p></div>
<div class="stats"><div class="stat">원천 증거 상태<br><strong>{safe(report["condition"])}</strong></div>
<div class="stat">마지막 검증 만기 후속 건수<br><strong>{report["last_verified_due_followups"]}</strong></div>
<div class="stat">외부 발송<br><strong>0</strong></div></div>
<table><thead><tr><th>순번</th><th>로컬 UTC 기록</th><th>검증</th>
<th>미전송 이벤트</th><th>후속 건수</th><th>미확인 K</th></tr></thead>
<tbody>{''.join(entries)}</tbody></table>
<p><small>로컬 SHA 증거 체인은 외부 공급자·시계 공증이 아닙니다.</small></p>
</main></body></html>"""


def audit_due_alert_ledger(output_dir:Path,*,registry_dir:Path,
                           native_config:Path|None=None) -> dict:
    """Read-only audit for local receipt and verified backup/restore tests."""
    root=Path(output_dir).absolute()
    dbfile=root/DB_NAME
    seal=root/SEAL_NAME
    if (root.is_symlink() or not root.is_dir() or dbfile.is_symlink() or
            seal.is_symlink() or not dbfile.is_file() or not seal.is_file()):
        raise ValueError("Missing or unsafe local prospective due-alert ledger")
    binding=_binding(registry_dir,native_config)
    with closing(sqlite3.connect(dbfile.as_uri()+"?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=_verified(db,seal,binding)
    return {"total_checks":len(rows),"head_sha256":rows[-1]["event_sha256"] if rows else ZERO,
            "last":json.loads(rows[-1]["payload_json"]) if rows else None,
            "events":rows}


def run_prospective_due_alerts(project:Path, *,registry_dir:Path,
                               native_config:Path|None=None,
                               clock:datetime|None=None) -> dict:
    """Run strict full census audit and record only unsent, SHA-sealed transitions."""
    now=_now(clock)
    root=Path(project).absolute()
    out,backups,control=_safe_roots(root)
    binding=_binding(registry_dir,native_config)
    control.mkdir(parents=True,exist_ok=True)
    lock=control/"batch.lock"
    with lock.open("a+b") as file:
        try:
            fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_ALREADY_RUNNING","messages_sent":0,
                    "external_api_calls":0}
        out.mkdir(parents=True,exist_ok=True)
        dbfile=out/DB_NAME
        seal=out/SEAL_NAME
        if dbfile.exists()!=seal.exists():
            raise ValueError("Missing due-watch genesis/ledger; never reset first-write")
        for p in (dbfile,seal):
            if p.is_symlink() or (p.exists() and
                (not p.is_file() or p.stat().st_size==0)):
                raise ValueError("Unsafe due-watch ledger/marker file")
        with closing(_open(dbfile,seal,binding)) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior=_verified(db,seal,binding)
                last=json.loads(prior[-1]["payload_json"]) if prior else None
                if last and now<_time(last["observed_at_utc"]):
                    raise ValueError("Due-alert observation clock backdated")
                blocked=False
                verified=None
                try:
                    verified=audit_prospective_due_followups(
                        registry_dir,evaluated_at=now.isoformat(),
                        native_config=native_config,clock=now)
                    _validate_evidence(verified)
                    if last:
                        prev_count=last["trusted_receipt_count"]
                        prev_head=last["trusted_receipt_head_sha256"]
                        if (verified["strict_registry_count"]<prev_count or
                                not _source_prefix_ok(Path(registry_dir),prev_count,prev_head)):
                            raise ValueError("Previously verified prospective index prefix replaced")
                except (ValueError,RuntimeError,OSError,sqlite3.DatabaseError):
                    blocked=True
                row=_observe(now,verified,last,binding,audit_failed=blocked)
                # A repeated situation has NO new event and no new "delivery";
                # the newly checked wall-clock must never rewrite first history.
                changed=(last is None or row["condition"]!=last["condition"] or
                         any(row[key]!=last[key] for key in (
                           "trusted_receipt_count","trusted_receipt_head_sha256",
                           "last_verified_frozen_k","last_verified_due_gaps",
                           "last_verified_gap_k","last_verified_unknown_k",
                           "last_verified_gap_sha256")))
                if changed:
                    seq=len(prior)+1
                    prior_head=prior[-1]["event_sha256"] if prior else ZERO
                    raw=_json(row).decode()
                    head=_sha([seq,raw,prior_head])
                    db.execute("INSERT INTO alert_checks(seq,payload_json,previous_sha256,event_sha256) VALUES(?,?,?,?)",
                               (seq,raw,prior_head,head))
                    db.execute("UPDATE alert_meta SET value=? WHERE name='count'",
                               (str(seq),))
                    db.execute("UPDATE alert_meta SET value=? WHERE name='head'",
                               (head,))
                checks=_verified(db,seal,binding)
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        report=_publish_view(checks,len(row["warnings"]) if changed else 0,out)
        backups.mkdir(parents=True,exist_ok=True)
        archive=backups/("due_alerts_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")+
                         "_"+uuid.uuid4().hex[:8]+".zip")
        create_backup(out,archive)
        valid=verify_backup(archive)
        if valid["status"]!="LOCAL_BACKUP_VERIFIED" or valid["file_count"]!=4:
            raise RuntimeError("Prospective due alert backup did not verify exactly four artifacts")
        after=audit_due_alert_ledger(
            out,registry_dir=registry_dir,native_config=native_config)
        if after["head_sha256"]!=checks[-1]["event_sha256"]:
            raise RuntimeError("Prospective due-alert ledger changed after backup")
        return {
            "status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP",
            "condition":report["condition"],
            "new_warnings":report["new_warnings_this_run"],
            "total_events":report["historical_event_count"],
            "last_verified_due_followups":report["last_verified_due_followups"],
            "last_verified_unknown_k":report["last_verified_unknown_k"],
            "archive":str(archive),
            "messages_sent":0,"external_api_calls":0,
            "official_leaders_confirmed":0,
            "actual_future_leader_skill_certified":False,
            "local_artifacts_only":True,
        }
