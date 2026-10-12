"""6_5 opt-in scheduled local RSA X509 recovery key/expiry readiness only."""
from __future__ import annotations

import json
import pytest

from eraleader import local_schedule
from scripts.run_local_scheduled import main
from test_scheduled_native_encrypted_watchdog import rig, args
from test_native_encrypted_watchdog import rig as prepared, create


def flags(rig, key=True):
    setup,jobs = rig
    opts = args(rig, slots=setup["slots"][:1]) + ["--native-recovery-readiness"]
    if key:
        opts += ["--native-recovery-check-key",str(setup["key"])]
    return opts


def test_scheduler_recovery_readiness_is_local_after_sha_watch(rig,capsys):
    setup,jobs=rig
    create(setup,0)
    website=setup["project"]/"output"/"site"
    website.mkdir()
    (website/"index.html").write_text("<html><body>EraLeader</body></html>")
    assert main(flags(rig)) == 0
    report=json.loads(capsys.readouterr().out)
    assert report["native_encrypted_watchdog"]["authenticated_plaintext_verified"] is False
    readiness=report["native_recovery_readiness"]
    assert readiness["verified_backup_count"] == 1
    assert readiness["private_key_status"]=="PUBLIC_KEY_MATCHED_NO_RECOVERY_DRILL"
    assert readiness["recovery_drill_executed"] is False
    assert readiness["messages_sent"]==readiness["external_api_calls"]==0
    assert len(jobs)==1
    assert (website/"native_recovery_readiness.html").is_file()
    assert "native_recovery_readiness.html" in (website/"index.html").read_text()
    assert main(flags(rig)) == 0
    repeat=json.loads(capsys.readouterr().out)
    assert repeat["native_recovery_readiness"]["verified_backup_count"]==1
    assert (website/"index.html").read_text().count("native_recovery_readiness.html")==1


def test_scheduler_opt_in_without_secret_key_explicitly_unverified(rig,capsys):
    setup,jobs=rig
    create(setup,0)
    assert main(flags(rig,key=False))==0
    result=json.loads(capsys.readouterr().out)["native_recovery_readiness"]
    assert result["private_key_status"]=="NOT_CONFIGURED_NO_RECOVERY_ASSERTION"
    assert result["needs_operator_review"] is True


@pytest.mark.parametrize("invalid",["key_without_flag","days_without_flag","flag_without_monitor","warn_out_of_range"])
def test_scheduler_recovery_flag_misuse_blocked_before_any_job(rig,invalid):
    setup,jobs=rig
    base=["--project",str(setup["project"])]
    if invalid=="key_without_flag":
        flags_now=base+["--native-recovery-check-key",str(setup["key"])]
    elif invalid=="days_without_flag":
        flags_now=base+["--native-recovery-warn-days","45"]
    elif invalid=="flag_without_monitor":
        flags_now=base+["--native-recovery-readiness"]
    else:
        flags_now=flags(rig)+["--native-recovery-warn-days","366"]
    with pytest.raises(ValueError,match="require|horizon"):
        main(flags_now)
    assert jobs == []
    assert not (setup["project"]/"output"/"native_recovery_readiness").exists()


def test_generate_plist_never_installs_private_key_audit(rig,tmp_path):
    setup,jobs=rig
    plist=tmp_path/"not_installed.plist"
    with pytest.raises(ValueError,match="not supported"):
        main(flags(rig)+["--generate-plist",str(plist)])
    assert not plist.exists() and jobs==[]


def test_primary_stale_failure_keeps_failure_and_collects_key_health(rig,monkeypatch):
    setup,jobs=rig
    create(setup,0)
    def failed(**kwargs):
        jobs.append("stale")
        raise ValueError("PRIMARY_STALE_RESEARCH")
    monkeypatch.setattr(local_schedule,"run_scheduled",failed)
    with pytest.raises(ValueError,match="PRIMARY_STALE_RESEARCH"):
        main(flags(rig))
    report=setup["project"]/"output"/"native_recovery_readiness"/"report.json"
    assert report.is_file()
    details=json.loads(report.read_text())
    assert details["verified_backup_count"]==1
    assert details["messages_sent"]==0 and details["recovery_drill_executed"] is False
    assert jobs==["stale"]
