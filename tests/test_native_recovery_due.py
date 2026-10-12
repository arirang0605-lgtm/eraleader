"""6_5 key-free native encrypted recovery due observer tests (synthetic only)."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader import native_recovery_due as due
from eraleader.native_recovery_due import (
    run_recovery_due_watchdog, verify_recovery_due_history, STATUS, ZERO,
)
from test_native_encrypted_vault import rig
from test_native_recovery_drill import prepared, do
from test_scheduled_native_archive import NOW


def run(rig, *, offset_days=0, minutes=5, due_days=30, warn_days=7, slots=None):
    evidence, first, scratch=rig
    return run_recovery_due_watchdog(
        evidence["project"],
        [first["slot"]] if slots is None else slots,
        evidence["vault"], evidence["witness"], evidence["cert"], scratch,
        due_days=due_days, warn_days=warn_days,
        clock=NOW+timedelta(days=offset_days,minutes=minutes))


def records(result):
    return next(iter(result["cohorts"].values()))


def directory(rig):
    return rig[0]["project"]/"output"/"native_recovery_due_alerts"


def verify(rig,*,due_days=30,warn_days=7):
    original, _, scratch = rig
    return verify_recovery_due_history(
        original["project"], original["vault"],
        original["witness"], original["cert"], scratch,
        due_days=due_days, warn_days=warn_days)


def test_no_original_drill_is_warning_not_false_pass(prepared):
    first=run(prepared)
    row=records(first)
    assert first["status"]==STATUS
    assert row["state"]=="NEVER_TESTED"
    assert row["issue"]=="NO_SUCCESSFUL_DRILL"
    assert row["pinned_drill_count"]==0 and row["pinned_drill_sha256"]==ZERO
    assert len(first["new_alerts"])==1
    assert not run(prepared,minutes=6)["new_alerts"]
    assert first["messages_sent"]==first["external_api_calls"]==0
    assert first["actual_future_leader_skill_certified"] is False
    assert verify(prepared)["chain_verified"] is True


def test_successful_drill_is_fresh_then_due_soon_overdue_and_renewed(prepared):
    do(prepared)
    fresh=run(prepared,offset_days=1)
    assert records(fresh)["state"]=="HEALTHY"
    assert not fresh["new_alerts"]
    near=run(prepared,offset_days=24)
    assert records(near)["state"]=="DUE_SOON"
    assert len(near["new_alerts"])==1
    assert not run(prepared,offset_days=25)["new_alerts"]
    overdue=run(prepared,offset_days=31)
    assert records(overdue)["state"]=="OVERDUE"
    assert len(overdue["new_alerts"])==1
    do(prepared,clock=NOW+timedelta(days=31,minutes=10))
    recovery=run(prepared,offset_days=31,minutes=11)
    assert records(recovery)["state"]=="HEALTHY"
    assert recovery["new_alerts"][0].endswith(":VERIFIED_RECOVERY_DRILL_FRESH")
    assert verify(prepared)["check_count"]==5


def test_recent_failed_drill_cannot_reset_previous_success(prepared,tmp_path):
    do(prepared)
    first=run(prepared,offset_days=1)
    assert records(first)["state"]=="HEALTHY"
    missing=tmp_path/"missing_0600_private.pem"
    out=do(prepared,key=missing,clock=NOW+timedelta(days=2))
    assert out["latest"]["outcome"]=="FAILED"
    failed=run(prepared,offset_days=2,minutes=6)
    assert records(failed)["state"]=="FAILED"
    assert records(failed)["issue"]=="LAST_REHEARSAL_FAILED"
    assert len(failed["new_alerts"])==1
    do(prepared,clock=NOW+timedelta(days=3))
    repaired=run(prepared,offset_days=3,minutes=6)
    assert records(repaired)["state"]=="HEALTHY"
    assert repaired["new_alerts"][0].endswith("VERIFIED_RECOVERY_DRILL_FRESH")


def test_only_failed_historical_drills_never_count_as_a_pass(prepared,tmp_path):
    rig,_,_=prepared
    missing=tmp_path/"missing_key"
    do(prepared,key=missing)
    checked=run(prepared,minutes=6)
    assert records(checked)["state"]=="FAILED"
    assert records(checked)["last_passed_at_utc"] is None
    assert records(checked)["next_due_at_utc"] is None
    assert records(checked)["pinned_drill_count"]==1


def test_old_drill_history_self_consistent_replacement_is_integrity_anomaly(prepared,monkeypatch):
    do(prepared)
    first=run(prepared)
    orig=due._read_drills
    def fake(*args):
        events,verified=orig(*args)
        copy=[dict(x) for x in events]
        copy[0]["event_sha256"]="f"*64
        return copy,verified
    monkeypatch.setattr(due,"_read_drills",fake)
    alarm=run(prepared,minutes=6)
    assert records(alarm)["state"]=="INVALID_EVIDENCE"
    assert records(alarm)["issue"]=="DRILL_SHA_HISTORY_UNTRUSTED"
    assert records(alarm)["pinned_drill_sha256"]==records(first)["pinned_drill_sha256"]
    assert len(alarm["new_alerts"])==1


@pytest.mark.parametrize("corrupt",[
    "genesis.json","first_event.json","history.jsonl","report.json",".checks.lock",
])
def test_original_recovery_sha_history_corruption_becomes_dry_run_warning(prepared,corrupt):
    do(prepared)
    run(prepared)
    file=prepared[0]["project"]/"output"/"native_recovery_drills"/corrupt
    original=file.read_bytes()
    if corrupt==".checks.lock": file.unlink()
    else: file.write_bytes(b"{}\n")
    alarm=run(prepared,minutes=6)
    assert records(alarm)["state"]=="INVALID_EVIDENCE"
    assert len(alarm["new_alerts"])==1
    assert not run(prepared,minutes=7)["new_alerts"]
    file.write_bytes(original)
    good=run(prepared,minutes=8)
    assert records(good)["state"]=="HEALTHY"
    assert good["new_alerts"][0].endswith(":VERIFIED_RECOVERY_DRILL_FRESH")


def test_complete_first_drill_files_deleted_after_previous_success_cannot_reset(prepared):
    do(prepared)
    run(prepared)
    root=prepared[0]["project"]/"output"/"native_recovery_drills"
    backup={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    for name in backup: (root/name).unlink()
    warning=run(prepared,minutes=6)
    assert records(warning)["state"]=="INVALID_EVIDENCE"
    assert records(warning)["pinned_drill_count"]==1
    assert warning["new_alerts"]
    for name,body in backup.items(): (root/name).write_bytes(body)
    restored=run(prepared,minutes=7)
    assert records(restored)["state"]=="HEALTHY"


def test_slots_dropped_are_monitored_not_silently_removed(prepared):
    rig,first,scratch=prepared
    us="us_"+"b"*24
    first_report=run(prepared,slots=[first["slot"],us])
    assert len(first_report["cohorts"])==2
    removed=run(prepared,slots=[first["slot"]],minutes=6)
    assert len(removed["cohorts"])==2
    us_id=sha256(us.encode()).hexdigest()
    assert removed["cohorts"][us_id]["state"]=="MISSING_SCAN_INPUT"
    assert len(removed["new_alerts"])==1
    assert not run(prepared,slots=[first["slot"]],minutes=7)["new_alerts"]
    come_back=run(prepared,slots=[first["slot"],us],minutes=8)
    assert come_back["cohorts"][us_id]["state"]=="NEVER_TESTED"


def test_new_slot_added_without_rewriting_original_proof(prepared):
    do(prepared)
    first=run(prepared)
    original=records(first)["pinned_drill_sha256"]
    secondary="us_"+"a"*24
    later=run(prepared,slots=[prepared[1]["slot"],secondary],minutes=6)
    assert len(later["cohorts"])==2
    original_slot=sha256(prepared[1]["slot"].encode()).hexdigest()
    assert later["cohorts"][original_slot]["pinned_drill_sha256"]==original
    assert later["cohorts"][sha256(secondary.encode()).hexdigest()]["state"]=="NEVER_TESTED"


@pytest.mark.parametrize("file",[
    "genesis.json","first_event.json","history.jsonl","report.json",".checks.lock",
])
def test_due_watch_first_sha_history_loss_fails_closed(prepared,file):
    run(prepared)
    path=directory(prepared)/file
    if file==".checks.lock": path.unlink()
    else: path.write_bytes(b"{}\n")
    with pytest.raises((RuntimeError,ValueError)):
        run(prepared,minutes=6)


def test_due_watch_history_rollback_detected_by_report(prepared):
    run(prepared)
    file=directory(prepared)/"history.jsonl"
    original=file.read_bytes()
    run(prepared,minutes=6)
    file.write_bytes(original)
    with pytest.raises(ValueError,match="checkpoint|history|rollback"):
        verify(prepared)


def test_monotonic_local_clock_and_immutable_policy(prepared):
    run(prepared,minutes=10)
    with pytest.raises(ValueError,match="clock"):
        run(prepared,minutes=6)
    with pytest.raises(ValueError,match="genesis|policy"):
        run(prepared,minutes=11,due_days=60,warn_days=10)


@pytest.mark.parametrize("policy",[(0,0),(366,0),(30,30),(30,-1),(True,0)])
def test_due_policy_bounds_fail_before_first_watch_write(prepared,policy):
    with pytest.raises(ValueError,match="policy"):
        run(prepared,due_days=policy[0],warn_days=policy[1])
    assert not directory(prepared).exists()


def test_bad_scratch_path_and_duplicate_slot_rejected(prepared,tmp_path):
    rig,first,scratch=prepared
    with pytest.raises(ValueError,match="Duplicate"):
        run(prepared,slots=[first["slot"],first["slot"]])
    with pytest.raises(ValueError,match="different filesystem|overlap"):
        due.run_recovery_due_watchdog(
            rig["project"],[first["slot"]],rig["vault"],rig["witness"],
            rig["cert"],rig["project"]/"output")
    assert not directory(prepared).exists()


def test_local_report_and_dashboard_redact_original_sources(prepared):
    rig, first, scratch = prepared
    site=rig["project"]/"output"/"site"
    site.mkdir()
    (site/"index.html").write_text("<html><body>EraLeader</body></html>")
    do(prepared)
    run(prepared)
    run(prepared,minutes=6)
    report=(directory(prepared)/"report.json").read_text()
    page=(site/"native_recovery_due.html").read_text()
    assert "DRY-RUN" in page
    assert "native_recovery_due.html" in (site/"index.html").read_text()
    assert (site/"index.html").read_text().count("native_recovery_due.html")==1
    for sensitive in (str(rig["key"]),str(rig["cert"]),str(rig["vault"]),
                      str(rig["witness"]),str(scratch),str(rig["plan"]),
                      "issuer_id","security_id","original/watch.sqlite"):
        assert sensitive not in page
        assert sensitive not in report
    assert records(run(prepared,minutes=7))["state"]=="HEALTHY"
    assert run(prepared,minutes=8)["messages_sent"]==0


def test_key_free_verify_no_private_key_access(prepared):
    do(prepared)
    original,_,_=prepared
    original["key"].unlink()
    assert records(run(prepared))["state"]=="HEALTHY"
    assert verify(prepared)["status"]=="LOCAL_RECOVERY_DUE_SHA_CHAIN_VERIFIED"
