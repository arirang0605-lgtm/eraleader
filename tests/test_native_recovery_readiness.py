"""6_5 local recovery X509 expiry and owner-only private-key pairing.

Only PUBLIC SPKI ever leaves private-key OpenSSL subprocess; no plaintext
market/issuer evidence is decrypted or copied by this readiness diagnostic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader.native_recovery_readiness import (
    inspect_native_recovery_readiness, _cert_window, _key_status, STATUS,
)
from eraleader.native_encrypted_vault import (
    verify_encrypted_native_original, restore_encrypted_native_original, _cert,
)
from test_native_encrypted_vault import rig, backup

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_native_recovery_readiness.py"


def audit(rig, key=None, clock=None, warn=90):
    from eraleader.native_evidence_archive import _slot
    from eraleader.native_first_capture import read_capture_plan
    slot = _slot(read_capture_plan(rig["plan"])[0])
    return inspect_native_recovery_readiness(
        rig["project"], [slot], rig["vault"], rig["witness"],
        rig["cert"], key=key, clock=clock, warning_days=warn)


def test_verified_local_ciphertext_and_matching_owner_private_key(rig):
    original = backup(rig)
    original_bytes = {str(f): sha256(f.read_bytes()).hexdigest()
                      for f in [rig["zip"], rig["key"], rig["cert"],
                                next(rig["vault"].glob("*.cms"))]}
    (rig["project"]/"output"/"site").mkdir()
    (rig["project"]/"output"/"site"/"index.html").write_text(
        "<html><body>EraLeader</body></html>")
    result = audit(rig, key=rig["key"], warn=1)
    assert result["status"] == STATUS
    assert result["private_key_status"] == "PUBLIC_KEY_MATCHED_NO_RECOVERY_DRILL"
    assert result["certificate"]["status"] in {"CURRENT", "EXPIRING_FOR_NEW_BACKUPS"}
    assert result["verified_backup_count"] == 1
    assert result["recovery_drill_executed"] is False
    assert result["authenticated_plaintext_verified"] is False
    assert result["messages_sent"] == result["external_api_calls"] == 0
    page = (rig["project"]/"output"/"site"/"native_recovery_readiness.html").read_text()
    assert "PUBLIC_KEY_MATCHED" in page and "DRY-RUN" in page
    assert "native_recovery_readiness.html" in (
        rig["project"]/"output"/"site"/"index.html").read_text()
    for sensitive in (str(rig["key"]), str(rig["cert"]), str(rig["plan"]),
                      "issuer_id", "security_id"):
        assert sensitive not in page
        assert sensitive not in (rig["project"]/"output"/
                                 "native_recovery_readiness"/"report.json").read_text()
    assert original_bytes == {str(f): sha256(f.read_bytes()).hexdigest()
                               for f in [rig["zip"], rig["key"], rig["cert"],
                                         next(rig["vault"].glob("*.cms"))]}


def test_no_user_key_never_misclaims_recovery_ready(rig):
    backup(rig)
    result = audit(rig)
    assert result["verified_backup_count"] == 1
    assert result["private_key_status"] == "NOT_CONFIGURED_NO_RECOVERY_ASSERTION"
    assert result["needs_operator_review"] is True


def test_certificate_expiry_only_blocks_new_backups_not_old_verification(rig):
    first = backup(rig)
    dates = _cert_window(rig["cert"], datetime.now(timezone.utc), 1)
    expiry = datetime.fromisoformat(dates["expires_at_utc"])
    after = audit(rig, key=rig["key"], clock=expiry+timedelta(days=1))
    assert after["certificate"]["status"] == "EXPIRED_FOR_NEW_BACKUPS"
    assert after["needs_operator_review"] is True
    assert after["verified_backup_count"] == 1
    # Actual existing CMS read still verifies, even after simulated expiry.
    check = verify_encrypted_native_original(
        rig["vault"], first["slot"], rig["witness"], rig["cert"])
    assert check["archive_sha256"] == first["archive_sha256"]
    recovered = restore_encrypted_native_original(
        rig["vault"], first["slot"], rig["witness"], rig["cert"],
        rig["key"], rig["project"].parent/"recovered_expiry_warning")
    assert recovered["first_original_watch_replayed"] is True


def test_certificate_within_warning_window_is_not_counted_as_expired(rig):
    backup(rig)
    at = _cert_window(rig["cert"], datetime.now(timezone.utc), 90)
    expiry = datetime.fromisoformat(at["expires_at_utc"])
    result = audit(rig, key=rig["key"], clock=expiry-timedelta(hours=5))
    assert result["certificate"]["status"] == "EXPIRING_FOR_NEW_BACKUPS"
    assert result["verified_backup_count"] == 1


@pytest.mark.parametrize("invalid", [0, -2, 366, True, "90"])
def test_invalid_certificate_warning_window_fails_before_output(rig,invalid):
    with pytest.raises(ValueError, match="warning_days"):
        audit(rig, warn=invalid)
    assert not (rig["project"]/"output"/"native_recovery_readiness").exists()


def test_unmatched_private_key_does_not_look_ready(rig,tmp_path):
    backup(rig)
    wrong = tmp_path/"other_key.pem"
    run = subprocess.run(["openssl","genrsa","-out",str(wrong),"2048"],capture_output=True)
    assert run.returncode == 0
    wrong.chmod(0o600)
    result = audit(rig,key=wrong)
    assert result["private_key_status"] == "PRIVATE_KEY_CERT_MISMATCH"
    assert result["needs_operator_review"] is True


def test_world_readable_private_key_is_rejected_without_export(rig):
    backup(rig)
    rig["key"].chmod(0o644)
    result = audit(rig,key=rig["key"])
    assert result["private_key_status"] == "MISSING_UNREADABLE_OR_UNSAFE_KEY"
    assert result["needs_operator_review"] is True
    assert result["external_api_calls"] == 0


def test_key_stored_under_git_project_not_read_even_with_mode600(rig):
    backup(rig)
    prohibited=rig["project"]/"secret.pem"
    prohibited.write_bytes(rig["key"].read_bytes())
    prohibited.chmod(0o600)
    result=audit(rig,key=prohibited)
    assert result["private_key_status"] == "UNSAFE_PRIVATE_KEY_PATH"
    assert result["verified_backup_count"] == 1


def test_ciphertext_mutation_never_misreported_as_readiness(rig):
    backup(rig)
    cipher = next(rig["vault"].glob("*.cms"))
    corrupted=bytearray(cipher.read_bytes())
    corrupted[len(corrupted)//2] ^= 1
    cipher.write_bytes(corrupted)
    result=audit(rig,key=rig["key"])
    assert result["verified_backup_count"] == 0
    assert result["needs_operator_review"] is True


def test_missing_first_cipher_and_witness_are_not_ready(rig):
    result=audit(rig,key=None)
    assert result["verified_backup_count"] == 0
    assert result["needs_operator_review"] is True


def test_public_cert_not_a_key_and_invalid_cert_is_not_current(rig):
    result = _cert_window(rig["key"], datetime.now(timezone.utc), 90)
    assert result["status"] == "INVALID_OR_MISSING"
    assert result["expires_at_utc"] is None


def test_historic_certificate_validation_uses_dates_not_checkend(rig,monkeypatch):
    # Even if a system reports x509 -checkend 0 as expired, the historical
    # verification routine must use -dates (original bytes still SHA pinned).
    from eraleader import native_encrypted_vault as vault_module
    backup(rig)
    orig = vault_module.subprocess.run
    calls=[]
    def controlled(command, **kwargs):
        if len(command)>1 and command[1]=="x509":
            calls.append(list(command))
            if "-checkend" in command:
                raise AssertionError("historic encrypted ZIP verification may not check current cert validity")
        return orig(command,**kwargs)
    monkeypatch.setattr(vault_module.subprocess,"run",controlled)
    value=verify_encrypted_native_original(
        rig["vault"], next(rig["vault"].glob("*.cms")).stem.removeprefix("native_"),
        rig["witness"],rig["cert"])
    assert value["ciphertext_verified"] is True
    assert any("-dates" in x for x in calls)


def test_cli_output_sanitized_and_distinct_derived_site(rig,capsys):
    from scripts.run_native_recovery_readiness import main
    first=backup(rig)
    opts=["--project",str(rig["project"]),"--slot",first["slot"],
          "--vault-root",str(rig["vault"]),
          "--witness-root",str(rig["witness"]),
          "--recipient-cert",str(rig["cert"]),
          "--private-key",str(rig["key"])]
    assert main(opts)==0
    message=capsys.readouterr().out
    assert "PUBLIC_KEY_MATCHED" in message
    for sensitive in (str(rig["key"]),str(rig["cert"]),str(rig["plan"])):
        assert sensitive not in message
    assert json.loads(message)["status"]==STATUS


def test_existing_symlinked_dashboard_destination_rejected(rig,tmp_path):
    backup(rig)
    site=rig["project"]/"output"/"site"
    site.mkdir()
    external=tmp_path/"external.html"
    external.write_text("untouched")
    (site/"native_recovery_readiness.html").symlink_to(external)
    with pytest.raises(ValueError,match="Linked"):
        audit(rig,key=rig["key"])
    assert external.read_text()=="untouched"


def test_real_expired_x509_refused_for_new_backup_but_historic_sha_usable(tmp_path):
    # OpenSSL CA issues an ACTUALLY expired (Jan 2025) public certificate.
    # This is a local synthetic key/cert only, not an operating credential.
    local=tmp_path/"historical_x509"
    local.mkdir()
    key=local/"private.pem"
    request=local/"request.csr"
    ca=local/"ca.pem"
    old=local/"historical_expired.crt"
    def openssl(*args):
        result=subprocess.run(["openssl",*map(str,args)],capture_output=True)
        assert result.returncode==0, result.stderr[-220:]
    openssl("req","-new","-newkey","rsa:2048","-nodes",
            "-subj","/CN=EraLeaderExpiredLocalFixture",
            "-keyout",key,"-out",request)
    openssl("req","-x509","-new","-key",key,
            "-subj","/CN=EraLeaderLocalIssuer",
            "-days","1","-out",ca)
    (local/"index.txt").write_text("")
    (local/"serial").write_text("01\n")
    (local/"newcerts").mkdir()
    config=local/"ca.cnf"
    config.write_text(
        "[ca]\ndefault_ca=CA_default\n[CA_default]\n"
        f"dir={local}\n"
        "database=$dir/index.txt\nnew_certs_dir=$dir/newcerts\n"
        "serial=$dir/serial\nprivate_key=$dir/private.pem\n"
        "certificate=$dir/ca.pem\ndefault_md=sha256\n"
        "policy=policy_any\n[policy_any]\ncommonName=supplied\n")
    openssl("ca","-selfsign","-batch","-config",config,
            "-in",request,"-out",old,"-notext",
            "-startdate","20250101000000Z","-enddate","20250102000000Z")
    with pytest.raises(ValueError,match="expired"):
        _cert(old,require_current=True)
    assert _cert(old,require_current=False) == sha256(old.read_bytes()).hexdigest()
