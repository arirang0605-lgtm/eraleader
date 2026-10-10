"""Calendar readiness of frozen prospective cohorts; labels NEVER loaded."""
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import json
import pytest

from eraleader.frozen_holdout import (
    freeze_registered_candidates, _read_frozen, _digest,
)
from eraleader.holdout_maturity import audit_holdout_maturity
from eraleader.prospective import ProspectiveRegistry
from eraleader.cli import main
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_frozen_holdout import freeze, run, LABEL, VERSION

NOW=datetime(2026,11,1,tzinfo=timezone.utc)
APRIL="2026-04-15T17:00:00+09:00"
OCT="2026-10-10T17:00:00+09:00"

def readiness(tmp_path,at=OCT,limit=20):
    freeze(tmp_path)
    return audit_holdout_maturity(tmp_path/"holdout_manifest.json",
                                  as_of=at,sample_limit=limit,clock=NOW)


def test_april_cohort_pending_and_october_cohort_elapsed(tmp_path):
    early=readiness(tmp_path,APRIL)
    assert early["eligible_frozen_candidates"]==4
    assert early["horizon_pending_count"]==4
    assert early["horizon_elapsed_count"]==0
    assert all(x["days_until_horizon_end"]>0
               for x in early["maturity_schedule_sample"])
    later=audit_holdout_maturity(tmp_path/"holdout_manifest.json",
                                as_of=OCT,clock=NOW)
    assert later["eligible_frozen_candidates"]==4
    assert later["horizon_elapsed_count"]==4
    assert later["horizon_pending_count"]==0
    assert all(x["full_horizon_elapsed"] for x in later["maturity_schedule_sample"])
    assert all(x["outcome_source_independently_verified"] is False
               for x in later["maturity_schedule_sample"])
    assert later["actual_known_outcomes"]==0
    assert later["positive_leader_labels_inferred"]==0
    assert later["negative_leader_labels_inferred"]==0
    assert later["official_leader_promotions"]==0
    assert later["historic_pit_certified"] is False


def test_horizon_maturity_exact_market_local_day(tmp_path):
    early=readiness(tmp_path,"2026-09-28T17:00:00+09:00")
    assert early["horizon_pending_count"]==4
    assert all(x["days_until_horizon_end"]==1 for x in early["maturity_schedule_sample"])
    midnight=audit_holdout_maturity(tmp_path/"holdout_manifest.json",
         as_of="2026-09-29T00:00:00+09:00",clock=NOW)
    assert midnight["horizon_pending_count"]==4
    assert all(x["horizon_end_market_day"]=="2026-09-29"
               for x in midnight["maturity_schedule_sample"])
    due=audit_holdout_maturity(tmp_path/"holdout_manifest.json",
         as_of="2026-09-29T17:00:00+09:00",clock=NOW)
    assert due["horizon_elapsed_count"]==4


def test_partial_cohort_due_counts_use_registration_not_backdated_observation(tmp_path):
    path=tmp_path/"prospective.sqlite"
    p=ProspectiveRegistry(path)
    try:
        p.record_integrated(run(["A"],as_of="2026-04-02T11:00:00+09:00"),
                            clock=datetime(2026,4,2,8,tzinfo=timezone.utc))
        p.record_integrated(run(["B"],as_of="2026-04-09T11:00:00+09:00"),
                            clock=datetime(2026,4,9,8,tzinfo=timezone.utc))
    finally:p.close()
    target=tmp_path/"holdout_manifest.json"
    freeze_registered_candidates(path,target,market="KR",model_version=VERSION,
             label_definition_id=LABEL,clock=datetime(2026,4,10,tzinfo=timezone.utc))
    report=audit_holdout_maturity(target,
             as_of="2026-09-30T17:00:00+09:00",clock=NOW)
    assert report["horizon_elapsed_count"]==1
    assert report["horizon_pending_count"]==1
    assert [x["security_id"] for x in report["maturity_schedule_sample"]]==["A","B"]
    assert [x["days_until_horizon_end"] for x in report["maturity_schedule_sample"]]==[0,6]


def test_missing_label_file_is_not_loaded_or_assumed_negative(tmp_path):
    report=readiness(tmp_path)
    assert report["external_outcome_evidence_verified"] is False
    assert report["actual_known_outcomes"]==0
    assert report["maturity_sample_limit"]==20


def test_market_us_timezone_and_dst_market_day(tmp_path):
    p=ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        p.record_integrated(run(["US-A"],market="US",
            as_of="2026-03-06T15:00:00-05:00"),
            clock=datetime(2026,3,6,21,tzinfo=timezone.utc))
    finally:p.close()
    sealed=tmp_path/"us_holdout.json"
    freeze_registered_candidates(tmp_path/"prospective.sqlite",sealed,
         market="US",model_version=VERSION,label_definition_id=LABEL,
         horizon_days=10,clock=datetime(2026,3,7,tzinfo=timezone.utc))
    early=audit_holdout_maturity(sealed,
        as_of="2026-03-15T23:30:00+09:00",
        clock=datetime(2026,4,20,tzinfo=timezone.utc))
    assert early["market_as_of_day"]=="2026-03-15"
    assert early["horizon_pending_count"]==1
    not_yet=audit_holdout_maturity(sealed,
        as_of="2026-03-16T01:00:00-04:00",
        clock=datetime(2026,4,20,tzinfo=timezone.utc))
    assert not_yet["horizon_pending_count"]==1
    matured=audit_holdout_maturity(sealed,
        as_of="2026-03-16T16:00:00-04:00",
        clock=datetime(2026,4,20,tzinfo=timezone.utc))
    assert matured["horizon_elapsed_count"]==1
    assert matured["maturity_schedule_sample"][0]["horizon_end_market_day"]=="2026-03-16"


