"""6_5 encrypted native original ZIP + first witness SHA, synthetic offline tests."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import stat
import subprocess
import sys

import pytest

from eraleader import native_sha_witness
from eraleader.native_encrypted_vault import (
    backup_encrypted_native_original, verify_encrypted_native_original,
    restore_encrypted_native_original,
)
from eraleader.native_first_capture import capture_first_native_topk
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from test_scheduled_native_archive import setup, NOW

SCRIPT = Path(__file__).resolve().parents[1]/"scripts"/"native_encrypted_original_vault.py"


def _openssl(*args):
    process = subprocess.run(["openssl", *map(str,args)], capture_output=True)
    assert process.returncode == 0, process.stderr[-300:]


@pytest.fixture
def rig(tmp_path,monkeypatch):
    project,bundle,plan,capture=setup(tmp_path)
    witness=tmp_path/"mac_disk"/"first_witness"
    vault=tmp_path/"mac_disk"/"encrypted_vault"
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:True)
    key_dir=tmp_path/"local_private_key"
    key_dir.mkdir(mode=0o700)
    key_dir.chmod(0o700)
    key=key_dir/"recovery_private.pem"
    cert=key_dir/"recipient_public.crt"
    _openssl("req","-newkey","rsa:3072","-x509","-nodes",
             "-days","1","-subj","/CN=EraLeaderSynthetic",
             "-keyout",key,"-out",cert)
    key.chmod(0o600)
    first=capture_first_native_topk(plan,capture,clock=NOW)
    archive=archive_captured_native_plan(project,plan,capture,first,clock=NOW)
    record_native_sha_witness(project,plan,capture,archive,witness,clock=NOW)
    return {"project":project,"plan":plan,"capture":capture,"witness":witness,
            "vault":vault,"cert":cert,"key":key,
            "zip":next((project/"output"/"native_first_private_archives").glob("*.zip"))}


def backup(rig,clock=NOW+timedelta(minutes=1)):
    return backup_encrypted_native_original(rig["project"],rig["plan"],rig["capture"],
                                           rig["witness"],rig["vault"],rig["cert"],clock=clock)


def verify(rig,slot):
    return verify_encrypted_native_original(rig["vault"],slot,rig["witness"],rig["cert"])


def restore(rig,slot,name="recovered_new"):
    return restore_encrypted_native_original(rig["vault"],slot,rig["witness"],
                                             rig["cert"],rig["key"],
                                             rig["project"].parent/name)


def paths(rig):
    vault=rig["vault"]
    return (next(vault.glob("*.cms")),next(vault.glob("*_first.json")),
            next(vault.glob("*_guard.json")),next(vault.glob(".*.lock")))


def test_aes_gcm_original_first_sha_off_disk_recover_and_replay(rig):
    original_sha=sha256(rig["zip"].read_bytes()).hexdigest()
    result=backup(rig)
    assert result["status"]=="FIRST_ENCRYPTED_NATIVE_BACKUP_CREATED"
    assert result["archive_sha256"]==original_sha
    assert result["ciphertext_verified"] is True
    assert result["authenticated_plaintext_verified"] is False
    assert result["real_future_leader_accuracy_certified"] is False
    assert result["official_leader_promotions"]==0
    cipher,first,guard,lock=paths(rig)
    assert cipher.read_bytes()[:2] != b"PK"
    assert cipher.read_bytes()!=rig["zip"].read_bytes()
    for phrase in (str(rig["plan"]).encode(),b"original/watch.sqlite",
                   b"security_id",b"issuer_id"):
        assert phrase not in cipher.read_bytes()
        assert phrase not in first.read_bytes() + guard.read_bytes()
    assert stat.S_IMODE(cipher.stat().st_mode)==0o600
    previous={f.name:sha256(f.read_bytes()).hexdigest() for f in paths(rig)}
    again=backup(rig, NOW+timedelta(minutes=2))
    assert again["status"]=="EXISTING_ENCRYPTED_NATIVE_BACKUP_VERIFIED"
    assert previous=={f.name:sha256(f.read_bytes()).hexdigest() for f in paths(rig)}
    audit=verify(rig,result["slot"])
    assert audit["status"]=="ENCRYPTED_NATIVE_BACKUP_SHA_VERIFIED_NOT_DECRYPTED"
    assert sha256(rig["zip"].read_bytes()).hexdigest()==original_sha
    recovery=restore(rig,result["slot"])
    assert recovery["status"]=="ENCRYPTED_NATIVE_FIRST_ORIGINAL_RESTORED_NOT_PIT_CERTIFIED"
    assert recovery["authenticated_plaintext_verified"] is True
    assert recovery["first_original_watch_replayed"] is True
    assert recovery["registered_index_chain_verified"] is True
    assert (rig["project"].parent/"recovered_new"/"original"/"watch.sqlite").is_file()


def test_original_ssd_deleted_can_recover_from_mac_witness_encrypted_vault(rig):
    first=backup(rig)
    # Simulate original SSD unavailable; DO NOT remove the user's real T5DATA.
    shutil.rmtree(rig["project"])
    out=restore(rig,first["slot"],"restore_without_original_SSD")
    assert out["registered_index_chain_verified"] is True
    assert out["archive_sha256"]==first["archive_sha256"]


def test_changed_public_certificate_and_missing_guard_rejected(rig,tmp_path):
    first=backup(rig)
    alternate=tmp_path/"other_cert.crt"
    alternate.write_text("invalid")
    with pytest.raises(ValueError,match="certificate"):
        verify_encrypted_native_original(rig["vault"],first["slot"],
                                         rig["witness"],alternate)
    paths(rig)[2].unlink()
    with pytest.raises(ValueError,match="receipt|guard|Missing"):
        verify(rig,first["slot"])
    with pytest.raises(ValueError,match="receipt|guard|Missing|Partial"):
        backup(rig)


@pytest.mark.parametrize("artifact",["cipher","first","guard","lock"])
def test_cross_device_encrypted_vault_tamper_blocks_restore(rig,artifact):
    first=backup(rig)
    named=dict(zip(("cipher","first","guard","lock"),paths(rig)))
    dest=named[artifact]
    if artifact=="lock":
        dest.unlink()
    elif artifact=="cipher":
        tampered=bytearray(dest.read_bytes());tampered[len(tampered)//2]^=1
        dest.write_bytes(tampered)
    else:
        dest.write_bytes(dest.read_bytes()+b" ")
    with pytest.raises((ValueError,RuntimeError)):
        verify(rig,first["slot"])
    target=rig["project"].parent/"must_not_restore_after_tamper"
    with pytest.raises((ValueError,RuntimeError)):
        restore_encrypted_native_original(rig["vault"],first["slot"],rig["witness"],
                                           rig["cert"],rig["key"],target)
    assert not target.exists()


def test_wrong_private_key_never_publishes_plaintext(rig,tmp_path):
    first=backup(rig)
    other=tmp_path/"other_private_key"
    _openssl("genrsa","-out",other,"3072")
    other.chmod(0o600)
    target=tmp_path/"wrong_key_should_not_restore"
    with pytest.raises(ValueError,match="CMS|decryption"):
        restore_encrypted_native_original(rig["vault"],first["slot"],rig["witness"],
                                           rig["cert"],other,target)
    assert not target.exists()
    assert not list(tmp_path.glob(".encrypted-native-recovery-*"))


def test_world_readable_private_key_cannot_decrypt(rig):
    first=backup(rig)
    rig["key"].chmod(0o644)
    target=rig["project"].parent/"recovery_world_readable"
    with pytest.raises(ValueError,match="mode 0600"):
        restore_encrypted_native_original(rig["vault"],first["slot"],rig["witness"],
                                           rig["cert"],rig["key"],target)
    assert not target.exists()


def test_same_original_volume_rejected_before_any_encrypted_copy(rig,monkeypatch):
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:False)
    with pytest.raises(ValueError,match="different filesystem"):
        backup(rig)
    assert not rig["vault"].exists()


def test_missing_external_witness_first_or_original_source_prevents_first_backup(rig):
    external=next(rig["witness"].glob("*_guard.json"))
    external.unlink()
    with pytest.raises(ValueError,match="guard|witness|receipt|SHA"):
        backup(rig)
    assert not rig["vault"].exists()


def test_source_zip_rewritten_prevents_first_encrypted_publication(rig):
    rig["zip"].write_bytes(rig["zip"].read_bytes()+b"appended")
    with pytest.raises(ValueError,match="SHA|archive|receipt|ZIP"):
        backup(rig)
    assert not rig["vault"].exists()


def test_same_first_model_never_reencrypts_after_witness_digest_change(rig,monkeypatch):
    first=backup(rig)
    from eraleader import native_encrypted_vault as module
    orig=module._external_first
    def spoof(*args,**kwargs):
        value=dict(orig(*args,**kwargs))
        value["witness_sha256"]="f"*64
        return value
    monkeypatch.setattr(module,"_external_first",spoof)
    with pytest.raises(ValueError,match="witness"):
        backup(rig)
    assert len(list(rig["vault"].glob("*.cms")))==1


def test_repeat_restore_does_not_overwrite_first_recovered_original(rig):
    first=backup(rig)
    restore(rig,first["slot"])
    before=(rig["project"].parent/"recovered_new"/"original"/"watch.sqlite").read_bytes()
    with pytest.raises(FileExistsError,match="NEW|already"):
        restore(rig,first["slot"])
    assert (rig["project"].parent/"recovered_new"/"original"/"watch.sqlite").read_bytes()==before


def test_stolen_external_witness_guard_missing_blocks_backup_restore(rig):
    first=backup(rig)
    guard=next(rig["witness"].glob("*_guard.json"))
    guard.unlink()
    with pytest.raises((ValueError, RuntimeError)):
        verify(rig,first["slot"])
    with pytest.raises((ValueError, RuntimeError)):
        restore(rig,first["slot"])


def test_cli_actions_do_not_output_raw_private_paths(rig,capsys):
    # In-process to preserve synthetic distinct-filesystem validation monkeypatch.
    # Mac real cross-volume subprocess is separately tested on T5DATA.
    from scripts.native_encrypted_original_vault import main
    base=["--vault-root",str(rig["vault"]),
          "--witness-root",str(rig["witness"]),
          "--recipient-cert",str(rig["cert"])]
    assert main(base+["--action","backup","--project",str(rig["project"]),
                     "--plan",str(rig["plan"])])==0
    stdout=capsys.readouterr().out
    result=json.loads(stdout)
    assert result["first_backup_created"] is True
    assert str(rig["plan"]) not in stdout
    assert main(base+["--action","verify","--slot",result["slot"]])==0
    assert json.loads(capsys.readouterr().out)["authenticated_plaintext_verified"] is False
    assert main(base+["--action","restore","--slot",result["slot"],
                     "--private-key",str(rig["key"]),
                     "--target",str(rig["project"].parent/"cli_new_target")])==0
    stdout=capsys.readouterr().out
    assert json.loads(stdout)["authenticated_plaintext_verified"] is True
    assert str(rig["plan"]) not in stdout
