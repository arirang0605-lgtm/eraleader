"""5_5 one-command first native WATCH+score frozen census (synthetic only)."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import subprocess
import sys

import pytest

from eraleader.native_first_capture import (
    capture_first_native_topk,read_capture_plan,PLAN_SCHEMA,
    OUTCOME_NAME,RECEIPT_NAME,_inspect_complete,
)
from eraleader.native_census_gate import audit_native_census
from eraleader.prospective_census_seal import indexed_audit_censuses, _index_path
from eraleader.rank_score_pipeline import compute_and_register_rank_scores
from eraleader.ranked_discovery import _frozen
from test_native_topk_freeze import fixture as native_fixture, NOW,LABEL
from test_rank_score_ledger import MODEL,WRITE
from test_rank_score_pipeline import score

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"capture_native_first_topk.py"


def prepare(tmp_path,*,market="KR",scored=True,top_k=1,cohort_id="FIRST_WATCH"):
    root=tmp_path/"original"
    root.mkdir(parents=True,exist_ok=True)
    bundle,rule,unused=native_fixture(root,market=market,scored=scored)
    plan={
        "schema_version":PLAN_SCHEMA,
        "cohort_id":cohort_id,"market":market,"model_version":MODEL,
        "score_ledger":str(bundle[4].absolute()),
        "watch_ledger":str(bundle[1].absolute()),
        "features_dir":str(bundle[2].absolute()),
        "label_definition_file":str(rule.absolute()),
        "label_definition_sha256":sha256(rule.read_bytes()).hexdigest(),
        "label_definition_id":LABEL,"horizon_days":180,
        "top_k":top_k,"max_age_hours":24,
    }
    planfile=tmp_path/"predeclared_native_capture_plan.json"
    planfile.write_text(json.dumps(plan,sort_keys=True))
    rootout=tmp_path/"first_captured"
    return bundle,rule,planfile,rootout


def capture(plan,root,clock=NOW):
    return capture_first_native_topk(plan,root,clock=clock)


def artifacts(out,cohort="FIRST_WATCH",market="KR"):
    slot=market.lower()+"_"+sha256(MODEL.encode()).hexdigest()[:24]
    folder=out/("native_"+slot)
    return (
        folder,
        folder/"evidence",
        folder/"registered",
        folder/"capture_receipt.json",
    )


@pytest.mark.parametrize("market",["KR","US"])
def test_first_real_native_watch_scores_frozen_and_indexed_census_in_one_call(tmp_path,market):
    b,rule,plan,output=prepare(tmp_path,market=market)
    native_before=sha256(b[4].read_bytes()).hexdigest()
    watch_before=sha256(b[1].read_bytes()).hexdigest()
    result=capture(plan,output)
    assert result["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"
    assert result["market"]==market
    assert result["original_complete_positive_watch"]==2
    assert result["first_frozen_top_k"]==1
    assert result["unknown_or_censored_now"]==1
    assert result["locally_documented_hits_not_official"]==0
    assert result["native_watch_score_provenance_rechecked"] is True
    assert result["independent_market_pit_certified"] is False
    assert result["real_future_leader_accuracy_certified"] is False
    assert result["official_leader_promotions"]==0
    assert result["messages_sent"]==0
    assert result["external_api_calls"]==0
    cohort, evidence, registry, receipt=artifacts(output,market=market)
    assert receipt.is_file()
    frozen=_frozen(evidence/"first_ranked_native_topk.json")
    assert frozen["retrospective_freeze"] is False
    assert frozen["native_cohort_binding"]["positive_watch_count"]==2
    assert frozen["requested_k"]==1
    assert not (evidence/OUTCOME_NAME).exists()
    assert not (evidence/RECEIPT_NAME).exists()
    assert sorted(p.name for p in registry.iterdir())==["census_FIRST_WATCH.json"]
    indexed=indexed_audit_censuses(registry,evaluated_at=NOW.isoformat(),clock=NOW)
    assert indexed["receipt_index_entries"]==1
    assert indexed["frozen_selected_denominator"]==1
    assert indexed["unknown_or_censored"]==1
    assert audit_native_census(
        registry,native_config=evidence/"native_source_proofs.json",
        evaluated_at=NOW.isoformat(),clock=NOW,
    )["fully_native_bound_cohorts"]==1
    assert sha256(b[4].read_bytes()).hexdigest()==native_before
    assert sha256(b[1].read_bytes()).hexdigest()==watch_before


def test_duplicate_run_never_rewrites_first_time_or_source_bytes(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    first=capture(plan,out)
    cohort,evidence,registry,receipt=artifacts(out)
    paths=[
        receipt,evidence/"first_ranked_native_topk.json",
        evidence/"predeclared_leader_rule.json",
        evidence/"census_input.json",
        evidence/"native_source_proofs.json",
        registry/"census_FIRST_WATCH.json",
        _index_path(registry),
        registry.parent/"registered_native_required.json",
    ]
    original={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    repeat=capture(plan,out,clock=NOW+timedelta(minutes=30))
    assert repeat["status"]=="ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY"
    assert repeat["frozen_rank_sha256"]==first["frozen_rank_sha256"]
    assert repeat["unknown_or_censored_now"]==1
    assert original=={str(p):sha256(p.read_bytes()).hexdigest() for p in paths}


def test_waits_until_all_original_positive_watch_native_scores_exist(tmp_path):
    b,rule,plan,out=prepare(tmp_path,scored=False)
    waiting=capture(plan,out)
    assert waiting["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
    assert waiting["waiting_reason"]=="WAITING_FOR_ALL_NATIVE_SCORES"
    assert waiting["positive_watch_count_observed"]==2
    assert waiting["native_score_count_observed"]==0
    assert not out.exists()
    score(b,at=WRITE)
    completed=capture(plan,out)
    assert completed["first_frozen_top_k"]==1
    assert completed["real_future_leader_accuracy_certified"] is False


def test_partial_score_count_is_not_cherry_picked_as_complete_native_watch(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    import sqlite3
    with sqlite3.connect(b[4]) as con:
        con.execute("DELETE FROM rank_score_events WHERE security_id='B'")
    result=capture(plan,out)
    assert result["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
    assert result["positive_watch_count_observed"]==2
    assert result["native_score_count_observed"]==1
    assert not out.exists()


def test_full_count_but_forged_first_score_or_feature_cannot_capture(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    file=b[2]/"A.json"
    file.write_bytes(file.read_bytes()+b" ")
    with pytest.raises(ValueError,match="feature|formula|provenance|original"):
        capture(plan,out)
    assert not out.exists()


def test_predeclared_k_cannot_be_greater_than_first_scores(tmp_path):
    b,rule,plan,out=prepare(tmp_path,top_k=3)
    with pytest.raises(ValueError,match="Top-K"):
        capture(plan,out)
    assert not out.exists()


def test_stale_score_cannot_be_backdated_by_capture(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    with pytest.raises(ValueError,match="Stale|fresh|score"):
        capture(plan,out,clock=NOW+timedelta(days=2))
    assert not out.exists()


def test_future_clock_input_cannot_materialize_when_original_watch_is_future(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    with pytest.raises(ValueError,match="Future|after"):
        capture(plan,out,clock=WRITE-timedelta(minutes=10))
    assert not out.exists()


def test_tampered_original_label_rule_is_rejected_before_freeze(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    rule.write_bytes(rule.read_bytes()+b" ")
    with pytest.raises(ValueError,match="Changed"):
        capture(plan,out)
    assert not out.exists()


def test_missing_future_source_files_are_left_missing_until_actual_maturity(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    _,evidence,registry,_=artifacts(out)
    assert not (evidence/"future_outcomes.json").exists()
    assert not (evidence/"future_source_receipts.json").exists()
    result=capture(plan,out)
    assert result["unknown_or_censored_now"]==1


def test_another_predeclared_plan_cannot_reuse_prior_complete_cohort_as_new_result(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    modified=json.loads(plan.read_text())
    modified["top_k"]=2
    plan.write_text(json.dumps(modified,sort_keys=True))
    with pytest.raises(ValueError,match="plan|capture"):
        capture(plan,out)
    assert _frozen(artifacts(out)[1]/"first_ranked_native_topk.json")["requested_k"]==1


@pytest.mark.parametrize("tamper",["frozen","native_config","census_manifest","receipt_index","rule","original_feature"])
def test_existing_capture_proof_mutation_blocks_no_fresh_replacement(tmp_path,tamper):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    cohort,evidence,reg,receipt=artifacts(out)
    files={
        "frozen":evidence/"first_ranked_native_topk.json",
        "native_config":evidence/"native_source_proofs.json",
        "census_manifest":reg/"census_FIRST_WATCH.json",
        "receipt_index":_index_path(reg),
        "rule":evidence/"predeclared_leader_rule.json",
        "original_feature":b[2]/"A.json",
    }
    path=files[tamper]
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises((ValueError,RuntimeError),match="revised|SHA|changed|native|source|first|pinned|invalid|corrupt"):
        capture(plan,out,clock=NOW+timedelta(minutes=8))
    assert receipt.exists()
    assert not (evidence/OUTCOME_NAME).exists()


def test_partial_crash_state_is_never_auto_repaired_or_credited(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    cohort,evidence,reg,receipt=artifacts(out)
    receipt.unlink()
    with pytest.raises(ValueError,match="Partial"):
        capture(plan,out,clock=NOW+timedelta(minutes=5))
    assert not receipt.exists()
    assert (reg/"census_FIRST_WATCH.json").exists()


def test_full_cohort_folder_deleted_but_lock_survives_cannot_regenerate_past(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    import shutil
    cohort,*_=artifacts(out)
    shutil.rmtree(cohort)
    with pytest.raises(ValueError,match="missing.*first|first.*missing"):
        capture(plan,out)
    assert not cohort.exists()


def test_same_source_score_can_be_captured_once_per_predeclared_model_not_later_overwritten(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    result=capture(plan,out,clock=NOW+timedelta(minutes=40))
    assert result["status"].startswith("ALREADY_CAPTURED")
    cohort,*_=artifacts(out)
    assert len(list(out.glob("native_*")))==1
    assert cohort.exists()


def test_symlinked_plan_is_refused_without_receipts(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    source=tmp_path/"source.json";plan.rename(source)
    plan.symlink_to(source)
    with pytest.raises(ValueError,match="Missing|linked|unsafe"):
        capture(plan,out)
    assert not out.exists()


def test_plan_rejects_outcome_label_schema_or_malformed_model(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    values=json.loads(plan.read_text())
    values["future_label_prediction"]=True
    plan.write_text(json.dumps(values))
    with pytest.raises(ValueError,match="plan"):
        capture(plan,out)
    assert not out.exists()


@pytest.mark.parametrize("change",[
    {"top_k":True},{"horizon_days":0},
    {"cohort_id":"../evil"},{"label_definition_sha256":"x"*64},
    {"max_age_hours":169},
])
def test_invalid_plan_cannot_create_any_first_write_directories(tmp_path,change):
    b,rule,plan,out=prepare(tmp_path)
    data=json.loads(plan.read_text())
    data.update(change)
    plan.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="plan|criterion|predeclared"):
        capture(plan,out)
    assert not out.exists()


def test_two_markets_distinct_immutable_capture_names_can_coexist(tmp_path):
    common=tmp_path/"collect"
    for market in ("KR","US"):
        b,rule,plan,unused=prepare(tmp_path/market,market=market,
                                   cohort_id="FIRST_"+market)
        result=capture(plan,common)
        assert result["market"]==market
    model_slug=sha256(MODEL.encode()).hexdigest()[:24]
    assert sorted(p.name for p in common.iterdir() if p.is_dir())==[
        "native_kr_"+model_slug,"native_us_"+model_slug]
    assert capture(tmp_path/"KR/predeclared_native_capture_plan.json",common)["status"].startswith("ALREADY")


def test_cli_with_old_synthetic_score_witness_fails_no_fake_new_os_time(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    result=subprocess.run([sys.executable,str(SCRIPT),
        "--plan",str(plan),"--capture-root",str(out)],
        capture_output=True,text=True)
    assert result.returncode==2
    assert "Stale" in result.stderr or "score" in result.stderr
    assert not out.exists()


def test_original_frozen_receipt_contains_no_preexisting_future_outcome(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    cohort,evidence,reg,receipt=artifacts(out)
    meta=json.loads(receipt.read_text())
    assert meta["original_outcome_unknown"]==1
    assert meta["real_future_leader_accuracy_certified"] is False
    assert meta["official_leader_promotions"]==0
    assert "SYN-A" not in receipt.read_text()
    assert str(b[1]) not in receipt.read_text()
    assert "is_future_leader" not in receipt.read_text()


def test_preset_output_symlink_fails_closed(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    elsewhere=tmp_path/"elsewhere";elsewhere.mkdir()
    out.symlink_to(elsewhere,target_is_directory=True)
    with pytest.raises(ValueError,match="Unsafe"):
        capture(plan,out)
    assert not list(elsewhere.iterdir())


def test_refuses_new_capture_if_outcome_evidence_already_exists(tmp_path,monkeypatch):
    from eraleader import native_first_capture as mod
    b,rule,plan,out=prepare(tmp_path)
    original=mod._create
    def injected(path,payload):
        result=original(path,payload)
        if path.name=="census_input.json":
            (path.parent/"future_outcomes.json").write_text("[]")
        return result
    monkeypatch.setattr(mod,"_create",injected)
    with pytest.raises(ValueError,match="must not exist"):
        capture(plan,out)
    assert not artifacts(out)[3].exists()


def test_same_market_and_model_cannot_be_reenrolled_by_changing_cohort_id(tmp_path):
    b,rule,plan,root=prepare(tmp_path,cohort_id="FIRST_EARLY")
    first=capture(plan,root)
    assert first["status"]=="FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"
    frozen=next(root.glob("native_*/evidence/first_ranked_native_topk.json"))
    original=sha256(frozen.read_bytes()).hexdigest()
    changed=json.loads(plan.read_text())
    changed["cohort_id"]="PICK_WINNERS_LATER"
    plan.write_text(json.dumps(changed,sort_keys=True))
    with pytest.raises(ValueError,match="plan|capture"):
        capture(plan,root,clock=NOW+timedelta(minutes=15))
    assert len(list(root.glob("native_*")))==1
    assert sha256(frozen.read_bytes()).hexdigest()==original


def test_original_source_registry_missing_before_score_does_not_create_capture(tmp_path):
    b,rule,plan,root=prepare(tmp_path,scored=False)
    b[1].unlink()
    result=capture(plan,root)
    assert result["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
    assert result["waiting_reason"]=="WAITING_FOR_POSITIVE_FIRST_WATCH"
    assert not root.exists()


def test_partial_crash_lock_but_missing_original_refuses_even_when_scores_gone(tmp_path):
    b,rule,plan,root=prepare(tmp_path)
    capture(plan,root)
    import shutil
    path=next(root.glob("native_*"))
    shutil.rmtree(path)
    b[4].unlink()
    with pytest.raises(ValueError,match="missing.*first|first.*missing"):
        capture(plan,root)
    assert not list(root.glob("native_*"))


def test_second_capture_with_no_lock_despite_complete_receipt_refused(tmp_path):
    b,rule,plan,root=prepare(tmp_path)
    capture(plan,root)
    next(root.glob(".capture_*.lock")).unlink()
    with pytest.raises(ValueError,match="lock"):
        capture(plan,root)
    assert next(root.glob("native_*/capture_receipt.json")).exists()


def test_receipt_cannot_rewrite_original_actual_freeze_timestamp(tmp_path):
    b,rule,plan,out=prepare(tmp_path)
    capture(plan,out)
    receipt=next(out.glob("native_*/capture_receipt.json"))
    event=json.loads(receipt.read_text())
    event["captured_at_utc"]=(NOW-timedelta(seconds=1)).isoformat()
    receipt.write_text(json.dumps(event,sort_keys=True))
    with pytest.raises(ValueError,match="clock differs"):
        capture(plan,out,clock=NOW+timedelta(minutes=3))
