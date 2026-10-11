"""6_5 SHA/quality downgrade local-only alerts; synthetic claimed inputs."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import sqlite3

import pytest

from eraleader.local_backup import restore_backup, verify_backup
from eraleader.provider_quality_history import record_quality_snapshot
from eraleader.provider_quality_watchdog import (
    run_provider_quality_watchdog, audit_quality_watchdog,
    render_quality_watchdog, SCHEMA,
)
from test_provider_gate_quality_view import case_with_lineage
from test_provider_quality_history import changed, CLOCK
from test_scheduled_failure_outbox_bridge import load_script
from eraleader import local_schedule
from eraleader import provider_quality_watchdog


def sample(tmp_path,market="KR"):
    _,_,gate=case_with_lineage(tmp_path/"feeds",market)
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    return project,gate


def history(project):
    return project/"output"


def outbox(project):
    return project/"output"/"provider_quality_alerts"


def checks(project):
    return audit_quality_watchdog(outbox(project))["checks"]


def report(project):
    return json.loads((outbox(project)/"provider_quality_alerts_research.json").read_text())


def run(project,minute=0):
    return run_provider_quality_watchdog(project,clock=CLOCK+timedelta(minutes=minute))


def test_no_history_is_unconfigured_not_false_provider_failure(tmp_path):
    project=tmp_path/"project"
    (project/"output").mkdir(parents=True)
    first=run(project)
    assert first["status"]=="LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP"
    assert first["condition"]=="NOT_CONFIGURED"
    assert first["new_warnings"]==0
    assert first["messages_sent"]==0 and first["external_api_calls"]==0
    assert first["official_leaders_confirmed"]==0
    assert first["actual_future_leader_skill_certified"] is False
    assert verify_backup(Path(first["archive"]))["file_count"]==4
    second=run(project,1)
    assert second["checks_recorded"]==1 and second["new_warnings"]==0
    assert checks(project)[0]["delivery_status"]=="DRY_RUN_NEVER_SENT"
    assert not (history(project)/"provider_quality_history.sqlite").exists()


@pytest.mark.parametrize("market",["KR","US"])
def test_verified_history_baseline_idempotent_no_source_mutation(tmp_path,market):
    project,gate=sample(tmp_path,market)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    original=(history(project)/"provider_quality_history.sqlite").read_bytes()
    one=run(project)
    assert one["condition"]=="VERIFIED"
    assert one["new_warnings"]==0
    assert one["checks_recorded"]==1
    two=run(project,1)
    assert two["checks_recorded"]==1 and two["new_warnings"]==0
    assert (history(project)/"provider_quality_history.sqlite").read_bytes()==original
    assert report(project)["history_event_count_last_verified"]==1
    assert "실전 전송 0" in (outbox(project)/"site"/"index.html").read_text()


def test_evidence_downgrade_is_one_dry_run_warning(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    weak=changed(gate,decision="2026-10-12T10:30:00+09:00",permitted=True,strict=False)
    record_quality_snapshot(history(project),weak,clock=CLOCK+timedelta(hours=1))
    first=run(project,60)
    assert first["new_weakened"]==1 and first["new_blocked"]==0
    assert first["new_warnings"]==1
    assert json.loads(checks(project)[-1]["alerts_json"])==[
        "QUALITY_EVIDENCE_WEAKENED_LOCAL"]
    assert run(project,61)["new_warnings"]==0
    assert len(checks(project))==2


def test_allowed_to_blocked_warning_and_later_reopen_not_official(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    blocked=changed(gate,decision="2026-10-12T11:00:00+09:00")
    record_quality_snapshot(history(project),blocked,clock=CLOCK+timedelta(hours=2))
    result=run(project,120)
    assert result["new_blocked"]==1
    assert "WATCH_GATE_BLOCKED_LOCAL" in json.loads(checks(project)[-1]["alerts_json"])
    reopened=changed(gate,decision="2026-10-12T12:00:00+09:00",permitted=True)
    record_quality_snapshot(history(project),reopened,clock=CLOCK+timedelta(hours=3))
    good=run(project,180)
    assert good["condition"]=="VERIFIED" and good["new_warnings"]==0
    assert report(project)["official_leader_promotions"]==0
    assert report(project)["actual_future_leader_precision"] is None


def test_changed_blocker_on_already_blocked_watch_is_new_local_warning(tmp_path):
    project,gate=sample(tmp_path)
    first=changed(gate,decision="2026-10-12T10:00:00+09:00")
    record_quality_snapshot(history(project),first,clock=CLOCK)
    run(project)
    different=changed(gate,decision="2026-10-12T11:00:00+09:00",
                      reason="ISSUER_CLASS_CANDIDATE_ISSUER_MISMATCH")
    record_quality_snapshot(history(project),different,
                            clock=CLOCK+timedelta(hours=2))
    assert run(project,120)["new_blocked"]==1
    assert run(project,121)["new_warnings"]==0


def test_same_decision_revised_to_blocked_is_alert_not_masked(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    change=changed(gate,decision=gate["decision_at_utc"])
    record_quality_snapshot(history(project),change,clock=CLOCK+timedelta(minutes=1))
    result=run(project,1)
    assert result["new_blocked"]==1


def test_first_registration_already_blocked_is_warning(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),changed(gate,permitted=False),
                            clock=CLOCK)
    result=run(project)
    assert result["new_blocked"]==1
    assert result["new_warnings"]==1


def test_unsupervised_intermediate_quality_drop_is_not_skipped(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    weak=changed(gate,decision="2026-10-12T10:30:00+09:00",permitted=True,strict=False)
    record_quality_snapshot(history(project),weak,clock=CLOCK+timedelta(hours=1))
    strong=changed(gate,decision="2026-10-12T11:30:00+09:00",permitted=True)
    record_quality_snapshot(history(project),strong,clock=CLOCK+timedelta(hours=2))
    result=run(project,120)
    assert result["new_weakened"]==1
    assert result["new_warnings"]==1


def test_sqlite_history_sha_tampering_alerts_without_repairing_source(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    path=history(project)/"provider_quality_history.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE quality_events SET payload_json='{}' WHERE event_no=1")
    altered=path.read_bytes()
    result=run(project,1)
    assert result["condition"]=="INTEGRITY_ANOMALY"
    assert result["new_warnings"]==1
    assert json.loads(checks(project)[-1]["alerts_json"])==[
        "LOCAL_HISTORY_SHA_INTEGRITY_ANOMALY"]
    assert path.read_bytes()==altered
    assert run(project,2)["new_warnings"]==0


def test_detect_self_consistent_history_rollback_against_independent_checkpoint(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    path=history(project)/"provider_quality_history.sqlite"
    prior=path.read_bytes()
    run(project)
    changed_gate=changed(gate,decision="2026-10-12T10:30:00+09:00")
    record_quality_snapshot(history(project),changed_gate,
                            clock=CLOCK+timedelta(hours=1))
    assert run(project,60)["checks_recorded"]==2
    path.write_bytes(prior)  # locally self-consistent count=1 but checkpoint had count=2
    result=run(project,61)
    assert result["condition"]=="INTEGRITY_ANOMALY"
    assert result["new_warnings"]==1
    assert checks(project)[-1]["trusted_event_count"]==2


@pytest.mark.parametrize("part",["db","seal","both"])
def test_quality_ledger_partial_or_total_deletion_after_observation_alerts(tmp_path,part):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    names={
        "db":"provider_quality_history.sqlite",
        "seal":"provider_quality_history_genesis.json",
    }
    for which in (("db","seal") if part=="both" else (part,)):
        (history(project)/names[which]).unlink()
    result=run(project,1)
    assert result["condition"]=="INTEGRITY_ANOMALY"
    assert result["new_warnings"]==1
    assert run(project,2)["new_warnings"]==0
    for which in (("db","seal") if part=="both" else (part,)):
        assert not (history(project)/names[which]).exists()


def test_marker_bytes_tamper_detected_and_source_never_rewritten(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    path=history(project)/"provider_quality_history_genesis.json"
    original=path.read_bytes()
    path.write_bytes(original+b"\n")
    assert run(project,1)["condition"]=="INTEGRITY_ANOMALY"
    assert path.read_bytes()==original+b"\n"


def test_source_recovery_only_local_not_market_certification(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    path=history(project)/"provider_quality_history.sqlite"
    original=path.read_bytes()
    run(project)
    path.write_bytes(b"broken bytes")
    assert run(project,1)["condition"]=="INTEGRITY_ANOMALY"
    path.write_bytes(original)
    result=run(project,2)
    assert result["condition"]=="VERIFIED"
    assert "LOCAL_HISTORY_RESTORED" in json.loads(checks(project)[-1]["alerts_json"])
    assert report(project)["local_chain_not_independent_attestation"] is True


def test_source_symlink_is_safely_classified_anomaly_not_read(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    original=history(project)/"provider_quality_history.sqlite"
    actual=tmp_path/"outside.sqlite"
    actual.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(actual)
    assert run(project,1)["condition"]=="INTEGRITY_ANOMALY"
    assert actual.is_file()


def test_tampered_watchdog_outbox_cannot_claim_success(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    with sqlite3.connect(outbox(project)/"provider_quality_watchdog.sqlite") as db:
        db.execute("UPDATE watchdog_checks SET messages_sent=1 WHERE check_no=1")
    with pytest.raises(ValueError,match="watchdog|Tampered|chain"):
        run(project,1)


def test_deleted_watchdog_genesis_refuses_reset(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    (outbox(project)/"provider_quality_watchdog_genesis.json").unlink()
    with pytest.raises(ValueError,match="Missing watchdog"):
        run(project,1)


def test_no_retroactive_runtime_after_backdated_clock(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project,1)
    with pytest.raises(ValueError,match="backdated"):
        run(project,0)


def test_derived_zip_sha_and_new_directory_restore(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    result=run(project)
    archive=Path(result["archive"])
    assert verify_backup(archive)["file_count"]==4
    target=tmp_path/"new-location"
    assert restore_backup(archive,target)["status"]=="LOCAL_BACKUP_RESTORED"
    assert audit_quality_watchdog(target)["checks"]==checks(project)
    assert (target/"provider_quality_alerts_research.json").read_bytes()==(
        outbox(project)/"provider_quality_alerts_research.json").read_bytes()


def test_renderer_rejects_fake_delivery_or_success(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    result=report(project)
    for key,value in (("messages_sent",1),("external_api_calls",1),
                      ("official_leader_promotions",1),
                      ("actual_future_leader_precision",0.92)):
        forged=deepcopy(result)
        forged[key]=value
        with pytest.raises(ValueError,match="Unsafe"):
            render_quality_watchdog(forged)


def test_stale_source_evidence_does_not_modify_provider_or_watch_runs(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    before={p.name:sha256(p.read_bytes()).hexdigest() for p in history(project).glob(
        "provider_quality_history*.json")}
    one=run(project)
    two=run(project,1)
    assert one["condition"]=="VERIFIED" and two["new_warnings"]==0
    assert before=={p.name:sha256(p.read_bytes()).hexdigest() for p in
                   history(project).glob("provider_quality_history*.json")}
    assert not (history(project)/"prospective.sqlite").exists()


def test_scheduler_optin_quality_bridge_and_default_unchanged(tmp_path,monkeypatch,capsys):
    project=tmp_path/"project";project.mkdir()
    calls=[]
    def job(**kwargs):
        calls.append("schedule")
        return {"status":"SKIPPED_STALE_CACHE","messages_sent":0,"external_api_calls":0}
    def monitor(project):
        calls.append("quality")
        return {"status":"LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP",
                "messages_sent":0,"external_api_calls":0,
                "official_leaders_confirmed":0,
                "actual_future_leader_skill_certified":False,"local_artifacts_only":True}
    monkeypatch.setattr(local_schedule,"run_scheduled",job)
    monkeypatch.setattr(provider_quality_watchdog,"run_provider_quality_watchdog",monitor)
    assert load_script().main(["--project",str(project)])==0
    assert calls==["schedule"]
    capsys.readouterr()
    assert load_script().main(["--project",str(project),
                               "--provider-quality-dry-run"])==0
    data=json.loads(capsys.readouterr().out)
    assert calls==["schedule","schedule","quality"]
    assert data["provider_quality_watchdog"]["messages_sent"]==0


def test_scheduler_failure_still_monitors_but_preserves_failure(tmp_path,monkeypatch):
    project=tmp_path/"project";project.mkdir()
    calls=[]
    def fails(**kwargs):
        calls.append("failure")
        raise RuntimeError("stale price refused")
    def monitor(project):
        calls.append("quality")
        return {"status":"LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP"}
    monkeypatch.setattr(local_schedule,"run_scheduled",fails)
    monkeypatch.setattr(provider_quality_watchdog,"run_provider_quality_watchdog",monitor)
    with pytest.raises(RuntimeError,match="stale price refused"):
        load_script().main(["--project",str(project),"--provider-quality-dry-run"])
    assert calls==["failure","quality"]


def test_scheduler_rejects_skipped_or_sent_monitor(tmp_path,monkeypatch,capsys):
    project=tmp_path/"project";project.mkdir()
    monkeypatch.setattr(local_schedule,"run_scheduled",
        lambda **kwargs:{"status":"SKIPPED_STALE_CACHE","messages_sent":0})
    monkeypatch.setattr(provider_quality_watchdog,"run_provider_quality_watchdog",
        lambda root:{"status":"SKIPPED_ALREADY_RUNNING","messages_sent":1})
    with pytest.raises(RuntimeError,match="quality dry-run verification"):
        load_script().main(["--project",str(project),"--provider-quality-dry-run"])
    assert not capsys.readouterr().out


def test_future_local_receipt_cannot_be_accepted_as_present_evidence(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK+timedelta(hours=1))
    result=run(project,0)
    assert result["condition"]=="INTEGRITY_ANOMALY"
    assert result["new_warnings"]==1
    assert checks(project)[-1]["trusted_event_count"]==0
    later=run(project,60)
    assert later["condition"]=="VERIFIED"
    assert later["new_warnings"]==0  # no earlier trustworthy source to restore
    assert checks(project)[-1]["trusted_event_count"]==1


def test_both_source_files_recreated_validly_still_detected_by_watchdog(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    (history(project)/"provider_quality_history.sqlite").unlink()
    (history(project)/"provider_quality_history_genesis.json").unlink()
    record_quality_snapshot(history(project),gate,clock=CLOCK+timedelta(minutes=1))
    result=run(project,2)
    assert result["condition"]=="INTEGRITY_ANOMALY"
    assert checks(project)[-1]["trusted_event_count"]==1


def test_tampered_watchdog_marker_fails_closed(tmp_path):
    project,gate=sample(tmp_path)
    record_quality_snapshot(history(project),gate,clock=CLOCK)
    run(project)
    marker=outbox(project)/"provider_quality_watchdog_genesis.json"
    marker.write_bytes(marker.read_bytes()+b" ")
    with pytest.raises(ValueError,match="genesis|marker|meta"):
        run(project,1)


def test_multi_market_global_chain_quality_alerts(tmp_path):
    project,kr=sample(tmp_path,"KR")
    _,_,us=case_with_lineage(tmp_path/"feeds_us","US")
    record_quality_snapshot(history(project),kr,clock=CLOCK)
    record_quality_snapshot(history(project),us,clock=CLOCK+timedelta(minutes=1))
    run(project,1)
    weak_kr=changed(kr,decision="2026-10-12T10:30:00+09:00",
                    permitted=True,strict=False)
    record_quality_snapshot(history(project),weak_kr,
                            clock=CLOCK+timedelta(hours=1))
    assert run(project,60)["new_weakened"]==1
    assert checks(project)[-1]["trusted_event_count"]==3


def test_quality_dry_run_cannot_generate_live_plist(tmp_path):
    project=tmp_path/"project";project.mkdir()
    with pytest.raises(ValueError,match="not supported with"):
        load_script().main(["--project",str(project),
                            "--provider-quality-dry-run",
                            "--generate-plist",str(tmp_path/"agent.plist")])
    assert not (tmp_path/"agent.plist").exists()
