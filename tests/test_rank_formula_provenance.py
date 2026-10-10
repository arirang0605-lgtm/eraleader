"""Pin locally computed four-factor formula claims in immutable rank events.

Time-injected fixtures are retrospective simulations, NOT real prospective
ranking performance or authenticated source publication times.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from zipfile import ZipFile
import pytest

from eraleader.rank_score_pipeline import (
    compute_and_register_rank_scores, audit_computed_rank_provenance,
    formula_provenance, HEURISTIC_VERSION,
)
from eraleader.rank_score_ledger import register_rank_scores
from eraleader.ranked_discovery import freeze_ranked_snapshot, main as rank_cli
from eraleader.cli import main
from eraleader.local_backup import create_backup,verify_backup,restore_backup
from test_rank_score_pipeline import bundle, MODEL, WRITE, STAMP


def prepared(tmp_path, *, native=True):
    b=bundle(tmp_path)
    if native:
        created=compute_and_register_rank_scores(b[2],b[1],b[4],market="KR",
                                                 model_version=MODEL,clock=WRITE)
        assert created["new_score_records"]==2
        assert created["formula_provenance_sha256"]==formula_provenance()["formula_sha256"]
    else:
        docs=[]
        for sec,n in (("A",100.0),("B",50.0)):
            source=b[2]/f"{sec}.json"
            original=json.loads(source.read_text())
            docs.append({
                "security_id":sec,"score":n,
                "feature_file":source.name,
                "feature_sha256":sha256(source.read_bytes()).hexdigest(),
                "features_available_at":original["available_at"],
            })
        candidates=b[0].parent/"external_scores.json"
        candidates.write_text(json.dumps(docs))
        register_rank_scores(b[4],b[1],b[2],candidates,market="KR",
                             model_version=MODEL,clock=WRITE)
    candidates=[]
    for sid,score in (("A",100.0),("B",50.0)):
        doc=json.loads((b[2]/f"{sid}.json").read_text())
        candidates.append({
            "security_id":sid,"score":score,
            "features_available_at":doc["available_at"],
            "score_computed_at":WRITE.isoformat(),
            "recorded_at":WRITE.isoformat(),
        })
    rank_source=tmp_path/"computed_rank_candidates.json"
    rank_source.write_text(json.dumps(candidates))
    sealed=tmp_path/"computation_sealed_rank.json"
    freeze_ranked_snapshot(rank_source,sealed,market="KR",
                            snapshot_at=(WRITE+timedelta(minutes=1)).isoformat(),
                            model_version=MODEL,horizon_days=180,k=1,
                            clock=WRITE+timedelta(minutes=2))
    return b,rank_source,sealed


def audit(b,sealed):
    return audit_computed_rank_provenance(
        sealed,b[4],b[2],watch_db=b[1])


def native_freeze_args(b,rank_source,output):
    return ["freeze","--input",str(rank_source),"--market","KR",
        "--snapshot-at",(WRITE+timedelta(minutes=1)).isoformat(),
        "--model-version",MODEL,"--horizon-days","180","--k","1",
        "--prospective-ledger",str(b[1]),
        "--score-ledger",str(b[4]),
        "--features-dir",str(b[2]),
        "--require-native-computation","--out",str(output)]


def test_first_native_formula_digest_is_stored_in_each_original_score_event(tmp_path):
    b,_,sealed=prepared(tmp_path)
    with sqlite3.connect(b[4]) as conn:
        rows=[json.loads(x[0]) for x in conn.execute("SELECT payload FROM rank_score_events")]
    assert len(rows)==2
    assert all(row["computation_provenance"]==formula_provenance() for row in rows)
    check=audit(b,sealed)
    assert check["locally_computed_score_records_matched"]==2
    assert check["formula_reproduction_locally_consistent"] is True
    assert check["blocker_count"]==0
    assert check["formula_version"]==HEURISTIC_VERSION
    assert check["formula_execution_independently_attested"] is False
    assert check["real_future_leader_skill_certified"] is False


def test_manual_submitted_scores_do_not_pretend_to_be_native_computation(tmp_path):
    b,_,sealed=prepared(tmp_path,native=False)
    check=audit(b,sealed)
    assert check["locally_computed_score_records_matched"]==0
    assert any("NUMERIC_SCORE_WAS_EXTERNAL_SUBMISSION" in x for x in check["blockers"])
    assert check["real_future_leader_skill_certified"] is False


def test_native_computation_cannot_rewrite_old_generic_score_event(tmp_path):
    b,_,_=prepared(tmp_path,native=False)
    with pytest.raises(ValueError,match="mutation rejected"):
        compute_and_register_rank_scores(b[2],b[1],b[4],
                       market="KR",model_version=MODEL,clock=WRITE+timedelta(minutes=1))
    with sqlite3.connect(b[4]) as conn:
        assert all("computation_provenance" not in json.loads(x[0])
                   for x in conn.execute("SELECT payload FROM rank_score_events"))


def test_formula_digest_changed_even_with_rehashed_payload_is_blocked(tmp_path):
    b,_,sealed=prepared(tmp_path)
    with sqlite3.connect(b[4]) as conn:
        old=conn.execute("SELECT payload FROM rank_score_events WHERE security_id='A'").fetchone()[0]
        obj=json.loads(old)
        obj["computation_provenance"]["formula_sha256"]="a"*64
        from eraleader.prospective import _canonical
        encoded=_canonical(obj)
        digest=sha256(encoded.encode()).hexdigest()
        conn.execute("UPDATE rank_score_events SET payload=?,evidence_hash=? WHERE security_id='A'",
                     (encoded,digest))
    check=audit(b,sealed)
    assert "A:PINNED_FORMULA_VERSION_OR_DIGEST_MISMATCH" in check["blockers"]


def test_native_formal_model_recomputes_from_original_feature_bytes(tmp_path):
    b,_,sealed=prepared(tmp_path)
    f=b[2]/"A.json"
    obj=json.loads(f.read_text())
    obj["features"]["momentum_6m"]=.0
    f.write_text(json.dumps(obj))
    check=audit(b,sealed)
    assert "A:SOURCE_FEATURE_BYTES_REVISED" in check["blockers"]
    assert check["locally_computed_score_records_matched"]==1


def test_native_rank_does_not_claim_model_computed_before_watch(tmp_path):
    b,rank_source,sealed=prepared(tmp_path)
    data=json.loads(rank_source.read_text())
    data[0]["score_computed_at"]=(STAMP-timedelta(minutes=1)).isoformat()
    data[0]["recorded_at"]=WRITE.isoformat()
    rank_source.write_text(json.dumps(data))
    new_seal=tmp_path/"invalid_compute_time_seal.json"
    with pytest.raises(ValueError,match="Native rank calculation provenance preflight failed"):
        rank_cli(native_freeze_args(b,rank_source,new_seal))
    assert not new_seal.exists()


def test_native_rank_rejects_backdated_score_registration(tmp_path):
    b,rank_source,_=prepared(tmp_path)
    rows=json.loads(rank_source.read_text())
    rows[0]["recorded_at"]=STAMP.isoformat()
    rows[0]["score_computed_at"]=STAMP.isoformat()
    rank_source.write_text(json.dumps(rows))
    bad=tmp_path/"incorrect_score_registration_seal.json"
    with pytest.raises(ValueError,match="Native rank calculation provenance preflight failed"):
        rank_cli(native_freeze_args(b,rank_source,bad))
    assert not bad.exists()


def test_native_frozen_rank_checks_unchanged_original_watch_bytes(tmp_path):
    b,_,sealed=prepared(tmp_path)
    with sqlite3.connect(b[1]) as conn:
        old=conn.execute("SELECT payload FROM prospective_signals WHERE security_id='A'").fetchone()[0]
        obj=json.loads(old)
        obj["company"]["full_score"]=100.0
        from eraleader.prospective import _canonical
        encoded=_canonical(obj)
        conn.execute("UPDATE prospective_signals SET payload=?,payload_hash=? WHERE security_id='A'",
                     (encoded,sha256(encoded.encode()).hexdigest()))
    r=audit(b,sealed)
    assert "A:SCORE_ORIGINAL_WATCH_REGISTRY_INVALID" in r["blockers"]
    assert not r["formula_reproduction_locally_consistent"]


def test_guarded_native_rank_freeze_with_logged_computation_passes(tmp_path,capsys):
    b,source,_=prepared(tmp_path)
    new=tmp_path/"guarded_native_seal.json"
    assert rank_cli(native_freeze_args(b,source,new))==0
    capsys.readouterr()
    assert new.is_file()
    assert audit(b,new)["blocker_count"]==0


def test_native_cli_audit_and_safe_summary_only_backup(tmp_path,capsys):
    b,_,sealed=prepared(tmp_path)
    out=tmp_path/"derived"
    main(["audit-native-rank-scores","--frozen-rank",str(sealed),
         "--watch-ledger",str(b[1]),"--score-ledger",str(b[4]),
         "--features-dir",str(b[2]),"--out",str(out)])
    response=json.loads(capsys.readouterr().out)
    assert response["locally_computed_score_records_matched"]==2
    assert response["blocker_count"]==0
    assert response["real_future_leader_skill_certified"] is False
    (out/"original_source_labels.json").write_text('{"key":"NO_UPLOAD"}')
    archive=tmp_path/"derived.zip"
    assert create_backup(out,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert z.namelist()==["native_score_kr_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert json.loads((restored/"native_score_kr_research.json").read_text())==json.loads(
        (out/"native_score_kr_research.json").read_text())
    assert not (restored/"original_source_labels.json").exists()
