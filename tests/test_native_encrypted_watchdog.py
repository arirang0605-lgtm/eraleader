"""6_5 original encrypted vault first-SHA warning monitor (synthetic only)."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import shutil
import subprocess

import pytest

from eraleader import native_sha_witness
from eraleader.native_encrypted_vault import backup_encrypted_native_original
from eraleader.native_encrypted_watchdog import (
    run_native_encrypted_watchdog, verify_native_encrypted_watchdog,
    validate_monitor_inputs, ZERO,
)
from eraleader.native_evidence_archive import _slot
from eraleader.native_first_capture import capture_first_native_topk, read_capture_plan
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from test_scheduled_native_archive import setup, NOW
from test_native_first_capture import prepare


@pytest.fixture
def rig(tmp_path, monkeypatch):
    project, _, kr, capture = setup(tmp_path, market="KR")
    _, _, us, _ = prepare(tmp_path / "us_fixture", market="US")
    witness = tmp_path / "separate_mac" / "sha_only"
    vault = tmp_path / "separate_mac" / "encrypted_original"
    monkeypatch.setattr(native_sha_witness, "_separate_device", lambda a,b: True)
    key_dir=tmp_path/"key_material"
    key_dir.mkdir(mode=0o700)
    cert=key_dir/"public.crt"
    key=key_dir/"private.key"
    p=subprocess.run(["openssl","req","-x509","-newkey","rsa:3072","-nodes",
                      "-days","1","-subj","/CN=EncryptedMonitorSynthetic",
                      "-keyout",str(key),"-out",str(cert)],capture_output=True)
    assert p.returncode==0,p.stderr.decode(errors="replace")[-300:]
    key.chmod(0o600)
    return {"project":project,"capture":capture,"plans":[kr,us],
            "slots":[_slot(read_capture_plan(p)[0]) for p in [kr,us]],
            "vault":vault,"witness":witness,"cert":cert,"key":key}


def create(rig, market_no):
    plan=rig["plans"][market_no]
    original=capture_first_native_topk(plan,rig["capture"],clock=NOW)
    assert original["messages_sent"]==0
    zipped=archive_captured_native_plan(rig["project"],plan,rig["capture"],original,clock=NOW)
    assert zipped["separate_local_first_sha_receipt_verified"] is True
    witnessed=record_native_sha_witness(
        rig["project"],plan,rig["capture"],zipped,rig["witness"],clock=NOW)
    assert witnessed["source_archive_verified"]
    backed=backup_encrypted_native_original(
        rig["project"],plan,rig["capture"],rig["witness"],rig["vault"],
        rig["cert"],clock=NOW)
    assert backed["ciphertext_verified"] is True


def scan(rig, minutes=0, slots=None):
    return run_native_encrypted_watchdog(
        rig["project"],rig["slots"] if slots is None else slots,
        rig["vault"],rig["witness"],rig["cert"],
        clock=NOW+timedelta(minutes=minutes))


def rows(result, market):
    return next(v for v in result["cohorts"].values() if v["market"]==market)


def folder(rig):
    return rig["project"]/"output"/"native_encrypted_alerts"


def test_two_markets_initial_pin_repeat_and_dashboard_no_source_leak(rig):
    create(rig,0);create(rig,1)
    (rig["project"]/"output"/"site").mkdir()
    (rig["project"]/"output"/"site"/"index.html").write_text(
        "<html><body>EraLeader original research</body></html>")
    first=scan(rig)
    assert first["check_count"]==1 and len(first["cohorts"])==2
    assert not first["new_alerts"]
    assert all(r["state"]=="VERIFIED" and r["encrypted_sha256"]!=ZERO
               for r in first["cohorts"].values())
    assert first["authenticated_plaintext_verified"] is False
    assert first["real_future_leader_accuracy_certified"] is False
    assert first["messages_sent"]==first["external_api_calls"]==0
    assert not scan(rig,minutes=2)["new_alerts"]
    status=verify_native_encrypted_watchdog(
        rig["project"],rig["vault"],rig["witness"],rig["cert"])
    assert status["first_verified_pins"]==2
    page=(rig["project"]/"output"/"site"/"native_encrypted_dry_run.html").read_text()
    index=(rig["project"]/"output"/"site"/"index.html").read_text()
    assert "DRY-RUN" in page and "KR" in page and "US" in page
    assert index.count("native_encrypted_dry_run.html")==1
    assert "native_encrypted_dry_run.html" in index
    for secret in (str(rig["key"]),str(rig["vault"]),str(rig["cert"]),
                   str(rig["plans"][0]),str(rig["plans"][1]),
                   "security_id","issuer_id","original/watch.sqlite"):
        assert secret not in page
        assert secret not in (folder(rig)/"report.json").read_text()
    assert not scan(rig,minutes=3)["new_alerts"]
    assert (rig["project"]/"output"/"site"/"index.html").read_text().count(
        "native_encrypted_dry_run.html")==1


def test_initial_plan_before_original_first_write_waits_without_alarm(rig):
    rig["vault"].mkdir(parents=True,mode=0o700)
    rig["witness"].mkdir(parents=True,mode=0o700)
    first=scan(rig)
    assert len(first["cohorts"])==2
    assert not first["new_alerts"]
    assert all(r["state"]=="WAITING" for r in first["cohorts"].values())
    create(rig,0)
    second=scan(rig,minutes=1)
    assert rows(second,"KR")["state"]=="VERIFIED"
    assert rows(second,"US")["state"]=="WAITING"
    assert not second["new_alerts"]


def test_first_witness_without_ciphertext_reports_unprotected_source(rig):
    original=capture_first_native_topk(rig["plans"][0],rig["capture"],clock=NOW)
    zipped=archive_captured_native_plan(
        rig["project"],rig["plans"][0],rig["capture"],original,clock=NOW)
    record_native_sha_witness(rig["project"],rig["plans"][0],rig["capture"],
                              zipped,rig["witness"],clock=NOW)
    rig["vault"].mkdir(parents=True,mode=0o700)
    first=scan(rig,slots=rig["slots"][:1])
    assert rows(first,"KR")["state"]=="ANOMALY"
    assert rows(first,"KR")["issue"]=="ENCRYPTED_BACKUP_MISSING"
    assert len(first["new_alerts"])==1
    assert not scan(rig,minutes=1,slots=rig["slots"][:1])["new_alerts"]


@pytest.mark.parametrize("kind",[
    "cipher","backup_first","backup_guard","backup_lock",
    "witness_first","witness_guard","witness_lock","certificate",
])
def test_vault_integrity_anomaly_dedup_and_bytes_restore(rig,kind):
    create(rig,0)
    scan(rig,slots=rig["slots"][:1])
    slot=rig["slots"][0]
    lookup={
        "cipher":rig["vault"]/("native_"+slot+".cms"),
        "backup_first":rig["vault"]/("native_"+slot+"_first.json"),
        "backup_guard":rig["vault"]/("native_"+slot+"_guard.json"),
        "backup_lock":rig["vault"]/(".native_"+slot+".lock"),
        "witness_first":rig["witness"]/("native_"+slot+"_first.json"),
        "witness_guard":rig["witness"]/("native_"+slot+"_guard.json"),
        "witness_lock":rig["witness"]/(".native_"+slot+".lock"),
        "certificate":rig["cert"],
    }
    target=lookup[kind]
    original=target.read_bytes()
    if kind in {"cipher","backup_guard","witness_first","certificate"}:
        target.write_bytes(original+b"tamper")
    else:
        target.unlink()
    incident=scan(rig,minutes=1,slots=rig["slots"][:1])
    assert rows(incident,"KR")["state"]=="ANOMALY"
    assert len(incident["new_alerts"])==1
    unchanged=scan(rig,minutes=2,slots=rig["slots"][:1])
    assert not unchanged["new_alerts"]
    target.write_bytes(original)
    restored=scan(rig,minutes=3,slots=rig["slots"][:1])
    assert rows(restored,"KR")["state"]=="VERIFIED"
    assert len(restored["new_alerts"])==1 and restored["new_alerts"][0].endswith(":RESTORED")
    assert restored["messages_sent"]==restored["external_api_calls"]==0


@pytest.mark.parametrize("missing",["vault","witness"])
def test_entire_external_root_disappearance_is_alert_not_implicit_reinstall(rig,missing):
    create(rig,0)
    scan(rig,slots=rig["slots"][:1])
    source=rig[missing]
    hidden=source.parent/("temporarily_unavailable_"+missing)
    source.rename(hidden)
    try:
        result=scan(rig,minutes=1,slots=rig["slots"][:1])
        assert rows(result,"KR")["state"]=="ANOMALY"
        assert rows(result,"KR")["issue"]==(
            "VAULT_ROOT_UNAVAILABLE" if missing=="vault"
            else "WITNESS_ROOT_UNAVAILABLE")
        assert not source.exists()
    finally:
        hidden.rename(source)
    assert rows(scan(rig,minutes=2,slots=rig["slots"][:1]),"KR")["state"]=="VERIFIED"


def test_missing_selected_slot_is_a_warning_not_dropped_from_denominator(rig):
    create(rig,0);create(rig,1)
    before=scan(rig)
    later=scan(rig,minutes=1,slots=rig["slots"][:1])
    assert len(later["cohorts"])==len(before["cohorts"])==2
    assert rows(later,"US")["issue"]=="MISSING_SCAN_INPUT"
    assert len(later["new_alerts"])==1
    assert not scan(rig,minutes=2,slots=rig["slots"][:1])["new_alerts"]
    resumed=scan(rig,minutes=3)
    assert rows(resumed,"US")["state"]=="VERIFIED"
    assert resumed["new_alerts"][0].endswith(":RESTORED")


def test_immutable_first_verified_pin_catches_consistent_rewrite(rig,monkeypatch):
    create(rig,0)
    before=scan(rig,slots=rig["slots"][:1])
    from eraleader import native_encrypted_watchdog as module
    actual=module._verified
    def forged(*args,**kwargs):
        payload=dict(actual(*args,**kwargs))
        payload["encrypted_sha256"]="f"*64
        return payload
    monkeypatch.setattr(module,"_verified",forged)
    incident=scan(rig,minutes=1,slots=rig["slots"][:1])
    assert rows(incident,"KR")["issue"]=="FIRST_ENCRYPTED_SHA_PIN_CHANGED"
    assert len(incident["new_alerts"])==1
    assert rows(before,"KR")["encrypted_sha256"]!="f"*64


@pytest.mark.parametrize("artifact",[
    "genesis.json","first_event.json","history.jsonl","report.json",".checks.lock"
])
def test_first_monitor_receipt_history_or_lock_corruption_fails_closed(rig,artifact):
    create(rig,0)
    scan(rig,slots=rig["slots"][:1])
    target=folder(rig)/artifact
    if artifact==".checks.lock":
        target.unlink()
    else:
        target.write_bytes(b"{}\n")
    with pytest.raises((ValueError,RuntimeError)):
        scan(rig,minutes=1,slots=rig["slots"][:1])


def test_report_checkpoint_detects_whole_event_tail_rollback(rig):
    create(rig,0)
    scan(rig,slots=rig["slots"][:1])
    log=folder(rig)/"history.jsonl"
    first=log.read_bytes()
    scan(rig,minutes=1,slots=rig["slots"][:1])
    log.write_bytes(first)
    with pytest.raises(ValueError,match="report|rollback|history"):
        scan(rig,minutes=2,slots=rig["slots"][:1])


def test_clock_backward_refused_and_checkpoint_unmodified(rig):
    create(rig,0)
    scan(rig,minutes=5,slots=rig["slots"][:1])
    report=folder(rig)/"report.json"
    before=sha256(report.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="clock"):
        scan(rig,minutes=2,slots=rig["slots"][:1])
    assert sha256(report.read_bytes()).hexdigest()==before


def test_new_slot_adds_without_rewriting_existing_verified_shas(rig):
    create(rig,0)
    first=scan(rig,slots=rig["slots"][:1])
    original=rows(first,"KR")["encrypted_sha256"]
    create(rig,1)
    appended=scan(rig,minutes=1)
    assert len(appended["cohorts"])==2 and len(appended["new_alerts"])==0
    assert rows(appended,"KR")["encrypted_sha256"]==original
    assert verify_native_encrypted_watchdog(
        rig["project"],rig["vault"],rig["witness"],rig["cert"])[
            "first_verified_pins"]==2


def test_duplicate_or_invalid_slot_rejected_before_monitor_files(rig):
    with pytest.raises(ValueError,match="Duplicate"):
        scan(rig,slots=[rig["slots"][0],rig["slots"][0]])
    with pytest.raises(ValueError,match="slots"):
        scan(rig,slots=["KR_plain_symbol"])
    assert not folder(rig).exists()


def test_same_ssd_or_overlapping_roots_rejected_before_first_check(rig,monkeypatch):
    with pytest.raises(ValueError,match="overlap"):
        validate_monitor_inputs(rig["project"],rig["slots"],
                                rig["witness"],rig["witness"],rig["cert"])
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:False)
    rig["witness"].mkdir(parents=True,mode=0o700)
    with pytest.raises(ValueError,match="different filesystem"):
        scan(rig)
    assert not folder(rig).exists()


def test_no_crypto_private_key_needed_to_audit_cipher_hashes(rig):
    create(rig,0)
    rig["key"].unlink()
    result=scan(rig,slots=rig["slots"][:1])
    assert rows(result,"KR")["state"]=="VERIFIED"
    assert result["authenticated_plaintext_verified"] is False
    assert result["independent_market_pit_certified"] is False


def test_dry_run_does_not_modify_ciphertext_first_receipts_or_original_watch(rig):
    create(rig,0)
    files=[p for p in list(rig["vault"].glob("*")) + list(rig["witness"].glob("*"))
           if p.is_file()]
    files+=list((rig["project"]/"output"/"native_first_private_archives").glob("*.zip"))
    files+=list((rig["project"]/"output"/"native_first_archive_receipts").glob("*json"))
    before={p:sha256(p.read_bytes()).hexdigest() for p in files}
    scan(rig,slots=rig["slots"][:1])
    scan(rig,minutes=1,slots=rig["slots"][:1])
    assert before=={p:sha256(p.read_bytes()).hexdigest() for p in files}
