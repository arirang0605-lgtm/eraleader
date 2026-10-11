"""Strict optional two-provider raw-document first-ingest receipt linkage.

Only the local first-write SHA/witness binding is checked; publisher identity,
actual source clock and issuer/security/class PIT remain uncertified.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json

from .provider_staged_lineage import audit_staged_source_lineage

OriginalSources = tuple[tuple[Path, Path], tuple[Path, Path]]


def validate_original_sources(
    *, require_original_pins: bool, original_sources: OriginalSources | None,
) -> OriginalSources | None:
    """Never silently ignore partial paths or raw-pin-required mode."""
    if type(require_original_pins) is not bool:
        raise ValueError("Original first-ingest PIN requirement must be boolean")
    if not require_original_pins:
        if original_sources is not None:
            raise ValueError("Four original PIN source paths require strict mode")
        return None
    if (not isinstance(original_sources,(tuple,list)) or
        len(original_sources)!=2 or
        any(not isinstance(pair,(tuple,list)) or len(pair)!=2 or
            any(value is None or not isinstance(value,(str,Path))
                or not str(value).strip() for value in pair)
            for pair in original_sources)):
        raise ValueError("Strict original PIN mode requires both suppliers' staged and normalized manifests")
    sources=tuple(tuple(Path(v) for v in pair) for pair in original_sources)
    if (sources[0][0].resolve()==sources[1][0].resolve() or
        sources[0][1].resolve()==sources[1][1].resolve()):
        raise ValueError("Separate original source and normalized manifest paths required for both suppliers")
    return sources


def corroborate_pinned_original_sources(
    *, source_paths: OriginalSources,
    ledgers: tuple[Path,Path], bundle_hashes: tuple[str,str],
    receipts: list[dict], decision_at: str, clock: datetime,
) -> dict:
    """Read both raw original manifests and first-ingest receipts; fail closed.

    This is read-only and reconstructs raw source/witness hashes from files
    instead of accepting caller assertions about which source was imported.
    """
    reports=[]
    witnesses=[]
    for i,(paths,ledger,bundle,receipt) in enumerate(
        zip(source_paths,ledgers,bundle_hashes,receipts)
    ):
        audit=audit_staged_source_lineage(
            Path(paths[0]),Path(paths[1]),
            ledger_file=Path(ledger),decision_at=decision_at,
            clock=clock,require_original_first_ingest_pin=True,
        )
        if (audit["normalized_bundle_manifest_sha256"]!=bundle or
            audit["market"]!=receipt["market"] or
            audit["source_claims"]["source_id"]!=receipt["source_id"] or
            audit["source_claims"]["publisher_id_claimed"]!=receipt["publisher_id_claimed"] or
            audit["source_claims"]["vintage_id"]!=receipt["vintage_id"]):
            raise ValueError("Original source PIN identity differs from paired provider first-ingest receipt")
        if (not audit["usable_as_local_research_source_at_decision"] or
            not audit["original_doc_id_hash_attested_at_first_ingest"] or
            not audit["first_ingest_raw_and_witness_pin_present"]):
            raise ValueError("Original first-ingest PIN source not available by decision cutoff")
        witnesses.append({
            "bundle_sha256":bundle,
            "original_staged_manifest_sha256":audit["original_staged_manifest_sha256"],
            "original_line_to_normalized_witness_sha256":
                audit["original_line_to_normalized_witness_sha256"],
            "first_ingest_time_utc":audit["first_ingest_time_utc"],
            "market":audit["market"],
        })
        reports.append(audit)
    digest=sha256(json.dumps(
        witnesses,sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode()).hexdigest()
    return {
        "original_source_pair_witness_sha256":digest,
        "source_a_original_first_pin_matched":True,
        "source_b_original_first_pin_matched":True,
        "original_first_ingest_pins_locally_consistent":True,
        "independent_original_publisher_and_timestamp_verified":False,
    }
