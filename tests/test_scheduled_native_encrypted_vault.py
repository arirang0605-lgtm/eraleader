"""6_5 opt-in scheduled AES-GCM first native source backup without market API."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import pytest

from eraleader import (local_schedule,native_first_capture,
                      scheduled_native_archive,native_sha_witness)
from scripts.run_local_scheduled import main
from test_scheduled_native_archive import setup,NOW


@pytest.fixture
def rig(tmp_path,monkeypatch):
    project,b,plan,root=setup(tmp_path)
    witness=tmp_path/"external_mac"/"sha_only"
    vault=tmp_path/"external_mac"/"ciphertext_only"
    keys=tmp_path/"key_storage";keys.mkdir(mode=0o700)
    cert=keys/"public.crt";key=keys/"private.pem"
    done=subprocess.run(["openssl","req","-x509","-newkey","rsa:3072",
                         "-nodes","-days","1","-subj","/CN=ScheduledDemo",
                         "-keyout",str(key),"-out",str(cert)],capture_output=True)
    assert done.returncode==0
    key.chmod(0o600)
    original_capture=native_first_capture.capture_first_native_topk
    original_archive=scheduled_native_archive.archive_captured_native_plan
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:True)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda p,r:original_capture(p,r,clock=NOW))
    monkeypatch.setattr(scheduled_native_archive,"archive_captured_native_plan",
                        lambda project,plan,root,result:original_archive(
                            project,plan,root,result,clock=NOW))
    jobs=[]
    def research(**kwargs):
        jobs.append("research")
        return {"status":"SYNTHETIC_LOCAL_RESEARCH",
                "messages_sent":0,"external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",research)
    return project,plan,witness,vault,cert,root,jobs


def flags(rig):
    project,plan,witness,vault,cert,root,jobs=rig
    return ["--project",str(project),"--native-first-capture-plan",str(plan),
            "--native-first-private-archive",
            "--native-first-internal-witness-root",str(witness),
            "--native-first-encrypted-vault-root",str(vault),
            "--native-first-encryption-cert",str(cert)]


def test_opt_in_scheduler_handoffs_capture_zip_sha_then_encrypted_vault(rig,capsys):
    project,plan,witness,vault,cert,root,jobs=rig
    assert main(flags(rig))==0
    first=json.loads(capsys.readouterr().out)
    original=first["native_first_capture"]["private_original_archive"]
    assert original["archive_created"] is True
    assert original["separate_volume_sha_witness"]["source_archive_verified"] is True
    encrypted=original["encrypted_cross_volume_backup"]
    assert encrypted["first_backup_created"] is True
    assert encrypted["ciphertext_verified"] is True
    assert encrypted["authenticated_plaintext_verified"] is False
    assert encrypted["archive_sha256"]==original["archive_original_sha256"]
    assert first["messages_sent"]==first["external_api_calls"]==0
    assert len(list(vault.glob("*.cms")))==1 and jobs==["research"]
    assert main(flags(rig))==0
    second=json.loads(capsys.readouterr().out)
    assert second["native_first_capture"]["private_original_archive"][
        "encrypted_cross_volume_backup"]["first_backup_created"] is False
    assert len(list(vault.glob("*.cms")))==1 and len(jobs)==2


@pytest.mark.parametrize("remove",["cert","root","first_witness"])
def test_misconfigured_vault_refused_before_market_job(rig,remove):
    project,plan,witness,vault,cert,root,jobs=rig
    items=flags(rig)
    if remove=="cert":
        items=items[:items.index("--native-first-encryption-cert")]
    elif remove=="root":
        index=items.index("--native-first-encrypted-vault-root")
        items=items[:index]+items[index+2:]
    else:
        index=items.index("--native-first-internal-witness-root")
        items=items[:index]+items[index+2:]
    with pytest.raises(ValueError,match="BOTH|requires|witness"):
        main(items)
    assert jobs==[] and not vault.exists() and not root.exists()


def test_encrypted_vault_same_as_witness_rejected_before_job(rig):
    project,plan,witness,vault,cert,root,jobs=rig
    items=flags(rig)
    i=items.index("--native-first-encrypted-vault-root")
    items[i+1]=str(witness)
    with pytest.raises(ValueError,match="overlap"):
        main(items)
    assert jobs==[] and not root.exists()


def test_generate_plist_with_cipher_copy_does_not_install_or_run(rig,tmp_path):
    project,plan,witness,vault,cert,root,jobs=rig
    plist=tmp_path/"not_installed.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(flags(rig)+["--generate-plist",str(plist)])
    assert jobs==[] and not plist.exists()


def test_ciphertext_loss_does_not_silently_reissue_first_backup(rig,capsys):
    project,plan,witness,vault,cert,root,jobs=rig
    main(flags(rig));capsys.readouterr()
    next(vault.glob("*.cms")).unlink()
    with pytest.raises(ValueError,match="Partial|missing|archive|backup"):
        main(flags(rig))
    assert not len(list(vault.glob("*.cms")))
    assert len(jobs)==2
