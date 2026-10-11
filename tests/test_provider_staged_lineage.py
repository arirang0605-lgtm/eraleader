"""2_2/2_5 offline staged source-to-ingest lineage (synthetic, never official PIT)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import copy
import json
import sqlite3

import pytest

from eraleader.provider_staged_lineage import audit_staged_source_lineage
from eraleader.provider_export_normalizer import normalize_provider_export
from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.cli import main
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_provider_export_normalizer import (
    NOW, stage_fixture, rows_for, revise_stream,
)

AUDIT = NOW + timedelta(minutes=8)
BEFORE = (NOW + timedelta(minutes=3)).isoformat()
OLD = (NOW - timedelta(minutes=3)).isoformat()


def scenario(tmp_path, market="KR", *, ingest=True, ingest_clock=NOW):
    raw = stage_fixture(tmp_path, market)
    normalized = tmp_path / "normalized"
    normalize_provider_export(raw, normalized, clock=NOW)
    db = tmp_path / "provider.sqlite"
    imported = None
    if ingest:
        imported = import_provider_bundle(
            normalized / "manifest.json", db, clock=ingest_clock)
    return raw, normalized / "manifest.json", db, imported


def audit(bundle, *, ledger=True, cutoff=BEFORE, clock=AUDIT):
    raw, normalized, db, _ = bundle
    return audit_staged_source_lineage(
        raw, normalized, decision_at=cutoff,
        ledger_file=db if ledger else None, clock=clock,
    )


@pytest.mark.parametrize("market,expected_id", [
    ("KR", "KR:CORP00001234:ISSUE:ISSUE_A"),
    ("US", "US:CIK0000012345:CLASS:CLASS_A"),
])
def test_raw_document_sha_normalized_bytes_and_first_ingest_agree(
        tmp_path, market, expected_id):
    b = scenario(tmp_path, market)
    tracked = [b[0], *b[0].parent.glob("*.jsonl"),
               b[1], *b[1].parent.glob("*.jsonl"), b[2]]
    before = {str(p):sha256(p.read_bytes()).hexdigest() for p in tracked}
    r = audit(b)
    assert r["status"] == "LOCAL_STAGED_TO_FIRST_INGEST_LINEAGE_MATCHED_NOT_CERTIFIED"
    assert r["market"] == market
    assert r["normalized_record_count"] == 4
    assert r["raw_document_receipt_count"] == 4
    assert r["distinct_claimed_source_documents"] == 1
    assert r["source_and_normalized_bytes_matched"] is True
    assert r["locally_registered_before_decision"] is True
    assert r["usable_as_local_research_source_at_decision"] is True
    assert r["independent_publisher_authenticated"] is False
    assert r["official_issuer_or_share_class_certified"] is False
    assert r["external_pit_certified"] is False
    assert r["official_leader_promotions"] == 0
    assert expected_id not in json.dumps(r)
    assert {str(p):sha256(p.read_bytes()).hexdigest() for p in tracked} == before


def test_missing_ingest_receipt_is_not_historic_pit_qualification(tmp_path):
    b = scenario(tmp_path, ingest=False)
    r = audit(b, ledger=False)
    assert r["status"] == "LOCAL_STAGED_BYTES_MATCHED_NOT_FIRST_INGESTED"
    assert r["source_and_normalized_bytes_matched"] is True
    assert r["locally_registered_before_decision"] is False
    assert r["usable_as_local_research_source_at_decision"] is False


def test_late_first_import_is_censored_not_misrepresented_as_old_pit(tmp_path):
    b = scenario(tmp_path, ingest_clock=NOW + timedelta(minutes=5))
    r = audit(b)
    assert r["status"] == "CENSORED_STAGED_INGEST_AFTER_DECISION"
    assert r["source_and_normalized_bytes_matched"] is True
    assert r["locally_registered_before_decision"] is False
    assert r["usable_as_local_research_source_at_decision"] is False


def test_old_decision_before_claimed_retrieval_censors(tmp_path):
    b = scenario(tmp_path)
    r = audit(b, cutoff=OLD)
    assert r["status"] == "CENSORED_STAGED_INGEST_AFTER_DECISION"
    assert r["usable_as_local_research_source_at_decision"] is False


def test_missing_receipt_db_cannot_fake_success(tmp_path):
    b = scenario(tmp_path)
    b[2].unlink()
    with pytest.raises((ValueError,FileNotFoundError,sqlite3.OperationalError)):
        audit(b)


def test_raw_source_changed_after_normalization_without_rehash_rejected(tmp_path):
    b = scenario(tmp_path)
    revise_stream(b[0], "actions", lambda a: a[0].update(ratio=3), rehash=False)
    with pytest.raises(ValueError, match="SHA|digest"):
        audit(b)


def test_raw_source_changed_with_self_rehashed_manifest_still_rejected(tmp_path):
    b = scenario(tmp_path)
    revise_stream(b[0], "actions", lambda a: a[0].update(ratio=3))
    with pytest.raises(ValueError, match="source|normalized|lineage|match|byte"):
        audit(b)


def test_claimed_source_document_swapped_after_normalization_still_rejected(tmp_path):
    b = scenario(tmp_path)
    revise_stream(b[0], "membership",
                  lambda a: a[0].update(source_document_id="DIFFERENT_DOC"))
    with pytest.raises(ValueError, match="witness|lineage|source|match|byte"):
        audit(b)


def test_raw_identity_rewritten_and_fully_rehashed_cannot_remap_share_class(tmp_path):
    b = scenario(tmp_path, market="US")
    revise_stream(b[0], "membership",
                  lambda a: a[0].update(share_class_uid="CLASS_B"))
    with pytest.raises(ValueError, match="witness|lineage|normalized|match|byte"):
        audit(b)


def test_normalized_stream_bytes_rewritten_and_manifest_rehashed_rejected(tmp_path):
    b = scenario(tmp_path)
    p=b[1].parent/"actions.jsonl"
    entries=[json.loads(x) for x in p.read_text().splitlines()]
    entries[0]["ratio"]=4.0
    raw=b"".join((json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
                 for x in entries)
    p.write_bytes(raw)
    manifest=json.loads(b[1].read_text())
    for entry in manifest["streams"]:
        if entry["kind"]=="actions":
            entry["sha256"]=sha256(raw).hexdigest()
    b[1].write_text(json.dumps(manifest,sort_keys=True))
    with pytest.raises(ValueError, match="normalized|source|byte|lineage"):
        audit(b)


def test_normalized_manifest_profile_retarget_even_if_content_same_rejected(tmp_path):
    b = scenario(tmp_path)
    manifest=json.loads(b[1].read_text())
    manifest["publisher_id_claimed"]="FAKE_PROVIDER_CHANGED"
    b[1].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest|source|identity|matched"):
        audit(b)


def test_source_witness_bytes_rehashed_and_document_claim_changed_rejected(tmp_path):
    b = scenario(tmp_path)
    w=b[1].parent/"normalization_witnesses.jsonl"
    entries=[json.loads(x) for x in w.read_text().splitlines()]
    entries[0]["source_document_id_claimed"]="FORGED_DOC"
    w.write_text("\n".join(json.dumps(row,sort_keys=True) for row in entries)+"\n")
    with pytest.raises(ValueError, match="witness"):
        audit(b)


def test_missing_lineage_witness_is_not_silent_success(tmp_path):
    b = scenario(tmp_path)
    (b[1].parent/"normalization_witnesses.jsonl").unlink()
    with pytest.raises(ValueError, match="witness"):
        audit(b)


@pytest.mark.parametrize("name", ["membership.jsonl", "normalization_witnesses.jsonl",
                                   "manifest.json"])
def test_symlinked_normalized_source_or_witness_rejected(tmp_path,name):
    b = scenario(tmp_path)
    p=b[1].parent/name
    backup=b[1].parent/("saved_"+name)
    p.rename(backup)
    p.symlink_to(backup)
    with pytest.raises(ValueError, match="symlink|unsafe|linked"):
        audit(b)


def test_mixed_source_and_normalized_stages_rejected(tmp_path):
    b = scenario(tmp_path)
    other = tmp_path/"other"
    other.mkdir()
    f2 = stage_fixture(other, market="US")
    n2 = other/"normalized"
    normalize_provider_export(f2,n2,clock=NOW)
    with pytest.raises(ValueError, match="market|manifest|source|mismatch"):
        audit_staged_source_lineage(
            b[0],n2/"manifest.json",decision_at=BEFORE,clock=AUDIT)


def test_future_decision_cutoff_rejected(tmp_path):
    b=scenario(tmp_path)
    with pytest.raises(ValueError,match="Future|future"):
        audit(b, cutoff=(AUDIT+timedelta(seconds=1)).isoformat())


def test_missing_or_changed_original_receipt_rejected_not_reimported(tmp_path):
    b = scenario(tmp_path)
    with sqlite3.connect(b[2]) as db:
        db.execute("UPDATE provider_ingest_receipts SET source_id='SWAPPED'")
    with pytest.raises(ValueError,match="source|receipt|identity|mismatch"):
        audit(b)


def test_preflight_raw_revised_mid_audit_rejected(tmp_path,monkeypatch):
    import eraleader.provider_staged_lineage as module
    b=scenario(tmp_path)
    real=module.audit_registered_provider_asof
    def changed_on_receipt(*args,**kwargs):
        ret=real(*args,**kwargs)
        revise_stream(b[0],"fundamentals",lambda rows:rows[0].update(value=999.0))
        return ret
    monkeypatch.setattr(module,"audit_registered_provider_asof",changed_on_receipt)
    with pytest.raises(ValueError,match="source|revised|lineage|normalized|match|byte"):
        audit(b)


def test_cli_no_network_derived_only_backup_restore(tmp_path,capsys):
    b = scenario(tmp_path)
    derived=tmp_path/"derived"
    main(["audit-provider-staged-lineage",
          "--staged-manifest",str(b[0]),
          "--normalized-manifest",str(b[1]),
          "--ledger",str(b[2]),
          "--decision-at",BEFORE,"--out",str(derived)])
    payload=json.loads(capsys.readouterr().out)
    assert payload["source_and_normalized_bytes_matched"] is True
    assert payload["usable_as_local_research_source_at_decision"] is True
    assert payload["official_leader_promotions"]==0
    summary=derived/"provider_staged_lineage_research.json"
    assert summary.exists()
    assert "corp_code" not in summary.read_text()
    zip_path=tmp_path/"derived_only.zip"
    backup=create_backup(derived,zip_path)
    assert backup["file_count"]==1
    assert verify_backup(zip_path)["status"]=="LOCAL_BACKUP_VERIFIED"
    target=tmp_path/"restored"
    restore_backup(zip_path,target)
    assert (target/summary.name).read_bytes()==summary.read_bytes()


def test_us_multiclass_original_id_and_revised_financial_rows_are_separate(tmp_path):
    rows=rows_for("US")
    cls=copy.deepcopy(rows["membership"][0])
    cls["share_class_uid"]="CLASS_B"
    cls["ticker"]="EXA.B"
    rows["membership"].append(cls)
    fact=copy.deepcopy(rows["fundamentals"][0])
    fact["revision"]=2
    fact["published_at"]="2025-03-10T12:00:00+09:00"
    fact["value"]=444.0
    rows["fundamentals"].append(fact)
    raw=stage_fixture(tmp_path,market="US",rows=rows)
    norm=tmp_path/"normalized"
    normalize_provider_export(raw,norm,clock=NOW)
    db=tmp_path/"provider.sqlite"
    import_provider_bundle(norm/"manifest.json",db,clock=NOW)
    r=audit_staged_source_lineage(raw,norm/"manifest.json",
                                 ledger_file=db,decision_at=BEFORE,clock=AUDIT)
    assert r["normalized_record_count"]==6
    assert r["normalized_by_kind"]["membership"]==2
    assert r["normalized_by_kind"]["fundamentals"]==2
    assert r["usable_as_local_research_source_at_decision"] is True
    assert r["official_issuer_or_share_class_certified"] is False


def test_rehashed_raw_order_change_cannot_reorder_historical_receipts(tmp_path):
    rows=rows_for("US")
    cls=copy.deepcopy(rows["membership"][0])
    cls["share_class_uid"]="CLASS_B"
    cls["ticker"]="EXA.B"
    rows["membership"].append(cls)
    raw=stage_fixture(tmp_path,market="US",rows=rows)
    norm=tmp_path/"normalized"
    normalize_provider_export(raw,norm,clock=NOW)
    db=tmp_path/"provider.sqlite"
    import_provider_bundle(norm/"manifest.json",db,clock=NOW)
    revise_stream(raw,"membership",lambda r:r.reverse())
    with pytest.raises(ValueError,match="normalized|witness|source|byte"):
        audit_staged_source_lineage(raw,norm/"manifest.json",
                                   ledger_file=db,decision_at=BEFORE,clock=AUDIT)


def test_original_doc_id_is_not_first_ingest_attested_if_claim_and_witness_both_rewritten(tmp_path):
    b=scenario(tmp_path)
    assert audit(b)["original_doc_id_hash_attested_at_first_ingest"] is False
    original_normalized_hash=sha256(b[1].read_bytes()).hexdigest()
    revise_stream(b[0],"membership",
                  lambda rows:rows[0].update(source_document_id="REPLACED_SELF_DECLARED_DOC"))
    regenerated=tmp_path/"later_regenerated"
    normalize_provider_export(b[0],regenerated,clock=NOW)
    assert sha256((regenerated/"manifest.json").read_bytes()).hexdigest()==original_normalized_hash
    # The existing provider ingestion receipt stored only the normalized
    # bundle digest. It never stored the raw document IDs, so a changed raw
    # doc claim + regenerated witness MUST NOT be called independently pinned.
    (b[1].parent/"normalization_witnesses.jsonl").write_bytes(
        (regenerated/"normalization_witnesses.jsonl").read_bytes())
    r=audit(b)
    assert r["original_doc_id_to_normalized_digest_linked_locally"] is True
    assert r["original_doc_id_hash_attested_at_first_ingest"] is False
    assert r["independent_source_document_verified"] is False
