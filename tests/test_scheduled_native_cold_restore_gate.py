"""Opt-in cold original replay readiness in unchanged local market scheduler."""
from __future__ import annotations
import json
from datetime import timedelta
from pathlib import Path

import pytest

from eraleader import local_schedule, native_cold_integrity, native_cold_restore_gate
from scripts.run_local_scheduled import main
from test_native_cold_replay_drill import ready, run as rehearse
from test_native_cold_integrity import enrolled
from test_native_cold_custody import bundle
from test_native_encrypted_vault import rig
from test_scheduled_native_archive import NOW


@pytest.fixture
def scheduled(ready,monkeypatch):
    evidence,package,pin,first,receipt,scratch=ready
    called=[]
    def dummy(**kwargs):
        called.append("market")
        return {"status":"OFFLINE_RESEARCH_SYNTHETIC","messages_sent":0,
                "external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",dummy)
    # Synthetic first-capture clock must be consistent with the scheduled
    # observer: production current OS time would correctly mark it overdue.
    monkeypatch.setattr(native_cold_restore_gate,"_now",
                        lambda value: NOW+timedelta(minutes=5) if value is None else value)
    monkeypatch.setattr(native_cold_integrity,"_clock",
                        lambda value: NOW+timedelta(minutes=5) if value is None else value)
    options=["--project",str(evidence["project"]),
             "--native-cold-pin-root",str(pin),
             "--native-cold-allow-colocated-research-only",
             "--native-cold-restore-scratch-root",str(scratch)]
    return ready,called,options


def test_scheduled_cold_gate_runs_without_loading_key(scheduled,capsys):
    case,called,options=scheduled
    rehearse(case)
    assert main(options)==0
    report=json.loads(capsys.readouterr().out)
    assert report["native_cold_restore_gate"]["status"]==(
        "LOCAL_ENCRYPTED_COLD_RESTORE_READINESS_DRY_RUN")
    assert list(report["native_cold_restore_gate"]["rows"].values())[0][
        "state"]=="RESEARCH_ONLY_FRESH"
    assert report["native_cold_integrity"]["local_artifacts_only"] is True
    assert report["native_cold_restore_gate"]["private_key_accessed"] is False
    assert report["messages_sent"]==report["external_api_calls"]==0
    assert called==["market"]
    case[0]["key"].unlink()
    assert main(options)==0
    again=json.loads(capsys.readouterr().out)
    assert again["native_cold_restore_gate"]["new_alerts"]==[]
    assert again["native_cold_restore_gate"]["checks"]==2


def test_first_unreplayed_pin_remains_warning_not_production_pass(scheduled,capsys):
    case,called,options=scheduled
    assert main(options)==0
    report=json.loads(capsys.readouterr().out)
    gate=report["native_cold_restore_gate"]
    assert list(gate["rows"].values())[0]["state"]=="NEVER_REPLAYED"
    assert gate["verified_replay_count"]==0
    assert gate["warning_count"]==1
    assert main(options)==0
    assert json.loads(capsys.readouterr().out)["native_cold_restore_gate"][
        "new_alerts"]==[]


def test_primary_stale_cache_failure_remains_failure_while_cold_gate_runs(scheduled,monkeypatch):
    case,called,options=scheduled
    rehearse(case)
    def stale(**kwargs):
        called.append("stale")
        raise ValueError("ORIGINAL_MARKET_CACHE_STALE")
    monkeypatch.setattr(local_schedule,"run_scheduled",stale)
    with pytest.raises(ValueError,match="ORIGINAL_MARKET_CACHE_STALE"):
        main(options)
    root=case[0]["project"]/"output"
    assert (root/"native_cold_restore_readiness"/"report.json").exists()
    assert (root/"native_cold_integrity"/"report.json").exists()
    assert called==["stale"]


@pytest.mark.parametrize("invalid",["missing_pin","orphan_due",
                                     "orphan_warn","wrong_due","wrong_warn",
                                     "plist","missing_scratch"])
def test_incomplete_policy_or_optin_does_not_run_market_job(scheduled,invalid,tmp_path):
    case,called,options=scheduled
    flags=options[:]
    if invalid=="missing_pin":
        at=flags.index("--native-cold-pin-root")
        del flags[at:at+2]
    elif invalid=="orphan_due":
        flags=["--project",str(case[0]["project"]),
               "--native-cold-restore-due-days","15"]
    elif invalid=="orphan_warn":
        flags=["--project",str(case[0]["project"]),
               "--native-cold-restore-warn-days","5"]
    elif invalid=="wrong_due":
        flags+=["--native-cold-restore-due-days","0"]
    elif invalid=="wrong_warn":
        flags+=["--native-cold-restore-due-days","7",
                "--native-cold-restore-warn-days","7"]
    elif invalid=="plist":
        flags+=["--generate-plist",str(tmp_path/"not-installed.plist")]
    else:
        at=flags.index("--native-cold-restore-scratch-root")
        flags[at+1]=str(tmp_path/"missing_scratch")
    with pytest.raises((ValueError,OSError)):
        main(flags)
    assert called==[]


def test_default_scheduled_research_remains_untouched(scheduled,capsys):
    case,called,options=scheduled
    assert main(["--project",str(case[0]["project"])])==0
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="OFFLINE_RESEARCH_SYNTHETIC"
    assert "native_cold_restore_gate" not in report
    assert not (case[0]["project"]/"output"/"native_cold_restore_readiness").exists()
    assert called==["market"]
