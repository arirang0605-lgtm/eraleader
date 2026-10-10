"""Synthetic local cash-payment byte-evidence contracts, not official payments."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from eraleader.cash_exit_lineage import (
    audit_dual_vintage_cash_exit, STATUS_BLOCKED, STATUS_MATCH,
)
from eraleader.cash_payment_receipts import (
    audit_declared_cash_payment_receipt, RECEIPT_SCHEMA, DOCUMENT_SCHEMA,
)
from test_cash_exit_lineage import prepare, bundle, SEC, SIGNAL, EVALUATED


def inputs(tmp_path, *, market="KR"):
    scenario, files = prepare(tmp_path / "original", bundle(market=market))
    terms = scenario["price"]["settlement"]
    source = "DECLARED_SEPARATE_PAYMENT_REGISTRY"
    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "source_id": source,
        "market": scenario["identity"]["market"],
        "security_id": terms["security_id"],
        "event_id": terms["event_id"],
        "action_type": "cash_delist",
        "last_trading_on": terms["last_trading_on"],
        "effective_on": terms["effective_on"],
        "cash_per_share": terms["cash_per_share"],
        "currency": terms["currency"],
        "paid_at": terms["paid_at"],
        "cash_payment_confirmed": True,
    }
    folder = tmp_path / "receipt"
    folder.mkdir()
    doc_path = folder / "payment.json"
    raw = json.dumps(document, sort_keys=True).encode()
    doc_path.write_bytes(raw)
    if market == "KR":
        published, retrieved = ("2024-04-16T10:00:00+09:00",
                                "2024-04-17T09:00:00+09:00")
    else:
        published, retrieved = ("2024-03-21T12:00:00-04:00",
                                "2024-03-22T12:00:00-04:00")
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "market": scenario["identity"]["market"],
        "security_id": terms["security_id"],
        "source_id_claimed": source,
        "publisher_id_claimed": "SELF_DECLARED_NOT_VERIFIED",
        "file": "payment.json", "sha256": sha256(raw).hexdigest(),
        "published_at": published, "retrieved_at": retrieved,
    }
    manifest_path = folder / "receipt_manifest.json"
    manifest_path.write_text(json.dumps(receipt), encoding="utf-8")
    return scenario, files, manifest_path, doc_path


def run(scenario, files, manifest=None, *, required=False):
    return audit_dual_vintage_cash_exit(
        *files, market=scenario["identity"]["market"],
        security_id=scenario["price"]["settlement"]["security_id"],
        decision_at=scenario["decision"], evaluated_at=scenario["evaluation"],
        settlement_receipt_file=manifest,
        require_settlement_receipt=required,
    )


@pytest.mark.parametrize("market,expected", [("KR", .1), ("US", .05)])
def test_distinct_claimed_payout_file_matches_without_any_pit_certification(tmp_path,market,expected):
    scenario, files, manifest, _ = inputs(tmp_path,market=market)
    result=run(scenario,files,manifest,required=True)
    assert result["status"] == STATUS_MATCH
    assert result["cash_exit_total_return"] == expected
    assert result["settlement_receipt_supplied"] is True
    assert result["settlement_receipt_claims_consistent"] is True
    assert len(result["settlement_receipt_manifest_sha256"]) == 64
    assert result["settlement_receipt_independently_authenticated"] is False
    assert result["cash_payment_independently_verified"] is False


def test_absent_receipt_only_censors_when_explicitly_required(tmp_path):
    scenario, files, _, _ = inputs(tmp_path)
    research=run(scenario,files)
    strict=run(scenario,files,required=True)
    assert research["cash_exit_total_return"] == .1
    assert strict["status"] == STATUS_BLOCKED
    assert strict["cash_exit_total_return"] is None
    assert "CASH_PAYMENT_RECEIPT_NOT_PROVIDED" in strict["blocking_reasons"]


@pytest.mark.parametrize("field,value,reason", [
    ("security_id","WRONG-PERMANENT-ID","PAYMENT_DOCUMENT_SECURITY_ID_MISMATCH"),
    ("event_id","DIFFERENT-EVENT","PAYMENT_DOCUMENT_EVENT_ID_MISMATCH"),
    ("cash_per_share",54,"PAYMENT_DOCUMENT_CASH_AMOUNT_MISMATCH"),
    ("cash_per_share",True,"PAYMENT_DOCUMENT_CASH_AMOUNT_MISMATCH"),
    ("currency","USD","PAYMENT_DOCUMENT_CURRENCY_MISMATCH"),
    ("paid_at","2024-04-15T11:00:00+09:00","PAYMENT_DOCUMENT_PAID_AT_MISMATCH"),
    ("cash_payment_confirmed",False,"PAYMENT_DOCUMENT_UNCONFIRMED_PAYMENT"),
    ("last_trading_on","2024-04-02","PAYMENT_DOCUMENT_LAST_TRADING_ON_MISMATCH"),
])
def test_rehashed_but_conflicting_document_does_not_validate_exit(tmp_path,field,value,reason):
    scenario, files, manifest, doc = inputs(tmp_path)
    content = json.loads(doc.read_text())
    content[field] = value
    raw = json.dumps(content,sort_keys=True).encode()
    doc.write_bytes(raw)
    receipt = json.loads(manifest.read_text())
    receipt["sha256"] = sha256(raw).hexdigest()
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert result["status"] == STATUS_BLOCKED
    assert result["cash_exit_total_return"] is None
    assert reason in result["blocking_reasons"]


def test_valid_previous_hash_detects_changed_document_bytes(tmp_path):
    scenario, files, manifest, doc = inputs(tmp_path)
    doc.write_text(doc.read_text()+" ")
    result=run(scenario,files,manifest)
    assert "PAYMENT_DOCUMENT_SHA256_MISMATCH" in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None


@pytest.mark.parametrize("field,value,reason", [
    ("published_at","2024-04-15T09:59:00+09:00","RECEIPT_PUBLISHED_BEFORE_CLAIMED_PAYMENT"),
    ("retrieved_at","2024-06-01T10:00:00+09:00","RECEIPT_UNAVAILABLE_BY_EVALUATION"),
    ("retrieved_at","2024-04-16T09:00:00+09:00","RECEIPT_RETRIEVED_BEFORE_PUBLICATION"),
    ("source_id_claimed","SYN-ISSUER-VINTAGE","RECEIPT_NOT_A_DISTINCT_DECLARED_SOURCE"),
])
def test_local_claim_chronology_or_declared_source_conflict_is_censored(tmp_path,field,value,reason):
    scenario, files, manifest, _ = inputs(tmp_path)
    receipt = json.loads(manifest.read_text())
    receipt[field] = value
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert result["status"] == STATUS_BLOCKED
    assert reason in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None


@pytest.mark.parametrize("unsafe_name",["../payment.json","/tmp/payment.json",".private.json"])
def test_unsafe_relative_receipt_paths_are_rejected(tmp_path,unsafe_name):
    scenario, files, manifest, _ = inputs(tmp_path)
    receipt = json.loads(manifest.read_text())
    receipt["file"] = unsafe_name
    manifest.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match="Unsafe"):
        run(scenario,files,manifest)


def test_receipt_document_symlink_and_duplicate_json_fields_fail_closed(tmp_path):
    scenario, files, manifest, doc = inputs(tmp_path)
    other = doc.parent / "original_document.json"
    doc.rename(other)
    doc.symlink_to(other)
    with pytest.raises(ValueError,match="symlinked|Unsafe"):
        run(scenario,files,manifest)
    doc.unlink()
    doc.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(ValueError,match="Duplicate field"):
        run(scenario,files,manifest)


def test_existing_eraleader_cli_censors_unavailable_receipt_without_raw_data_copy(
        tmp_path,capsys):
    from eraleader.cli import main
    scenario, files, manifest, _ = inputs(tmp_path)
    a, b, c = files
    args=["audit-cash-delist","--file",str(a),
          "--decision-lineage",str(b),"--evaluation-lineage",str(c),
          "--settlement-receipt",str(manifest),
          "--require-settlement-receipt",
          "--security-id",SEC,"--market","KR",
          "--decision-at",SIGNAL,"--evaluated-at",EVALUATED]
    out=tmp_path/"derived"
    main([*args,"--out",str(out)])
    capsys.readouterr()
    report=json.loads((out/"cash_delisting_research.json").read_text())
    assert report["cash_exit_total_return"] == .1
    assert report["settlement_receipt_claims_consistent"] is True
    assert "cash_per_share" not in report
    manifest_obj=json.loads(manifest.read_text())
    manifest_obj["retrieved_at"]="2024-06-15T09:00:00+09:00"
    manifest.write_text(json.dumps(manifest_obj))
    blocked=tmp_path/"blocked"
    main([*args,"--out",str(blocked)])
    capsys.readouterr()
    report=json.loads((blocked/"cash_delisting_research.json").read_text())
    assert report["status"] == STATUS_BLOCKED
    assert report["cash_exit_total_return"] is None


def test_no_legacy_cli_receipt_without_lineage_pair(tmp_path):
    from eraleader.cli import main
    scenario, files, manifest, _ = inputs(tmp_path)
    with pytest.raises(SystemExit) as err:
        main(["audit-cash-delist","--file",str(files[0]),
              "--settlement-receipt",str(manifest),
              "--security-id",SEC,"--market","KR",
              "--decision-at",SIGNAL,"--evaluated-at",EVALUATED,
              "--out",str(tmp_path/"must_not_publish")])
    assert err.value.code == 2
    assert not (tmp_path/"must_not_publish"/"cash_delisting_research.json").exists()

@pytest.mark.parametrize("bad_source", [
    "SYNTHETIC_PROVIDER_NOT_CERTIFIED",
    "SYN-ISSUER-VINTAGE",
])
def test_claimed_second_source_cannot_be_the_same_declared_primary_source(
        tmp_path,bad_source):
    scenario, files, manifest, doc = inputs(tmp_path)
    data=json.loads(doc.read_text())
    data["source_id"]=bad_source
    raw=json.dumps(data,sort_keys=True).encode()
    doc.write_bytes(raw)
    receipt=json.loads(manifest.read_text())
    receipt["source_id_claimed"]=bad_source
    receipt["sha256"]=sha256(raw).hexdigest()
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert "RECEIPT_NOT_A_DISTINCT_DECLARED_SOURCE" in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None


def test_retrieval_before_settlement_known_does_not_make_retroactive_payment(tmp_path):
    scenario, files, manifest, _ = inputs(tmp_path)
    receipt=json.loads(manifest.read_text())
    receipt["published_at"]="2024-04-16T08:00:00+09:00"
    receipt["retrieved_at"]="2024-04-16T08:30:00+09:00"
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert "RECEIPT_RETRIEVED_BEFORE_SETTLEMENT_AVAILABLE" in result["blocking_reasons"]
    assert result["cash_exit_total_return"] is None


def test_payment_document_extra_claim_cannot_pretend_independent_certification(tmp_path):
    scenario, files, manifest, doc = inputs(tmp_path)
    data=json.loads(doc.read_text())
    data["independently_verified"]=True
    raw=json.dumps(data,sort_keys=True).encode()
    doc.write_bytes(raw)
    receipt=json.loads(manifest.read_text())
    receipt["sha256"]=sha256(raw).hexdigest()
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert "PAYMENT_DOCUMENT_SCHEMA_FIELDS_MISMATCH" in result["blocking_reasons"]
    assert result["settlement_receipt_independently_authenticated"] is False
    assert result["cash_exit_total_return"] is None


def test_manifest_extra_unsupported_certification_claim_is_rejected(tmp_path):
    scenario, files, manifest, _=inputs(tmp_path)
    receipt=json.loads(manifest.read_text())
    receipt["officially_attested"]=True
    manifest.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match="unexpected"):
        run(scenario,files,manifest)


def test_document_paid_at_equivalent_utc_instant_is_consistent_across_dst(tmp_path):
    scenario, files, manifest, doc = inputs(tmp_path,market="US")
    content=json.loads(doc.read_text())
    content["paid_at"]="2024-03-20T14:00:00Z"
    raw=json.dumps(content,sort_keys=True).encode()
    doc.write_bytes(raw)
    receipt=json.loads(manifest.read_text())
    receipt["sha256"]=sha256(raw).hexdigest()
    manifest.write_text(json.dumps(receipt))
    result=run(scenario,files,manifest)
    assert result["cash_exit_total_return"]==.05
    assert result["settlement_receipt_claims_consistent"] is True
