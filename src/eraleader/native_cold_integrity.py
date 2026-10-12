"""6_5 optional periodic full ciphertext-custody verification with cross-device SHA PIN.

The pin is first-written only after the caller supplies a *previously trusted*
package SHA256. Scheduled scans read that pin: they never adopt a new digest.
No private key, plaintext ZIP, network call, automatic installation or delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import os
import re
import stat
import uuid

from .native_cold_custody import check_portable_native_custody, _safe_path
from .native_encrypted_vault import _safe_private_root
from .native_sha_watchdog import _bytes, _json, _new, _atomic, _utc, _clock, ZERO

SCHEMA = "eraleader.periodic_cold_ciphertext_integrity.v1"
STATUS = "LOCAL_COLD_CUSTODY_INTEGRITY_DRY_RUN"
NAME = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
STATES = frozenset({"PENDING_SCAN", "VERIFIED", "RESEARCH_ONLY_VERIFIED",
                    "MISSED_SCAN_WINDOW", "PACKAGE_MISSING", "PACKAGE_INVALID",
                    "PACKAGE_PATH_UNSAFE", "PIN_MISSING", "PIN_CORRUPTED"})
MAX_PINS = 128
MAX_EVENTS = 20000


def _sha(raw):
    return sha256(raw).hexdigest()


def _identifier(name):
    if type(name) is not str or NAME.fullmatch(name) is None:
        raise ValueError("Invalid encrypted custody name")
    return _sha(name.encode())


def _configured(project, pin_root, max_gap_hours, *, research=False):
    if type(max_gap_hours) is not int or not 1 <= max_gap_hours <= 720:
        raise ValueError("Periodic cold integrity cadence must be 1..720 hours")
    project = Path(project)
    if not project.is_absolute() or project.is_symlink() or not project.is_dir():
        raise ValueError("Original project root required for independent custody")
    root = _safe_private_root(Path(pin_root), must_exist=True)
    if root == project or root in project.parents or project in root.parents:
        raise ValueError("Independent PIN cannot reside in or contain original project")
    if root.stat().st_uid != os.geteuid():
        raise ValueError("Independent first PIN root must belong to current owner")
    if root.stat().st_dev == project.stat().st_dev and not research:
        raise ValueError("First external SHA PIN must use a filesystem different from original SSD")
    pins = root / "pins"
    for path in (pins, root/"genesis.json", root/"history.jsonl",
                 root/"checkpoint.json", root/".checks.lock"):
        if path.is_symlink() or (path.exists() and not (
                path.is_dir() if path == pins else path.is_file())):
            raise ValueError("Unsafe independent PIN ledger path")
    return project, root


def _archive_path(path, project, root, research):
    archive = _safe_path(path)  # Do not require the archive to still be present.
    if (archive == root or root in archive.parents or archive in root.parents or
            archive == project or project in archive.parents or
            archive in project.parents):
        raise ValueError("PIN archive cannot overlap protected project/PIN root")
    if archive.exists():
        if not archive.is_file() or not stat.S_ISREG(archive.stat().st_mode):
            raise ValueError("Nonregular encrypted custody source")
        isolated = archive.stat().st_dev not in (
            root.stat().st_dev, project.stat().st_dev)
        if not isolated and not research:
            raise ValueError("Portable package and independent SHA PIN require different devices")
        return isolated
    return False


def _initial(root, project, max_gap):
    return {"schema": SCHEMA, "project_path_sha256": _sha(str(project).encode()),
            "pin_root_path_sha256": _sha(str(root).encode()),
            "max_gap_hours": max_gap}


def _lock(root, *, create):
    path = root / ".checks.lock"
    existing = path.exists()
    if not existing and any((root/item).exists() for item in
                            ("genesis.json", "history.jsonl", "checkpoint.json", "pins")):
        raise ValueError("Independent SHA PIN lock was lost")
    if not existing and not create:
        raise ValueError("Independent SHA PIN ledger was never initialized")
    fd = os.open(path, (os.O_RDWR | (os.O_CREAT | os.O_EXCL if not existing else 0) |
                        getattr(os, "O_NOFOLLOW", 0)), 0o600)
    handle = os.fdopen(fd, "rb+")
    lock_stat = os.fstat(handle.fileno())
    if (not stat.S_ISREG(lock_stat.st_mode) or
            lock_stat.st_uid != os.geteuid() or
            stat.S_IMODE(lock_stat.st_mode) & 0o077):
        handle.close()
        raise ValueError("Unsafe independent PIN lock")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError("Concurrent independent cold integrity scan") from exc
    return handle, existing


def _read_json(file, cap=100000):
    if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= cap:
        raise ValueError("Missing/damaged immutable SHA ledger evidence")
    raw = file.read_bytes()
    parsed = _json(raw)
    if _bytes(parsed) != raw:
        raise ValueError("Noncanonical independent custody SHA ledger")
    return parsed, raw


def _bootstrap(root, project, max_gap):
    pins = root/"pins"
    pins.mkdir(mode=0o700, exist_ok=False)
    _new(root/"genesis.json", _bytes({**_initial(root, project, max_gap),
                                       "nonce": uuid.uuid4().hex}))
    _new(root/"history.jsonl", b"")
    _new(root/"checkpoint.json", _bytes({"schema":SCHEMA, "events":0,
                                          "chain_sha256":ZERO, "registered":{}}))


def _audit(root, project, max_gap):
    genesis, raw = _read_json(root/"genesis.json", 2048)
    if (type(genesis) is not dict or set(genesis) !=
            set(_initial(root, project, max_gap)) | {"nonce"} or
            any(genesis[k] != v for k,v in _initial(root, project, max_gap).items()) or
            type(genesis.get("nonce")) is not str or
            re.fullmatch("[a-f0-9]{32}", genesis["nonce"]) is None):
        raise ValueError("Independent cold PIN immutable scan policy mismatch")
    history = root/"history.jsonl"
    pins = root/"pins"
    if (history.is_symlink() or not history.is_file() or
            history.stat().st_size > 40_000_000 or not pins.is_dir() or
            pins.is_symlink() or stat.S_IMODE(pins.stat().st_mode) & 0o077):
        raise ValueError("Original SHA witness history/inventory is incomplete")
    raw_lines = history.read_bytes()
    if raw_lines and not raw_lines.endswith(b"\n"):
        raise ValueError("Torn independent SHA history append")
    expected = {}
    chain = ZERO
    previous_time = None
    records = []
    last_rows = {}
    for line in raw_lines.splitlines():
        if not 0 < len(line) <= 40_000 or len(records) >= MAX_EVENTS:
            raise ValueError("Oversized independent SHA event")
        event = _json(line)
        if (type(event) is not dict or set(event) !=
                {"seq", "at_utc", "kind", "pin_id", "pin_first_sha256",
                 "rows", "previous_sha256", "event_sha256"} or
                type(event["seq"]) is not int or event["seq"] != len(records)+1 or
                event["previous_sha256"] != chain or _bytes(event) != line+b"\n" or
                event["kind"] not in ("ENROLL", "SCAN")):
            raise ValueError("Changed/truncated independent custody SHA event")
        now = _utc(event["at_utc"])
        if previous_time is not None and now < previous_time:
            raise ValueError("Independent cold custody local clock rolled backward")
        previous_time = now
        pin_id, first_sha = event["pin_id"], event["pin_first_sha256"]
        if event["kind"] == "ENROLL":
            if (type(pin_id) is not str or HEX.fullmatch(pin_id) is None or
                    pin_id in expected or len(expected) >= MAX_PINS or
                    type(first_sha) is not str or HEX.fullmatch(first_sha) is None):
                raise ValueError("Independent first SHA receipt was reassigned")
            expected[pin_id] = first_sha
        elif pin_id is not None or first_sha is not None:
            raise ValueError("Non-enrollment SHA cannot redefine PIN identity")
        rows = event["rows"]
        if (type(rows) is not dict or set(rows) != set(expected) or
                any(x not in STATES for x in rows.values())):
            raise ValueError("Independent inventory silently dropped pinned archive")
        if event["kind"] == "ENROLL":
            if any(rows[k] != last_rows[k] for k in last_rows):
                raise ValueError("Enrollment silently rewrote prior scan health")
            if rows[pin_id] != "PENDING_SCAN":
                raise ValueError("First-write SHA has false verified state")
        digest = event["event_sha256"]
        if type(digest) is not str or digest != _sha(_bytes(
                {k:v for k,v in event.items() if k != "event_sha256"})):
            raise ValueError("Independent custody append-chain SHA incorrect")
        chain = digest
        records.append(event)
        last_rows = rows
    checkpoint, _ = _read_json(root/"checkpoint.json", 20000)
    if checkpoint != {"schema":SCHEMA, "events":len(records),
                      "chain_sha256":chain, "registered":expected}:
        raise ValueError("Independent SHA checkpoint/registration rolled back")
    permitted = {name+suffix for name in expected for suffix in ("_first.json","_guard.json")}
    if not {x.name for x in pins.iterdir()}.issubset(permitted):
        raise ValueError("Unregistered/stray independent SHA first PIN files")
    return records, expected, last_rows, _sha(raw)


def _append(root, records, registered, when, kind, rows, *, pin_id=None, first_sha=None):
    event = {"seq":len(records)+1, "at_utc":when.isoformat(),
             "kind":kind, "pin_id":pin_id, "pin_first_sha256":first_sha,
             "rows":rows, "previous_sha256": records[-1]["event_sha256"]
                                                if records else ZERO}
    event["event_sha256"] = _sha(_bytes(event))
    with (root/"history.jsonl").open("ab") as sink:
        sink.write(_bytes(event))
        sink.flush()
        os.fsync(sink.fileno())
    _atomic(root/"checkpoint.json", _bytes({"schema":SCHEMA,
        "events":len(records)+1, "chain_sha256":event["event_sha256"],
        "registered":registered}))
    return event


def _pin_files(root, name_id):
    pin = root/"pins"/(name_id+"_first.json")
    guard = root/"pins"/(name_id+"_guard.json")
    return pin, guard


def _pin_state(root, project, name_id, first_sha, *, research):
    pin, guard = _pin_files(root, name_id)
    if not pin.is_file() or not guard.is_file() or pin.is_symlink() or guard.is_symlink():
        return "PIN_MISSING"
    if (stat.S_IMODE(pin.stat().st_mode) & 0o077 or
            stat.S_IMODE(guard.stat().st_mode) & 0o077 or
            pin.stat().st_uid != os.geteuid() or
            guard.stat().st_uid != os.geteuid()):
        return "PIN_CORRUPTED"
    try:
        meta, raw = _read_json(pin, 4096)
        seal, _ = _read_json(guard, 1024)
        if (set(meta) != {"schema","name","archive_path","package_sha256",
                          "registered_at_utc","colocated_research_only"} or
                meta["schema"] != SCHEMA or _identifier(meta["name"]) != name_id or
                _sha(raw) != first_sha or seal != {"first_sha256":first_sha,
                        "schema":SCHEMA} or
                type(meta["archive_path"]) is not str or
                type(meta["package_sha256"]) is not str or
                HEX.fullmatch(meta["package_sha256"]) is None or
                type(meta["colocated_research_only"]) is not bool):
            return "PIN_CORRUPTED"
        _utc(meta["registered_at_utc"])
        archive = Path(meta["archive_path"])
        if not archive.exists() and not archive.is_symlink():
            return "PACKAGE_MISSING"
        try:
            isolated = _archive_path(archive, project, root, research)
        except (ValueError, OSError):
            return "PACKAGE_PATH_UNSAFE"
        if not isolated and not meta["colocated_research_only"]:
            return "PACKAGE_PATH_UNSAFE"
        if meta["colocated_research_only"] and not research:
            return "PACKAGE_PATH_UNSAFE"
        try:
            check_portable_native_custody(archive, meta["package_sha256"])
        except (ValueError, OSError, RuntimeError, KeyError):
            return "PACKAGE_INVALID"
        if _sha(pin.read_bytes()) != first_sha:
            return "PIN_CORRUPTED"
        return "RESEARCH_ONLY_VERIFIED" if meta["colocated_research_only"] else "VERIFIED"
    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
        return "PIN_CORRUPTED"


def _result(event, *, new_alerts, research, genesis_sha):
    rows = event["rows"]
    return {"status": STATUS, "checked_at_utc":event["at_utc"],
            "check_count":event["seq"],"chain_head_sha256":event["event_sha256"],
            "genesis_sha256":genesis_sha, "packages":rows,
            "verified_count":sum(v=="VERIFIED" for v in rows.values()),
            "warning_count":sum(v not in ("VERIFIED","RESEARCH_ONLY_VERIFIED") for v in rows.values()),
            "new_alerts":new_alerts,
            "research_only_colocated_allowed":research,
            "independent_timestamp_attested":False,
            "offsite_geography_attested":False,
            "plaintext_decrypted":False, "private_key_accessed":False,
            "local_artifacts_only":True,
            "messages_sent":0,"external_api_calls":0,"official_leader_promotions":0,
            "independent_market_pit_certified":False,
            "actual_future_leader_skill_certified":False}


def _publish(project, report):
    folder = project/"output"/"native_cold_integrity"
    site = project/"output"/"site"
    for item in (folder, folder/"site", folder/"report.json",
                 folder/"site"/"index.html", site/"native_cold_integrity.html",
                 site/"index.html"):
        if item.is_symlink():
            raise ValueError("Unsafe output symlink for ciphertext integrity dashboard")
    (folder/"site").mkdir(mode=0o700, parents=True, exist_ok=True)
    _atomic(folder/"report.json", _bytes(report))
    trs = "".join("<tr><td>"+escape(k[:12])+"</td><td>"+
                  escape(v)+"</td></tr>" for k,v in sorted(report["packages"].items()))
    html = ("<!doctype html><html lang='ko'><meta charset='utf-8'><title>"
            "EraLeader 암호문 정기 무결성</title><h1>6_5 암호화 보관본 SHA 주기 감사 · DRY-RUN</h1>"
            "<p>SHA / 첫 witness 기준, 복호화·메시지 발송·실제 PIT 인증 없음.</p>"
            "<p>모델·개인키·로컬 원본 경로는 표시하지 않음.</p>"
            "<p>Scans: "+str(report["check_count"])+" / alerts: "+
            str(report["warning_count"])+"</p><table><tr><th>익명 package</th>"
            "<th>무결성 상태</th></tr>"+trs+"</table></html>")
    _atomic(folder/"site"/"index.html", html.encode())
    if site.is_dir() and not site.is_symlink():
        _atomic(site/"native_cold_integrity.html", html.encode())
        index = site/"index.html"
        if index.is_file() and not index.is_symlink():
            current = index.read_text()
            if "native_cold_integrity.html" not in current:
                link = ('<p><a href="native_cold_integrity.html">'
                        'Encrypted native custody SHA integrity (DRY-RUN)</a></p>')
                _atomic(index, (current.replace("</body>",link+"</body>",1)
                                if "</body>" in current else current+link).encode())


def enroll_cold_integrity(project, pin_root, name, archive, expected_sha256, *,
                          max_gap_hours=48, allow_colocated_research=False,
                          clock=None):
    """Require separately trusted SHA; O_EXCL immutable pin on other volume."""
    project, root = _configured(project, pin_root, max_gap_hours,
                                research=allow_colocated_research)
    name_id = _identifier(name)
    if type(expected_sha256) is not str or HEX.fullmatch(expected_sha256) is None:
        raise ValueError("Original trusted package SHA256 must be supplied on enrollment")
    archive = _safe_path(archive, exists=True)
    isolated = _archive_path(archive, project, root, allow_colocated_research)
    if not isolated and not allow_colocated_research:
        raise ValueError("Cannot pin encrypted backup on its own volume")
    check_portable_native_custody(archive, expected_sha256)
    now = _clock(clock)
    lock, existing = _lock(root, create=True)
    with lock:
        if not existing:
            _bootstrap(root, project, max_gap_hours)
        records, enrolled, rows, genesis_sha = _audit(root, project, max_gap_hours)
        if records and now < _utc(records[-1]["at_utc"]):
            raise ValueError("Independent PIN enrollment clock rollback")
        if name_id in enrolled:
            pin, _ = _pin_files(root, name_id)
            state = _pin_state(root, project, name_id, enrolled[name_id],
                               research=allow_colocated_research)
            if state not in ("VERIFIED","RESEARCH_ONLY_VERIFIED"):
                raise ValueError("Previous trusted PIN no longer verifies")
            value, _ = _read_json(pin, 4096)
            if (value["archive_path"] != str(archive) or
                    value["package_sha256"] != expected_sha256 or
                    value["name"] != name):
                raise ValueError("Cannot replace first SHA PIN or original custody path")
            return {"status":"EXISTING_FIRST_COLD_SHA_PIN_VERIFIED", "pin_id":name_id,
                    "first_pin_sha256":enrolled[name_id], "new_first_pins":0,
                    "independent_filesystem": isolated, "external_api_calls":0}
        for old_id, old_sha in enrolled.items():
            old_pin, _ = _pin_files(root, old_id)
            if _pin_state(root,project,old_id,old_sha,
                          research=allow_colocated_research) not in (
                    "VERIFIED","RESEARCH_ONLY_VERIFIED"):
                raise ValueError("Cannot enroll with broken prior independent PIN")
            old_meta, _ = _read_json(old_pin,4096)
            if (old_meta["archive_path"] == str(archive) or
                    old_meta["package_sha256"] == expected_sha256):
                raise ValueError("Existing independent custody archive already enrolled")
        if len(enrolled) >= MAX_PINS:
            raise ValueError("At most 128 independent ciphertext PIN records")
        pin, guard = _pin_files(root, name_id)
        if pin.exists() or guard.exists() or pin.is_symlink() or guard.is_symlink():
            raise ValueError("Partial or unregistered SHA PIN refuses reissue")
        body = _bytes({"schema":SCHEMA,"name":name,"archive_path":str(archive),
             "package_sha256":expected_sha256,"registered_at_utc":now.isoformat(),
             "colocated_research_only":not isolated})
        pin_sha = _sha(body)
        _new(pin, body)
        _new(guard, _bytes({"schema":SCHEMA, "first_sha256":pin_sha}))
        enrolled[name_id] = pin_sha
        snapshot = {**rows, name_id:"PENDING_SCAN"}
        event = _append(root, records, enrolled, now, "ENROLL", snapshot,
                        pin_id=name_id, first_sha=pin_sha)
        return {"status":"FIRST_COLD_SHA_PIN_STORED_NOT_NOTARIZED", "pin_id":name_id,
                "first_pin_sha256":pin_sha, "genesis_sha256":genesis_sha,
                "chain_head_sha256":event["event_sha256"], "new_first_pins":1,
                "independent_filesystem":isolated, "external_api_calls":0,
                "offsite_geography_attested":False}


def scan_cold_integrity(project, pin_root, *, max_gap_hours=48,
                        allow_colocated_research=False, clock=None):
    """Full ciphertext/member/first-witness SHA scan of EVERY enrolled package."""
    project, root = _configured(project, pin_root, max_gap_hours,
                                research=allow_colocated_research)
    now = _clock(clock)
    lock, _ = _lock(root, create=False)
    with lock:
        records, enrolled, previous, genesis_sha = _audit(root, project, max_gap_hours)
        if not enrolled:
            raise ValueError("No trusted encrypted custody packages registered")
        if records and now < _utc(records[-1]["at_utc"]):
            raise ValueError("Clock rollback in periodic encrypted custody scan")
        late = False
        scans = [x for x in records if x["kind"] == "SCAN"]
        if scans and (now-_utc(scans[-1]["at_utc"])).total_seconds() > max_gap_hours*3600:
            late = True
        states = {}
        for name_id, first_sha in sorted(enrolled.items()):
            status = _pin_state(root,project,name_id,first_sha,
                                research=allow_colocated_research)
            if late and status in ("VERIFIED", "RESEARCH_ONLY_VERIFIED"):
                status = "MISSED_SCAN_WINDOW"
            states[name_id] = status
        changes = []
        for name_id, status in states.items():
            prev = previous.get(name_id)
            if status != prev:
                changes.append(name_id+":"+(("FIRST_VERIFIED" if prev == "PENDING_SCAN"
                    else "RESTORED") if status in
                    ("VERIFIED", "RESEARCH_ONLY_VERIFIED") else status))
        event = _append(root, records, enrolled, now, "SCAN", states)
        report = _result(event,new_alerts=changes,
                         research=allow_colocated_research,genesis_sha=genesis_sha)
        _publish(project, report)
        return report


def verify_cold_integrity_history(project, pin_root, *, max_gap_hours=48,
                                  allow_colocated_research=False):
    """Read-only SHA event/first immutable enrollment cross-check, no source writes."""
    project, root = _configured(project, pin_root, max_gap_hours,
                                research=allow_colocated_research)
    lock, _ = _lock(root, create=False)
    with lock:
        records, registered, _, genesis_sha = _audit(root,project,max_gap_hours)
        pins = {name:_pin_state(root,project,name,raw,research=True)
                for name, raw in registered.items()}
        if any(x in ("PIN_MISSING","PIN_CORRUPTED") for x in pins.values()):
            raise ValueError("First cold SHA pin evidence incomplete")
        return {"status":"INDEPENDENT_COLD_SHA_HISTORY_VERIFIED",
                "check_count":len(records),"pin_count":len(registered),
                "genesis_sha256":genesis_sha,
                "chain_head_sha256":records[-1]["event_sha256"] if records else ZERO,
                "first_pins_verified":True,"external_api_calls":0}
