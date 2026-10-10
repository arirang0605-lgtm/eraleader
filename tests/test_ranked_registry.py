"""Cross-check pinned ranked top-K against the original prospective WATCH ledger.

All times are injected synthetic fixtures; no provider source or score is
independently authenticated. Never call this verified leader prediction.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json
import sqlite3
import pytest

from eraleader.prospective import ProspectiveRegistry
from eraleader.ranked_discovery import freeze_ranked_snapshot
from eraleader.ranked_registry import audit_ranked_watch_registry
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from eraleader.cli import main

STAMP=datetime(2026,4,2,8,tzinfo=timezone.utc)
SNAPSHOT=STAMP+timedelta(minutes=5)
FREEZE=SNAPSHOT+timedelta(minutes=1)
OBSERVED="2026-04-02T11:00:00+09:00"
MODEL="synthetic-real-registration-v1"


def run(secs, *, model=MODEL, observed=OBSERVED, market="KR", hit=True):
    return {"market":market,"as_of":observed,"version":model,
            "run_id":"synthetic-"+model+"-"+",".join(secs),
            "pit_certified":False,"offline_provenance":["synthetic_fixture"],
            "company_rows":[{
                "security_id":sec,"market":market,"as_of":observed,
                "state":"WATCH","full_score":None,
                "verified_future_leader_candidate":False,
                "research_growth_screen_hit":hit,
            } for sec in secs]}


def make(tmp_path, *, secs=("A","B"), ranked_secs=None, market="KR",
         model=MODEL, registration=STAMP, observed=OBSERVED,
         scores=None, ranked_recorded=None, rank_model=None, freeze_at=FREEZE):
    path=tmp_path/"prospective.sqlite"
    registry=ProspectiveRegistry(path)
    try:
        registry.record_integrated(run(secs,model=model,observed=observed,market=market),
                                   clock=registration)
    finally:
        registry.close()
    if ranked_secs is None:
        ranked_secs=secs
    if scores is None:
        scores={sid:90-10*i for i,sid in enumerate(ranked_secs)}
    recorded=ranked_recorded or registration
    inputs=[{
        "security_id":s,"score":scores[s],
        "features_available_at":(recorded-timedelta(minutes=10)).isoformat(),
        "score_computed_at":(recorded-timedelta(minutes=5)).isoformat(),
        "recorded_at":recorded.isoformat(),
    } for s in ranked_secs]
    score_file=tmp_path/"scores.json"
    score_file.write_text(json.dumps(inputs),encoding="utf-8")
    freeze_file=tmp_path/"ranking.json"
    freeze_ranked_snapshot(score_file,freeze_file,market=market,
                           snapshot_at=(registration+timedelta(minutes=5)).isoformat(),
                           model_version=rank_model or model,horizon_days=180,k=1,
                           clock=freeze_at)
    return freeze_file,path


def test_exact_watch_id_first_timestamp_link_but_numeric_score_still_unproven(tmp_path):
    frozen,ledger=make(tmp_path)
    before=sha256(ledger.read_bytes()).hexdigest()
    audit=audit_ranked_watch_registry(frozen,ledger)
    assert audit["ranked_candidate_count"]==2
    assert audit["requested_k"]==1
    assert audit["ranked_ids_and_first_timestamps_matched"]==2
    assert audit["blocker_count"]==0
    assert audit["rank_ids_and_registration_dates_locally_consistent"] is True
    assert audit["original_watch_has_independently_recorded_numeric_score"] is False
    assert audit["rank_score_availability_independently_attested"] is False
    assert audit["prospective_discovery_skill_certified"] is False
    assert audit["official_leader_promotions"]==0
    assert audit["candidate_sample"][0]["top_k_selected"] is True
    assert sha256(ledger.read_bytes()).hexdigest()==before


def test_unknown_ranked_candidate_is_blocked_not_created(tmp_path):
    f,db=make(tmp_path,ranked_secs=("A","Z"),scores={"A":90,"Z":85})
    audit=audit_ranked_watch_registry(f,db)
    assert audit["ranked_ids_and_first_timestamps_matched"]==1
    assert "Z:NO_ELIGIBLE_REGISTERED_WATCH_FOR_PINNED_MODEL" in audit["blockers"]


def test_rank_recorded_earlier_than_first_positive_watch_is_not_backdated(tmp_path):
    f,db=make(tmp_path,ranked_recorded=STAMP-timedelta(minutes=2))
    audit=audit_ranked_watch_registry(f,db)
    assert audit["ranked_ids_and_first_timestamps_matched"]==0
    assert all("RANK_TIMESTAMP_DIFFERS" in x for x in audit["blockers"])


def test_wrong_model_version_never_borrows_other_model_watch(tmp_path):
    f,db=make(tmp_path,rank_model="unregistered_model-v99")
    r=audit_ranked_watch_registry(f,db)
    assert r["blocker_count"]==2
    assert r["ranked_ids_and_first_timestamps_matched"]==0


def test_positive_register_from_old_data_cannot_become_fresh(tmp_path):
    f,db=make(tmp_path,observed="2024-01-01T11:00:00+09:00")
    r=audit_ranked_watch_registry(f,db)
    assert r["historical_backfill_records_excluded"]==2
    assert r["ranked_ids_and_first_timestamps_matched"]==0
    assert r["blocker_count"]==2


def test_missing_then_belated_signal_cannot_appear_in_preexisting_rank(tmp_path):
    f,db=make(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM prospective_signals WHERE security_id='A'")
    r=audit_ranked_watch_registry(f,db)
    assert r["ranked_ids_and_first_timestamps_matched"]==1
    assert "A:NO_ELIGIBLE_REGISTERED_WATCH_FOR_PINNED_MODEL" in r["blockers"]


def test_payload_checksum_corruption_is_fatal(tmp_path):
    f,db=make(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE prospective_signals SET payload='{}'")
    with pytest.raises(ValueError,match="checksum"):
        audit_ranked_watch_registry(f,db)


def test_rehashed_payload_forgery_still_fails_identity_check(tmp_path):
    f,db=make(tmp_path)
    with sqlite3.connect(db) as conn:
        source=conn.execute("SELECT payload FROM prospective_signals LIMIT 1").fetchone()[0]
        record=json.loads(source)
        record["company"]["full_score"]=100
        rewritten=json.dumps(record,ensure_ascii=False,sort_keys=True,
                             separators=(",",":"))
        conn.execute("UPDATE prospective_signals SET payload=?,payload_hash=?",
                     (rewritten,sha256(rewritten.encode()).hexdigest()))
    with pytest.raises(ValueError,match="identity mismatch"):
        audit_ranked_watch_registry(f,db)


def test_original_watch_signal_id_replacement_rejected(tmp_path):
    f,db=make(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE prospective_signals SET signal_id=? WHERE security_id='A'",
                     ("f"*64,))
    with pytest.raises(ValueError,match="ID"):
        audit_ranked_watch_registry(f,db)


def test_ranked_hash_tamper_rejected(tmp_path):
    f,db=make(tmp_path)
    data=json.loads(f.read_text())
    data["ranked_candidates"][0]["score"]=1
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="SHA256"):
        audit_ranked_watch_registry(f,db)


def test_ranked_symlink_and_missing_registry_fails_closed(tmp_path):
    f,db=make(tmp_path)
    real=db.with_name("original.sqlite")
    db.rename(real)
    db.symlink_to(real)
    with pytest.raises(ValueError,match="symlinked"):
        audit_ranked_watch_registry(f,db)
    db.unlink()
    with pytest.raises(ValueError,match="Missing"):
        audit_ranked_watch_registry(f,db)


def test_US_market_local_DST_registration_never_borrows_KR_ledger(tmp_path):
    observed="2026-03-08T01:30:00-05:00"
    stamp=datetime(2026,3,8,7,tzinfo=timezone.utc)
    f,db=make(tmp_path,market="US",observed=observed,registration=stamp,
              freeze_at=stamp+timedelta(minutes=6))
    r=audit_ranked_watch_registry(f,db)
    assert r["market"]=="US" and r["ranked_ids_and_first_timestamps_matched"]==2
    assert r["historical_backfill_records_excluded"]==0


def test_ranked_retrospective_freeze_does_not_claim_prospective_skill(tmp_path):
    f,db=make(tmp_path,freeze_at=STAMP+timedelta(days=12))
    r=audit_ranked_watch_registry(f,db)
    assert r["retrospective_freeze"] is True
    assert r["rank_ids_and_registration_dates_locally_consistent"] is True
    assert r["prospective_discovery_skill_certified"] is False


def test_cli_result_and_derived_only_backup_restore(tmp_path,capsys):
    frozen,db=make(tmp_path/"source")
    out=tmp_path/"safe"
    main(["audit-ranked-registry","--frozen-rank",str(frozen),
          "--ledger",str(db),"--out",str(out)])
    response=json.loads(capsys.readouterr().out)
    assert response["matched"]==2 and response["blocker_count"]==0
    assert response["prospective_discovery_skill_certified"] is False
    result=json.loads(Path(response["path"]).read_text())
    assert result["original_watch_has_independently_recorded_numeric_score"] is False
    (out/"original_future_labels.json").write_text('{"private_secret":"NEVER"}')
    archive=tmp_path/"backup.zip"
    assert create_backup(out,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipped:
        assert zipped.namelist()==["ranked_registry_kr_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert json.loads((restored/"ranked_registry_kr_research.json").read_text())==result
    assert not (restored/"original_future_labels.json").exists()


def test_freeze_cli_optin_registry_passes_only_locally_linked_watch(tmp_path,capsys):
    from eraleader.ranked_discovery import main as ranking_cli, _frozen
    f,db=make(tmp_path)
    out=tmp_path/"sealed_with_registry.json"
    assert ranking_cli([
        "freeze","--input",str(tmp_path/"scores.json"),
        "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
        "--model-version",MODEL,"--horizon-days","180","--k","1",
        "--prospective-ledger",str(db),"--out",str(out)])==0
    capsys.readouterr()
    sealed=_frozen(out)
    assert [x["security_id"] for x in sealed["ranked_candidates"]]==["A","B"]
    assert sealed["source_pit_independently_authenticated"] is False
    assert sealed["real_leader_prediction_certified"] is False
    # Normal O_EXCL freeze behavior still disallows overwriting a prior seal.
    with pytest.raises(FileExistsError):
        ranking_cli(["freeze","--input",str(tmp_path/"scores.json"),
                     "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
                     "--model-version",MODEL,"--horizon-days","180","--k","1",
                     "--prospective-ledger",str(db),"--out",str(out)])


def test_freeze_cli_rejects_unregistered_score_without_creating_final_file(tmp_path):
    from eraleader.ranked_discovery import main as ranking_cli
    _,db=make(tmp_path)
    rows=json.loads((tmp_path/"scores.json").read_text())
    rows.append({**rows[0],"security_id":"NEVER-REGISTERED"})
    (tmp_path/"scores.json").write_text(json.dumps(rows))
    out=tmp_path/"bad_rank_seal.json"
    with pytest.raises(ValueError,match="preflight failed"):
        ranking_cli(["freeze","--input",str(tmp_path/"scores.json"),
                     "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
                     "--model-version",MODEL,"--horizon-days","180","--k","1",
                     "--prospective-ledger",str(db),"--out",str(out)])
    assert not out.exists()


def test_freeze_cli_rejects_model_mismatch_without_creating_final_file(tmp_path):
    from eraleader.ranked_discovery import main as ranking_cli
    _,db=make(tmp_path)
    target=tmp_path/"wrong_model_seal.json"
    with pytest.raises(ValueError,match="preflight failed"):
        ranking_cli(["freeze","--input",str(tmp_path/"scores.json"),
                     "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
                     "--model-version","unknown-new-model","--horizon-days","180",
                     "--k","1","--prospective-ledger",str(db),"--out",str(target)])
    assert not target.exists()


def test_freeze_cli_default_standalone_research_behavior_is_preserved(tmp_path,capsys):
    from eraleader.ranked_discovery import main as ranking_cli, _frozen
    _,db=make(tmp_path)
    target=tmp_path/"standalone_research_seal.json"
    assert ranking_cli(["freeze","--input",str(tmp_path/"scores.json"),
                       "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
                       "--model-version",MODEL,"--horizon-days","180","--k","1",
                       "--out",str(target)])==0
    capsys.readouterr()
    assert _frozen(target)["real_leader_prediction_certified"] is False
