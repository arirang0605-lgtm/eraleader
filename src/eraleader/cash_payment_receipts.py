"""Read-only, locally asserted cash-delisting payment-document evidence audit.

A file hash and self-claimed issuer/publisher times do NOT certify that a real
payment occurred or that the alleged publisher supplied these historical bytes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from .delist_cash import _time as _stamp

RECEIPT_SCHEMA = "eraleader.cash_payment_receipt.v1"
DOCUMENT_SCHEMA = "eraleader.cash_payment_document.v1"
MAX_FILE_SIZE = 2_000_000
BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.json\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")
MANIFEST_KEYS = {
    "schema_version", "market", "security_id", "source_id_claimed",
    "publisher_id_claimed", "file", "sha256", "published_at", "retrieved_at",
}
DOCUMENT_KEYS = {
    "schema_version", "source_id", "market", "security_id", "event_id",
    "action_type", "last_trading_on", "effective_on", "cash_per_share",
    "currency", "paid_at", "cash_payment_confirmed",
}


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field in settlement evidence JSON")
        result[key] = value
    return result


def _read_json_file(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked settlement evidence")
    if not 0 < path.stat().st_size <= MAX_FILE_SIZE:
        raise ValueError("Empty or oversized settlement evidence")
    raw = path.read_bytes()
    if not 0 < len(raw) <= MAX_FILE_SIZE:
        raise ValueError("Empty or oversized settlement evidence")
    try:
        obj = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed settlement evidence JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("Settlement evidence must be a JSON object")
    return obj, sha256(raw).hexdigest()


def _amount_matches(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
    except (TypeError, ValueError, InvalidOperation):
        return False
    return a.is_finite() and b.is_finite() and a > 0 and a == b


def _timestamp_or_none(value: object) -> datetime | None:
    try:
        return _stamp(value)
    except (ValueError, TypeError, AttributeError):
        return None


def audit_declared_cash_payment_receipt(
    manifest_file: Path, settlement: dict, *,
    security_id: str, market: str, evaluated_at: str,
    issuer_source_id: str | None = None,
) -> dict:
    """Corroborate byte integrity and self-declared cash payment identity.

    Input is a receipt manifest plus a distinct normalized payment document.
    Structural/file security problems raise; contradictions return blockers.
    The result is research-only and cannot upgrade payout/PIT certifications.
    """
    cutoff = _stamp(evaluated_at)
    if market not in ("KR", "US") or not security_id.strip():
        raise ValueError("KR/US and permanent security ID required")
    if not isinstance(settlement, dict):
        raise ValueError("Cash settlement terms required for receipt audit")
    manifest_path = Path(manifest_file)
    manifest, manifest_sha = _read_json_file(manifest_path)
    if manifest.get("schema_version") != RECEIPT_SCHEMA:
        raise ValueError("Wrong settlement receipt manifest schema")
    if set(manifest) != MANIFEST_KEYS:
        raise ValueError("Missing or unexpected settlement receipt manifest fields")
    name = manifest.get("file")
    if (not isinstance(name, str) or not BASENAME.fullmatch(name)
            or name.startswith(".")):
        raise ValueError("Unsafe settlement receipt document filename")
    expected_hash = manifest.get("sha256")
    if not isinstance(expected_hash, str) or not HASH.fullmatch(expected_hash):
        raise ValueError("Invalid settlement document SHA256")
    if manifest_path.parent.is_symlink():
        raise ValueError("Symlinked settlement receipt directory")
    document_path = manifest_path.parent / name
    if document_path.is_symlink() or document_path.resolve().parent != manifest_path.parent.resolve():
        raise ValueError("Unsafe settlement document path")
    document, actual_hash = _read_json_file(document_path)
    problems: set[str] = set()
    if actual_hash != expected_hash:
        problems.add("PAYMENT_DOCUMENT_SHA256_MISMATCH")
    if manifest.get("market") != market or manifest.get("security_id") != security_id:
        problems.add("RECEIPT_MANIFEST_IDENTITY_MISMATCH")
    source = manifest.get("source_id_claimed")
    publisher = manifest.get("publisher_id_claimed")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Missing declared source identity")
    if not isinstance(publisher, str) or not publisher.strip():
        raise ValueError("Missing declared publisher identity")
    if source == settlement.get("source_id") or (
            issuer_source_id is not None and source == issuer_source_id):
        problems.add("RECEIPT_NOT_A_DISTINCT_DECLARED_SOURCE")

    published = _timestamp_or_none(manifest.get("published_at"))
    retrieved = _timestamp_or_none(manifest.get("retrieved_at"))
    paid = _timestamp_or_none(settlement.get("paid_at"))
    settlement_known = _timestamp_or_none(settlement.get("available_at"))
    if published is None or retrieved is None:
        problems.add("RECEIPT_PUBLICATION_OR_RETRIEVAL_CLOCK_INVALID")
    else:
        if retrieved < published:
            problems.add("RECEIPT_RETRIEVED_BEFORE_PUBLICATION")
        if retrieved > cutoff or published > cutoff:
            problems.add("RECEIPT_UNAVAILABLE_BY_EVALUATION")
        if paid is not None and published < paid:
            problems.add("RECEIPT_PUBLISHED_BEFORE_CLAIMED_PAYMENT")
        if settlement_known is not None and retrieved < settlement_known:
            problems.add("RECEIPT_RETRIEVED_BEFORE_SETTLEMENT_AVAILABLE")
    if document.get("schema_version") != DOCUMENT_SCHEMA:
        problems.add("PAYMENT_DOCUMENT_SCHEMA_MISMATCH")
    if set(document) != DOCUMENT_KEYS:
        problems.add("PAYMENT_DOCUMENT_SCHEMA_FIELDS_MISMATCH")
    for field in ("market", "security_id", "event_id", "action_type",
                  "last_trading_on", "effective_on", "currency"):
        expected = (market if field == "market" else security_id if field == "security_id"
                    else settlement.get(field))
        if document.get(field) != expected:
            problems.add("PAYMENT_DOCUMENT_" + field.upper() + "_MISMATCH")
    if document.get("action_type") != "cash_delist":
        problems.add("PAYMENT_DOCUMENT_NONCASH_EVENT")
    if not _amount_matches(document.get("cash_per_share"), settlement.get("cash_per_share")):
        problems.add("PAYMENT_DOCUMENT_CASH_AMOUNT_MISMATCH")
    if document.get("cash_payment_confirmed") is not True or settlement.get("cash_payment_confirmed") is not True:
        problems.add("PAYMENT_DOCUMENT_UNCONFIRMED_PAYMENT")
    if _timestamp_or_none(document.get("paid_at")) != paid or paid is None:
        problems.add("PAYMENT_DOCUMENT_PAID_AT_MISMATCH")
    if document.get("source_id") != source:
        problems.add("PAYMENT_DOCUMENT_SOURCE_ID_MISMATCH")

    blockers = sorted(problems)
    return {
        "status": ("LOCAL_PAYMENT_RECEIPT_CLAIMS_MATCH_NOT_CERTIFIED" if not blockers
                   else "CENSORED_PAYMENT_RECEIPT_CLAIMS_INCONSISTENT"),
        "market": market, "security_id": security_id,
        "receipt_manifest_sha256": manifest_sha,
        "payment_document_sha256": actual_hash,
        "declared_payment_source_id": source,
        "declared_publisher_id": publisher,
        "source_declared_distinct": "RECEIPT_NOT_A_DISTINCT_DECLARED_SOURCE" not in problems,
        "receipt_retrieved_at_utc": retrieved.isoformat() if retrieved else None,
        "blockers": blockers, "blocking_count": len(blockers),
        "receipt_claims_consistent": not bool(blockers),
        "cash_payment_independently_authenticated": False,
        "retrieval_timestamp_independently_attested": False,
        "historical_universe_pit_certified": False,
        "warning": (
            "A local hash and distinct CLAIMED publisher do not independently prove "
            "payment, publication time, source ownership or a complete historical universe."
        ),
    }
