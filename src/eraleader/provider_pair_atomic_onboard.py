"""2_2/2_5 atomic offline onboarding for two declared KR or US PIT feeds.

CONTINUE existing staged normalizer, immutable local first-receipt/import and
strict two-provider as-of checker. BOTH sources must pass before one directory
is published. This does not download data or certify claimed publishers/PIT.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import uuid
from pathlib import Path
import os
import shutil
import stat
import tempfile

from .provider_export_normalizer import (
    _preflight, normalize_provider_export, EXPORT_STATUS,
)
from .provider_pit_adapter import (
    _now, import_provider_bundle, INTAKE_STATUS,
)
from .provider_dual_source_audit import (
    audit_provider_source_pair, STATUS_CONSISTENT,
)
from .provider_staged_lineage import (
    audit_staged_source_lineage, STATUS_MATCHED,
)

STATUS = "LOCAL_TWO_PROVIDER_ATOMIC_FIRST_INGEST_RESEARCH_ONLY"
BLOCK = "BLOCKED_PROVIDER_PAIR_FIRST_INGEST_NOT_PUBLISHED"
SUBDIRS = ("source_a", "source_b")
RECEIPT_NAME = "first_pair_receipt.json"
RECEIPT_SCHEMA = "eraleader.provider_pair_first_commit.v1"


def _manifest_path(value):
    path = Path(value)
    if (not path.is_absolute() or path.is_symlink() or
            path.parent.is_symlink() or path.name != "manifest.json" or
            not path.is_file()):
        raise ValueError("Two existing absolute nonlinked raw staged manifests required")
    return path


def _destination(path, original):
    target = Path(path)
    if (not target.is_absolute() or ".." in target.parts or
            target.name in ("", ".", "..") or
            target.exists() or target.is_symlink()):
        raise ValueError("Atomic provider-pair output must be a NEW absolute directory")
    parent = target.parent
    if (parent.is_symlink() or not parent.is_dir() or
            parent.stat().st_uid != os.geteuid() or
            stat.S_IMODE(parent.stat().st_mode) & 0o077):
        raise ValueError("Two-provider output requires existing owner-only parent")
    for source in original:
        upstream = source.parent
        if (target == upstream or target in upstream.parents or
                upstream in target.parents):
            raise ValueError("Provider-pair publication must never overlap raw source folder")
    return target


def onboard_staged_provider_pair(staged_a, staged_b, target, *,
                                 clock:datetime|None=None):
    """All-or-nothing publication of paired normalized bundles + PIT receipts.

    The first registration and as-of cutoff are the SAME current clock.
    Retrospective user timestamps cannot be injected through the CLI, and
    alleged publishers remain unverified even after strict source agreement.
    """
    now = _now(clock)
    original = (_manifest_path(staged_a), _manifest_path(staged_b))
    if original[0].resolve() == original[1].resolve():
        raise ValueError("Two different original staged first-source manifests required")
    # Validate BOTH entire original source inventories before even allocating
    # the temporary destination, not only their declaration manifests.
    preflights = [_preflight(manifest, now) for manifest in original]
    a, b = (item[0] for item in preflights)
    if a["market"] != b["market"]:
        raise ValueError("Different KR/US markets cannot enter one paired PIT onboarding")
    if (a["source_id"].strip().casefold() == b["source_id"].strip().casefold() or
            a["publisher_id_claimed"].strip().casefold() ==
            b["publisher_id_claimed"].strip().casefold()):
        raise ValueError("Two distinct claimed publishers and source identities required")
    destination = _destination(target, original)
    first = tuple(item[3] for item in preflights)
    temp = Path(tempfile.mkdtemp(prefix=".eraleader_pair_ingest_", dir=destination.parent))
    try:
        os.chmod(temp, 0o700)
        normalized = []
        ledgers = []
        digest = []
        for tag, manifest in zip(SUBDIRS, original):
            root = temp / tag
            root.mkdir(mode=0o700)
            normalized_path = root / "normalized"
            converted = normalize_provider_export(manifest, normalized_path, clock=now)
            if (converted["status"] != EXPORT_STATUS or
                    converted["market"] != a["market"]):
                raise ValueError("Provider normalization diverged during pair import")
            ledger = root / "offline.sqlite"
            imported = import_provider_bundle(
                normalized_path/"manifest.json", ledger,
                clock=now, staged_manifest=manifest)
            if (imported["status"] != INTAKE_STATUS or
                    imported["first_registered_at_utc"] != now.isoformat() or
                    imported["original_staged_receipt_present"] is not True or
                    imported["original_staged_receipt_first_pinned"] is not True):
                raise ValueError("Provider first ingest was not immutably recorded")
            lineage = audit_staged_source_lineage(
                manifest, normalized_path/"manifest.json",
                decision_at=now.isoformat(), ledger_file=ledger,
                clock=now, require_original_first_ingest_pin=True)
            if (lineage["status"] != STATUS_MATCHED or
                    lineage["source_and_normalized_bytes_matched"] is not True or
                    lineage["original_doc_id_hash_attested_at_first_ingest"] is not True or
                    lineage["usable_as_local_research_source_at_decision"] is not True):
                raise ValueError("First original source lineage did not verify locally")
            normalized.append(normalized_path/"manifest.json")
            ledgers.append(ledger)
            digest.append(imported["bundle_sha256"])
        check = audit_provider_source_pair(
            ledgers[0], digest[0], ledgers[1], digest[1],
            decision_at=now.isoformat(),clock=now,
            require_original_pins=True,
            original_sources=((original[0],normalized[0]),
                              (original[1],normalized[1])))
        if (check["status"] != STATUS_CONSISTENT or
                check["problem_count"] != 0 or
                check["matched_active_issuer_count"] < 1 or
                check["source_a_original_first_pin_matched"] is not True or
                check["source_b_original_first_pin_matched"] is not True or
                check["original_first_ingest_pins_locally_consistent"] is not True or
                check["official_historical_universe_pit_certified"] is not False or
                check["official_leader_promotions"] != 0):
            raise ValueError("Two-provider first PIT source pair cannot corroborate local research")
        # Guard original bytes AFTER importer/pair audits; never publish a
        # normalized result from an original that changed during the session.
        for source, originally in zip(original, first):
            current = _preflight(source,now)[3]
            if current["source_raw_manifest_sha256"] != originally["source_raw_manifest_sha256"] or (
                current["source_file_sha256"] != originally["source_file_sha256"]
            ):
                raise ValueError("Original staged bytes changed during atomic paired import")
        # Record the WHOLE frozen pair identity before the single publish.
        # Relative DB/normalized paths remain stable across the final rename;
        # the private original input paths never enter a public JSON report.
        frozen_receipt = {
            "schema": RECEIPT_SCHEMA,
            "first_ingest_at_utc": now.isoformat(),
            "nonce": uuid.uuid4().hex,
            "market": a["market"],
            "original_staged_manifests": [str(path) for path in original],
            "original_manifest_sha256": [
                value["source_raw_manifest_sha256"] for value in first],
            "original_streams_sha256": [
                value["source_file_sha256"] for value in first],
            "normalized_manifest_sha256": list(digest),
            "initial_matched_active_securities": check["matched_active_issuer_count"],
            "initial_matched_actions": check["matched_corporate_event_count"],
            "initial_matched_fundamentals": check["matched_fundamental_fact_count"],
            "initial_matched_industry": check["matched_industry_fact_count"],
            "original_pin_pair_locally_matched": True,
            "official_source_pit_certified": False,
        }
        original_receipt = (json.dumps(
            frozen_receipt, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)+"\n").encode()
        fd=os.open(temp/RECEIPT_NAME,
                   os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as first_output:
            first_output.write(original_receipt)
            first_output.flush()
            os.fsync(first_output.fileno())
        receipt_sha = sha256(original_receipt).hexdigest()
        if destination.exists() or destination.is_symlink():
            raise ValueError("Atomic paired destination claimed by another process")
        os.rename(temp,destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {
        "status": STATUS,
        "market": a["market"],
        "first_ingest_registered_at_utc": now.isoformat(),
        "matched_active_declared_securities": check["matched_active_issuer_count"],
        "matched_corporate_events": check["matched_corporate_event_count"],
        "matched_fundamental_facts": check["matched_fundamental_fact_count"],
        "matched_industry_facts": check["matched_industry_fact_count"],
        "source_a_normalized_manifest_sha256": digest[0],
        "source_b_normalized_manifest_sha256": digest[1],
        "two_original_first_ingest_receipts_pinned": True,
        "first_pair_receipt_sha256": receipt_sha,
        "two_provider_semantic_conflicts": 0,
        "all_or_nothing_published": True,
        "research_watch_requires_separate_candidate_gate": True,
        "original_publisher_independently_authenticated": False,
        "source_retrieval_timestamp_independently_attested": False,
        "legal_issuer_security_class_pit_certified": False,
        "complete_historical_exchange_universe_certified": False,
        "actual_future_leader_skill_certified": False,
        "official_leader_promotions": 0,
        "external_api_calls": 0,
        "messages_sent": 0,
    }
