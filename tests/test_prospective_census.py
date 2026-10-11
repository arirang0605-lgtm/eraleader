"""5_5 first-write, all-cohort denominators; synthetic source evidence only."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader.prospective_census import register_census, audit_all_registered_censuses, _hash
from test_ranked_outcome_receipts import scenario, NOW, FROZEN, CUTOFF


def prepare(folder,market="KR",retrospective=False):
    frozen, outcome, receipt = scenario(folder,market=market,retrospective=retrospective)
    copy={str(outcome):outcome.read_bytes(),str(receipt):receipt.read_bytes()}
    outcome.unlink()
    receipt.unlink()
    spec=frozen.parent/"census_input.json"
    spec.write_text(json.dumps([{
        "frozen":frozen.name,"definition":"leader_rule.json",
        "outcomes":outcome.name,"receipts":receipt.name,
    }]))
    return spec,copy,frozen,outcome,receipt


def register(spec,root,name="census_one.json",clock=FROZEN+timedelta(minutes=5)):
    return register_census(spec,root,name,clock=clock)


def restore(saved):
    for name,content in saved.items():
        Path(name).write_bytes(content)


def evaluate(root,at=CUTOFF):
    return audit_all_registered_censuses(root,evaluated_at=at,clock=NOW)


def test_first_write_censors_entire_topk_until_future_outcomes(tmp_path):
    spec,_,freeze,_,_=prepare(tmp_path)
    reg=tmp_path/"census-registry"
    result=register(spec,reg)
    assert result["registered_cohorts"]==1 and result["selected_denominator"]==3
    batch=evaluate(reg)
    assert batch["frozen_selected_denominator"]==3
    assert batch["unknown_or_censored"]==3
    assert batch["locally_documented_early_hits"]==0
    assert batch["precision_on_documented_known"] is None
    assert batch["real_precision_at_k"] is None
    assert batch["full_frozen_k_precision_floor"]==0
    assert batch["full_frozen_k_precision_ceiling"]==1
    assert batch["cohort_status_counts"]=={"HORIZON_ELAPSED_SOURCE_UNKNOWN":1}
    assert batch["official_leader_promotions"]==0


def test_late_local_source_receipts_never_shrink_frozen_denominator(tmp_path):
    spec,saved,*_=prepare(tmp_path)
    reg=tmp_path/"reg"
    register(spec,reg)
    restore(saved)
    result=evaluate(reg)
    assert result["locally_documented_early_hits"]==1
    assert result["locally_documented_known_failures"]==1
    assert result["unknown_or_censored"]==1
    assert result["frozen_selected_denominator"]==3
    assert result["precision_on_documented_known"]==0.5
    assert result["full_frozen_k_precision_floor"]==round(1/3,6)
    assert result["full_frozen_k_precision_ceiling"]==round(2/3,6)
    assert result["real_future_leader_accuracy_certified"] is False


def test_multi_census_includes_unreported_cohort_not_only_successes(tmp_path):
    root=tmp_path/"reg"
    first,saved,*_=prepare(tmp_path/"kr")
    second,_,*_=prepare(tmp_path/"us",market="US")
    register(first,root,"census_KR.json")
    register(second,root,"census_US.json")
    restore(saved)
    result=evaluate(root)
    assert result["registered_cohort_count"]==2
    assert result["registry_manifest_count"]==2
    assert result["registered_market_cohort_counts"]=={"KR":1,"US":1}
    assert result["frozen_selected_denominator"]==6
    assert result["locally_documented_early_hits"]==1
    assert result["locally_documented_known_failures"]==1
    assert result["unknown_or_censored"]==4
    assert result["full_frozen_k_precision_floor"]==round(1/6,6)
    assert result["full_frozen_k_precision_ceiling"]==round(5/6,6)


def test_partial_late_source_pair_is_unknown_not_failure(tmp_path):
    spec,saved,_,outcome,_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    outcome.write_bytes(saved[str(outcome)])
    result=evaluate(root)
    assert result["unknown_or_censored"]==3
    assert result["cohort_status_counts"]=={"PARTIAL_SOURCE_EVIDENCE":1}


def test_pre_maturity_absence_is_not_failure(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    result=audit_all_registered_censuses(root,evaluated_at="2026-01-02T00:00:00+00:00",clock=NOW)
    assert result["unknown_or_censored"]==3
    assert result["cohort_status_counts"]=={"HORIZON_PENDING_SOURCE_UNKNOWN":1}


def test_late_registration_accepted_nothing(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    with pytest.raises(ValueError,match="Late|future"):
        register(spec,root,clock=FROZEN+timedelta(hours=2))
    assert not root.exists() or not list(root.glob("*.json"))


def test_existing_future_outcome_cannot_be_first_write_census(tmp_path):
    spec,saved,_,outcome,_=prepare(tmp_path)
    outcome.write_bytes(saved[str(outcome)])
    with pytest.raises(ValueError,match="must not exist"):
        register(spec,tmp_path/"reg")


def test_retro_frozen_rank_cannot_be_rebranded_prospective(tmp_path):
    spec,_,*_=prepare(tmp_path,retrospective=True)
    with pytest.raises(ValueError,match="prospective"):
        register(spec,tmp_path/"reg",clock=NOW+timedelta(minutes=5))


def test_duplicate_first_write_same_name_does_not_overwrite(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    file=root/"census_one.json"
    original=file.read_bytes()
    with pytest.raises(FileExistsError):
        register(spec,root)
    assert file.read_bytes()==original


def test_change_original_freeze_bytes_detected_even_if_contents_rehashed(tmp_path):
    spec,_,frozen,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    data=json.loads(frozen.read_text())
    data["model_version"]="changed_after_seal"
    frozen.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="SHA|mismatch|changed"):
        evaluate(root)


def test_registry_digest_protects_against_shrinkage(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    sealed=root/"census_one.json"
    record=json.loads(sealed.read_text())
    record["cohorts"]=[]
    sealed.write_text(json.dumps(record))
    with pytest.raises(ValueError,match="seal"):
        evaluate(root)


def test_rehashed_registry_cannot_understate_pinned_topk(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    sealed=root/"census_one.json"
    record=json.loads(sealed.read_text())
    record["cohorts"][0]["top_k_selected_count"]=1
    record["content_sha256"]=_hash({k:v for k,v in record.items() if k!="content_sha256"})
    sealed.write_text(json.dumps(record))
    with pytest.raises(ValueError,match="no longer matches"):
        evaluate(root)


def test_label_rule_bytes_changed_after_registration(tmp_path):
    spec,_,frozen,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    rule=frozen.parent/"leader_rule.json"
    rule.write_bytes(rule.read_bytes()+b" ")
    with pytest.raises(ValueError,match="label definition"):
        evaluate(root)


def test_duplicate_cohort_across_registry_cannot_be_double_counted(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root,"census_a.json")
    register(spec,root,"census_b.json")
    with pytest.raises(ValueError,match="Duplicate cohort"):
        evaluate(root)


def test_forged_future_evaluation_rejected(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    with pytest.raises(ValueError,match="Future"):
        audit_all_registered_censuses(root,evaluated_at="2027-01-01T00:00:00+00:00",clock=NOW)


@pytest.mark.parametrize("badname",["../bad.json","census_a/b.json","census_\\bad.json",".json","other.json"])
def test_unsafe_registry_filename_blocked(tmp_path,badname):
    spec,_,*_=prepare(tmp_path)
    with pytest.raises(ValueError,match="safe|census_"):
        register(spec,tmp_path/"reg",name=badname)


def test_full_manifest_source_claim_modification_halts_audit(tmp_path):
    spec,saved,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    restore(saved)
    receipt=Path(next(k for k in saved if k.endswith("outcome_source_receipts.json")))
    body=json.loads(receipt.read_text())
    body["outcomes_sha256"]="0"*64
    receipt.write_text(json.dumps(body))
    with pytest.raises(ValueError,match="SHA|mismatch"):
        evaluate(root)


def test_registry_read_only_audit_and_cli_writes_only_derived_result(tmp_path):
    spec,_,*_=prepare(tmp_path)
    root=tmp_path/"reg"
    register(spec,root)
    data_before=(root/"census_one.json").read_bytes()
    script=Path(__file__).resolve().parents[1]/"scripts"/"run_prospective_census.py"
    dest=tmp_path/"derived"
    done=subprocess.run([sys.executable,str(script),"audit","--registry-dir",str(root),
                         "--evaluated-at",CUTOFF,"--out",str(dest)],
                        capture_output=True,text=True,check=False)
    assert done.returncode==0,done.stderr
    payload=json.loads(done.stdout)
    assert payload["frozen_selected_denominator"]==3
    assert json.loads((dest/"prospective_census_research.json").read_text())==payload
    assert (root/"census_one.json").read_bytes()==data_before


def test_unrecognized_registry_name_cannot_hide_bad_cohort(tmp_path):
    first,_,*_=prepare(tmp_path/"kr")
    second,_,*_=prepare(tmp_path/"us",market="US")
    root=tmp_path/"reg"
    register(first,root,"census_KR.json")
    register(second,root,"census_US.json")
    (root/"census_US.json").rename(root/"hidden.json")
    with pytest.raises(ValueError,match="Unrecognized|unsupported|hidden"):
        evaluate(root)


def test_sanitized_census_json_only_backup_restore(tmp_path):
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    spec,_,*_=prepare(tmp_path/"data")
    registry=tmp_path/"registry"
    register(spec,registry)
    out=tmp_path/"derived"
    out.mkdir()
    payload=evaluate(registry)
    derived=out/"prospective_census_research.json"
    derived.write_text(json.dumps(payload,sort_keys=True))
    archive=tmp_path/"backups"/"local_only.zip"
    create_backup(out,archive)
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert set(z.namelist())=={"MANIFEST.json","prospective_census_research.json"}
    dest=tmp_path/"new_restore"
    restore_backup(archive,dest)
    assert (dest/derived.name).read_bytes()==derived.read_bytes()
