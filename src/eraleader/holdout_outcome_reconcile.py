"""Reconcile sealed research cohorts with separately supplied, dated labels.

This reports WHICH candidates have calendar-mature and internally valid
research outcomes, not a certified era-leader success metric. Neither local
hashes nor supplier declared timestamps constitute independent provenance.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json

from .frozen_holdout import (
    _read_frozen, _stamp, TIMEZONES, evaluate_frozen_candidates,
)
from .holdout_maturity import audit_holdout_maturity

STATUS = "LOCAL_HOLDOUT_OUTCOME_RECONCILIATION_NOT_CERTIFIED"
REASONS = (
    "HORIZON_PENDING_NO_LABEL",
    "HORIZON_ELAPSED_NO_LABEL",
    "LABEL_NOT_YET_AVAILABLE",
    "PREMATURE_NEGATIVE_LABEL",
    "RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED",
)


def reconcile_holdout_outcomes(
    frozen_file: Path, *, evaluated_at: str,
    outcome_file: Path | None = None, sample_limit: int = 100,
    clock: datetime | None = None,
) -> dict:
    """Link horizon readiness and label-maturity without inventing results."""
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("sample_limit must be a positive integer up to 1000")
    freeze = Path(frozen_file)
    if freeze.is_symlink() or not freeze.is_file():
        raise ValueError("Frozen research file missing or symlinked")
    now = clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Audit clock must have timezone")
    cutoff = _stamp(evaluated_at)
    if cutoff > now.astimezone(timezone.utc):
        raise ValueError("Future evaluation cutoff not allowed")
    frozen = _read_frozen(freeze)
    readiness = audit_holdout_maturity(
        freeze, as_of=evaluated_at, sample_limit=100, clock=now,
    )
    market = frozen["market"]
    market_zone = TIMEZONES[market]
    horizon = frozen["horizon_days"]
    expected = {signal["security_id"]:signal for signal in frozen["signals"]}
    if len(expected) != len(frozen["signals"]):
        raise ValueError("Duplicate frozen candidate IDs")
    labels: dict[str, dict] = {}
    labels_sha: str | None = None
    comparison = None

    if outcome_file is not None:
        path = Path(outcome_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 5_000_000:
            raise ValueError("Invalid or oversized local outcome label file")
        raw = path.read_bytes()
        labels_sha = sha256(raw).hexdigest()
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Outcome labels must be a list")
        for label in data:
            if not isinstance(label, dict):
                raise ValueError("Outcome label must be an object")
            sec = label.get("security_id")
            if not isinstance(sec, str) or not sec or sec in labels:
                raise ValueError("Duplicate or invalid outcome security identity")
            labels[sec] = label
        # Reuse the existing outcome protocol's PIT and label checks. This
        # rejects altered definitions, duplicate IDs, future/orphan timestamps,
        # early negative conclusions and prematurely available labels.
        comparison = evaluate_frozen_candidates(
            freeze,path,evaluated_at=evaluated_at,clock=now,
        )

    status_counts = {status: 0 for status in REASONS}
    samples: list[dict] = []
    ready_ids = 0
    for sec, signal in sorted(expected.items()):
        registered = _stamp(signal["recorded_at_utc"])
        required_end = registered.astimezone(market_zone).date() + timedelta(days=horizon)
        expired = cutoff.astimezone(market_zone).date() >= required_end
        label = labels.get(sec)
        if label is None:
            status = "HORIZON_ELAPSED_NO_LABEL" if expired else "HORIZON_PENDING_NO_LABEL"
        else:
            mature = _stamp(label["mature_at"])
            known = _stamp(label["outcome_available_at"])
            if mature > cutoff or known > cutoff:
                status = "LABEL_NOT_YET_AVAILABLE"
            elif (label["is_future_leader"] is False and
                    mature.astimezone(market_zone).date() < required_end):
                status = "PREMATURE_NEGATIVE_LABEL"
            else:
                status = "RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"
                ready_ids += 1
        status_counts[status] += 1
        if len(samples) < sample_limit:
            samples.append({
                "security_id": sec,
                "registration_market_day":registered.astimezone(market_zone).date().isoformat(),
                "horizon_end_market_day":required_end.isoformat(),
                "status":status,
                "horizon_elapsed":expired,
                "declared_label_present":label is not None,
                "outcome_source_independently_verified":False,
                "official_leader_status":None,
            })
    unmatched_ids = sorted(set(labels)-set(expected))
    if comparison is not None:
        if (ready_ids != comparison["known_outcomes"] or
            len(expected)-ready_ids != comparison["censored_outcomes"]):
            raise ValueError("Holdout label maturity and outcome evaluator disagree")
    if sum(status_counts.values()) != len(expected):
        raise ValueError("Holdout reconciliation coverage mismatch")
    return {
        "status":STATUS,
        "market":market,
        "model_version":frozen["model_version"],
        "label_definition_id":frozen["label_definition_id"],
        "predeclared_horizon_days":horizon,
        "frozen_manifest_sha256":frozen["content_sha256"],
        "outcomes_sha256":labels_sha,
        "labels_file_provided":outcome_file is not None,
        "evaluated_at_utc":cutoff.isoformat(),
        "frozen_candidates":len(expected),
        "horizon_elapsed_count":readiness["horizon_elapsed_count"],
        "horizon_pending_count":readiness["horizon_pending_count"],
        "internally_evaluable_outcome_count":ready_ids,
        "unknown_or_censored_count":len(expected)-ready_ids,
        "unmatched_outcome_count":len(unmatched_ids),
        "unmatched_outcome_sample":unmatched_ids[:sample_limit],
        "evidence_status_counts":status_counts,
        "candidate_evidence_sample":samples,
        "research_result_summary":({
            "known_outcomes":comparison["known_outcomes"],
            "censored_outcomes":comparison["censored_outcomes"],
            "true_early_discoveries":comparison["true_early_discoveries"],
            "false_discoveries":comparison["false_discoveries"],
            "late_or_post_onset":comparison["late_or_post_onset"],
        } if comparison is not None else None),
        "independent_outcome_source_certified":False,
        "historic_pit_certified":False,
        "leader_accuracy_certified":False,
        "official_leader_promotions":0,
        "note": (
            "Even internally evaluable dated labels are only supplied research "
            "claims, never independently verified era-leader results. A due "
            "calendar window is not a positive or negative label."
        ),
    }
