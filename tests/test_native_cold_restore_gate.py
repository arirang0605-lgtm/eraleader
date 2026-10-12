"""6_5 cold-PIN + actual native replay fresh/failed/late/rollback gate."""
from __future__ import annotations
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os
import sys

import pytest

from eraleader import native_cold_restore_gate as gate
from eraleader import native_cold_integrity as cold
from eraleader import native_cold_replay_drill as replay
from eraleader import native_cold_custody as custody
from eraleader.native_sha_watchdog import _bytes, _json
from test_native_cold_replay_drill import ready, run as rehearse
from test_native_cold_integrity import enrolled
from test_native_cold_custody import bundle, export
from test_native_encrypted_vault import rig, backup
from test_scheduled_native_archive import NOW
from test_native_first_capture import prepare
from eraleader.native_first_capture import capture_first_native_topk
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from eraleader.native_encrypted_vault import backup_encrypted_native_original


def check(case, at=NOW, *, days=30, warning=7, **changes):
    evidence,archive,root,first,receipt,scratch=case
    return gate.run_cold_restore_gate(
        evidence["project"],root,scratch,due_days=days,warn_days=warning,
        allow_colocated_research=True,clock=at,**changes)


def rows(report):
    return list(report["rows"].values())


def observed(case):
    evidence,archive,root,first,receipt,scratch=case
    return gate.verify_restore_gate_history(
        evidence["project"],root,scratch,allow_colocated_research=True)


def test_missing_actual_replay_denies_even_perfect_cold_sha(ready):
    response=check(ready)
    assert rows(response)[0]["state"]=="NEVER_REPLAYED"
    assert response["verified_replay_count"]==0
    assert response["warning_count"]==1
    assert response["new_alerts"]==[ready[4]["pin_id"]+":NEVER_REPLAYED"]
    assert check(ready)["new_alerts"]==[]
    assert observed(ready)["checks"]==2
    assert response["private_key_accessed"] is False
    assert response["plaintext_decrypted"] is False
    assert response["operational_offsite_attested"] is False
    assert response["messages_sent"]==response["external_api_calls"]==0


