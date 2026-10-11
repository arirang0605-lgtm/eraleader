"""6_5 local-only DRY-RUN warnings for quality weakening and SHA anomalies.

Reads the existing first-write provider quality history under its own lock.
Never edits the source, sends a message, certifies PIT, or upgrades WATCH.
A separate append-only check chain pins the previously observed source prefix:
a self-consistent rollback/replaced history is still an anomaly.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
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
from .provider_quality_history import (
    _open as history_open,
    _verified as history_verified, _strength,
    DB_NAME as HISTORY_DB, SEAL_NAME as HISTORY_SEAL,
)
from .watch_operating_reports import _atomic_text

SCHEMA="eraleader.provider_quality_watchdog.v1"
DB_NAME="provider_quality_watchdog.sqlite"
SEAL_NAME="provider_quality_watchdog_genesis.json"
REPORT_NAME="provider_quality_alerts_research.json"
ZERO="0"*64
SHA=re.compile(r"[0-9a-f]{64}\Z")
CONDITIONS={"NOT_CONFIGURED","VERIFIED","INTEGRITY_ANOMALY"}
ALERTS={
    "WATCH_GATE_BLOCKED_LOCAL","QUALITY_EVIDENCE_WEAKENED_LOCAL",
    "LOCAL_HISTORY_SHA_INTEGRITY_ANOMALY","LOCAL_HISTORY_RESTORED",
}
COLUMNS=(
    "check_no","recorded_at_utc","condition","history_event_count",
    "history_head_sha256","history_genesis_sha256",
    "trusted_event_count","trusted_head_sha256","trusted_genesis_sha256",
    "new_weakened","new_blocked","alerts_json","previous_sha256",
    "delivery_status","messages_sent","external_api_calls",
)


def _canonical(obj:object) -> bytes:
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _digest(obj:object) -> str:
    return sha256(_canonical(obj)).hexdigest()


def _now(clock:datetime|None) -> datetime:
    now=clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Quality DRY-RUN needs an aware observation time")
    return now.astimezone(timezone.utc)


def _check_time(raw:str) -> datetime:
    if type(raw) is not str:
        raise ValueError("Invalid watchdog observation clock")
    try:
        dt=datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Invalid watchdog observation clock") from exc
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset().total_seconds()!=0:
        raise ValueError("Watchdog observation must be UTC")
    return dt


def _safe_paths(project:Path) -> tuple[Path,Path,Path,Path]:
    project=Path(project).absolute()
    root=project/"output"
    if project.is_symlink() or not project.is_dir() or root.is_symlink() or not root.is_dir():
        raise ValueError("Local watchdog requires real project and output folder")
    out=root/"provider_quality_alerts"
    backups=root/"provider_quality_alerts_backups"
    control=root/"provider_quality_alerts_control"
    for p in (out,backups,control,out/"site",out/DB_NAME,out/SEAL_NAME,
              out/REPORT_NAME,out/"site"/"index.html",control/"batch.lock"):
        if p.is_symlink():
            raise ValueError("Unsafe linked quality watchdog artifact path")
    return root,out,backups,control


@contextmanager
def _source_lock(root:Path):
    # Use the SAME file lock as record_quality_snapshot but do not call its
    # pair preflight: a lost/corrupt ledger is exactly what must be alerted.
    lock=root/".provider_quality_history.lock"
    if lock.is_symlink():
        raise ValueError("Unsafe linked quality history lock")
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)


def _source_locked_snapshot(root:Path) -> tuple[list[dict]|None,str|None]:
    # Caller holds the original source lock. One absent pair is unconfigured; a
    # partial pair or a corrupt chain is handled as an integrity incident.
    dbpath=root/HISTORY_DB
    marker=root/HISTORY_SEAL
    if dbpath.is_symlink() or marker.is_symlink():
        raise ValueError("Unsafe linked quality history input")
    if not dbpath.exists() and not marker.exists():
        return None,None
    with closing(history_open(dbpath,marker,create=False)) as db:
        events=history_verified(db,marker)
    return events,sha256(marker.read_bytes()).hexdigest()


def _new_incidents(events:list[dict],start:int) -> tuple[int,int]:
    latest={}
    weakened=blocked=0
    for index,item in enumerate(events,1):
        current=item["payload"]
        market=current["market"]
        previous=latest.get(market)
        if index>start:
            if (not current["research_watch_allowed"] and
                    (previous is None or previous["research_watch_allowed"] or
                     current["blocker_counts"]!=previous["blocker_counts"])):
                blocked+=1
            if previous is not None and _strength(current)<_strength(previous):
                weakened+=1
        latest[market]=current
    return weakened,blocked


def _read_check_chain(db:sqlite3.Connection, marker:Path) -> list[dict]:
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("Damaged quality watchdog SQLite")
        raw=marker.read_bytes()
        if len(raw)>4096 or len(raw)==0:
            raise ValueError("Invalid watchdog first-write marker")
        first=json.loads(raw)
        if (type(first) is not dict or set(first)!={"schema","seed"} or
                first["schema"]!=SCHEMA or type(first["seed"]) is not str or
                not re.fullmatch("[0-9a-f]{32}",first["seed"]) or
                _canonical(first)!=raw):
            raise ValueError("Revised watchdog genesis")
        meta=dict(db.execute("SELECT name,value FROM watchdog_meta"))
        if (set(meta)!={"schema","count","head","genesis_sha256"} or
                meta["schema"]!=SCHEMA or
                meta["genesis_sha256"]!=sha256(raw).hexdigest() or
                not re.fullmatch("(0|[1-9][0-9]*)",meta["count"]) or
                int(meta["count"])>2500 or
                type(meta["head"]) is not str or not SHA.fullmatch(meta["head"])):
            raise ValueError("Damaged watchdog meta anchor")
        checks=[dict(row) for row in db.execute(
            "SELECT * FROM watchdog_checks ORDER BY check_no")]
        if len(checks)!=int(meta["count"]):
            raise ValueError("Missing watchdog check receipts")
        previous=ZERO
        last_time=None
        last_trusted=0
        for no,row in enumerate(checks,1):
            if (set(row)!=set(COLUMNS)|{"check_sha256"} or
                    row["check_no"]!=no or row["condition"] not in CONDITIONS or
                    row["previous_sha256"]!=previous or
                    row["delivery_status"]!="DRY_RUN_NEVER_SENT" or
                    type(row["messages_sent"]) is not int or row["messages_sent"]!=0 or
                    type(row["external_api_calls"]) is not int or row["external_api_calls"]!=0 or
                    type(row["trusted_event_count"]) is not int or
                    row["trusted_event_count"]<last_trusted or
                    type(row["history_event_count"]) is not int or
                    type(row["new_weakened"]) is not int or row["new_weakened"]<0 or
                    type(row["new_blocked"]) is not int or row["new_blocked"]<0):
                raise ValueError("Tampered watchdog check or delivery claim")
            for key in ("history_head_sha256","history_genesis_sha256",
                        "trusted_head_sha256","trusted_genesis_sha256"):
                if type(row[key]) is not str or not SHA.fullmatch(row[key]):
                    raise ValueError("Invalid watchdog SHA")
            at=_check_time(row["recorded_at_utc"])
            if last_time is not None and at<last_time:
                raise ValueError("Watchdog observations backdated")
            last_time=at
            alerts=json.loads(row["alerts_json"])
            if (type(alerts) is not list or len(alerts)!=len(set(alerts)) or
                    set(alerts)-ALERTS or _canonical(alerts).decode()!=row["alerts_json"]):
                raise ValueError("Forged watchdog warning codes")
            if (row["condition"]=="INTEGRITY_ANOMALY" and
                    "LOCAL_HISTORY_SHA_INTEGRITY_ANOMALY" not in alerts and
                    (no==1 or checks[no-2]["condition"]!="INTEGRITY_ANOMALY")):
                raise ValueError("Silent source integrity anomaly")
            if (row["condition"]=="VERIFIED" and
                    (row["history_event_count"]!=row["trusted_event_count"] or
                     row["history_head_sha256"]!=row["trusted_head_sha256"] or
                     row["history_genesis_sha256"]!=row["trusted_genesis_sha256"])):
                raise ValueError("Verified watchdog checkpoint mismatch")
            if _digest({name:row[name] for name in COLUMNS})!=row["check_sha256"]:
                raise ValueError("Broken watchdog SHA chain")
            last_trusted=row["trusted_event_count"]
            previous=row["check_sha256"]
        if meta["head"]!=previous:
            raise ValueError("Watchdog head SHA mismatch")
        return checks
    except (KeyError,TypeError,sqlite3.DatabaseError,json.JSONDecodeError) as exc:
        raise ValueError("Corrupt local watchdog chain") from exc


def _open_watchdog(dbfile:Path,marker:Path) -> sqlite3.Connection:
    fresh=not dbfile.exists()
    if fresh:
        raw=_canonical({"schema":SCHEMA,"seed":os.urandom(16).hex()})
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
        with os.fdopen(os.open(marker,flags,0o600),"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
    db=sqlite3.connect(dbfile.as_uri()+("?mode=rwc" if fresh else "?mode=rw"),
                       uri=True,isolation_level=None,timeout=8)
    db.row_factory=sqlite3.Row
    try:
        db.execute("PRAGMA busy_timeout=8000")
        if fresh:
            db.executescript("""
                CREATE TABLE watchdog_meta (name TEXT PRIMARY KEY NOT NULL,value TEXT NOT NULL);
                CREATE TABLE watchdog_checks (
                  check_no INTEGER PRIMARY KEY,recorded_at_utc TEXT NOT NULL,
                  condition TEXT NOT NULL,history_event_count INTEGER NOT NULL,
                  history_head_sha256 TEXT NOT NULL,history_genesis_sha256 TEXT NOT NULL,
                  trusted_event_count INTEGER NOT NULL,trusted_head_sha256 TEXT NOT NULL,
                  trusted_genesis_sha256 TEXT NOT NULL,new_weakened INTEGER NOT NULL,
                  new_blocked INTEGER NOT NULL,alerts_json TEXT NOT NULL,
                  previous_sha256 TEXT NOT NULL,delivery_status TEXT NOT NULL,
                  messages_sent INTEGER NOT NULL,external_api_calls INTEGER NOT NULL,
                  check_sha256 TEXT NOT NULL
                );
            """)
            db.executemany("INSERT INTO watchdog_meta (name,value) VALUES (?,?)",(
                ("schema",SCHEMA),("count","0"),("head",ZERO),
                ("genesis_sha256",sha256(marker.read_bytes()).hexdigest()),
            ))
        return db
    except Exception:
        db.close()
        raise


def audit_quality_watchdog(directory:Path) -> dict:
    """Verify the complete independent local DRY-RUN audit trail."""
    directory=Path(directory).absolute()
    dbfile,marker=directory/DB_NAME,directory/SEAL_NAME
    if (directory.is_symlink() or not directory.is_dir() or
            dbfile.is_symlink() or marker.is_symlink() or
            dbfile.exists()!=marker.exists() or not dbfile.exists()):
        raise ValueError("Missing/linked watchdog ledger or genesis")
    with closing(sqlite3.connect(dbfile.as_uri()+"?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        checks=_read_check_chain(db,marker)
    return {"checks":checks,"head_sha256":checks[-1]["check_sha256"] if checks else ZERO}


def _report(checks:list[dict],created:bool) -> dict:
    last=checks[-1]
    warnings=json.loads(last["alerts_json"])
    return {
        "schema_version":SCHEMA,"status":"LOCAL_PROVIDER_QUALITY_DRY_RUN_NOT_CERTIFIED",
        "condition":last["condition"],"latest_alert_types":warnings,
        "new_checks_this_run":int(created),"new_warnings_this_run":len(warnings) if created else 0,
        "new_weakened":last["new_weakened"] if created else 0,
        "new_blocked":last["new_blocked"] if created else 0,
        "history_event_count_last_verified":last["trusted_event_count"],
        "checks_recorded":len(checks),
        "check_chain_head_sha256":last["check_sha256"],
        "recent_checks":[{
            "check_no":r["check_no"],"recorded_at_utc":r["recorded_at_utc"],
            "condition":r["condition"],"alerts":json.loads(r["alerts_json"]),
            "new_weakened":r["new_weakened"],"new_blocked":r["new_blocked"],
        } for r in checks[-25:]],
        "delivery_status":"DRY_RUN_NEVER_SENT",
        "research_only":True,"local_chain_not_independent_attestation":True,
        "official_leader_promotions":0,"actual_future_leader_precision":None,
        "messages_sent":0,"external_api_calls":0,
    }


def render_quality_watchdog(report:dict) -> str:
    if (not isinstance(report,dict) or report.get("schema_version")!=SCHEMA or
            report.get("status")!="LOCAL_PROVIDER_QUALITY_DRY_RUN_NOT_CERTIFIED" or
            report.get("condition") not in CONDITIONS or
            report.get("delivery_status")!="DRY_RUN_NEVER_SENT" or
            report.get("messages_sent")!=0 or report.get("external_api_calls")!=0 or
            report.get("official_leader_promotions")!=0 or
            report.get("actual_future_leader_precision") is not None or
            report.get("research_only") is not True or
            report.get("local_chain_not_independent_attestation") is not True or
            type(report.get("checks_recorded")) is not int or
            not isinstance(report.get("recent_checks"),list) or
            len(report["recent_checks"])>25):
        raise ValueError("Unsafe quality alert renderer claim")
    rows=[]
    for r in report["recent_checks"]:
        if (r["condition"] not in CONDITIONS or
                type(r["check_no"]) is not int or
                type(r["new_weakened"]) is not int or
                type(r["new_blocked"]) is not int or
                not isinstance(r["alerts"],list) or set(r["alerts"])-ALERTS):
            raise ValueError("Untrusted quality alert receipt")
        _check_time(r["recorded_at_utc"])
        cells=(r["check_no"],r["recorded_at_utc"],r["condition"],
               ", ".join(r["alerts"]) or "NONE",r["new_weakened"],r["new_blocked"])
        rows.append("<tr>"+"".join("<td>"+escape(str(cell),quote=True)+"</td>"
                        for cell in cells)+"</tr>")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader · 6_5 품질 SHA 감시</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · DRY-RUN 품질 경고</h1></header><main>
<div class="note"><strong>공식 인증 0 · 미래 적중률 N/A · 실전 전송 0</strong>
<p>기록된 공급자 품질의 약화/후보 보류 및 로컬 SQLite·genesis SHA 위변조를 감시합니다.
모든 이벤트는 미발송 DRY-RUN입니다. 원천 공시·실제 시간 공증이나 정상 WATCH 재승격이
아니며, 공동 삭제·동시 재위조는 독립 신뢰 앵커 없이는 검증 불가합니다.</p></div>
<div class="stats"><div class="stat">현재 감시 상태<br><strong>{escape(report["condition"])}</strong></div>
<div class="stat">누적 체크포인트<br><strong>{report["checks_recorded"]}</strong></div>
<div class="stat">외부 발송<br><strong>0</strong></div></div>
<table><thead><tr><th>순번</th><th>UTC 관측</th><th>SHA 상태</th>
<th>로컬 경고</th><th>품질 약화</th><th>후보 보류</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p><small>로컬 DRY_RUN_NEVER_SENT · 실제 시장 PIT/알파 검증과 분리</small></p>
</main></body></html>"""


