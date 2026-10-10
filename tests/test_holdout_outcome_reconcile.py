"""Evidence reconciliation between a sealed research cohort and dated labels.

All inputs synthetic and intentionally NOT independently PIT certified.
"""
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZipFile
import json
import pytest

from eraleader.holdout_outcome_reconcile import reconcile_holdout_outcomes
from eraleader.local_backup import create_backup,verify_backup,restore_backup
from eraleader.cli import main
from test_frozen_holdout import freeze, outcomes_file

CLOCK=datetime(2026,11,1,tzinfo=timezone.utc)
CUTOFF="2026-10-10T17:00:00+09:00"


def reconcile(tmp_path,*,at=CUTOFF,labels=True):
    sealed=tmp_path/"holdout_manifest.json"
    if not sealed.exists():
        freeze(tmp_path)
    file=outcomes_file(tmp_path) if labels else None
    return reconcile_holdout_outcomes(sealed,evaluated_at=at,
                                      outcome_file=file,clock=CLOCK)


def test_due_without_any_label_file_still_unknown_not_failure(tmp_path):
    report=reconcile(tmp_path,labels=False)
    assert report["horizon_elapsed_count"]==4
    assert report["internally_evaluable_outcome_count"]==0
    assert report["unknown_or_censored_count"]==4
    assert report["evidence_status_counts"]["HORIZON_ELAPSED_NO_LABEL"]==4
    assert report["research_result_summary"] is None
    assert report["independent_outcome_source_certified"] is False
    assert report["official_leader_promotions"]==0
    assert report["leader_accuracy_certified"] is False


def test_available_research_labels_reconcile_but_never_certify_accuracy(tmp_path):
    report=reconcile(tmp_path)
    counts=report["evidence_status_counts"]
    assert report["frozen_candidates"]==4
    assert report["horizon_elapsed_count"]==4
    assert report["internally_evaluable_outcome_count"]==3
    assert report["unknown_or_censored_count"]==1
    assert counts["RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"]==3
    assert counts["LABEL_NOT_YET_AVAILABLE"]==1
    assert report["research_result_summary"]["true_early_discoveries"]==1
    assert report["research_result_summary"]["false_discoveries"]==1
    assert report["research_result_summary"]["late_or_post_onset"]==1
    assert report["independent_outcome_source_certified"] is False
    assert all(row["official_leader_status"] is None
               for row in report["candidate_evidence_sample"])


def test_early_negative_label_is_censored_not_false_discovery(tmp_path):
    freeze(tmp_path)
    path=outcomes_file(tmp_path)
    values=json.loads(path.read_text())
    negative=next(x for x in values if x["security_id"]=="B")
    negative["mature_at"]="2026-08-01T17:00:00+09:00"
    negative["outcome_available_at"]="2026-08-02T17:00:00+09:00"
    path.write_text(json.dumps(values))
    output=reconcile_holdout_outcomes(tmp_path/"holdout_manifest.json",
                       evaluated_at=CUTOFF,outcome_file=path,clock=CLOCK)
    assert output["evidence_status_counts"]["PREMATURE_NEGATIVE_LABEL"]==1
    assert output["internally_evaluable_outcome_count"]==2
    assert output["unknown_or_censored_count"]==2
    assert output["research_result_summary"]["false_discoveries"]==0


def test_before_full_horizon_all_due_statuses_pending_without_labels(tmp_path):
    report=reconcile(tmp_path,at="2026-04-15T17:00:00+09:00",labels=False)
    assert report["horizon_elapsed_count"]==0
    assert report["horizon_pending_count"]==4
    assert report["evidence_status_counts"]["HORIZON_PENDING_NO_LABEL"]==4


def test_future_published_label_not_misclassified_as_now_available(tmp_path):
    report=reconcile(tmp_path,at="2026-09-29T17:00:00+09:00")
    assert report["evidence_status_counts"]["LABEL_NOT_YET_AVAILABLE"]==2
    assert report["evidence_status_counts"]["RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"]==2
    assert report["internally_evaluable_outcome_count"]==2


def test_unmatched_outcome_label_cannot_improve_cohort_precision(tmp_path):
    freeze(tmp_path)
    path=outcomes_file(tmp_path)
    data=json.loads(path.read_text())
    data.append({"security_id":"OTHER-NOT-REGISTERED",
                 "label_definition_id":data[0]["label_definition_id"],
                 "is_future_leader":True,
                 "leader_start_at":"2026-06-01T10:00:00+09:00",
                 "mature_at":"2026-09-30T10:00:00+09:00",
                 "outcome_available_at":"2026-10-01T10:00:00+09:00"})
    path.write_text(json.dumps(data))
    output=reconcile_holdout_outcomes(tmp_path/"holdout_manifest.json",
                  evaluated_at=CUTOFF,outcome_file=path,clock=CLOCK)
    assert output["unmatched_outcome_count"]==1
    assert output["unmatched_outcome_sample"]==["OTHER-NOT-REGISTERED"]
    assert output["frozen_candidates"]==4
    assert output["internally_evaluable_outcome_count"]==3


