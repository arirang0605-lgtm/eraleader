"""2_2/2_5 raw staged-document first-ingest pin: synthetic fixtures only.

The local SHA pin and OS time are NOT independent publisher notarization.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.provider_export_normalizer import normalize_provider_export
from eraleader.provider_staged_lineage import audit_staged_source_lineage
from eraleader.cli import main
from test_provider_export_normalizer import NOW, stage_fixture, revise_stream

AFTER=(NOW+timedelta(minutes=8)).isoformat()
BEFORE=(NOW-timedelta(minutes=1)).isoformat()


def create(tmp_path,market="KR"):
    stage=stage_fixture(tmp_path,market=market)
    normalized=tmp_path/"normalized"
    normalize_provider_export(stage,normalized,clock=NOW)
    return stage, normalized/"manifest.json", tmp_path/"received.sqlite"


def incoming(paths, clock=NOW, staged=True):
    source,normalized,db=paths
    return import_provider_bundle(
        normalized,db,clock=clock,
        staged_manifest=source if staged else None,
    )


def check(paths, cutoff=AFTER, required=True, clock=NOW+timedelta(minutes=10)):
    stage,normalized,db=paths
    return audit_staged_source_lineage(
        stage,normalized,ledger_file=db,
        decision_at=cutoff,
        require_original_first_ingest_pin=required,
        clock=clock,
    )


def rows(path):
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT original_payload,original_payload_sha256 "
            "FROM provider_staged_original_receipts"
        ).fetchall()


@pytest.mark.parametrize("market",["KR","US"])
def test_atomically_first_pin_raw_document_claim_and_witness_at_ingest(tmp_path,market):
    paths=create(tmp_path,market)
    watched=[paths[0], *paths[0].parent.glob("*.jsonl"),paths[1],
             *paths[1].parent.glob("*.jsonl")]
    preserved={p:sha256(p.read_bytes()).hexdigest() for p in watched}
    result=incoming(paths)
    audit=check(paths)
    assert result["original_staged_receipt_first_pinned"] is True
    assert result["original_staged_receipt_independently_attested"] is False
    assert audit["status"]=="LOCAL_STAGED_TO_FIRST_INGEST_LINEAGE_MATCHED_NOT_CERTIFIED"
    assert audit["first_ingest_raw_and_witness_pin_present"] is True
    assert audit["original_doc_id_hash_attested_at_first_ingest"] is True
    assert audit["original_doc_id_first_ingest_pin_locally_only"] is True
    assert audit["independent_source_document_verified"] is False
    assert audit["locally_registered_before_decision"] is True
    assert audit["external_pit_certified"] is False
    assert audit["official_leader_promotions"]==0
    assert len(rows(paths[2]))==1
    payload_str,payload_hash=rows(paths[2])[0]
    assert sha256(payload_str.encode()).hexdigest()==payload_hash
    payload=json.loads(payload_str)
    assert payload["first_registered_at_utc"]==NOW.isoformat()
    assert payload["normalized_bundle_manifest_sha256"]==result["bundle_sha256"]
    assert payload["original_staged_manifest_sha256"]==sha256(paths[0].read_bytes()).hexdigest()
    assert {p:sha256(p.read_bytes()).hexdigest() for p in watched}==preserved


def test_original_document_id_and_witness_rehashed_after_first_pin_rejected(tmp_path):
    p=create(tmp_path)
    incoming(p)
    revise_stream(p[0],"membership",
                  lambda rec:rec[0].update(source_document_id="NEW_UNTRUSTED_DOC"))
    rebuilt=tmp_path/"rebuilt"
    normalize_provider_export(p[0],rebuilt,clock=NOW)
    # Normalized financial/issuer data and its imported manifest remain identical.
    assert (rebuilt/"manifest.json").read_bytes()==p[1].read_bytes()
    (p[1].parent/"normalization_witnesses.jsonl").write_bytes(
        (rebuilt/"normalization_witnesses.jsonl").read_bytes())
    with pytest.raises(ValueError,match="first|original|pin|witness"):
        check(p)


def test_strict_audit_requires_pinned_ingest_not_legacy_unlinked_claim(tmp_path):
    p=create(tmp_path)
    plain=incoming(p,staged=False)
    assert plain["rows_inserted"]==4
    unstrict=check(p,required=False)
    assert unstrict["original_doc_id_hash_attested_at_first_ingest"] is False
    assert unstrict["first_ingest_raw_and_witness_pin_present"] is False
    with pytest.raises(ValueError,match="original|first|pin"):
        check(p,required=True)


def test_no_retroactive_upgrade_of_preexisting_normalized_bundle(tmp_path):
    p=create(tmp_path)
    incoming(p,staged=False)
    with pytest.raises(ValueError,match="retroactive|first|already"):
        incoming(p,staged=True)
    with sqlite3.connect(p[2]) as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='provider_staged_original_receipts'"
        ).fetchone() or not db.execute(
            "SELECT count(*) FROM provider_staged_original_receipts"
        ).fetchone()[0]


def test_identical_replay_keeps_first_raw_hash_and_local_clock(tmp_path):
    p=create(tmp_path)
    original=incoming(p)
    second=incoming(p,clock=NOW+timedelta(minutes=4))
    assert second["rows_inserted"]==0
    assert second["first_registered_at_utc"]==original["first_registered_at_utc"]
    assert second["original_staged_receipt_first_pinned"] is False
    assert second["original_staged_receipt_present"] is True
    assert len(rows(p[2]))==1
    assert json.loads(rows(p[2])[0][0])["first_registered_at_utc"]==NOW.isoformat()


def test_replayed_raw_claim_rewrites_without_witness_not_silently_accepted(tmp_path):
    p=create(tmp_path)
    incoming(p)
    revise_stream(p[0],"actions",lambda rec:rec[0].update(source_document_id="NEW_DOC"))
    with pytest.raises(ValueError,match="witness|original|source"):
        incoming(p)


def test_late_first_import_is_censored_not_backdated(tmp_path):
    p=create(tmp_path)
    incoming(p)
    r=check(p,cutoff=BEFORE)
    assert r["status"]=="CENSORED_STAGED_INGEST_AFTER_DECISION"
    assert r["locally_registered_before_decision"] is False
    assert r["original_doc_id_hash_attested_at_first_ingest"] is True
    assert r["usable_as_local_research_source_at_decision"] is False


def test_distinct_source_origin_claims_cannot_be_borrowed_from_another_ingest(tmp_path):
    p=create(tmp_path)
    incoming(p)
    other=create(tmp_path/"other",market="US")
    incoming(other)
    with pytest.raises(ValueError,match="original|manifest|receipt|source"):
        audit_staged_source_lineage(
            other[0],other[1],ledger_file=p[2],decision_at=AFTER,
            require_original_first_ingest_pin=True,
            clock=NOW+timedelta(minutes=10),
        )


def test_corrupted_pin_hash_stops_audit(tmp_path):
    p=create(tmp_path)
    incoming(p)
    with sqlite3.connect(p[2]) as db:
        db.execute("UPDATE provider_staged_original_receipts "
                   "SET original_payload_sha256=?",("0"*64,))
    with pytest.raises(ValueError,match="first|original|pin|digest"):
        check(p)


def test_rehashed_pin_different_raw_sha_stops_audit(tmp_path):
    p=create(tmp_path)
    incoming(p)
    payload=json.loads(rows(p[2])[0][0])
    payload["original_staged_manifest_sha256"]="0"*64
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,
                   separators=(",",":"))
    with sqlite3.connect(p[2]) as db:
        db.execute("UPDATE provider_staged_original_receipts "
                   "SET original_payload=?,original_payload_sha256=?",
                   (raw,sha256(raw.encode()).hexdigest()))
    with pytest.raises(ValueError,match="first|original|pin|hash"):
        check(p)


def test_sqlite_orphan_first_pin_cannot_be_a_valid_normalized_bundle(tmp_path):
    p=create(tmp_path)
    incoming(p)
    with sqlite3.connect(p[2]) as db:
        db.execute("DELETE FROM provider_ingest_receipts")
    with pytest.raises(ValueError):
        check(p)


def test_atomic_rollback_on_stage_source_change_during_import(tmp_path,monkeypatch):
    p=create(tmp_path)
    import eraleader.provider_staged_lineage as module
    original=module._one_pass
    calls=[0]
    def mutate(*args,**kwargs):
        calls[0]+=1
        result=original(*args,**kwargs)
        if calls[0]==1:
            revise_stream(p[0],"fundamentals",lambda rec:rec[0].update(value=999))
        return result
    monkeypatch.setattr(module,"_one_pass",mutate)
    with pytest.raises(ValueError,match="changed|revised|witness|source|normalized"):
        incoming(p)
    if p[2].exists():
        with sqlite3.connect(p[2]) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='provider_ingest_receipts'").fetchone():
                assert db.execute("SELECT count(*) FROM provider_ingest_receipts").fetchone()[0]==0
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='provider_staged_original_receipts'").fetchone():
                assert db.execute("SELECT count(*) FROM provider_staged_original_receipts").fetchone()[0]==0


def test_new_raw_ingest_option_requires_staged_normalizer_manifest(tmp_path):
    p=create(tmp_path)
    wrong=tmp_path/"wrong.json"
    wrong.write_text('{"not":"staged"}')
    with pytest.raises(ValueError):
        import_provider_bundle(p[1],p[2],clock=NOW,staged_manifest=wrong)


def test_corrupt_or_symlink_staged_manifest_blocks_new_first_pin(tmp_path):
    p=create(tmp_path)
    alias=tmp_path/"stage_alias.json"
    alias.symlink_to(p[0])
    with pytest.raises(ValueError,match="symlink|unsafe"):
        import_provider_bundle(p[1],p[2],clock=NOW,staged_manifest=alias)
    assert not p[2].exists()


def test_cli_optin_staged_import_and_strict_audit_timestamp(tmp_path,capsys):
    from datetime import datetime, timezone
    clock=datetime.now(timezone.utc)
    # synthetic staged claimed retrieved timestamp must not be in the future
    p=create(tmp_path)
    # The fixture's old claimed retrieval is fine for a current-time CLI.
    root=tmp_path/"derived"
    main(["import-provider-pit","--manifest",str(p[1]),
          "--staged-manifest",str(p[0]),"--ledger",str(p[2]),
          "--out",str(root)])
    read=json.loads(capsys.readouterr().out)
    assert read["original_staged_receipt_present"] is True
    main(["audit-provider-staged-lineage","--staged-manifest",str(p[0]),
          "--normalized-manifest",str(p[1]),"--ledger",str(p[2]),
          "--decision-at",datetime.now(timezone.utc).isoformat(),
          "--require-original-first-ingest-pin","--out",str(root)])
    result=json.loads(capsys.readouterr().out)
    assert result["first_ingest_raw_and_witness_pin_present"] is True
    assert result["original_doc_id_hash_attested_at_first_ingest"] is True
    assert result["official_leader_promotions"]==0
    assert clock<=datetime.fromisoformat(read["first_registered_at_utc"])<=datetime.now(timezone.utc)


def test_source_pin_never_independently_certifies_official_pit(tmp_path):
    p=create(tmp_path)
    incoming(p)
    row=check(p)
    assert row["independent_source_document_verified"] is False
    assert row["official_issuer_or_share_class_certified"] is False
    assert row["original_source_available_at_independently_attested"] is False
    assert row["external_pit_certified"] is False
    assert row["official_leader_promotions"]==0


def test_deleting_first_pin_cannot_silently_downgrade_to_legacy_mode(tmp_path):
    p=create(tmp_path)
    incoming(p)
    with sqlite3.connect(p[2]) as db:
        db.execute("DELETE FROM provider_staged_original_receipts")
    with pytest.raises(ValueError,match="pin|original|missing|marker"):
        check(p,required=False)
    with pytest.raises(ValueError,match="pin|original|missing|marker"):
        incoming(p,staged=False)


def test_first_ingest_pin_anchor_digest_mutation_rejected(tmp_path):
    p=create(tmp_path)
    incoming(p)
    with sqlite3.connect(p[2]) as db:
        db.execute("UPDATE provider_ingest_receipts "
                   "SET original_staged_pin_sha256=?",("0"*64,))
    with pytest.raises(ValueError,match="pin|original|digest|marker"):
        check(p)
    with pytest.raises(ValueError,match="pin|original|digest|marker"):
        incoming(p,staged=True)


def test_legacy_mode_may_reimport_identical_without_accidental_raw_pin(tmp_path):
    p=create(tmp_path)
    one=incoming(p,staged=False)
    two=incoming(p,staged=False,clock=NOW+timedelta(minutes=5))
    assert one["rows_inserted"]==4 and two["rows_inserted"]==0
    assert two["original_staged_receipt_present"] is False
    assert check(p,required=False)["original_doc_id_hash_attested_at_first_ingest"] is False
