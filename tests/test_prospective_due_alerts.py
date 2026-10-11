"""6_5: local-only prospective due-evidence warning/outbox regression cases."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import fcntl
import importlib.util
import json
import sqlite3
import subprocess
import sys

import pytest

from eraleader import local_schedule, prospective_due_alerts
from eraleader.local_backup import verify_backup, restore_backup
from eraleader.prospective_census_seal import indexed_register_census, _index_path
from eraleader.prospective_due_alerts import (
    run_prospective_due_alerts,audit_due_alert_ledger,render_due_alerts,
)
from eraleader.prospective_due_followups import audit_prospective_due_followups
from eraleader.ranked_discovery import _frozen
from eraleader.prospective_census import _due
from eraleader.native_census_gate import register_native_census
from test_prospective_due_followups import create as make_cohort
from test_prospective_census import prepare,restore
from test_ranked_outcome_receipts import scenario,NOW,FROZEN
from test_native_census_gate import prepare as make_native,config as native_config
from test_native_topk_freeze import NOW as NATIVE_NOW
from test_scheduled_failure_outbox_bridge import load_script

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_due_alerts.py"


def setup(tmp_path,*,market="KR"):
    registry,saved,frozen,outcome,receipts=make_cohort(tmp_path/"proofs",market=market)
    project=tmp_path/"era-project"
    (project/"output").mkdir(parents=True)
    return project,registry,saved,frozen,outcome,receipts


def due(frozen):
    return _due(_frozen(frozen))


def monitor(project,registry,clock,config=None):
    return run_prospective_due_alerts(
        project,registry_dir=registry,native_config=config,clock=clock)


def out(project):
    return project/"output"/"prospective_due_alerts"


def checks(project,registry,config=None):
    return audit_due_alert_ledger(out(project),registry_dir=registry,
                                  native_config=config)


def alerts(project,registry,config=None):
    return [entry["warnings"] for entry in (
        json.loads(e["payload_json"]) for e in checks(project,registry,config)["events"])]


def test_first_pending_registers_only_local_zero_alert_baseline(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    at=FROZEN+timedelta(minutes=20)
    before=frozen.read_bytes()
    result=monitor(project,registry,at)
    assert result["status"]=="LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP"
    assert result["condition"]=="VERIFIED_LOCAL"
    assert result["new_warnings"]==0
    assert result["total_events"]==1
    assert result["last_verified_due_followups"]==0
    assert result["messages_sent"]==0 and result["external_api_calls"]==0
    assert result["official_leaders_confirmed"]==0
    assert result["actual_future_leader_skill_certified"] is False
    assert checks(project,registry)["last"]["delivery_status"]=="DRY_RUN_NEVER_SENT"
    assert frozen.read_bytes()==before


def test_maturity_boundary_emits_one_missing_evidence_warning_and_deduplicates(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    limit=due(frozen)
    monitor(project,registry,limit-timedelta(seconds=1))
    first=monitor(project,registry,limit)
    assert first["new_warnings"]==1
    assert first["last_verified_due_followups"]==1
    assert first["last_verified_unknown_k"]==3
    assert alerts(project,registry)[-1]==["PROSPECTIVE_DUE_EVIDENCE_GAP_LOCAL"]
    again=monitor(project,registry,limit+timedelta(days=4))
    assert again["new_warnings"]==0
    assert again["total_events"]==2
    assert len(alerts(project,registry))==2


def test_initial_run_already_due_warns_without_fake_failure(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    result=monitor(project,registry,due(frozen))
    assert result["new_warnings"]==1
    assert result["last_verified_due_followups"]==1
    data=json.loads((out(project)/"prospective_due_alerts_research.json").read_text())
    assert data["real_precision_at_k"] is None
    assert data["source_pit_independently_verified"] is False
    assert data["last_verified_unknown_k"]==3
    assert "실전 전송 0" in (out(project)/"site"/"index.html").read_text()


def test_partial_outcome_changes_state_even_if_same_gap_count(tmp_path):
    project,registry,saved,frozen,outcome,*_=setup(tmp_path)
    cutoff=due(frozen)
    monitor(project,registry,cutoff)
    outcome.write_bytes(saved[str(outcome)])
    result=monitor(project,registry,cutoff+timedelta(minutes=1))
    assert result["new_warnings"]==1
    assert result["last_verified_due_followups"]==1
    assert alerts(project,registry)[-1]==["PROSPECTIVE_DUE_EVIDENCE_CHANGED_LOCAL"]
    assert monitor(project,registry,cutoff+timedelta(minutes=2))["new_warnings"]==0


def test_censored_pair_is_not_considered_clear_or_success(tmp_path):
    project,registry,saved,frozen,*_=setup(tmp_path)
    cutoff=due(frozen)
    monitor(project,registry,cutoff)
    restore(saved)
    next_run=monitor(project,registry,cutoff+timedelta(days=3))
    assert next_run["last_verified_due_followups"]==1
    assert next_run["last_verified_unknown_k"]==1
    assert next_run["new_warnings"]==1
    assert "PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL" not in alerts(project,registry)[-1]


def test_full_paired_k2_moves_to_clear_but_never_certified(tmp_path):
    original=tmp_path/"original"
    frozen,outcome,receipt=scenario(original,k=2)
    contents={outcome:outcome.read_bytes(),receipt:receipt.read_bytes()}
    outcome.unlink();receipt.unlink()
    spec=frozen.parent/"census_input.json"
    spec.write_text(json.dumps([{
        "frozen":frozen.name,"definition":"leader_rule.json",
        "outcomes":outcome.name,"receipts":receipt.name,
    }]))
    registry=tmp_path/"reg"
    indexed_register_census(spec,registry,"census_2.json",
                            clock=FROZEN+timedelta(minutes=2))
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    monitor(project,registry,due(frozen))
    for file,raw in contents.items():file.write_bytes(raw)
    cleared=monitor(project,registry,NOW)
    assert cleared["condition"]=="VERIFIED_LOCAL"
    assert cleared["last_verified_due_followups"]==0
    assert cleared["last_verified_unknown_k"]==0
    assert alerts(project,registry)[-1]==["PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL"]
    assert cleared["official_leaders_confirmed"]==0
    assert monitor(project,registry,NOW+timedelta(hours=1))["new_warnings"]==0


def test_tampered_registry_causes_local_blocked_not_false_gap_clear(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    cutoff=due(frozen)
    first=monitor(project,registry,cutoff)
    file=registry/"census_first.json"
    raw=file.read_bytes()
    file.write_bytes(raw+b"\n")
    blocked=monitor(project,registry,cutoff+timedelta(hours=1))
    assert blocked["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert blocked["last_verified_due_followups"]==first["last_verified_due_followups"]
    assert blocked["new_warnings"]==1
    assert alerts(project,registry)[-1]==["PROSPECTIVE_SOURCE_AUDIT_BLOCKED_LOCAL"]
    assert monitor(project,registry,cutoff+timedelta(hours=2))["new_warnings"]==0
    file.write_bytes(raw)
    restored=monitor(project,registry,cutoff+timedelta(hours=3))
    assert restored["condition"]=="VERIFIED_LOCAL"
    assert alerts(project,registry)[-1]==["PROSPECTIVE_SOURCE_AUDIT_RESTORED_LOCAL"]


def test_receipt_index_deleted_never_replaces_last_trusted_k(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    cutoff=due(frozen)
    monitor(project,registry,cutoff)
    path=_index_path(registry)
    data=path.read_bytes()
    path.unlink()
    fail=monitor(project,registry,cutoff+timedelta(minutes=1))
    assert fail["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert fail["last_verified_due_followups"]==1
    assert fail["last_verified_unknown_k"]==3
    path.write_bytes(data)
    assert monitor(project,registry,cutoff+timedelta(minutes=2))["condition"]=="VERIFIED_LOCAL"


def test_valid_rewritten_smaller_index_and_registry_is_detected_by_old_receipt(tmp_path):
    spec1,*_=prepare(tmp_path/"kr")
    spec2,*_=prepare(tmp_path/"us",market="US")
    registry=tmp_path/"registry"
    indexed_register_census(spec1,registry,"census_kr.json",
                            clock=FROZEN+timedelta(minutes=2))
    index=_index_path(registry)
    previous_bytes=index.read_bytes()
    indexed_register_census(spec2,registry,"census_us.json",
                            clock=FROZEN+timedelta(minutes=3))
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    first=monitor(project,registry,NOW)
    assert checks(project,registry)["last"]["trusted_receipt_count"]==2
    (registry/"census_us.json").unlink()
    index.write_bytes(previous_bytes)  # both remaining files are self-consistent
    fail=monitor(project,registry,NOW+timedelta(minutes=2))
    assert fail["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert fail["new_warnings"]==1
    assert checks(project,registry)["last"]["trusted_receipt_count"]==2
    assert checks(project,registry)["last"]["trusted_receipt_head_sha256"]!=("0"*64)


def test_source_missing_on_first_observation_is_blocked_without_false_success(tmp_path):
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    registry=tmp_path/"missing_registry"
    result=monitor(project,registry,NOW)
    assert result["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert result["new_warnings"]==1
    assert result["last_verified_due_followups"]==0
    assert result["last_verified_unknown_k"]==0


def test_native_required_registry_cannot_downgrade_to_generic_audit(tmp_path):
    b,rule,frozen,source,item=make_native(tmp_path/"native")
    config=native_config(tmp_path/"native-proofs.json",[item])
    registry=tmp_path/"registry"
    register_native_census(source,registry,"census_native.json",
                           native_config=config,clock=NATIVE_NOW+timedelta(minutes=2))
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    skipped=monitor(project,registry,NATIVE_NOW+timedelta(minutes=4))
    assert skipped["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert skipped["new_warnings"]==1
    # A bound local source identity cannot silently change after first-write.
    with pytest.raises(ValueError,match="genesis|binding"):
        monitor(project,registry,NATIVE_NOW+timedelta(minutes=5),config=config)


def test_valid_native_first_score_index_stays_uncertified(tmp_path):
    b,rule,frozen,source,item=make_native(tmp_path/"native")
    config=native_config(tmp_path/"native-proofs.json",[item])
    registry=tmp_path/"registry"
    register_native_census(source,registry,"census_native.json",
                           native_config=config,clock=NATIVE_NOW+timedelta(minutes=2))
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    result=monitor(project,registry,NATIVE_NOW+timedelta(minutes=4),config=config)
    assert result["condition"]=="VERIFIED_LOCAL"
    assert result["last_verified_due_followups"]==0
    assert result["official_leaders_confirmed"]==0
    assert checks(project,registry,config)["last"]["trusted_receipt_count"]==1


def test_same_project_cannot_switch_to_different_registry(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen))
    registry2=tmp_path/"different"
    registry2.mkdir()
    with pytest.raises(ValueError,match="genesis|binding"):
        monitor(project,registry2,due(frozen)+timedelta(minutes=1))


def test_dry_run_alert_ledger_cannot_claim_delivery(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen))
    with sqlite3.connect(out(project)/"prospective_due_alerts.sqlite") as db:
        row=json.loads(db.execute("SELECT payload_json FROM alert_checks WHERE seq=1").fetchone()[0])
        row["messages_sent"]=1
        db.execute("UPDATE alert_checks SET payload_json=? WHERE seq=1",
                   (json.dumps(row,sort_keys=True),))
    with pytest.raises(ValueError,match="due-watch|delivered|claim"):
        monitor(project,registry,due(frozen)+timedelta(minutes=1))


def test_alert_genesis_missing_and_wipe_cannot_restart(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen))
    (out(project)/"prospective_due_alerts_genesis.json").unlink()
    with pytest.raises(ValueError,match="genesis|ledger"):
        monitor(project,registry,due(frozen)+timedelta(minutes=1))


def test_local_alert_genesis_mutation_halts_without_reset(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen))
    path=out(project)/"prospective_due_alerts_genesis.json"
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError,match="marker|genesis|metadata"):
        monitor(project,registry,due(frozen)+timedelta(minutes=1))


def test_local_alert_clock_regression_is_refused(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen)+timedelta(minutes=5))
    with pytest.raises(ValueError,match="backdated"):
        monitor(project,registry,due(frozen))


def test_alert_symlink_artifact_path_refused(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    directory=project/"output"/"prospective_due_alerts"
    outside=tmp_path/"unrelated";outside.mkdir()
    directory.symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match="Unsafe"):
        monitor(project,registry,due(frozen))
    assert not list(outside.iterdir())


def test_concurrent_dry_run_lock_is_not_success(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    control=project/"output"/"prospective_due_alerts_control"
    control.mkdir()
    file=(control/"batch.lock").open("a+b")
    try:
        fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=monitor(project,registry,due(frozen))
        assert result["status"]=="SKIPPED_ALREADY_RUNNING"
        assert not out(project).exists()
    finally:
        fcntl.flock(file,fcntl.LOCK_UN)
        file.close()


def test_backup_zip_4_sanitized_outputs_restored_and_verified(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    first=monitor(project,registry,due(frozen))
    archive=Path(first["archive"])
    assert verify_backup(archive)["file_count"]==4
    location=tmp_path/"restored"
    assert restore_backup(archive,location)["status"]=="LOCAL_BACKUP_RESTORED"
    saved=audit_due_alert_ledger(location,registry_dir=registry)
    assert saved["total_checks"]==1
    assert sha256((out(project)/"prospective_due_alerts_research.json").read_bytes()).hexdigest()==(
        sha256((location/"prospective_due_alerts_research.json").read_bytes()).hexdigest())
    assert "source_dir" not in (location/"prospective_due_alerts_research.json").read_text()
    assert "SYN-A" not in (location/"site"/"index.html").read_text()


def test_renderer_rejects_fake_certification_or_message(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    monitor(project,registry,due(frozen))
    payload=json.loads((out(project)/"prospective_due_alerts_research.json").read_text())
    for key,value in (
        ("official_leader_promotions",1),("real_precision_at_k",0.5),
        ("messages_sent",1),("external_api_calls",1),
        ("source_pit_independently_verified",True),
    ):
        changed=deepcopy(payload);changed[key]=value
        with pytest.raises(ValueError,match="Unsafe"):
            render_due_alerts(changed)


def test_cli_standalone_subprocess_runs_actual_synthetic_project(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    cmd=[sys.executable,str(SCRIPT),"--project",str(project),
         "--registry-dir",str(registry)]
    completed=subprocess.run(cmd,capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr
    result=json.loads(completed.stdout)
    assert result["status"]=="LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP"
    assert result["messages_sent"]==0
    assert (out(project)/"site"/"index.html").exists()


def test_source_regained_after_failed_first_observation_is_local_only(tmp_path):
    project=tmp_path/"project";(project/"output").mkdir(parents=True)
    registry=tmp_path/"registry"
    missing=monitor(project,registry,NOW)
    assert missing["condition"]=="SOURCE_AUDIT_BLOCKED"
    spec,saved,frozen,*_=prepare(tmp_path/"sources")
    indexed_register_census(spec,registry,"census_first.json",
                            clock=FROZEN+timedelta(minutes=2))
    recovered=monitor(project,registry,NOW+timedelta(minutes=1))
    assert recovered["condition"]=="VERIFIED_LOCAL"
    assert "PROSPECTIVE_SOURCE_AUDIT_RESTORED_LOCAL" in alerts(project,registry)[-1]
    assert recovered["official_leaders_confirmed"]==0


@pytest.mark.parametrize("invalid",[
    {"status":"SKIPPED_ALREADY_RUNNING","messages_sent":0},
    {"status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP","messages_sent":1},
    {"status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP","messages_sent":0,
     "external_api_calls":0,"official_leaders_confirmed":1,
     "actual_future_leader_skill_certified":False,"local_artifacts_only":True},
])
def test_scheduler_rejects_skipped_sent_or_fake_certified_due_monitor(
        tmp_path,monkeypatch,invalid,capsys):
    project=tmp_path/"project";project.mkdir()
    monkeypatch.setattr(local_schedule,"run_scheduled",
                        lambda **kw:{"status":"SKIPPED_STALE_CACHE","messages_sent":0})
    monkeypatch.setattr(prospective_due_alerts,"run_prospective_due_alerts",
                        lambda *a,**kw:invalid)
    with pytest.raises(RuntimeError,match="Prospective due dry-run verification"):
        load_script().main(["--project",str(project),
                            "--prospective-due-registry",str(tmp_path/"reg")])
    assert not capsys.readouterr().out


def test_scheduler_optin_and_unflagged_both_preserve_original_behavior(tmp_path,monkeypatch,capsys):
    project=tmp_path/"project";project.mkdir()
    calls=[]
    def job(**kw):
        calls.append("schedule")
        return {"status":"SKIPPED_STALE_CACHE","messages_sent":0,"external_api_calls":0}
    def observer(root,*,registry_dir,native_config=None):
        calls.append("due")
        assert root==project
        assert registry_dir==tmp_path/"registry"
        assert native_config is None
        return {"status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP",
                "messages_sent":0,"external_api_calls":0,
                "official_leaders_confirmed":0,
                "actual_future_leader_skill_certified":False,"local_artifacts_only":True}
    monkeypatch.setattr(local_schedule,"run_scheduled",job)
    monkeypatch.setattr(prospective_due_alerts,"run_prospective_due_alerts",observer)
    assert load_script().main(["--project",str(project)])==0
    assert calls==["schedule"]
    capsys.readouterr()
    assert load_script().main(["--project",str(project),
                               "--prospective-due-registry",str(tmp_path/"registry")])==0
    assert calls==["schedule","schedule","due"]
    response=json.loads(capsys.readouterr().out)
    assert response["prospective_due_alerts"]["messages_sent"]==0
    assert response["schedule"]["status"]=="SKIPPED_STALE_CACHE"


def test_scheduler_failure_still_checks_due_without_masking_original(tmp_path,monkeypatch):
    project=tmp_path/"project";project.mkdir()
    calls=[]
    def fails(**kw):
        calls.append("schedule_error")
        raise ValueError("stale price denied")
    def observer(*a,**kw):
        calls.append("due_checked")
        return {"status":"LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP"}
    monkeypatch.setattr(local_schedule,"run_scheduled",fails)
    monkeypatch.setattr(prospective_due_alerts,"run_prospective_due_alerts",observer)
    with pytest.raises(ValueError,match="stale price denied"):
        load_script().main(["--project",str(project),
                            "--prospective-due-registry",str(tmp_path/"registry")])
    assert calls==["schedule_error","due_checked"]


def test_no_launchagent_generated_for_new_optin(tmp_path):
    project=tmp_path/"project";project.mkdir()
    plist=tmp_path/"agent.plist"
    with pytest.raises(ValueError,match="not supported with --generate-plist"):
        load_script().main(["--project",str(project),
                            "--prospective-due-registry",str(tmp_path/"registry"),
                            "--generate-plist",str(plist)])
    assert not plist.exists()


def test_native_flag_without_registry_rejected(tmp_path):
    project=tmp_path/"project";project.mkdir()
    with pytest.raises(ValueError,match="Native due evidence"):
        load_script().main(["--project",str(project),
                            "--prospective-due-native-config",str(tmp_path/"a.json")])


def test_source_invalid_label_claim_stays_blocked_not_known_negative(tmp_path):
    project,registry,saved,frozen,outcome,receipt=setup(tmp_path)
    cutoff=due(frozen)
    monitor(project,registry,cutoff)
    restore(saved)
    raw=json.loads(receipt.read_text())
    raw["outcomes_sha256"]="f"*64
    receipt.write_text(json.dumps(raw))
    result=monitor(project,registry,cutoff+timedelta(hours=1))
    assert result["condition"]=="SOURCE_AUDIT_BLOCKED"
    assert result["last_verified_due_followups"]==1
    assert result["last_verified_unknown_k"]==3


def test_new_index_entry_pins_prefix_even_without_new_due_warning(tmp_path):
    project,registry,_,frozen,*_=setup(tmp_path)
    one=monitor(project,registry,FROZEN+timedelta(minutes=10))
    assert one["new_warnings"]==0
    spec2,*_=prepare(tmp_path/"us",market="US")
    indexed_register_census(spec2,registry,"census_US.json",
                            clock=FROZEN+timedelta(minutes=11))
    later=monitor(project,registry,FROZEN+timedelta(minutes=12))
    assert later["new_warnings"]==0
    assert later["total_events"]==2
    assert checks(project,registry)["last"]["trusted_receipt_count"]==2