def run_provider_quality_watchdog(project:Path, *,clock:datetime|None=None) -> dict:
    """Scheduled opt-in monitor. Original quality history is read-only."""
    now=_now(clock)
    root,out,backups,control=_safe_paths(project)
    control.mkdir(parents=True,exist_ok=True)
    lock=control/"batch.lock"
    with lock.open("a+b") as fd:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_ALREADY_RUNNING","messages_sent":0,
                    "external_api_calls":0}
        # Pin source lock across the read, independent receipt and ZIP audit.
        with _source_lock(root):
            try:
                events,source_genesis=_source_locked_snapshot(root)
                source_error=False
            except (ValueError,sqlite3.DatabaseError,OSError):
                events,source_genesis=None,None
                source_error=True
            out.mkdir(parents=True,exist_ok=True)
            dbfile,marker=out/DB_NAME,out/SEAL_NAME
            if dbfile.exists()!=marker.exists():
                raise ValueError("Missing watchdog ledger/genesis; refusing reset")
            for p in (dbfile,marker):
                if p.is_symlink() or (p.exists() and
                    (not p.is_file() or p.stat().st_size==0)):
                    raise ValueError("Unsafe/empty watchdog receipt artifact")
            with closing(_open_watchdog(dbfile,marker)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    checks=_read_check_chain(db,marker)
                    previous=checks[-1] if checks else None
                    if previous is not None and now<_check_time(previous["recorded_at_utc"]):
                        raise ValueError("Watchdog observation clock backdated")
                    trusted_count=previous["trusted_event_count"] if previous else 0
                    trusted_head=previous["trusted_head_sha256"] if previous else ZERO
                    trusted_genesis=previous["trusted_genesis_sha256"] if previous else ZERO
                    condition="NOT_CONFIGURED"
                    weakened=blocked=0
                    alerts=[]
                    count=0;head=ZERO;genesis=ZERO
                    if source_error or (events and
                            _check_time(events[-1]["row"]["recorded_at_utc"])>now):
                        condition="INTEGRITY_ANOMALY"
                    elif events is None:
                        if trusted_genesis!=ZERO:
                            condition="INTEGRITY_ANOMALY"
                    else:
                        count=len(events)
                        head=events[-1]["row"]["event_sha256"] if events else ZERO
                        genesis=source_genesis
                        if (trusted_genesis!=ZERO and
                                (trusted_genesis!=genesis or count<trusted_count or
                                 (trusted_count and events[trusted_count-1]["row"]["event_sha256"]!=trusted_head))):
                            condition="INTEGRITY_ANOMALY"
                        else:
                            condition="VERIFIED"
                            weakened,blocked=_new_incidents(events,trusted_count)
                            trusted_count,trusted_head,trusted_genesis=count,head,genesis
                            if weakened:
                                alerts.append("QUALITY_EVIDENCE_WEAKENED_LOCAL")
                            if blocked:
                                alerts.append("WATCH_GATE_BLOCKED_LOCAL")
                    if condition=="INTEGRITY_ANOMALY":
                        if previous is None or previous["condition"]!="INTEGRITY_ANOMALY":
                            alerts.append("LOCAL_HISTORY_SHA_INTEGRITY_ANOMALY")
                    elif previous is not None and previous["condition"]=="INTEGRITY_ANOMALY":
                        if (condition=="VERIFIED" and trusted_genesis!=ZERO and
                                previous["trusted_genesis_sha256"]!=ZERO):
                            alerts.append("LOCAL_HISTORY_RESTORED")
                    changed=bool(
                        previous is None or previous["condition"]!=condition or
                        previous["trusted_event_count"]!=trusted_count or
                        previous["trusted_head_sha256"]!=trusted_head or
                        previous["trusted_genesis_sha256"]!=trusted_genesis)
                    if changed:
                        check={
                            "check_no":len(checks)+1,"recorded_at_utc":now.isoformat(),
                            "condition":condition,"history_event_count":count,
                            "history_head_sha256":head,"history_genesis_sha256":genesis,
                            "trusted_event_count":trusted_count,
                            "trusted_head_sha256":trusted_head,
                            "trusted_genesis_sha256":trusted_genesis,
                            "new_weakened":weakened,"new_blocked":blocked,
                            "alerts_json":_canonical(alerts).decode(),
                            "previous_sha256":previous["check_sha256"] if previous else ZERO,
                            "delivery_status":"DRY_RUN_NEVER_SENT",
                            "messages_sent":0,"external_api_calls":0,
                        }
                        check_hash=_digest(check)
                        db.execute(
                            "INSERT INTO watchdog_checks ("+
                            ",".join(COLUMNS)+",check_sha256) VALUES ("+
                            ",".join("?" for _ in range(len(COLUMNS)+1))+")",
                            (*(check[key] for key in COLUMNS),check_hash))
                        db.execute("UPDATE watchdog_meta SET value=? WHERE name='count'",
                                   (str(check["check_no"]),))
                        db.execute("UPDATE watchdog_meta SET value=? WHERE name='head'",
                                   (check_hash,))
                    checks=_read_check_chain(db,marker)
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            report=_report(checks,changed)
            page=render_quality_watchdog(report)
            _atomic_text(out/"site"/"index.html",page)
            _atomic_text(out/REPORT_NAME,json.dumps(
                report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
            backups.mkdir(parents=True,exist_ok=True)
            archive=backups/("quality_alerts_"+
                 datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")+
                 "_"+uuid.uuid4().hex[:8]+".zip")
            create_backup(out,archive)
            verified=verify_backup(archive)
            if verified["status"]!="LOCAL_BACKUP_VERIFIED":
                raise RuntimeError("Quality watchdog backup not verified")
            saved=audit_quality_watchdog(out)
            if saved["head_sha256"]!=checks[-1]["check_sha256"]:
                raise RuntimeError("Watchdog changed during backup")
            return {
                "status":"LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP",
                "condition":condition,"new_warnings":report["new_warnings_this_run"],
                "new_weakened":report["new_weakened"],"new_blocked":report["new_blocked"],
                "checks_recorded":len(checks),"archive":str(archive),
                "messages_sent":0,"external_api_calls":0,
                "official_leaders_confirmed":0,
                "actual_future_leader_skill_certified":False,
                "local_artifacts_only":True,
            }
