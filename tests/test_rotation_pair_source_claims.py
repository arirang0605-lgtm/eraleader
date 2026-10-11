"""Fail-closed local pair-outcome source receipt audit; all data synthetic."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader.rotation_pair_source_claims import (
    audit_rotation_pair_source_claims, MANIFEST_SCHEMA, DOCUMENT_SCHEMA,
)
from eraleader.rotation_holdout import audit_rotation_pair_outcomes
from test_rotation_holdout import scenario, freeze, labels_path, FREEZE, AFTER, LABEL_ID

CUTOFF=AFTER.isoformat()


def prepared(tmp_path):
    tmp_path.mkdir(parents=True,exist_ok=True)
    b=scenario(tmp_path)
    freeze(b)
    labels=labels_path(tmp_path)
    claimsdir=tmp_path/"receipt"
    claimsdir.mkdir()
    source_rows=[]
    original=json.loads(labels.read_text())
    for record in original:
        sec=record["security_id"]
        doc={"schema_version":DOCUMENT_SCHEMA,**record}
        raw=json.dumps(doc,sort_keys=True).encode()
        (claimsdir/(sec+".json")).write_bytes(raw)
        source_rows.append({
            "security_id":sec,
            "publisher_id_claimed":"SYNTHETIC_OFFLINE_PUBLISHER",
            "source_id":"SYNTHETIC_DOC_SOURCE_"+sec,
            "file":sec+".json",
            "sha256":sha256(raw).hexdigest(),
            "published_at":"2026-10-09T10:55:00+09:00",
            "retrieved_at":"2026-10-09T11:15:00+09:00",
        })
    frozen=json.loads(b[3].read_text())
    receipt={
        "schema_version":MANIFEST_SCHEMA,
        "market":"KR",
        "label_definition_id":LABEL_ID,
        "rotation_freeze_sha256":frozen["content_sha256"],
        "outcomes_sha256":sha256(labels.read_bytes()).hexdigest(),
        "claims":source_rows,
    }
    path=claimsdir/"manifest.json"
    path.write_text(json.dumps(receipt,sort_keys=True))
    return b,labels,path


def run(items, **kwargs):
    b,labels,receipts=items
    return audit_rotation_pair_source_claims(
        b[3],labels,receipts,evaluated_at=CUTOFF,clock=AFTER,**kwargs)


def change_manifest(items, edit):
    manifest=items[2]
    obj=json.loads(manifest.read_text())
    edit(obj)
    manifest.write_text(json.dumps(obj,sort_keys=True))
    return items


def change_document(items, sec, edit, *, rehash=True):
    manifest=items[2]
    path=manifest.parent/(sec+".json")
    doc=json.loads(path.read_text())
    edit(doc)
    raw=json.dumps(doc,sort_keys=True).encode()
    path.write_bytes(raw)
    if rehash:
        m=json.loads(manifest.read_text())
        match=next(x for x in m["claims"] if x["security_id"]==sec)
        match["sha256"]=sha256(raw).hexdigest()
        manifest.write_text(json.dumps(m,sort_keys=True))
    return items


def test_two_source_documents_both_match_internal_pair_but_not_independent_proof(tmp_path):
    result=run(prepared(tmp_path))
    assert result["status"]=="LOCAL_ROTATION_PAIR_SOURCE_CLAIMS_RESEARCH_NOT_CERTIFIED"
    assert result["frozen_pair_count"]==1
    assert result["internally_evaluable_pair_count"]==1
    assert result["locally_source_corroborated_pairs"]==1
    assert result["locally_source_corroborated_research_confirmations"]==1
    assert result["locally_source_corroborated_research_nonconfirmations"]==0
    assert result["eligible_pairs_missing_or_conflicting_source_evidence"]==0
    row=result["pair_evidence_sample"][0]
    assert row["underlying_research_outcome_status"]=="RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED"
    assert row["local_source_claim_status"]=="LOCAL_TWO_OUTCOME_DOCUMENT_CLAIMS_MATCH_NOT_AUTHENTICATED"
    assert row["local_source_claims_consistent"] is True
    assert result["publisher_independently_authenticated"] is False
    assert result["source_retrieval_time_independently_attested"] is False
    assert result["actual_leader_replacement_certified"] is False
    assert result["official_leader_replacements"]==0
    assert len(result["rotation_freeze_sha256"])==64
    assert "is_future_leader" not in json.dumps(result)


@pytest.mark.parametrize("missing",["INC","NEW"])
def test_one_missing_document_claim_censors_entire_pair_not_false_failure(tmp_path,missing):
    items=prepared(tmp_path)
    change_manifest(items,lambda m:m["claims"].__setitem__(
        slice(None),[x for x in m["claims"] if x["security_id"]!=missing]))
    result=run(items)
    assert result["locally_source_corroborated_pairs"]==0
    assert result["eligible_pairs_missing_or_conflicting_source_evidence"]==1
    assert result["locally_source_corroborated_research_confirmations"]==0
    assert result["pair_evidence_sample"][0]["local_source_claim_status"]=="CENSORED_MISSING_OR_CONFLICTING_PAIR_SOURCE"
    assert f"{missing}:MISSING_PAIR_OUTCOME_SOURCE_RECEIPT" in result["blockers"]
    assert result["official_leader_replacements"]==0


def test_doc_hash_changed_without_manifest_update_censors_pair(tmp_path):
    items=prepared(tmp_path)
    change_document(items,"NEW",lambda d:d.update(security_id="SWAPPED"),rehash=False)
    result=run(items)
    assert result["locally_source_corroborated_pairs"]==0
    assert "NEW:SOURCE_DOCUMENT_SHA256_MISMATCH" in result["blockers"]


@pytest.mark.parametrize("field,value",[
    ("security_id","SOMEONE_ELSE"),
    ("label_definition_id","OPTIMIZED_EX_POST"),
    ("is_future_leader",False),
    ("mature_at","2026-10-10T10:20:00+09:00"),
    ("outcome_available_at","2026-10-09T12:00:00+09:00"),
    ("leader_start_at","2026-10-03T09:00:00+09:00"),
])
def test_rehashed_wrong_normalized_document_censors_positive_pair(tmp_path,field,value):
    items=prepared(tmp_path)
    change_document(items,"NEW",lambda d:d.update({field:value}))
    result=run(items)
    assert result["locally_source_corroborated_pairs"]==0
    assert "NEW:SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH" in result["blockers"]


def test_rehashed_wrong_negative_label_censors_entire_pair(tmp_path):
    items=prepared(tmp_path)
    change_document(items,"INC",lambda d:d.update(is_future_leader=True))
    result=run(items)
    assert result["locally_source_corroborated_pairs"]==0
    assert "INC:SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH" in result["blockers"]


@pytest.mark.parametrize("field,new_value,code",[
    ("published_at","2026-10-09T10:19:00+09:00","SOURCE_PUBLISHED_BEFORE_LABEL_MATURE"),
    ("published_at","2026-10-09T11:01:00+09:00","SOURCE_PUBLISHED_AFTER_DECLARED_LABEL_AVAILABILITY"),
    ("retrieved_at","2026-10-09T10:00:00+09:00","SOURCE_RETRIEVED_BEFORE_PUBLICATION"),
    ("retrieved_at","2026-10-12T11:00:00+09:00","SOURCE_RETRIEVED_AFTER_EVALUATION"),
    ("retrieved_at","2026-10-09T10:58:00+09:00","SOURCE_RETRIEVED_BEFORE_LABEL_AVAILABLE"),
])
def test_claimed_publication_retrieval_time_contradictions_censor(tmp_path,field,new_value,code):
    items=prepared(tmp_path)
    change_manifest(items,lambda m:m["claims"][0].update({field:new_value}))
    r=run(items)
    assert r["locally_source_corroborated_pairs"]==0
    assert f"NEW:{code}" in r["blockers"] or f"INC:{code}" in r["blockers"]


@pytest.mark.parametrize("key",["rotation_freeze_sha256","outcomes_sha256",
                                 "market","label_definition_id"])
def test_manifest_bound_to_exact_sealed_protocol_and_label_bytes(tmp_path,key):
    items=prepared(tmp_path)
    change_manifest(items,lambda m:m.update({key:"WRONG"}))
    with pytest.raises(ValueError,match="manifest|bound|protocol|label"):
        run(items)


def test_missing_or_extra_document_claim_field_rejected(tmp_path):
    items=prepared(tmp_path)
    change_document(items,"NEW",lambda d:d.update(officially_authenticated=True))
    result=run(items)
    assert "NEW:SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH" in result["blockers"]


def test_duplicate_json_keys_or_symlink_source_are_not_trusted(tmp_path):
    items=prepared(tmp_path)
    doc=items[2].parent/"NEW.json"
    doc.write_text('{"schema_version":"x","schema_version":"y"}')
    m=json.loads(items[2].read_text())
    next(x for x in m["claims"] if x["security_id"]=="NEW")["sha256"]=sha256(doc.read_bytes()).hexdigest()
    items[2].write_text(json.dumps(m))
    report=run(items)
    assert "NEW:SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH" in report["blockers"]

    original=items[2].parent/"renamed.json"
    doc.rename(original)
    doc.symlink_to(original)
    report=run(items)
    assert "NEW:SOURCE_FILE_MISSING_OR_UNSAFE" in report["blockers"]


@pytest.mark.parametrize("name",["../NEW.json","/tmp/NEW.json",".hidden.json"])
def test_unsafe_manifest_relative_paths_are_rejected(tmp_path,name):
    items=prepared(tmp_path)
    change_manifest(items,lambda m:m["claims"][0].update(file=name))
    with pytest.raises(ValueError,match="filename|Unsafe|path"):
        run(items)


def test_duplicate_receipts_and_unmatched_injected_issuer_rejected(tmp_path):
    items=prepared(tmp_path)
    change_manifest(items,lambda m:m["claims"].append(deepcopy(m["claims"][0])))
    with pytest.raises(ValueError,match="Duplicate"):
        run(items)
    items=prepared(tmp_path/"second")
    change_manifest(items,lambda m:m["claims"][0].update(security_id="ATTACKER"))
    with pytest.raises(ValueError,match="unknown|unmatched"):
        run(items)


def test_unmatured_future_pair_even_with_fake_matching_documents_is_not_evaluable(tmp_path):
    items=prepared(tmp_path)
    result=audit_rotation_pair_source_claims(
        items[0][3],items[1],items[2],
        evaluated_at=(FREEZE+timedelta(days=4)).isoformat(),clock=AFTER)
    assert result["internally_evaluable_pair_count"]==0
    assert result["locally_source_corroborated_pairs"]==0
    assert result["pair_evidence_sample"][0]["local_source_claim_status"]=="PAIR_OUTCOME_NOT_EVALUABLE"
    assert result["research_pair_confirmation_fraction_locally_corroborated"] is None


def test_missing_issuer_label_never_promoted_by_receipt(tmp_path):
    items=prepared(tmp_path)
    rows=json.loads(items[1].read_text())
    items[1].write_text(json.dumps(rows[:1]))
    # Manifest should match changed outcome bytes; no passage without status.
    change_manifest(items,lambda m:m.update(outcomes_sha256=sha256(items[1].read_bytes()).hexdigest()))
    report=run(items)
    assert report["internally_evaluable_pair_count"]==0
    assert report["locally_source_corroborated_pairs"]==0


def test_cli_derived_only_zip_backup_and_immutability(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    items=prepared(tmp_path)
    before={p:sha256(p.read_bytes()).hexdigest() for p in [items[0][0],items[0][1],items[0][3],items[1],items[2]]}
    out=tmp_path/"derived"
    main(["audit-rotation-pair-sources","--freeze-file",str(items[0][3]),
          "--outcomes",str(items[1]),"--receipt-manifest",str(items[2]),
          "--evaluated-at",CUTOFF,"--out",str(out)])
    printed=json.loads(capsys.readouterr().out)
    assert printed["locally_source_corroborated_pairs"]==1
    assert printed["official_leader_replacements"]==0
    report=json.loads((out/"rotation_pair_source_claims_research.json").read_text())
    assert "is_future_leader" not in json.dumps(report)
    assert {p:sha256(p.read_bytes()).hexdigest() for p in before}==before
    zip_path=tmp_path/"only_derived.zip"
    backed=create_backup(out,zip_path)
    assert backed["file_count"]==1
    assert verify_backup(zip_path)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(zip_path) as z:
        assert z.namelist()==["rotation_pair_source_claims_research.json","MANIFEST.json"]
    restore_backup(zip_path,tmp_path/"restored")
    assert (tmp_path/"restored"/"rotation_pair_source_claims_research.json").read_bytes()==(
        out/"rotation_pair_source_claims_research.json").read_bytes()


def test_report_is_research_only_when_all_source_claims_match(tmp_path):
    r=run(prepared(tmp_path))
    assert r["research_pair_confirmation_fraction_locally_corroborated"]==1.0
    assert r["historic_pit_certified"] is False
    assert r["actual_leader_replacement_certified"] is False
    assert r["publisher_independently_authenticated"] is False
