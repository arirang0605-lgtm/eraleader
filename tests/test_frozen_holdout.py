from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pytest

from eraleader.frozen_holdout import (
    freeze_registered_candidates, evaluate_frozen_candidates, _read_frozen,
)
from eraleader.prospective import ProspectiveRegistry
from eraleader.cli import main

VERSION = "era-offline-join-0.1"
LABEL = "synthetic-leader-rule-v1"
SEEN = "2026-04-02T11:00:00+09:00"
CLOCK = datetime(2026, 4, 2, 8, tzinfo=timezone.utc)
FREEZE_CLOCK = datetime(2026, 4, 10, tzinfo=timezone.utc)

def run(securities, *, as_of=SEEN, market="KR"):
    return {
        "market":market,"as_of":as_of, "version":VERSION,
        "run_id":"test-"+"-".join(securities),
        "pit_certified":False,"offline_provenance":["synthetic_fixture"],
        "company_rows":[{
            "security_id":security,"market":market,"as_of":as_of,
            "state":"WATCH","full_score":None,
            "verified_future_leader_candidate":False,
            "research_growth_screen_hit":True
        } for security in securities]
    }

def setup_registry(tmp_path):
    ledger=tmp_path/"prospective.sqlite"
    p=ProspectiveRegistry(ledger)
    try:
        p.record_integrated(run(["A","B","C","D"]),clock=CLOCK)
        p.record_integrated(run(["OLD"],as_of="2024-01-03T17:00:00+09:00"),clock=CLOCK)
    finally:
        p.close()
    return ledger

def outcomes_file(tmp_path):
    outcomes=[
      {"security_id":"A","label_definition_id":LABEL,"is_future_leader":True,
       "leader_start_at":"2026-05-10T10:00:00+09:00",
       "mature_at":"2026-08-01T17:00:00+09:00",
       "outcome_available_at":"2026-08-03T17:00:00+09:00"},
      {"security_id":"B","label_definition_id":LABEL,"is_future_leader":False,
       "mature_at":"2026-10-02T17:00:00+09:00",
       "outcome_available_at":"2026-10-03T17:00:00+09:00"},
      {"security_id":"C","label_definition_id":LABEL,"is_future_leader":True,
       "leader_start_at":"2026-04-01T10:00:00+09:00",
       "mature_at":"2026-08-01T17:00:00+09:00",
       "outcome_available_at":"2026-08-03T17:00:00+09:00"},
      {"security_id":"D","label_definition_id":LABEL,"is_future_leader":True,
       "leader_start_at":"2026-08-10T10:00:00+09:00",
       "mature_at":"2027-01-01T10:00:00+09:00",
       "outcome_available_at":"2027-01-02T10:00:00+09:00"}
    ]
    target=tmp_path/"labels.json"
    target.write_text(json.dumps(outcomes),encoding="utf-8")
    return target

def freeze(tmp_path):
    return freeze_registered_candidates(setup_registry(tmp_path),
                                        tmp_path/"holdout_manifest.json",
                                        market="KR",model_version=VERSION,label_definition_id=LABEL,
                                        clock=FREEZE_CLOCK)

def test_freeze_records_only_actual_not_backfilled_signals(tmp_path):
    result=freeze(tmp_path)
    assert result["eligible_candidates"]==4
    assert result["excluded_historical_backfills"]==1
    manifest=_read_frozen(tmp_path/"holdout_manifest.json")
    assert manifest["model_version"]==VERSION
    assert manifest["outcome_labels_included"] is False
    assert manifest["historic_pit_certified"] is False
    assert {r["security_id"] for r in manifest["signals"]}=={"A","B","C","D"}
    assert all(r["registration_lag_days"]==0 for r in manifest["signals"])
    assert "is_future_leader" not in json.dumps(manifest)
    with pytest.raises(FileExistsError):
        freeze_registered_candidates(tmp_path/"prospective.sqlite",
                                     tmp_path/"holdout_manifest.json",
                                     market="KR",model_version=VERSION,label_definition_id=LABEL,
                                     clock=FREEZE_CLOCK)
    assert _read_frozen(tmp_path/"holdout_manifest.json")==manifest

