"""Opt-in local corroboration of a declared close clock against a separate calendar.

Both are user-supplied assertions, never independently authenticated market data.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json

from .calendar_audit import SCHEMA as CALENDAR_SCHEMA
from .corporate_returns import MARKET_ZONE
from .session_close_gate import _aware


def _day(value):
    if not isinstance(value, str):
        raise ValueError("Calendar dates must be ISO strings")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid calendar ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical calendar ISO date")
    return parsed


def _unique_days(values, label):
    if not isinstance(values, list) or len(values) > 10000:
        raise ValueError(f"Invalid {label} sessions")
    parsed = [_day(value) for value in values]
    if parsed != sorted(set(parsed)):
        raise ValueError(f"Unsorted or duplicate {label} sessions")
    return parsed


def corroborate_declared_closes(clock, calendar, *, market, decision_at,
                                raw_source_id, reference_source_id):
    """Require full local session and close-time agreement before publishing results.

    The independent *file identity* here is NOT independent exchange attestation.
    """
    if market not in MARKET_ZONE:
        raise ValueError("Unknown market")
    if not isinstance(clock, dict) or not isinstance(calendar, dict):
        raise ValueError("Clock and calendar JSON objects required")
    if calendar.get("schema_version") != CALENDAR_SCHEMA or calendar.get("market") != market:
        raise ValueError("Calendar schema/market mismatch")
    source = calendar.get("source_id")
    if (not isinstance(source, str) or not source.strip() or
            source in (clock.get("source_id"), raw_source_id, reference_source_id)):
        raise ValueError("Calendar must claim a distinct source identity")
    if not isinstance(calendar.get("publisher_id_claimed"), str) or not calendar["publisher_id_claimed"].strip():
        raise ValueError("Calendar publisher claim required")
    if calendar.get("asserted_complete") is not True:
        raise ValueError("Complete calendar coverage must be explicitly claimed")
    if _aware(calendar.get("retrieved_at")) > _aware(decision_at):
        raise ValueError("Calendar retrieved after decision cutoff")
    start, end = _day(calendar.get("coverage_start")), _day(calendar.get("coverage_end"))
    if start > end:
        raise ValueError("Invalid calendar coverage range")
    opens = _unique_days(calendar.get("trading_sessions"), "trading")
    closes = _unique_days(calendar.get("closed_sessions", []), "closed")
    if not opens or set(opens) & set(closes):
        raise ValueError("Calendar open/closed sessions conflict")
    if any(not start <= day <= end for day in opens + closes):
        raise ValueError("Calendar sessions outside declared coverage")
    scheduled = calendar.get("trading_session_closes")
    if not isinstance(scheduled, dict) or set(scheduled) != {x.isoformat() for x in opens}:
        raise ValueError("Trading session close map must cover every open session")
    for key, stamp in scheduled.items():
        if _aware(stamp).astimezone(MARKET_ZONE[market]).date() != _day(key):
            raise ValueError("Calendar close belongs to wrong exchange-local session")

    sessions = clock.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Clock sessions required")
    observed = []
    for entry in sessions:
        if not isinstance(entry, dict):
            raise ValueError("Invalid clock session entry")
        day = _day(entry.get("session"))
        if day < start or day > end or day not in opens:
            raise ValueError("Clock session absent from declared trading calendar")
        if _aware(entry.get("close_at")) != _aware(scheduled[day.isoformat()]):
            raise ValueError("Clock and calendar session close disagreement")
        observed.append(day)
    if observed != sorted(set(observed)):
        raise ValueError("Clock sessions must be strictly ordered")
    expected = [day for day in opens if observed[0] <= day <= observed[-1]]
    if observed != expected:
        raise ValueError("Missing open exchange session in return-index series")
    digest = sha256(json.dumps(calendar, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "status": "DUAL_DECLARED_CALENDAR_CORROBORATION_RESEARCH_ONLY",
        "market": market, "matched_sessions": len(observed),
        "calendar_source_id_claimed": source, "calendar_manifest_sha256": digest,
        "calendar_retrieved_at_claimed": _aware(calendar["retrieved_at"]).isoformat(),
        "independent_calendar_verified": False, "historic_pit_certified": False,
    }
