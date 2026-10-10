"""Synthetic progression audits; no real stock performance or independent PIT."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.watch_progression import audit_watch_progression
from eraleader.cli import main

MODEL="synthetic-screen-v1"
FIRST=datetime(2026,10,5,8,tzinfo=timezone.utc)


def snapshot(clock, *, security="SYN-A", hit=True, market="KR"):
    observation=clock.astimezone(timezone.utc).isoformat()
    return {
        "market":market,"as_of":observation,"version":MODEL,
        "run_id":f"syn-run-{observation}-{security}",
        "pit_certified":False,"offline_provenance":["synthetic_fixture"],
        "company_rows":[{
            "market":market,"security_id":security,"as_of":observation,
            "state":"WATCH","full_score":None,
            "verified_future_leader_candidate":False,
            "research_growth_screen_hit":hit,
        }]
    }


def observe(ledger,day,*,security="SYN-A",hit=True,market="KR"):
    timestamp=FIRST+timedelta(days=day)
    return ledger.record_integrated(
        snapshot(timestamp,security=security,hit=hit,market=market),clock=timestamp)


def test_first_persist_weak_reenter_in_actual_prospective_order(tmp_path):
    ledger=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        assert observe(ledger,0)["new_research_observations"]==1
        assert observe(ledger,1)["new_records"]==1
        assert observe(ledger,2,hit=False)["screen_hits"]==0
        observe(ledger,3,hit=True)
    finally:ledger.close()
    result=audit_watch_progression(tmp_path/"prospective.sqlite",market="KR",
                                   model_version=MODEL)
    assert result["source_ledger_observations"]==4
    assert result["eligible_prospective_observations"]==4
    assert result["excluded_retrospective_observations"]==0
    assert [e["transition"] for e in result["transition_event_sample"]]==[
        "INITIAL_WATCH","WATCH_PERSISTED","SCREEN_WEAKENED","SCREEN_REENTERED"]
    assert result["transition_counts"]["SCREEN_WEAKENED"]==1
    assert result["official_state_promotions"]==0
    assert result["pit_certified"] is False


def test_absent_company_in_other_run_never_counts_as_weakness(tmp_path):
    path=tmp_path/"prospective.sqlite"
    p=ProspectiveRegistry(path)
    try:
        observe(p,0)
        observe(p,1,security="SYN-B",hit=False)
        observe(p,2)
    finally:p.close()
    report=audit_watch_progression(path,market="KR",model_version=MODEL)
    assert report["transition_counts"]["SCREEN_WEAKENED"]==0
    assert report["transition_counts"]["WATCH_PERSISTED"]==1
    assert report["transition_counts"]["PRE_WATCH"]==1
    assert report["securities_with_eligible_observations"]==2


def test_no_hit_then_first_hit_then_two_negative_reports(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        observe(reg,0,hit=False)
        observe(reg,1,hit=True)
        observe(reg,2,hit=False)
        observe(reg,3,hit=False)
    finally:reg.close()
    result=audit_watch_progression(path,market="KR",model_version=MODEL)
    assert [r["transition"] for r in result["transition_event_sample"]]==[
        "PRE_WATCH","INITIAL_WATCH","SCREEN_WEAKENED","SCREEN_STILL_WEAK"]
    assert result["transition_counts"]["SCREEN_REENTERED"]==0


def test_replay_is_idempotent_and_does_not_retimestamp(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        first=observe(reg,0)
        rerun=reg.record_integrated(snapshot(FIRST),clock=FIRST+timedelta(days=1))
        assert first["new_records"]==1
        assert rerun["new_records"]==0
        assert rerun["new_research_observations"]==0
    finally:reg.close()
    result=audit_watch_progression(path,market="KR",model_version=MODEL)
    assert result["source_ledger_observations"]==1
    assert result["transition_event_sample"][0]["registered_at"]==FIRST.isoformat()


def test_conflicting_observation_does_not_partially_insert_new_rows(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        observe(reg,0,hit=True)
        updated=snapshot(FIRST,hit=False)
        with pytest.raises(ValueError,match="observation mutation"):
            reg.record_integrated(updated,clock=FIRST+timedelta(hours=1))
        counted=audit_watch_progression(path,market="KR",model_version=MODEL)
        assert counted["transition_counts"]["INITIAL_WATCH"]==1
        assert counted["transition_counts"]["SCREEN_WEAKENED"]==0
    finally:reg.close()


def test_backfilled_historical_run_excluded_from_prospective_transitions(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        historical=datetime(2024,6,1,8,tzinfo=timezone.utc)
        reg.record_integrated(snapshot(historical),clock=FIRST)
        observe(reg,0,security="SYN-A",hit=True)
    finally:reg.close()
    result=audit_watch_progression(path,market="KR",model_version=MODEL)
    assert result["excluded_retrospective_observations"]==1
    assert result["transition_counts"]["INITIAL_WATCH"]==1
    assert result["eligible_prospective_observations"]==1


def test_rehashed_payload_tampering_cannot_forge_an_observation(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try: observe(reg,0)
    finally:reg.close()
    with sqlite3.connect(path) as conn:
        obj=json.loads(conn.execute("SELECT payload FROM research_screen_observations").fetchone()[0])
        obj["company"]["security_id"]="FORGED"
        from hashlib import sha256
        payload=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        conn.execute("UPDATE research_screen_observations SET payload=?,payload_hash=?",
                     (payload,sha256(payload.encode()).hexdigest()))
    with pytest.raises(ValueError,match="payload identity"):
        audit_watch_progression(path,market="KR",model_version=MODEL)


def test_legacy_positive_registration_time_remains_anchored(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    report=snapshot(FIRST)
    try:
        reg.record_integrated(report,clock=FIRST)
    finally:reg.close()
    # Simulate a pre-upgrade database with original positive events and
    # no complete-screen observations.
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM research_screen_observations")
    reg=ProspectiveRegistry(path)
    try:
        assert reg.record_integrated(report,clock=FIRST+timedelta(days=3))[
            "new_research_observations"]==1
    finally:reg.close()
    out=audit_watch_progression(path,market="KR",model_version=MODEL)
    assert out["transition_event_sample"][0]["registered_at"]==FIRST.isoformat()


def test_us_timezone_and_sample_limit_never_infer_outcomes(tmp_path):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    try:
        observe(reg,0,market="US")
        observe(reg,1,market="US",hit=False)
    finally:reg.close()
    out=audit_watch_progression(path,market="US",model_version=MODEL,sample_limit=1)
    assert out["eligible_prospective_observations"]==2
    assert len(out["transition_event_sample"])==1
    assert out["leader_prediction_accuracy_certified"] is False


def test_cli_writes_derived_report_only_and_backup_is_safe(tmp_path,capsys):
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    root=tmp_path/"audit"
    root.mkdir()
    reg=ProspectiveRegistry(root/"prospective.sqlite")
    try:
        observe(reg,0)
        observe(reg,1,hit=False)
    finally:reg.close()
    derived=tmp_path/"derived"
    main(["audit-watch-progression","--ledger",str(root/"prospective.sqlite"),
          "--market","KR","--model-version",MODEL,"--out",str(derived)])
    printed=json.loads(capsys.readouterr().out)
    assert printed["prospective_observations"]==2
    assert printed["official_state_promotions"]==0
    report=json.loads((derived/"watch_progression_kr_research.json").read_text())
    assert report["transition_counts"]["SCREEN_WEAKENED"]==1
    assert report["pit_certified"] is False
    (derived/"original_private_prices.json").write_text('{"password":"NEVER_EXPORT"}')
    archive=tmp_path/"safe.zip"
    assert create_backup(derived,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert z.namelist()==["watch_progression_kr_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert (restored/"watch_progression_kr_research.json").is_file()
    assert not (restored/"original_private_prices.json").exists()


@pytest.mark.parametrize("kwargs",[
    {"market":"XX"},{"max_registration_lag_days":True},
    {"max_registration_lag_days":15},{"sample_limit":0},{"sample_limit":1.5},
    {"model_version":""},
])
def test_audit_rejects_invalid_parameters(tmp_path,kwargs):
    path=tmp_path/"prospective.sqlite"
    reg=ProspectiveRegistry(path)
    reg.close()
    defaults={"market":"KR","model_version":MODEL}
    defaults.update(kwargs)
    with pytest.raises(ValueError):
        audit_watch_progression(path,**defaults)
