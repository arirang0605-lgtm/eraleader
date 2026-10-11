"""2_2/2_5: offline declared legal issuer / individual security-class comparison.

Compares two DIFFERENT self-declared staged/lineage sources as of the decision
instant. A ticker, company code (KR corp code / US CIK), or identical payload
does NOT independently prove a legal issuer/class, original availability or
complete historical exchange universe. Zero official candidate promotions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .issuer_lineage import (
    _timestamp, _date, audit_issuer_lineage, ZONES,
)
from .provider_export_normalizer import _preflight
from .provider_pit_adapter import _json, _now

STATUS_MATCH = "LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
STATUS_BLOCKED = "BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
STATUS_LATE = "CENSORED_STAGED_ISSUER_CLASS_SOURCE_NOT_INDEPENDENT_OR_PIT"
MAX_REFERENCE_BYTES = 5_000_000
KR_CLASS = re.compile(r"(KR:CORP[0-9]{8}):ISSUE:([A-Za-z][A-Za-z0-9_-]{0,40})\Z")
US_CLASS = re.compile(r"(US:CIK[0-9]{10}):CLASS:([A-Za-z][A-Za-z0-9_-]{0,40})\Z")
EXIT_TYPES = frozenset(("delist", "cash_delist", "merger"))


def _claimed(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("Issuer/security class source requires nonempty claimed identity")
    return value.strip().casefold()


def _entity(sec: str, market: str) -> str | None:
    match = (KR_CLASS if market == "KR" else US_CLASS).fullmatch(sec)
    return match.group(1) if match else None


def _read_reference(path: Path) -> tuple[dict, str]:
    p=Path(path)
    if (p.is_symlink() or p.parent.is_symlink() or not p.is_file()
            or not 0<p.stat().st_size<=MAX_REFERENCE_BYTES):
        raise ValueError("Missing/unsafe issuer class lineage reference")
    raw=p.read_bytes()
    if not 0<len(raw)<=MAX_REFERENCE_BYTES:
        raise ValueError("Empty/oversized issuer class lineage input")
    ref=_json(raw)  # duplicate-key/nonfinite rejection from existing provider reader
    if not isinstance(ref, dict):
        raise ValueError("Issuer class lineage reference must be a JSON object")
    return ref, sha256(raw).hexdigest()


def _reference_active(registry: dict, cutoff: datetime, day: str, issues: Counter):
    """Issuer lineage validation is delegated to the existing PIT auditor."""
    latest={}
    for rec in registry["identities"]:
        if _timestamp(rec["known_at"])>cutoff:
            continue
        key=rec["record_id"]
        if key not in latest or rec["revision"]>latest[key]["revision"]:
            latest[key]=rec
    active={}
    for rec in latest.values():
        if rec["valid_from"]<=day and (not rec.get("valid_to") or day<rec["valid_to"]):
            sec=rec["security_id"]
            if sec in active:
                issues["DUPLICATE_ACTIVE_ISSUER_CLASS"]+=1
            active[sec]=rec
    ended={e["security_id"] for e in registry["events"]
           if (e["action_type"] in EXIT_TYPES and e["effective_on"]<=day
               and _timestamp(e["known_at"])<=cutoff)}
    for sec in sorted(ended & active.keys()):
        issues["LINEAGE_TERMINAL_EXIT_CONFLICT"]+=1
        active.pop(sec)
    return active


def _stage_active(streams: dict, cutoff: datetime, day: str, issues: Counter):
    """Latest contemporaneously published membership, not today's ticker list."""
    latest={}
    for row in streams.get("membership",[]):
        if _timestamp(row["known_at"])>cutoff or row["valid_from"]>day:
            continue
        sec=row["security_id"]
        prior=latest.get(sec)
        if prior is None or (row["valid_from"],row["known_at"],row["revision"]) > (
            prior["valid_from"],prior["known_at"],prior["revision"]
        ):
            latest[sec]=row
    active={
        sec:rec for sec,rec in latest.items()
        if rec.get("valid_to") is None or day<rec["valid_to"]
    }
    ended={e["security_id"] for e in streams.get("actions",[])
           if (e["action_type"] in EXIT_TYPES and e["effective_on"]<=day
               and _timestamp(e["known_at"])<=cutoff)}
    for sec in sorted(ended & active.keys()):
        issues["STAGED_TERMINAL_EXIT_CONFLICT"]+=1
        active.pop(sec)
    return active


def _collisions(rows: dict, label: str, issues: Counter):
    by_ticker=defaultdict(set)
    for sec,row in rows.items():
        by_ticker[row["ticker"]].add(sec)
    for secs in by_ticker.values():
        if len(secs)>1:
            issues[label+"_ACTIVE_TICKER_COLLISION"]+=1
    return by_ticker