def test_mature_outcome_censor_late_and_precision(tmp_path):
    freeze(tmp_path)
    result=evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                      outcomes_file(tmp_path),
                                      evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))
    assert result["eligible_candidates"]==4
    assert result["known_outcomes"]==3 and result["censored_outcomes"]==1
    assert result["true_early_discoveries"]==1
    assert result["false_discoveries"]==1 and result["late_or_post_onset"]==1
    assert result["precision_known_including_late"]==round(1/3,6)
    assert result["conservative_precision_floor"]==0.25
    assert result["coverage_fraction"]==0.75
    assert result["median_early_lead_days"]==38
    assert result["recall_complete_universe"] is None
    assert result["historic_pit_certified"] is False

def test_truncated_or_mutated_frozen_manifest_fails_closed(tmp_path):
    freeze(tmp_path)
    target=tmp_path/"holdout_manifest.json"
    body=json.loads(target.read_text())
    body["signals"].pop()
    target.write_text(json.dumps(body))
    with pytest.raises(ValueError,match="hash mismatch"):
        evaluate_frozen_candidates(target,outcomes_file(tmp_path),
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_outcome_publish_must_follow_maturity(tmp_path):
    freeze(tmp_path)
    path=outcomes_file(tmp_path)
    labels=json.loads(path.read_text())
    labels[0]["outcome_available_at"]="2026-07-01T17:00:00+09:00"
    path.write_text(json.dumps(labels))
    with pytest.raises(ValueError,match="before maturity"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",path,
                                  evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_outcome_label_not_allowed_at_freeze(tmp_path):
    freeze(tmp_path)
    with pytest.raises(ValueError,match="after freeze"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                   outcomes_file(tmp_path),
                                   evaluated_at="2026-04-01T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_duplicate_outcomes_rejected(tmp_path):
    freeze(tmp_path)
    labels=outcomes_file(tmp_path)
    body=json.loads(labels.read_text())
    body.append(body[0])
    labels.write_text(json.dumps(body))
    with pytest.raises(ValueError,match="Duplicate"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",labels,
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_future_registered_timestamp_fails_freeze(tmp_path):
    path=setup_registry(tmp_path)
    p=ProspectiveRegistry(path)
    try:
        p.record_integrated(run(["F"]),clock=datetime(2026,11,1,tzinfo=timezone.utc))
    finally:p.close()
    with pytest.raises(ValueError,match="future timestamps"):
        freeze_registered_candidates(path,tmp_path/"holdout_manifest.json",
                                     market="KR",model_version=VERSION,label_definition_id=LABEL,clock=FREEZE_CLOCK)
    assert not (tmp_path/"holdout_manifest.json").exists()

@pytest.mark.parametrize("lag",[-1,15,True,1.2])
def test_invalid_lag_rejected(tmp_path,lag):
    path=setup_registry(tmp_path)
    with pytest.raises(ValueError,match="Invalid observation lag"):
        freeze_registered_candidates(path,tmp_path/"holdout_manifest.json",
                                     market="KR",model_version=VERSION,label_definition_id=LABEL,
                                     max_observation_lag_days=lag,clock=FREEZE_CLOCK)

def test_freeze_empty_model_version_has_no_fake_success(tmp_path):
    path=setup_registry(tmp_path)
    result=freeze_registered_candidates(path,tmp_path/"holdout_manifest.json",
                                        market="KR",model_version="another-v99",label_definition_id=LABEL,clock=FREEZE_CLOCK)
    assert result["eligible_candidates"]==0
    assessment=evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                          outcomes_file(tmp_path),
                                          evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))
    assert assessment["known_outcomes"]==0
    assert assessment["precision_known_including_late"] is None

def test_cli_freeze_and_separate_outcome_report(tmp_path,capsys):
    path=tmp_path/"prospective.sqlite"
    now=datetime.now(timezone.utc)-timedelta(minutes=3)
    # Direct synthetic test only; CLI is not allowed to supply a fake clock.
    local=now.astimezone(ZoneInfo("Asia/Seoul"))
    asof=(local-timedelta(minutes=2)).isoformat()
    p=ProspectiveRegistry(path)
    try:p.record_integrated(run(["SYN"],as_of=asof),clock=now)
    finally:p.close()
    manifest=tmp_path/"holdout_manifest.json"
    main(["freeze-holdout","--ledger",str(path),"--market","KR",
          "--model-version",VERSION,"--label-definition-id",LABEL,"--freeze-file",str(manifest)])
    snap=json.loads(capsys.readouterr().out)
    assert snap["eligible_candidates"]==1
    with pytest.raises(SystemExit) as err:
        main(["freeze-holdout","--ledger",str(path),"--market","KR",
              "--model-version",VERSION,"--label-definition-id",LABEL,"--freeze-file",str(manifest)])
    assert err.value.code==2
    labels=tmp_path/"outcomes.json"
    labels.write_text("[]")
    future=datetime.now(timezone.utc).isoformat()
    main(["evaluate-holdout","--freeze-file",str(manifest),
          "--outcomes",str(labels),"--evaluated-at",future,
          "--out",str(tmp_path)])
    report=json.loads(capsys.readouterr().out)
    assert report["known_outcomes"]==0
    assert report["censored_outcomes"]==1
    assert json.loads((tmp_path/"holdout_evaluation_research.json").read_text())["historic_pit_certified"] is False

def test_future_evaluation_cutoff_is_rejected(tmp_path):
    freeze(tmp_path)
    with pytest.raises(ValueError,match="Future evaluation cutoff"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                   outcomes_file(tmp_path),
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,5,1,tzinfo=timezone.utc))

def test_known_outcomes_are_censored_when_publication_is_late(tmp_path):
    freeze(tmp_path)
    result=evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                      outcomes_file(tmp_path),
                                      evaluated_at="2026-07-01T17:00:00+09:00",
                                      clock=datetime(2026,10,11,tzinfo=timezone.utc))
    assert result["known_outcomes"]==0
    assert result["censored_outcomes"]==4
    assert result["precision_known_including_late"] is None

