"""6_5 read-only local encrypted native recovery readiness: certificate/key health.

Public certificate expiry affects NEW backups, not historic GCM ciphertext.
An optional private-key check derives PUBLIC SPKI in memory and compares it to
the certificate; the private key/password are never copied or logged.
This is a diagnostic, not a DR drill or a real market/PIT attestation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import math
import os
import shutil
import stat
import subprocess

from .native_encrypted_vault import _private_key, verify_encrypted_native_original
from .native_encrypted_watchdog import validate_monitor_inputs
from .native_sha_watchdog import _bytes, _atomic

STATUS = "LOCAL_NATIVE_RECOVERY_READINESS_RESEARCH_NOT_ATTESTED"


def _openssl(*args, stdin=None):
    executable = shutil.which("openssl")
    if not executable:
        raise ValueError("OpenSSL binary unavailable")
    try:
        proc = subprocess.run([executable, *map(str, args)],
                              input=stdin, stdin=subprocess.DEVNULL if stdin is None else None,
                              capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("OpenSSL local public-key inspection unavailable") from exc
    if proc.returncode != 0 or len(proc.stdout) > 65536:
        raise ValueError("OpenSSL certificate/key inspection invalid")
    return proc.stdout


def _cert_window(cert, now, warning_days):
    cert = Path(cert)
    try:
        if (cert.is_symlink() or any(p.is_symlink() for p in cert.parents) or
                not cert.is_file() or not 0 < cert.stat().st_size <= 65536):
            raise ValueError("Unsafe/missing public cert")
        content = _openssl("x509", "-in", cert, "-noout", "-startdate", "-enddate")
        dates = {}
        for line in content.decode("ascii").strip().splitlines():
            k, delim, value = line.partition("=")
            if not delim or k in dates or k not in {"notBefore", "notAfter"}:
                raise ValueError("Invalid X509 date record")
            dates[k] = datetime.strptime(value, "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
        if set(dates) != {"notBefore", "notAfter"} or dates["notBefore"] >= dates["notAfter"]:
            raise ValueError("Invalid X509 validity interval")
    except (ValueError, UnicodeError, OSError):
        return {"status": "INVALID_OR_MISSING", "expires_at_utc": None,
                "days_remaining": None}
    expiry = dates["notAfter"]
    if now < dates["notBefore"]:
        state = "NOT_YET_VALID"
    elif now >= expiry:
        state = "EXPIRED_FOR_NEW_BACKUPS"
    elif expiry - now <= timedelta(days=warning_days):
        state = "EXPIRING_FOR_NEW_BACKUPS"
    else:
        state = "CURRENT"
    return {"status": state, "expires_at_utc": expiry.isoformat(),
            "days_remaining": math.ceil((expiry - now).total_seconds() / 86400)}


def _key_status(project, vault, witness, cert, key):
    if key is None:
        return "NOT_CONFIGURED_NO_RECOVERY_ASSERTION"
    key = Path(key)
    if (not key.is_absolute() or ".." in key.parts or
            key.is_symlink() or any(p.is_symlink() for p in key.parents) or
            key == project or project in key.parents or
            key == vault or vault in key.parents or
            key == witness or witness in key.parents):
        return "UNSAFE_PRIVATE_KEY_PATH"
    try:
        _private_key(key)
        from_cert = _openssl("x509", "-in", cert, "-pubkey", "-noout")
        canonical_pub = _openssl("pkey", "-pubin", "-outform", "DER", stdin=from_cert)
        # An explicit EMPTY passphrase prevents hangs/prompts even for keys
        # which need one. Encrypted keys need a separate operator-led process.
        derived_pub = _openssl("pkey", "-in", key, "-pubout", "-outform", "DER",
                               "-passin", "pass:")
    except (ValueError, OSError):
        return "MISSING_UNREADABLE_OR_UNSAFE_KEY"
    return ("PUBLIC_KEY_MATCHED_NO_RECOVERY_DRILL" if
            sha256(canonical_pub).digest() == sha256(derived_pub).digest()
            else "PRIVATE_KEY_CERT_MISMATCH")


def _time(clock):
    now = clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Recovery readiness requires timezone aware local clock")
    return now.astimezone(timezone.utc)


def _html(info):
    entries = "".join(
        "<tr><td>" + escape(row["market"]) + "</td><td>" +
        escape(identifier[:12]) + "</td><td>" +
        escape(row["status"]) + "</td></tr>"
        for identifier, row in sorted(info["cohorts"].items()))
    expires = info["certificate"]["expires_at_utc"] or "N/A"
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader first native recovery readiness</title>"
            "<style>body{font:16px system-ui;max-width:920px;margin:2rem auto;padding:1rem}"
            "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;"
            "padding:10px;text-align:left}</style>"
            "<h1>Original first-native encrypted vault · recovery readiness DRY-RUN</h1>"
            "<p>Local-only, no key exported, no decrypt/restore drill, no API or live message.</p>"
            "<p>Public certificate: " + escape(info["certificate"]["status"]) +
            " | expires UTC: " + escape(expires) + "</p>"
            "<p>Private recovery key: " + escape(info["private_key_status"]) + "</p>"
            "<p>Backup copies verified: " + str(info["verified_backup_count"]) +
            "/" + str(len(info["cohorts"])) + "</p>"
            "<table><tr><th>Market</th><th>Hashed cohort</th><th>Encrypted SHA</th></tr>"
            + entries + "</table>"
            "<p>Expired public certificate does not revoke OLD ciphertext; "
            "new encryptions require a valid certificate. Key match is not recovery replay.</p>"
            "<a href='index.html'>EraLeader local dashboard</a></html>")


def inspect_native_recovery_readiness(
    project, slots, vault_root, witness_root, recipient_cert, *,
    key=None, warning_days=90, clock=None,
):
    """Read-only per-slot ciphertext and optional restricted-key match report."""
    now = _time(clock)
    if type(warning_days) is not int or not 1 <= warning_days <= 365:
        raise ValueError("Recovery certificate warning_days must be 1..365")
    project, vault, witness, cert = validate_monitor_inputs(
        project, slots, vault_root, witness_root, recipient_cert)
    cert_info = _cert_window(cert, now, warning_days)
    key_info = _key_status(project, vault, witness, cert, key)
    all_rows = {}
    for slot in slots:
        item = {"market": slot[:2].upper(), "status": "MISSING_OR_INVALID_ORIGINAL_BACKUP_SHA"}
        try:
            evidence = verify_encrypted_native_original(vault, slot, witness, cert)
            if (evidence.get("ciphertext_verified") is True and
                    evidence.get("authenticated_plaintext_verified") is False and
                    evidence.get("messages_sent") == 0 and evidence.get("external_api_calls") == 0
                    and evidence.get("official_leader_promotions") == 0):
                item["status"] = "ORIGINAL_CIPHERTEXT_SHA_WITNESS_VERIFIED"
        except RuntimeError:
            # Writer in progress; do not treat an inconclusive read as complete.
            raise
        except (OSError, ValueError, KeyError, TypeError):
            pass
        all_rows[sha256(slot.encode()).hexdigest()] = item
    verified = sum(v["status"] == "ORIGINAL_CIPHERTEXT_SHA_WITNESS_VERIFIED"
                   for v in all_rows.values())
    actionable = (verified != len(all_rows) or cert_info["status"] != "CURRENT" or
                  key_info != "PUBLIC_KEY_MATCHED_NO_RECOVERY_DRILL")
    result = {
        "status": STATUS, "observed_at_utc": now.isoformat(),
        "certificate": cert_info, "private_key_status": key_info,
        "verified_backup_count": verified, "cohorts": all_rows,
        "needs_operator_review": actionable, "recovery_drill_executed": False,
        "authenticated_plaintext_verified": False,
        "independent_timestamp_attested": False,
        "independent_market_pit_certified": False,
        "real_future_leader_accuracy_certified": False,
        "official_leader_promotions": 0, "external_api_calls": 0,
        "messages_sent": 0, "local_artifacts_only": True,
    }
    # Diagnostic site is derived-only; never write into vault/witness/first ZIP.
    site = project / "output" / "site"
    out = project / "output" / "native_recovery_readiness"
    for folder in (out, site):
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError("Unsafe local recovery readiness output folder")
    targets = (out / "report.json", out / "index.html",
               site / "native_recovery_readiness.html", site / "index.html")
    if any(file.is_symlink() for file in targets):
        raise ValueError("Linked recovery readiness output is not permitted")
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    _atomic(out / "report.json", _bytes(result))
    _atomic(out / "index.html", _html(result).encode())
    if site.exists():
        _atomic(site / "native_recovery_readiness.html", _html(result).encode())
        index = site / "index.html"
        if index.is_file() and index.stat().st_size <= 1000000:
            raw = index.read_text(encoding="utf-8")
            if "native_recovery_readiness.html" not in raw and "</body>" in raw:
                link = ("<p><a href='native_recovery_readiness.html'>"
                        "Private backup recovery readiness (local)</a></p>")
                _atomic(index, raw.replace("</body>", link + "</body>", 1).encode())
    return result
