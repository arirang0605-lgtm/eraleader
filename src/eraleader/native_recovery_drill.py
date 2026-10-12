"""6_5 private, opt-in encrypted native first-evidence recovery rehearsal.

Uses the existing authenticated AES-GCM recovery + original score/census replay,
then destroys a temporary restored copy. Publishes only coarse local SHA audit
metadata. This is not a hardware disaster test or independent market PIT proof.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
import fcntl
import os
import re
import uuid

from .native_encrypted_vault import (
    SLOT, DIGEST, _private_key, verify_encrypted_native_original,
    restore_encrypted_native_original,
)
from .native_sha_witness import validate_witness_destination
from .native_sha_watchdog import _bytes, _json, _atomic, _new, _utc, ZERO

SCHEMA = "eraleader.native_encrypted_recovery_drill.v1"
DIR = "native_recovery_drills"
STATUS = "LOCAL_NATIVE_RECOVERY_DRILL_RECORDED_NOT_PIT_CERTIFIED"
CAUSES = frozenset({
    "NONE", "UNSAFE_OR_MISSING_KEY", "BACKUP_SHA_INVALID",
    "DECRYPT_OR_REPLAY_FAILED", "PROVENANCE_INCOMPLETE",
    "PRIVATE_SCRATCH_CLEANUP_FAILED",
})


def _sha(data):
    return sha256(data).hexdigest()


def _clock(value):
    now = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Recovery drill requires timezone-aware clock")
    return now.astimezone(timezone.utc)


def _inputs(project, slot, vault, witness, cert, scratch):
    project = Path(project).absolute()
    if (not project.is_dir() or project.is_symlink() or
            not (project / "output").is_dir() or
            (project / "output").is_symlink()):
        raise ValueError("Missing trusted original EraLeader project/output")
    if type(slot) is not str or SLOT.fullmatch(slot) is None:
        raise ValueError("Recovery drill needs a hashed first-native market slot")
    scratch = validate_witness_destination(project, Path(scratch))
    if not scratch.is_dir():
        raise ValueError("Explicit existing mode-0700 recovery scratch directory required")
    vault, witness, cert = (Path(vault), Path(witness), Path(cert))
    for source in (vault, witness):
        if not source.is_absolute() or ".." in source.parts:
            raise ValueError("Recovery drill needs absolute encrypted evidence roots")
        if (scratch == source or scratch in source.parents or
                source in scratch.parents):
            raise ValueError("Recovery scratch cannot overlap vault or SHA witness")
        # A rehearsal cannot claim cross-volume resilience if the source
        # ciphertext/witness silently moved back onto the original SSD.
        validate_witness_destination(project, source)
    if (not cert.is_absolute() or ".." in cert.parts or
            cert.is_symlink() or scratch == cert or scratch in cert.parents):
        raise ValueError("Invalid public recipient certificate location")
    return project, slot, vault, witness, cert, scratch


def _output_paths(project):
    folder = project / "output" / DIR
    site = project / "output" / "site"
    tracked = (
        folder, folder / "genesis.json", folder / "history.jsonl",
        folder / "first_event.json", folder / "report.json",
        folder / ".checks.lock", folder / "site", folder / "site" / "index.html",
        site, site / "native_recovery_drill.html", site / "index.html",
    )
    directories = {folder, folder / "site", site}
    for f in tracked:
        if f.is_symlink() or (f.exists() and (
                not f.is_dir() if f in directories else not f.is_file())):
            raise ValueError("Linked or invalid local recovery drill output")
    return folder, site


def _genesis(project, vault, witness, cert, scratch):
    return {
        "schema": SCHEMA,
        "project_sha256": _sha(str(project).encode()),
        "vault_root_sha256": _sha(str(vault).encode()),
        "witness_root_sha256": _sha(str(witness).encode()),
        "certificate_path_sha256": _sha(str(cert).encode()),
        "scratch_root_sha256": _sha(str(scratch).encode()),
    }


def _validate_event(obj, previous, expected_seq, previous_utc, previous_hash):
    keys = {
        "seq", "observed_at_utc", "slot_sha256", "market", "outcome",
        "reason", "archive_sha256", "encrypted_sha256",
        "aes_gcm_authenticated", "first_watch_score_replayed",
        "census_index_replayed", "temporary_plaintext_path_removed",
        "no_live_delivery", "previous_sha256", "event_sha256",
    }
    if type(obj) is not dict or set(obj) != keys:
        raise ValueError("Incomplete local first-recovery drill evidence")
    when = _utc(obj["observed_at_utc"])
    if (type(obj["seq"]) is not int or obj["seq"] != expected_seq or
            obj["previous_sha256"] != previous_hash or
            (previous_utc is not None and when < previous_utc)):
        raise ValueError("Recovery drill history rollback / invalid time")
    if (type(obj["slot_sha256"]) is not str or not DIGEST.fullmatch(obj["slot_sha256"]) or
            obj["market"] not in {"KR", "US"} or
            obj["outcome"] not in {"PASSED", "FAILED"} or
            obj["reason"] not in CAUSES or
            any(type(obj[k]) is not str or not DIGEST.fullmatch(obj[k])
                for k in ("archive_sha256", "encrypted_sha256")) or
            obj["no_live_delivery"] is not True or
            type(obj["aes_gcm_authenticated"]) is not bool or
            type(obj["first_watch_score_replayed"]) is not bool or
            type(obj["census_index_replayed"]) is not bool or
            type(obj["temporary_plaintext_path_removed"]) is not bool):
        raise ValueError("Forged local recovery drill status")
    if obj["outcome"] == "PASSED":
        if (obj["reason"] != "NONE" or ZERO in (
                obj["archive_sha256"], obj["encrypted_sha256"]) or
                not all(obj[k] for k in (
                    "aes_gcm_authenticated", "first_watch_score_replayed",
                    "census_index_replayed", "temporary_plaintext_path_removed"))):
            raise ValueError("Unauthenticated replay cannot be a successful recovery drill")
    elif obj["reason"] == "NONE":
        raise ValueError("Failed original recovery drill must provide fixed incident code")
    expected = _sha(_bytes({k: v for k, v in obj.items() if k != "event_sha256"}))
    if obj["event_sha256"] != expected:
        raise ValueError("Recovery drill event SHA chain altered")
    return when


def _audit(folder, expected):
    genesis = folder / "genesis.json"
    history = folder / "history.jsonl"
    if any(p.is_symlink() or not p.is_file() for p in (genesis, history)):
        raise ValueError("Missing original local recovery drill audit genesis")
    initial = genesis.read_bytes()
    root = _json(initial)
    if (not 0 < len(initial) <= 2048 or type(root) is not dict or
            set(root) != set(expected) | {"nonce"} or
            any(root.get(k) != v for k, v in expected.items()) or
            type(root.get("nonce")) is not str or
            re.fullmatch(r"[0-9a-f]{32}", root["nonce"]) is None or
            _bytes(root) != initial):
        raise ValueError("Replaced recovery drill first SHA genesis")
    raw = history.read_bytes()
    if len(raw) > 40_000_000 or (raw and not raw.endswith(b"\n")):
        raise ValueError("Truncated recovery drill history")
    records, last_utc, previous_sha = [], None, ZERO
    for line in raw.splitlines():
        if not 0 < len(line) <= 3072 or len(records) >= 30000:
            raise ValueError("Oversized recovery drill SHA evidence")
        event = _json(line)
        last_utc = _validate_event(event, records[-1] if records else None,
                                   len(records)+1, last_utc, previous_sha)
        if line+b"\n" != _bytes(event):
            raise ValueError("Noncanonical recovery drill history bytes")
        previous_sha = event["event_sha256"]
        records.append(event)
    first = folder / "first_event.json"
    if records:
        if first.is_symlink() or not first.is_file() or first.stat().st_size > 512:
            raise ValueError("Recovery drill first event lost")
        raw_first = first.read_bytes()
        receipt = _json(raw_first)
        if (type(receipt) is not dict or set(receipt) != {
                "schema", "genesis_sha256", "first_event_sha256"} or
                receipt["schema"] != SCHEMA or
                receipt["genesis_sha256"] != _sha(initial) or
                receipt["first_event_sha256"] != records[0]["event_sha256"] or
                _bytes(receipt) != raw_first):
            raise ValueError("Original recovery drill first event rewritten")
    elif first.exists() or first.is_symlink():
        raise ValueError("First recovery receipt exists without SHA events")
    report = folder / "report.json"
    if records:
        if report.is_symlink() or not report.is_file() or report.stat().st_size > 4096:
            raise ValueError("Recovery drill last checkpoint is missing")
        raw_report = report.read_bytes()
        latest = _json(raw_report)
        last = records[-1]
        if (type(latest) is not dict or _bytes(latest) != raw_report or
                latest.get("status") != STATUS or
                latest.get("check_count") != len(records) or
                latest.get("chain_head_sha256") != last["event_sha256"] or
                latest.get("latest") != last or
                latest.get("independent_market_pit_certified") is not False or
                latest.get("actual_future_leader_skill_certified") is not False or
                latest.get("official_leader_promotions") != 0 or
                latest.get("messages_sent") != 0 or
                latest.get("external_api_calls") != 0):
            raise ValueError("Recovery drill report/history checkpoint mismatch")
    elif report.exists() or report.is_symlink():
        raise ValueError("Recovery drill report without first event")
    return records


def _html(report):
    current = report["latest"]
    return (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>EraLeader native original recovery DRY-RUN</title>"
        "<style>body{font:16px system-ui;max-width:800px;margin:2rem auto;"
        "padding:0 1rem}td{padding:8px;border-bottom:1px solid #bbb}</style>"
        "<h1>Original native encrypted backup · recovery rehearsal</h1>"
        "<p>Local DRY-RUN · no permanent plaintext · no live messages, PIT or "
        "investment-performance certification.</p>"
        "<p>Checks: "+str(report["check_count"])+"</p>"
        "<table><tr><td>Market</td><td>"+escape(current["market"])+"</td></tr>"
        "<tr><td>Status</td><td>"+escape(current["outcome"])+"</td></tr>"
        "<tr><td>Reason</td><td>"+escape(current["reason"])+"</td></tr>"
        "<tr><td>SHA prefix</td><td>"+escape(current["slot_sha256"][:12])+"</td></tr>"
        "</table><a href='index.html'>EraLeader dashboard</a></html>"
    )


def verify_native_recovery_drill_history(project, vault, witness, cert, scratch):
    """Read-only audit of prior first-recovery drill SHA events, no private key."""
    p, _, v, w, c, s = _inputs(
        project, "kr_"+"0"*24, vault, witness, cert, scratch)
    folder, _ = _output_paths(p)
    lock = folder / ".checks.lock"
    if lock.is_symlink() or not lock.is_file():
        raise ValueError("Missing original local recovery drill writer lock")
    fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Recovery drill history concurrently being written") from exc
        try:
            rows = _audit(folder, _genesis(p, v, w, c, s))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {
        "status": "LOCAL_NATIVE_RECOVERY_DRILL_HISTORY_VERIFIED",
        "check_count": len(rows), "chain_verified": True,
        "messages_sent": 0, "external_api_calls": 0,
        "official_leader_promotions": 0,
    }


def run_native_recovery_drill(project, slot, vault, witness, cert, key, scratch, *, clock=None):
    """Actually decrypt+replay into disposable external private scratch, then erase."""
    now = _clock(clock)
    project, slot, vault, witness, cert, scratch = _inputs(
        project, slot, vault, witness, cert, scratch)
    folder, site = _output_paths(project)
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    (folder / "site").mkdir(mode=0o700, exist_ok=True)
    lock = folder / ".checks.lock"
    had_lock = lock.exists()
    if not had_lock and ((folder / "genesis.json").exists() or
                         (folder / "history.jsonl").exists()):
        raise ValueError("Original local recovery drill lock was removed")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "rb+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent local native recovery rehearsal") from exc
        try:
            genesis, history = folder / "genesis.json", folder / "history.jsonl"
            if not genesis.exists() and not history.exists():
                if had_lock:
                    raise ValueError("Recovery drill history was deleted; no reset")
                _new(genesis, _bytes({**_genesis(project, vault, witness, cert, scratch),
                                      "nonce": uuid.uuid4().hex}))
                _new(history, b"")
            prior = _audit(folder, _genesis(project, vault, witness, cert, scratch))
            if prior and now < _utc(prior[-1]["observed_at_utc"]):
                raise ValueError("Recovery rehearsal local clock rollback")
            result = {
                "archive_sha256": ZERO, "encrypted_sha256": ZERO,
                "aes_gcm_authenticated": False,
                "first_watch_score_replayed": False, "census_index_replayed": False,
                "temporary_plaintext_path_removed": False,
                "outcome": "FAILED", "reason": "BACKUP_SHA_INVALID",
            }
            try:
                _private_key(Path(key))
            except (OSError, ValueError, TypeError):
                result["reason"] = "UNSAFE_OR_MISSING_KEY"
            else:
                try:
                    source = verify_encrypted_native_original(vault, slot, witness, cert)
                    if (source.get("status") !=
                            "ENCRYPTED_NATIVE_BACKUP_SHA_VERIFIED_NOT_DECRYPTED" or
                            source.get("ciphertext_verified") is not True or
                            source.get("authenticated_plaintext_verified") is not False or
                            source.get("messages_sent") != 0 or
                            source.get("external_api_calls") != 0 or
                            source.get("official_leader_promotions") != 0):
                        raise ValueError("Original native backup SHA did not verify")
                    result["archive_sha256"] = source["archive_sha256"]
                    result["encrypted_sha256"] = source["encrypted_sha256"]
                except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                    result["reason"] = "BACKUP_SHA_INVALID"
                else:
                    temp_name = None
                    try:
                        with TemporaryDirectory(
                                prefix=".eraleader-native-recovery-drill-", dir=scratch
                        ) as temporary:
                            temp_name = Path(temporary)
                            recovered = restore_encrypted_native_original(
                                vault, slot, witness, cert, key,
                                temp_name / "recovered_original")
                            if (recovered.get("status") !=
                                    "ENCRYPTED_NATIVE_FIRST_ORIGINAL_RESTORED_NOT_PIT_CERTIFIED" or
                                    recovered.get("archive_sha256") != result["archive_sha256"] or
                                    recovered.get("authenticated_plaintext_verified") is not True or
                                    recovered.get("first_original_watch_replayed") is not True or
                                    recovered.get("registered_index_chain_verified") is not True or
                                    recovered.get("official_leader_promotions") != 0 or
                                    recovered.get("messages_sent") != 0 or
                                    recovered.get("external_api_calls") != 0 or
                                    recovered.get("real_future_leader_accuracy_certified") is not False):
                                raise RuntimeError("Original native replay verification incomplete")
                            result.update(
                                aes_gcm_authenticated=True,
                                first_watch_score_replayed=True,
                                census_index_replayed=True,
                            )
                    except (ValueError, OSError, RuntimeError, FileExistsError):
                        result["reason"] = "DECRYPT_OR_REPLAY_FAILED"
                    if temp_name is not None and temp_name.exists():
                        # A cleanup failure is a local privacy incident:
                        # never record this as a successful proof.
                        result["reason"] = "PRIVATE_SCRATCH_CLEANUP_FAILED"
                    else:
                        result["temporary_plaintext_path_removed"] = True
                    if all(result[k] for k in (
                            "aes_gcm_authenticated", "first_watch_score_replayed",
                            "census_index_replayed", "temporary_plaintext_path_removed")):
                        result["outcome"] = "PASSED"
                        result["reason"] = "NONE"
            event = {
                "seq": len(prior)+1,
                "observed_at_utc": now.isoformat(),
                "slot_sha256": _sha(slot.encode()),
                "market": slot[:2].upper(),
                "outcome": result["outcome"],
                "reason": result["reason"],
                "archive_sha256": result["archive_sha256"],
                "encrypted_sha256": result["encrypted_sha256"],
                "aes_gcm_authenticated": result["aes_gcm_authenticated"],
                "first_watch_score_replayed": result["first_watch_score_replayed"],
                "census_index_replayed": result["census_index_replayed"],
                "temporary_plaintext_path_removed": result["temporary_plaintext_path_removed"],
                "no_live_delivery": True,
                "previous_sha256": prior[-1]["event_sha256"] if prior else ZERO,
            }
            event["event_sha256"] = _sha(_bytes(event))
            with open(history, "ab", buffering=0) as output:
                output.write(_bytes(event))
                os.fsync(output.fileno())
            if not prior:
                _new(folder / "first_event.json", _bytes({
                    "schema": SCHEMA, "genesis_sha256": _sha(genesis.read_bytes()),
                    "first_event_sha256": event["event_sha256"],
                }))
            report = {
                "status": STATUS,
                "check_count": len(prior)+1,
                "chain_head_sha256": event["event_sha256"],
                "latest": event,
                "independent_market_pit_certified": False,
                "actual_future_leader_skill_certified": False,
                "official_leader_promotions": 0,
                "messages_sent": 0,
                "external_api_calls": 0,
            }
            _atomic(folder / "report.json", _bytes(report))
            if len(_audit(folder, _genesis(project, vault, witness, cert, scratch))) != len(prior)+1:
                raise RuntimeError("Recovery drill appended original chain not verified")
            _atomic(folder / "site" / "index.html", _html(report).encode())
            if site.exists():
                page, index = site / "native_recovery_drill.html", site / "index.html"
                _atomic(page, _html(report).encode())
                if index.is_file() and index.stat().st_size <= 1_000_000:
                    html = index.read_text(encoding="utf-8")
                    if "native_recovery_drill.html" not in html and "</body>" in html:
                        link = ("<p><a href='native_recovery_drill.html'>"
                                "Original source recovery DRY-RUN</a></p>")
                        _atomic(index, html.replace("</body>", link+"</body>", 1).encode())
            return report
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
