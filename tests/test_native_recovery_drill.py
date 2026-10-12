"""6_5 encrypted native original source recovery rehearsal (synthetic only).

Never stores decrypted ZIP, original issuer identities, sources, key paths
or private key bytes inside a public dashboard or Git.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader import native_sha_witness
from eraleader.native_recovery_drill import (
    run_native_recovery_drill, verify_native_recovery_drill_history, STATUS,
)
from test_native_encrypted_vault import rig, backup
from test_scheduled_native_archive import NOW

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_native_recovery_drill.py"


@pytest.fixture
def prepared(rig, tmp_path):
    archive = backup(rig)
    scratch = tmp_path / "safe_mac_rehearsal_scratch"
    scratch.mkdir(mode=0o700)
    scratch.chmod(0o700)
    return rig, archive, scratch


def do(prepared, *, key=None, slot=None, clock=NOW+timedelta(minutes=4)):
    rig, archived, scratch = prepared
    return run_native_recovery_drill(
        rig["project"], slot or archived["slot"], rig["vault"],
        rig["witness"], rig["cert"], key if key is not None else rig["key"],
        scratch, clock=clock)


def files(prepared):
    return prepared[0]["project"] / "output" / "native_recovery_drills"


def audit(prepared):
    rig, _, scratch = prepared
    return verify_native_recovery_drill_history(
        rig["project"], rig["vault"], rig["witness"], rig["cert"], scratch)


def assert_erased(prepared):
    _, _, scratch = prepared
    assert list(scratch.iterdir()) == []


def test_successful_authentication_replay_and_cleanup_no_plaintext(prepared):
    rig, archived, scratch = prepared
    (rig["project"] / "output" / "site").mkdir()
    (rig["project"] / "output" / "site" / "index.html").write_text(
        "<html><body>EraLeader research</body></html>")
    original = sha256(rig["zip"].read_bytes()).hexdigest()
    out = do(prepared)
    assert out["status"] == STATUS
    assert out["check_count"] == 1
    last = out["latest"]
    assert last["outcome"] == "PASSED" and last["reason"] == "NONE"
    assert last["aes_gcm_authenticated"] is True
    assert last["first_watch_score_replayed"] is True
    assert last["census_index_replayed"] is True
    assert last["temporary_plaintext_path_removed"] is True
    assert last["archive_sha256"] == original
    assert_erased(prepared)
    assert sha256(rig["zip"].read_bytes()).hexdigest() == original
    assert out["messages_sent"] == out["external_api_calls"] == 0
    assert out["actual_future_leader_skill_certified"] is False
    page = (rig["project"] / "output" / "site" / "native_recovery_drill.html")
    assert page.is_file() and "PASSED" in page.read_text()
    assert "native_recovery_drill.html" in (
        rig["project"] / "output" / "site" / "index.html").read_text()
    for value in (str(rig["key"]), str(rig["cert"]), str(rig["vault"]),
                  str(rig["plan"]), "issuer_id", "security_id"):
        assert value not in page.read_text()
        assert value not in (files(prepared) / "report.json").read_text()
    assert audit(prepared)["check_count"] == 1


def test_repeated_rehearsal_appends_hash_history_without_source_mutation(prepared):
    first = do(prepared)
    report = files(prepared) / "first_event.json"
    initial = sha256(report.read_bytes()).hexdigest()
    second = do(prepared, clock=NOW+timedelta(minutes=7))
    assert first["check_count"] == 1 and second["check_count"] == 2
    assert second["chain_head_sha256"] != first["chain_head_sha256"]
    assert sha256(report.read_bytes()).hexdigest() == initial
    assert audit(prepared)["check_count"] == 2
    assert_erased(prepared)


def test_rehearsal_works_without_original_unencrypted_ssd_zip(prepared):
    rig, _, _ = prepared
    zip_file = rig["zip"]
    zip_file.rename(zip_file.with_suffix(".temporarily_hidden"))
    outcome = do(prepared)
    assert outcome["latest"]["outcome"] == "PASSED"
    assert_erased(prepared)


def test_wrong_key_causes_failed_rehearsal_and_cleans_tmp(prepared,tmp_path):
    new_key = tmp_path / "different.pem"
    p = subprocess.run(["openssl", "genrsa", "-out", str(new_key), "3072"],
                       capture_output=True)
    assert p.returncode == 0
    new_key.chmod(0o600)
    out = do(prepared, key=new_key)
    assert out["latest"]["outcome"] == "FAILED"
    assert out["latest"]["reason"] == "DECRYPT_OR_REPLAY_FAILED"
    assert out["latest"]["temporary_plaintext_path_removed"] is True
    assert out["latest"]["aes_gcm_authenticated"] is False
    assert_erased(prepared)
    assert audit(prepared)["check_count"] == 1


@pytest.mark.parametrize("variant", ["no_key", "unsafe_permissions", "symlink"])
def test_bad_private_key_fails_with_no_decrypted_files(prepared,tmp_path,variant):
    rig, _, _ = prepared
    if variant == "no_key":
        key = tmp_path/"absent_key.pem"
    elif variant == "unsafe_permissions":
        key = tmp_path/"world_readable_private.pem"
        key.write_bytes(rig["key"].read_bytes());key.chmod(0o644)
    else:
        key = tmp_path/"key_link.pem"
        key.symlink_to(rig["key"])
    out = do(prepared, key=key)
    assert out["latest"]["outcome"] == "FAILED"
    assert out["latest"]["reason"] == "UNSAFE_OR_MISSING_KEY"
    assert_erased(prepared)


def test_ciphertext_tamper_records_failure_not_trusted_success(prepared):
    rig, archived, _ = prepared
    ciphertext = next(rig["vault"].glob("*.cms"))
    original = ciphertext.read_bytes()
    altered = bytearray(original);altered[len(altered)//2] ^= 1
    ciphertext.write_bytes(altered)
    try:
        out = do(prepared)
        assert out["latest"]["outcome"] == "FAILED"
        assert out["latest"]["reason"] == "BACKUP_SHA_INVALID"
        assert out["latest"]["aes_gcm_authenticated"] is False
        assert_erased(prepared)
    finally:
        ciphertext.write_bytes(original)
    good = do(prepared, clock=NOW+timedelta(minutes=8))
    assert good["latest"]["outcome"] == "PASSED"
    assert audit(prepared)["check_count"] == 2


def test_replay_broken_provenance_never_marked_success(prepared,monkeypatch):
    from eraleader import native_recovery_drill as module
    original = module.restore_encrypted_native_original
    def fake_result(*args,**kwargs):
        result=original(*args,**kwargs)
        result["registered_index_chain_verified"]=False
        return result
    monkeypatch.setattr(module,"restore_encrypted_native_original",fake_result)
    out=do(prepared)
    assert out["latest"]["outcome"]=="FAILED"
    assert out["latest"]["reason"]=="DECRYPT_OR_REPLAY_FAILED"
    assert_erased(prepared)


@pytest.mark.parametrize("corrupt",[
    "genesis.json","first_event.json","history.jsonl",
    "report.json",".checks.lock",
])
def test_missing_or_modified_recovery_audit_evidence_fails_closed(prepared,corrupt):
    do(prepared)
    path=files(prepared)/corrupt
    if corrupt==".checks.lock":path.unlink()
    else:path.write_bytes(b"{}\n")
    with pytest.raises((ValueError,RuntimeError)):
        do(prepared,clock=NOW+timedelta(minutes=8))


def test_sha_history_rollback_detected_against_last_report(prepared):
    do(prepared)
    log=files(prepared)/"history.jsonl"
    first=log.read_bytes()
    do(prepared,clock=NOW+timedelta(minutes=7))
    log.write_bytes(first)
    with pytest.raises(ValueError,match="checkpoint|history|report"):
        audit(prepared)


def test_timestamp_rollback_prevents_new_drill_and_preserves_checkpoint(prepared):
    do(prepared,clock=NOW+timedelta(minutes=9))
    report=files(prepared)/"report.json"
    digest=sha256(report.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="clock"):
        do(prepared,clock=NOW+timedelta(minutes=4))
    assert digest == sha256(report.read_bytes()).hexdigest()


def test_scratch_is_private_separate_device_and_nonoverlapping(prepared,monkeypatch):
    rig,archived,scratch=prepared
    with pytest.raises(ValueError,match="overlap"):
        run_native_recovery_drill(
            rig["project"],archived["slot"],rig["vault"],rig["witness"],
            rig["cert"],rig["key"],rig["vault"],clock=NOW)
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:False)
    with pytest.raises(ValueError,match="different filesystem"):
        do(prepared)
    assert not files(prepared).exists()


def test_symlinked_scratch_directory_is_refused(prepared,tmp_path):
    rig,arc,scratch=prepared
    sym=tmp_path/"unsafe_scratch_link"
    sym.symlink_to(scratch,target_is_directory=True)
    with pytest.raises(ValueError,match="Linked|linked"):
        run_native_recovery_drill(
            rig["project"],arc["slot"],rig["vault"],rig["witness"],
            rig["cert"],rig["key"],sym)
    assert not files(prepared).exists()


def test_cli_run_reports_local_result_but_no_private_path_and_verify_needs_no_key(
        prepared,capsys):
    from scripts.run_native_recovery_drill import main
    rig, archived, scratch=prepared
    basic=[
        "--project",str(rig["project"]),
        "--vault-root",str(rig["vault"]),
        "--witness-root",str(rig["witness"]),
        "--recipient-cert",str(rig["cert"]),
        "--scratch-root",str(scratch),
    ]
    assert main(["--action","run","--slot",archived["slot"],
                 "--private-key",str(rig["key"]),*basic]) == 0
    stdout=capsys.readouterr().out
    assert json.loads(stdout)["latest"]["outcome"]=="PASSED"
    for item in (str(rig["key"]),str(rig["plan"]),str(scratch),str(rig["vault"])):
        assert item not in stdout
    assert main(["--action","verify-history",*basic]) == 0
    assert json.loads(capsys.readouterr().out)["chain_verified"] is True


def test_cli_failed_drill_returns_nonzero_with_sanitized_json(prepared,tmp_path,capsys):
    from scripts.run_native_recovery_drill import main
    rig, archived, scratch=prepared
    wrong=tmp_path/"badkey"
    assert main([
        "--action","run","--project",str(rig["project"]),
        "--slot",archived["slot"],"--vault-root",str(rig["vault"]),
        "--witness-root",str(rig["witness"]),
        "--recipient-cert",str(rig["cert"]),
        "--scratch-root",str(scratch),"--private-key",str(wrong)
    ]) == 2
    report=json.loads(capsys.readouterr().out)
    assert report["latest"]["reason"]=="UNSAFE_OR_MISSING_KEY"
    assert str(wrong) not in json.dumps(report)
