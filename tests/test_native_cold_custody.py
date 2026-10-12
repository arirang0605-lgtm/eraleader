"""6_5 portable encrypted-only first native cold custody tests (synthetic)."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import json
import shutil
import os

import pytest

from eraleader import native_cold_custody as custody
from eraleader.native_cold_custody import (
    create_portable_native_custody, check_portable_native_custody,
)
from eraleader.native_encrypted_vault import restore_encrypted_native_original
from eraleader.native_first_capture import capture_first_native_topk, read_capture_plan
from eraleader.native_evidence_archive import _slot
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from test_native_encrypted_vault import rig, backup
from test_native_first_capture import prepare
from test_scheduled_native_archive import NOW


@pytest.fixture
def bundle(rig,tmp_path):
    sealed=backup(rig)
    destination=tmp_path/"cold_store"
    destination.mkdir(mode=0o700)
    destination.chmod(0o700)
    path=destination/"first_native_cold.zip"
    return rig,sealed,path


def export(bundle,*,allow=True):
    rig,first,path=bundle
    return create_portable_native_custody(
        rig["project"],[first["slot"]],rig["vault"],rig["witness"],
        rig["cert"],path,allow_colocated_research=allow,clock=NOW)


def recover(bundle,name="offline_reconstruction"):
    rig,first,path=bundle
    folder=rig["project"].parent/"restored_cold"
    folder.mkdir(mode=0o700,exist_ok=True)
    folder.chmod(0o700)
    target=folder/name
    return target


def test_encrypted_only_export_pin_verify_reconstruct_and_real_original_replay(bundle):
    rig,first,path=bundle
    original=sha256(rig["zip"].read_bytes()).hexdigest()
    created=export(bundle)
    assert created["status"]=="PORTABLE_ENCRYPTED_NATIVE_CUSTODY_CREATED_NOT_OFFSITE_ATTESTED"
    assert created["third_filesystem_st_dev_distinct"] is False
    assert created["offsite_geography_attested"] is False
    assert created["separate_package_sha_pin_required_for_recovery"] is True
    assert created["plaintext_or_private_key_included"] is False
    assert created["messages_sent"]==created["external_api_calls"]==0
    assert created["file_count"]==8 and created["slot_count"]==1
    digest=sha256(path.read_bytes()).hexdigest()
    assert digest==created["package_sha256"]
    with ZipFile(path) as zf:
        members=set(zf.namelist())
        assert "public/original_recipient.crt" in members
        assert "COLD_CUSTODY_MANIFEST.json" in members
        assert f"vault/native_{first['slot']}.cms" in members
        assert not any(".pem" in m or ".sqlite" in m or
                       "original/" in m or "private" in m for m in members)
        source_cipher=next(rig["vault"].glob("*.cms")).read_bytes()
        assert zf.read(f"vault/native_{first['slot']}.cms")==source_cipher
        assert zf.read(f"vault/native_{first['slot']}.cms")[:2]!=b"PK"
        assert not any(str(rig["plan"]).encode() in zf.read(name) or
                       str(rig["key"]).encode() in zf.read(name)
                       for name in members if name!="public/original_recipient.crt")
    validated=check_portable_native_custody(path,digest)
    assert validated["ciphertext_and_first_witness_verified"] is True
    assert validated["plaintext_authenticated_or_replayed"] is False
    assert validated["private_key_accessed"] is False
    target=recover(bundle)
    restored=check_portable_native_custody(path,digest,restore_target=target)
    assert restored["status"]=="PORTABLE_ENCRYPTED_NATIVE_CUSTODY_RESTORED_NOT_DECRYPTED"
    assert (target/"vault").is_dir() and (target/"witness").is_dir()
    assert (target/"public"/"original_recipient.crt").is_file()
    # The reconstructed encrypted evidence is sufficient for the existing
    # authenticated plaintext/census replay only when user supplies key.
    replay=restore_encrypted_native_original(
        target/"vault",first["slot"],target/"witness",
        target/"public"/"original_recipient.crt",rig["key"],
        target.parent/"authenticated_watch_recovered")
    assert replay["authenticated_plaintext_verified"] is True
    assert replay["first_original_watch_replayed"] is True
    assert replay["registered_index_chain_verified"] is True
    assert replay["archive_sha256"]==original
    assert sha256(rig["zip"].read_bytes()).hexdigest()==original


def test_strict_cold_storage_refuses_same_filesystem_before_creating_zip(bundle):
    with pytest.raises(ValueError,match="THIRD filesystem"):
        export(bundle,allow=False)
    assert not bundle[2].exists()


def test_staged_third_filesystem_accepts_distinct_st_dev_and_still_not_offsite_attested(
        bundle,monkeypatch):
    monkeypatch.setattr(custody,"_distinct_filesystems",lambda *a:True)
    report=export(bundle,allow=False)
    assert report["third_filesystem_st_dev_distinct"] is True
    assert report["offsite_geography_attested"] is False


def test_first_package_immutable_no_replace_even_same_original_inputs(bundle):
    export(bundle)
    original_sha=sha256(bundle[2].read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        export(bundle)
    assert sha256(bundle[2].read_bytes()).hexdigest()==original_sha


def test_requires_external_first_sha_pin_for_verify_and_restore(bundle):
    export(bundle)
    with pytest.raises(ValueError,match="REQUIRES"):
        check_portable_native_custody(bundle[2],None)
    with pytest.raises(ValueError,match="SHA PIN"):
        check_portable_native_custody(bundle[2],"f"*64)
    assert not recover(bundle).exists()


def test_no_plaintext_source_zip_needed_for_portable_export_or_verify(bundle):
    rig,_,path=bundle
    original_zip=rig["zip"]
    original_zip.unlink()
    result=export(bundle)
    assert check_portable_native_custody(path,result["package_sha256"])[
        "ciphertext_and_first_witness_verified"] is True


def test_original_ssd_project_can_disappear_after_custody_export(bundle):
    rig,first,path=bundle
    seal=export(bundle)
    shutil.rmtree(rig["project"])
    assert check_portable_native_custody(path,seal["package_sha256"])[
        "ciphertext_and_first_witness_verified"] is True
    dest=recover(bundle,"no_original_project")
    check_portable_native_custody(path,seal["package_sha256"],restore_target=dest)
    replay=restore_encrypted_native_original(
        dest/"vault",first["slot"],dest/"witness",
        dest/"public"/"original_recipient.crt",rig["key"],
        dest.parent/"new_watch_without_source_ssd")
    assert replay["registered_index_chain_verified"] is True


@pytest.mark.parametrize("kind",["cipher","encrypted_first","encrypted_guard",
                                 "encrypted_lock","witness_first","witness_guard",
                                 "witness_lock","cert"])
def test_missing_or_corrupt_original_immutable_evidence_prevents_export(bundle,kind):
    rig,first,path=bundle
    slot=first["slot"]
    sources={
        "cipher":rig["vault"]/f"native_{slot}.cms",
        "encrypted_first":rig["vault"]/f"native_{slot}_first.json",
        "encrypted_guard":rig["vault"]/f"native_{slot}_guard.json",
        "encrypted_lock":rig["vault"]/f".native_{slot}.lock",
        "witness_first":rig["witness"]/f"native_{slot}_first.json",
        "witness_guard":rig["witness"]/f"native_{slot}_guard.json",
        "witness_lock":rig["witness"]/f".native_{slot}.lock",
        "cert":rig["cert"],
    }
    item=sources[kind]
    original=item.read_bytes()
    if kind in ("cipher","encrypted_first","cert"):
        item.write_bytes(original+b"tamper")
    else:
        item.unlink()
    with pytest.raises((ValueError,OSError,RuntimeError)):
        export(bundle)
    assert not path.exists()


def test_portable_package_tamper_detected_before_any_restoration(bundle):
    done=export(bundle)
    path=bundle[2]
    original=bytearray(path.read_bytes())
    original[len(original)//2]^=1
    path.write_bytes(original)
    dest=recover(bundle)
    with pytest.raises(ValueError,match="SHA PIN"):
        check_portable_native_custody(path,done["package_sha256"],restore_target=dest)
    assert not dest.exists()


def test_user_repin_of_rewritten_cipher_cannot_bypass_original_first_anchors(bundle):
    export(bundle)
    path=bundle[2]
    altered=path.parent/"repack.zip"
    with ZipFile(path) as source, ZipFile(altered,"w",compression=ZIP_STORED) as z:
        for info in source.infolist():
            body=bytearray(source.read(info.filename))
            if info.filename.endswith(".cms"):
                body[len(body)//2]^=1
            z.writestr(info,body)
    with pytest.raises(ValueError,match="SHA mismatch|ciphertext|portable|SHA"):
        check_portable_native_custody(altered,sha256(altered.read_bytes()).hexdigest())


def test_additional_member_even_with_new_pin_is_refused(bundle):
    export(bundle)
    path=bundle[2]
    path2=path.parent/"extra.zip"
    with ZipFile(path) as original, ZipFile(path2,"w",compression=ZIP_STORED) as forged:
        for i in original.infolist():
            forged.writestr(i,original.read(i.filename))
        forged.writestr("../leaked_source.sqlite",b"forbidden")
    with pytest.raises(ValueError,match="untrusted|member|encrypted"):
        check_portable_native_custody(path2,sha256(path2.read_bytes()).hexdigest())


def test_restore_never_overwrites_existing_reconstructed_vault(bundle):
    created=export(bundle)
    target=recover(bundle)
    check_portable_native_custody(bundle[2],created["package_sha256"],restore_target=target)
    original=(target/"vault"/f"native_{bundle[1]['slot']}.cms").read_bytes()
    with pytest.raises(FileExistsError):
        check_portable_native_custody(bundle[2],created["package_sha256"],restore_target=target)
    assert (target/"vault"/f"native_{bundle[1]['slot']}.cms").read_bytes()==original


def test_unprotected_or_linked_cold_destination_rejected_before_packaging(bundle,tmp_path):
    rig,_,path=bundle
    other=tmp_path/"world_visible"
    other.mkdir(mode=0o755)
    other.chmod(0o755)
    with pytest.raises(ValueError,match="mode 0700"):
        create_portable_native_custody(
            rig["project"],[bundle[1]["slot"]],rig["vault"],
            rig["witness"],rig["cert"],other/"pkg.zip",
            allow_colocated_research=True)
    link=tmp_path/"linked"
    link.symlink_to(path.parent,target_is_directory=True)
    with pytest.raises(ValueError,match="Linked"):
        create_portable_native_custody(
            rig["project"],[bundle[1]["slot"]],rig["vault"],
            rig["witness"],rig["cert"],link/"pkg.zip",
            allow_colocated_research=True)
    assert not path.exists()


def test_duplicate_slots_or_incorrect_model_rejected_before_copy(bundle):
    rig,first,path=bundle
    with pytest.raises(ValueError,match="Duplicate"):
        create_portable_native_custody(
            rig["project"],[first["slot"]]*2,rig["vault"],rig["witness"],
            rig["cert"],path,allow_colocated_research=True)
    with pytest.raises(ValueError,match="model"):
        create_portable_native_custody(
            rig["project"],["kr_aaa"],rig["vault"],rig["witness"],
            rig["cert"],path,allow_colocated_research=True)
    assert not path.exists()


def test_manifest_allows_kr_and_us_multi_slot_without_raw_sources(bundle,tmp_path):
    rig,first,path=bundle
    b,rule,us,unused=prepare(tmp_path/"fresh_us",market="US")
    original=capture_first_native_topk(us,rig["capture"],clock=NOW)
    issued=archive_captured_native_plan(
        rig["project"],us,rig["capture"],original,clock=NOW)
    record_native_sha_witness(
        rig["project"],us,rig["capture"],issued,rig["witness"],clock=NOW)
    from eraleader.native_encrypted_vault import backup_encrypted_native_original
    second=backup_encrypted_native_original(
        rig["project"],us,rig["capture"],rig["witness"],
        rig["vault"],rig["cert"],clock=NOW)
    first_slot,second_slot=first["slot"],second["slot"]
    summary=create_portable_native_custody(
        rig["project"],[second_slot,first_slot],
        rig["vault"],rig["witness"],rig["cert"],path,
        allow_colocated_research=True)
    assert summary["slots"]==sorted([first_slot,second_slot])
    assert summary["file_count"]==15 and summary["slot_count"]==2
    restored=recover(bundle)
    check_portable_native_custody(path,summary["package_sha256"],restore_target=restored)
    for slot in (first_slot,second_slot):
        assert (restored/"vault"/f"native_{slot}.cms").is_file()
        assert (restored/"witness"/f"native_{slot}_first.json").is_file()


def test_copy_forbidden_into_source_project_or_first_vault(bundle):
    rig,first,path=bundle
    target=rig["project"]/"output"/"do_not_put_custody_here.zip"
    with pytest.raises(ValueError,match="must not go inside"):
        create_portable_native_custody(
            rig["project"],[first["slot"]],rig["vault"],rig["witness"],
            rig["cert"],target,allow_colocated_research=True)
    target=rig["vault"]/"do_not_put_custody_here.zip"
    with pytest.raises(ValueError,match="must not go inside"):
        create_portable_native_custody(
            rig["project"],[first["slot"]],rig["vault"],rig["witness"],
            rig["cert"],target,allow_colocated_research=True)


def test_source_change_after_staging_prevents_cold_publishing(bundle,monkeypatch):
    rig,first,path=bundle
    original=custody._verified
    calls=[]
    def switch(*args,**kwargs):
        data=dict(original(*args,**kwargs))
        calls.append(1)
        if len(calls)>1:
            data["encrypted_sha256"]="f"*64
        return data
    monkeypatch.setattr(custody,"_verified",switch)
    with pytest.raises(ValueError,match="changed|contradicts"):
        export(bundle)
    assert not path.exists()


def test_no_private_key_needed_for_export_verify_and_encrypted_reconstruction(bundle):
    rig,first,path=bundle
    rig["key"].unlink()
    created=export(bundle)
    validated=check_portable_native_custody(path,created["package_sha256"])
    assert validated["plaintext_authenticated_or_replayed"] is False
    dest=recover(bundle)
    reconstructed=check_portable_native_custody(
        path,created["package_sha256"],restore_target=dest)
    assert reconstructed["private_key_accessed"] is False
    assert (dest/"vault"/f"native_{first['slot']}.cms").is_file()


@pytest.mark.parametrize("mutation",["nonstring_member","bad_local_clock","duplicate_member"])
def test_forged_metadata_types_never_throw_unhandled_tracebacks(bundle,mutation):
    created=export(bundle)
    original=bundle[2]
    forged=original.parent/("malformed_"+mutation+".zip")
    from eraleader.native_evidence_archive import _bytes
    with ZipFile(original) as source, ZipFile(forged,"w",compression=ZIP_STORED) as output:
        for info in source.infolist():
            body=source.read(info.filename)
            if info.filename=="COLD_CUSTODY_MANIFEST.json":
                data=json.loads(body)
                if mutation=="nonstring_member":
                    data["members"][0]["name"]=["not", "a", "file"]
                elif mutation=="bad_local_clock":
                    data["created_at_local_utc"]=["wrong", "type"]
                else:
                    data["members"][-1]["name"]=data["members"][0]["name"]
                body=_bytes(data)
            output.writestr(info,body)
    with pytest.raises(ValueError):
        check_portable_native_custody(
            forged,sha256(forged.read_bytes()).hexdigest())
