"""External-recipient key escrow: real CMS GCM, negative cases and DR drills.

The fixture 'offline key' is generated in a test temp directory only.
It DOES NOT constitute an actual independent human/offline escrow.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import pytest

from test_dart_vintage_registry import fx
from test_dart_cfs_vintage_backup import prepared, backup
from eraleader.dart_cfs_vintage_backup import create_recovery_keypair
from eraleader.dart_cfs_external_key_escrow import (
    prepare_external_key_escrow, verify_external_key_escrow,
    drill_external_key_escrow, ARTIFACTS,
)


@pytest.fixture
def external(prepared,tmp_path):
    external_home=tmp_path/"SIMULATED_external_offline_custodian"
    result=create_recovery_keypair(external_home)
    assert result["private_key_escrow_independent_volume_verified"] is False
    target=tmp_path/"external_encrypted_storage"
    target.mkdir(mode=0o700)
    return {
        "key":external_home/"recovery_private.pem",
        "cert":external_home/"recovery_public.crt",
        "root":target,
    }


def export(prepared, external):
    return prepare_external_key_escrow(
        prepared["key"],prepared["cert"],external["cert"],external["root"],
        require_independent_device=False)


def test_external_recipient_key_escrow_restores_existing_authenticated_cfs(prepared,external):
    sealed=export(prepared,external)
    assert sealed["status"]=="EXTERNAL_KEY_ESCROW_ENCRYPTED_NOT_OFFLINE_CUSTODY_CERTIFIED"
    assert sealed["actual_offline_private_key_custody_verified"] is False
    escrow=external["root"]/sealed["slot"]
    assert set(p.name for p in escrow.iterdir())==ARTIFACTS
    assert b"BEGIN PRIVATE KEY" not in (escrow/"recovery_key.cms").read_bytes()
    assert not any(p.stat().st_mode & 0o077 for p in escrow.iterdir())
    expected=verify_external_key_escrow(escrow,prepared["cert"],external["cert"])
    assert expected["ciphertext_sha256"]==sealed["ciphertext_sha256"]
    _,ssd,mac=backup(prepared)
    recovered=drill_external_key_escrow(
        escrow,prepared["cert"],external["cert"],external["key"],
        ssd,mac,prepared["scratch"],require_independent_device=False)
    assert recovered["first_known_asof_replay_verified"] is True
    assert recovered["original_backup_authenticated"] is True
    assert recovered["scratch_plaintext_retained"] is False
    assert recovered["actual_offline_private_key_custody_verified"] is False
    assert list(prepared["scratch"].iterdir())==[]
    assert prepared["key"].is_file()


def test_external_escrow_refuses_same_primary_RSA_recipient(prepared,external):
    with pytest.raises(ValueError,match="DIFFERENT"):
        prepare_external_key_escrow(
            prepared["key"],prepared["cert"],prepared["cert"],external["root"],
            require_independent_device=False)
    assert list(external["root"].iterdir())==[]


def test_same_device_rejected_by_default_without_test_switch(prepared,external):
    with pytest.raises(ValueError,match="DIFFERENT device"):
        prepare_external_key_escrow(
            prepared["key"],prepared["cert"],external["cert"],external["root"])
    assert list(external["root"].iterdir())==[]


def test_wrong_external_private_key_does_not_create_decrypted_backup(prepared,external,tmp_path):
    package=export(prepared,external)
    _,ssd,mac=backup(prepared)
    other=tmp_path/"other_external_key"
    create_recovery_keypair(other)
    with pytest.raises(ValueError,match="mismatches"):
        drill_external_key_escrow(
            external["root"]/package["slot"],prepared["cert"],external["cert"],
            other/"recovery_private.pem",ssd,mac,prepared["scratch"],
            require_independent_device=False)
    assert list(prepared["scratch"].iterdir())==[]


def test_key_escrow_tamper_blocks_before_decryption(prepared,external):
    info=export(prepared,external)
    folder=external["root"]/info["slot"]
    cipher=folder/"recovery_key.cms"
    raw=bytearray(cipher.read_bytes())
    raw[-30]^=0x11
    cipher.write_bytes(raw)
    with pytest.raises(ValueError,match="ciphertext SHA mismatch"):
        verify_external_key_escrow(folder,prepared["cert"],external["cert"])


def test_incomplete_key_escrow_marker_rejected(prepared,external):
    info=export(prepared,external)
    folder=external["root"]/info["slot"]
    (folder/"complete.json").unlink()
    with pytest.raises(ValueError,match="Incomplete"):
        verify_external_key_escrow(folder,prepared["cert"],external["cert"])


def test_different_external_recipient_certificate_fails_pinned_escrow(prepared,external,tmp_path):
    info=export(prepared,external)
    other=tmp_path/"different_external_cert"
    create_recovery_keypair(other)
    with pytest.raises(ValueError,match="receipt/identity"):
        verify_external_key_escrow(
            external["root"]/info["slot"],prepared["cert"],
            other/"recovery_public.crt")


def test_second_new_slot_does_not_overwrite_existing_escrow(prepared,external):
    first=export(prepared,external)
    path=external["root"]/first["slot"]/"recovery_key.cms"
    old=path.read_bytes()
    second=export(prepared,external)
    assert first["slot"]!=second["slot"]
    assert path.read_bytes()==old
    assert len(list(external["root"].iterdir()))==2


def test_escrow_wrong_source_private_identity_fails_before_publish(prepared,external):
    with pytest.raises(ValueError,match="does not match"):
        prepare_external_key_escrow(
            external["key"],prepared["cert"],external["cert"],external["root"],
            require_independent_device=False)
    assert list(external["root"].iterdir())==[]



def test_escrow_verify_cli_reports_only_sha_without_key_or_path(prepared, external):
    package=export(prepared,external)
    escrow=external["root"]/package["slot"]
    script=Path(__file__).resolve().parents[1]/"scripts/run_dart_cfs_external_escrow.py"
    result=subprocess.run([
        sys.executable,str(script),"verify","--escrow",str(escrow),
        "--original-public-cert",str(prepared["cert"]),
        "--external-public-cert",str(external["cert"])
    ],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert output["status"]=="EXTERNAL_KEY_ESCROW_SHA_VERIFIED_NOT_DECRYPTED"
    assert output["actual_offline_private_key_custody_verified"] is False
    assert output["external_recovery_drill_passed"] is False
    assert str(prepared["key"]) not in result.stdout
    assert "PRIVATE KEY" not in result.stdout


def test_export_cli_refuses_same_volume_and_never_prints_private_path(prepared,external):
    script=Path(__file__).resolve().parents[1]/"scripts/run_dart_cfs_external_escrow.py"
    result=subprocess.run([
        sys.executable,str(script),"export",
        "--original-private-key",str(prepared["key"]),
        "--original-public-cert",str(prepared["cert"]),
        "--external-public-cert",str(external["cert"]),
        "--escrow-root",str(external["root"])
    ],capture_output=True,text=True,timeout=15)
    assert result.returncode==2
    assert result.stdout==""
    assert result.stderr.startswith("EXTERNAL_KEY_ESCROW_BLOCKED")
    assert str(prepared["key"]) not in result.stderr
    assert list(external["root"].iterdir())==[]