def test_replay_after_registration_releases_research_only_not_offsite(ready):
    first=check(ready)
    actually=rehearse(ready)
    assert actually["latest"]["outcome"]=="PASSED"
    report=check(ready,at=NOW+timedelta(minutes=1))
    assert rows(report)[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert report["research_only_fresh_count"]==1
    assert report["verified_replay_count"]==0
    assert report["warning_count"]==0
    assert report["new_alerts"]==[ready[4]["pin_id"]+":RESTORED_FRESH_REPLAY"]
    assert check(ready,at=NOW+timedelta(minutes=1))["new_alerts"]==[]
    assert observed(ready)["checks"]==3
    assert (ready[0]["project"]/"output"/gate.DIR/"site"/"index.html").is_file()
    html=(ready[0]["project"]/"output"/gate.DIR/"site"/"index.html").read_text()
    js=(ready[0]["project"]/"output"/gate.DIR/"report.json").read_text()
    assert str(ready[0]["key"]) not in html+js
    assert str(ready[1]) not in html+js
    assert str(ready[0]["plan"]) not in html+js


def test_due_soon_overdue_then_renewal_and_deduplicate(ready):
    rehearse(ready)
    assert rows(check(ready,at=NOW+timedelta(days=20)))[0]["state"]=="RESEARCH_ONLY_FRESH"
    soon=check(ready,at=NOW+timedelta(days=25))
    assert rows(soon)[0]["state"]=="DUE_SOON"
    assert len(soon["new_alerts"])==1
    assert check(ready,at=NOW+timedelta(days=25))["new_alerts"]==[]
    late=check(ready,at=NOW+timedelta(days=31))
    assert rows(late)[0]["state"]=="OVERDUE"
    rehearse(ready,time=NOW+timedelta(days=31))
    fresh=check(ready,at=NOW+timedelta(days=31,minutes=1))
    assert rows(fresh)[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert len(fresh["new_alerts"])==1


def test_last_failed_replay_overrides_earlier_success(ready):
    rehearse(ready)
    check(ready)
    invalid=ready[0]["key"]
    original=invalid.read_bytes()
    invalid.chmod(0o644)
    try:
        attempted=rehearse(ready,time=NOW+timedelta(minutes=1))
        assert attempted["latest"]["outcome"]=="FAILED"
    finally:
        invalid.chmod(0o600)
    failed=check(ready,at=NOW+timedelta(minutes=2))
    assert rows(failed)[0]["state"]=="LAST_REPLAY_FAILED"
    assert failed["warning_count"]==1
    assert check(ready,at=NOW+timedelta(minutes=2))["new_alerts"]==[]
    rehearse(ready,time=NOW+timedelta(minutes=3))
    assert rows(check(ready,at=NOW+timedelta(minutes=4)))[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert invalid.read_bytes()==original


@pytest.mark.parametrize("failure",["corrupt","removed","symlink"])
def test_current_cold_archive_damage_blocks_health_after_pass(ready,failure,tmp_path):
    rehearse(ready)
    check(ready)
    archive=ready[1]
    original=archive.read_bytes()
    if failure=="corrupt":
        archive.write_bytes(original+b"BAD")
    elif failure=="removed":
        archive.unlink()
    else:
        displaced=tmp_path/"archive_elsewhere.zip"
        archive.rename(displaced)
        archive.symlink_to(displaced)
    warning=check(ready,at=NOW+timedelta(minutes=1))
    assert rows(warning)[0]["state"]=="UNTRUSTED_COLD_SHA"
    if archive.is_symlink():
        archive.unlink()
    archive.write_bytes(original)
    assert rows(check(ready,at=NOW+timedelta(minutes=2)))[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert sha256(archive.read_bytes()).hexdigest()==ready[3]["package_sha256"]


def test_invalid_replay_ledger_never_retains_healthy_status(ready):
    rehearse(ready)
    check(ready)
    folder=ready[0]["project"]/"output"/replay.DIR
    original=(folder/"report.json").read_bytes()
    (folder/"report.json").write_bytes(original+b"bad")
    invalid=check(ready,at=NOW+timedelta(minutes=1))
    assert rows(invalid)[0]["state"]=="REPLAY_EVIDENCE_INVALID"
    (folder/"report.json").write_bytes(original)
    restored=check(ready,at=NOW+timedelta(minutes=2))
    assert rows(restored)[0]["state"]=="RESEARCH_ONLY_FRESH"


def test_self_consistent_replay_log_rollback_blocked_by_observer_pin(ready):
    first=rehearse(ready)
    original_folder=ready[0]["project"]/"output"/replay.DIR
    earlier_report=(original_folder/"report.json").read_bytes()
    earlier_history=(original_folder/"history.jsonl").read_bytes()
    rehearse(ready,time=NOW+timedelta(minutes=1))
    latest_report=(original_folder/"report.json").read_bytes()
    latest_history=(original_folder/"history.jsonl").read_bytes()
    check(ready,at=NOW+timedelta(minutes=2))
    (original_folder/"report.json").write_bytes(earlier_report)
    (original_folder/"history.jsonl").write_bytes(earlier_history)
    rollback=check(ready,at=NOW+timedelta(minutes=3))
    assert rows(rollback)[0]["state"]=="REPLAY_HISTORY_ROLLBACK"
    (original_folder/"report.json").write_bytes(latest_report)
    (original_folder/"history.jsonl").write_bytes(latest_history)
    assert rows(check(ready,at=NOW+timedelta(minutes=4)))[0]["state"]=="RESEARCH_ONLY_FRESH"


def test_pin_first_guard_missing_never_claims_replay_ready(ready):
    rehearse(ready)
    check(ready)
    parent=ready[2]/"pins"
    guard=parent/(ready[4]["pin_id"]+"_guard.json")
    original=guard.read_bytes()
    guard.unlink()
    invalid=check(ready,at=NOW+timedelta(minutes=1))
    assert rows(invalid)[0]["state"]=="UNTRUSTED_COLD_SHA"
    guard.write_bytes(original)
    guard.chmod(0o600)  # Immutable witness was originally owner-only.
    restored=check(ready,at=NOW+timedelta(minutes=2))
    assert rows(restored)[0]["state"]=="RESEARCH_ONLY_FRESH"


def test_pin_history_tamper_fails_closed_without_new_pin(ready):
    rehearse(ready)
    check(ready)
    ledger=ready[2]/"history.jsonl"
    unchanged=ledger.read_bytes()
    ledger.write_bytes(unchanged+b"broken")
    report=check(ready,at=NOW+timedelta(minutes=1))
    assert rows(report)[0]["state"]=="PIN_HISTORY_INVALID"
    ledger.write_bytes(unchanged)
    assert rows(check(ready,at=NOW+timedelta(minutes=2)))[0]["state"]=="RESEARCH_ONLY_FRESH"


@pytest.mark.parametrize("name",["genesis.json","history.jsonl","first_event.json","report.json"])
def test_observer_original_sha_proof_tamper_blocks_future_scan(ready,name):
    rehearse(ready)
    check(ready)
    f=ready[0]["project"]/"output"/gate.DIR/name
    if name=="history.jsonl":
        f.write_bytes(b"")
    else:
        f.write_bytes(f.read_bytes()+b"wrong")
    with pytest.raises((ValueError,KeyError)):
        check(ready,at=NOW+timedelta(minutes=1))
    with pytest.raises((ValueError,KeyError)):
        observed(ready)


def test_immutable_policy_clock_and_strict_hardware_contract(ready):
    rehearse(ready)
    check(ready)
    with pytest.raises(ValueError,match="wall clock"):
        check(ready,at=NOW-timedelta(seconds=1))
    with pytest.raises(ValueError,match="policy|first"):
        check(ready,days=60)
    rig,archive,root,first,receipt,scratch=ready
    with pytest.raises(ValueError,match="different from original SSD"):
        gate.run_cold_restore_gate(rig["project"],root,scratch)
    assert observed(ready)["private_key_accessed"] is False


def test_no_key_or_decrypt_even_when_sources_have_key(ready,monkeypatch):
    rehearse(ready)
    def forbidden(*args,**kwargs):
        raise AssertionError("Gate must NOT decrypt or use private RSA key")
    monkeypatch.setattr(replay,"restore_encrypted_native_original",forbidden)
    monkeypatch.setattr(replay,"_private_key",forbidden)
    outcome=check(ready)
    assert rows(outcome)[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert outcome["private_key_accessed"] is False


def test_mixed_kr_us_package_requires_every_model_authenticated(tmp_path,rig):
    first=backup(rig)
    b,rule,us_plan,unused=prepare(tmp_path/"fresh_us",market="US")
    captured=capture_first_native_topk(us_plan,rig["capture"],clock=NOW)
    issued=archive_captured_native_plan(
        rig["project"],us_plan,rig["capture"],captured,clock=NOW)
    record_native_sha_witness(
        rig["project"],us_plan,rig["capture"],issued,rig["witness"],clock=NOW)
    second=backup_encrypted_native_original(
        rig["project"],us_plan,rig["capture"],rig["witness"],
        rig["vault"],rig["cert"],clock=NOW)
    target=tmp_path/"private_multi"
    target.mkdir(mode=0o700)
    archive=target/"both.zip"
    pkg=custody.create_portable_native_custody(
        rig["project"],[first["slot"],second["slot"]],
        rig["vault"],rig["witness"],rig["cert"],archive,
        allow_colocated_research=True,clock=NOW)
    pin_root=tmp_path/"pin_root"
    pin_root.mkdir(mode=0o700)
    pin=cold.enroll_cold_integrity(
        rig["project"],pin_root,"krus-first",archive,pkg["package_sha256"],
        allow_colocated_research=True,clock=NOW)
    scratch=tmp_path/"scratch"
    scratch.mkdir(mode=0o700)
    def gate_scan(at):
        return gate.run_cold_restore_gate(
            rig["project"],pin_root,scratch,allow_colocated_research=True,clock=at)
    assert rows(gate_scan(NOW))[0]["state"]=="NEVER_REPLAYED"
    kr=replay.run_cold_replay_drill(
        rig["project"],pin_root,"krus-first",first["slot"],rig["key"],
        scratch,allow_colocated_research=True,clock=NOW)
    assert kr["latest"]["outcome"]=="PASSED"
    only_kr=gate_scan(NOW+timedelta(minutes=1))
    assert rows(only_kr)[0]["state"]=="NEVER_REPLAYED"
    us=replay.run_cold_replay_drill(
        rig["project"],pin_root,"krus-first",second["slot"],rig["key"],
        scratch,allow_colocated_research=True,clock=NOW+timedelta(minutes=2))
    assert us["latest"]["outcome"]=="PASSED"
    both=gate_scan(NOW+timedelta(minutes=3))
    assert rows(both)[0]["state"]=="RESEARCH_ONLY_FRESH"
    assert rows(both)[0]["market"]=="MIXED"
    assert both["verified_replay_count"]==0
    assert not list(scratch.iterdir())
