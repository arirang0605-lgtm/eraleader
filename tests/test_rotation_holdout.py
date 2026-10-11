"""Synthetic pair rotation holdout freeze/label maturity; no real alpha."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
from copy import deepcopy

import pytest

from eraleader.rotation_holdout import (
    freeze_rotation_pairs, audit_rotation_pair_outcomes, _read_rotation_freeze,
    FROZEN_SCHEMA, FREEZE_STATUS, AUDIT_STATUS,
)
from eraleader.frozen_holdout import _digest
from test_peer_score_series import setup, MODEL, ROOT

FREEZE = ROOT+timedelta(days=3,minutes=20)
AFTER = FREEZE+timedelta(days=6,hours=1)
HORIZON = 5
LABEL_ID = "synthetic-rotation-pair-label-v1"


def scenario(tmp_path, *, second_advantage=72, market="KR"):
    if market != "KR":
        raise ValueError("Use explicit US scenario fixture")
    watch, scores, features = setup(tmp_path,second_advantage=second_advantage)
    frozen = tmp_path/"rotation_pair_holdout.json"
    return (watch,scores,features,frozen)


def freeze(bundle, *, clock=FREEZE, horizon=HORIZON, label=LABEL_ID):
    watch,scores,features,frozen=bundle
    return freeze_rotation_pairs(
        watch,scores,features,frozen,
        market="KR",model_version=MODEL,label_definition_id=label,
        horizon_days=horizon,clock=clock)


def read(bundle):
    return _read_rotation_freeze(bundle[3])


def label_record(sec,hit, *, mature="2026-10-09T10:20:00+09:00",
                 known="2026-10-09T11:00:00+09:00",
                 onset="2026-10-06T09:00:00+09:00"):
    record={
        "security_id":sec,"label_definition_id":LABEL_ID,
        "is_future_leader":hit,
        "mature_at":mature,"outcome_available_at":known,
    }
    if hit:
        record["leader_start_at"]=onset
    return record


def labels_path(tmp_path, *, contender=True, incumbent=False,
                negative_mature=None, positive_mature=None,
                positive_onset=None, published_at=None):
    records=[
        label_record("NEW",contender,
                     mature=positive_mature or "2026-10-09T10:20:00+09:00",
                     known=published_at or "2026-10-09T11:00:00+09:00",
                     onset=positive_onset or "2026-10-06T09:00:00+09:00"),
        label_record("INC",incumbent,
                     mature=negative_mature or "2026-10-09T10:20:00+09:00",
                     known=published_at or "2026-10-09T11:00:00+09:00",
                     onset="2026-10-06T08:30:00+09:00"),
    ]
    path=tmp_path/"local_declared_pair_outcomes.json"
    path.write_text(json.dumps(records,sort_keys=True))
    return path


def audit(bundle, *, labels=None, cutoff=AFTER, **extra):
    return audit_rotation_pair_outcomes(
        bundle[3],evaluated_at=cutoff.isoformat(),
        outcome_file=labels,clock=AFTER,**extra)


def test_freeze_only_explicit_contemporaneous_two_score_witnesses_and_no_labels(tmp_path):
    b=scenario(tmp_path)
    result=freeze(b)
    assert result["status"]==FREEZE_STATUS
    assert result["eligible_pairs"]==1
    assert result["outcome_labels_included"] is False
    raw=read(b)
    assert raw["schema_version"]==FROZEN_SCHEMA
    assert raw["frozen_at_utc"]==FREEZE.isoformat()
    assert raw["market"]=="KR" and raw["model_version"]==MODEL
    assert raw["horizon_days"]==5 and raw["label_definition_id"]==LABEL_ID
    assert raw["eligible_pair_count"]==1
    assert raw["official_leader_replacements"]==0
    assert raw["historic_pit_certified"] is False
    pair=raw["pairs"][0]
    assert pair["incumbent_security_id"]=="INC"
    assert pair["contender_security_id"]=="NEW"
    assert pair["last_two_paired_market_days"]==["2026-10-03","2026-10-04"]
    assert len(pair["last_two_paired_score_event_hashes"])==2
    assert all(len(x["incumbent_event_sha256"])==64 for x in pair["last_two_paired_score_event_hashes"])
    assert "outcome" not in json.dumps(raw).lower().replace("outcome_labels_included","")
    assert "is_future_leader" not in json.dumps(raw)
    assert len(pair["pair_id"])==64


def test_repeated_freeze_never_overwrites_existing_sealed_pair(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    before=b[3].read_bytes()
    with pytest.raises(FileExistsError):
        freeze(b,clock=FREEZE+timedelta(minutes=3))
    assert b[3].read_bytes()==before


def test_stale_research_score_pair_cannot_be_frozen_as_live_prediction(tmp_path):
    b=scenario(tmp_path)
    with pytest.raises(ValueError,match="stale|later|window|freeze"):
        freeze(b,clock=FREEZE+timedelta(days=6))
    assert not b[3].exists()


def test_single_weak_advantage_cannot_be_upgraded_into_frozen_rotation(tmp_path):
    b=scenario(tmp_path,second_advantage=40)
    with pytest.raises(ValueError,match="eligible|corroborat"):
        freeze(b)
    assert not b[3].exists()


@pytest.mark.parametrize("horizon", [0,False,1096])
def test_invalid_pinned_horizon_never_publishes_pair(tmp_path,horizon):
    b=scenario(tmp_path)
    with pytest.raises(ValueError,match="horizon"):
        freeze(b,horizon=horizon)
    assert not b[3].exists()


def test_hindsight_freeze_clock_cannot_precede_score_research(tmp_path):
    b=scenario(tmp_path)
    with pytest.raises(ValueError,match="eligible|corroborat|not|freeze"):
        freeze(b,clock=ROOT+timedelta(days=2))
    assert not b[3].exists()


def test_registered_pair_can_be_censored_until_evaluation_horizon_elapsed(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    result=audit(b,cutoff=FREEZE+timedelta(days=4))
    assert result["frozen_pair_count"]==1
    assert result["full_horizon_elapsed_pair_count"]==0
    assert result["internally_evaluable_pair_count"]==0
    assert result["unknown_or_censored_pair_count"]==1
    assert result["research_pair_confirmed_count"]==0
    assert result["pair_evidence_sample"][0]["status"]=="HORIZON_PENDING"
    assert result["independent_future_label_source_certified"] is False


def test_elapsed_horizon_without_labels_does_not_count_as_failed_pair(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    result=audit(b)
    assert result["full_horizon_elapsed_pair_count"]==1
    assert result["internally_evaluable_pair_count"]==0
    assert result["unknown_or_censored_pair_count"]==1
    assert result["pair_evidence_sample"][0]["status"]=="HORIZON_ELAPSED_NO_COMPLETE_LABELS"
    assert result["research_pair_nonconfirmation_count"]==0
    assert result["research_known_pair_confirmation_fraction"] is None
    assert result["research_pair_confirmation_floor"] is None
    assert result["independent_future_label_source_certified"] is False


def test_two_matured_available_self_declared_labels_correlate_but_not_certify(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    evidence=labels_path(tmp_path)
    result=audit(b,labels=evidence)
    assert result["status"]==AUDIT_STATUS
    assert result["frozen_pair_count"]==1
    assert result["internally_evaluable_pair_count"]==1
    assert result["research_pair_confirmed_count"]==1
    assert result["research_pair_nonconfirmation_count"]==0
    assert result["unknown_or_censored_pair_count"]==0
    assert result["research_known_pair_confirmation_fraction"]==1.
    assert result["research_pair_confirmation_floor"]==1.
    assert result["pair_evidence_sample"][0]["status"]=="RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED"
    assert result["historic_pit_certified"] is False
    assert result["real_leader_replacement_certified"] is False
    assert result["official_leader_replacements"]==0


def test_mature_negative_contender_is_research_nonconfirmation_only(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    result=audit(b,labels=labels_path(tmp_path,contender=False))
    assert result["research_pair_nonconfirmation_count"]==1
    assert result["research_pair_confirmed_count"]==0
    assert result["research_known_pair_confirmation_fraction"]==0.
    assert result["official_leader_replacements"]==0


def test_existing_incumbent_future_leader_claim_cannot_be_called_successful_replacement(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    result=audit(b,labels=labels_path(tmp_path,incumbent=True))
    assert result["research_pair_nonconfirmation_count"]==1
    assert result["research_pair_confirmed_count"]==0


def test_premature_negative_label_is_censored_not_false_rotation(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    file=labels_path(tmp_path,negative_mature="2026-10-09T10:19:00+09:00")
    result=audit(b,labels=file)
    assert result["internally_evaluable_pair_count"]==0
    assert result["research_pair_nonconfirmation_count"]==0
    assert result["pair_evidence_sample"][0]["status"]=="PREMATURE_NEGATIVE_LABEL"


def test_missing_incumbent_or_contender_stays_unknown_without_fabricated_failure(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path)
    values=json.loads(path.read_text())
    path.write_text(json.dumps(values[:1]))
    result=audit(b,labels=path)
    assert result["internally_evaluable_pair_count"]==0
    assert result["unknown_or_censored_pair_count"]==1
    assert result["pair_evidence_sample"][0]["status"]=="HORIZON_ELAPSED_NO_COMPLETE_LABELS"


def test_label_first_available_after_eval_cannot_be_known_at_cutoff(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path,published_at="2026-10-12T11:00:00+09:00")
    result=audit(b,labels=path)
    assert result["internally_evaluable_pair_count"]==0
    assert result["pair_evidence_sample"][0]["status"]=="LABEL_NOT_YET_AVAILABLE"


def test_successful_label_declared_onset_before_freeze_is_not_forward_success(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path,positive_onset="2026-10-03T13:00:00+09:00")
    result=audit(b,labels=path)
    assert result["internally_evaluable_pair_count"]==0
    assert result["pair_evidence_sample"][0]["status"]=="PREEXISTING_OR_UNRELIABLE_POSITIVE_ONSET"


def test_unmatched_extra_labels_do_not_improve_denominator_or_precision(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path)
    values=json.loads(path.read_text())
    values.append(label_record("OTHER",True))
    path.write_text(json.dumps(values))
    report=audit(b,labels=path)
    assert report["frozen_pair_count"]==1
    assert report["internally_evaluable_pair_count"]==1
    assert report["unmatched_outcome_label_count"]==1
    assert report["research_pair_confirmed_count"]==1


def test_swapped_company_identity_and_duplicate_labels_rejected(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path)
    values=json.loads(path.read_text())
    values.append(deepcopy(values[0]))
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError,match="Duplicate"):
        audit(b,labels=path)


def test_mutated_holdout_contents_with_original_hash_are_rejected(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    data=json.loads(b[3].read_text())
    data["pairs"][0]["contender_security_id"]="WRONG"
    b[3].write_text(json.dumps(data))
    with pytest.raises(ValueError,match="hash"):
        audit(b)


def test_rehashed_altered_pair_id_or_fake_certification_is_rejected(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    data=json.loads(b[3].read_text())
    data["pairs"][0]["pair_id"]="0"*64
    data.pop("content_sha256")
    data["content_sha256"]=_digest(data)
    b[3].write_text(json.dumps(data))
    with pytest.raises(ValueError,match="pair.*id|identity"):
        audit(b)


def test_label_definition_cannot_change_after_freeze(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    path=labels_path(tmp_path)
    rows=json.loads(path.read_text())
    rows[0]["label_definition_id"]="retrospectively_optimized"
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="definition"):
        audit(b,labels=path)


def test_future_cutoff_and_symlinked_holdout_blocked(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    link=tmp_path/"alias.json"
    link.symlink_to(b[3])
    with pytest.raises(ValueError,match="symlink"):
        audit_rotation_pair_outcomes(link,evaluated_at=AFTER.isoformat(),clock=AFTER)
    with pytest.raises(ValueError,match="Future"):
        audit_rotation_pair_outcomes(b[3],evaluated_at="2030-01-01T00:00:00Z",clock=AFTER)


def test_label_outcome_file_symlink_not_followed(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    real=labels_path(tmp_path)
    link=tmp_path/"alias_labels.json"
    link.symlink_to(real)
    with pytest.raises(ValueError,match="symlink"):
        audit(b,labels=link)


def test_extra_rehashed_future_label_inside_sealed_manifest_rejected(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    original=json.loads(b[3].read_text())
    original["is_future_leader"]=True
    original.pop("content_sha256")
    original["content_sha256"]=_digest(original)
    b[3].write_text(json.dumps(original))
    with pytest.raises(ValueError,match="schema|field|label|research"):
        audit(b)


def test_rehashed_fake_seal_certification_cannot_be_used_as_true_leader(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    raw=json.loads(b[3].read_text())
    raw["real_leader_replacement_certified"]=True
    raw.pop("content_sha256")
    raw["content_sha256"]=_digest(raw)
    b[3].write_text(json.dumps(raw))
    with pytest.raises(ValueError,match="research|protocol|certif"):
        audit(b)


def test_exact_kr_horizon_minute_before_does_not_issue_false_failure(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    result=audit(b,cutoff=FREEZE+timedelta(days=5,minutes=-1))
    assert result["horizon_pending_pair_count"]==1
    assert result["research_pair_nonconfirmation_count"]==0
    result=audit(b,cutoff=FREEZE+timedelta(days=5))
    assert result["horizon_pending_pair_count"]==0
    assert result["pair_evidence_sample"][0]["status"]=="HORIZON_ELAPSED_NO_COMPLETE_LABELS"


def test_preexisting_outcome_available_before_pair_seal_rejected(tmp_path):
    b=scenario(tmp_path)
    freeze(b)
    file=labels_path(tmp_path)
    rows=json.loads(file.read_text())
    rows[0]["outcome_available_at"]=(FREEZE-timedelta(minutes=1)).isoformat()
    file.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match="predates freeze|maturity"):
        audit(b,labels=file)


def test_cli_later_pair_audit_and_safe_derived_only_sha_backup(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    b=scenario(tmp_path)
    freeze(b)
    labels=labels_path(tmp_path)
    before=(sha256(b[0].read_bytes()).hexdigest(),
            sha256(b[1].read_bytes()).hexdigest(),
            sha256(b[3].read_bytes()).hexdigest())
    target=tmp_path/"derived"
    main(["audit-rotation-pair-outcomes","--freeze-file",str(b[3]),
          "--evaluated-at",AFTER.isoformat(),"--outcomes",str(labels),
          "--out",str(target)])
    output=json.loads(capsys.readouterr().out)
    assert output["internally_evaluable_pair_count"]==1
    assert output["research_pair_confirmed_count"]==1
    assert output["official_leader_replacements"]==0
    report=json.loads((target/"rotation_pair_outcomes_research.json").read_text())
    assert "is_future_leader" not in json.dumps(report)
    after=(sha256(b[0].read_bytes()).hexdigest(),
           sha256(b[1].read_bytes()).hexdigest(),
           sha256(b[3].read_bytes()).hexdigest())
    assert before==after
    archive=tmp_path/"derived_only.zip"
    info=create_backup(target,archive)
    assert info["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert z.namelist()==["rotation_pair_outcomes_research.json","MANIFEST.json"]
    restore_backup(archive,tmp_path/"restored")
    assert (tmp_path/"restored"/"rotation_pair_outcomes_research.json").read_bytes()==(
        target/"rotation_pair_outcomes_research.json").read_bytes()


def test_cli_cannot_rename_old_scores_as_present_prospective_freeze(tmp_path):
    from eraleader.cli import main
    b=scenario(tmp_path)
    with pytest.raises(SystemExit) as err:
        main(["freeze-rotation-pairs","--watch-ledger",str(b[0]),
              "--score-history",str(b[1]),"--feature-root",str(b[2]),
              "--market","KR","--model-version",MODEL,
              "--label-definition-id",LABEL_ID,"--horizon-days","5",
              "--freeze-file",str(b[3])])
    assert err.value.code==2
    assert not b[3].exists()


def test_us_dst_crossing_exact_local_horizon_clock(tmp_path):
    from eraleader.prospective import ProspectiveRegistry
    from eraleader.peer_score_series import record_peer_score_series
    from test_peer_score_series import screen,doc
    folder=tmp_path/"us_features"
    folder.mkdir()
    ledger=tmp_path/"us_prospective.sqlite"
    score_db=tmp_path/"us_peer_scores.sqlite"
    holder=tmp_path/"us_rotation_holdout.json"
    reg=ProspectiveRegistry(ledger)
    try:
        for day,clock in [(0,"2026-02-25T16:00:00-05:00"),
                          (1,"2026-02-26T16:00:00-05:00")]:
            at=datetime.fromisoformat(clock)
            screen(reg,day,"US-INC",True,market="US",moment=at)
        for day,clock in [(2,"2026-03-05T16:00:00-05:00"),
                          (3,"2026-03-06T16:00:00-05:00")]:
            at=datetime.fromisoformat(clock)
            screen(reg,day,"US-INC",False,market="US",moment=at)
            screen(reg,day,"US-NEW",True,market="US",moment=at+timedelta(minutes=5))
            doc(folder,day,"US-INC",40 if day==2 else 35,
                at+timedelta(minutes=9),market="US")
            doc(folder,day,"US-NEW",75 if day==2 else 80,
                at+timedelta(minutes=9),market="US")
            record_peer_score_series(score_db,ledger,folder,market="US",
                                     model_version=MODEL,clock=at+timedelta(minutes=10))
    finally:
        reg.close()
    freeze_time=datetime.fromisoformat("2026-03-06T16:20:00-05:00")
    ret=freeze_rotation_pairs(ledger,score_db,folder,holder,market="US",
          model_version=MODEL,label_definition_id=LABEL_ID,
          horizon_days=10,clock=freeze_time)
    assert ret["eligible_pairs"]==1
    at_before=datetime.fromisoformat("2026-03-16T16:19:00-04:00")
    at_due=datetime.fromisoformat("2026-03-16T16:20:00-04:00")
    actual=datetime(2026,4,1,tzinfo=timezone.utc)
    pending=audit_rotation_pair_outcomes(holder,evaluated_at=at_before.isoformat(),clock=actual)
    assert pending["horizon_pending_pair_count"]==1
    due=audit_rotation_pair_outcomes(holder,evaluated_at=at_due.isoformat(),clock=actual)
    assert due["full_horizon_elapsed_pair_count"]==1
    assert due["internally_evaluable_pair_count"]==0
    assert due["pair_evidence_sample"][0]["horizon_end_utc"]==at_due.astimezone(timezone.utc).isoformat()


def test_current_cli_freeze_cannot_backdate_and_does_not_read_any_future_labels(tmp_path,capsys):
    """Only the FREEZE command uses OS wall-clock, with freshly injected fixtures.

    A synthetic test clock is used when creating WATCH/scores; this is NOT a
    claim that real contemporary financial sources were observed today.
    """
    from zoneinfo import ZoneInfo
    from eraleader.cli import main
    from eraleader.prospective import ProspectiveRegistry
    from eraleader.peer_score_series import record_peer_score_series
    from test_peer_score_series import screen, doc
    now = datetime.now(timezone.utc)
    zone = ZoneInfo("Asia/Seoul")
    local = now.astimezone(zone)
    local_score = local.replace(hour=9,minute=30,second=0,microsecond=0)
    if local.hour < 10:
        local_score -= timedelta(days=1)
    latest = local_score.astimezone(timezone.utc)
    previous = latest-timedelta(days=1)
    watch=tmp_path/"fresh_watch.sqlite"
    scores=tmp_path/"fresh_scores.sqlite"
    root=tmp_path/"recent_features"
    root.mkdir()
    reg=ProspectiveRegistry(watch)
    try:
        for day in (-4,-3):
            screen(reg,day,"CURRENT-INC",True,moment=latest+timedelta(days=day))
        for day,stamp in enumerate((previous,latest)):
            _,at=screen(reg,day,"CURRENT-INC",False,moment=stamp)
            screen(reg,day,"CURRENT-NEW",True,moment=stamp+timedelta(minutes=5))
            doc(root,day,"CURRENT-INC",40 if day==0 else 38,
                stamp+timedelta(minutes=9))
            doc(root,day,"CURRENT-NEW",65 if day==0 else 72,
                stamp+timedelta(minutes=9))
            record_peer_score_series(scores,watch,root,market="KR",
                model_version=MODEL,clock=stamp+timedelta(minutes=10))
    finally:
        reg.close()
    holder=tmp_path/"current_rotation_pair_holdout.json"
    main(["freeze-rotation-pairs",
          "--watch-ledger",str(watch),"--score-history",str(scores),
          "--feature-root",str(root),"--market","KR","--model-version",MODEL,
          "--label-definition-id",LABEL_ID,"--horizon-days","5",
          "--freeze-file",str(holder)])
    summary=json.loads(capsys.readouterr().out)
    assert summary["eligible_pairs"]==1
    obj=_read_rotation_freeze(holder)
    assert obj["outcome_labels_included"] is False
    assert obj["official_leader_replacements"]==0
    assert "leader_start_at" not in json.dumps(obj)
    # No future label exists, so evaluation must remain pending.
    target=tmp_path/"derived"
    main(["audit-rotation-pair-outcomes","--freeze-file",str(holder),
          "--evaluated-at",datetime.now(timezone.utc).isoformat(),
          "--out",str(target)])
    capsys.readouterr()
    audited=json.loads((target/"rotation_pair_outcomes_research.json").read_text())
    assert audited["horizon_pending_pair_count"]==1
    assert audited["research_pair_confirmed_count"]==0
    assert audited["official_leader_replacements"]==0
