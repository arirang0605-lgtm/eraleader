"""6_5 independent SHA-only periodic ciphertext cold-custody integrity (synthetic)."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from hashlib import sha256
import json
import os

import pytest

from eraleader import native_cold_integrity as integ
from test_native_cold_custody import bundle, export
from test_native_encrypted_vault import rig
from test_scheduled_native_archive import NOW


@pytest.fixture
def enrolled(bundle,tmp_path):
    first=export(bundle)
    rig,_,package=bundle
    root=tmp_path/"pin_archive"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    init=integ.enroll_cold_integrity(
        rig["project"],root,"kr-first",package,first["package_sha256"],
        allow_colocated_research=True,clock=NOW)
    return rig,package,root,first,init


def scan(case, *, at=NOW, **kw):
    rig,archive,root,first,init=case
    return integ.scan_cold_integrity(
        rig["project"],root,clock=at,allow_colocated_research=True,**kw)


def test_first_external_sha_enrollment_immutable_and_full_cold_verification(enrolled):
    rig,archive,root,first,init=enrolled
    assert init["new_first_pins"]==1
    assert init["independent_filesystem"] is False
    assert init["offsite_geography_attested"] is False
    before=sha256(archive.read_bytes()).hexdigest()
    response=scan(enrolled)
    assert response["verified_count"]==0
    assert response["warning_count"]==0
    assert list(response["packages"].values())==["RESEARCH_ONLY_VERIFIED"]
    assert response["new_alerts"]==[init["pin_id"]+":FIRST_VERIFIED"]
    assert response["messages_sent"]==response["external_api_calls"]==0
    assert response["private_key_accessed"] is False
    assert sha256(archive.read_bytes()).hexdigest()==before
    assert (rig["project"]/"output"/"native_cold_integrity"/"site"/"index.html").is_file()
    report=(rig["project"]/"output"/"native_cold_integrity"/"report.json").read_text()
    assert str(archive) not in report and str(rig["key"]) not in report
    assert list(root.joinpath("pins").glob("*_first.json"))
    second=scan(enrolled)
    assert second["new_alerts"]==[]
    assert second["check_count"]==3
    assert integ.verify_cold_integrity_history(
        rig["project"],root,allow_colocated_research=True)["pin_count"]==1


def test_wrong_trusted_digest_rejected_before_first_pin(bundle,tmp_path):
    first=export(bundle)
    rig,_,archive=bundle
    root=tmp_path/"fresh_pin"; root.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="SHA PIN"):
        integ.enroll_cold_integrity(
            rig["project"],root,"kr-first",archive,"e"*64,
            allow_colocated_research=True)
    assert not (root/"genesis.json").exists()


def test_strict_mode_cannot_claim_same_filesystem_operational(enrolled):
    rig,archive,root,first,init=enrolled
    with pytest.raises(ValueError,match="different from original SSD"):
        integ.scan_cold_integrity(rig["project"],root)
    with pytest.raises(ValueError,match="different from original SSD"):
        integ.enroll_cold_integrity(rig["project"],root,
           "kr-second",archive,first["package_sha256"])
    assert not (root/"pins"/(integ._identifier("kr-second")+"_first.json")).exists()


def test_idempotent_same_pin_no_rewrite_or_second_slot(enrolled):
    rig,archive,root,first,init=enrolled
    pin=root/"pins"/(init["pin_id"]+"_first.json")
    before=pin.read_bytes()
    response=integ.enroll_cold_integrity(
       rig["project"],root,"kr-first",archive,first["package_sha256"],
       allow_colocated_research=True,clock=NOW)
    assert response["new_first_pins"]==0
    assert pin.read_bytes()==before
    with pytest.raises(ValueError,match="already enrolled"):
        integ.enroll_cold_integrity(
            rig["project"],root,"us-copy",archive,first["package_sha256"],
            allow_colocated_research=True,clock=NOW)


@pytest.mark.parametrize("failure",["tamper","remove","linked"])
def test_package_damage_missing_or_symlink_is_recorded_without_repin(enrolled,failure,tmp_path):
    rig,archive,root,first,init=enrolled
    scan(enrolled)
    old=archive.read_bytes()
    if failure=="tamper":
        archive.write_bytes(old+b"corruption")
        expected="PACKAGE_INVALID"
    elif failure=="remove":
        archive.unlink()
        expected="PACKAGE_MISSING"
    else:
        moved=tmp_path/"renamed_untrusted_original.zip"
        archive.rename(moved)
        archive.symlink_to(moved)
        expected="PACKAGE_PATH_UNSAFE"
    incident=scan(enrolled)
    assert list(incident["packages"].values())==[expected]
    assert incident["warning_count"]==1
    assert incident["new_alerts"]==[init["pin_id"]+":"+expected]
    assert scan(enrolled)["new_alerts"]==[]
    if archive.is_symlink():
        archive.unlink()
    archive.write_bytes(old)
    recovered=scan(enrolled)
    assert recovered["new_alerts"]==[init["pin_id"]+":RESTORED"]
    assert recovered["warning_count"]==0
    assert first["package_sha256"]==sha256(archive.read_bytes()).hexdigest()


@pytest.mark.parametrize("failure",["first_lost","guard_lost","first_tamper","chmod_unsafe"])
def test_independent_first_sha_loss_or_change_is_fail_closed(enrolled,failure):
    rig,archive,root,first,init=enrolled
    scan(enrolled)
    pin=root/"pins"/(init["pin_id"]+"_first.json")
    guard=root/"pins"/(init["pin_id"]+"_guard.json")
    if failure=="first_lost":
        pin.unlink(); expected="PIN_MISSING"
    elif failure=="guard_lost":
        guard.unlink(); expected="PIN_MISSING"
    elif failure=="first_tamper":
        pin.write_bytes(pin.read_bytes().replace(b"kr-first",b"us-first")); expected="PIN_CORRUPTED"
    else:
        pin.chmod(0o644); expected="PIN_CORRUPTED"
    result=scan(enrolled)
    assert result["warning_count"]==1
    assert list(result["packages"].values())==[expected]
    assert result["new_alerts"]==[init["pin_id"]+":"+expected]
    with pytest.raises(ValueError,match="first|PIN|incomplete"):
        integ.verify_cold_integrity_history(rig["project"],root,
                                             allow_colocated_research=True)
    assert not pin.exists() or pin.read_bytes()


@pytest.mark.parametrize("target",["history.jsonl","checkpoint.json","genesis.json"])
def test_independent_history_chain_or_checkpoint_rollback_cannot_self_heal(enrolled,target):
    rig,archive,root,first,init=enrolled
    scan(enrolled)
    file=root/target
    original=file.read_bytes()
    if target=="history.jsonl":
        file.write_bytes(original.splitlines(keepends=True)[0])
    else:
        file.write_bytes(original+b"tamper")
    with pytest.raises((ValueError,KeyError)):
        scan(enrolled)
    assert file.read_bytes()!=original


def test_cadence_miss_warning_then_recovery(enrolled):
    scan(enrolled)
    late=scan(enrolled,at=NOW+timedelta(hours=49))
    assert list(late["packages"].values())==["MISSED_SCAN_WINDOW"]
    assert late["warning_count"]==1
    assert scan(enrolled,at=NOW+timedelta(hours=49,minutes=1))["new_alerts"]==[
        enrolled[4]["pin_id"]+":RESTORED"]


def test_monotonic_clock_and_locked_interval_policy(enrolled):
    scan(enrolled,at=NOW)
    rig,archive,root,first,init=enrolled
    with pytest.raises(ValueError,match="rollback"):
        scan(enrolled,at=NOW-timedelta(seconds=1))
    with pytest.raises(ValueError,match="policy|mismatch"):
        integ.scan_cold_integrity(rig["project"],root,max_gap_hours=10,
                                  allow_colocated_research=True)
    with pytest.raises(ValueError,match="48|720"):
        integ.scan_cold_integrity(rig["project"],root,max_gap_hours=0,
                                  allow_colocated_research=True)


def test_unregistered_pin_sideload_fails_closed(enrolled):
    rig,archive,root,first,init=enrolled
    (root/"pins"/"untrusted_first.json").write_text("{}")
    with pytest.raises(ValueError,match="Unregistered"):
        scan(enrolled)


def test_enrollment_requires_name_path_and_original_independent_sha(enrolled):
    rig,archive,root,first,init=enrolled
    for name in ("", "a/../../attack", "KR model", "a"*80):
        with pytest.raises(ValueError):
            integ.enroll_cold_integrity(
                rig["project"],root,name,archive,first["package_sha256"],
                allow_colocated_research=True)
    with pytest.raises(ValueError, match="[Oo]riginal"):
        integ.enroll_cold_integrity(
            rig["project"],root,"us-new",archive,None,
            allow_colocated_research=True)
