"""AES256-GCM/RSA-OAEP CFS SQLite online backup, tamper and restore."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3

import pytest

from test_dart_vintage_registry import fx, capture, reg
from eraleader.dart_cfs_vintage_backup import (
    create_recovery_keypair, backup_vintage_ledger,
    verify_recovery_copies, verify_authenticated_recovery, FILES,
)


@pytest.fixture
def prepared(fx,tmp_path):
    for i,year in enumerate((2023,2024,2025)):
        raw=capture(fx,year=year,nonce=i)
        reg(fx,*raw,seconds=22+i)
    mac=tmp_path/"mac";mac.mkdir(mode=0o700)
    key_dir=mac/"recipient"
    key_info=create_recovery_keypair(key_dir)
    assert key_info["private_key_escrow_independent_volume_verified"] is False
    secret=key_dir/"recovery_private.pem"
    cert=key_dir/"recovery_public.crt"
    assert secret.is_file() and os.stat(secret).st_mode&0o077==0
    assert b"BEGIN PRIVATE KEY" in secret.read_bytes()  # test-only key
    ssd=tmp_path/"ssd";ssd.mkdir(mode=0o700)
    mirror=mac/"ProtectedBackups";mirror.mkdir(mode=0o700)
    scratch=mac/"isolated_recovery";scratch.mkdir(mode=0o700)
    return {"fx":fx,"db":fx["db"],"ssd":ssd,"mac":mirror,
            "cert":cert,"key":secret,"scratch":scratch,"key_dir":key_dir}


def backup(prepared):
    x=prepared
    result=backup_vintage_ledger(
        x["db"],x["ssd"],x["mac"],x["cert"],
        require_independent_devices=False)
    slot=result["slot"]
    return result,x["ssd"]/slot,x["mac"]/slot


def test_authenticated_independent_copies_restore_all_original_sha_and_chain(prepared):
    report,ssd,mac=backup(prepared)
    assert report["events"]==3
    assert report["crypto"]=="AES-256-GCM/RSA-OAEP"
    assert report["private_key_offline_escrow_verified"] is False
    assert set(p.name for p in ssd.iterdir())==FILES
    assert set(p.name for p in mac.iterdir())==FILES
    assert (ssd/"vintage.cms").read_bytes() == (mac/"vintage.cms").read_bytes()
    assert b"SQLite format 3" not in (ssd/"vintage.cms").read_bytes()
    verified=verify_recovery_copies(
        ssd,mac,prepared["cert"],require_independent_devices=False)
    assert not verified["authenticated_recovery_tested"]
    passed=verify_authenticated_recovery(
        ssd,mac,prepared["cert"],prepared["key"],prepared["scratch"],
        require_independent_devices=False)
    assert passed["authenticated_recovery_tested"] is True
    assert passed["restored_chain_verified"] is True
    assert passed["first_known_asof_replay_verified"] is True
    assert passed["events"]==3
    assert passed["plaintext_retained"] is False
    assert list(prepared["scratch"].iterdir())==[]


def test_new_incremental_backup_never_overwrites_old_ciphertext(prepared):
    first,folder,mirror=backup(prepared)
    content=(folder/"vintage.cms").read_bytes()
    second,_,_=backup(prepared)
    assert first["slot"]!=second["slot"]
    assert (folder/"vintage.cms").read_bytes()==content
    assert len(list(prepared["ssd"].iterdir()))==2
    assert len(list(prepared["mac"].iterdir()))==2


def test_mismatched_or_corrupted_ciphertext_blocks_restore(prepared):
    report,ssd,mirror=backup(prepared)
    encrypted=ssd/"vintage.cms"
    content=bytearray(encrypted.read_bytes())
    content[-25]^=0x02
    encrypted.write_bytes(content)
    with pytest.raises(ValueError,match="ciphertext"):
        verify_recovery_copies(ssd,mirror,prepared["cert"],
                               require_independent_devices=False)
    with pytest.raises(ValueError):
        verify_authenticated_recovery(
            ssd,mirror,prepared["cert"],prepared["key"],prepared["scratch"],
            require_independent_devices=False)
    assert list(prepared["scratch"].iterdir())==[]


def test_changing_receipt_json_fails_mac_ssd_compare(prepared):
    _,ssd,mirror=backup(prepared)
    path=ssd/"receipt.json"
    obj=json.loads(path.read_text())
    obj["events"]=999
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="receipt|disagree"):
        verify_recovery_copies(ssd,mirror,prepared["cert"],
                               require_independent_devices=False)


def test_mismatched_certificate_and_wrong_private_key_fail_closed(prepared,tmp_path):
    _,ssd,mirror=backup(prepared)
    unrelated=tmp_path/"other";create_recovery_keypair(unrelated)
    with pytest.raises(ValueError,match="recipient"):
        verify_recovery_copies(ssd,mirror,unrelated/"recovery_public.crt",
                               require_independent_devices=False)
    with pytest.raises(ValueError,match="CMS"):
        verify_authenticated_recovery(
            ssd,mirror,prepared["cert"],unrelated/"recovery_private.pem",
            prepared["scratch"],require_independent_devices=False)
    assert list(prepared["scratch"].iterdir())==[]


def test_backup_rejects_same_volume_without_test_switch(prepared):
    with pytest.raises(ValueError,match="physically separate"):
        backup_vintage_ledger(
            prepared["db"],prepared["ssd"],prepared["mac"],prepared["cert"])
    assert list(prepared["ssd"].iterdir())==[]


def test_missing_or_public_source_blocked_before_encrypt(prepared):
    no_db=prepared["db"].parent/"absent.sqlite"
    with pytest.raises(ValueError):
        backup_vintage_ledger(no_db,prepared["ssd"],prepared["mac"],
                              prepared["cert"],require_independent_devices=False)
    assert list(prepared["ssd"].iterdir())==[]


def test_partial_snapshot_never_passes_complete_marker_gate(prepared):
    _,ssd,mirror=backup(prepared)
    (ssd/"complete.json").unlink()
    with pytest.raises(ValueError,match="Incomplete"):
        verify_recovery_copies(ssd,mirror,prepared["cert"],
                               require_independent_devices=False)


def test_recovery_keypair_refuses_rewriting_existing_secret(prepared):
    first=sha256(prepared["key"].read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="NEW"):
        create_recovery_keypair(prepared["key_dir"])
    assert sha256(prepared["key"].read_bytes()).hexdigest()==first
