"""6_5 real cold-package SHA PIN -> AES-GCM -> first-WATCH/census replay (synthetic)."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from eraleader import native_cold_replay_drill as drill
from eraleader import native_cold_integrity as pin
from test_native_encrypted_vault import rig
from test_native_cold_custody import bundle, export
from test_native_cold_integrity import enrolled
from test_scheduled_native_archive import NOW

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"run_native_cold_replay_drill.py"
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def ready(enrolled,tmp_path):
    rig,archive,root,first,receipt=enrolled
    scratch=tmp_path/"separate_private_scratch"
    scratch.mkdir(mode=0o700)
    scratch.chmod(0o700)
    return rig,archive,root,first,receipt,scratch


def run(case,*,name="kr-first",slot=None,key=None,time=NOW):
    rig,archive,root,first,receipt,scratch=case
    return drill.run_cold_replay_drill(
        rig["project"],root,name,slot or first["slots"][0],
        key if key is not None else rig["key"],scratch,
        allow_colocated_research=True,clock=time)


def history(case):
    rig,archive,root,first,receipt,scratch=case
    return drill.verify_cold_replay_history(
        rig["project"],root,scratch,allow_colocated_research=True)


def test_cold_zip_recovers_real_original_from_separate_pinned_ciphertext(ready):
    rig,archive,root,first,receipt,scratch=ready
    raw=sha256(archive.read_bytes()).hexdigest()
    original=sha256(rig["zip"].read_bytes()).hexdigest()
    registered=(root/"pins"/(receipt["pin_id"]+"_first.json")).read_bytes()
    result=run(ready)
    latest=result["latest"]
    assert result["status"]==drill.STATUS
    assert latest["outcome"]=="PASSED" and latest["reason"]=="NONE"
    assert latest["full_cold_zip_verified"] is True
    assert latest["aes_gcm_authenticated"] is True
    assert latest["first_watch_score_replayed"] is True
    assert latest["census_index_replayed"] is True
    assert latest["temporary_plaintext_removed"] is True
    assert latest["package_sha256"]==raw
    assert latest["first_pin_sha256"]==receipt["first_pin_sha256"]
    assert latest["original_archive_sha256"]==original
    assert result["messages_sent"]==result["external_api_calls"]==0
    assert list(scratch.iterdir())==[]
    assert sha256(archive.read_bytes()).hexdigest()==raw
    assert sha256(rig["zip"].read_bytes()).hexdigest()==original
    assert (root/"pins"/(receipt["pin_id"]+"_first.json")).read_bytes()==registered
    html=(rig["project"]/"output"/drill.DIR/"site"/"index.html").read_text()
    output=(rig["project"]/"output"/drill.DIR/"report.json").read_text()
    for private in (str(rig["key"]),str(rig["plan"]),str(archive)):
        assert private not in html and private not in output
    assert history(ready)["check_count"]==1


def test_repeated_replays_append_proofs_without_overwriting_first(ready):
    first=run(ready)
    path=ready[0]["project"]/"output"/drill.DIR/"first_event.json"
    original=path.read_bytes()
    second=run(ready,time=NOW+timedelta(minutes=1))
    assert second["latest"]["previous_sha256"]==first["latest"]["event_sha256"]
    assert second["check_count"]==2
    assert path.read_bytes()==original
    assert history(ready)["chain_verified"] is True
    assert ready[-1].is_dir() and not list(ready[-1].iterdir())


@pytest.mark.parametrize("state",["corrupt","missing","symlink"])
def test_backup_damage_refuses_private_key_replay_and_records_failure(ready,state,tmp_path):
    rig,archive,root,first,receipt,scratch=ready
    raw=archive.read_bytes()
    if state=="corrupt": archive.write_bytes(raw+b"bad")
    elif state=="missing": archive.unlink()
    else:
        moved=tmp_path/"renamed_cold.zip"
        archive.rename(moved)
        archive.symlink_to(moved)
    result=run(ready)
    row=result["latest"]
    assert row["outcome"]=="FAILED"
    assert row["reason"]=="INDEPENDENT_PIN_NOT_VERIFIED"
    assert row["aes_gcm_authenticated"] is False
    assert row["first_watch_score_replayed"] is False
    assert row["package_sha256"]==drill.ZERO
    assert not list(scratch.iterdir())
    assert history(ready)["check_count"]==1
    if archive.is_symlink():archive.unlink()
    archive.write_bytes(raw)
    restored=run(ready,time=NOW+timedelta(minutes=1))
    assert restored["latest"]["outcome"]=="PASSED"


@pytest.mark.parametrize("state",["removed_guard","damaged_first","public_mode"])
def test_damaged_external_sha_pin_blocks_cold_restore(ready,state):
    rig,archive,root,first,receipt,scratch=ready
    p=root/"pins"/(receipt["pin_id"]+"_first.json")
    g=root/"pins"/(receipt["pin_id"]+"_guard.json")
    if state=="removed_guard":g.unlink()
    elif state=="damaged_first":p.write_bytes(p.read_bytes()+b"edit")
    else:p.chmod(0o644)
    result=run(ready)
    assert result["latest"]["reason"]=="INDEPENDENT_PIN_NOT_VERIFIED"
    assert result["latest"]["outcome"]=="FAILED"
    assert result["latest"]["aes_gcm_authenticated"] is False
    assert not list(scratch.iterdir())


@pytest.mark.parametrize("mode",["wrong_password_key","world_readable","key_missing"])
def test_explicit_wrong_or_unsafe_key_is_failed_proof(ready,mode,tmp_path):
    rig,archive,root,first,receipt,scratch=ready
    key=tmp_path/"untrusted_key.pem"
    if mode=="wrong_password_key":
        key.write_text("not-a-key")
    elif mode=="world_readable":
        key.write_bytes(rig["key"].read_bytes());key.chmod(0o644)
    else:
        pass
    response=run(ready,key=key)
    assert response["latest"]["reason"]=="UNSAFE_OR_MISSING_KEY"
    assert response["latest"]["aes_gcm_authenticated"] is False
    assert response["latest"]["outcome"]=="FAILED"
    assert not list(scratch.iterdir())


def test_wrong_or_unenrolled_slot_cannot_claim_original_replay(ready):
    result=run(ready,slot="us_"+"a"*24)
    assert result["latest"]["outcome"]=="FAILED"
    assert result["latest"]["reason"]=="COLD_PACKAGE_RECONSTRUCTION_FAILED"
    assert result["latest"]["original_archive_sha256"]==drill.ZERO
    assert list(ready[-1].iterdir())==[]


def test_missing_name_or_duplicate_digest_never_enrolls_by_drill(ready):
    project,archive,root,first,receipt,scratch=ready
    before=set(root.joinpath("pins").iterdir())
    report=run(ready,name="us-other")
    assert report["latest"]["outcome"]=="FAILED"
    assert report["latest"]["reason"]=="INDEPENDENT_PIN_NOT_VERIFIED"
    assert set(root.joinpath("pins").iterdir())==before


def test_forged_return_from_replay_never_passes_without_census(ready,monkeypatch):
    def counterfeit(*a,**kw):
        return {"status":"ENCRYPTED_NATIVE_FIRST_ORIGINAL_RESTORED_NOT_PIT_CERTIFIED",
                "authenticated_plaintext_verified":True,
                "first_original_watch_replayed":True,
                "registered_index_chain_verified":False,
                "official_leader_promotions":0,"messages_sent":0,
                "external_api_calls":0,"real_future_leader_accuracy_certified":False}
    monkeypatch.setattr(drill,"restore_encrypted_native_original",counterfeit)
    outcome=run(ready)["latest"]
    assert outcome["outcome"]=="FAILED"
    assert outcome["reason"]=="ORIGINAL_WATCH_OR_CENSUS_REPLAY_FAILED"
    assert outcome["aes_gcm_authenticated"] is False
    assert outcome["temporary_plaintext_removed"] is True


@pytest.mark.parametrize("target",["genesis.json","history.jsonl","first_event.json","report.json"])
def test_original_sha_replay_log_tamper_or_rollback_is_not_success(ready,target):
    run(ready)
    path=ready[0]["project"]/"output"/drill.DIR/target
    if target=="history.jsonl":
        path.write_bytes(b"")
    else:
        path.write_bytes(path.read_bytes()+b"tamper")
    with pytest.raises((ValueError,KeyError)):
        history(ready)
    with pytest.raises((ValueError,KeyError)):
        run(ready,time=NOW+timedelta(minutes=1))


def test_recovery_clock_backdating_rejected_before_event_write(ready):
    run(ready)
    with pytest.raises(ValueError,match="clock"):
        run(ready,time=NOW-timedelta(seconds=1))
    assert history(ready)["check_count"]==1


def test_hardened_scratch_permissions_and_no_project_overlap(ready):
    rig,archive,root,first,receipt,scratch=ready
    scratch.chmod(0o755)
    with pytest.raises(ValueError,match="0700|group/others"):
        run(ready)
    scratch.chmod(0o700)
    with pytest.raises(ValueError,match="overlap|different|destination"):
        drill.run_cold_replay_drill(
            rig["project"],root,"kr-first",first["slots"][0],rig["key"],root,
            allow_colocated_research=True)


def test_strict_external_fs_boundary_remains_fail_closed(ready):
    rig,archive,root,first,receipt,scratch=ready
    with pytest.raises(ValueError,match="different from original"):
        drill.run_cold_replay_drill(
            rig["project"],root,"kr-first",first["slots"][0],rig["key"],scratch)
    assert not (rig["project"]/"output"/drill.DIR).exists()


def test_verify_history_does_not_need_private_key_even_if_unavailable(ready):
    run(ready)
    rig,archive,root,first,receipt,scratch=ready
    rig["key"].unlink()
    result=history(ready)
    assert result["private_key_accessed"] is False
    assert result["plaintext_decrypted"] is False
    assert result["check_count"]==1


def test_cli_real_replay_verify_history_and_failure_redacts_paths(ready):
    rig,archive,root,first,receipt,scratch=ready
    base=[sys.executable,str(SCRIPT),"--project",str(rig["project"]),
          "--pin-root",str(root),"--scratch-root",str(scratch),
          "--allow-colocated-research-only"]
    env=os.environ.copy()
    env["PYTHONPATH"]=str(ROOT/"src")
    invocation=base+["--action","run","--name","kr-first",
                     "--slot",first["slots"][0],"--private-key",str(rig["key"])]
    launched=subprocess.run(invocation,cwd=ROOT,env=env,text=True,capture_output=True)
    assert launched.returncode==2
    assert str(rig["key"]) not in launched.stderr
    assert str(archive) not in launched.stderr
    from scripts.run_native_cold_replay_drill import main
    assert main(base[2:]+["--action","run","--name","kr-first",
                           "--slot",first["slots"][0],
                           "--private-key",str(rig["key"])])==0
    assert main(base[2:]+["--action","verify-history"])==0
    assert main(base[2:]+["--action","run","--name","kr-first",
                         "--slot",first["slots"][0],
                         "--private-key",str(scratch/"lost.pem")])==2
    assert history(ready)["check_count"]==2
    assert not list(scratch.iterdir())


def test_no_private_key_argument_allowed_in_history_verification(ready):
    rig,archive,root,first,receipt,scratch=ready
    env=os.environ.copy();env["PYTHONPATH"]=str(ROOT/"src")
    command=[sys.executable,str(SCRIPT),"--action","verify-history",
             "--project",str(rig["project"]),"--pin-root",str(root),
             "--scratch-root",str(scratch),"--private-key",str(rig["key"])]
    process=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
    assert process.returncode==2
    assert "verify-history" in process.stderr
    assert not (rig["project"]/"output"/drill.DIR).exists()
