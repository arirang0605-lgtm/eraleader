"""Synthetic first-at-write numeric ranking evidence; never real alpha/PIT."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import pytest

from eraleader.rank_score_ledger import register_rank_scores,audit_frozen_rank_scores
from eraleader.ranked_discovery import main as rank_cli
from eraleader.cli import main
from eraleader.local_backup import create_backup,verify_backup,restore_backup
from test_ranked_registry import make, STAMP, SNAPSHOT, MODEL

WRITE=STAMP+timedelta(minutes=2)


def setup(tmp_path, *, recorded_at=WRITE, members=("A","B"), market="KR"):
    tmp_path.mkdir(parents=True,exist_ok=True)
    ranking,watch=make(tmp_path,secs=members,market=market)
    folder=tmp_path/"input_features"
    folder.mkdir()
    items=[]
    for idx,sec in enumerate(members):
        file=folder/f"{sec}.json"
        available=(STAMP-timedelta(minutes=12)).isoformat()
        data={"schema":"eraleader.rank_feature_document.v1",
              "market":market,"model_version":MODEL,"security_id":sec,
              "available_at":available,
              "features":{"revenue_yoy":.44+idx/100,"industry_growth":.20}}
        raw=json.dumps(data,sort_keys=True).encode()
        file.write_bytes(raw)
        items.append({"security_id":sec,"score":float(90-10*idx),
                      "feature_file":file.name,
                      "feature_sha256":sha256(raw).hexdigest(),
                      "features_available_at":available})
    scores=tmp_path/"rank_score_inputs.json"
    scores.write_text(json.dumps(items),encoding="utf-8")
    db=tmp_path/"rank_scores.sqlite"
    return ranking,watch,folder,scores,db


def record(bundle,*,at=WRITE,model=MODEL):
    _,watch,features,scores,db=bundle
    return register_rank_scores(db,watch,features,scores,market="KR",
                                model_version=model,clock=at)


def test_first_numeric_scores_written_locally_and_linked_to_watch_and_rank(tmp_path):
    bundle=setup(tmp_path)
    first=record(bundle)
    assert first["new_score_records"]==2
    assert first["score_computation_independently_verified"] is False
    out=audit_frozen_rank_scores(bundle[0],bundle[4],bundle[2])
    assert out["ranked_candidate_count"]==2
    assert out["local_numeric_score_records_matched"]==2
    assert out["rank_score_preexisted_snapshot_locally"] is True
    assert out["blocker_count"]==0
    assert out["score_computation_independently_verified"] is False
    assert out["real_leader_prediction_certified"] is False
    with sqlite3.connect(bundle[4]) as con:
        payload=json.loads(con.execute("SELECT payload FROM rank_score_events LIMIT 1").fetchone()[0])
    assert payload["score_recorded_at_utc"]==WRITE.isoformat()
    assert payload["watch_registered_at_utc"]==STAMP.isoformat()
    assert payload["score"] in (90.0,80.0)
    assert "is_future_leader" not in json.dumps(payload)


def test_identical_rerun_keeps_actual_first_score_record_time(tmp_path):
    b=setup(tmp_path)
    assert record(b)["new_score_records"]==2
    next_result=record(b,at=WRITE+timedelta(minutes=10))
    assert next_result["new_score_records"]==0
    assert next_result["duplicate_score_records"]==2
    with sqlite3.connect(b[4]) as con:
        assert {json.loads(x[0])["score_recorded_at_utc"] for x in
                con.execute("SELECT payload FROM rank_score_events")}=={WRITE.isoformat()}


def test_score_restatement_is_rejected_atomically_and_previous_score_intact(tmp_path):
    b=setup(tmp_path)
    record(b)
    row=json.loads(b[3].read_text())
    row[1]["score"]=91
    b[3].write_text(json.dumps(row))
    with pytest.raises(ValueError,match="mutation rejected"):
        record(b,at=WRITE+timedelta(minutes=4))
    r=audit_frozen_rank_scores(b[0],b[4],b[2])
    assert r["blocker_count"]==0 and r["local_numeric_score_records_matched"]==2


def test_feature_source_mutation_is_blocked_at_registration(tmp_path):
    b=setup(tmp_path)
    (b[2]/"A.json").write_text('{"modified":"after_source_claim"}')
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        record(b)
    assert not b[4].exists()


def test_source_mutation_after_recording_blocks_frozen_rank(tmp_path):
    b=setup(tmp_path)
    record(b)
    (b[2]/"A.json").write_text('{"modified":"after_recording"}')
    result=audit_frozen_rank_scores(b[0],b[4],b[2])
    assert "A:SOURCE_FEATURE_BYTES_REVISED" in result["blockers"]
    assert result["local_numeric_score_records_matched"]==1


def test_unregistered_numeric_score_cannot_forge_watch_backfill(tmp_path):
    b=setup(tmp_path)
    with sqlite3.connect(b[1]) as con:
        con.execute("DELETE FROM prospective_signals WHERE security_id='A'")
    with pytest.raises(ValueError,match="No eligible"):
        record(b)
    assert not b[4].exists()


def test_wrong_model_version_never_borrows_other_model_watch(tmp_path):
    b=setup(tmp_path)
    with pytest.raises(ValueError,match="Feature evidence identity/schema mismatch"):
        record(b,model="another-model")
    assert not b[4].exists()


def test_late_first_scoring_cannot_be_retroactively_credited(tmp_path):
    b=setup(tmp_path)
    with pytest.raises(ValueError,match="too late"):
        record(b,at=STAMP+timedelta(hours=4))
    assert not b[4].exists()


def test_feature_claimed_available_after_score_event_is_rejected(tmp_path):
    b=setup(tmp_path)
    rows=json.loads(b[3].read_text())
    rows[0]["features_available_at"]=(WRITE+timedelta(days=1)).isoformat()
    b[3].write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="Feature evidence identity/schema"):
        record(b)
    assert not b[4].exists()


def test_future_outcome_like_metric_name_rejected(tmp_path):
    b=setup(tmp_path)
    source=b[2]/"A.json"
    value=json.loads(source.read_text())
    value["features"]["future_outcome_winner"]=1
    blob=json.dumps(value,sort_keys=True).encode()
    source.write_bytes(blob)
    rows=json.loads(b[3].read_text())
    rows[0]["feature_sha256"]=sha256(blob).hexdigest()
    b[3].write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="Forbidden future"):
        record(b)


def test_existing_event_hash_corruption_rejected_not_overwritten(tmp_path):
    b=setup(tmp_path)
    record(b)
    with sqlite3.connect(b[4]) as con:
        con.execute("UPDATE rank_score_events SET evidence_hash=? WHERE security_id='A'",
                    ("f"*64,))
    with pytest.raises(ValueError,match="corrupted"):
        record(b,at=WRITE+timedelta(minutes=1))
    with pytest.raises(ValueError,match="hash"):
        audit_frozen_rank_scores(b[0],b[4],b[2])


def test_missing_numeric_rank_score_blocks_without_fabrication(tmp_path):
    b=setup(tmp_path)
    record(b)
    with sqlite3.connect(b[4]) as con:
        con.execute("DELETE FROM rank_score_events WHERE security_id='B'")
    result=audit_frozen_rank_scores(b[0],b[4],b[2])
    assert "B:MISSING_CONTEMPORANEOUS_NUMERIC_SCORE_OBSERVATION" in result["blockers"]
    assert result["local_numeric_score_records_matched"]==1


def test_postdated_numeric_score_can_never_be_said_preexisting_at_rank_time(tmp_path):
    b=setup(tmp_path)
    # Score is recorded 8 minutes after first WATCH, while the previously
    # frozen research snapshot had an earlier 5-minute cutoff.
    record(b,at=STAMP+timedelta(minutes=8))
    report=audit_frozen_rank_scores(b[0],b[4],b[2])
    assert report["local_numeric_score_records_matched"]==0
    assert any("NUMERIC_SCORE_REGISTERED_AFTER_RANK_SNAPSHOT" in x
               for x in report["blockers"])


def test_guarded_rank_freeze_accepts_score_ledger_and_rejects_missing(tmp_path,capsys):
    b=setup(tmp_path)
    record(b)
    good=tmp_path/"sealed_registry_and_score.json"
    args=["freeze","--input",str(tmp_path/"scores.json"),
          "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
          "--model-version",MODEL,"--horizon-days","180","--k","1",
          "--prospective-ledger",str(b[1]),"--score-ledger",str(b[4]),
          "--features-dir",str(b[2])]
    assert rank_cli(args+["--out",str(good)])==0
    capsys.readouterr()
    assert good.is_file()
    with sqlite3.connect(b[4]) as con:
        con.execute("DELETE FROM rank_score_events WHERE security_id='A'")
    bad=tmp_path/"bad_score_freeze.json"
    with pytest.raises(ValueError,match="score ledger preflight failed"):
        rank_cli(args+["--out",str(bad)])
    assert not bad.exists()


@pytest.mark.parametrize("extra",[
    ["--score-ledger","some.sqlite"],
    ["--features-dir","features"],
    ["--score-ledger","some.sqlite","--features-dir","features"],
])
def test_guarded_rank_freeze_requires_complete_options(tmp_path,extra):
    b=setup(tmp_path)
    with pytest.raises(ValueError,match="requires|supplied together"):
        rank_cli(["freeze","--input",str(tmp_path/"scores.json"),
                  "--market","KR","--snapshot-at",SNAPSHOT.isoformat(),
                  "--model-version",MODEL,"--horizon-days","180","--k","1",
                  "--out",str(tmp_path/"cannot_publish.json")]+extra)
    assert not (tmp_path/"cannot_publish.json").exists()


def test_cli_audit_and_safe_derived_json_backup(tmp_path,capsys):
    b=setup(tmp_path)
    record(b)
    out=tmp_path/"reports"
    main(["audit-rank-scores","--frozen-rank",str(b[0]),
          "--score-ledger",str(b[4]),"--features-dir",str(b[2]),
          "--out",str(out)])
    answer=json.loads(capsys.readouterr().out)
    assert answer["matched"]==2
    assert answer["real_leader_prediction_certified"] is False
    (out/"raw_labels.json").write_text('{"secret":"KEEP_OUT"}')
    archive=tmp_path/"rank_score_safe.zip"
    assert create_backup(out,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    restored=tmp_path/"restore"
    restore_backup(archive,restored)
    assert (restored/"rank_score_kr_research.json").exists()
    assert not (restored/"raw_labels.json").exists()


def test_record_rank_scores_cli_stamps_real_current_time_without_backdating(tmp_path,capsys):
    from eraleader.prospective import ProspectiveRegistry
    from test_ranked_registry import run
    actual=datetime.now(timezone.utc)
    watched=actual-timedelta(seconds=5)
    model="cli-live-os-clock-synthetic"
    watch_db=tmp_path/"prospective.sqlite"
    watch=ProspectiveRegistry(watch_db)
    try:
        watch.record_integrated(run(["SYN-CLOCK"],market="KR",model=model,
                                    observed=watched.isoformat()),clock=watched)
    finally:watch.close()
    feature_dir=tmp_path/"features"
    feature_dir.mkdir()
    evidence={
        "schema":"eraleader.rank_feature_document.v1",
        "security_id":"SYN-CLOCK","market":"KR","model_version":model,
        "available_at":(actual-timedelta(minutes=15)).isoformat(),
        "features":{"growth_yoy":0.3}}
    blob=json.dumps(evidence).encode()
    (feature_dir/"cli_feature.json").write_bytes(blob)
    supplied=[{"security_id":"SYN-CLOCK","score":85.0,
        "features_available_at":evidence["available_at"],"feature_file":"cli_feature.json",
        "feature_sha256":sha256(blob).hexdigest()}]
    supplied_file=tmp_path/"supplied_scores.json"
    supplied_file.write_text(json.dumps(supplied))
    score_db=tmp_path/"score.sqlite"
    main(["record-rank-scores","--market","KR","--model-version",model,
          "--scores",str(supplied_file),"--features-dir",str(feature_dir),
          "--watch-ledger",str(watch_db),"--score-ledger",str(score_db)])
    response=json.loads(capsys.readouterr().out)
    first_recorded=datetime.fromisoformat(response["score_recorded_at_utc"])
    assert actual<=first_recorded<=datetime.now(timezone.utc)
    assert response["new_score_records"]==1
    # A real, after-registration rank snapshot can now cite the write event.
    rank_input=[{
        "security_id":"SYN-CLOCK","score":85.0,
        "features_available_at":evidence["available_at"],
        "score_computed_at":(watched-timedelta(seconds=2)).isoformat(),
        "recorded_at":watched.isoformat(),
    }]
    rank_source=tmp_path/"ranking_input.json"
    rank_source.write_text(json.dumps(rank_input))
    rank_final=tmp_path/"rank_sealed_after_registration.json"
    assert rank_cli([
        "freeze","--input",str(rank_source),"--market","KR",
        "--snapshot-at",datetime.now(timezone.utc).isoformat(),
        "--model-version",model,"--horizon-days","180","--k","1",
        "--prospective-ledger",str(watch_db),"--score-ledger",str(score_db),
        "--features-dir",str(feature_dir),"--out",str(rank_final)
    ])==0
    capsys.readouterr()
    assert audit_frozen_rank_scores(rank_final,score_db,feature_dir)["blocker_count"]==0