@pytest.mark.parametrize("asof,err",[
    ("2026-04-01T17:00:00+09:00","before holdout freeze"),
    ("2026-11-02T17:00:00+09:00","Future as-of"),
    ("2026-10-10T17:00:00","Timezone-aware"),
])
def test_invalid_clock_or_pre_freeze_rejected(tmp_path,asof,err):
    freeze(tmp_path)
    with pytest.raises(ValueError,match=err):
        audit_holdout_maturity(tmp_path/"holdout_manifest.json",
                              as_of=asof,clock=NOW)


def test_tampered_or_symlinked_freeze_rejected(tmp_path):
    freeze(tmp_path)
    p=tmp_path/"holdout_manifest.json"
    content=json.loads(p.read_text())
    content["eligible_count"]=999
    p.write_text(json.dumps(content))
    with pytest.raises(ValueError,match="hash mismatch"):
        audit_holdout_maturity(p,as_of=OCT,clock=NOW)
    p.unlink()
    safe=tmp_path/"outside.json"
    safe.write_text("{}")
    p.symlink_to(safe)
    with pytest.raises(ValueError,match="symlinked"):
        audit_holdout_maturity(p,as_of=OCT,clock=NOW)


def test_rehashed_duplicate_candidate_fails_closed(tmp_path):
    freeze(tmp_path)
    p=tmp_path/"holdout_manifest.json"
    data=json.loads(p.read_text())
    data["signals"].append(dict(data["signals"][0]))
    data["eligible_count"]+=1
    data.pop("content_sha256")
    data["content_sha256"]=_digest(data)
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="Duplicate"):
        audit_holdout_maturity(p,as_of=OCT,clock=NOW)


def test_cli_and_safe_backup_only_derived_maturity_report(tmp_path,capsys):
    freeze(tmp_path)
    out=tmp_path/"derived"
    main(["audit-holdout-maturity",
          "--freeze-file",str(tmp_path/"holdout_manifest.json"),
          "--as-of","2026-10-09T17:00:00+09:00","--out",str(out)])
    output=json.loads(capsys.readouterr().out)
    assert output["horizon_elapsed_count"]==4
    assert output["actual_known_outcomes"]==0
    assert output["official_leader_promotions"]==0
    body=json.loads(Path(output["path"]).read_text())
    assert body["frozen_manifest_sha256"]==_read_frozen(
        tmp_path/"holdout_manifest.json")["content_sha256"]
    (out/"private_future_labels.json").write_text('{"secret":"NEVER_BACKUP"}')
    archive=tmp_path/"maturity_report.zip"
    assert create_backup(out,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipped:
        assert zipped.namelist()==["holdout_maturity_research.json","MANIFEST.json"]
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert json.loads((restored/"holdout_maturity_research.json").read_text())==body
    assert not (restored/"private_future_labels.json").exists()

def test_same_market_day_one_minute_before_horizon_remains_pending(tmp_path):
    early = readiness(tmp_path, "2026-09-29T16:59:00+09:00")
    assert early["horizon_elapsed_count"] == 0
    assert early["horizon_pending_count"] == 4
    assert all(x["full_horizon_elapsed"] is False
               for x in early["maturity_schedule_sample"])
    due = audit_holdout_maturity(tmp_path/"holdout_manifest.json",
        as_of="2026-09-29T17:00:00+09:00", clock=NOW)
    assert due["horizon_elapsed_count"] == 4
    assert all(x["full_horizon_elapsed"] is True
               for x in due["maturity_schedule_sample"])


@pytest.mark.parametrize("cutoff,expected", [
    ("2026-03-16T15:59:00-04:00", False),
    ("2026-03-16T16:00:00-04:00", True),
])
def test_us_dst_maturity_needs_exact_exchange_local_clock(tmp_path, cutoff, expected):
    reg = ProspectiveRegistry(tmp_path/"prospective.sqlite")
    try:
        reg.record_integrated(run(["US-X"], market="US",
            as_of="2026-03-06T15:00:00-05:00"),
            clock=datetime(2026, 3, 6, 21, tzinfo=timezone.utc))
    finally:
        reg.close()
    target = tmp_path/"holdout.json"
    freeze_registered_candidates(tmp_path/"prospective.sqlite", target,
        market="US", model_version=VERSION, label_definition_id=LABEL,
        horizon_days=10, clock=datetime(2026, 3, 7, tzinfo=timezone.utc))
    out = audit_holdout_maturity(target, as_of=cutoff,
        clock=datetime(2026, 4, 20, tzinfo=timezone.utc))
    assert out["horizon_elapsed_count"] == int(expected)
    assert out["maturity_schedule_sample"][0]["full_horizon_elapsed"] is expected
