"""6_5 opt-in scheduler bridge: raw source stays on SSD; SHA goes off SSD."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from eraleader import (
    local_schedule,native_first_capture,scheduled_native_archive,
    native_sha_witness,
)
from scripts.run_local_scheduled import main
from test_scheduled_native_archive import setup, NOW


@pytest.fixture
def rig(tmp_path,monkeypatch):
    project,b,plan,root=setup(tmp_path)
    disk=tmp_path/"mac_internal"/"first_sha_witness"
    original_capture=native_first_capture.capture_first_native_topk
    original_archive=scheduled_native_archive.archive_captured_native_plan
    calls=[]
    def research(**kwargs):
        calls.append("research")
        return {"status":"LOCAL_RESEARCH_SYNTHETIC_ONLY",
                "messages_sent":0,"external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",research)
    monkeypatch.setattr(native_first_capture,"capture_first_native_topk",
                        lambda plan_path,capture: original_capture(plan_path,capture,clock=NOW))
    monkeypatch.setattr(scheduled_native_archive,"archive_captured_native_plan",
                        lambda project,plan,capture,record: original_archive(
                            project,plan,capture,record,clock=NOW))
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:True)
    return project,plan,root,disk,calls


def flags(rig):
    project,plan,root,disk,calls=rig
    return ["--project",str(project),
            "--native-first-capture-plan",str(plan),
            "--native-first-private-archive",
            "--native-first-internal-witness-root",str(disk)]


def test_explicit_scheduler_runs_capture_then_private_archive_then_separate_disk_witness(
        rig,capsys):
    project,plan,root,disk,calls=rig
    assert main(flags(rig))==0
    record=json.loads(capsys.readouterr().out)
    first=record["native_first_capture"]
    assert first["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"
    assert first["private_original_archive"]["archive_created"] is True
    witness=first["private_original_archive"]["separate_volume_sha_witness"]
    assert witness["status"]=="FIRST_SEPARATE_VOLUME_NATIVE_SHA_WITNESSED_NOT_ATTESTED"
    assert witness["archive_sha256"]==first["private_original_archive"]["archive_original_sha256"]
    assert record["messages_sent"]==record["external_api_calls"]==0
    assert len(list(disk.glob("native_*_first.json")))==1
    assert calls==["research"]
    assert main(flags(rig))==0
    later=json.loads(capsys.readouterr().out)["native_first_capture"]
    again=later["private_original_archive"]["separate_volume_sha_witness"]
    assert again["status"]=="EXISTING_SEPARATE_VOLUME_NATIVE_SHA_REVERIFIED_NOT_ATTESTED"
    assert later["private_original_archive"]["archive_created"] is False
    assert later["private_original_archive"]["archive_original_sha256"]==witness["archive_sha256"]
    assert calls==["research","research"]


def test_scheduler_default_and_existing_private_archive_flag_have_no_outside_writes(
        rig,capsys):
    project,plan,root,disk,calls=rig
    assert main(["--project",str(project),
                 "--native-first-capture-plan",str(plan),
                 "--native-first-private-archive"])==0
    report=json.loads(capsys.readouterr().out)
    assert "separate_volume_sha_witness" not in report["native_first_capture"]["private_original_archive"]
    assert not disk.exists()


def test_witness_option_without_archive_refused_before_any_market_job(rig,capsys):
    project,plan,root,disk,calls=rig
    with pytest.raises(ValueError,match="private|archive"):
        main(["--project",str(project),
              "--native-first-capture-plan",str(plan),
              "--native-first-internal-witness-root",str(disk)])
    assert calls==[] and not disk.exists()
    assert not capsys.readouterr().out


def test_unsafe_same_ssd_location_is_rejected_before_job(rig,monkeypatch):
    project,plan,root,disk,calls=rig
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:False)
    with pytest.raises(ValueError,match="different filesystem"):
        main(flags(rig))
    assert calls==[] and not disk.exists() and not root.exists()


def test_missing_first_internal_guard_after_success_blocks_next_scheduler_run(rig,capsys):
    project,plan,root,disk,calls=rig
    main(flags(rig))
    capsys.readouterr()
    next(disk.glob("*_guard.json")).unlink()
    with pytest.raises(ValueError,match="Partial|missing|receipt"):
        main(flags(rig))
    assert not capsys.readouterr().out


def test_bad_internal_witness_prevents_success_after_completed_capture(rig,monkeypatch,capsys):
    project,plan,root,disk,calls=rig
    main(flags(rig))
    capsys.readouterr()
    first=next(disk.glob("*_first.json"))
    first.write_bytes(first.read_bytes()+b" ")
    with pytest.raises(ValueError,match="witness|canonical"):
        main(flags(rig))
    assert not capsys.readouterr().out


def test_no_plist_install_when_internal_witness_option_selected(rig,tmp_path):
    project,plan,root,disk,calls=rig
    plist=tmp_path/"prohibited.plist"
    with pytest.raises(ValueError,match="not supported"):
        main([*flags(rig),"--generate-plist",str(plist)])
    assert not plist.exists() and calls==[]


def test_primary_schedule_error_preserved_but_witness_still_created(
        rig,monkeypatch):
    project,plan,root,disk,calls=rig
    monkeypatch.setattr(local_schedule,"run_scheduled",
                        lambda **kw: (_ for _ in ()).throw(
                            ValueError("stale primary price-cache blocked")))
    with pytest.raises(ValueError,match="stale primary price-cache"):
        main(flags(rig))
    assert len(list(disk.glob("*_first.json")))==1


def test_multiple_plan_same_market_model_rejected_before_witness_first_write(rig,tmp_path):
    project,plan,root,disk,calls=rig
    alter=tmp_path/"alternate.json"
    obj=json.loads(plan.read_text())
    obj["cohort_id"]="AFTER_RANKING_RENAMED"
    alter.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="Duplicate pinned native model"):
        main([*flags(rig),"--native-first-capture-plan",str(alter)])
    assert not disk.exists()


def test_private_witness_cli_read_only_after_existing_first_receipt(rig,capsys):
    from scripts.verify_native_sha_witness import main as check
    project,plan,root,disk,calls=rig
    main(flags(rig))
    capsys.readouterr()
    assert check(["--project",str(project),
                  "--plan",str(plan),
                  "--capture-root",str(root),
                  "--witness-root",str(disk)])==0
    obj=json.loads(capsys.readouterr().out)
    assert obj["status"]=="SEPARATE_VOLUME_NATIVE_SHA_VERIFIED_NOT_ATTESTED"
    assert obj["messages_sent"]==0
    assert str(plan) not in json.dumps(obj)
