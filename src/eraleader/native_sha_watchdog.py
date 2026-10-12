"""6_5 opt-in multi-cohort cross-volume native SHA monitor, local DRY-RUN only.

Reuses the strict original source / first-witness verifier. Never copies raw
cohort data, signs market PIT, transmits a message, or repairs an original.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import json
import os
import re
import uuid

from .native_evidence_archive import _slot
from .native_first_capture import read_capture_plan
from .native_sha_witness import validate_witness_destination, verify_native_sha_witness

SCHEMA = "eraleader.native_multi_sha_watchdog.v1"
ZERO = "0" * 64
STATES = {"VERIFIED", "WAITING", "ANOMALY"}
ISSUES = {"NONE", "WAITING_FIRST_WRITE", "PLAN_INVALID_OR_MISSING",
          "MISSING_SCAN_INPUT", "ORIGINAL_OR_WITNESS_MISSING",
          "UNWITNESSED_OR_PARTIAL", "SHA_INTEGRITY_FAILURE",
          "FIRST_PIN_REPLACED"}
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _sha(raw):
    return sha256(raw).hexdigest()


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("Invalid native SHA watchdog UTC")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid native SHA watchdog UTC") from exc
    if at.tzinfo is None or at.utcoffset() is None or at.utcoffset().total_seconds() != 0:
        raise ValueError("Invalid native SHA watchdog UTC")
    return at


def _clock(value):
    now = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Native SHA watchdog needs an aware local clock")
    return now.astimezone(timezone.utc)


def _new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())


def _atomic(path, raw):
    temporary = path.parent / ("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        _new(temporary, raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate native SHA watchdog JSON key")
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid native SHA watchdog JSON") from exc


def _locations(project, capture_root, witness_root):
    project = Path(project).absolute()
    capture = Path(capture_root).absolute()
    witness = validate_witness_destination(project, Path(witness_root))
    output = project / "output"
    if (not output.is_dir() or output.is_symlink() or project.is_symlink() or
            output not in capture.parents or capture == output):
        raise ValueError("Original first-capture root must be inside project/output")
    folder = output / "native_sha_alerts"
    if (folder == capture or folder in capture.parents or capture in folder.parents or
            folder == witness or folder in witness.parents or witness in folder.parents):
        raise ValueError("Native SHA watchdog cannot overlap original or witness roots")
    for path in (folder, folder / "genesis.json", folder / "history.jsonl",
                 folder / "first_event.json", folder / ".checks.lock",
                 folder / "report.json", folder / "site",
                 folder / "site" / "index.html"):
        if path.is_symlink() or (path.exists() and
                                 (not path.is_dir() if path in (folder, folder / "site")
                                  else not path.is_file())):
            raise ValueError("Unsafe native SHA watchdog artifact")
    return folder, project, capture, witness


def _genesis(project, capture, witness):
    return {"schema": SCHEMA, "project_sha256": _sha(str(project).encode()),
            "capture_root_sha256": _sha(str(capture).encode()),
            "witness_root_sha256": _sha(str(witness).encode())}


def _empty(issue, market="UNKNOWN"):
    return {"market": market, "state": "ANOMALY", "issue": issue,
            "archive_sha256": ZERO, "witness_sha256": ZERO}


def _probe(project, plan_path, capture, witness, pinned, now):
    market = pinned["market"] if pinned else "UNKNOWN"
    if plan_path.is_symlink() or not plan_path.is_file():
        return _empty("PLAN_INVALID_OR_MISSING", market)
    try:
        plan, _, _ = read_capture_plan(plan_path)
        market = plan["market"]
        slot = _slot(plan)
    except (ValueError, KeyError, TypeError, OSError):
        return _empty("PLAN_INVALID_OR_MISSING", market)
    if pinned and pinned["market"] not in ("UNKNOWN", market):
        return _empty("FIRST_PIN_REPLACED", pinned["market"])
    archive = project / "output" / "native_first_private_archives" / ("native_" + slot + ".zip")
    receipts = project / "output" / "native_first_archive_receipts"
    local = receipts / ("native_" + slot + "_receipt.json")
    external = witness / ("native_" + slot + "_first.json")
    # Absence is WAITING only when no first capture or even partial seal exists.
    # In particular, a deleted first receipt with a surviving guard/lock must
    # not masquerade as a fresh model waiting for its first score.
    related = (archive, local, external,
               receipts / ("native_" + slot + "_guard.json"),
               receipts / (".native_" + slot + ".lock"),
               witness / ("native_" + slot + "_guard.json"),
               witness / (".native_" + slot + ".lock"),
               capture / ("native_" + slot) / "capture_receipt.json")
    if not any(p.exists() or p.is_symlink() for p in related):
        if pinned and pinned["state"] == "VERIFIED":
            return _empty("ORIGINAL_OR_WITNESS_MISSING", market)
        return {"market": market, "state": "WAITING", "issue": "WAITING_FIRST_WRITE",
                "archive_sha256": ZERO, "witness_sha256": ZERO}
    if not (archive.is_file() and local.is_file() and external.is_file()):
        return _empty("UNWITNESSED_OR_PARTIAL", market)
    try:
        checked = verify_native_sha_witness(project, plan_path, capture, witness, clock=now)
        if (checked.get("status") != "SEPARATE_VOLUME_NATIVE_SHA_VERIFIED_NOT_ATTESTED" or
                checked.get("source_archive_verified") is not True or
                checked.get("separate_device_checked") is not True or
                checked.get("messages_sent") != 0 or checked.get("external_api_calls") != 0 or
                checked.get("official_leader_promotions") != 0 or
                checked.get("real_future_leader_accuracy_certified") is not False or
                checked.get("independent_timestamp_attested") is not False):
            raise ValueError("Unverified cross-volume SHA evidence")
        archive_sha, witness_sha = checked["archive_sha256"], checked["witness_sha256"]
        if not all(isinstance(x, str) and HEX.fullmatch(x) for x in
                   (archive_sha, witness_sha)):
            raise ValueError("Invalid original SHA digest")
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        return _empty("SHA_INTEGRITY_FAILURE", market)
    if pinned and pinned["state"] == "VERIFIED" and (
            pinned["archive_sha256"] != archive_sha or
            pinned["witness_sha256"] != witness_sha):
        return _empty("FIRST_PIN_REPLACED", market)
    return {"market": market, "state": "VERIFIED", "issue": "NONE",
            "archive_sha256": archive_sha, "witness_sha256": witness_sha}


def _validate_row(row):
    if (type(row) is not dict or set(row) !=
            {"market", "state", "issue", "archive_sha256", "witness_sha256"} or
            row["market"] not in ("KR", "US", "UNKNOWN") or
            row["state"] not in STATES or row["issue"] not in ISSUES or
            not all(type(row[k]) is str and HEX.fullmatch(row[k]) for k in
                    ("archive_sha256", "witness_sha256"))):
        raise ValueError("Invalid native SHA monitor state")
    if row["state"] == "VERIFIED":
        if row["issue"] != "NONE" or row["market"] == "UNKNOWN" or any(
                row[k] == ZERO for k in ("archive_sha256", "witness_sha256")):
            raise ValueError("Forged verified native SHA state")
    elif (row["archive_sha256"] != ZERO or row["witness_sha256"] != ZERO or
          (row["state"] == "WAITING") != (row["issue"] == "WAITING_FIRST_WRITE") or
          (row["state"] == "ANOMALY" and row["issue"] in ("NONE", "WAITING_FIRST_WRITE"))):
        raise ValueError("Forged pending/anomaly SHA state")


def _audit(folder, expected):
    genesis = folder / "genesis.json"
    log = folder / "history.jsonl"
    if not genesis.is_file() or not log.is_file():
        raise ValueError("Missing native SHA watchdog first-write history")
    original = genesis.read_bytes()
    obj = _json(original)
    if (len(original) > 2048 or type(obj) is not dict or
            set(obj) != set(expected) | {"nonce"} or
            any(obj.get(k) != v for k, v in expected.items()) or
            type(obj.get("nonce")) is not str or
            re.fullmatch(r"[a-f0-9]{32}", obj["nonce"]) is None or
            original != _bytes(obj)):
        raise ValueError("Original native SHA watchdog genesis mismatch")
    raw = log.read_bytes()
    if len(raw) > 30_000_000 or (raw and not raw.endswith(b"\n")):
        raise ValueError("Native SHA watchdog log truncated or oversized")
    events, trusted = [], {}
    previous, last_at = ZERO, None
    for line in raw.splitlines():
        if not 0 < len(line) <= 500_000 or len(events) >= 20000:
            raise ValueError("Native SHA watchdog oversized event")
        event = _json(line)
        if (type(event) is not dict or set(event) !=
                {"seq", "observed_at_utc", "cohorts", "new_alerts",
                 "previous_sha256", "event_sha256"} or
                type(event["seq"]) is not int or event["seq"] != len(events) + 1 or
                event["previous_sha256"] != previous or
                line + b"\n" != _bytes(event)):
            raise ValueError("Native SHA watchdog chain malformed")
        at = _utc(event["observed_at_utc"])
        if last_at is not None and at < last_at:
            raise ValueError("Native SHA watchdog clock rollback")
        last_at = at
        rows = event["cohorts"]
        if type(rows) is not dict or len(rows) == 0 or len(rows) > 128 or (
                events and not set(events[-1]["cohorts"]).issubset(rows)):
            raise ValueError("Native SHA watchdog cohort inventory dropped")
        for key, row in rows.items():
            if type(key) is not str or HEX.fullmatch(key) is None:
                raise ValueError("Native SHA watchdog invalid cohort ID")
            _validate_row(row)
            original_pin = trusted.get(key)
            if original_pin and row["state"] == "VERIFIED" and (
                    original_pin["archive_sha256"] != row["archive_sha256"] or
                    original_pin["witness_sha256"] != row["witness_sha256"] or
                    original_pin["market"] != row["market"]):
                raise ValueError("Native SHA watchdog historical first pin revised")
            if row["state"] == "VERIFIED" and original_pin is None:
                trusted[key] = row
        alerts = event["new_alerts"]
        if (type(alerts) is not list or len(alerts) > len(rows) or
                len(alerts) != len(set(alerts)) or
                any(type(s) is not str or ":" not in s or
                    s.split(":", 1)[0] not in rows or
                    s.split(":", 1)[1] not in ISSUES | {"RESTORED"}
                    for s in alerts)):
            raise ValueError("Invalid native SHA watchdog warning record")
        if _sha(_bytes({k:v for k,v in event.items() if k != "event_sha256"})) != event["event_sha256"]:
            raise ValueError("Native SHA watchdog SHA chain broken")
        previous = event["event_sha256"]
        events.append(event)
    first = folder / "first_event.json"
    if events:
        if not first.is_file() or len(first.read_bytes()) > 512:
            raise ValueError("Native SHA watchdog first receipt lost")
        receipt = _json(first.read_bytes())
        if (type(receipt) is not dict or set(receipt) !=
                {"schema", "genesis_sha256", "first_event_sha256"} or
                receipt["schema"] != SCHEMA or receipt["genesis_sha256"] != _sha(original) or
                receipt["first_event_sha256"] != events[0]["event_sha256"] or
                _bytes(receipt) != first.read_bytes()):
            raise ValueError("Native SHA watchdog first receipt mismatch")
    elif first.exists():
        raise ValueError("Native SHA watchdog first receipt without history")
    report_path = folder / "report.json"
    if events:
        if not report_path.is_file():
            raise ValueError("Native SHA watchdog published checkpoint lost")
        checkpoint = _json(report_path.read_bytes())
        if (type(checkpoint) is not dict or _bytes(checkpoint) != report_path.read_bytes() or
                checkpoint.get("chain_head_sha256") != events[-1]["event_sha256"] or
                checkpoint.get("check_count") != len(events) or
                checkpoint.get("cohorts") != events[-1]["cohorts"] or
                checkpoint.get("new_alerts") != events[-1]["new_alerts"] or
                checkpoint.get("status") != "LOCAL_NATIVE_SHA_DRY_RUN_RECORDED" or
                checkpoint.get("messages_sent") != 0 or
                checkpoint.get("external_api_calls") != 0 or
                checkpoint.get("official_leader_promotions") != 0 or
                checkpoint.get("independent_pit_certified") is not False or
                checkpoint.get("local_artifacts_only") is not True):
            raise ValueError("Native SHA watchdog report/chain rollback or tampering")
    elif report_path.exists():
        raise ValueError("Native SHA watchdog report without history")
    return events, trusted


def _html(result, *, main_link='../../site/index.html'):
    cohorts = result["cohorts"]
    rows = "".join(
        "<tr><td>" + escape(row["market"]) + "</td><td>" +
        escape(key[:12]) + "</td><td>" + escape(row["state"]) +
        "</td><td>" + escape(row["issue"]) + "</td></tr>"
        for key, row in sorted(cohorts.items()))
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader native SHA DRY-RUN</title>"
            "<style>body{font:16px system-ui;max-width:980px;margin:2rem auto;padding:0 1rem}"
            "table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #bbb}"
            "</style><h1>Native first Top-K · multi-cohort SHA integrity</h1>"
            "<p>Local DRY-RUN only · never sent · not external timestamp / PIT / leader certified</p>"
            "<p>Checks: " + str(result["check_count"]) + " | monitored: " +
            str(len(cohorts)) + " | anomalies: " +
            str(sum(v["state"] == "ANOMALY" for v in cohorts.values())) +
            " | new warnings: " + str(len(result["new_alerts"])) + "</p>"
            "<a href='" + main_link + "'>EraLeader local dashboard</a>"
            "<table><thead><tr><th>Market</th><th>Cohort ID prefix</th>"
            "<th>SHA status</th><th>Issue</th></tr></thead><tbody>" +
            rows + "</tbody></table></html>")


def run_native_sha_watchdog(project, plans, witness_root, *, capture_root=None, clock=None):
    """Audit multiple explicitly registered plans, pin first verified SHA per plan.

    The prior inventory cannot be silently dropped; new plans may be appended.
    Every result is a local-only observation, NEVER a user notification.
    """
    now = _clock(clock)
    project = Path(project).absolute()
    capture = Path(capture_root).absolute() if capture_root is not None else (
        project / "output" / "native_first_captures")
    folder, project, capture, witness = _locations(project, capture, witness_root)
    paths = [Path(p) for p in plans]
    if not 1 <= len(paths) <= 128 or any(
            not p.is_absolute() or ".." in p.parts for p in paths):
        raise ValueError("Explicit 1..128 absolute native SHA monitoring plans required")
    ids = {_sha(str(p).encode()): p for p in paths}
    if len(ids) != len(paths):
        raise ValueError("Duplicate native SHA monitoring plan")
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    (folder / "site").mkdir(mode=0o700, exist_ok=True)
    lock = folder / ".checks.lock"
    existed = lock.exists()
    if not existed and ((folder / "genesis.json").exists() or
                        (folder / "history.jsonl").exists()):
        raise ValueError("Native SHA watchdog audit lock lost after first write")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "rb+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Native SHA watchdog already running") from exc
        try:
            genesis, log = folder / "genesis.json", folder / "history.jsonl"
            if not genesis.exists() and not log.exists():
                if existed:
                    raise ValueError("Original native SHA watchdog evidence deleted")
                _new(genesis, _bytes({**_genesis(project, capture, witness),
                                      "nonce": uuid.uuid4().hex}))
                _new(log, b"")
            events, trusted = _audit(folder, _genesis(project, capture, witness))
            if events and now < _utc(events[-1]["observed_at_utc"]):
                raise ValueError("Native SHA watchdog local clock rollback")
            prior = events[-1]["cohorts"] if events else {}
            if len(set(prior) | set(ids)) > 128:
                raise ValueError("Native SHA watchdog plan inventory exceeds limit")
            snapshot = {}
            for key in sorted(set(prior) | set(ids)):
                if key not in ids:
                    snapshot[key] = _empty("MISSING_SCAN_INPUT", prior[key]["market"])
                else:
                    snapshot[key] = _probe(project, ids[key], capture, witness,
                                           trusted.get(key), now)
            warnings = []
            for key, row in sorted(snapshot.items()):
                last = prior.get(key)
                if row["state"] == "ANOMALY" and (
                        not last or last["state"] != "ANOMALY" or
                        last["issue"] != row["issue"]):
                    warnings.append(key + ":" + row["issue"])
                elif row["state"] == "VERIFIED" and last and last["state"] == "ANOMALY":
                    warnings.append(key + ":RESTORED")
            event = {"seq": len(events) + 1, "observed_at_utc": now.isoformat(),
                     "cohorts": snapshot, "new_alerts": warnings,
                     "previous_sha256": events[-1]["event_sha256"] if events else ZERO}
            event["event_sha256"] = _sha(_bytes(event))
            with open(log, "ab", buffering=0) as output:
                output.write(_bytes(event))
                os.fsync(output.fileno())
            if not events:
                _new(folder / "first_event.json", _bytes({
                    "schema": SCHEMA, "genesis_sha256": _sha(genesis.read_bytes()),
                    "first_event_sha256": event["event_sha256"]}))
            result = {"status": "LOCAL_NATIVE_SHA_DRY_RUN_RECORDED",
                      "check_count": len(events) + 1,
                      "chain_head_sha256": event["event_sha256"],
                      "cohorts": snapshot, "new_alerts": warnings,
                      "local_artifacts_only": True,
                      "independent_pit_certified": False,
                      "actual_future_leader_skill_certified": False,
                      "official_leader_promotions": 0,
                      "messages_sent": 0, "external_api_calls": 0}
            _atomic(folder / "report.json", _bytes(result))
            checked, _ = _audit(folder, _genesis(project, capture, witness))
            if len(checked) != len(events) + 1:
                raise RuntimeError("Native SHA watchdog append verification failed")
            _atomic(folder / "site" / "index.html", _html(result).encode())
            # The built-in HTTP server serves output/site, not sibling folders.
            # Publish only sanitized derived HTML there, and link its existing index.
            web = project / "output" / "site"
            if web.exists():
                if web.is_symlink() or not web.is_dir():
                    raise ValueError("Unsafe public local dashboard directory")
                page = web / "native_sha_dry_run.html"
                index = web / "index.html"
                if page.is_symlink() or index.is_symlink():
                    raise ValueError("Linked public native SHA dashboard destination")
                _atomic(page, _html(result, main_link="index.html").encode())
                if index.is_file() and index.stat().st_size <= 1_000_000:
                    raw_index = index.read_text(encoding="utf-8")
                    if "native_sha_dry_run.html" not in raw_index and "</body>" in raw_index:
                        anchor = ("<p><a href='native_sha_dry_run.html'>"
                                  "Native Top-K SHA DRY-RUN monitor</a></p>")
                        _atomic(index, raw_index.replace("</body>", anchor+"</body>", 1).encode())
            return result
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
