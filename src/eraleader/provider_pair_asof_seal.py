"""Read-only as-of revalidation of an atomically first-pinned KR/US PIT pair.

The external caller must provide the *original* first-receipt SHA256 from the
pair's first publication. This prevents accepting a new, locally rewritten
pair receipt as if it were the original. No issuer/source authenticity or
historical market completeness is independently attested.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import os
import re
import stat

from .frozen_holdout import _stamp
from .provider_export_normalizer import _preflight
from .provider_pair_atomic_onboard import (
    RECEIPT_NAME, RECEIPT_SCHEMA, SUBDIRS, _manifest_path,
)
from .provider_pit_adapter import _json, _now
from .provider_dual_source_audit import (
    audit_provider_source_pair, STATUS_CONSISTENT,
)

READY="LOCAL_PINNED_TWO_PROVIDER_ASOF_CONCORDANT_RESEARCH_ONLY"
LATE="BLOCKED_PINNED_PROVIDER_PAIR_RETROSPECTIVE_ASOF"
CONFLICT="BLOCKED_PINNED_PROVIDER_PAIR_SOURCE_CONTRADICTION"
SHA=re.compile(r"[0-9a-f]{64}\Z")
HEX32=re.compile(r"[0-9a-f]{32}\Z")
MAX_RECEIPT=16_384
COUNTS={
    "initial_matched_active_securities": "matched_active_issuer_count",
    "initial_matched_actions": "matched_corporate_event_count",
    "initial_matched_fundamentals": "matched_fundamental_fact_count",
    "initial_matched_industry": "matched_industry_fact_count",
}
FIELDS={
    "schema","first_ingest_at_utc","nonce","market",
    "original_staged_manifests","original_manifest_sha256",
    "original_streams_sha256","normalized_manifest_sha256",
    *COUNTS, "original_pin_pair_locally_matched",
    "official_source_pit_certified",
}


def _receipt(root, trusted_sha):
    if not isinstance(trusted_sha,str) or SHA.fullmatch(trusted_sha) is None:
        raise ValueError("Original independently held pair receipt SHA256 is mandatory")
    root=Path(root)
    if (not root.is_absolute() or root.is_symlink() or
            root.parent.is_symlink() or not root.is_dir() or
            root.stat().st_uid!=os.geteuid() or
            stat.S_IMODE(root.stat().st_mode)&0o077):
        raise ValueError("Pinned provider pair requires original private 0700 root")
    file=root/RECEIPT_NAME
    if (file.is_symlink() or not file.is_file() or
            file.stat().st_uid!=os.geteuid() or
            stat.S_IMODE(file.stat().st_mode)&0o077 or
            not 0<file.stat().st_size<=MAX_RECEIPT):
        raise ValueError("Missing or unsafe first pair SHA receipt")
    raw=file.read_bytes()
    if sha256(raw).hexdigest()!=trusted_sha:
        raise ValueError("First published provider pair receipt SHA changed")
    doc=_json(raw)
    if (type(doc) is not dict or set(doc)!=FIELDS or
            doc["schema"]!=RECEIPT_SCHEMA or doc["market"] not in {"KR","US"} or
            not isinstance(doc["nonce"],str) or
            HEX32.fullmatch(doc["nonce"]) is None or
            doc["original_pin_pair_locally_matched"] is not True or
            doc["official_source_pit_certified"] is not False):
        raise ValueError("Forged original provider pair provenance")
    import json
    if (json.dumps(doc,sort_keys=True,ensure_ascii=False,
                   separators=(",",":"),allow_nan=False)+"\n").encode()!=raw:
        raise ValueError("Noncanonical first pair receipt")
    if (not isinstance(doc["original_staged_manifests"],list) or
            len(doc["original_staged_manifests"])!=2 or
            not all(type(v) is str for v in doc["original_staged_manifests"]) or
            not isinstance(doc["original_manifest_sha256"],list) or
            len(doc["original_manifest_sha256"])!=2 or
            not all(type(v) is str and SHA.fullmatch(v)
                    for v in doc["original_manifest_sha256"]) or
            not isinstance(doc["normalized_manifest_sha256"],list) or
            len(doc["normalized_manifest_sha256"])!=2 or
            not all(type(v) is str and SHA.fullmatch(v)
                    for v in doc["normalized_manifest_sha256"]) or
            not isinstance(doc["original_streams_sha256"],list) or
            len(doc["original_streams_sha256"])!=2):
        raise ValueError("Incomplete paired original stream inventory")
    for streams in doc["original_streams_sha256"]:
        if (type(streams) is not dict or
                not streams or len(streams)>4 or
                not set(streams).issubset(
                    {"membership","actions","fundamentals","industry"}) or
                any(type(x) is not str or SHA.fullmatch(x) is None
                    for x in streams.values())):
            raise ValueError("Invalid original frozen pair source digests")
    if any(type(doc[k]) is not int or doc[k]<0 for k in COUNTS):
        raise ValueError("Original first pair source counts were rewritten")
    if doc["initial_matched_active_securities"]<1:
        raise ValueError("An empty originally active PIT population cannot be first verified")
    when=_stamp(doc["first_ingest_at_utc"])
    originals=tuple(_manifest_path(x) for x in doc["original_staged_manifests"])
    if originals[0].resolve()==originals[1].resolve():
        raise ValueError("Both provider slots point to one original")
    return root,doc,when,originals


def audit_atomic_provider_pair_asof(
    pair_root:Path, first_pair_receipt_sha256:str, *, decision_at:str,
    clock:datetime|None=None,
)->dict:
    """Check FULL original staged source, normalized docs and first receipt.

    No writes or API calls. The pair's first-receipt digest MUST have been
    retained separately at onboarding: local bytes alone cannot provide
    independent first-observation assurance.
    """
    now=_now(clock)
    cutoff=_stamp(decision_at)
    if cutoff>now:
        raise ValueError("Provider pair as-of audit cannot use a future decision")
    root,receipt,registered,originals=_receipt(
        pair_root,first_pair_receipt_sha256)
    if registered>now:
        raise ValueError("Original pair first registration is in the future")

    # Both original source files and their first normalized bundle must still
    # match. No reconstructed/simulated raw first-received timestamp is allowed.
    normalized=[]
    ledgers=[]
    digests=[]
    for i,(tag,original) in enumerate(zip(SUBDIRS,originals)):
        metadata,_,_,integrity=_preflight(original,now)
        if (metadata["market"]!=receipt["market"] or
                integrity["source_raw_manifest_sha256"]!=
                    receipt["original_manifest_sha256"][i] or
                integrity["source_file_sha256"]!=
                    receipt["original_streams_sha256"][i]):
            raise ValueError("Original first PIT publisher files changed since paired publication")
        subdir=root/tag
        if (subdir.is_symlink() or not subdir.is_dir() or
                subdir.stat().st_uid!=os.geteuid()):
            raise ValueError("Unsafe first paired source folder")
        manifest=subdir/"normalized"/"manifest.json"
        ledger=subdir/"offline.sqlite"
        if (manifest.is_symlink() or manifest.parent.is_symlink() or
                not manifest.is_file() or ledger.is_symlink() or
                not ledger.is_file()):
            raise ValueError("Published PIT normalized source/receipt is missing")
        if sha256(manifest.read_bytes()).hexdigest()!=receipt[
                "normalized_manifest_sha256"][i]:
            raise ValueError("First normalized PIT manifest SHA changed")
        normalized.append(manifest)
        ledgers.append(ledger)
        digests.append(receipt["normalized_manifest_sha256"][i])

    original_sources=tuple((source,normalized[i])
                           for i,source in enumerate(originals))
    initial=audit_provider_source_pair(
        ledgers[0],digests[0],ledgers[1],digests[1],
        decision_at=registered.isoformat(),clock=now,
        require_original_pins=True,original_sources=original_sources,
        sample_limit=1)
    if (initial["status"]!=STATUS_CONSISTENT or
            initial["problem_count"]!=0 or
            any(initial[v]!=receipt[k] for k,v in COUNTS.items()) or
            initial["source_a_original_first_pin_matched"] is not True or
            initial["source_b_original_first_pin_matched"] is not True):
        raise ValueError("Published pair original first decision SHA/counts cannot replay")

    if cutoff<registered:
        return _summary(
            LATE,receipt,registered,cutoff,first_pair_receipt_sha256,
            0,{},False)
    current=audit_provider_source_pair(
        ledgers[0],digests[0],ledgers[1],digests[1],
        decision_at=cutoff.isoformat(),clock=now,
        require_original_pins=True,original_sources=original_sources,
        sample_limit=1)
    state=READY if (
        current["status"]==STATUS_CONSISTENT and
        current["problem_count"]==0 and
        current["matched_active_issuer_count"]>0 and
        current["source_a_original_first_pin_matched"] is True and
        current["source_b_original_first_pin_matched"] is True and
        current["original_first_ingest_pins_locally_consistent"] is True
    ) else CONFLICT
    return _summary(
        state,receipt,registered,cutoff,first_pair_receipt_sha256,
        current["matched_active_issuer_count"],
        current["blocker_counts"], state==READY)


def _summary(state,first,registered,cutoff,digest,active,problems,eligible):
    return {
        "status":state,
        "market":first["market"],
        "decision_at_utc":cutoff.isoformat(),
        "first_registered_at_utc":registered.isoformat(),
        "first_pair_receipt_sha256":digest,
        "source_a_bundle_sha256":first["normalized_manifest_sha256"][0],
        "source_b_bundle_sha256":first["normalized_manifest_sha256"][1],
        "matched_active_declared_securities_at_asof":active,
        "blocker_counts":dict(sorted(problems.items())),
        "eligible_for_local_candidate_watch_research_only":eligible,
        "official_pit_certified":False,
        "permanent_issuer_and_class_attested":False,
        "independent_publisher_and_timestamp_attested":False,
        "complete_historical_universe_certified":False,
        "real_future_leader_precision":None,
        "official_leader_promotions":0,
        "external_api_calls":0,
        "messages_sent":0,
    }
