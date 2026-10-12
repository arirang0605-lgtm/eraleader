"""6_5 safe read-only joining of existing research dashboard + cold SHA evidence."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen
import json
import os
import pytest

from eraleader import operations_cold_bridge as bridge
from eraleader import native_cold_restore_gate as gate
from eraleader.operations_overview import publish_operations_overview
from test_native_cold_replay_drill import ready, run as rehearse
from test_native_cold_integrity import enrolled
from test_native_cold_custody import bundle
from test_native_encrypted_vault import rig
from test_native_cold_restore_gate import check as gated
from test_operations_overview import seed as seed_scheduler
from test_scheduled_native_archive import NOW


def view(case, *, at=NOW+timedelta(minutes=1), **options):
    rig, cold_file, pin, seal, receipt, scratch = case
    return bridge.audit_operations_cold_bridge(
        rig["project"],pin,scratch,
        allow_colocated_research=True,clock=at,**options)


def render(case, *, at=NOW+timedelta(minutes=1), **options):
    rig, cold_file, pin, seal, receipt, scratch = case
    return bridge.publish_operations_cold_bridge(
        rig["project"],pin,scratch,
        allow_colocated_research=True,clock=at,**options)


def test_no_cold_gate_observation_is_not_claimed_as_valid_replay(ready):
    report=view(ready)
    assert report["cold_evidence"]["state"]=="NO_COLD_RESTORE_RECORD"
    assert report["cold_evidence"]["total_cold_packages"]==0
    assert report["overall_gate"]=="HOLD_UNVERIFIED_RESEARCH"
    assert report["actual_future_leader_skill_certified"] is False
    html=bridge.render_operations_cold_bridge(report)
    assert "NO_COLD_RESTORE_RECORD" in html and "실전 적중률" in html


def test_colocated_replay_on_main_dashboard_remains_research_only(ready):
    rig, cold_file, pin, seal, receipt, scratch=ready
    for mode in ("price","watch","maturity"):
        seed_scheduler(rig["project"],mode)
    unchanged={p:sha256(p.read_bytes()).hexdigest()
               for p in rig["project"].glob("output/**/last_verified_*.json")}
    original_pin=(pin/"pins"/(receipt["pin_id"]+"_first.json")).read_bytes()
    rehearse(ready)
    observation=gated(ready)
    assert list(observation["rows"].values())[0]["state"]=="RESEARCH_ONLY_FRESH"
    report=view(ready)
    cold=report["cold_evidence"]
    assert cold["state"]=="RESEARCH_ONLY_PREVIOUS_REPLAY"
    assert cold["total_cold_packages"]==1
    assert cold["research_only_packages"]==1
    assert cold["incident_packages"]==0
    assert cold["current_pin_ciphertext_reverified"] is False
    assert cold["aes_gcm_replayed_now"] is False
    result=render(ready)
    assert result["status"]==bridge.STATUS
    assert result["cold_package_count"]==1
    assert result["source_pit_certified"] is False
    assert result["actual_future_leader_skill_certified"] is False
    assert result["live_notifications_sent"]==0
    assert result["external_api_calls"]==0
    site=rig["project"]/"output"/"operations_cold"/"site"/"index.html"
    summary=rig["project"]/"output"/"operations_cold"/"cold_operations_research.json"
    assert site.is_file() and summary.is_file()
    html=site.read_text()
    assert "RESEARCH_ONLY_PREVIOUS_REPLAY" in html
    assert "실전 적중률" in html
    assert str(cold_file) not in html and str(rig["key"]) not in html
    assert str(cold_file) not in summary.read_text()
    assert (pin/"pins"/(receipt["pin_id"]+"_first.json")).read_bytes()==original_pin
    assert {p:sha256(p.read_bytes()).hexdigest() for p in unchanged}==unchanged
    handler=lambda *a,**k:SimpleHTTPRequestHandler(*a,directory=str(site.parent),**k)
    server=ThreadingHTTPServer(("127.0.0.1",0),handler)
    worker=Thread(target=server.serve_forever,daemon=True); worker.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/",timeout=3) as r:
            assert r.status==200 and b"EraLeader" in r.read()
    finally:
        server.shutdown();server.server_close()
    assert not (rig["project"]/"output"/"operations"/"site"/"index.html").exists()


def test_last_failed_or_corrupted_original_replay_shows_cold_incident(ready):
    rehearse(ready)
    gated(ready)
    prior=view(ready)
    assert prior["cold_evidence"]["state"]=="RESEARCH_ONLY_PREVIOUS_REPLAY"
    # Source gate really runs a read-only audit; its latest frozen incident
    # should appear in the integrated view, never as a success.
    rig=ready[0]
    rig["key"].chmod(0o644)
    try:
        fail=rehearse(ready,time=NOW+timedelta(minutes=1))
        assert fail["latest"]["outcome"]=="FAILED"
    finally:
        rig["key"].chmod(0o600)
    gated(ready,at=NOW+timedelta(minutes=2))
    outcome=view(ready,at=NOW+timedelta(minutes=3))
    assert outcome["cold_evidence"]["state"]=="COLD_INCIDENT_PRESENT"
    assert outcome["cold_evidence"]["incident_packages"]==1


def test_previous_fresh_sha_ages_out_from_overview(ready):
    rehearse(ready)
    gated(ready)
    fresh=view(ready)
    assert fresh["cold_evidence"]["state"]=="RESEARCH_ONLY_PREVIOUS_REPLAY"
    stale=view(ready,at=NOW+timedelta(days=3))
    assert stale["cold_evidence"]["state"]=="COLD_OBSERVATION_STALE"


@pytest.mark.parametrize("damage",["history","report","first_receipt","missing_lock"])
def test_cold_gate_tamper_never_shown_as_healthy(ready,damage):
    rehearse(ready)
    gated(ready)
    folder=ready[0]["project"]/"output"/gate.DIR
    name={"history":"history.jsonl","report":"report.json",
          "first_receipt":"first_event.json","missing_lock":".checks.lock"}[damage]
    item=folder/name
    if damage=="missing_lock":
        item.unlink()
    else:
        item.write_bytes(item.read_bytes()+b"forged")
    health=view(ready)
    assert health["cold_evidence"]["state"]=="COLD_OBSERVER_CORRUPTED"
    assert health["cold_evidence"]["total_cold_packages"]==0


def test_extra_live_key_claim_from_locally_consistent_json_rejected(ready):
    rehearse(ready)
    gated(ready)
    report=ready[0]["project"]/"output"/gate.DIR/"report.json"
    doc=json.loads(report.read_bytes())
    doc["private_key_accessed"]=True
    report.write_text(json.dumps(doc,sort_keys=True,separators=(",",":"))+"\n")
    assert view(ready)["cold_evidence"]["state"]=="COLD_OBSERVER_CORRUPTED"


def test_future_local_gate_clock_is_untrusted(ready):
    rehearse(ready)
    gated(ready)
    snapshot=view(ready,at=NOW-timedelta(days=2))
    assert snapshot["cold_evidence"]["state"]=="COLD_OBSERVER_CORRUPTED"


def test_renderer_refuses_relabeling_and_executable_html(ready):
    snapshot=view(ready)
    snapshot["overall_gate"]="LIVE_CERTIFIED"
    with pytest.raises(ValueError):
        bridge.render_operations_cold_bridge(snapshot)
    snapshot["overall_gate"]="HOLD_UNVERIFIED_RESEARCH"
    snapshot["cold_evidence"]["state"]="<svg/onload=alert(1)>"
    with pytest.raises(ValueError):
        bridge.render_operations_cold_bridge(snapshot)


def test_mid_audit_swap_fails_without_publishing(tmp_path, ready, monkeypatch):
    rehearse(ready);gated(ready)
    original=bridge.audit_operations_cold_bridge
    calls=[0]
    def swap(*args,**kwargs):
        result=original(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            gate_file=ready[0]["project"]/"output"/gate.DIR/"report.json"
            raw=gate_file.read_bytes()
            gate_file.write_bytes(raw+b"bad")
        return result
    monkeypatch.setattr(bridge,"audit_operations_cold_bridge",swap)
    with pytest.raises(RuntimeError,match="changed"):
        render(ready)
    target=ready[0]["project"]/"output"/"operations_cold"
    assert not target.exists()


def test_symlink_publication_root_and_invalid_user_mode_rejected(ready,tmp_path):
    project=ready[0]["project"]
    root=project/"output"/"operations_cold"
    root.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError):
        render(ready)
    root.unlink()
    with pytest.raises(ValueError,match="different from original"):
        bridge.audit_operations_cold_bridge(
            project,ready[2],ready[-1],clock=NOW)


def test_cli_same_process_workflow_no_key_or_network(ready,capsys):
    from scripts.render_local_cold_operations import main
    rehearse(ready);gated(ready)
    rig,_,pin,_,_,scratch=ready
    assert main(["--project",str(rig["project"]),
                 "--pin-root",str(pin),
                 "--scratch-root",str(scratch),
                 "--allow-colocated-research-only"]) == 0
    report=json.loads(capsys.readouterr().out)
    assert report["status"]==bridge.STATUS
    assert report["external_api_calls"]==0
