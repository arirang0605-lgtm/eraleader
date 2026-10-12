"""6_5 scheduled, key-free first-native recovery rehearsal due watchdog.

Only the original local SHA-validated drill ledger is read. No restore,
private key, network, alert delivery, hardware action or model update.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import os
import re
import uuid

from .native_recovery_drill import (
    _inputs as _drill_inputs, _audit as _drill_audit,
    _genesis as _drill_genesis, DIR as DRILL_DIR,
)
from .native_encrypted_vault import SLOT
from .native_sha_watchdog import _bytes, _json, _new, _atomic, _utc, ZERO

SCHEMA = "eraleader.native_recovery_due_watchdog.v1"
DIR = "native_recovery_due_alerts"
STATUS = "LOCAL_NATIVE_RECOVERY_DUE_DRY_RUN_RECORDED"
STATES = frozenset({"HEALTHY", "DUE_SOON", "OVERDUE", "NEVER_TESTED",
                    "FAILED", "INVALID_EVIDENCE", "MISSING_SCAN_INPUT"})
ISSUES = frozenset({"NONE", "NEXT_DRILL_APPROACHING", "DRILL_INTERVAL_EXCEEDED",
                    "NO_SUCCESSFUL_DRILL", "LAST_REHEARSAL_FAILED",
                    "DRILL_SHA_HISTORY_UNTRUSTED", "EXPECTED_SLOT_NOT_SCANNED"})
ALERT_STATES = STATES - {"HEALTHY"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_EVENTS = 20000
MAX_SLOTS = 128


def _sha(data):
    return sha256(data).hexdigest()


def _now(clock):
    value = clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Recovery due observer requires aware local time")
    return value.astimezone(timezone.utc)


def _config(project, slots, vault, witness, cert, scratch, due_days, warn_days):
    if (type(due_days) is not int or not 1 <= due_days <= 365 or
            type(warn_days) is not int or not 0 <= warn_days < due_days):
        raise ValueError("Immutable recovery drill policy requires 1..365 due days and 0 <= warn < due")
    if type(slots) not in (list, tuple) or not 1 <= len(slots) <= MAX_SLOTS:
        raise ValueError("Specify 1..128 first-native recovery model slots")
    if any(type(slot) is not str or SLOT.fullmatch(slot) is None for slot in slots):
        raise ValueError("Recovery due observer accepts only hashed KR/US native model slots")
    if len(set(slots)) != len(slots):
        raise ValueError("Duplicate first-native model slot in recovery due schedule")
    p, _, v, w, c, s = _drill_inputs(
        project, slots[0], vault, witness, cert, scratch)
    return p, tuple(slots), v, w, c, s, due_days, warn_days


def _paths(project):
    folder = project / "output" / DIR
    site = project / "output" / "site"
    dirs = (folder, folder/"site", site)
    files = (folder/"genesis.json", folder/"first_event.json",
             folder/"history.jsonl", folder/"report.json",
             folder/".checks.lock", folder/"site"/"index.html",
             site/"native_recovery_due.html", site/"index.html")
    for path in (*dirs, *files):
        if path.is_symlink() or (path.exists() and not (
                path.is_dir() if path in dirs else path.is_file())):
            raise ValueError("Unsafe linked or replaced recovery due artifact")
    return folder, site


def _genesis(project, vault, witness, cert, scratch, due_days, warn_days):
    return {
        "schema": SCHEMA,
        "project_root_sha256": _sha(str(project).encode()),
        "vault_root_sha256": _sha(str(vault).encode()),
        "witness_root_sha256": _sha(str(witness).encode()),
        "certificate_path_sha256": _sha(str(cert).encode()),
        "scratch_root_sha256": _sha(str(scratch).encode()),
        "due_days": due_days,
        "warn_days": warn_days,
    }


def _read_drills(project, vault, witness, cert, scratch):
    """Copy verified immutable local drill evidence under its original SH lock.

    A completely absent first ledger is 'never tested', not a zero-risk pass.
    Once a due observer saw an earlier head, lost/rolled-back drills remain
    incidents even if the original files are fully deleted or replaced.
    """
    root = project/"output"/DRILL_DIR
    evidence = (root/"genesis.json", root/"history.jsonl",
                root/"first_event.json", root/"report.json", root/".checks.lock")
    if not any(item.exists() or item.is_symlink() for item in evidence):
        return [], True
    lock = root/".checks.lock"
    if lock.is_symlink() or not lock.is_file():
        return [], False
    fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Recovery rehearsal writer active; due audit skipped") from exc
        try:
            try:
                records = _drill_audit(root, _drill_genesis(
                    project, vault, witness, cert, scratch))
            except (OSError, ValueError, KeyError, TypeError):
                return [], False
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return records, True


def _blank(market, old=None):
    return {
        "market": market, "state": "INVALID_EVIDENCE",
        "issue": "DRILL_SHA_HISTORY_UNTRUSTED",
        "last_passed_at_utc": None, "next_due_at_utc": None,
        "last_attempt_at_utc": None,
        "pinned_drill_count": old["pinned_drill_count"] if old else 0,
        "pinned_drill_sha256": old["pinned_drill_sha256"] if old else ZERO,
    }


def _row(slot, records, verified, old, now, due_days, warn_days):
    market = slot[:2].upper()
    previous = old or {"pinned_drill_count": 0, "pinned_drill_sha256": ZERO}
    if not verified or (records and _utc(records[-1]["observed_at_utc"]) > now):
        return _blank(market, old)
    previously_seen = previous["pinned_drill_count"]
    # The newest original report must extend EXACTLY the previously pinned
    # historical head, not replace it with a different self-consistent ledger.
    if (previously_seen > len(records) or
            (previously_seen and records[previously_seen-1]["event_sha256"] !=
             previous["pinned_drill_sha256"])):
        return _blank(market, old)
    head = records[-1]["event_sha256"] if records else ZERO
    recent = [event for event in records
              if event["slot_sha256"] == _sha(slot.encode())]
    passed = next((event for event in reversed(recent)
                   if event["outcome"] == "PASSED"), None)
    last = recent[-1] if recent else None
    date = _utc(passed["observed_at_utc"]) if passed else None
    next_due = date + timedelta(days=due_days) if date else None
    if last and last["outcome"] == "FAILED":
        state, issue = "FAILED", "LAST_REHEARSAL_FAILED"
    elif date is None:
        state, issue = "NEVER_TESTED", "NO_SUCCESSFUL_DRILL"
    elif now >= next_due:
        state, issue = "OVERDUE", "DRILL_INTERVAL_EXCEEDED"
    elif now >= next_due - timedelta(days=warn_days):
        state, issue = "DUE_SOON", "NEXT_DRILL_APPROACHING"
    else:
        state, issue = "HEALTHY", "NONE"
    return {
        "market": market, "state": state, "issue": issue,
        "last_passed_at_utc": date.isoformat() if date else None,
        "next_due_at_utc": next_due.isoformat() if next_due else None,
        "last_attempt_at_utc": last["observed_at_utc"] if last else None,
        "pinned_drill_count": len(records),
        "pinned_drill_sha256": head,
    }


def _removed(old):
    return {
        **old,
        "state": "MISSING_SCAN_INPUT",
        "issue": "EXPECTED_SLOT_NOT_SCANNED",
    }


def _validate_row(key, row, previous=None):
    if type(key) is not str or not SHA.fullmatch(key):
        raise ValueError("Invalid anonymized first-native due watch slot")
    if (type(row) is not dict or set(row) != {
            "market", "state", "issue", "last_passed_at_utc",
            "next_due_at_utc", "last_attempt_at_utc",
            "pinned_drill_count", "pinned_drill_sha256"} or
            row["market"] not in ("KR", "US") or row["state"] not in STATES or
            row["issue"] not in ISSUES or
            type(row["pinned_drill_count"]) is not int or
            not 0 <= row["pinned_drill_count"] <= 30000 or
            type(row["pinned_drill_sha256"]) is not str or
            not SHA.fullmatch(row["pinned_drill_sha256"])):
        raise ValueError("Invalid recovery due observation")
    if (row["pinned_drill_count"] == 0) != (
            row["pinned_drill_sha256"] == ZERO):
        raise ValueError("Forged empty/nonempty recovery original SHA history")
    for field in ("last_passed_at_utc", "next_due_at_utc", "last_attempt_at_utc"):
        if row[field] is not None:
            _utc(row[field])
    if row["state"] == "HEALTHY" and (
            row["issue"] != "NONE" or
            row["last_passed_at_utc"] is None or row["next_due_at_utc"] is None or
            row["pinned_drill_count"] == 0):
        raise ValueError("Claimed healthy recovery cadence without a successful rehearsal")
    legal = {
        "HEALTHY":"NONE", "DUE_SOON":"NEXT_DRILL_APPROACHING",
        "OVERDUE":"DRILL_INTERVAL_EXCEEDED",
        "NEVER_TESTED":"NO_SUCCESSFUL_DRILL",
        "FAILED":"LAST_REHEARSAL_FAILED",
        "INVALID_EVIDENCE":"DRILL_SHA_HISTORY_UNTRUSTED",
        "MISSING_SCAN_INPUT":"EXPECTED_SLOT_NOT_SCANNED",
    }
    if row["issue"] != legal[row["state"]]:
        raise ValueError("Inconsistent due-recovery observation state")
    if row["state"] in ("HEALTHY", "DUE_SOON", "OVERDUE") and (
            row["last_passed_at_utc"] is None or row["next_due_at_utc"] is None):
        raise ValueError("Recovery due date without a positive drill")
    if row["state"] == "NEVER_TESTED" and row["last_passed_at_utc"] is not None:
        raise ValueError("Never-tested slot claims a successful recovery")
    if previous:
        if (row["pinned_drill_count"] < previous["pinned_drill_count"] or
                (row["pinned_drill_count"] == previous["pinned_drill_count"] and
                 row["pinned_drill_sha256"] != previous["pinned_drill_sha256"])):
            raise ValueError("Recovery due watcher source SHA pin revised")


def _alerts(previous, current):
    warnings = []
    for slot, row in sorted(current.items()):
        old = previous.get(slot)
        if row["state"] in ALERT_STATES:
            if (old is None or old["state"] != row["state"] or
                    old["issue"] != row["issue"]):
                warnings.append(slot+":"+row["issue"])
        elif old is not None and old["state"] in ALERT_STATES:
            warnings.append(slot+":VERIFIED_RECOVERY_DRILL_FRESH")
    return warnings


def _audit_observer(folder, expected):
    first, history = folder/"genesis.json", folder/"history.jsonl"
    if any(item.is_symlink() or not item.is_file() for item in (first, history)):
        raise ValueError("Recovery due original first SHA history missing")
    genesis_raw = first.read_bytes()
    base = _json(genesis_raw)
    if (not 0 < len(genesis_raw) <= 2048 or type(base) is not dict or
            set(base) != set(expected) | {"nonce"} or
            any(base.get(k) != v for k, v in expected.items()) or
            type(base.get("nonce")) is not str or
            re.fullmatch(r"[a-f0-9]{32}", base["nonce"]) is None or
            _bytes(base) != genesis_raw):
        raise ValueError("Recovery due first SHA policy/history genesis mismatch")
    raw = history.read_bytes()
    if len(raw) > 40_000_000 or (raw and not raw.endswith(b"\n")):
        raise ValueError("Truncated recovery due SHA history")
    events = []
    head = ZERO
    last_at = None
    for line in raw.splitlines():
        if not 0 < len(line) <= 250_000 or len(events) >= MAX_EVENTS:
            raise ValueError("Oversized local recovery due event")
        event = _json(line)
        if (type(event) is not dict or set(event) != {
                "seq", "observed_at_utc", "cohorts", "new_alerts",
                "previous_sha256", "event_sha256"} or
                type(event["seq"]) is not int or
                event["seq"] != len(events)+1 or
                event["previous_sha256"] != head or
                line+b"\n" != _bytes(event)):
            raise ValueError("Recovery due event chain replaced/truncated")
        at = _utc(event["observed_at_utc"])
        if last_at is not None and at < last_at:
            raise ValueError("Recovery due recorded clock rolled back")
        last_at = at
        cohort = event["cohorts"]
        before = events[-1]["cohorts"] if events else {}
        if (type(cohort) is not dict or not 1 <= len(cohort) <= MAX_SLOTS or
                not set(before).issubset(cohort)):
            raise ValueError("Recovery due first cohort inventory silently lost")
        for key, row in cohort.items():
            _validate_row(key, row, before.get(key))
        if (type(event["new_alerts"]) is not list or
                event["new_alerts"] != _alerts(before, cohort)):
            raise ValueError("Recovered evidence alert transitions were edited")
        raw_event = {k:v for k,v in event.items() if k != "event_sha256"}
        if event["event_sha256"] != _sha(_bytes(raw_event)):
            raise ValueError("Recovery due event chain SHA mismatch")
        head = event["event_sha256"]
        events.append(event)
    receipt = folder/"first_event.json"
    if events:
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 512:
            raise ValueError("Recovery due immutable first event receipt lost")
        body = receipt.read_bytes()
        obj = _json(body)
        if (type(obj) is not dict or set(obj) != {
                "schema", "genesis_sha256", "first_event_sha256"} or
                obj["schema"] != SCHEMA or obj["genesis_sha256"] != _sha(genesis_raw) or
                obj["first_event_sha256"] != events[0]["event_sha256"] or
                _bytes(obj) != body):
            raise ValueError("Recovery due first SHA receipt contradicts history")
    elif receipt.exists() or receipt.is_symlink():
        raise ValueError("Recovery due first event exists without history")
    report = folder/"report.json"
    if events:
        if report.is_symlink() or not report.is_file() or report.stat().st_size > 130_000:
            raise ValueError("Recovery due final SHA checkpoint lost")
        current_raw = report.read_bytes()
        current = _json(current_raw)
        last = events[-1]
        if (type(current) is not dict or current_raw != _bytes(current) or
                current.get("status") != STATUS or
                current.get("check_count") != len(events) or
                current.get("chain_head_sha256") != last["event_sha256"] or
                current.get("cohorts") != last["cohorts"] or
                current.get("new_alerts") != last["new_alerts"] or
                current.get("messages_sent") != 0 or
                current.get("external_api_calls") != 0 or
                current.get("official_leader_promotions") != 0 or
                current.get("local_artifacts_only") is not True or
                current.get("independent_market_pit_certified") is not False or
                current.get("actual_future_leader_skill_certified") is not False):
            raise ValueError("Recovery due reported checkpoint/history rolled back")
    elif report.exists() or report.is_symlink():
        raise ValueError("Recovery due last SHA checkpoint exists without history")
    return events


def _html(report):
    rows = "".join(
        "<tr><td>"+escape(item["market"])+"</td><td>"+escape(key[:12])+
        "</td><td>"+escape(item["state"])+"</td><td>"+escape(item["issue"])+
        "</td><td>"+escape(item["next_due_at_utc"] or "N/A")+"</td></tr>"
        for key, item in sorted(report["cohorts"].items()))
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>EraLeader encrypted recovery cadence</title>"
            "<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem}"
            "table{border-collapse:collapse;width:100%}td,th{padding:10px;"
            "border-bottom:1px solid #bbb}</style>"
            "<h1>Native original recovery drill · local DRY-RUN cadence</h1>"
            "<p>Only original first-recovery SHA evidence is read. No private key, "
            "decryption, official issuer PIT, automatic messages or orders.</p>"
            "<p>Checks: "+str(report["check_count"])+" | cohorts: "+
            str(len(report["cohorts"]))+" | new alerts: "+
            str(len(report["new_alerts"]))+"</p>"
            "<a href='index.html'>EraLeader research dashboard</a>"
            "<table><tr><th>Market</th><th>Slot SHA</th><th>Health</th>"
            "<th>Issue</th><th>Next rehearsal due (UTC)</th></tr>"+
            rows+"</table></html>")


def verify_recovery_due_history(project, vault, witness, cert, scratch, *,
                                due_days=30, warn_days=7):
    """Read-only integrity check of the independent due observer's SHA chain."""
    p,_,v,w,c,s,due,warn = _config(
        project, ["kr_"+"0"*24], vault, witness, cert, scratch, due_days, warn_days)
    folder,_ = _paths(p)
    lock = folder/".checks.lock"
    if lock.is_symlink() or not lock.is_file():
        raise ValueError("Missing recovery due original watcher lock")
    fd = os.open(lock, os.O_RDONLY | getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent recovery due SHA writer") from exc
        try:
            records = _audit_observer(folder, _genesis(p,v,w,c,s,due,warn))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {
        "status": "LOCAL_RECOVERY_DUE_SHA_CHAIN_VERIFIED",
        "check_count": len(records),
        "chain_verified": True,
        "messages_sent": 0, "external_api_calls": 0,
        "official_leader_promotions": 0,
    }


def run_recovery_due_watchdog(project, slots, vault, witness, cert, scratch, *,
                              due_days=30, warn_days=7, clock=None):
    """Opt-in key-free periodic warning; no actual recovery is scheduled."""
    now = _now(clock)
    p,slots,v,w,c,s,due,warn = _config(
        project, slots, vault, witness, cert, scratch, due_days, warn_days)
    folder,site = _paths(p)
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    (folder/"site").mkdir(mode=0o700, exist_ok=True)
    lock = folder/".checks.lock"
    lock_existed=lock.exists()
    if not lock_existed and ((folder/"genesis.json").exists() or
                             (folder/"history.jsonl").exists()):
        raise ValueError("Recovery due independent first-write lock missing")
    fd=os.open(lock,os.O_CREAT | os.O_RDWR | getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent recovery due observation") from exc
        try:
            genesis,history=folder/"genesis.json",folder/"history.jsonl"
            if not genesis.exists() and not history.exists():
                if lock_existed:
                    raise ValueError("Recovery due previous first history deleted")
                _new(genesis, _bytes({**_genesis(p,v,w,c,s,due,warn),
                                      "nonce": uuid.uuid4().hex}))
                _new(history, b"")
            previous=_audit_observer(folder,_genesis(p,v,w,c,s,due,warn))
            if previous and now < _utc(previous[-1]["observed_at_utc"]):
                raise ValueError("Recovery due observer local clock rollback")
            previous_rows=previous[-1]["cohorts"] if previous else {}
            ids={_sha(slot.encode()):slot for slot in slots}
            if len(set(previous_rows)|set(ids)) > MAX_SLOTS:
                raise ValueError("Recovery due monitored cohorts exceed 128")
            original_events,verified = _read_drills(p,v,w,c,s)
            snapshot={}
            for key in sorted(set(previous_rows)|set(ids)):
                if key not in ids:
                    snapshot[key]=_removed(previous_rows[key])
                else:
                    snapshot[key]=_row(
                        ids[key],original_events,verified,previous_rows.get(key),
                        now,due,warn)
            alerts=_alerts(previous_rows,snapshot)
            event={
                "seq":len(previous)+1,"observed_at_utc":now.isoformat(),
                "cohorts":snapshot,"new_alerts":alerts,
                "previous_sha256":previous[-1]["event_sha256"] if previous else ZERO,
            }
            event["event_sha256"]=_sha(_bytes(event))
            with open(history,"ab",buffering=0) as out:
                out.write(_bytes(event))
                os.fsync(out.fileno())
            if not previous:
                _new(folder/"first_event.json",_bytes({
                    "schema":SCHEMA,"genesis_sha256":_sha(genesis.read_bytes()),
                    "first_event_sha256":event["event_sha256"],
                }))
            result={
                "status": STATUS,
                "check_count":len(previous)+1,
                "chain_head_sha256":event["event_sha256"],
                "cohorts":snapshot,"new_alerts":alerts,
                "local_artifacts_only":True,
                "independent_market_pit_certified":False,
                "actual_future_leader_skill_certified":False,
                "official_leader_promotions":0,
                "messages_sent":0,"external_api_calls":0,
            }
            _atomic(folder/"report.json",_bytes(result))
            if len(_audit_observer(folder,_genesis(p,v,w,c,s,due,warn))) != event["seq"]:
                raise RuntimeError("Recovery due SHA append verification inconsistent")
            _atomic(folder/"site"/"index.html",_html(result).encode())
            if site.exists():
                page,index=site/"native_recovery_due.html",site/"index.html"
                _atomic(page,_html(result).encode())
                if index.is_file() and index.stat().st_size <= 1_000_000:
                    raw_index=index.read_text(encoding="utf-8")
                    if "native_recovery_due.html" not in raw_index and "</body>" in raw_index:
                        anchor=("<p><a href='native_recovery_due.html'>"
                                "Recovery DRILL due SHA DRY-RUN</a></p>")
                        _atomic(index,raw_index.replace("</body>",anchor+"</body>",1).encode())
            return result
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
