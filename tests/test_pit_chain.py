"""Synthetic market PIT -> sealed cohort -> dated outcome receipt chain.

No test asserts an actual early-leader hit rate or official source provenance.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import pytest

from eraleader.cli import main
from eraleader.evidence_gate import REPORTS
from eraleader.pit_chain import audit_pit_to_outcome_chain
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_evidence_gate import valid_reports,write_bundle
from test_outcome_source_claims import make_bundle

DECISION="2026-04-02T16:00:00+09:00"
EVALUATED="2026-10-10T17:00:00+09:00"
NOW=datetime(2026,11,1,tzinfo=timezone.utc)


def setup(tmp_path,*,day="2026-04-02",market="KR"):
    root=tmp_path/"labels"
    frozen, outcomes, receipts=make_bundle(root)
    reports=valid_reports(market)
    source=f"{day}T07:00:00+00:00"
    reports["source_vintage"]["decision_at"]=source
    reports["issuer_lineage"]["decision_at"]=source
    for key in ("exchange_calendar","price_continuity","membership_price"):
        field={"exchange_calendar":"cutoff","price_continuity":"as_of_requested",
               "membership_price":"requested_as_of"}[key]
        reports[key][field]=day
    (tmp_path/"audits").mkdir()
    report_dir=write_bundle(tmp_path/"audits",reports,market)
    return frozen,outcomes,receipts,report_dir


def audit(paths,*,market="KR",decision=DECISION,evaluated=EVALUATED,labels=True,clock=NOW):
    frozen,outcomes,receipts,reports=paths
    return audit_pit_to_outcome_chain(
        market=market,decision_at=decision,evaluated_at=evaluated,
        report_dir=reports,frozen_file=frozen,
        outcome_file=outcomes if labels else None,
        receipt_manifest=receipts if labels else None,clock=clock)


def test_full_local_reports_do_not_override_missing_matured_label_or_certify(tmp_path):
    r=audit(setup(tmp_path))
    assert r["source_report_domains_present"]==5
    assert r["local_market_domain_diagnostics_complete"] is True
    assert r["frozen_candidate_count"]==4
    assert r["internally_evaluable_research_labels"]==3
    assert r["local_consistent_outcome_source_claims"]==3
    assert r["unresolved_candidate_count"]==1
    assert "outcomes:UNRESOLVED_OR_UNMATURED_HOLDOUT_CANDIDATES" in r["blockers"]
    assert r["official_leader_promotions"]==0
    assert r["leader_prediction_accuracy_certified"] is False
    assert r["historic_universe_pit_certified"] is False
    assert len(r["frozen_manifest_sha256"])==64


def test_missing_outcomes_is_blocker_not_failure_label(tmp_path):
    r=audit(setup(tmp_path),labels=False)
    assert r["internally_evaluable_research_labels"]==0
    assert r["unresolved_candidate_count"]==4
    assert r["source_claim_manifest_sha256"] is None
    assert "outcomes:SOURCE_LABEL_RECEIPTS_NOT_PROVIDED" in r["blockers"]
    assert r["official_leader_promotions"]==0


def test_missing_pit_reports_concrete_blockers(tmp_path):
    paths=setup(tmp_path)
    for f in paths[3].iterdir():
        f.unlink()
    r=audit(paths,labels=False)
    assert r["source_report_domains_present"]==0
    assert r["blocker_count"]>=7
    assert any(x=="source:issuer_lineage:REPORT_MISSING" for x in r["blockers"])


def test_source_decision_after_candidate_registration_is_caught(tmp_path):
    paths=setup(tmp_path,day="2026-04-03")
    r=audit(paths,decision="2026-04-03T16:00:00+09:00")
    assert "cross_stage:SOURCE_CUTOFF_AFTER_CANDIDATE_REGISTRATION" in r["blockers"]
    assert r["research_chain_locally_coherent"] is False


def test_one_issuer_collision_blocks_even_with_otherwise_valid_outcome_claims(tmp_path):
    paths=setup(tmp_path)
    audit_file=paths[3]/REPORTS["issuer_lineage"].format(market="kr")
    content=json.loads(audit_file.read_text())
    content["active_ticker_conflict_count"]=1
    audit_file.write_text(json.dumps(content))
    r=audit(paths)
    assert any("ACTIVE_TICKER_CONFLICT_COUNT" in c for c in r["blockers"])
    assert r["official_leader_promotions"]==0


def test_modified_source_document_blocks_the_entire_chain(tmp_path):
    paths=setup(tmp_path)
    (tmp_path/"labels"/"A.json").write_text('{"modified":1}')
    r=audit(paths)
    assert "outcomes:A:SOURCE_BYTES_SHA256_MISMATCH" in r["blockers"]
    assert "outcomes:MISSING_OR_INCONSISTENT_EVALUABLE_SOURCE_EVIDENCE" in r["blockers"]
    assert r["local_consistent_outcome_source_claims"]==2


def test_mismatched_market_is_rejected_before_linking(tmp_path):
    paths=setup(tmp_path)
    with pytest.raises(ValueError,match="market differs"):
        audit(paths,market="US")


@pytest.mark.parametrize("mode",["missing_receipt","missing_labels"])
def test_half_provided_outcome_inputs_are_rejected(tmp_path,mode):
    frozen,labels,receipts,report_dir=setup(tmp_path)
    kw={"outcome_file":labels,"receipt_manifest":None} if mode=="missing_receipt" else {
        "outcome_file":None,"receipt_manifest":receipts}
    with pytest.raises(ValueError,match="supplied together"):
        audit_pit_to_outcome_chain(
            market="KR",decision_at=DECISION,evaluated_at=EVALUATED,
            report_dir=report_dir,frozen_file=frozen,clock=NOW,**kw)


def test_source_cutoff_after_freeze_rejected(tmp_path):
    paths=setup(tmp_path)
    with pytest.raises(ValueError,match="postdates sealed freeze"):
        audit(paths,decision="2026-05-01T12:00:00+09:00")


def test_entire_research_chain_consistent_still_uncertified(tmp_path):
    paths=setup(tmp_path)
    frozen,outcomes,receipts,_=paths
    # Extend as-of to a future *synthetic* evaluation clock, after D's
    # declared 2027 maturity/availability. Supply a separate D document.
    contents=json.loads(receipts.read_text())
    new_doc=json.dumps({"fictional_source":"D","kind":"synthetic"}).encode()
    (receipts.parent/"D.json").write_bytes(new_doc)
    contents["claims"].append({
        "security_id":"D","publisher_id_claimed":"SYNTHETIC",
        "source_id":"TEST_D","file":"D.json",
        "sha256":sha256(new_doc).hexdigest(),
        "published_at":"2027-01-02T10:00:00+09:00",
        "retrieved_at":"2027-01-03T10:00:00+09:00"})
    receipts.write_text(json.dumps(contents))
    r=audit(paths,evaluated="2027-02-10T17:00:00+09:00",
            clock=datetime(2027,2,11,tzinfo=timezone.utc))
    assert r["blocker_count"]==0
    assert r["research_chain_locally_coherent"] is True
    assert r["status"]=="LOCAL_PIT_TO_OUTCOME_CHAIN_COHERENT_NOT_CERTIFIED"
    assert r["internally_evaluable_research_labels"]==4
    assert r["local_consistent_outcome_source_claims"]==4
    assert r["publisher_independently_authenticated"] is False
    assert r["source_availability_independently_attested"] is False
    assert r["leader_prediction_accuracy_certified"] is False


def test_cli_with_missing_labels_and_safe_derived_backup(tmp_path,capsys):
    frozen,_,_,report_dir=setup(tmp_path)
    target=tmp_path/"derived"
    main(["audit-pit-chain","--market","KR","--decision-at",DECISION,
          "--evaluated-at",EVALUATED,"--report-dir",str(report_dir),
          "--freeze-file",str(frozen),"--out",str(target)])
    result=json.loads(capsys.readouterr().out)
    assert result["frozen_candidate_count"]==4
    assert result["official_leader_promotions"]==0
    content=json.loads(Path(result["path"]).read_text())
    assert content["blocker_count"]>0
    (target/"raw_vendor_data.json").write_text('{"api_key":"NEVER_COPY"}')
    archive=tmp_path/"derived.zip"
    assert create_backup(target,archive)["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as z:
        assert z.namelist()==["pit_chain_kr_research.json","MANIFEST.json"]
    restore=tmp_path/"restored"
    restore_backup(archive,restore)
    assert json.loads((restore/"pit_chain_kr_research.json").read_text())==content
    assert not (restore/"raw_vendor_data.json").exists()
