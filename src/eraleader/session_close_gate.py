"""Research-only opt-in check of asserted exchange session close times."""
from __future__ import annotations
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from .corporate_returns import MARKET_ZONE

SCHEMA = "eraleader.session_close_manifest.v1"


def _aware(value):
    if not isinstance(value, str):
        raise ValueError("Clock timestamps require timezone")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid clock timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Clock timestamps require timezone")
    return stamp.astimezone(timezone.utc)


def audit_declared_session_close(bars, index_bars, clock, *, market,
                                 raw_source_id, reference_source_id,
                                 decision_at, evaluated_at):
    """Fail closed on late/missing clocks, dates and pre-close observations."""
    if market not in MARKET_ZONE:
        raise ValueError("Unknown market")
    if not isinstance(clock, dict) or clock.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported session close contract")
    if clock.get("market") != market:
        raise ValueError("Session clock market mismatch")
    source = clock.get("source_id")
    if (not isinstance(source, str) or not source.strip() or
        source in (raw_source_id, reference_source_id)):
        raise ValueError("Session clock source must have distinct declared identity")
    if not isinstance(clock.get("publisher_id_claimed"), str) or not clock["publisher_id_claimed"].strip():
        raise ValueError("Claimed clock publisher is required")
    published = _aware(clock.get("published_at"))
    retrieved = _aware(clock.get("retrieved_at"))
    if published > retrieved:
        raise ValueError("Clock publication must precede retrieval")
    if retrieved > _aware(decision_at):
        raise ValueError("Clock manifest retrieved after decision")
    if _aware(decision_at) > _aware(evaluated_at):
        raise ValueError("Evaluation before decision")
    sessions = clock.get("sessions")
    if not isinstance(sessions, list) or not isinstance(bars, list) or not isinstance(index_bars, list):
        raise ValueError("Session clock coverage requires three ordered lists")
    names = [entry.get("session") if isinstance(entry, dict) else None for entry in sessions]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate session in declared clock")
    if len(sessions) != len(bars) or len(sessions) != len(index_bars):
        raise ValueError("Session clock coverage differs from observed bars")
    if not sessions:
        raise ValueError("Empty session clock coverage")
    for bar, indexed, schedule in zip(bars, index_bars, sessions):
        if not isinstance(bar, dict) or not isinstance(indexed, dict) or not isinstance(schedule, dict):
            raise ValueError("Invalid price/index/clock record")
        day = schedule.get("session")
        try:
            parsed_day = date.fromisoformat(day)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid session clock ISO date") from exc
        if day != bar.get("session") or day != indexed.get("session"):
            raise ValueError("Session clock coverage/order mismatch")
        closed = _aware(schedule.get("close_at"))
        if closed.astimezone(MARKET_ZONE[market]).date() != parsed_day:
            raise ValueError("Declared session close must fall on market day")
        if closed > _aware(evaluated_at):
            raise ValueError("Session close after evaluation cutoff")
        for record in (bar, indexed):
            if _aware(record.get("available_at")) < closed:
                raise ValueError("Observation claimed available before declared session close")
    digest = sha256(json.dumps(clock, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "status": "DECLARED_SESSION_CLOSE_RESEARCH_ONLY",
        "market": market, "sessions_checked": len(sessions),
        "declared_clock_source_id": source, "declared_clock_sha256": digest,
        "manifest_retrieved_at_claimed": retrieved.isoformat(),
        "independent_exchange_clock_verified": False,
        "historic_pit_certified": False,
    }
