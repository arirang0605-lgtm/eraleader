"""Time-to-maturity inventory for sealed prospective research holdouts.

This schedules when a candidate *could* undergo full-horizon evaluation.
It NEVER infers a positive/negative future leader label or attests to
the availability, correctness or PIT legitimacy of any outcome source.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .frozen_holdout import _read_frozen, _stamp, TIMEZONES

STATUS = "LOCAL_HOLDOUT_MATURITY_SCHEDULE_NOT_PERFORMANCE_CERTIFIED"


def audit_holdout_maturity(
    frozen_file: Path, *, as_of: str, sample_limit: int = 20,
    clock: datetime | None = None,
) -> dict:
    """Compute horizon completion, WITHOUT reading outcome labels.

    A fully elapsed window is only *eligible for evidence review*, not an
    observed success, failure, or independently available mature outcome.
    """
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError("sample_limit must be an integer between 1 and 100")
    file = Path(frozen_file)
    if file.is_symlink() or not file.is_file():
        raise ValueError("Missing or symlinked frozen holdout is not trusted")
    frozen = _read_frozen(file)
    market = frozen.get("market")
    if market not in TIMEZONES:
        raise ValueError("Unknown frozen holdout exchange")
    zone = TIMEZONES[market]
    evaluated = _stamp(as_of)
    now = clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current audit clock must have timezone")
    if evaluated > now.astimezone(timezone.utc):
        raise ValueError("Future as-of cannot be presented as current readiness")
    frozen_at = _stamp(frozen.get("frozen_at_utc"))
    if evaluated < frozen_at:
        raise ValueError("Cannot audit candidate maturity before holdout freeze")
    horizon = frozen.get("horizon_days")
    if type(horizon) is not int or not 1 <= horizon <= 1095:
        raise ValueError("Invalid pre-registered holdout horizon")
    if frozen.get("outcome_labels_included") is not False or (
            frozen.get("historic_pit_certified") is not False):
        raise ValueError("Frozen holdout contains non-research certification")
    signals = frozen.get("signals")
    if not isinstance(signals, list) or len(signals) != frozen.get("eligible_count"):
        raise ValueError("Frozen holdout candidate inventory inconsistent")

    current_market_day = evaluated.astimezone(zone).date()
    complete = pending = 0
    due = []
    first_ids = set()
    registrations = []
    for signal in signals:
        if not isinstance(signal, dict):
            raise ValueError("Malformed frozen candidate")
        sec = signal.get("security_id")
        if not isinstance(sec, str) or not sec or sec in first_ids:
            raise ValueError("Duplicate or missing frozen permanent security ID")
        if signal.get("model_version") != frozen.get("model_version"):
            raise ValueError("Frozen candidate model differs from sealed protocol")
        recorded = _stamp(signal.get("recorded_at_utc"))
        observed = _stamp(signal.get("observed_as_of"))
        if recorded > frozen_at or observed > recorded:
            raise ValueError("Frozen registration chronology mismatch")
        if (recorded.astimezone(zone).date() - observed.astimezone(zone).date()).days > (
                frozen["max_observation_lag_days"]):
            raise ValueError("Frozen historical backfill cannot be claimed prospective")
        first_ids.add(sec)
        registration_day = recorded.astimezone(zone).date()
        eligibility_day = registration_day + timedelta(days=horizon)
        days_remaining = max((eligibility_day - current_market_day).days, 0)
        elapsed = days_remaining == 0
        if elapsed:
            complete += 1
        else:
            pending += 1
        registrations.append({
            "security_id": sec,
            "registration_market_day": registration_day.isoformat(),
            "horizon_end_market_day": eligibility_day.isoformat(),
            "days_until_horizon_end": days_remaining,
            "full_horizon_elapsed": elapsed,
            "outcome_source_independently_verified": False,
            "leader_outcome_known": False,
        })
    registrations.sort(key=lambda x: (x["horizon_end_market_day"],x["security_id"]))
    due = registrations[:sample_limit]
    return {
        "status": STATUS, "market": market,
        "model_version": frozen["model_version"],
        "label_definition_id": frozen["label_definition_id"],
        "frozen_manifest_sha256": frozen["content_sha256"],
        "frozen_at_utc": frozen["frozen_at_utc"],
        "as_of_utc": evaluated.isoformat(),
        "market_as_of_day": current_market_day.isoformat(),
        "predeclared_horizon_days": horizon,
        "eligible_frozen_candidates": len(signals),
        "horizon_elapsed_count": complete,
        "horizon_pending_count": pending,
        "excluded_historical_backfills_at_freeze":
            frozen["excluded_historical_backfills"],
        "maturity_schedule_sample": due,
        "maturity_sample_limit": sample_limit,
        "actual_known_outcomes": 0,
        "positive_leader_labels_inferred": 0,
        "negative_leader_labels_inferred": 0,
        "official_leader_promotions": 0,
        "external_outcome_evidence_verified": False,
        "historic_pit_certified": False,
        "clock_independently_attested": False,
        "warning": (
            "Horizon elapsed means only that a full window has passed since "
            "the locally recorded candidate. It is NOT a matured available "
            "label, leader success/failure, real prediction validation or "
            "independent historical source/clock attestation."
        ),
    }
