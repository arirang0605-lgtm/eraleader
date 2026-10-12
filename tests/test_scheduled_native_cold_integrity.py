"""Only explicit SHA-only encrypted native custody periodic audit joins scheduler."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
import json
import pytest

from eraleader import local_schedule, native_cold_integrity
from scripts.run_local_scheduled import main
from test_native_encrypted_vault import rig
from test_native_cold_custody import bundle
from test_native_cold_integrity import enrolled
from test_scheduled_native_archive import NOW


@pytest.fixture
def scheduled(enrolled,monkeypatch):
    rig,archive,root,first,init=enrolled
    invoked=[]
    def normal(**kwargs):
        invoked.append("main")
        return {"status":"SYNTHETIC_MARKET_RESEARCH","messages_sent":0,
                "external_api_calls":0}
    monkeypatch.setattr(local_schedule,"run_scheduled",normal)
    monkeypatch.setattr(native_cold_integrity,"_clock",
                        lambda value: NOW+timedelta(minutes=5) if value is None else value)
    opts=["--project",str(rig["project"]), "--native-cold-pin-root",str(root),
          "--native-cold-allow-colocated-research-only"]
    return rig,archive,root,first,init,invoked,opts


def test_periodic_opt_in_scans_sha_only_without_archive_or_key_arg(scheduled,capsys):
    rig,archive,root,first,init,ran,opts=scheduled
    assert main(opts)==0
    report=json.loads(capsys.readouterr().out)
    cold=report["native_cold_integrity"]
    assert cold["status"]==native_cold_integrity.STATUS
    assert list(cold["packages"].values())==["RESEARCH_ONLY_VERIFIED"]
    assert cold["external_api_calls"]==cold["messages_sent"]==0
    assert ran==["main"]
    assert main(opts)==0
    again=json.loads(capsys.readouterr().out)["native_cold_integrity"]
    assert again["new_alerts"]==[]
    assert again["check_count"]==3
    assert not (rig["project"]/"output"/"native_cold_integrity").is_symlink()


def test_stale_market_failure_does_not_suppress_cold_sha_audit(scheduled,monkeypatch):
    rig,archive,root,first,init,ran,opts=scheduled
    def stale(**kwargs):
        ran.append("stale")
        raise ValueError("EXISTING_MARKET_CACHE_STALE")
    monkeypatch.setattr(local_schedule,"run_scheduled",stale)
    with pytest.raises(ValueError,match="EXISTING_MARKET_CACHE_STALE"):
        main(opts)
    report=rig["project"]/"output"/"native_cold_integrity"/"report.json"
    assert json.loads(report.read_bytes())["status"]==native_cold_integrity.STATUS
    assert ran==["stale"]


@pytest.mark.parametrize("problem",["missing_root","orphan_research","orphan_policy",
                                     "bad_gap","wrong_mode","plist"])
def test_bad_or_implicit_cold_scheduler_configuration_rejected_early(
        scheduled,tmp_path,problem):
    rig,archive,root,first,init,ran,opts=scheduled
    if problem=="missing_root":
        opts[3]=str(tmp_path/"does_not_exist")
    if problem=="orphan_research":
        opts=opts[:2]+["--native-cold-allow-colocated-research-only"]
    if problem=="orphan_policy":
        opts=opts[:2]+["--native-cold-max-gap-hours","24"]
    if problem=="bad_gap":
        opts+=["--native-cold-max-gap-hours","0"]
    if problem=="wrong_mode":
        opts=opts[:-1]
    if problem=="plist":
        opts+=["--generate-plist",str(tmp_path/"not_installed.plist")]
    with pytest.raises((ValueError,FileNotFoundError)):
        main(opts)
    assert ran==[]


def test_ordinary_scheduler_untouched_without_opt_in(scheduled,capsys):
    rig,archive,root,first,init,ran,opts=scheduled
    assert main(["--project",str(rig["project"])])==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="SYNTHETIC_MARKET_RESEARCH"
    assert "native_cold_integrity" not in result
    assert ran==["main"]
