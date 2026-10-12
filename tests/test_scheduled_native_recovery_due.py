"""Opt-in key-free recovery drill due scheduler integration, no live delivery."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import json

import pytest

from eraleader import local_schedule, native_recovery_due
from scripts.run_local_scheduled import main
from test_native_encrypted_vault import rig
from test_native_recovery_due import prepared, do
from test_scheduled_native_archive import NOW


@pytest.fixture
def schedule_case(prepared, monkeypatch):
    evidence, first, scratch = prepared
    ran=[]
    def regular(**kwargs):
        ran.append("ordinary_market_research")
        return {"status":"SYNTHETIC_RESEARCH_ONLY",
                "external_api_calls":0,"messages_sent":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",regular)
    monkeypatch.setattr(native_recovery_due,"_now",
                        lambda at:NOW+timedelta(days=1))
    return prepared,ran


def options(schedule_case):
    prepared,ran=schedule_case
    evidence, first, scratch=prepared
    return [
        "--project",str(evidence["project"]),
        "--native-encrypted-watch-slot",first["slot"],
        "--native-encrypted-watch-vault-root",str(evidence["vault"]),
        "--native-encrypted-watch-witness-root",str(evidence["witness"]),
        "--native-encrypted-watch-cert",str(evidence["cert"]),
        "--native-recovery-due",
        "--native-recovery-due-scratch-root",str(scratch),
    ]


def test_explicit_scheduler_reads_original_drill_shas_without_key(schedule_case,capsys):
    prepared,ran=schedule_case
    do(prepared)
    assert main(options(schedule_case)) == 0
    report=json.loads(capsys.readouterr().out)
    due=report["native_recovery_due"]
    assert due["status"]=="LOCAL_NATIVE_RECOVERY_DUE_DRY_RUN_RECORDED"
    assert list(due["cohorts"].values())[0]["state"]=="HEALTHY"
    assert not due["new_alerts"]
    assert report["messages_sent"]==report["external_api_calls"]==0
    assert ran==["ordinary_market_research"]
    scratch=prepared[2]
    assert not list(scratch.iterdir())
    assert main(options(schedule_case))==0
    another=json.loads(capsys.readouterr().out)
    assert another["native_recovery_due"]["check_count"]==2
    assert not another["native_recovery_due"]["new_alerts"]


def test_first_never_drilled_is_local_once_only_warning(schedule_case,capsys):
    prepared,ran=schedule_case
    assert main(options(schedule_case))==0
    first=json.loads(capsys.readouterr().out)
    assert list(first["native_recovery_due"]["cohorts"].values())[0]["state"]=="NEVER_TESTED"
    assert len(first["native_recovery_due"]["new_alerts"])==1
    assert main(options(schedule_case))==0
    later=json.loads(capsys.readouterr().out)["native_recovery_due"]
    assert later["new_alerts"]==[]
    assert ran==["ordinary_market_research"]*2


def test_scheduler_stale_failure_preserved_and_due_audit_still_written(schedule_case,monkeypatch):
    prepared,ran=schedule_case
    do(prepared)
    def stale(**kwargs):
        ran.append("stale")
        raise ValueError("EXISTING_STALE_CACHE_FAILURE")
    monkeypatch.setattr(local_schedule,"run_scheduled",stale)
    with pytest.raises(ValueError,match="EXISTING_STALE_CACHE_FAILURE"):
        main(options(schedule_case))
    report=prepared[0]["project"]/"output"/"native_recovery_due_alerts"/"report.json"
    assert report.is_file()
    assert json.loads(report.read_bytes())["messages_sent"]==0
    assert ran==["stale"]


@pytest.mark.parametrize("missing",["due","scratch","encrypted_slot","vault","witness","cert"])
def test_incomplete_due_opt_in_is_rejected_before_research(schedule_case, missing):
    prepared,ran=schedule_case
    args=options(schedule_case)
    lookup={
        "due":"--native-recovery-due",
        "scratch":"--native-recovery-due-scratch-root",
        "encrypted_slot":"--native-encrypted-watch-slot",
        "vault":"--native-encrypted-watch-vault-root",
        "witness":"--native-encrypted-watch-witness-root",
        "cert":"--native-encrypted-watch-cert",
    }
    target=lookup[missing]
    i=args.index(target)
    del args[i:i+(1 if missing=="due" else 2)]
    with pytest.raises(ValueError,match="require|needs|DRY-RUN"):
        main(args)
    assert ran==[]
    assert not (prepared[0]["project"]/"output"/"native_recovery_due_alerts").exists()


@pytest.mark.parametrize("invalid",["due_zero","warn_not_below","negative_warn"])
def test_bad_due_cadence_rejected_without_market_job(schedule_case,invalid):
    prepared,ran=schedule_case
    args=options(schedule_case)
    if invalid=="due_zero":
        args+=["--native-recovery-due-days","0"]
    if invalid=="warn_not_below":
        args+=["--native-recovery-due-days","7"]
    if invalid=="negative_warn":
        args+=["--native-recovery-due-warn-days","-1"]
    with pytest.raises(ValueError,match="policy"):
        main(args)
    assert ran==[]


def test_generate_plist_does_not_install_due_drill_monitor(schedule_case,tmp_path):
    prepared,ran=schedule_case
    target=tmp_path/"NOT_INSTALLED.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(options(schedule_case)+["--generate-plist",str(target)])
    assert not target.exists() and ran==[]


def test_default_scheduler_unchanged_without_due_opt_in(schedule_case,capsys):
    prepared,ran=schedule_case
    assert main(["--project",str(prepared[0]["project"])]) == 0
    raw=json.loads(capsys.readouterr().out)
    assert raw["status"]=="SYNTHETIC_RESEARCH_ONLY"
    assert ran==["ordinary_market_research"]
    assert not (prepared[0]["project"]/"output"/"native_recovery_due_alerts").exists()


def test_private_key_never_needed_or_auto_decrypt_scheduled(schedule_case,monkeypatch,capsys):
    prepared,ran=schedule_case
    do(prepared)
    evidence,_,_=prepared
    evidence["key"].unlink()
    from eraleader import native_encrypted_vault
    def never_decrypt(*a,**k):
        raise AssertionError("Key-free due observer must NEVER perform recovery")
    monkeypatch.setattr(native_encrypted_vault,"restore_encrypted_native_original",never_decrypt)
    assert main(options(schedule_case))==0
    report=json.loads(capsys.readouterr().out)
    assert "native_recovery_due" in report
    assert report["messages_sent"]==0