@pytest.mark.parametrize("modify,error",[
    (lambda labels: labels[0].update(label_definition_id="AFTER_THE_FACT"),"definition"),
    (lambda labels: labels.append(dict(labels[0])),"Duplicate"),
    (lambda labels: labels[0].update(outcome_available_at="2026-07-01T10:00:00+09:00"),"before maturity"),
])
def test_invalid_or_revised_labels_fail_closed(tmp_path,modify,error):
    freeze(tmp_path)
    file=outcomes_file(tmp_path)
    labels=json.loads(file.read_text())
    modify(labels)
    file.write_text(json.dumps(labels))
    with pytest.raises(ValueError,match=error):
        reconcile_holdout_outcomes(tmp_path/"holdout_manifest.json",
            evaluated_at=CUTOFF,outcome_file=file,clock=CLOCK)


def test_corrupt_frozen_manifest_and_symlinked_outcomes_rejected(tmp_path):
    freeze(tmp_path)
    sealed=tmp_path/"holdout_manifest.json"
    data=json.loads(sealed.read_text())
    data["horizon_days"]=5
    sealed.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="hash mismatch"):
        reconcile_holdout_outcomes(sealed,evaluated_at=CUTOFF,clock=CLOCK)
    # A separate valid manifest with a symlinked label source is rejected.
    other=tmp_path/"separate"
    other.mkdir()
    freeze(other)
    outside=outcomes_file(tmp_path)
    alias=other/"label_alias.json"
    alias.symlink_to(outside)
    with pytest.raises(ValueError,match="Invalid or oversized"):
        reconcile_holdout_outcomes(other/"holdout_manifest.json",
                                  outcome_file=alias,evaluated_at=CUTOFF,clock=CLOCK)


def test_cli_optional_labels_and_derived_only_zip_backup(tmp_path,capsys):
    freeze(tmp_path)
    root=tmp_path/"derived"
    main(["reconcile-holdout-outcomes","--freeze-file",
          str(tmp_path/"holdout_manifest.json"),
          "--evaluated-at",CUTOFF,"--out",str(root)])
    out=json.loads(capsys.readouterr().out)
    assert out["internally_evaluable_outcome_count"]==0
    assert out["unknown_or_censored_count"]==4
    assert out["leader_accuracy_certified"] is False
    report=json.loads(Path(out["path"]).read_text())
    assert report["outcomes_sha256"] is None
    assert report["labels_file_provided"] is False
    (root/"vendor_outcomes_raw.json").write_text('{"secret":"DONT_ARCHIVE"}')
    target=tmp_path/"safe.zip"
    assert create_backup(root,target)["file_count"]==1
    assert verify_backup(target)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(target) as archive:
        assert archive.namelist()==["holdout_outcome_reconciliation_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(target,restored)
    assert json.loads((restored/"holdout_outcome_reconciliation_research.json").read_text())==report
    assert not (restored/"vendor_outcomes_raw.json").exists()


def test_cli_with_synthetic_labels_returns_consistent_uncertified_totals(tmp_path,capsys):
    freeze(tmp_path)
    file=outcomes_file(tmp_path)
    main(["reconcile-holdout-outcomes","--freeze-file",
          str(tmp_path/"holdout_manifest.json"),
          "--outcomes",str(file),"--evaluated-at",CUTOFF,
          "--out",str(tmp_path/"report")])
    out=json.loads(capsys.readouterr().out)
    assert out["internally_evaluable_outcome_count"]==3
    assert out["unknown_or_censored_count"]==1
    assert out["official_leader_promotions"]==0

def test_reconciled_due_clock_consistent_with_sealed_evaluator(tmp_path):
    pending = reconcile(tmp_path, at="2026-09-29T16:59:00+09:00", labels=False)
    assert pending["horizon_pending_count"] == 4
    assert pending["evidence_status_counts"]["HORIZON_PENDING_NO_LABEL"] == 4
    due = reconcile_holdout_outcomes(tmp_path/"holdout_manifest.json",
        evaluated_at="2026-09-29T17:00:00+09:00", clock=CLOCK)
    assert due["horizon_elapsed_count"] == 4
    assert due["evidence_status_counts"]["HORIZON_ELAPSED_NO_LABEL"] == 4


def test_reconcile_negative_one_minute_before_full_horizon_stays_censored(tmp_path):
    freeze(tmp_path)
    path = outcomes_file(tmp_path)
    rows = json.loads(path.read_text())
    negative = next(x for x in rows if x["security_id"] == "B")
    negative["mature_at"] = "2026-09-29T16:59:00+09:00"
    negative["outcome_available_at"] = "2026-09-30T17:00:00+09:00"
    path.write_text(json.dumps(rows))
    report = reconcile_holdout_outcomes(tmp_path/"holdout_manifest.json",
        evaluated_at=CUTOFF, outcome_file=path, clock=CLOCK)
    assert report["evidence_status_counts"]["PREMATURE_NEGATIVE_LABEL"] == 1
    assert report["research_result_summary"]["false_discoveries"] == 0
    assert report["internally_evaluable_outcome_count"] == 2
