"""6_5 opt-in first-ZIP SHA witness on a different local filesystem.

This proves local cross-volume continuity only, not independent publication time
or market PIT. Synthetic source data is never written to the witness volume.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader.native_sha_witness import (
    record_native_sha_witness, verify_native_sha_witness,
    validate_witness_destination,
)
from eraleader.native_first_capture import capture_first_native_topk
from eraleader.scheduled_native_archive import archive_captured_native_plan
from test_scheduled_native_archive import setup, NOW


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    project,bundle,plan,root=setup(tmp_path)
    captured=capture_first_native_topk(plan,root,clock=NOW)
    sealed=archive_captured_native_plan(project,plan,root,captured,clock=NOW)
    witness=tmp_path/"internal_volume"/"witnesses"
    import eraleader.native_sha_witness as module
    monkeypatch.setattr(module,"_separate_device",lambda a,b:True)
    return project,bundle,plan,root,sealed,witness


def seal(prepared,at=NOW):
    project,_,plan,root,receipt,witness=prepared
    return record_native_sha_witness(
        project,plan,root,receipt,witness,clock=at)


def verify(prepared,at=NOW):
    project,_,plan,root,_,witness=prepared
    return verify_native_sha_witness(
        project,plan,root,witness,clock=at)


def paths(prepared):
    _,_,_,_,_,witness=prepared
    return (next(witness.glob("native_*_first.json")),
            next(witness.glob("native_*_guard.json")),
            next(witness.glob(".native_*.lock")))


@pytest.mark.parametrize("market",["KR","US"])
def test_first_witness_contains_only_hashes_and_repeats_without_reanchoring(tmp_path,monkeypatch,market):
    project,b,plan,root=setup(tmp_path,market=market)
    captured=capture_first_native_topk(plan,root,clock=NOW)
    receipt=archive_captured_native_plan(project,plan,root,captured,clock=NOW)
    witness=tmp_path/"internal_volume"/"witnesses"
    import eraleader.native_sha_witness as module
    monkeypatch.setattr(module,"_separate_device",lambda a,b:True)
    first=record_native_sha_witness(project,plan,root,receipt,witness,clock=NOW)
    assert first["status"]=="FIRST_SEPARATE_VOLUME_NATIVE_SHA_WITNESSED_NOT_ATTESTED"
    assert first["market"]==market and first["separate_device_checked"] is True
    assert first["messages_sent"]==first["external_api_calls"]==0
    assert first["independent_timestamp_attested"] is False
    assert first["official_leader_promotions"]==0
    assert first["archive_sha256"]==receipt["archive_original_sha256"]
    files=list(witness.glob("native_*.json"))
    assert len(files)==2
    assert len(list(witness.glob(".native_*.lock")))==1
    raw=b"".join(f.read_bytes() for f in files)
    for sensitive in (str(plan).encode(),str(root).encode(),b"positive_watch",
                      b"security_id",b"issuer_id",b"model_version"):
        assert sensitive not in raw
    assert all(not f.is_symlink() for f in files)
    before={p:p.read_bytes() for p in witness.iterdir()}
    repeated=record_native_sha_witness(project,plan,root,receipt,witness,
                                        clock=NOW+timedelta(minutes=4))
    assert repeated["status"]=="EXISTING_SEPARATE_VOLUME_NATIVE_SHA_REVERIFIED_NOT_ATTESTED"
    assert repeated["archive_sha256"]==first["archive_sha256"]
    assert before=={p:p.read_bytes() for p in witness.iterdir()}
    assert verify_native_sha_witness(project,plan,root,witness,
                                     clock=NOW+timedelta(minutes=4))["source_archive_verified"] is True


@pytest.mark.parametrize("item",["zip","ssd_first","ssd_guard","internal_first","internal_guard","internal_lock"])
def test_sha_mismatch_partial_deletion_or_rewritten_ssd_receipt_fails_closed(prepared,item):
    seal(prepared)
    project,bundle,plan,root,receipt,witness=prepared
    internal_first,internal_guard,lock=paths(prepared)
    if item=="zip":
        next((project/"output"/"native_first_private_archives").glob("*.zip")).write_bytes(b"fake")
    elif item=="ssd_first":
        next((project/"output"/"native_first_archive_receipts").glob("*_receipt.json")).unlink()
    elif item=="ssd_guard":
        next((project/"output"/"native_first_archive_receipts").glob("*_guard.json")).unlink()
    elif item=="internal_first":
        internal_first.unlink()
    elif item=="internal_guard":
        internal_guard.unlink()
    else:
        lock.unlink()
    with pytest.raises((ValueError,RuntimeError),match="witness|receipt|archive|lock|missing|partial|source"):
        verify(prepared,at=NOW+timedelta(minutes=3))
    with pytest.raises((ValueError,RuntimeError)):
        seal(prepared,at=NOW+timedelta(minutes=4))


def test_entire_ssd_archive_and_local_sha_resealed_self_consistently_cannot_reanchor(prepared):
    seal(prepared)
    project,_,plan,root,receipt,witness=prepared
    local=project/"output"/"native_first_archive_receipts"
    first=next(local.glob("*_receipt.json"))
    obj=json.loads(first.read_bytes())
    obj["archive_sha256"]="f"*64
    first.write_text(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    with pytest.raises(ValueError,match="receipt|SHA|source|witness"):
        verify(prepared)
    original_witness=paths(prepared)[0].read_bytes()
    assert b"f"*64 not in original_witness


def test_same_device_rejected_without_creating_any_internal_receipt(tmp_path):
    project,b,plan,root=setup(tmp_path)
    dest=tmp_path/"same_disk_witness"
    with pytest.raises(ValueError,match="different|separate|filesystem"):
        validate_witness_destination(project,dest)
    assert not dest.exists()


def test_existing_source_different_root_cannot_be_reused_after_first_seal(prepared):
    seal(prepared)
    project,_,plan,root,receipt,witness=prepared
    other=project/"output"/"fake_capture_root"
    other.mkdir()
    with pytest.raises(ValueError,match="capture|source|original|receipt"):
        verify_native_sha_witness(project,plan,other,witness)


def test_missing_both_first_files_but_lock_survives_cannot_restart(prepared):
    seal(prepared)
    first,guard,lock=paths(prepared)
    first.unlink()
    guard.unlink()
    with pytest.raises(ValueError,match="witness|missing|lock|partial"):
        seal(prepared)


def test_corrupted_witness_bytes_and_symlinks_are_never_trusted(prepared,tmp_path):
    seal(prepared)
    first,guard,lock=paths(prepared)
    first.write_bytes(first.read_bytes()+b" ")
    with pytest.raises(ValueError,match="witness|canonical|revised"):
        verify(prepared)
    first.write_bytes(first.read_bytes()[:-1])
    guard.unlink()
    guard.symlink_to(first)
    with pytest.raises(ValueError,match="linked|witness|unsafe"):
        verify(prepared)


def test_wait_does_not_create_external_disk_artifacts(prepared):
    project,b,plan,root,receipt,witness=prepared
    waiting={"status":"WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN"}
    with pytest.raises(ValueError,match="completed|archive"):
        record_native_sha_witness(project,plan,root,waiting,witness)
    assert not witness.exists()


def test_self_consistent_resealed_ssd_metadata_conflicts_with_external_first_sha(
        prepared,monkeypatch):
    seal(prepared)
    import eraleader.native_sha_witness as module
    original=module._read_local_source
    def forged_local(*args,**kwargs):
        revised=dict(original(*args,**kwargs))
        revised["archive_sha256"]="e"*64
        revised["local_receipt_sha256"]="d"*64
        return revised
    # Simulates an SSD-side mutually consistent archive/receipt rewrite.
    # The source verifier itself would already fail ordinary forgery, but a
    # separate-device first PIN is an additional independent-path protection.
    monkeypatch.setattr(module,"_read_local_source",forged_local)
    with pytest.raises(ValueError,match="witness|original|contradicts"):
        verify(prepared,at=NOW+timedelta(minutes=3))


def test_different_device_is_not_a_symlink_bypass(tmp_path,monkeypatch):
    import eraleader.native_sha_witness as module
    project=tmp_path/"project";project.mkdir()
    disk=tmp_path/"other_disk";disk.mkdir()
    link=tmp_path/"symlinked"
    link.symlink_to(disk,target_is_directory=True)
    monkeypatch.setattr(module,"_separate_device",lambda a,b:True)
    with pytest.raises(ValueError,match="Linked|link"):
        validate_witness_destination(project,link/"first")
    assert not (disk/"first").exists()


def test_existing_world_readable_witness_directory_is_rejected(tmp_path,monkeypatch):
    import eraleader.native_sha_witness as module
    project=tmp_path/"project";project.mkdir()
    destination=tmp_path/"unprotected";destination.mkdir(mode=0o755)
    destination.chmod(0o755)
    monkeypatch.setattr(module,"_separate_device",lambda a,b:True)
    with pytest.raises(ValueError,match="group/others"):
        validate_witness_destination(project,destination)
