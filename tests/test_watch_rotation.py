"""Synthetic prospective peer WATCH rotation detection; never verified leaders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.watch_rotation import audit_watch_rotation
from test_watch_progression import snapshot, MODEL

START = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
EVAL = "2026-10-09T00:00:00Z"
CLOCK = datetime(2026, 10, 11, tzinfo=timezone.utc)


def record(db, offset, *, sec, hit, industry="SEMICON", recorded_offset=None,
           market="KR", model=MODEL):
    observed = START + timedelta(days=offset)
    payload = snapshot(observed,security=sec,hit=hit,market=market)
    payload["version"] = model
    payload["company_rows"][0]["industry_id"] = industry
    clock = observed if recorded_offset is None else START + timedelta(days=recorded_offset)
    return db.record_integrated(payload,clock=clock)


def planted(tmp_path, *, save_more=None):
    path = tmp_path / "prospective.sqlite"
    db = ProspectiveRegistry(path)
    try:
        record(db,0,sec="INC",hit=True)
        record(db,1,sec="INC",hit=True)
        record(db,2,sec="INC",hit=False)
        record(db,3,sec="INC",hit=False)
        record(db,2.5,sec="NEW",hit=True)
        record(db,3.5,sec="NEW",hit=True)
        if save_more:
            save_more(db)
    finally:
        db.close()
    return path


def audit(path, **kwargs):
    return audit_watch_rotation(path,market="KR",model_version=MODEL,
                                evaluated_at=EVAL,clock=CLOCK,**kwargs)


def test_two_confirmed_explicit_weaknesses_and_first_two_new_hits_are_a_hypothesis(tmp_path):
    report=audit(planted(tmp_path))
    assert report["rotation_hypothesis_count"]==1
    event=report["hypothesis_sample"][0]
    assert event["incumbent_security_id"]=="INC"
    assert event["contender_security_id"]=="NEW"
    assert event["industry_id"]=="SEMICON"
    assert event["kind"]=="RESEARCH_PEER_WATCH_REPLACEMENT_HYPOTHESIS"
    assert report["eligible_observation_count"]==6
    assert report["market"]=="KR" and report["model_version"]==MODEL
    assert report["official_leader_replacements"]==0
    assert report["historic_pit_certified"] is False
    assert report["actual_prediction_accuracy_certified"] is False


@pytest.mark.parametrize("bad_case",[
    "no_second_negative", "incumbent_reentered",
    "no_second_new_hit", "contender_old_watch",
    "missing_industry", "different_industry",
    "sector_reclassified",
])
def test_insufficient_or_ambiguous_evidence_must_not_emit_rotation(tmp_path,bad_case):
    path=tmp_path/"ledger.sqlite"
    db=ProspectiveRegistry(path)
    try:
        record(db,0,sec="INC",hit=True)
        record(db,1,sec="INC",hit=True)
        record(db,2,sec="INC",hit=False)
        if bad_case!="no_second_negative":
            record(db,3,sec="INC",hit=False)
        if bad_case=="incumbent_reentered":
            record(db,4,sec="INC",hit=True)
        if bad_case=="contender_old_watch":
            record(db,1,sec="NEW",hit=True)
        elif bad_case=="missing_industry":
            record(db,2.5,sec="NEW",hit=True,industry=None)
        else:
            record(db,2.5,sec="NEW",hit=True,
                   industry="BIO" if bad_case=="different_industry" else "SEMICON")
        if bad_case not in ("no_second_new_hit",):
            record(db,3.5,sec="NEW",hit=True,
                   industry=("BIO" if bad_case in ("different_industry","sector_reclassified") else "SEMICON"))
    finally:
        db.close()
    report=audit(path)
    assert report["rotation_hypothesis_count"]==0
    assert report["official_leader_replacements"]==0


def test_candidate_absent_from_a_run_does_not_create_negative_observation(tmp_path):
    path=tmp_path/"ledger.sqlite"
    db=ProspectiveRegistry(path)
    try:
        record(db,0,sec="INC",hit=True)
        record(db,1,sec="INC",hit=True)
        record(db,2,sec="NEW",hit=True)
        record(db,3,sec="NEW",hit=True)
    finally: db.close()
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0
    assert r["excluded_hindsight_or_backfill_count"]==0


def test_future_observation_after_evaluation_is_not_retrospective_evidence(tmp_path):
    path=planted(tmp_path)
    report=audit_watch_rotation(path,market="KR",model_version=MODEL,
                   evaluated_at="2026-10-04T00:00:00Z",clock=CLOCK)
    assert report["rotation_hypothesis_count"]==0
    assert report["excluded_future_registered_count"]>=1


def test_backfilled_new_candidate_cannot_create_prospective_rotation(tmp_path):
    path=tmp_path/"ledger.sqlite"
    db=ProspectiveRegistry(path)
    try:
        record(db,0,sec="INC",hit=True)
        record(db,1,sec="INC",hit=True)
        record(db,2,sec="INC",hit=False)
        record(db,3,sec="INC",hit=False)
        record(db,2.5,sec="NEW",hit=True,recorded_offset=7)
        record(db,3.5,sec="NEW",hit=True,recorded_offset=7.1)
    finally:db.close()
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0
    assert r["excluded_hindsight_or_backfill_count"]>=1


def test_dual_snapshot_replay_at_same_recorded_instant_cannot_confirm_twice(tmp_path):
    path=tmp_path/"ledger.sqlite"
    db=ProspectiveRegistry(path)
    try:
        record(db,0,sec="INC",hit=True)
        record(db,1,sec="INC",hit=True)
        record(db,2,sec="INC",hit=False)
        record(db,3,sec="INC",hit=False)
        record(db,2.5,sec="NEW",hit=True,recorded_offset=4)
        record(db,3.5,sec="NEW",hit=True,recorded_offset=4)
    finally:db.close()
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0


def test_broken_canonical_payload_is_not_considered_reliable(tmp_path):
    path=planted(tmp_path)
    con=sqlite3.connect(path)
    try:
        con.execute("UPDATE research_screen_observations SET screen_hit=0 WHERE security_id='NEW'")
        con.commit()
    finally:
        con.close()
    with pytest.raises(ValueError,match="payload|hit|mismatch"):
        audit(path)


def test_future_cutoff_and_missing_ledger_fail_closed(tmp_path):
    with pytest.raises(ValueError,match="future"):
        audit_watch_rotation(planted(tmp_path),market="KR",model_version=MODEL,
                             evaluated_at="2027-01-01T00:00:00Z",clock=CLOCK)
    with pytest.raises(ValueError,match="ledger|missing"):
        audit(tmp_path/"absent.sqlite")


def test_market_and_model_isolation(tmp_path):
    path=planted(tmp_path)
    r=audit_watch_rotation(path,market="US",model_version=MODEL,
                          evaluated_at=EVAL,clock=CLOCK)
    assert r["rotation_hypothesis_count"]==0
    r=audit_watch_rotation(path,market="KR",model_version="other-model",
                          evaluated_at=EVAL,clock=CLOCK)
    assert r["rotation_hypothesis_count"]==0


def test_new_contender_with_explicit_weakness_between_watches_is_not_continuous(tmp_path):
    path=planted(tmp_path,save_more=lambda db:[
        record(db,4,sec="NEW",hit=False),
        record(db,5,sec="NEW",hit=True),
        record(db,6,sec="NEW",hit=True),
    ])
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0


def test_incumbent_watch_from_many_months_ago_is_not_current_sector_incumbent(tmp_path):
    path=tmp_path/"ledger.sqlite"
    db=ProspectiveRegistry(path)
    try:
        record(db,-90,sec="INC",hit=True)
        record(db,-88,sec="INC",hit=True)
        record(db,2,sec="INC",hit=False)
        record(db,3,sec="INC",hit=False)
        record(db,2.5,sec="NEW",hit=True)
        record(db,3.5,sec="NEW",hit=True)
    finally:db.close()
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0


def test_us_dst_march_transition_keeps_utc_order_and_industry(tmp_path):
    path=tmp_path/"us.sqlite"
    reg=ProspectiveRegistry(path)
    def watch(sec, when, hit):
        t=datetime.fromisoformat(when)
        row=snapshot(t,security=sec,market="US",hit=hit)
        row["company_rows"][0]["industry_id"]="SEMICON"
        reg.record_integrated(row,clock=t)
    try:
        watch("US-INC","2026-03-05T16:00:00-05:00",True)
        watch("US-INC","2026-03-06T16:00:00-05:00",True)
        watch("US-INC","2026-03-09T16:00:00-04:00",False)
        watch("US-INC","2026-03-10T16:00:00-04:00",False)
        watch("US-NEW","2026-03-09T17:00:00-04:00",True)
        watch("US-NEW","2026-03-10T17:00:00-04:00",True)
    finally:
        reg.close()
    r=audit_watch_rotation(path,market="US",model_version=MODEL,
                           evaluated_at="2026-03-12T17:00:00-04:00",clock=CLOCK)
    assert r["rotation_hypothesis_count"]==1
    assert r["hypothesis_sample"][0]["contender_security_id"]=="US-NEW"
    assert r["official_leader_replacements"]==0


def test_standalone_cli_writes_sanitized_once_and_does_not_mutate_ledger(tmp_path,capsys):
    from eraleader.watch_rotation import main
    path=planted(tmp_path)
    digest=__import__("hashlib").sha256(path.read_bytes()).hexdigest()
    file=tmp_path/"output"/"rotation.json"
    args=["--ledger",str(path),"--market","KR",
          "--model-version",MODEL,"--evaluated-at",EVAL,"--out",str(file)]
    assert main(args)==0
    output=json.loads(file.read_text())
    assert output["rotation_hypothesis_count"]==1
    assert output["actual_prediction_accuracy_certified"] is False
    assert "payload" not in file.read_text()
    assert __import__("hashlib").sha256(path.read_bytes()).hexdigest()==digest
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code==2


def test_project_cli_outputs_only_derived_rotation_hypotheses(tmp_path,capsys):
    from eraleader.cli import main
    path=planted(tmp_path)
    folder=tmp_path/"research"
    main(["audit-watch-rotation","--ledger",str(path),"--market","KR",
          "--model-version",MODEL,"--evaluated-at",EVAL,"--out",str(folder)])
    printed=json.loads(capsys.readouterr().out)
    report=json.loads((folder/"watch_rotation_kr_research.json").read_text())
    assert printed["rotation_hypothesis_count"]==1
    assert printed["official_leader_replacements"]==0
    assert report["rotation_hypothesis_count"]==1
    assert "provenances" not in json.dumps(report)
    assert report["historic_pit_certified"] is False


def test_safe_derived_backup_restores_rotation_without_watch_ledger(tmp_path):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    path=planted(tmp_path)
    derived=tmp_path/"derived"
    main(["audit-watch-rotation","--ledger",str(path),"--market","KR",
          "--model-version",MODEL,"--evaluated-at",EVAL,"--out",str(derived)])
    archive=tmp_path/"rotation_research.zip"
    info=create_backup(derived,archive)
    assert info["file_count"]==2
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert "prospective.sqlite" not in z.namelist()
        assert sorted(z.namelist())==sorted(["watch_rotation_kr_research.json",
            "site/watch_rotation_kr.html","MANIFEST.json"])
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert (restored/"watch_rotation_kr_research.json").read_bytes()==(
        derived/"watch_rotation_kr_research.json").read_bytes()
    assert (restored/"site"/"watch_rotation_kr.html").read_bytes()==(
        derived/"site"/"watch_rotation_kr.html").read_bytes()


def test_missing_industry_field_from_legacy_watch_is_not_joined_to_peer(tmp_path):
    path=tmp_path/"legacy.sqlite"
    db=ProspectiveRegistry(path)
    try:
        for offset,hit in [(0,True),(1,True),(2,False),(3,False)]:
            payload=snapshot(START+timedelta(days=offset),security="INC",hit=hit)
            db.record_integrated(payload,clock=START+timedelta(days=offset))
        record(db,2.5,sec="NEW",hit=True)
        record(db,3.5,sec="NEW",hit=True)
    finally:db.close()
    r=audit(path)
    assert r["rotation_hypothesis_count"]==0
    assert r["excluded_unassigned_industry_securities"]==1


def test_symlinked_research_ledger_not_followed(tmp_path):
    path=planted(tmp_path)
    link=tmp_path/"alias.sqlite"
    link.symlink_to(path)
    with pytest.raises(ValueError,match="symlinked"):
        audit(link)


def test_snapshot_clock_naive_rejected(tmp_path):
    path=planted(tmp_path)
    with pytest.raises(ValueError,match="timezone"):
        audit_watch_rotation(path,market="KR",model_version=MODEL,
                             evaluated_at=EVAL,clock=datetime(2026,10,11))


def test_readonly_watch_rotation_html_shows_hypotheses_not_official_promotions(tmp_path):
    from eraleader.delivery import render_watch_rotation_dashboard
    report=audit(planted(tmp_path))
    html=render_watch_rotation_dashboard(report)
    assert "WATCH 교체 후보" in html
    assert "확정 대장주 0건" in html
    assert "INC" in html and "NEW" in html
    assert "SEMICON" in html
    assert "투자 추천이 아닙니다" in html


def test_rotation_dashboard_escapes_issuer_industry_html_and_rejects_fake_certification(tmp_path):
    from eraleader.delivery import render_watch_rotation_dashboard
    report=audit(planted(tmp_path))
    entry=report["hypothesis_sample"][0]
    entry["industry_id"]='<img src=x onerror="alert(1)">'
    html=render_watch_rotation_dashboard(report)
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html
    report["official_leader_replacements"]=1
    with pytest.raises(ValueError,match="certif|official|promotion|research"):
        render_watch_rotation_dashboard(report)
    report["official_leader_replacements"]=0
    report["actual_prediction_accuracy_certified"]=True
    with pytest.raises(ValueError,match="certif|official|promotion|research"):
        render_watch_rotation_dashboard(report)


def test_rotation_dashboard_rejects_inconsistent_or_forged_counts(tmp_path):
    from eraleader.delivery import render_watch_rotation_dashboard
    report=audit(planted(tmp_path))
    report["rotation_hypothesis_count"]=0
    with pytest.raises(ValueError,match="count|sample"):
        render_watch_rotation_dashboard(report)
    report["rotation_hypothesis_count"]=1
    report["hypothesis_sample"][0]["kind"]="OFFICIALLY_CONFIRMED"
    with pytest.raises(ValueError,match="kind|sample"):
        render_watch_rotation_dashboard(report)