def test_frozen_holdout_and_report_are_allowlisted_in_local_backup(tmp_path):
    from eraleader.local_backup import create_backup, verify_backup, restore_backup
    from zipfile import ZipFile
    out=tmp_path/"holdout_out"
    out.mkdir()
    path=setup_registry(out)
    manifest=out/"holdout_manifest.json"
    freeze_registered_candidates(path,manifest,market="KR",
                                 model_version=VERSION,label_definition_id=LABEL,clock=FREEZE_CLOCK)
    labels=outcomes_file(tmp_path)
    report=evaluate_frozen_candidates(manifest,labels,
                                      evaluated_at="2026-10-10T17:00:00+09:00",
                                      clock=datetime(2026,10,11,tzinfo=timezone.utc))
    (out/"holdout_evaluation_research.json").write_text(json.dumps(report))
    (out/"private_vendor_raw.json").write_text('{"private_token":"never_archived"}')
    archive=tmp_path/"holdout_backup.zip"
    create_backup(out,archive)
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert {"holdout_manifest.json","holdout_evaluation_research.json","prospective.sqlite"}.issubset(z.namelist())
        assert "private_vendor_raw.json" not in z.namelist()
    restored=tmp_path/"holdout_restored"
    restore_backup(archive,restored)
    assert _read_frozen(restored/"holdout_manifest.json")["eligible_count"]==4

