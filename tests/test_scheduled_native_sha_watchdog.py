"""6_5 SHA-only multi-cohort DRY-RUN opt-in scheduled bridge."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import json
import pytest

from eraleader import local_schedule, native_sha_witness, native_sha_watchdog
from eraleader.native_first_capture import capture_first_native_topk
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from scripts.run_local_scheduled import main
from test_scheduled_native_archive import setup, NOW


@pytest.fixture
def rig(tmp_path, monkeypatch):
    project, bundle, plan, root = setup(tmp_path)
    external = tmp_path/"mac_os_sha_witness"
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:True)
    first = capture_first_native_topk(plan,root,clock=NOW)
    sealed = archive_captured_native_plan(project,plan,root,first,clock=NOW)
    record_native_sha_witness(project,plan,root,sealed,external,clock=NOW)
    monkeypatch.setattr(native_sha_watchdog,"_clock",lambda dt:NOW+timedelta(minutes=6))
    seen = []
    def fake_job(**kwargs):
        seen.append(True)
        return {"status":"LOCAL_SYNTHETIC_SCHEDULE", "messages_sent":0, "external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",fake_job)
    return project,plan,external,seen


def options(rig):
    project,plan,witness,seen=rig
    return ["--project",str(project),
            "--native-sha-dry-run-plan",str(plan),
            "--native-sha-dry-run-witness-root",str(witness)]


def test_opt_in_scheduled_monitor_exposes_unsent_dashboard_in_native_web(rig,capsys):
    project,plan,witness,seen=rig
    site=project/"output"/"site"
    site.mkdir()
    (site/"index.html").write_text("<html><body>EraLeader</body></html>")
    assert main(options(rig))==0
    outcome=json.loads(capsys.readouterr().out)
    audit=outcome["native_sha_watchdog"]
    assert audit["status"]=="LOCAL_NATIVE_SHA_DRY_RUN_RECORDED"
    assert not audit["new_alerts"]
    assert outcome["messages_sent"]==outcome["external_api_calls"]==0
    assert len(seen)==1
    assert (site/"native_sha_dry_run.html").exists()
    assert "native_sha_dry_run.html" in (site/"index.html").read_text()
    assert str(plan) not in (site/"native_sha_dry_run.html").read_text()
    assert main(options(rig))==0
    later=json.loads(capsys.readouterr().out)
    assert later["native_sha_watchdog"]["check_count"]==2
    assert later["native_sha_watchdog"]["new_alerts"]==[]
    assert (site/"index.html").read_text().count("native_sha_dry_run.html")==1


def test_missing_sha_reported_without_starting_capture_again(rig,capsys):
    project,plan,witness,seen=rig
    next(witness.glob("*_guard.json")).unlink()
    assert main(options(rig))==0
    audit=json.loads(capsys.readouterr().out)["native_sha_watchdog"]
    assert len(audit["new_alerts"])==1
    assert next(iter(audit["cohorts"].values()))["state"]=="ANOMALY"
    assert len(seen)==1
    assert not (project/"output"/"native_sha_alerts"/"report.json").is_symlink()


@pytest.mark.parametrize("missing",["plan","witness"])
def test_monitor_flags_reject_unpaired_without_running_research(rig,missing):
    project,plan,witness,seen=rig
    flags=["--project",str(project)]
    if missing=="plan":
        flags+=["--native-sha-dry-run-witness-root",str(witness)]
    else:
        flags+=["--native-sha-dry-run-plan",str(plan)]
    with pytest.raises(ValueError,match="BOTH"):
        main(flags)
    assert seen==[]


def test_plist_rejects_monitor_flags_without_installation(rig,tmp_path):
    project,plan,witness,seen=rig
    path=tmp_path/"never-installed.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(options(rig)+["--generate-plist",str(path)])
    assert not path.exists() and seen==[]


def test_invalid_witness_filesystem_rejected_before_job(rig,monkeypatch):
    project,plan,witness,seen=rig
    monkeypatch.setattr(native_sha_witness,"_separate_device",lambda a,b:False)
    with pytest.raises(ValueError,match="different filesystem"):
        main(options(rig))
    assert seen==[]


def test_scheduler_failure_does_not_hide_primary_and_audits_separate_sha(rig,monkeypatch):
    project,plan,witness,seen=rig
    def failed_job(**kwargs):
        seen.append(True)
        raise ValueError("old_stale_cache_block")
    monkeypatch.setattr(local_schedule,"run_scheduled",failed_job)
    with pytest.raises(ValueError,match="old_stale_cache_block"):
        main(options(rig))
    report=project/"output"/"native_sha_alerts"/"report.json"
    assert report.exists()
    assert json.loads(report.read_text())["messages_sent"]==0
    assert len(seen)==1
