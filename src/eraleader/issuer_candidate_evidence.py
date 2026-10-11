"""Optional 2_2/2_5 issuer/security-class pre-WATCH evidence, local claims only.

Requires the SAME staged source A whose original bytes were first-ingest PIN
verified against the candidate provider ledger. This additional witness is
necessary, never sufficient, for a research WATCH, and cannot certify PIT.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json

from .frozen_holdout import _stamp
from .issuer_class_bridge import (
    STATUS_MATCH, _stage_active, audit_staged_issuer_class, ZONES,
)
from .provider_export_normalizer import _preflight
from .provider_pit_adapter import _now


def audit_candidate_issuer_class(
    staged_manifest: Path, issuer_lineage: Path, *,
    market: str, decision_at: str, candidate_members: dict,
    clock: datetime | None = None,
) -> dict:
    """Corroborate each actual as-of candidate ID, not merely aggregate counts.

    Caller MUST verify that staged_manifest belongs to a first-ingest-pinned
    original provider A receipt. A separate self-declared issuer source cannot
    upgrade the local gate to authenticated or full-exchange PIT.
    """
    if market not in ZONES or not isinstance(candidate_members, dict):
        raise ValueError("Issuer class candidate market/membership required")
    cutoff = _stamp(decision_at)
    now = _now(clock)
    if cutoff > now:
        raise ValueError("Future issuer-class candidate decision forbidden")
    before = audit_staged_issuer_class(
        Path(staged_manifest), Path(issuer_lineage),
        decision_at=cutoff.isoformat(), clock=now,
    )
    if before["market"] != market:
        raise ValueError("Issuer-class bridge market differs from candidate market")
    issues = Counter()
    matched = 0
    if before["status"] != STATUS_MATCH:
        for reason, count in before["blocker_counts"].items():
            issues["BRIDGE_" + reason] += count
        if not issues:
            issues["BRIDGE_NOT_CONCORDANT"] += 1
    else:
        stage, normalized, _, metadata = _preflight(Path(staged_manifest), now)
        if (stage["market"] != market or
                metadata["source_raw_manifest_sha256"] !=
                before["staged_source_manifest_sha256"]):
            raise ValueError("First-pinned staged class source changed")
        day = cutoff.astimezone(ZONES[market]).date().isoformat()
        active = _stage_active(normalized, cutoff, day, issues)
        for sec, member in sorted(candidate_members.items()):
            if type(sec) is not str or not isinstance(member, dict):
                issues["INVALID_CANDIDATE_CLASS"] += 1
                continue
            claimed = active.get(sec)
            if claimed is None:
                issues["CANDIDATE_CLASS_NOT_IN_PINNED_SOURCE"] += 1
            elif (member.get("security_id") != sec or
                  member.get("market") != market or
                  any(member.get(field) != claimed.get(field)
                      for field in ("ticker", "valid_from", "valid_to"))):
                issues["CANDIDATE_CLASS_MEMBERSHIP_MISMATCH"] += 1
            else:
                matched += 1
        if not candidate_members:
            issues["NO_CANDIDATE_CLASS"] += 1
    # A two-pass class audit is necessary but not enough: do not publish a
    # positive research result after a source edit between passes.
    after = audit_staged_issuer_class(
        Path(staged_manifest), Path(issuer_lineage),
        decision_at=cutoff.isoformat(), clock=now,
    )
    if before != after:
        raise RuntimeError("Issuer class source revised during candidate gate")
    evidence = {
        "market": market,
        "decision_at_utc": cutoff.isoformat(),
        "staged_manifest_sha256": before["staged_source_manifest_sha256"],
        "staged_stream_sha256": before["staged_source_stream_sha256"],
        "lineage_sha256": before["issuer_reference_sha256"],
        "status": before["status"],
        "matched_candidates": matched,
        "blocker_counts": dict(sorted(issues.items())),
    }
    digest = sha256(json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return {
        "status": before["status"],
        "candidate_class_match_count": matched,
        "candidate_class_evidence_sha256": digest,
        "blocker_counts": dict(sorted(issues.items())),
        "research_evidence_only": True,
        "issuer_or_class_independently_authenticated": False,
        "historical_universe_pit_certified": False,
        "official_leader_promotions": 0,
    }