def test_evaluation_cannot_redefine_predeclared_horizon(tmp_path):
    frozen = freeze(tmp_path)
    assert frozen["horizon_days"] == 180
    assert frozen["label_definition_id"] == LABEL
    with pytest.raises(ValueError, match="cannot differ"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",
                                   outcomes_file(tmp_path),
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   horizon_days=365,
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_evaluation_cannot_swap_label_definition(tmp_path):
    freeze(tmp_path)
    labels=outcomes_file(tmp_path)
    rows=json.loads(labels.read_text())
    rows[0]["label_definition_id"]="after-the-fact-rule"
    labels.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="definition does not match"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",labels,
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

def test_preexisting_mature_outcome_not_a_prospective_holdout(tmp_path):
    freeze(tmp_path)
    labels=outcomes_file(tmp_path)
    rows=json.loads(labels.read_text())
    rows[0]["mature_at"]="2026-04-09T17:00:00+09:00"
    rows[0]["outcome_available_at"]="2026-04-09T18:00:00+09:00"
    rows[0]["leader_start_at"]="2026-04-07T10:00:00+09:00"
    labels.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="already mature or known"):
        evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",labels,
                                   evaluated_at="2026-10-10T17:00:00+09:00",
                                   clock=datetime(2026,10,11,tzinfo=timezone.utc))

@pytest.mark.parametrize("bad_horizon",[0,-5,True,1096])
def test_invalid_predeclared_horizon_rejected(tmp_path,bad_horizon):
    registry=setup_registry(tmp_path)
    with pytest.raises(ValueError,match="fixed at freeze"):
        freeze_registered_candidates(registry,tmp_path/"manifest.json",market="KR",
                                     model_version=VERSION,label_definition_id=LABEL,
                                     horizon_days=bad_horizon,clock=FREEZE_CLOCK)

def test_missing_label_protocol_denied_at_freeze(tmp_path):
    registry=setup_registry(tmp_path)
    with pytest.raises(ValueError,match="predeclared"):
        freeze_registered_candidates(registry,tmp_path/"manifest.json",market="KR",
                                     model_version=VERSION,label_definition_id="",
                                     clock=FREEZE_CLOCK)

def test_premature_negative_label_is_censored_not_declared_false_positive(tmp_path):
    freeze(tmp_path)
    labels=outcomes_file(tmp_path)
    body=json.loads(labels.read_text())
    body[1]["mature_at"]="2026-08-01T17:00:00+09:00"
    body[1]["outcome_available_at"]="2026-08-03T17:00:00+09:00"
    labels.write_text(json.dumps(body))
    result=evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",labels,
                                    evaluated_at="2026-10-10T17:00:00+09:00",
                                    clock=datetime(2026,10,11,tzinfo=timezone.utc))
    assert result["true_early_discoveries"]==1
    assert result["false_discoveries"]==0
    assert result["late_or_post_onset"]==1
    assert result["known_outcomes"]==2
    assert result["censored_outcomes"]==2
    assert result["premature_negative_labels_censored"]==1
    assert result["precision_known_including_late"]==0.5
    assert result["conservative_precision_floor"]==0.25
    assert result["historic_pit_certified"] is False


def test_negative_label_maturing_on_exact_frozen_horizon_is_allowed(tmp_path):
    freeze(tmp_path)
    labels=outcomes_file(tmp_path)
    body=json.loads(labels.read_text())
    # First candidate registered at 2026-04-02 KST; 180 days is 2026-09-29.
    body[1]["mature_at"]="2026-09-29T17:00:00+09:00"
    body[1]["outcome_available_at"]="2026-09-30T10:00:00+09:00"
    labels.write_text(json.dumps(body))
    result=evaluate_frozen_candidates(tmp_path/"holdout_manifest.json",labels,
                                    evaluated_at="2026-10-10T17:00:00+09:00",
                                    clock=datetime(2026,10,11,tzinfo=timezone.utc))
    assert result["false_discoveries"]==1
    assert result["premature_negative_labels_censored"]==0
    assert result["known_outcomes"]==3
    assert result["historic_pit_certified"] is False