def _one_pass(stage_file: Path, reference_file: Path, *,
              cutoff: datetime, now: datetime) -> dict:
    stage, normalized, _, metadata = _preflight(Path(stage_file), now)
    ref, reference_sha = _read_reference(Path(reference_file))
    # This existing audit validates source, issuer revision/effective chronology,
    # cross-market records, events and ticker collision in its own contract.
    ref_audit=audit_issuer_lineage(Path(reference_file),decision_at=cutoff.isoformat())
    market=stage["market"]
    if ref.get("market")!=market or ref_audit["market"]!=market:
        raise ValueError("Cross-market staged and issuer class PIT comparison")
    ref_retrieved=_timestamp(ref["retrieved_at"])
    if ref_retrieved>now:
        raise ValueError("Claimed issuer source was retrieved after local audit clock")
    stage_retrieved=_timestamp(stage["retrieved_at_claimed"])
    blockers=Counter()
    if stage_retrieved>cutoff:
        blockers["STAGED_SOURCE_NOT_AVAILABLE_BY_DECISION"]+=1
    if ref_retrieved>cutoff or ref_audit["retrospective_retrieval"]:
        blockers["ISSUER_LINEAGE_NOT_AVAILABLE_BY_DECISION"]+=1
    if _claimed(stage["source_id"])==_claimed(ref["source_id"]):
        blockers["DUPLICATE_CLAIMED_SOURCE"]+=1
    if _claimed(stage["publisher_id_claimed"])==_claimed(ref["publisher_id_claimed"]):
        blockers["DUPLICATE_CLAIMED_PUBLISHER"]+=1

    measured=0
    entities=set()
    source_n=reference_n=0
    if not blockers:
        day=cutoff.astimezone(ZONES[market]).date().isoformat()
        left=_stage_active(normalized,cutoff,day,blockers)
        right=_reference_active(ref,cutoff,day,blockers)
        source_n, reference_n=len(left),len(right)
        by_stage=_collisions(left,"STAGED",blockers)
        by_ref=_collisions(right,"ISSUER_LINEAGE",blockers)
        if ref_audit["active_ticker_conflict_count"]:
            blockers["REFERENCE_ACTIVE_TICKER_CONFLICT"]+=1
        if ref_audit["corporate_events_with_unknown_parent_count"]:
            blockers["REFERENCE_EVENT_UNKNOWN_PARENT"]+=1
        if ref_audit["corporate_events_with_missing_successor_count"]:
            blockers["REFERENCE_EVENT_MISSING_SUCCESSOR"]+=1

        for sec in sorted(set(left)|set(right)):
            a,b=left.get(sec),right.get(sec)
            if a is None:
                blockers["ISSUER_LINEAGE_ONLY_SECURITY_CLASS"]+=1
                if b["ticker"] in by_stage:
                    blockers["TICKER_ONLY_DIFFERENT_SECURITY_CLASS"]+=1
            elif b is None:
                blockers["STAGED_ONLY_SECURITY_CLASS"]+=1
                if a["ticker"] in by_ref:
                    blockers["TICKER_ONLY_DIFFERENT_SECURITY_CLASS"]+=1
            elif _entity(sec,market) is None:
                blockers["UNSUPPORTED_DECLARED_ISSUER_CLASS_ID"]+=1
            elif a["ticker"]!=b["ticker"]:
                blockers["SECURITY_CLASS_TICKER_CONFLICT"]+=1
            elif (a["valid_from"]!=b["valid_from"]
                  or a.get("valid_to")!=b.get("valid_to")):
                blockers["SECURITY_CLASS_LISTING_INTERVAL_CONFLICT"]+=1
            else:
                measured+=1
                entities.add(_entity(sec,market))
        if measured==0:
            blockers["NO_EXACT_SECURITY_CLASS_EVIDENCE"]+=1
    status=(STATUS_LATE if (any(x in blockers for x in (
        "STAGED_SOURCE_NOT_AVAILABLE_BY_DECISION",
        "ISSUER_LINEAGE_NOT_AVAILABLE_BY_DECISION",
        "DUPLICATE_CLAIMED_SOURCE","DUPLICATE_CLAIMED_PUBLISHER"
    ))) else STATUS_BLOCKED if blockers else STATUS_MATCH)
    report={
        "status":status,
        "market":market,
        "decision_at_utc":cutoff.isoformat(),
        "staged_profile":stage["profile"],
        "staged_source_manifest_sha256":metadata["source_raw_manifest_sha256"],
        "staged_source_stream_sha256":metadata["source_file_sha256"],
        "issuer_reference_sha256":reference_sha,
        "declared_sources_available_by_decision":(
            stage_retrieved<=cutoff and ref_retrieved<=cutoff
        ),
        "claimed_publishers_distinct":(
            _claimed(stage["publisher_id_claimed"])!=
            _claimed(ref["publisher_id_claimed"])
        ),
        "staged_asof_active_security_classes":source_n,
        "issuer_lineage_asof_active_security_classes":reference_n,
        "matched_security_class_count":measured if status!=STATUS_LATE else 0,
        "matched_legal_entity_count":len(entities) if status!=STATUS_LATE else 0,
        "unmatched_or_conflicted_count":sum(blockers.values()),
        "blocker_counts":dict(sorted(blockers.items())),
        "legal_issuer_or_class_independently_verified":False,
        "original_source_clocks_independently_attested":False,
        "historical_universe_pit_certified":False,
        "official_candidate_promotion_allowed":False,
        "research_watch_allowed_by_this_audit":False,
        "real_future_leader_precision":None,
        "official_leader_promotions":0,
        "external_api_calls":0,
        "warning":(
            "KR corp_code/issue_uid or SEC CIK/share_class_uid are self-claimed "
            "provider fields, NOT official authenticated securities. Matching "
            "issuer/class keys, ticker and effective intervals prove only "
            "local cross-document consistency, not complete exchange PIT."
        ),
    }
    return report


def audit_staged_issuer_class(
    staged_manifest: Path, issuer_lineage_file: Path, *, decision_at: str,
    clock: datetime | None = None,
) -> dict:
    """Read-only two-pass cross-check of whole claimed as-of issuer/class sets."""
    now=_now(clock)
    cutoff=_timestamp(decision_at)
    if cutoff>now:
        raise ValueError("Future issuer class PIT audit decision is forbidden")
    first=_one_pass(staged_manifest,issuer_lineage_file,cutoff=cutoff,now=now)
    second=_one_pass(staged_manifest,issuer_lineage_file,cutoff=cutoff,now=now)
    if first!=second:
        raise ValueError("Original staged or issuer class source changed during audit")
    return first
