"""5_5 private, source-complete first-native evidence archive / restore tests.

All sources synthetic. No external provider, future labels or live delivery.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import shutil
import subprocess
import sys

import pytest

from eraleader.native_evidence_archive import (
    create_native_evidence_archive,
    verify_native_evidence_archive,
    restore_native_evidence_archive,
)
from test_native_first_capture import prepare, capture, artifacts, NOW

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"archive_native_first_evidence.py"


def ready(tmp_path, market="KR"):
    bundle,rule,plan,captures=prepare(tmp_path,market=market)
    result=capture(plan,captures)
    assert result["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"
    archive=tmp_path/"output"/"private_evidence.zip"
    archive.parent.mkdir()
    return bundle,rule,plan,captures,archive


def create(bundle,rule,plan,captures,archive):
    originals={
        str(p):sha256(p.read_bytes()).hexdigest()
        for p in [bundle[1],bundle[4],rule,plan,*sorted(bundle[2].glob("*.json"))]
    }
    report=create_native_evidence_archive(plan,captures,archive,project=archive.parent.parent,clock=NOW)
    assert originals=={p:sha256(Path(p).read_bytes()).hexdigest() for p in originals}
    assert report["status"]=="PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_PIT_CERTIFIED"
    assert report["messages_sent"]==report["external_api_calls"]==0
    assert report["official_leader_promotions"]==0
    assert report["real_future_leader_accuracy_certified"] is False
    assert report["source_bytes_unchanged"] is True
    return report


@pytest.mark.parametrize("market",["KR","US"])
def test_live_original_proofs_archived_verified_and_restored_without_backdating(tmp_path,market):
    b,rule,plan,captures,archive=ready(tmp_path,market)
    saved=create(b,rule,plan,captures,archive)
    verified=verify_native_evidence_archive(archive,expected_sha256=saved["archive_sha256"])
    assert verified["status"]=="PRIVATE_NATIVE_EVIDENCE_ARCHIVE_VERIFIED"
    assert verified["file_count"]>=13
    assert verified["market"]==market
    assert verified["archive_sha256"]==saved["archive_sha256"]
    restored=tmp_path/"output"/"inspection_copy"
    done=restore_native_evidence_archive(archive,restored,expected_sha256=saved["archive_sha256"])
    assert done["status"]=="PRIVATE_NATIVE_EVIDENCE_RESTORED_AND_REPLAYED_NOT_PIT_CERTIFIED"
    assert done["offline_original_score_provenance_verified"] is True
    assert done["registered_index_chain_verified"] is True
    assert done["official_leader_promotions"]==0
    assert (restored/"original"/"watch.sqlite").is_file()
    assert (restored/"original"/"score.sqlite").is_file()
    assert (restored/"features"/"A.json").is_file()
    assert (restored/"capture"/"registered"/"census_FIRST_WATCH.json").is_file()
    assert not list(restored.rglob("future_outcomes.json"))
    assert not list(restored.rglob("future_source_receipts.json"))
    for path in restored.rglob("*"):
        assert not path.is_symlink()
    assert not (archive.parent/"inspection_copy2").exists()


def test_original_post_capture_feature_byte_tamper_refuses_backup(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    (b[2]/"A.json").write_bytes((b[2]/"A.json").read_bytes()+b" ")
    with pytest.raises((ValueError,RuntimeError),match="source|feature|formula|first|evidence|proof"):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    assert not archive.exists()


@pytest.mark.parametrize("item",["watch","score","label","receipt"])
def test_missing_or_revised_first_written_original_refuses_credential_archive(tmp_path,item):
    b,rule,plan,captures,archive=ready(tmp_path)
    path={
        "watch":b[1],"score":b[4],"label":rule,
        "receipt":artifacts(captures)[3],
    }[item]
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises((ValueError,RuntimeError)):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    assert not archive.exists()


def test_future_outcome_files_are_never_copied_into_original_first_write_vault(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    evidence=artifacts(captures)[1]
    (evidence/"future_outcomes.json").write_text('{"later":true}')
    # Future label files must NEVER be smuggled in as first prediction.
    saved=create(b,rule,plan,captures,archive)
    with ZipFile(archive) as reader:
        names=set(reader.namelist())
    assert not any("future_outcomes" in x for x in names)
    assert not any("future_source_receipts" in x for x in names)
    assert saved["source_bytes_unchanged"] is True


def test_verifier_rejects_byte_corruption_and_wrong_expected_archive_sha(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    saved=create(b,rule,plan,captures,archive)
    with pytest.raises(ValueError,match="SHA"):
        verify_native_evidence_archive(archive,expected_sha256="0"*64)
    archive.write_bytes(archive.read_bytes()+b"changed")
    with pytest.raises(ValueError,match="SHA"):
        verify_native_evidence_archive(archive,expected_sha256=saved["archive_sha256"])


def test_restore_refuses_overwrite_original_or_existing_directory(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    saved=create(b,rule,plan,captures,archive)
    with pytest.raises((FileExistsError,ValueError)):
        restore_native_evidence_archive(archive,b[2])
    target=tmp_path/"output"/"restored"
    restore_native_evidence_archive(archive,target,expected_sha256=saved["archive_sha256"])
    before=sha256((target/"original"/"score.sqlite").read_bytes()).hexdigest()
    with pytest.raises((FileExistsError,ValueError)):
        restore_native_evidence_archive(archive,target,expected_sha256=saved["archive_sha256"])
    assert sha256((target/"original"/"score.sqlite").read_bytes()).hexdigest()==before


def test_source_symlink_or_hidden_feature_document_blocks_creation(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    original=b[2]/"A.json"
    external=tmp_path/"outside.json"
    external.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(external)
    with pytest.raises(ValueError,match="feature|FEATURE|linked|unsafe"):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    assert not archive.exists()


def test_private_destination_must_not_be_public_git_tracked_project_root(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    dangerous=tmp_path/"native_private_raw.zip"
    with pytest.raises(ValueError,match="private|output"):
        create_native_evidence_archive(plan,captures,dangerous,project=tmp_path,clock=NOW)
    assert not dangerous.exists()


def test_archive_creation_never_overwrites_first_private_backup(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    first=create(b,rule,plan,captures,archive)
    before=sha256(archive.read_bytes()).hexdigest()
    with pytest.raises((ValueError,FileExistsError),match="previous|published|existing|Unsafe"):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    assert sha256(archive.read_bytes()).hexdigest()==before==first["archive_sha256"]


def test_restored_copy_replays_even_when_original_features_later_changed(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    saved=create(b,rule,plan,captures,archive)
    (b[2]/"A.json").write_bytes((b[2]/"A.json").read_bytes()+b"\nREVISED")
    recovered=tmp_path/"output"/"sealed_inspection"
    result=restore_native_evidence_archive(
        archive,recovered,expected_sha256=saved["archive_sha256"],project=tmp_path)
    assert result["offline_original_score_provenance_verified"] is True
    assert sha256((recovered/"features"/"A.json").read_bytes()).hexdigest()!=sha256(
        (b[2]/"A.json").read_bytes()).hexdigest()


def test_restore_requires_external_original_archive_sha_pin(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    create(b,rule,plan,captures,archive)
    with pytest.raises(ValueError,match="separately pinned"):
        restore_native_evidence_archive(archive,tmp_path/"output"/"not_restored",project=tmp_path)
    assert not (tmp_path/"output"/"not_restored").exists()


def test_zip_member_substitution_and_zip_slip_rejected_before_creating_target(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    create(b,rule,plan,captures,archive)
    rogue=tmp_path/"output"/"rogue.zip"
    with ZipFile(archive,"r") as original, ZipFile(rogue,"w",ZIP_DEFLATED) as writer:
        for name in original.namelist():
            writer.writestr(name,original.read(name))
        writer.writestr("../outside_private.txt",b"untrusted")
    target=tmp_path/"output"/"should_not_exist"
    with pytest.raises(ValueError,match="omits|required|unsafe|manifest|member"):
        verify_native_evidence_archive(rogue)
    with pytest.raises(ValueError):
        restore_native_evidence_archive(
            rogue,target,expected_sha256=sha256(rogue.read_bytes()).hexdigest(),project=tmp_path)
    assert not target.exists()
    assert not (tmp_path/"output"/"outside_private.txt").exists()


def test_original_active_journal_or_unexpected_hidden_feature_is_not_archived(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    sidecar=Path(str(b[1])+"-wal")
    sidecar.write_bytes(b"unreconciled")
    with pytest.raises(ValueError,match="SQLite sidecar"):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    sidecar.unlink()
    (b[2]/".hidden.json").write_text('{"dummy":true}')
    with pytest.raises(ValueError,match="feature evidence"):
        create_native_evidence_archive(plan,captures,archive,project=tmp_path,clock=NOW)
    assert not archive.exists()


def test_mac_cli_create_verify_restore_end_to_end_synthetic(tmp_path):
    b,rule,plan,captures,archive=ready(tmp_path)
    project=tmp_path
    args=[sys.executable,str(SCRIPT)]
    created=subprocess.run([*args,"--action","create","--project",str(project),
                            "--plan",str(plan),"--capture-root",str(captures),
                            "--archive",str(archive)],capture_output=True,text=True)
    assert created.returncode==0,created.stderr
    output=json.loads(created.stdout)
    assert output["market"]=="KR"
    assert output["messages_sent"]==output["external_api_calls"]==0
    assert str(b[1]) not in created.stdout
    original_sha=output["archive_sha256"]
    verified=subprocess.run([*args,"--action","verify","--project",str(project),
                             "--archive",str(archive),
                             "--expected-sha256",original_sha],capture_output=True,text=True)
    assert verified.returncode==0,verified.stderr
    target=tmp_path/"output"/"new_originals"
    restored=subprocess.run([*args,"--action","restore","--project",str(project),
                             "--archive",str(archive),"--target",str(target),
                             "--expected-sha256",original_sha],capture_output=True,text=True)
    assert restored.returncode==0,restored.stderr
    assert json.loads(restored.stdout)["registered_index_chain_verified"] is True
    assert (target/"capture"/"capture_receipt.json").is_file()
