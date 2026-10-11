"""2_2/2_5: audit exact staged export -> normalized bytes -> first ingest.

This is only a local provenance consistency audit of self-claimed vendor exports.
Original issuer/class, official source documents, timestamps and true independent
publisher identities cannot be certified by hashing local files.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json

from .frozen_holdout import _stamp
from .offline_pit import KINDS
from .provider_export_normalizer import _preflight
from .provider_pit_adapter import (
    BUNDLE_SCHEMA, MAX_MANIFEST_BYTES, MAX_STREAM_BYTES,
    _json, _now, audit_registered_provider_asof, inspect_provider_bundle,
)

STATUS_MATCHED = "LOCAL_STAGED_TO_FIRST_INGEST_LINEAGE_MATCHED_NOT_CERTIFIED"
STATUS_NO_INGEST = "LOCAL_STAGED_BYTES_MATCHED_NOT_FIRST_INGESTED"
STATUS_CENSORED = "CENSORED_STAGED_INGEST_AFTER_DECISION"
WITNESS_NAME = "normalization_witnesses.jsonl"


def _safe_bytes(path: Path, *, limit: int, label: str) -> bytes:
    path=Path(path)
    if (path.is_symlink() or path.parent.is_symlink()
            or not path.is_file() or not 0<path.stat().st_size<=limit):
        raise ValueError("Missing, unsafe symlink or oversized "+label)
    return path.read_bytes()


def _compact_line(obj: dict) -> bytes:
    return (json.dumps(
        obj, ensure_ascii=False, sort_keys=True,
        separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def _one_pass(staged_manifest: Path, normalized_manifest: Path,
              now: datetime) -> tuple[dict,dict]:
    """Reconstruct ALL resulting normalized bytes from original staged lines.

    Do not trust the witness file's own hashes. Recreate each expected witness
    from raw source lines, claimed document ID and known normalization function.
    """
    source,converted,evidence,source_meta = _preflight(
        Path(staged_manifest), now,
    )
    path=Path(normalized_manifest)
    normalized_raw=_safe_bytes(
        path,limit=MAX_MANIFEST_BYTES,label="normalized manifest",
    )
    normalized=_json(normalized_raw)
    if not isinstance(normalized,dict):
        raise ValueError("Normalized provider manifest must be an object")
    root=path.parent
    stream_manifest=[]
    normalized_sha={}
    for kind in KINDS:
        if kind not in converted:
            continue
        expected=b"".join(_compact_line(row) for row in converted[kind])
        name=kind+".jsonl"
        actual=_safe_bytes(root/name,limit=MAX_STREAM_BYTES,
                           label="normalized "+kind+" stream")
        if actual!=expected:
            raise ValueError(
                "Staged source and normalized "+kind+" bytes mismatch"
            )
        digest=sha256(expected).hexdigest()
        normalized_sha[kind]=digest
        stream_manifest.append({
            "kind":kind,"file":name,"sha256":digest,
            "record_count":len(converted[kind]),
        })
    expected_manifest={
        "schema_version":BUNDLE_SCHEMA,
        "market":source["market"],
        "source_id":source["source_id"],
        "publisher_id_claimed":source["publisher_id_claimed"],
        "vintage_id":source["vintage_id"],
        "retrieved_at_claimed":source["retrieved_at_claimed"],
        "streams":stream_manifest,
    }
    expected_raw=(json.dumps(
        expected_manifest,sort_keys=True,ensure_ascii=False,indent=2
    )+"\n").encode()
    if normalized!=expected_manifest or normalized_raw!=expected_raw:
        raise ValueError("Staged source and normalized manifest identity/bytes mismatch")
    witnesses=b"".join(_compact_line(record) for record in evidence)
    actual_witnesses=_safe_bytes(
        root/WITNESS_NAME,
        limit=max(2_000_000, min(80_000_000, MAX_STREAM_BYTES*4)),
        label="normalization witness",
    )
    if actual_witnesses!=witnesses:
        raise ValueError("Original staged document witness bytes mismatch")
    inspected=inspect_provider_bundle(path,clock=now)
    if (inspected["rows_received"]!=len(evidence) or
        inspected["market"]!=source["market"] or
        inspected["source_id"]!=source["source_id"]):
        raise ValueError("Normalized source preflight disagrees with witness count/identity")
    digest={
        "original_staged_manifest_sha256":source_meta["source_raw_manifest_sha256"],
        "source_file_sha256":source_meta["source_file_sha256"],
        "normalized_bundle_manifest_sha256":sha256(normalized_raw).hexdigest(),
        "normalized_file_sha256":normalized_sha,
        "normalized_witness_sha256":sha256(witnesses).hexdigest(),
        "original_raw_document_witness_count":len(evidence),
    }
    report={
        "market":source["market"],
        "profile":source["profile"],
        "source_id":source["source_id"],
        "publisher_id_claimed":source["publisher_id_claimed"],
        "vintage_id":source["vintage_id"],
        "retrieved_at_claimed_utc":_stamp(
            source["retrieved_at_claimed"]).isoformat(),
        "normalized_record_count":len(evidence),
        "raw_document_receipt_count":len(evidence),
        "distinct_claimed_source_documents":len({
            r["source_document_id_claimed"] for r in evidence
        }),
        "normalized_by_kind":{kind:len(converted.get(kind,[])) for kind in KINDS},
        **digest,
    }
    return report,digest


def audit_staged_source_lineage(
    staged_manifest:Path,normalized_manifest:Path,*,decision_at:str,
    ledger_file:Path|None=None,clock:datetime|None=None,
) -> dict:
    """Report a conservative, first-ingest-pinned local lineage at cutoff.

    Missing imported evidence is not equivalent to a timely import. If any
    original/normalized/witness document is changed, reject before reporting.
    """
    now=_now(clock)
    cutoff=_stamp(decision_at)
    if cutoff>now:
        raise ValueError("Future staged-source decision cutoff is not allowed")
    original, witness=_one_pass(
        Path(staged_manifest),Path(normalized_manifest),now
    )
    receipt=None
    timely=False
    if ledger_file is not None:
        receipt=audit_registered_provider_asof(
            Path(ledger_file),
            original["normalized_bundle_manifest_sha256"],
            decision_at=cutoff.isoformat(),clock=now,
        )
        for key in ("market","source_id","publisher_id_claimed","vintage_id"):
            if original[key]!=receipt[key]:
                raise ValueError("Original provider first-ingest identity mismatch: "+key)
        if (_stamp(original["retrieved_at_claimed_utc"]) !=
                _stamp(receipt["retrieved_at_claimed_utc"]) or
            original["normalized_record_count"] !=
                receipt["rows_first_imported_local"]):
            raise ValueError("Staged normalized rows/retrieval differ from first-ingest receipt")
        timely=receipt["eligible_for_contemporaneous_research"] is True
    # A second source read catches a stage that changed during the receipt
    # lookup, including raw source_doc IDs which do not survive normalization.
    last,second=_one_pass(
        Path(staged_manifest),Path(normalized_manifest),now
    )
    if witness!=second or original!=last:
        raise ValueError("Staged source/normalization lineage revised during audit")
    if ledger_file is not None:
        repeated=audit_registered_provider_asof(
            Path(ledger_file),
            original["normalized_bundle_manifest_sha256"],
            decision_at=cutoff.isoformat(),clock=now,
        )
        if receipt!=repeated:
            raise ValueError("Provider first-ingest receipt revised during lineage audit")
    status=(STATUS_NO_INGEST if receipt is None else
            STATUS_MATCHED if timely else STATUS_CENSORED)
    # The report deliberately contains no raw identifier, unredacted source
    # document, price, financial values, or archived official document body.
    return {
        "status":status,
        "market":original["market"],
        "profile":original["profile"],
        "decision_at_utc":cutoff.isoformat(),
        "source_claims": {
            "source_id":original["source_id"],
            "publisher_id_claimed":original["publisher_id_claimed"],
            "vintage_id":original["vintage_id"],
        },
        "original_staged_manifest_sha256":original["original_staged_manifest_sha256"],
        "raw_source_file_sha256":original["source_file_sha256"],
        "normalized_bundle_manifest_sha256":original["normalized_bundle_manifest_sha256"],
        "normalized_stream_sha256":original["normalized_file_sha256"],
        "original_line_to_normalized_witness_sha256":original["normalized_witness_sha256"],
        "normalized_record_count":original["normalized_record_count"],
        "raw_document_receipt_count":original["raw_document_receipt_count"],
        "distinct_claimed_source_documents":original["distinct_claimed_source_documents"],
        "normalized_by_kind":original["normalized_by_kind"],
        "source_and_normalized_bytes_matched":True,
        "original_doc_id_to_normalized_digest_linked_locally":True,
        "original_doc_id_hash_attested_at_first_ingest":False,
        "local_first_ingest_receipt_supplied":receipt is not None,
        "locally_registered_before_decision":timely,
        "usable_as_local_research_source_at_decision":timely,
        "retrospective_source_ingestion":(
            receipt["retrospective_local_ingestion"] if receipt else None
        ),
        "retrospective_source_claimed_retrieval":(
            receipt["retrospective_provider_retrieval"] if receipt else None
        ),
        "first_ingest_time_utc":(
            receipt["first_registered_at_utc"] if receipt else None
        ),
        "independent_publisher_authenticated":False,
        "official_issuer_or_share_class_certified":False,
        "independent_source_document_verified":False,
        "original_source_available_at_independently_attested":False,
        "external_pit_certified":False,
        "official_leader_promotions":0,
        "warning":(
            "This ties staged source row hashes/document-ID claims to normalized "
            "files and a local first-ingest receipt only. It does not authenticate "
            "official documents, legal issuer/share class, exchange completeness, "
            "licensed provider independence, or real historical PIT/leader skill."
        ),
    }
