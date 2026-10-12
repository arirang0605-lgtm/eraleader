"""6_5 multi-cohort local SHA alarm tests: all evidence is synthetic."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader import native_sha_witness
from eraleader.native_sha_watchdog import run_native_sha_watchdog, ZERO
from eraleader.native_first_capture import capture_first_native_topk
from eraleader.scheduled_native_archive import archive_captured_native_plan
from eraleader.native_sha_witness import record_native_sha_witness
from test_native_first_capture import prepare
from test_scheduled_native_archive import NOW


@pytest.fixture
def rig(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "output").mkdir(parents=True)
    root = project / "output" / "native_first_captures"
    witness = tmp_path / "mac_volume" / "witnesses"
    monkeypatch.setattr(native_sha_witness, "_separate_device", lambda a,b: True)
    plans = []
    for market in ("KR", "US"):
        bundle, rule, plan, unused = prepare(tmp_path / market.lower(), market=market)
        plans.append(plan)
    return project, root, witness, plans


def seal(rig, which=0):
    project, root, witness, plans = rig
    captured = capture_first_native_topk(plans[which], root, clock=NOW)
    archived = archive_captured_native_plan(project, plans[which], root, captured, clock=NOW)
    record_native_sha_witness(project, plans[which], root, archived, witness, clock=NOW)


def scan(rig, at=NOW, plans=None):
    project, root, witness, originals = rig
    return run_native_sha_watchdog(project, originals if plans is None else plans,
                                   witness, clock=at)


def row(result, market):
    return next(v for v in result["cohorts"].values() if v["market"] == market)


def audit_paths(rig):
    return rig[0] / "output" / "native_sha_alerts"


def test_two_cohorts_sha_pinned_steady_rechecks_dashboard_private(rig):
    seal(rig, 0)
    seal(rig, 1)
    first = scan(rig)
    assert first["check_count"] == 1
    assert len(first["cohorts"]) == 2
    assert not first["new_alerts"]
    assert all(value["state"] == "VERIFIED" and
               value["archive_sha256"] != ZERO for value in first["cohorts"].values())
    later = scan(rig, NOW + timedelta(minutes=2))
    assert later["check_count"] == 2 and not later["new_alerts"]
    page = (audit_paths(rig) / "site" / "index.html").read_text()
    assert "multi-cohort SHA integrity" in page
    assert "KR" in page and "US" in page and "DRY-RUN" in page
    for sensitive in (str(rig[3][0]), str(rig[3][1]), "issuer_id", "security_id"):
        assert sensitive not in page
        assert sensitive not in (audit_paths(rig) / "report.json").read_text()
    assert later["messages_sent"] == later["external_api_calls"] == 0
    assert later["official_leader_promotions"] == 0


def test_waiting_is_not_falsely_reported_as_failure_then_first_verified(rig):
    pending = scan(rig)
    assert all(x["state"] == "WAITING" for x in pending["cohorts"].values())
    assert pending["new_alerts"] == []
    seal(rig, 0)
    next_scan = scan(rig, NOW + timedelta(minutes=1))
    assert row(next_scan, "KR")["state"] == "VERIFIED"
    assert row(next_scan, "US")["state"] == "WAITING"
    assert not next_scan["new_alerts"]


@pytest.mark.parametrize("target", ["zip", "ssd_guard", "witness_first", "witness_guard", "witness_lock"])
def test_integrity_failure_warning_once_and_no_automatic_reseal(rig, target):
    seal(rig, 0)
    scan(rig, plans=rig[3][:1])
    project, root, witness, plans = rig
    if target == "zip":
        path = next((project/"output"/"native_first_private_archives").glob("*.zip"))
        original = path.read_bytes()
        path.write_bytes(original + b"tamper")
    elif target == "ssd_guard":
        path = next((project/"output"/"native_first_archive_receipts").glob("*_guard.json"))
        original = path.read_bytes()
        path.unlink()
    elif target == "witness_first":
        path = next(witness.glob("*_first.json"))
        original = path.read_bytes()
        path.unlink()
    elif target == "witness_guard":
        path = next(witness.glob("*_guard.json"))
        original = path.read_bytes()
        path.write_bytes(original+b"\n")
    else:
        path = next(witness.glob(".*.lock"))
        original = path.read_bytes()
        path.unlink()
    warning = scan(rig, NOW + timedelta(minutes=1), plans=plans[:1])
    assert row(warning, "KR")["state"] == "ANOMALY"
    assert len(warning["new_alerts"]) == 1
    repeated = scan(rig, NOW + timedelta(minutes=2), plans=plans[:1])
    assert not repeated["new_alerts"]
    path.write_bytes(original)
    restored = scan(rig, NOW + timedelta(minutes=3), plans=plans[:1])
    assert row(restored, "KR")["state"] == "VERIFIED"
    assert restored["new_alerts"][0].endswith(":RESTORED")


def test_entire_missing_witness_and_archive_after_first_anchor_is_alarm(rig):
    seal(rig,0)
    scan(rig,plans=rig[3][:1])
    for path in rig[2].iterdir():
        path.unlink()
    archive = next((rig[0]/"output"/"native_first_private_archives").glob("*.zip"))
    archive.unlink()
    result = scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])
    assert row(result,"KR")["state"]=="ANOMALY"
    assert row(result,"KR")["issue"] != "WAITING_FIRST_WRITE"


def test_missing_plan_in_input_does_not_silently_reduce_monitored_inventory(rig):
    seal(rig,0);seal(rig,1)
    scan(rig)
    removed = scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])
    assert len(removed["cohorts"]) == 2
    assert row(removed,"US")["issue"] == "MISSING_SCAN_INPUT"
    assert len(removed["new_alerts"]) == 1
    same = scan(rig,NOW+timedelta(minutes=2),plans=rig[3][:1])
    assert same["new_alerts"] == []
    back = scan(rig,NOW+timedelta(minutes=3))
    assert len(back["new_alerts"]) == 1
    assert back["new_alerts"][0].endswith(":RESTORED")


def test_plan_file_deleted_is_alarmed_without_echoing_private_path(rig):
    seal(rig,0)
    scan(rig,plans=rig[3][:1])
    plan = rig[3][0]
    original = plan.read_bytes()
    plan.unlink()
    alarm = scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])
    assert row(alarm,"KR")["issue"] == "PLAN_INVALID_OR_MISSING"
    assert str(plan) not in (audit_paths(rig)/"site"/"index.html").read_text()
    plan.write_bytes(original)
    assert row(scan(rig,NOW+timedelta(minutes=2),plans=rig[3][:1]),"KR")["state"]=="VERIFIED"


@pytest.mark.parametrize("artifact", ["genesis.json", "first_event.json", "report.json", "history.jsonl", ".checks.lock"])
def test_watcher_audit_chain_corruption_or_loss_fails_closed(rig,artifact):
    seal(rig,0)
    scan(rig,plans=rig[3][:1])
    path = audit_paths(rig) / artifact
    if artifact == ".checks.lock":
        path.unlink()
    else:
        path.write_bytes(b"{}\n")
    with pytest.raises((ValueError, RuntimeError)):
        scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])


def test_whole_history_rollback_detected_by_published_sha_checkpoint(rig):
    seal(rig,0)
    scan(rig,plans=rig[3][:1])
    folder = audit_paths(rig)
    log = folder/"history.jsonl"
    first = log.read_bytes()
    scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])
    log.write_bytes(first)
    with pytest.raises(ValueError,match="rollback|checkpoint|history"):
        scan(rig,NOW+timedelta(minutes=2),plans=rig[3][:1])


def test_new_plan_can_be_enrolled_without_resetting_original_sha_pin(rig):
    seal(rig,0)
    original = scan(rig,plans=rig[3][:1])
    seal(rig,1)
    expanded = scan(rig,NOW+timedelta(minutes=1))
    assert len(expanded["cohorts"]) == 2
    kr_before = row(original,"KR")["witness_sha256"]
    assert row(expanded,"KR")["witness_sha256"] == kr_before


def test_dup_plan_and_invalid_root_rejected_before_first_history(rig):
    with pytest.raises(ValueError,match="Duplicate"):
        scan(rig,plans=[rig[3][0],rig[3][0]])
    assert not audit_paths(rig).exists()
    with pytest.raises(ValueError):
        run_native_sha_watchdog(rig[0],rig[3],rig[0]/"output"/"witness")
    assert not audit_paths(rig).exists()


def test_mac_local_first_stamp_is_not_pit_or_prediction_attestation(rig):
    seal(rig,0)
    result=scan(rig,plans=rig[3][:1])
    assert result["independent_pit_certified"] is False
    assert result["actual_future_leader_skill_certified"] is False
    assert result["local_artifacts_only"] is True
    assert "Not" not in result["status"]


def test_enrolled_seal_swap_is_not_accepted_as_new_cohort_identity(rig,monkeypatch):
    seal(rig,0)
    original=scan(rig,plans=rig[3][:1])
    from eraleader import native_sha_watchdog as module
    original_verify=module.verify_native_sha_witness
    def swapped(*args,**kwargs):
        value=dict(original_verify(*args,**kwargs))
        value["witness_sha256"]="f"*64
        return value
    monkeypatch.setattr(module,"verify_native_sha_witness",swapped)
    alarm=scan(rig,NOW+timedelta(minutes=1),plans=rig[3][:1])
    assert row(alarm,"KR")["issue"] == "FIRST_PIN_REPLACED"
    assert row(alarm,"KR")["state"] == "ANOMALY"
    assert row(original,"KR")["witness_sha256"] != "f"*64


@pytest.mark.parametrize("artifact",["orphan_ssd_guard","orphan_external_guard","captured_first_without_archive"])
def test_partial_first_seal_or_completed_capture_is_never_false_waiting(rig,artifact):
    from eraleader.native_evidence_archive import _slot
    from eraleader.native_first_capture import read_capture_plan
    project,root,witness,plans=rig
    slot=_slot(read_capture_plan(plans[0])[0])
    if artifact=="orphan_ssd_guard":
        path=project/"output"/"native_first_archive_receipts"/("native_"+slot+"_guard.json")
        path.parent.mkdir()
        path.write_text("{}")
    elif artifact=="orphan_external_guard":
        path=witness/("native_"+slot+"_guard.json")
        path.parent.mkdir(parents=True,mode=0o700)
        path.write_text("{}")
    else:
        captured=capture_first_native_topk(plans[0],root,clock=NOW)
        assert captured["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"
    result=scan(rig,plans=plans[:1])
    assert row(result,"KR")["state"]=="ANOMALY"
    assert row(result,"KR")["issue"]=="UNWITNESSED_OR_PARTIAL"
    assert len(result["new_alerts"])==1
