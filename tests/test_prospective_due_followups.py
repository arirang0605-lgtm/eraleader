"""5_5 all-cohort outcome due queue: synthetic first-write evidence only."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import subprocess
import sys

import pytest

from eraleader.local_backup import create_backup,restore_backup,verify_backup
from eraleader.prospective_census import register_census
from eraleader.prospective_census_seal import indexed_register_census,_index_path
from eraleader.prospective_due_followups import (
    audit_prospective_due_followups,publish_due_followups,render_due_followups,
)
from eraleader.prospective_census import _due
from eraleader.ranked_discovery import _frozen
from test_prospective_census import prepare,restore
from test_ranked_outcome_receipts import scenario,NOW,FROZEN,CUTOFF
from test_native_census_gate import prepare as prepare_native,config as native_config
from test_native_topk_freeze import NOW as NATIVE_NOW
from eraleader.native_census_gate import register_native_census

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_census.py"


def create(folder,*,market="KR",name="census_first.json",registry=None):
    spec,saved,frozen,outcome,receipt=prepare(folder,market=market)
    root=registry or (folder/"first_write_registry")
    indexed_register_census(spec,root,name,clock=FROZEN+timedelta(minutes=3))
    return root,saved,frozen,outcome,receipt


def evaluate(root,*,at=CUTOFF,clock=NOW,config=None):
    return audit_prospective_due_followups(
        root,evaluated_at=at,clock=clock,native_config=config)


def test_due_missing_both_is_followup_not_zero_or_loss(tmp_path):
    root,_,frozen,_,_=create(tmp_path)
    before=frozen.read_bytes()
    result=evaluate(root)
    assert result["status"]=="LOCAL_DUE_EVIDENCE_GAPS_NOT_CERTIFIED"
    assert result["first_write_index_verified"] is True
    assert result["cohorts_evaluated_all"]==1
    assert result["original_frozen_k_denominator"]==3
    assert result["horizon_elapsed_cohorts"]==1
    assert result["due_evidence_followups"]==1
    assert result["due_evidence_followup_k"]==3
    assert result["due_unknown_or_censored_k"]==3
    assert result["all_unknown_or_censored_k"]==3
    assert result["followup_state_counts"]=={"DUE_BOTH_SOURCES_MISSING":1}
    assert result["real_precision_at_k"] is None
    assert result["official_leader_promotions"]==0
    assert result["external_api_calls"]==0 and result["messages_sent"]==0
    assert frozen.read_bytes()==before


def test_pending_horizon_does_not_create_overdue_false_alarm(tmp_path):
    root,*_=create(tmp_path)
    summary=evaluate(root,at="2026-01-02T00:00:00+00:00")
    assert summary["due_evidence_followups"]==0
    assert summary["horizon_elapsed_cohorts"]==0
    assert summary["followup_state_counts"]=={"AWAITING_HORIZON":1}
    assert summary["followup_rows"][0]["days_overdue"] is None
    assert summary["followup_rows"][0]["days_until_due"]>0
    assert summary["status"]=="LOCAL_DUE_EVIDENCE_QUEUE_NOT_CERTIFIED"


@pytest.mark.parametrize("one,expected",[
    ("outcome","DUE_RECEIPTS_MISSING"),
    ("receipt","DUE_OUTCOMES_MISSING"),
])
def test_one_outcome_source_is_missing_not_known_negative(tmp_path,one,expected):
    root,saved,_,outcome,receipt=create(tmp_path)
    p=outcome if one=="outcome" else receipt
    p.write_bytes(saved[str(p)])
    result=evaluate(root)
    assert result["followup_state_counts"]=={expected:1}
    assert result["due_evidence_followups"]==1
    assert result["all_unknown_or_censored_k"]==3
    assert result["followup_rows"][0]["known_failures_claimed_only"]==0


def test_source_pair_keeps_censored_topk_and_reports_followup(tmp_path):
    root,saved,*_=create(tmp_path)
    restore(saved)
    result=evaluate(root)
    assert result["followup_state_counts"]=={"DUE_PAIRED_CENSORED":1}
    assert result["original_frozen_k_denominator"]==3
    assert result["due_unknown_or_censored_k"]==1
    row=result["followup_rows"][0]
    assert row["known_hits_claimed_only"]==1
    assert row["known_failures_claimed_only"]==1
    assert row["unknown_or_censored"]==1
    assert result["real_precision_at_k"] is None


def test_due_pair_with_all_local_labels_is_still_unverified(tmp_path):
    folder=tmp_path/"synthetic"
    frozen,outcome,receipt=scenario(folder,k=2)
    original={outcome:outcome.read_bytes(),receipt:receipt.read_bytes()}
    outcome.unlink();receipt.unlink()
    spec=frozen.parent/"census_input.json"
    spec.write_text(json.dumps([{"frozen":frozen.name,
        "definition":"leader_rule.json","outcomes":outcome.name,"receipts":receipt.name}]))
    registry=tmp_path/"registry"
    indexed_register_census(spec,registry,"census_two.json",
                            clock=FROZEN+timedelta(minutes=2))
    for p,raw in original.items():p.write_bytes(raw)
    result=evaluate(registry)
    assert result["original_frozen_k_denominator"]==2
    assert result["followup_state_counts"]=={
        "DUE_PAIRED_LOCALLY_KNOWN_NOT_CERTIFIED":1}
    assert result["due_evidence_followups"]==0
    assert result["future_leader_accuracy_certified"] is False


def test_early_pair_does_not_claim_horizon_maturity(tmp_path):
    root,saved,*_=create(tmp_path)
    restore(saved)
    result=evaluate(root,at="2026-01-02T00:00:00+00:00")
    assert result["horizon_elapsed_cohorts"]==0
    assert result["followup_state_counts"]=={"AWAITING_HORIZON_WITH_LOCAL_PAIR":1}
    assert result["real_precision_at_k"] is None


def test_exact_market_local_horizon_boundary(tmp_path):
    root,_,frozen,*_=create(tmp_path)
    due=_due(_frozen(frozen))
    just_before=evaluate(root,at=(due-timedelta(microseconds=1)).isoformat())
    exactly=evaluate(root,at=due.isoformat())
    assert just_before["horizon_elapsed_cohorts"]==0
    assert exactly["horizon_elapsed_cohorts"]==1
    assert exactly["followup_rows"][0]["days_overdue"]==0


def test_kr_us_multi_registry_no_survivor_or_success_selection(tmp_path):
    root=tmp_path/"all_registry"
    _,saved_kr,*_=create(tmp_path/"kr",registry=root,
                            name="census_kr.json")
    create(tmp_path/"us",market="US",registry=root,name="census_us.json")
    restore(saved_kr)
    result=evaluate(root)
    assert result["cohorts_evaluated_all"]==2
    assert result["original_frozen_k_denominator"]==6
    assert result["due_evidence_followups"]==2
    assert result["due_evidence_followup_k"]==6
    assert result["all_unknown_or_censored_k"]==4
    assert [r["market"] for r in result["followup_rows"]]==["US","KR"] or (
        {r["market"] for r in result["followup_rows"]}=={"US","KR"})


def test_source_id_is_not_exposed_in_json_or_html(tmp_path):
    root,saved,*_=create(tmp_path)
    restore(saved)
    result=evaluate(root)
    raw=json.dumps(result)
    html=render_due_followups(result)
    assert "SYN-A" not in raw and "SYN-B" not in raw
    assert "census_first.json" not in raw
    assert str(root.parent) not in raw and str(root.parent) not in html
    assert "CIK0000" not in html and "SYN-A" not in html
    assert "공식 대장주 0" in html
    assert "N/A" in html


def test_multi_rows_escapes_untrusted_manifest_filename(tmp_path):
    root,*_=create(tmp_path)
    report=evaluate(root)
    forged=deepcopy(report)
    forged["followup_rows"][0]["registry_ref"]="<script>alert(1)</script>"
    rendered=render_due_followups(forged)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered  # Displayed untrusted reference must be HTML-escaped


@pytest.mark.parametrize("bad",[
    ("real_precision_at_k",0.9),("official_leader_promotions",1),
    ("messages_sent",1),("external_api_calls",1),
    ("first_write_index_verified",False),
    ("future_leader_accuracy_certified",True),
])
def test_renderer_rejects_fake_source_pit_performance_or_delivery(tmp_path,bad):
    root,*_=create(tmp_path)
    forged=deepcopy(evaluate(root))
    forged[bad[0]]=bad[1]
    with pytest.raises(ValueError,match="Unsafe"):
        render_due_followups(forged)


def test_index_deleted_refuses_computation(tmp_path):
    root,*_=create(tmp_path)
    _index_path(root).unlink()
    with pytest.raises(ValueError,match="index"):
        evaluate(root)


def test_unindexed_legacy_cannot_be_relabelled_certified(tmp_path):
    spec,*_=prepare(tmp_path)
    root=tmp_path/"legacy"
    register_census(spec,root,"census_legacy.json",clock=FROZEN)
    with pytest.raises(ValueError,match="index"):
        evaluate(root)


def test_registry_tamper_fails_without_issuing_followup(tmp_path):
    root,*_=create(tmp_path)
    item=root/"census_first.json"
    item.write_bytes(item.read_bytes()+b" ")
    with pytest.raises(ValueError,match="index|SHA|receipt"):
        evaluate(root)


def test_source_label_definition_rewrite_fails_closed(tmp_path):
    root,_,frozen,*_=create(tmp_path)
    rule=frozen.parent/"leader_rule.json"
    rule.write_bytes(rule.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="label definition|SHA|mismatch"):
        evaluate(root)


def test_symlink_partial_receipt_never_accepted_as_missing(tmp_path):
    root,_,_,_,receipt=create(tmp_path)
    external=tmp_path/"outside.json"
    external.write_text("[]")
    receipt.symlink_to(external)
    with pytest.raises(ValueError,match="linked|unsafe"):
        evaluate(root)


def test_invalid_future_cutoff_rejected(tmp_path):
    root,*_=create(tmp_path)
    with pytest.raises(ValueError,match="Future"):
        evaluate(root,at="2027-01-01T00:00:00+00:00")


def test_mid_audit_source_revision_rejected_not_published(tmp_path,monkeypatch):
    import eraleader.prospective_due_followups as mod
    root,saved,_,outcome,_=create(tmp_path)
    original=mod._build_queue
    invoked=[0]
    def change(*a,**kw):
        answer=original(*a,**kw)
        invoked[0]+=1
        if invoked[0]==1:
            outcome.write_bytes(saved[str(outcome)])
        return answer
    monkeypatch.setattr(mod,"_build_queue",change)
    with pytest.raises(RuntimeError,match="revised|changed"):
        evaluate(root)
    assert invoked[0]==2


def test_native_marker_requires_strict_native_config(tmp_path):
    *_,source,item=prepare_native(tmp_path/"native")
    proof=native_config(tmp_path/"native_sources.json",[item])
    root=tmp_path/"indexed"
    register_native_census(source,root,"census_native.json",
                           native_config=proof,clock=NATIVE_NOW+timedelta(minutes=2))
    with pytest.raises(ValueError,match="Native|config"):
        evaluate(root,at=(NATIVE_NOW+timedelta(minutes=3)).isoformat(),
                 clock=NATIVE_NOW+timedelta(minutes=4))
    result=evaluate(root,at=(NATIVE_NOW+timedelta(minutes=3)).isoformat(),
                    clock=NATIVE_NOW+timedelta(minutes=4),config=proof)
    assert result["native_watch_score_rechecked"] is True
    assert result["original_frozen_k_denominator"]==1
    assert result["followup_state_counts"]=={"AWAITING_HORIZON":1}


def test_native_config_without_required_first_write_marker_rejected(tmp_path):
    root,*_=create(tmp_path)
    bogus=tmp_path/"native.json";bogus.write_text("{}")
    with pytest.raises(ValueError,match="Native|config"):
        evaluate(root,config=bogus)


def test_derived_only_safe_backup_and_new_path_restore(tmp_path):
    root,_,frozen,*_=create(tmp_path)
    original=sha256(frozen.read_bytes()).hexdigest()
    report=evaluate(root)
    out=tmp_path/"derived"
    paths=publish_due_followups(report,out)
    assert paths["messages_sent"]==0
    archive=tmp_path/"due_archive.zip"
    assert create_backup(out,archive)["file_count"]==2
    assert verify_backup(archive)["file_count"]==2
    target=tmp_path/"new_location"
    assert restore_backup(archive,target)["status"]=="LOCAL_BACKUP_RESTORED"
    assert json.loads((target/"prospective_due_followups_research.json").read_text())==report
    assert sha256(frozen.read_bytes()).hexdigest()==original


def test_linked_derived_output_halts_before_any_file_is_written(tmp_path):
    root,*_=create(tmp_path)
    report=evaluate(root)
    actual=tmp_path/"real";actual.mkdir()
    link=tmp_path/"output_link";link.symlink_to(actual,target_is_directory=True)
    with pytest.raises(ValueError,match="Unsafe"):
        publish_due_followups(report,link)
    assert not list(actual.iterdir())


def test_cli_optin_preserves_old_census_output_and_writes_due_queue(tmp_path):
    root,*_=create(tmp_path)
    derived=tmp_path/"derived"
    run=subprocess.run([sys.executable,str(SCRIPT),"audit","--receipt-index",
        "--registry-dir",str(root),"--evaluated-at",CUTOFF,
        "--due-followups","--out",str(derived)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    output=json.loads(run.stdout)
    assert output["census_audit"]["frozen_selected_denominator"]==3
    assert output["due_followups"]["due_evidence_followups"]==1
    baseline=json.loads((derived/"prospective_census_research.json").read_text())
    assert baseline==output["census_audit"]
    assert (derived/"site"/"prospective_due_followups.html").is_file()


def test_cli_default_still_emits_only_baseline_no_queue(tmp_path):
    root,*_=create(tmp_path)
    derived=tmp_path/"derived"
    run=subprocess.run([sys.executable,str(SCRIPT),"audit","--receipt-index",
        "--registry-dir",str(root),"--evaluated-at",CUTOFF,
        "--out",str(derived)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    output=json.loads(run.stdout)
    assert "due_followups" not in output
    assert not (derived/"prospective_due_followups_research.json").exists()


def test_cli_due_queue_requires_explicit_first_write_index(tmp_path):
    spec,*_=prepare(tmp_path)
    root=tmp_path/"legacy"
    register_census(spec,root,"census_legacy.json",clock=FROZEN)
    derived=tmp_path/"derived"
    run=subprocess.run([sys.executable,str(SCRIPT),"audit",
        "--registry-dir",str(root),"--evaluated-at",CUTOFF,
        "--due-followups","--out",str(derived)],capture_output=True,text=True)
    assert run.returncode==2
    assert "receipt-index" in run.stderr
    assert not derived.exists()


def test_display_limit_never_hides_full_unresolved_k_denominator(tmp_path):
    from eraleader.prospective_due_followups import _report,MAX_DISPLAY_ROWS
    root,*_=create(tmp_path)
    example=evaluate(root)["followup_rows"][0]
    n=MAX_DISPLAY_ROWS+13
    rows=[{**example,"cohort_ref":f"KR-{i:016x}","cohort_position":i+1}
          for i in range(n)]
    totals={"cohorts":n,"k":3*n,"hits":0,"failures":0,"unknown":3*n,
            "due_cohorts":n,"due_k":3*n,"due_unknown":3*n,
            "due_gaps":n,"due_gap_k":3*n,"due_gap_unknown":3*n}
    strict={"registered_cohort_count":n,"frozen_selected_denominator":3*n,
            "locally_documented_early_hits":0,
            "locally_documented_known_failures":0,
            "unknown_or_censored":3*n,"registry_manifest_count":n,
            "first_write_receipts_verified":True,
            "receipt_index_head_sha256":"a"*64}
    result=_report(rows,totals,strict,NOW)
    assert result["cohorts_evaluated_all"]==n
    assert result["original_frozen_k_denominator"]==3*n
    assert result["due_evidence_followups"]==n
    assert result["displayed_followup_rows"]==MAX_DISPLAY_ROWS
    assert result["followup_rows_truncated"] is True
    assert len(result["followup_rows"])==MAX_DISPLAY_ROWS
    changed=[dict(row) for row in rows]
    changed[-1]["followup_state"]="DUE_RECEIPTS_MISSING"
    revised=_report(changed,totals,strict,NOW+timedelta(hours=1))
    assert revised["followup_rows"]==result["followup_rows"]
    assert revised["due_evidence_followups"]==result["due_evidence_followups"]
    assert revised["due_evidence_state_sha256"]!=result["due_evidence_state_sha256"]
    assert "전체 코호트" in render_due_followups(result)
