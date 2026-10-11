"""5_5: strict predeclared ranked leader labels + local document receipts.

Each source is explicitly synthetic and self-declared; agreement never
authenticates a real stock leader or an official provider timestamp.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest

from eraleader.ranked_discovery import (
    freeze_ranked_snapshot,evaluate_ranked_precision_at_k,
    main as ranked_cli,
)
from eraleader.ranked_outcome_receipts import (
    audit_ranked_outcome_receipts,
    STATUS_RESEARCH,STATUS_RETROSPECTIVE,
)
from eraleader.local_backup import create_backup,verify_backup,restore_backup

UTC=timezone.utc
SNAP="2026-01-01T00:00:00+00:00"
FROZEN=datetime(2026,1,1,0,30,tzinfo=UTC)
CUTOFF="2026-03-01T00:00:00+00:00"
NOW=datetime(2026,3,2,tzinfo=UTC)
MODEL="predeclared-v1"
LABEL_ID="LEADER_TREND_30D_V1"


def ranked(sec,score):
    return {
        "security_id":sec,"score":score,
        "features_available_at":"2025-12-31T22:00:00+00:00",
        "score_computed_at":"2025-12-31T22:10:00+00:00",
        "recorded_at":"2025-12-31T22:12:00+00:00",
    }


def label(sec,winner,*,published="2026-02-03T00:00:00+00:00",
          mature="2026-02-02T00:00:00+00:00",onset="2026-01-11T00:00:00+00:00"):
    row={
        "security_id":sec,
        "label_definition_id":LABEL_ID,
        "is_future_leader":winner,
        "mature_at":mature,
        "outcome_available_at":published,
    }
    if winner:row["leader_start_at"]=onset
    return row


def protocol(path,market="KR",horizon=30):
    rule={
        "schema_version":"eraleader.future_leader_label_definition.v1",
        "label_definition_id":LABEL_ID,
        "market":market,"horizon_days":horizon,
        "positive_criterion":"Research leader onset within 30 market-local calendar days of sealed ranked snapshot.",
        "measurement_method":"Compare separately declared positive leader_start_at to original snapshot market date.",
        "universe_scope":"Only pre-sealed ranked security IDs; no survivor-filled universe.",
        "delisted_handling":"Never assume a delisted issuer is a loser without original cash-settlement evidence.",
    }
    path.write_text(json.dumps(rule,sort_keys=True))
    return path


def scenario(tmp_path,*,k=3,labels=None,retrospective=False,market="KR"):
    folder=tmp_path/"scenario"
    folder.mkdir(parents=True)
    definition=protocol(folder/"leader_rule.json",market)
    source=folder/"ranking.json"
    source.write_text(json.dumps([
        ranked("SYN-A",95),ranked("SYN-B",85),ranked("SYN-C",60)
    ]))
    frozen=folder/"ranked_frozen.json"
    seal=NOW if retrospective else FROZEN
    freeze_ranked_snapshot(source,frozen,market=market,snapshot_at=SNAP,
                           model_version=MODEL,horizon_days=30,k=k,
                           label_definition_id=LABEL_ID,
                           label_definition_file=definition,clock=seal)
    if labels is None:
        labels=[
            label("SYN-A",True),
            label("SYN-B",False,mature="2026-01-31T00:00:00+00:00",
                  published="2026-02-01T00:00:00+00:00"),
        ]
    outcome=folder/"later_outcomes.json"
    outcome.write_text(json.dumps(labels,sort_keys=True))
    receipts=folder/"outcome_source_receipts.json"
    claims=[]
    for rec in labels:
        doc={**rec,"schema_version":"eraleader.outcome_label_evidence.v1"}
        file=rec["security_id"]+".json"
        raw=json.dumps(doc,sort_keys=True).encode()
        (folder/file).write_bytes(raw)
        claims.append({
            "security_id":rec["security_id"],
            "publisher_id_claimed":"SYNTHETIC_PUBLISHER",
            "source_id":"TEST_ONLY_SOURCE",
            "file":file,"sha256":sha256(raw).hexdigest(),
            "published_at":rec["mature_at"],
            "retrieved_at":rec["outcome_available_at"],
        })
    payload={
        "schema_version":"eraleader.ranked_outcome_receipts.v1",
        "market":market,"model_version":MODEL,
        "label_definition_id":LABEL_ID,
        "ranked_snapshot_sha256":json.loads(frozen.read_text())["content_sha256"],
        "outcomes_sha256":sha256(outcome.read_bytes()).hexdigest(),
        "claims":claims,
    }
    receipts.write_text(json.dumps(payload,sort_keys=True))
    return frozen,outcome,receipts


def evaluate(files,*,cutoff=CUTOFF,clock=NOW):
    return audit_ranked_outcome_receipts(
        *files,evaluated_at=cutoff,clock=clock,sample_limit=20,
        label_definition_file=files[0].parent/"leader_rule.json")


def change_manifest(file,func):
    obj=json.loads(file.read_text());func(obj)
    file.write_text(json.dumps(obj,sort_keys=True))


def rewrite_doc(files,sec,update,*,rehash=True):
    _,_,manifest=files
    doc=manifest.parent/(sec+".json")
    obj=json.loads(doc.read_text());update(obj)
    raw=json.dumps(obj,sort_keys=True).encode()
    doc.write_bytes(raw)
    if rehash:
        change_manifest(manifest,lambda body:next(
            x for x in body["claims"] if x["security_id"]==sec
        ).update(sha256=sha256(raw).hexdigest()))


def test_freeze_pins_label_definition_before_any_future_results(tmp_path):
    files=scenario(tmp_path)
    seal=json.loads(files[0].read_text())
    assert seal["label_definition_id"]==LABEL_ID
    assert seal["retrospective_freeze"] is False
    assert seal["outcome_definition_pinned_before_labels"] is True
    assert seal["label_rule_bytes_pinned"] is True
    assert seal["label_definition_sha256"]==sha256(
        (files[0].parent/"leader_rule.json").read_bytes()).hexdigest()
    result=evaluate(files)
    assert result["label_rule_bytes_verified_against_frozen_sha"] is True
    assert result["status"]==STATUS_RESEARCH
    assert result["label_definition_id"]==LABEL_ID
    assert result["top_k_selected_count"]==3
    assert result["source_document_matched_early_hits"]==1
    assert result["source_document_matched_known_failures"]==1
    assert result["unknown_or_source_censored_count"]==1
    assert result["precision_on_locally_documented_known"]==0.5
    assert result["locally_documented_precision_full_k_floor"]==round(1/3,6)
    assert result["locally_documented_precision_full_k_ceiling"]==round(2/3,6)
    assert result["median_locally_documented_lead_days"]==10
    assert result["recall_at_k"] is None
    assert result["actual_future_leader_accuracy_certified"] is False
    assert result["official_leader_promotions"]==0
    assert result["independently_authenticated_publisher"] is False


def test_pinned_label_definition_mismatch_fails_closed_even_for_same_results(tmp_path):
    files=scenario(tmp_path)
    raw=json.loads(files[1].read_text())
    raw[0]["label_definition_id"]="RETROFITTED_WINNER_RULE"
    files[1].write_text(json.dumps(raw))
    with pytest.raises(ValueError,match="label definition"):
        evaluate_ranked_precision_at_k(files[0],files[1],evaluated_at=CUTOFF,clock=NOW)


def test_legacy_ranked_freeze_remains_readable_but_cannot_pass_strict_receipts(tmp_path):
    folder=tmp_path/"raw"
    folder.mkdir()
    inputs=folder/"ranked.json"
    inputs.write_text(json.dumps([ranked("SYN-A",95)]))
    frozen=folder/"legacy_freeze.json"
    freeze_ranked_snapshot(inputs,frozen,market="KR",snapshot_at=SNAP,
                           model_version=MODEL,horizon_days=30,k=1,clock=FROZEN)
    evaluated=evaluate_ranked_precision_at_k(frozen,None,evaluated_at=CUTOFF,clock=NOW)
    assert evaluated["label_definition_predeclared"] is False
    assert evaluated["real_leader_prediction_certified"] is False
    files=scenario(tmp_path)
    with pytest.raises(ValueError,match="predeclared|pinned|definition"):
        evaluate((frozen,files[1],files[2]))


def test_label_definition_changed_inside_manifest_does_not_select_other_success_rule(tmp_path):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda body:body.update(label_definition_id="AFTER_LOOKING_AT_OUTCOMES"))
    with pytest.raises(ValueError,match="label_definition|definition|protocol"):
        evaluate(files)


def test_topk_denominator_never_shrinks_when_outcome_missing(tmp_path):
    files=scenario(tmp_path,labels=[label("SYN-A",True)],k=3)
    out=evaluate(files)
    assert out["top_k_selected_count"]==3
    assert out["source_document_matched_early_hits"]==1
    assert out["unknown_or_source_censored_count"]==2
    assert out["precision_on_locally_documented_known"]==1.0
    assert out["locally_documented_precision_full_k_ceiling"]==1.0


def test_missing_document_receipt_censors_matured_negative_instead_of_false_failure(tmp_path):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda body:body["claims"].pop(-1))
    r=evaluate(files)
    assert r["source_document_matched_early_hits"]==1
    assert r["source_document_matched_known_failures"]==0
    assert r["unknown_or_source_censored_count"]==2
    assert r["blocker_counts"]["MISSING_LOCAL_SOURCE_RECEIPT"]==1


def test_rehashed_incorrect_document_leader_label_cannot_count_early_hit(tmp_path):
    files=scenario(tmp_path)
    rewrite_doc(files,"SYN-A",lambda obj:obj.update(is_future_leader=False))
    r=evaluate(files)
    assert r["source_document_matched_early_hits"]==0
    assert r["blocker_counts"]["SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"]==1
    assert r["precision_on_locally_documented_known"]==0.0


def test_document_byte_hash_change_censors_but_does_not_change_original_freeze(tmp_path):
    files=scenario(tmp_path)
    original_hash=sha256(files[0].read_bytes()).hexdigest()
    rewrite_doc(files,"SYN-A",lambda obj:obj.update(leader_start_at="2026-01-15T00:00:00+00:00"),
                rehash=False)
    r=evaluate(files)
    assert r["blocker_counts"]["SOURCE_BYTES_SHA256_MISMATCH"]==1
    assert r["source_document_matched_early_hits"]==0
    assert sha256(files[0].read_bytes()).hexdigest()==original_hash


@pytest.mark.parametrize("mutator,blocker",[
    (lambda entry:entry.update(published_at="2026-01-10T00:00:00Z"),
     "SOURCE_PUBLISHED_BEFORE_MATURITY"),
    (lambda entry:entry.update(published_at="2026-02-04T00:00:00Z"),
     "SOURCE_PUBLISHED_AFTER_LABEL_AVAILABILITY"),
    (lambda entry:entry.update(retrieved_at="2026-01-01T10:00:00Z"),
     "SOURCE_RETRIEVED_BEFORE_AVAILABILITY"),
    (lambda entry:entry.update(retrieved_at="2026-03-02T01:00:00Z"),
     "SOURCE_RETRIEVED_AFTER_EVALUATION"),
])
def test_claimed_source_timestamp_contradictions_censor_hit(tmp_path,mutator,blocker):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda m:mutator(m["claims"][0]))
    r=evaluate(files)
    assert r["source_document_matched_early_hits"]==0
    assert r["blocker_counts"][blocker]==1
    assert r["actual_future_leader_accuracy_certified"] is False


def test_retrospective_freeze_has_no_retrospective_precision_credit(tmp_path):
    files=scenario(tmp_path,retrospective=True)
    r=evaluate(files,clock=NOW)
    assert r["status"]==STATUS_RETROSPECTIVE
    assert r["source_document_matched_early_hits"]==0
    assert r["precision_on_locally_documented_known"] is None
    assert r["locally_documented_precision_full_k_floor"] is None
    assert r["retrospective_freeze"] is True
    assert r["actual_future_leader_accuracy_certified"] is False


def test_eval_asof_before_sealed_at_fails_prospective_source_metrics(tmp_path):
    files=scenario(tmp_path)
    early="2026-01-01T00:10:00Z"
    r=evaluate(files,cutoff=early)
    assert r["status"]==STATUS_RETROSPECTIVE
    assert r["source_document_matched_early_hits"]==0


def test_immature_negative_never_failure_even_with_valid_claimed_receipt(tmp_path):
    files=scenario(tmp_path,labels=[
        label("SYN-A",False,mature="2026-01-15T00:00:00Z",
              published="2026-01-16T00:00:00Z")],k=1)
    r=evaluate(files)
    assert r["source_document_matched_known_failures"]==0
    assert r["unknown_or_source_censored_count"]==1
    assert r["blocker_counts"]["OUTCOME_NOT_MATURE_OR_AVAILABLE"]==1


def test_positive_onset_after_exact_horizon_counts_failure_not_hit(tmp_path):
    files=scenario(tmp_path,labels=[
        label("SYN-A",True,mature="2026-02-20T00:00:00Z",
              published="2026-02-21T00:00:00Z",
              onset="2026-02-01T00:01:00Z")],k=1)
    r=evaluate(files)
    assert r["source_document_matched_early_hits"]==0
    assert r["source_document_matched_known_failures"]==1


def test_missing_all_results_has_no_denominator_illusion(tmp_path):
    files=scenario(tmp_path,labels=[])
    r=evaluate(files)
    assert r["top_k_selected_count"]==3
    assert r["source_document_matched_early_hits"]==0
    assert r["source_document_matched_known_failures"]==0
    assert r["unknown_or_source_censored_count"]==3
    assert r["precision_on_locally_documented_known"] is None
    assert r["locally_documented_precision_full_k_ceiling"]==1.0
    assert r["real_future_leader_precision"] is None


def test_unknown_or_duplicate_source_security_claim_rejected(tmp_path):
    files=scenario(tmp_path)
    def unknown(m):m["claims"].append({**m["claims"][0],"security_id":"NOT_FROZEN"})
    change_manifest(files[2],unknown)
    with pytest.raises(ValueError,match="unknown|frozen"):
        evaluate(files)
    files=scenario(tmp_path/"second")
    change_manifest(files[2],lambda m:m["claims"].append(dict(m["claims"][0])))
    with pytest.raises(ValueError,match="Duplicate|duplicate"):
        evaluate(files)


def test_wrong_bound_freeze_digest_and_outcomes_digest_rejected(tmp_path):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda m:m.update(ranked_snapshot_sha256="0"*64))
    with pytest.raises(ValueError,match="ranked|SHA|hash"):
        evaluate(files)
    another=scenario(tmp_path/"later")
    change_manifest(another[2],lambda m:m.update(outcomes_sha256="0"*64))
    with pytest.raises(ValueError,match="outcome|SHA|hash"):
        evaluate(another)


def test_symlink_or_path_traversal_receipt_documents_not_followed(tmp_path):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda m:m["claims"][0].update(file="../../private.json"))
    with pytest.raises(ValueError,match="Unsafe|file|path"):
        evaluate(files)
    more=scenario(tmp_path/"more")
    path=more[2].parent/"SYN-A.json"
    real=more[2].parent/"real.json"
    path.rename(real);path.symlink_to(real)
    r=evaluate(more)
    assert r["blocker_counts"]["MISSING_OR_UNSAFE_LOCAL_SOURCE_FILE"]==1
    assert r["source_document_matched_early_hits"]==0


def test_invalid_document_issuer_id_even_when_document_hash_updated_is_censored(tmp_path):
    files=scenario(tmp_path)
    rewrite_doc(files,"SYN-A",lambda obj:obj.update(security_id="SYN-B"))
    r=evaluate(files)
    assert r["blocker_counts"]["SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"]==1


def test_no_mismatched_pair_labels_should_appear_in_sealed_evaluation(tmp_path):
    files=scenario(tmp_path)
    outcomes=json.loads(files[1].read_text())
    outcomes[0]["label_definition_id"]="SNEAKY_RETRO_LABELLING"
    files[1].write_text(json.dumps(outcomes))
    change_manifest(files[2],lambda m:m.update(
        outcomes_sha256=sha256(files[1].read_bytes()).hexdigest()))
    with pytest.raises(ValueError,match="label definition"):
        evaluate(files)


def test_ranked_cli_flags_predeclared_definition_and_rejects_bad_freeze(tmp_path):
    f=tmp_path/"rank.json"
    f.write_text(json.dumps([ranked("SYN-A",99)]))
    out=tmp_path/"seal.json"
    definition=protocol(tmp_path/"leader_rule.json")
    assert ranked_cli([
        "freeze","--input",str(f),"--out",str(out),"--market","KR",
        "--snapshot-at",SNAP,"--model-version",MODEL,
        "--horizon-days","30","--k","1",
        "--label-definition-id",LABEL_ID,
        "--label-definition-file",str(definition),
    ])==0
    assert json.loads(out.read_text())["label_definition_id"]==LABEL_ID
    assert json.loads(out.read_text())["label_rule_bytes_pinned"] is True


def test_audit_cli_writes_derived_only_report_and_safe_backup(tmp_path,capsys):
    from eraleader.cli import main
    files=scenario(tmp_path)
    out=tmp_path/"derived_only"
    main([
        "audit-ranked-outcome-receipts",
        "--freeze",str(files[0]),"--outcomes",str(files[1]),
        "--receipt-manifest",str(files[2]),
        "--evaluated-at",CUTOFF,
        "--definition-file",str(files[0].parent/"leader_rule.json"),
        "--out",str(out),
    ])
    summary=json.loads(capsys.readouterr().out)
    assert summary["actual_future_leader_accuracy_certified"] is False
    assert summary["locally_documented_known_count"]==2
    output=out/"ranked_outcome_receipts_research.json"
    report=json.loads(output.read_text())
    assert report["status"]==STATUS_RESEARCH
    assert report["official_leader_promotions"]==0
    zip_path=tmp_path/"safe_derived.zip"
    copied=create_backup(out,zip_path)
    assert copied["file_count"]==1
    assert verify_backup(zip_path)["status"]=="LOCAL_BACKUP_VERIFIED"
    from zipfile import ZipFile
    with ZipFile(zip_path) as z:
        assert z.namelist()==["ranked_outcome_receipts_research.json","MANIFEST.json"]
        assert not any(x.endswith(".json") and "SYN" in x for x in z.namelist())
    restored=tmp_path/"restored"
    restore_backup(zip_path,restored)
    assert (restored/output.name).read_bytes()==output.read_bytes()


def test_rehashed_retrospective_seal_flag_cannot_fake_prospective_cohort(tmp_path):
    from eraleader.ranked_discovery import _canonical
    files=scenario(tmp_path,retrospective=True)
    frozen=json.loads(files[0].read_text())
    frozen["retrospective_freeze"]=False
    frozen["content_sha256"]=sha256(_canonical({
        k:v for k,v in frozen.items() if k!="content_sha256"
    })).hexdigest()
    files[0].write_text(json.dumps(frozen))
    change_manifest(files[2],lambda m:m.update(
        ranked_snapshot_sha256=frozen["content_sha256"]))
    with pytest.raises(ValueError,match="retrospective"):
        evaluate(files)


def test_rehashed_independent_clock_attestation_claim_cannot_upgrade_source(tmp_path):
    from eraleader.ranked_discovery import _canonical
    files=scenario(tmp_path)
    frozen=json.loads(files[0].read_text())
    frozen["timestamp_independently_attested"]=True
    frozen["content_sha256"]=sha256(_canonical({
        k:v for k,v in frozen.items() if k!="content_sha256"
    })).hexdigest()
    files[0].write_text(json.dumps(frozen))
    change_manifest(files[2],lambda m:m.update(
        ranked_snapshot_sha256=frozen["content_sha256"]))
    with pytest.raises(ValueError,match="timestamp|attested|certification"):
        evaluate(files)


def test_extra_manifest_metadata_claimed_verification_not_allowed(tmp_path):
    files=scenario(tmp_path)
    change_manifest(files[2],lambda obj:obj.update(
        officially_certified_by_the_exchange=True))
    with pytest.raises(ValueError,match="schema fields"):
        evaluate(files)


def test_leader_rule_bytes_changed_under_same_predeclared_id_are_rejected(tmp_path):
    files=scenario(tmp_path)
    path=files[0].parent/"leader_rule.json"
    earlier=sha256(path.read_bytes()).hexdigest()
    rule=json.loads(path.read_text())
    rule["positive_criterion"]="Revised success definition after observing winners."
    path.write_text(json.dumps(rule,sort_keys=True))
    assert sha256(path.read_bytes()).hexdigest()!=earlier
    with pytest.raises(ValueError,match="rule content SHA"):
        evaluate(files)


def test_staged_rule_protocol_market_or_horizon_mismatch_denied_before_seal(tmp_path):
    rowfile=tmp_path/"candidates.json"
    rowfile.write_text(json.dumps([ranked("SYN-A",90)]))
    protocol_file=protocol(tmp_path/"leader_rule.json",market="US",horizon=30)
    with pytest.raises(ValueError,match="protocol mismatch"):
        freeze_ranked_snapshot(
            rowfile,tmp_path/"seal_kr.json",market="KR",snapshot_at=SNAP,
            model_version=MODEL,horizon_days=30,k=1,clock=FROZEN,
            label_definition_id=LABEL_ID,
            label_definition_file=protocol_file)
    assert not (tmp_path/"seal_kr.json").exists()


def test_rank_sealed_only_with_label_id_cannot_masquerade_as_content_pinned(tmp_path):
    root=tmp_path/"rank.json"
    root.write_text(json.dumps([ranked("SYN-A",90)]))
    older=tmp_path/"unpinned_bytes.json"
    freeze_ranked_snapshot(
        root,older,market="KR",snapshot_at=SNAP,model_version=MODEL,
        horizon_days=30,k=1,clock=FROZEN,label_definition_id=LABEL_ID)
    real=scenario(tmp_path/"later")
    from eraleader.ranked_discovery import _frozen
    assert _frozen(older)["label_definition_id"]==LABEL_ID
    with pytest.raises(ValueError,match="rule file SHA"):
        evaluate((older,real[1],real[2]))


def test_duplicate_label_protocol_json_keys_do_not_get_hashed_as_valid(tmp_path):
    root=tmp_path/"ranked.json"
    root.write_text(json.dumps([ranked("SYN-A",90)]))
    payload=protocol(tmp_path/"rule.json")
    obj=payload.read_text()
    payload.write_text(obj[:-1]+',"label_definition_id":"DUPLICATE"}')
    with pytest.raises(ValueError,match="Duplicate"):
        freeze_ranked_snapshot(
            root,tmp_path/"seal.json",market="KR",snapshot_at=SNAP,
            model_version=MODEL,horizon_days=30,k=1,clock=FROZEN,
            label_definition_id=LABEL_ID,label_definition_file=payload)
