"""Opt-in atomic first-ingest *local* raw staged/witness SHA pin.

A pin protects against later source-doc-claim edits when the normalized
manifest digest stays constant. Neither SQLite, SHA nor the Mac OS wall clock
is independently notarized, and this does not authenticate vendor origins.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

SCHEMA="eraleader.staged_original_first_ingest_pin.v1"
TABLE="provider_staged_original_receipts"


def _serialized(payload: dict) -> str:
    return json.dumps(payload,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False)


def _make_payload(original: dict,first_utc: str) -> dict:
    return {
        "schema_version":SCHEMA,
        "normalized_bundle_manifest_sha256":
            original["normalized_bundle_manifest_sha256"],
        "original_staged_manifest_sha256":
            original["original_staged_manifest_sha256"],
        "original_staged_file_sha256":
            original["source_file_sha256"],
        "original_line_to_normalized_witness_sha256":
            original["normalized_witness_sha256"],
        "normalized_stream_sha256":
            original["normalized_file_sha256"],
        "original_document_claim_count":
            original["distinct_claimed_source_documents"],
        "original_raw_document_witness_count":
            original["raw_document_receipt_count"],
        "market":original["market"],
        "profile":original["profile"],
        "source_id":original["source_id"],
        "publisher_id_claimed":original["publisher_id_claimed"],
        "vintage_id":original["vintage_id"],
        "retrieved_at_claimed_utc":original["retrieved_at_claimed_utc"],
        "first_registered_at_utc":first_utc,
        "independent_document_time_attested":False,
        "official_source_authenticity_verified":False,
    }


def _fetch(db: sqlite3.Connection,bundle_sha: str) -> tuple[str,str] | None:
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
    ).fetchone() is None:
        return None
    return db.execute(
        f"SELECT original_payload,original_payload_sha256 FROM {TABLE} "
        "WHERE bundle_sha256=?", (bundle_sha,),
    ).fetchone()


def _pin_anchor(db:sqlite3.Connection,bundle_sha:str) -> bool:
    """Use the normalized first-ingest receipt to require a raw pin forever.

    A deleted original-pin table/row cannot silently masquerade as an old
    normalized-only import while the normalized receipt anchor is intact.
    """
    columns={row[1] for row in db.execute(
        "PRAGMA table_info(provider_ingest_receipts)"
    ).fetchall()}
    original=_fetch(db,bundle_sha)
    if "original_staged_pin_sha256" not in columns:
        if original is not None:
            raise ValueError("Orphan original first-ingest pin without normalized receipt marker")
        return False
    linked=db.execute(
        "SELECT original_staged_pin_sha256 FROM provider_ingest_receipts "
        "WHERE bundle_sha256=?",(bundle_sha,),
    ).fetchone()
    if linked is None:
        if original is not None:
            raise ValueError("Orphan original staged pin without normalized provider receipt")
        return False
    marker=linked[0]
    if marker is None:
        if original is not None:
            raise ValueError("Orphan original first-ingest pin not anchored to normalized receipt")
        return False
    if (not isinstance(marker,str) or len(marker)!=64
            or original is None or original[1]!=marker
            or sha256(original[0].encode()).hexdigest()!=marker):
        raise ValueError("Missing or corrupt original first-ingest pin digest/marker")
    return True


def _validate_row(row: tuple[str,str],expected:dict) -> None:
    saved,claimed_sha=row
    if (type(saved) is not str or type(claimed_sha) is not str or
        sha256(saved.encode("utf-8")).hexdigest()!=claimed_sha):
        raise ValueError("Corrupt original first-ingest pin content SHA256")
    # Compare entire canonical payload, not merely user-supplied digest:
    # originally pinned document IDs/source files cannot be restated.
    if saved!=_serialized(expected):
        raise ValueError("Original staged first-ingest pin differs from source/witness bytes")


def bind_first_original_receipt(db:sqlite3.Connection,original:dict,
                                first_utc:str,*,was_imported:bool) -> bool:
    """Call inside provider normalized ingest's *existing* IMMEDIATE txn.

    Never upgrade an older normalized-only receipt into a supposedly
    original document pin. SQLite txn rollback covers both tables.
    """
    expected=_make_payload(original,first_utc)
    digest=expected["normalized_bundle_manifest_sha256"]
    old=_fetch(db,digest)
    if was_imported:
        if old is None:
            raise ValueError("Cannot retroactively first-pin original staged documents for already imported bundle")
        _validate_row(old,expected)
        if not _pin_anchor(db,digest):
            raise ValueError("Missing original first-ingest normalized receipt marker")
        return False
    if old is not None:
        raise ValueError("Orphan original first-ingest pin exists without normalized first-ingest receipt")
    db.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        bundle_sha256 TEXT PRIMARY KEY,
        original_payload TEXT NOT NULL,
        original_payload_sha256 TEXT NOT NULL
    )""")
    encoded=_serialized(expected)
    db.execute(
        f"INSERT INTO {TABLE} "
        "(bundle_sha256,original_payload,original_payload_sha256) "
        "VALUES (?,?,?)",
        (digest,encoded,sha256(encoded.encode()).hexdigest()),
    )
    row=_fetch(db,digest)
    if row is None:
        raise ValueError("Atomic original first-ingest pin not recorded")
    _validate_row(row,expected)
    columns={item[1] for item in db.execute(
        "PRAGMA table_info(provider_ingest_receipts)"
    ).fetchall()}
    if "original_staged_pin_sha256" not in columns:
        db.execute("ALTER TABLE provider_ingest_receipts "
                   "ADD COLUMN original_staged_pin_sha256 TEXT")
    wrote=db.execute(
        "UPDATE provider_ingest_receipts "
        "SET original_staged_pin_sha256=? "
        "WHERE bundle_sha256=? AND original_staged_pin_sha256 IS NULL",
        (sha256(encoded.encode()).hexdigest(),digest),
    )
    if wrote.rowcount!=1 or not _pin_anchor(db,digest):
        raise ValueError("Could not atomically anchor original staged pin in normalized receipt")
    return True


def audit_first_original_receipt(ledger_file: Path,original:dict,
                                 *,first_registered_at_utc:str) -> bool:
    """Read optional original pin. False for legitimate historic legacy data.

    An existing but mismatched pin is always fatal, even outside strict mode.
    Caller must separately verify the normalized ingest receipt and its
    first time, and not treat local SHA as independent publisher attestation.
    """
    target=Path(ledger_file)
    if target.is_symlink() or not target.is_file():
        raise ValueError("Missing/unsafe original first-ingest receipt database")
    db=sqlite3.connect(target.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        db.execute("BEGIN")
        if not _pin_anchor(db,original["normalized_bundle_manifest_sha256"]):
            return False
        source=_fetch(db,original["normalized_bundle_manifest_sha256"])
        if source is None:
            raise ValueError("Original first-ingest pin missing despite normalized anchor")
        _validate_row(source,_make_payload(original,first_registered_at_utc))
        return True
    except sqlite3.DatabaseError as exc:
        raise ValueError("Original first-ingest pin database is corrupt") from exc
    finally:
        db.close()
