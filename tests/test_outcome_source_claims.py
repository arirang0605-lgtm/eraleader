"""Synthetic issuer-outcome source *claims* integrity/chronology audits.

Hashes and user-claimed retrieval times are not independent supplier truth.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import pytest

from eraleader.outcome_source_claims import audit_outcome_source_claims,SCHEMA
from eraleader.frozen_holdout import _read_frozen
from eraleader.cli import main
from eraleader.local_backup import create_backup,verify_backup,restore_backup
from test_frozen_holdout import freeze,outcomes_file

CUTOFF="2026-10-10T17:00:00+09:00"
NOW=datetime(2026,11,1,tzinfo=timezone.utc)


def make_bundle(root: Path):
    root.mkdir(parents=True,exist_ok=True)
    freeze(root)
    target=outcomes_file(root)
    original=json.loads(target.read_text())
    base={
        "schema_version":SCHEMA,
        "market":"KR",
        "label_definition_id":"synthetic-leader-rule-v1",
        "frozen_manifest_sha256":_read_frozen(root/"holdout_manifest.json")["content_sha256"],
        "outcomes_sha256":sha256(target.read_bytes()).hexdigest(),
        "claims":[],
    }
    for record in original[:3]:
        sec=record["security_id"]
        filename=f"{sec}.json"
        blob=json.dumps({"fictional_source":sec,"kind":"synthetic-leader-evidence"}).encode()
        (root/filename).write_bytes(blob)
        published=("2026-10-02T18:00:00+09:00" if sec=="B"
                   else "2026-08-02T17:00:00+09:00")
        retrieved=("2026-10-03T17:00:00+09:00" if sec=="B"
                   else "2026-08-03T17:00:00+09:00")
        base["claims"].append({
            "security_id":sec,"publisher_id_claimed":"SYNTHETIC_TEST_PROVIDER",
            "source_id":f"TEST_{sec}","file":filename,
            "sha256":sha256(blob).hexdigest(),
            "published_at":published,"retrieved_at":retrieved})
    manifest=root/"claims.json"
    manifest.write_text(json.dumps(base,sort_keys=True),encoding="utf-8")
    return root/"holdout_manifest.json",target,manifest


def audit(base,**kwargs):
    seal, labels, manifest=base
    return audit_outcome_source_claims(
        seal,labels,manifest,evaluated_at=CUTOFF,clock=NOW,**kwargs)


def test_three_claims_consistent_but_no_independent_outcome_certification(tmp_path):
    result=audit(make_bundle(tmp_path))
    assert result["frozen_candidates"]==4
    assert result["internally_evaluable_outcomes"]==3
    assert result["local_source_claims_consistent"]==3
    assert result["eligible_outcomes_missing_or_inconsistent_sources"]==0
    assert result["blocker_count"]==0
    assert result["official_leader_promotions"]==0
    assert result["independently_source_authenticated"] is False
    assert result["actual_leader_prediction_certified"] is False
    assert len(result["outcomes_sha256"])==64
    assert "published_at" not in json.dumps(result["candidate_evidence_sample"])


def test_missing_source_receipt_is_blocker_not_imputed_failure(tmp_path):
    base=make_bundle(tmp_path)
    p=base[2];data=json.loads(p.read_text())
    data["claims"]=[x for x in data["claims"] if x["security_id"]!="B"]
    p.write_text(json.dumps(data))
    result=audit(base)
    assert result["internally_evaluable_outcomes"]==3
    assert result["local_source_claims_consistent"]==2
    assert result["blocker_count"]==1
    assert result["blockers"]==["B:MISSING_OUTCOME_SOURCE_RECEIPT"]
    assert result["actual_leader_prediction_certified"] is False


def test_actual_document_tamper_detected_even_when_json_label_unchanged(tmp_path):
    base=make_bundle(tmp_path)
    (tmp_path/"A.json").write_text('{"altered":true}')
    r=audit(base)
    assert "A:SOURCE_BYTES_SHA256_MISMATCH" in r["blockers"]
    assert r["local_source_claims_consistent"]==2


@pytest.mark.parametrize("field,value,expected",[
    ("retrieved_at","2026-10-12T12:00:00+09:00","SOURCE_RETRIEVED_AFTER_EVALUATION"),
    ("retrieved_at","2026-07-15T12:00:00+09:00","SOURCE_RETRIEVED_BEFORE_PUBLICATION"),
    ("published_at","2026-07-01T12:00:00+09:00","SOURCE_PUBLISHED_BEFORE_LABEL_MATURITY"),
    ("published_at","2026-08-04T12:00:00+09:00","LABEL_AVAILABLE_BEFORE_CLAIMED_PUBLICATION"),
])
def test_source_chronology_claims_are_checked(tmp_path,field,value,expected):
    base=make_bundle(tmp_path)
    p=base[2];data=json.loads(p.read_text())
    data["claims"][0][field]=value
    p.write_text(json.dumps(data))
    r=audit(base)
    assert f"A:{expected}" in r["blockers"]
    assert r["local_source_claims_consistent"]==2


def test_receipt_hash_must_anchor_exact_frozen_manifest_and_outcomes(tmp_path):
    base=make_bundle(tmp_path)
    path=base[2]
    d=json.loads(path.read_text())
    d["outcomes_sha256"]="0"*64
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="different frozen protocol"):
        audit(base)
    d["outcomes_sha256"]=sha256(base[1].read_bytes()).hexdigest()
    d["frozen_manifest_sha256"]="1"*64
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="different frozen protocol"):
        audit(base)


def test_duplicate_and_unknown_outcome_source_claims_fail_closed(tmp_path):
    base=make_bundle(tmp_path)
    path=base[2];d=json.loads(path.read_text())
    d["claims"].append(dict(d["claims"][0]))
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="Duplicate source claim"):
        audit(base)
    d["claims"][-1]["security_id"]="INVENTED"
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="unknown outcome"):
        audit(base)


@pytest.mark.parametrize("file",["../A.json","A/../../B.json","/etc/passwd",".hidden.json"])
def test_path_escape_or_hidden_source_file_rejected(tmp_path,file):
    base=make_bundle(tmp_path)
    p=base[2];d=json.loads(p.read_text())
    d["claims"][0]["file"]=file
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match="Unsafe local evidence filename"):
        audit(base)


def test_missing_source_file_is_explicit_blocker_not_success(tmp_path):
    base=make_bundle(tmp_path)
    (tmp_path/"B.json").unlink()
    r=audit(base)
    assert "B:MISSING_OR_UNSAFE_SOURCE_FILE" in r["blockers"]
    assert r["local_source_claims_consistent"]==2


def test_symlink_source_and_receipt_both_refused(tmp_path):
    base=make_bundle(tmp_path)
    real=tmp_path/"backing.dat"
    (tmp_path/"A.json").rename(real)
    (tmp_path/"A.json").symlink_to(real)
    r=audit(base)
    assert "A:MISSING_OR_UNSAFE_SOURCE_FILE" in r["blockers"]
    base[2].rename(tmp_path/"real_claims.json")
    base[2].symlink_to(tmp_path/"real_claims.json")
    with pytest.raises(ValueError,match="Missing or symlinked"):
        audit(base)


def test_premature_negative_not_upgraded_by_valid_document(tmp_path):
    base=make_bundle(tmp_path)
    labels=json.loads(base[1].read_text())
    b=next(x for x in labels if x["security_id"]=="B")
    b["mature_at"]="2026-08-01T17:00:00+09:00"
    b["outcome_available_at"]="2026-08-03T17:00:00+09:00"
    base[1].write_text(json.dumps(labels))
    p=base[2];d=json.loads(p.read_text())
    d["outcomes_sha256"]=sha256(base[1].read_bytes()).hexdigest()
    p.write_text(json.dumps(d))
    r=audit(base)
    assert r["internally_evaluable_outcomes"]==2
    assert r["local_source_claims_consistent"]==2
    assert next(x for x in r["candidate_evidence_sample"] if x["security_id"]=="B")[
        "issues"]==["OUTCOME_NOT_YET_EVALUABLE"]


def test_cli_and_derived_only_archive(tmp_path,capsys):
    base=make_bundle(tmp_path/"inputs")
    output=tmp_path/"results"
    main(["audit-outcome-source-claims","--freeze-file",str(base[0]),
          "--outcomes",str(base[1]),"--receipt-manifest",str(base[2]),
          "--evaluated-at",CUTOFF,"--out",str(output)])
    printed=json.loads(capsys.readouterr().out)
    assert printed["local_source_claims_consistent"]==3
    assert printed["independently_source_authenticated"] is False
    report=json.loads(Path(printed["path"]).read_text())
    assert report["actual_leader_prediction_certified"] is False
    (output/"sensitive_raw_outcomes.json").write_text('{"private_key":"NEVER"}')
    zipped=tmp_path/"source_claims_research.zip"
    assert create_backup(output,zipped)["file_count"]==1
    assert verify_backup(zipped)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(zipped) as archive:
        assert archive.namelist()==["outcome_source_claims_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(zipped,restored)
    assert json.loads((restored/"outcome_source_claims_research.json").read_text())==report
    assert not (restored/"sensitive_raw_outcomes.json").exists()



@pytest.mark.parametrize("mature,expected_evaluable", [
    ("2026-09-29T16:59:00+09:00", False),
    ("2026-09-29T17:00:00+09:00", True),
    ("2026-09-29T17:01:00+09:00", True),
])
def test_source_claim_cannot_upgrade_negative_before_exact_frozen_clock(
        tmp_path, mature, expected_evaluable):
    """An apparently perfect local receipt cannot override the sealed evaluator."""
    base=make_bundle(tmp_path)
    labels=json.loads(base[1].read_text(encoding="utf-8"))
    negative=next(x for x in labels if x["security_id"]=="B")
    negative["mature_at"]=mature
    negative["outcome_available_at"]="2026-10-03T17:00:00+09:00"
    base[1].write_text(json.dumps(labels), encoding="utf-8")
    receipt=json.loads(base[2].read_text(encoding="utf-8"))
    receipt["outcomes_sha256"]=sha256(base[1].read_bytes()).hexdigest()
    base[2].write_text(json.dumps(receipt), encoding="utf-8")
    result=audit(base)
    reconciliation=result["internally_evaluable_outcomes"]
    passed=result["local_source_claims_consistent"]
    assert reconciliation==(3 if expected_evaluable else 2)
    assert passed==(3 if expected_evaluable else 2)
    assert result["eligible_outcomes_missing_or_inconsistent_sources"]==0
    row=next(row for row in result["candidate_evidence_sample"]
             if row["security_id"]=="B")
    assert row["maturity_status"]==(
        "RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"
        if expected_evaluable else "PREMATURE_NEGATIVE_LABEL")
    assert row["local_source_bytes_checked"] is expected_evaluable
    assert result["independently_source_authenticated"] is False


@pytest.mark.parametrize("mature,eligible", [
    ("2026-03-16T15:59:00-04:00", False),
    ("2026-03-16T16:00:00-04:00", True),
    ("2026-03-16T16:01:00-04:00", True),
])
def test_us_dst_source_receipt_does_not_upgrade_early_negative(
        tmp_path, mature, eligible):
    from eraleader.prospective import ProspectiveRegistry
    from eraleader.frozen_holdout import freeze_registered_candidates
    from test_frozen_holdout import run, LABEL, VERSION
    ledger=tmp_path/"prospective.sqlite"
    db=ProspectiveRegistry(ledger)
    try:
        db.record_integrated(run(["US-DST"], market="US",
            as_of="2026-03-06T15:00:00-05:00"),
            clock=datetime(2026,3,6,21,tzinfo=timezone.utc))
    finally:
        db.close()
    frozen=tmp_path/"holdout_us.json"
    freeze_registered_candidates(ledger, frozen,
        market="US",model_version=VERSION,label_definition_id=LABEL,
        horizon_days=10,clock=datetime(2026,3,7,tzinfo=timezone.utc))
    label_path=tmp_path/"labels_us.json"
    label_path.write_text(json.dumps([{
        "security_id":"US-DST","label_definition_id":LABEL,
        "is_future_leader":False,"mature_at":mature,
        "outcome_available_at":"2026-03-17T12:00:00-04:00",
    }]), encoding="utf-8")
    blob=b'{"synthetic":"US-DST"}'
    (tmp_path/"US-DST.json").write_bytes(blob)
    claim={
        "schema_version":SCHEMA,"market":"US",
        "label_definition_id":LABEL,
        "frozen_manifest_sha256":_read_frozen(frozen)["content_sha256"],
        "outcomes_sha256":sha256(label_path.read_bytes()).hexdigest(),
        "claims":[{
            "security_id":"US-DST","publisher_id_claimed":"SYNTHETIC_ONLY",
            "source_id":"FAKE_DST","file":"US-DST.json",
            "sha256":sha256(blob).hexdigest(),
            "published_at":"2026-03-17T10:00:00-04:00",
            "retrieved_at":"2026-03-18T12:00:00-04:00",
        }],
    }
    manifest=tmp_path/"receipt_us.json"
    manifest.write_text(json.dumps(claim), encoding="utf-8")
    result=audit_outcome_source_claims(frozen,label_path,manifest,
        evaluated_at="2026-03-20T17:00:00-04:00",
        clock=datetime(2026,4,1,tzinfo=timezone.utc))
    assert result["internally_evaluable_outcomes"]==int(eligible)
    assert result["local_source_claims_consistent"]==int(eligible)
    assert result["eligible_outcomes_missing_or_inconsistent_sources"]==0
    assert result["candidate_evidence_sample"][0]["maturity_status"]==(
        "RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"
        if eligible else "PREMATURE_NEGATIVE_LABEL")
    assert result["actual_leader_prediction_certified"] is False


def test_source_audit_fails_closed_on_reconciler_status_disagreement(
        tmp_path, monkeypatch):
    from eraleader import outcome_source_claims as module
    original=module.reconcile_holdout_outcomes
    def conflicting_status(*args, **kwargs):
        report=original(*args, **kwargs)
        report["candidate_evidence_sample"]=[
            {**row,"status":"PREMATURE_NEGATIVE_LABEL"}
            if row["security_id"]=="B" else row
            for row in report["candidate_evidence_sample"]
        ]
        return report
    monkeypatch.setattr(module,"reconcile_holdout_outcomes",conflicting_status)
    with pytest.raises(ValueError,match="evaluator disagree"):
        audit(make_bundle(tmp_path))


def test_source_audit_refuses_more_claims_than_evaluable_labels(
        tmp_path, monkeypatch):
    from eraleader import outcome_source_claims as module
    original=module.reconcile_holdout_outcomes
    def conflicting_total(*args, **kwargs):
        report=original(*args, **kwargs)
        report["internally_evaluable_outcome_count"]-=1
        return report
    monkeypatch.setattr(module,"reconcile_holdout_outcomes",conflicting_total)
    with pytest.raises(ValueError,match="exceed sealed"):
        audit(make_bundle(tmp_path))

# Strict local receipt-to-outcome binding remains research-only, never a provider signature.
def bound_bundle(tmp_path):
    base=make_bundle(tmp_path)
    labels={x["security_id"]:x for x in json.loads(base[1].read_text())}
    receipts=json.loads(base[2].read_text())
    for claim in receipts["claims"]:
        sec=claim["security_id"]
        blob=json.dumps({"schema_version":"eraleader.outcome_label_evidence.v1",
                         **labels[sec]},sort_keys=True).encode()
        (tmp_path/claim["file"]).write_bytes(blob)
        claim["sha256"]=sha256(blob).hexdigest()
    base[2].write_text(json.dumps(receipts))
    return base


def test_strict_binding_refuses_opaque_document_even_with_valid_hash(tmp_path):
    base=make_bundle(tmp_path)
    result=audit(base,require_document_label_binding=True)
    assert result["local_source_claims_consistent"]==0
    assert result["local_source_labels_bound"]==0
    assert result["blocker_count"]==3
    assert "A:SOURCE_DOCUMENT_LABEL_BINDING_REQUIRED" in result["blockers"]


def test_strict_binding_accepts_exact_canonical_outcome_fields_but_not_certified(tmp_path):
    base=bound_bundle(tmp_path)
    result=audit(base,require_document_label_binding=True)
    assert result["local_source_claims_consistent"]==3
    assert result["local_source_labels_bound"]==3
    assert result["blocker_count"]==0
    assert result["actual_leader_prediction_certified"] is False


@pytest.mark.parametrize("field,value",[
    ("security_id","B"),
    ("is_future_leader",False),
    ("mature_at","2026-08-02T17:00:00+09:00"),
    ("outcome_available_at","2026-08-04T17:00:00+09:00"),
    ("leader_start_at","2026-05-11T10:00:00+09:00"),
])
def test_strict_binding_detects_falsified_source_label_even_if_receipt_rehashed(
        tmp_path,field,value):
    base=bound_bundle(tmp_path)
    p=tmp_path/"A.json"
    doc=json.loads(p.read_text())
    doc[field]=value
    blob=json.dumps(doc,sort_keys=True).encode()
    p.write_bytes(blob)
    receipts=json.loads(base[2].read_text())
    receipts["claims"][0]["sha256"]=sha256(blob).hexdigest()
    base[2].write_text(json.dumps(receipts))
    result=audit(base,require_document_label_binding=True)
    assert result["local_source_claims_consistent"]==2
    assert result["local_source_labels_bound"]==2
    assert "A:SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH" in result["blockers"]
    assert result["actual_leader_prediction_certified"] is False

def test_cli_strict_document_binding_from_synthetic_receipts(tmp_path,capsys):
    base=bound_bundle(tmp_path/"sources")
    out=tmp_path/"derived"
    main(["audit-outcome-source-claims",
          "--freeze-file",str(base[0]),"--outcomes",str(base[1]),
          "--receipt-manifest",str(base[2]),"--evaluated-at",CUTOFF,
          "--require-document-label-binding","--out",str(out)])
    result=json.loads(capsys.readouterr().out)
    assert result["local_source_claims_consistent"]==3
    report=json.loads((out/"outcome_source_claims_research.json").read_text())
    assert report["local_source_labels_bound"]==3
    assert report["require_document_label_binding"] is True
    assert report["independently_source_authenticated"] is False
