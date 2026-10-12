"""6_5 read-only multi-cohort encrypted original vault DRY-RUN watchdog.

No private key, source ZIP, recovery, network, scheduled installation or live
messaging. Uses the original encrypted-vault verifier (ciphertext SHA + first
external witness) and independently pins each first healthy observation.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
import fcntl
import os
import re
import uuid

from .native_sha_watchdog import (
    ZERO, _bytes, _sha, _json, _utc, _clock, _new, _atomic,
)
from .native_encrypted_vault import (
    _safe_private_root, _verified, _paths, SLOT, DIGEST,
)
from .native_sha_witness import validate_witness_destination

SCHEMA = "eraleader.native_encrypted_vault_watchdog.v1"
DIR = "native_encrypted_alerts"
STATES = frozenset({"VERIFIED", "WAITING", "ANOMALY"})
ISSUES = frozenset({
    "NONE", "AWAITING_FIRST_NATIVE_EVIDENCE",
    "MISSING_SCAN_INPUT", "VAULT_ROOT_UNAVAILABLE",
    "WITNESS_ROOT_UNAVAILABLE", "FIRST_SHA_WITNESS_MISSING",
    "ENCRYPTED_BACKUP_MISSING", "ENCRYPTED_BACKUP_INCOMPLETE",
    "SHA_OR_CERTIFICATE_INVALID", "FIRST_ENCRYPTED_SHA_PIN_CHANGED",
})
WARNINGS = ISSUES - {"NONE", "AWAITING_FIRST_NATIVE_EVIDENCE"}
SHA_FIELDS = ("archive_sha256", "encrypted_sha256", "witness_sha256",
              "certificate_sha256")


def validate_monitor_inputs(project, slots, vault_root, witness_root, cert):
    """Fail before running market jobs for invalid or unsafe explicit paths.

    Unavailable but previously configured storage roots are assessed by the
    observer as missing, not silently recreated or adopted on the SSD.
    """
    project = Path(project).absolute()
    output = project / "output"
    if (project.is_symlink() or not project.is_dir() or
            output.is_symlink() or not output.is_dir()):
        raise ValueError("Native encrypted monitor requires existing local project/output")
    if not isinstance(slots, (tuple, list)) or not 1 <= len(slots) <= 128:
        raise ValueError("Explicit 1..128 encrypted native SHA monitoring slots required")
    if any(type(s) is not str or SLOT.fullmatch(s) is None for s in slots):
        raise ValueError("Only hashed KR/US native market-model slots accepted")
    if len(set(slots)) != len(slots):
        raise ValueError("Duplicate encrypted original SHA monitoring slot")
    roots = []
    for value in (vault_root, witness_root):
        path = _safe_private_root(Path(value), must_exist=False)
        if project == path or project in path.parents or path in project.parents:
            raise ValueError("Encrypted monitoring sources must not overlap research project")
        if path.exists():
            validate_witness_destination(project, path)
        roots.append(path)
    vault, witness = roots
    if vault == witness or vault in witness.parents or witness in vault.parents:
        raise ValueError("Vault and original first SHA witness directories must not overlap")
    cert = Path(cert)
    if (not cert.is_absolute() or ".." in cert.parts or cert.is_symlink() or
            any(p.is_symlink() for p in cert.parents)):
        raise ValueError("Absolute non-linked public recipient certificate required")
    if cert == project or cert in (vault, witness):
        raise ValueError("Certificate location conflicts with vault paths")
    return project, vault, witness, cert


def _paths_output(project):
    folder = project / "output" / DIR
    web = project / "output" / "site"
    paths = (folder, folder / "genesis.json", folder / "history.jsonl",
             folder / "first_event.json", folder / "report.json",
             folder / ".checks.lock", folder / "site",
             folder / "site" / "index.html", web,
             web / "native_encrypted_dry_run.html", web / "index.html")
    dirs = {folder, folder / "site", web}
    for path in paths:
        if path.is_symlink() or (path.exists() and
                (not path.is_dir() if path in dirs else not path.is_file())):
            raise ValueError("Unsafe native encrypted DRY-RUN audit output path")
    return folder, web


def _genesis(project, vault, witness, cert):
    return {
        "schema": SCHEMA,
        "project_sha256": _sha(str(project).encode()),
        "vault_root_sha256": _sha(str(vault).encode()),
        "witness_root_sha256": _sha(str(witness).encode()),
        "recipient_cert_path_sha256": _sha(str(cert).encode()),
    }


def _row(market, state, issue, hashes=None):
    hashes = hashes or {}
    return {
        "market": market, "state": state, "issue": issue,
        **{name: hashes.get(name, ZERO) for name in SHA_FIELDS},
    }


def _presence(root, slot, *, vault):
    if vault:
        _, cipher, receipt, guard, lock = _paths(root, slot)
        files = (cipher, receipt, guard, lock)
    else:
        files = (
            root / ("native_" + slot + "_first.json"),
            root / ("native_" + slot + "_guard.json"),
            root / (".native_" + slot + ".lock"),
        )
    return tuple(p.exists() or p.is_symlink() for p in files)


def _probe(slot, vault, witness, cert, pinned):
    market = slot[:2].upper()
    if not witness.is_dir():
        return _row(market, "ANOMALY", "WITNESS_ROOT_UNAVAILABLE")
    if not vault.is_dir():
        return _row(market, "ANOMALY", "VAULT_ROOT_UNAVAILABLE")
    w = _presence(witness, slot, vault=False)
    v = _presence(vault, slot, vault=True)
    if not any(w) and not any(v):
        if pinned:
            return _row(market, "ANOMALY", "FIRST_SHA_WITNESS_MISSING")
        return _row(market, "WAITING", "AWAITING_FIRST_NATIVE_EVIDENCE")
    if not all(w):
        return _row(market, "ANOMALY", "FIRST_SHA_WITNESS_MISSING")
    if not any(v):
        return _row(market, "ANOMALY", "ENCRYPTED_BACKUP_MISSING")
    if not all(v):
        return _row(market, "ANOMALY", "ENCRYPTED_BACKUP_INCOMPLETE")
    try:
        # The original strict verifier takes SH locks and checks ciphertext
        # SHA, first receipt/guard, cross-volume witness and X509 cert SHA.
        # It never requests a private decryption key or original SSD ZIP.
        checked = _verified(vault, slot, witness, cert)
        digests = {
            "archive_sha256": checked["archive_sha256"],
            "encrypted_sha256": checked["encrypted_sha256"],
            "witness_sha256": checked["original_witness_sha256"],
            "certificate_sha256": checked["certificate_sha256"],
        }
        if (checked.get("market") != market or
                any(type(x) is not str or DIGEST.fullmatch(x) is None
                    for x in digests.values())):
            raise ValueError("Invalid verified ciphertext/first SHA digest")
    except RuntimeError:
        # Concurrent first writer: do not turn an incomplete check into a
        # trustworthy market/backup incident record.
        raise
    except (OSError, ValueError, KeyError, TypeError):
        return _row(market, "ANOMALY", "SHA_OR_CERTIFICATE_INVALID")
    if pinned and any(pinned[k] != digests[k] for k in SHA_FIELDS):
        return _row(market, "ANOMALY", "FIRST_ENCRYPTED_SHA_PIN_CHANGED")
    return _row(market, "VERIFIED", "NONE", digests)


def _validate_row(obj):
    if (type(obj) is not dict or
            set(obj) != {"market", "state", "issue", *SHA_FIELDS} or
            obj["market"] not in {"KR", "US"} or obj["state"] not in STATES or
            obj["issue"] not in ISSUES or
            any(type(obj[k]) is not str or DIGEST.fullmatch(obj[k]) is None
                for k in SHA_FIELDS)):
        raise ValueError("Forged or incomplete encrypted backup health snapshot")
    actual = {obj[k] for k in SHA_FIELDS}
    if obj["state"] == "VERIFIED":
        if obj["issue"] != "NONE" or ZERO in actual:
            raise ValueError("Unverified encrypted original incorrectly marked healthy")
    elif (actual != {ZERO} or
          (obj["state"] == "WAITING") != (obj["issue"] == "AWAITING_FIRST_NATIVE_EVIDENCE") or
          (obj["state"] == "ANOMALY" and obj["issue"] not in WARNINGS)):
        raise ValueError("Forged encrypted backup non-healthy status")


def _expected_alerts(previous, current):
    alerts = []
    for key, row in sorted(current.items()):
        earlier = previous.get(key)
        if row["state"] == "ANOMALY" and (
                earlier is None or earlier["state"] != "ANOMALY" or
                earlier["issue"] != row["issue"]):
            alerts.append(key + ":" + row["issue"])
        elif row["state"] == "VERIFIED" and earlier and earlier["state"] == "ANOMALY":
            alerts.append(key + ":RESTORED")
    return alerts


def _audit(folder, expected):
    first, events_file, pinned_file = (
        folder / "genesis.json", folder / "history.jsonl",
        folder / "first_event.json",
    )
    if any(p.is_symlink() or not p.is_file() for p in (first, events_file)):
        raise ValueError("Original encrypted monitoring genesis/history absent")
    raw = first.read_bytes()
    genesis = _json(raw)
    if (not 0 < len(raw) <= 2048 or type(genesis) is not dict or
            set(genesis) != set(expected) | {"nonce"} or
            any(genesis.get(k) != v for k, v in expected.items()) or
            type(genesis.get("nonce")) is not str or
            re.fullmatch(r"[a-f0-9]{32}", genesis["nonce"]) is None or
            _bytes(genesis) != raw):
        raise ValueError("Encrypted watchdog first genesis/root commitment mismatch")
    chain = events_file.read_bytes()
    if len(chain) > 30_000_000 or (chain and not chain.endswith(b"\n")):
        raise ValueError("Encrypted watchdog history truncated or oversized")
    records, first_pins = [], {}
    prior_sha, last_at = ZERO, None
    for line in chain.splitlines():
        if not 0 < len(line) <= 200_000 or len(records) >= 20000:
            raise ValueError("Encrypted watchdog SHA event oversized")
        event = _json(line)
        if (type(event) is not dict or set(event) != {
                "seq", "observed_at_utc", "cohorts", "new_alerts",
                "previous_sha256", "event_sha256"} or
                type(event["seq"]) is not int or event["seq"] != len(records)+1 or
                event["previous_sha256"] != prior_sha or line+b"\n" != _bytes(event)):
            raise ValueError("Encrypted watchdog original SHA chain malformed")
        at = _utc(event["observed_at_utc"])
        if last_at is not None and at < last_at:
            raise ValueError("Encrypted watchdog local OS clock rollback")
        last_at = at
        rows = event["cohorts"]
        prev = records[-1]["cohorts"] if records else {}
        if (type(rows) is not dict or not 1 <= len(rows) <= 128 or
                not set(prev).issubset(rows)):
            raise ValueError("Encrypted watchdog monitored inventory dropped")
        for key, value in rows.items():
            if type(key) is not str or DIGEST.fullmatch(key) is None:
                raise ValueError("Invalid anonymized first-native slot key")
            _validate_row(value)
            pin = first_pins.get(key)
            if value["state"] == "VERIFIED":
                if pin and any(pin[k] != value[k] for k in SHA_FIELDS):
                    raise ValueError("Encrypted vault initial SHA pin silently revised")
                if pin and pin["market"] != value["market"]:
                    raise ValueError("Encrypted vault market source revised")
                if pin is None:
                    first_pins[key] = value
        if (type(event["new_alerts"]) is not list or
                event["new_alerts"] != _expected_alerts(prev, rows)):
            raise ValueError("Encrypted watchdog incident transitions falsified")
        unsigned = {k: v for k, v in event.items() if k != "event_sha256"}
        if event["event_sha256"] != _sha(_bytes(unsigned)):
            raise ValueError("Encrypted watchdog SHA event altered")
        prior_sha = event["event_sha256"]
        records.append(event)
    if records:
        if pinned_file.is_symlink() or not pinned_file.is_file() or (
                pinned_file.stat().st_size > 1024):
            raise ValueError("Encrypted watchdog first-write checkpoint missing")
        stamp_bytes = pinned_file.read_bytes()
        stamp = _json(stamp_bytes)
        if (type(stamp) is not dict or set(stamp) != {
                "schema", "genesis_sha256", "first_event_sha256"} or
                stamp["schema"] != SCHEMA or stamp["genesis_sha256"] != _sha(raw) or
                stamp["first_event_sha256"] != records[0]["event_sha256"] or
                _bytes(stamp) != stamp_bytes):
            raise ValueError("Encrypted watchdog original first receipt replaced")
    elif pinned_file.exists() or pinned_file.is_symlink():
        raise ValueError("Encrypted watchdog original first event without chain")
    report = folder / "report.json"
    if records:
        if report.is_symlink() or not report.is_file() or report.stat().st_size > 100_000:
            raise ValueError("Encrypted watchdog latest report checkpoint missing")
        raw_report = report.read_bytes()
        current = _json(raw_report)
        last = records[-1]
        if (type(current) is not dict or _bytes(current) != raw_report or
                current.get("status") != "LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED" or
                current.get("check_count") != len(records) or
                current.get("chain_head_sha256") != last["event_sha256"] or
                current.get("cohorts") != last["cohorts"] or
                current.get("new_alerts") != last["new_alerts"] or
                current.get("local_artifacts_only") is not True or
                current.get("authenticated_plaintext_verified") is not False or
                current.get("independent_market_pit_certified") is not False or
                current.get("real_future_leader_accuracy_certified") is not False or
                current.get("official_leader_promotions") != 0 or
                current.get("messages_sent") != 0 or
                current.get("external_api_calls") != 0):
            raise ValueError("Encrypted watchdog previous report/history rollback")
    elif report.exists() or report.is_symlink():
        raise ValueError("Encrypted watchdog report without first SHA event")
    return records, first_pins


def verify_native_encrypted_watchdog(project, vault_root, witness_root, cert):
    """Read-only check of all earlier encrypted vault audit events."""
    p, vault, witness, cert = validate_monitor_inputs(
        project, ["kr_"+"0"*24], vault_root, witness_root, cert)
    folder, _ = _paths_output(p)
    lock = folder / ".checks.lock"
    if not lock.is_file() or lock.is_symlink():
        raise ValueError("Missing first encrypted SHA watchdog lock")
    fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Encrypted watchdog update is in progress") from exc
        try:
            records, pins = _audit(folder, _genesis(p, vault, witness, cert))
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"check_count": len(records), "first_verified_pins": len(pins),
            "history_sha_chain_verified": True}


def _html(report, *, main_link):
    rows = "".join(
        "<tr><td>"+escape(record["market"])+"</td><td>"+escape(key[:12])+
        "</td><td>"+escape(record["state"])+"</td><td>"+
        escape(record["issue"])+"</td></tr>"
        for key, record in sorted(report["cohorts"].items()))
    count = sum(row["state"] == "ANOMALY" for row in report["cohorts"].values())
    pending = sum(row["state"] == "WAITING" for row in report["cohorts"].values())
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader encrypted backup SHA DRY-RUN</title>"
            "<style>body{font:16px system-ui;max-width:980px;margin:2rem auto;padding:0 1rem}"
            "table{border-collapse:collapse;width:100%}"
            "td,th{padding:10px;border-bottom:1px solid #bbb}"
            "</style><h1>Encrypted native Top-K archive · DRY-RUN integrity</h1>"
            "<p>SHA-only original ciphertext+external witness check; no private key, "
            "no live alerts, no official leader or PIT certification.</p>"
            "<p>Checks: "+str(report["check_count"])+
            " | cohorts: "+str(len(report["cohorts"]))+
            " | anomalies: "+str(count)+" | pending: "+str(pending)+
            " | new alerts: "+str(len(report["new_alerts"]))+"</p>"
            "<a href='"+main_link+"'>EraLeader local dashboard</a>"
            "<table><thead><tr><th>Market</th><th>First slot SHA prefix</th>"
            "<th>State</th><th>Issue</th></tr></thead><tbody>"+
            rows+"</tbody></table></html>")


def run_native_encrypted_watchdog(project, slots, vault_root, witness_root, cert, *, clock=None):
    """Periodically check SHA-only encrypted vault, publish unsent local dashboard."""
    now = _clock(clock)
    project, vault, witness, cert = validate_monitor_inputs(
        project, slots, vault_root, witness_root, cert)
    folder, web = _paths_output(project)
    paths = {_sha(slot.encode()): slot for slot in slots}
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    (folder / "site").mkdir(mode=0o700, exist_ok=True)
    lock = folder / ".checks.lock"
    lock_present = lock.exists()
    if not lock_present and ((folder / "genesis.json").exists() or
                             (folder / "history.jsonl").exists()):
        raise ValueError("Original encrypted SHA monitoring lock was deleted")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "rb+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another encrypted SHA monitor is writing") from exc
        try:
            genesis, history = folder / "genesis.json", folder / "history.jsonl"
            if not genesis.exists() and not history.exists():
                if lock_present:
                    raise ValueError("Original encrypted SHA history deleted; never reset")
                _new(genesis, _bytes({**_genesis(project, vault, witness, cert),
                                      "nonce": uuid.uuid4().hex}))
                _new(history, b"")
            prior, first_pins = _audit(
                folder, _genesis(project, vault, witness, cert))
            if prior and now < _utc(prior[-1]["observed_at_utc"]):
                raise ValueError("Encrypted SHA watchdog local clock rolled backward")
            prev = prior[-1]["cohorts"] if prior else {}
            if len(set(prev) | set(paths)) > 128:
                raise ValueError("Encrypted SHA monitoring inventory exceeds 128 slots")
            current = {}
            for key in sorted(set(prev) | set(paths)):
                if key not in paths:
                    current[key] = _row(prev[key]["market"], "ANOMALY",
                                        "MISSING_SCAN_INPUT")
                else:
                    current[key] = _probe(paths[key], vault, witness, cert,
                                          first_pins.get(key))
            warnings = _expected_alerts(prev, current)
            event = {"seq": len(prior)+1, "observed_at_utc": now.isoformat(),
                     "cohorts": current, "new_alerts": warnings,
                     "previous_sha256": prior[-1]["event_sha256"] if prior else ZERO}
            event["event_sha256"] = _sha(_bytes(event))
            with open(history, "ab", buffering=0) as output:
                output.write(_bytes(event))
                os.fsync(output.fileno())
            if not prior:
                _new(folder / "first_event.json", _bytes({
                    "schema": SCHEMA, "genesis_sha256": _sha(genesis.read_bytes()),
                    "first_event_sha256": event["event_sha256"]}))
            result = {
                "status": "LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED",
                "check_count": len(prior)+1,
                "chain_head_sha256": event["event_sha256"],
                "cohorts": current, "new_alerts": warnings,
                "local_artifacts_only": True,
                "authenticated_plaintext_verified": False,
                "independent_market_pit_certified": False,
                "real_future_leader_accuracy_certified": False,
                "official_leader_promotions": 0,
                "messages_sent": 0, "external_api_calls": 0,
            }
            _atomic(folder / "report.json", _bytes(result))
            checked, _ = _audit(folder, _genesis(project, vault, witness, cert))
            if len(checked) != event["seq"]:
                raise RuntimeError("Encrypted native SHA event append was not verified")
            _atomic(folder / "site" / "index.html",
                    _html(result, main_link="../../site/index.html").encode())
            if web.exists():
                page, index = web / "native_encrypted_dry_run.html", web / "index.html"
                _atomic(page, _html(result, main_link="index.html").encode())
                if index.is_file() and index.stat().st_size <= 1_000_000:
                    original = index.read_text(encoding="utf-8")
                    if ("native_encrypted_dry_run.html" not in original and
                            "</body>" in original):
                        new_link = ("<p><a href='native_encrypted_dry_run.html'>"
                                    "Encrypted first Top-K SHA DRY-RUN monitor</a></p>")
                        _atomic(index, original.replace(
                            "</body>", new_link+"</body>", 1).encode())
            return result
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
