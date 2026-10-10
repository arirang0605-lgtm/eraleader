"""Offline point-in-time issuer identity and corporate-event linkage audit.

A vendor ticker, publisher ID, or claimed retrieval vintage is never
considered official proof of a permanent security identity.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json

SCHEMA = "eraleader.issuer_lineage_research.v1"
ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
EVENTS = {"ticker_change", "merger", "delist", "cash_delist", "split", "dividend"}


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timezone-aware source timestamp required")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid source timestamp") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Timezone-aware source timestamp required")
    return t.astimezone(timezone.utc)


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("ISO calendar day required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid identity field {key}")
    return value


def _in_interval(row: dict, day: date) -> bool:
    start = _date(row["valid_from"])
    end = _date(row["valid_to"]) if row.get("valid_to") else None
    return start <= day and (end is None or day < end)


def audit_issuer_lineage(registry_file: Path, *, decision_at: str,
                         sample_limit: int = 20) -> dict:
    """Compare as-of issuer identities, ticker reuse and corporate event links.

    Retrospectively retrieved reference files contribute ZERO historical
    eligible members even when their content declares early availability.
    """
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError("sample_limit must be between 1 and 100")
    cutoff = _timestamp(decision_at)
    source = Path(registry_file)
    raw = source.read_bytes()
    if len(raw) > 5_000_000:
        raise ValueError("Oversized issuer lineage registry")
    bundle = json.loads(raw)
    if not isinstance(bundle, dict) or bundle.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported issuer lineage schema")
    market = bundle.get("market")
    if market not in ZONES:
        raise ValueError("KR or US market required")
    day = cutoff.astimezone(ZONES[market]).date()
    source_id = _text(bundle, "source_id")
    publisher = _text(bundle, "publisher_id_claimed")
    retrieved = _timestamp(bundle.get("retrieved_at"))
    historical_retrieval = retrieved <= cutoff
    identities = bundle.get("identities")
    events = bundle.get("events")
    if not isinstance(identities, list) or not 1 <= len(identities) <= 50000:
        raise ValueError("Nonempty identity rows required")
    if not isinstance(events, list) or len(events) > 50000:
        raise ValueError("Event list required")
    references = {}
    versions = defaultdict(list)
    permanent_ids = set()
    for row in identities:
        if not isinstance(row, dict):
            raise ValueError("Identity record must be an object")
        record_id = _text(row, "record_id")
        sec = _text(row, "security_id")
        _text(row, "ticker")
        if row.get("market") != market or row.get("source_id") != source_id:
            raise ValueError("Cross-market or cross-source identity")
        revised = row.get("revision")
        if type(revised) is not int or revised < 1:
            raise ValueError("Identity revision must be positive integer")
        effective = _date(row.get("valid_from"))
        closing = _date(row["valid_to"]) if row.get("valid_to") else None
        if closing is not None and closing <= effective:
            raise ValueError("Identity valid_to must be after valid_from")
        known = _timestamp(row.get("known_at"))
        if known > retrieved:
            raise ValueError("Identity revision known after declared retrieval")
        owner = references.get(record_id)
        if owner is not None and owner != (sec, effective):
            raise ValueError("Logical identity record switched permanent security")
        references[record_id] = (sec, effective)
        versions[record_id].append((revised, known, row))
        permanent_ids.add(sec)
    visible = []
    future_revision_count = 0
    for records in versions.values():
        ordered = sorted(records, key=lambda item: item[0])
        if len({item[0] for item in ordered}) != len(ordered):
            raise ValueError("Duplicate identity revision")
        if any(later[1] < earlier[1] for earlier, later in zip(ordered, ordered[1:])):
            raise ValueError("Identity revision publication chronology reversed")
        eligible = [v for v in ordered if v[1] <= cutoff]
        future_revision_count += len(ordered) - len(eligible)
        if eligible and historical_retrieval:
            visible.append(eligible[-1][2])
    active = [row for row in visible if _in_interval(row, day)]
    active_by_ticker = defaultdict(set)
    for row in active:
        active_by_ticker[row["ticker"]].add(row["security_id"])
    collisions = sorted(t for t, secs in active_by_ticker.items() if len(secs) > 1)
    ticker_all = defaultdict(set)
    for row in visible:
        if _date(row["valid_from"]) <= day:
            ticker_all[row["ticker"]].add(row["security_id"])
    reuses = sorted(t for t, secs in ticker_all.items() if len(secs) > 1)

    missing_parent = set()
    missing_successor = set()
    unknown_settlement = set()
    asof_event_count = 0
    event_keys = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Corporate event must be an object")
        event_id = _text(event, "event_id")
        sec = _text(event, "security_id")
        typ = event.get("action_type")
        if typ not in EVENTS:
            raise ValueError("Unsupported corporate event kind")
        if event.get("source_id") != source_id:
            raise ValueError("Corporate event source mismatch")
        if event_id in event_keys:
            raise ValueError("Duplicate corporate event")
        event_keys.add(event_id)
        _date(event.get("effective_on"))
        known = _timestamp(event.get("known_at"))
        if known > retrieved:
            raise ValueError("Corporate event known after source retrieval")
        if known > cutoff or not historical_retrieval:
            continue
        asof_event_count += 1
        if sec not in permanent_ids:
            missing_parent.add(event_id)
        successor = event.get("successor_security_id")
        if typ in ("merger", "ticker_change") and successor is not None:
            if not isinstance(successor, str) or not successor:
                raise ValueError("Invalid successor identity")
            if successor not in permanent_ids:
                missing_successor.add(event_id)
        if typ in ("cash_delist", "delist"):
            unknown_settlement.add(event_id)

    observations = bundle.get("observed_tickers", [])
    if not isinstance(observations, list) or len(observations) > 50000:
        raise ValueError("Observed ticker sample must be an array")
    if any(not isinstance(s, str) or not s.strip() for s in observations):
        raise ValueError("Invalid observed ticker")
    if len(set(observations)) != len(observations):
        raise ValueError("Duplicate observed ticker")
    absent = sorted(t for t in observations if t not in active_by_ticker)
    ambiguous = sorted(t for t in observations if len(active_by_ticker[t]) > 1)
    state = ("RESEARCH_RETROSPECTIVE_IDENTITY_NOT_PIT" if not historical_retrieval
             else "RESEARCH_ISSUER_IDENTITY_AUDIT_NOT_CERTIFIED")
    return {
        "status": state, "market": market, "decision_at": cutoff.isoformat(),
        "registry_sha256": sha256(raw).hexdigest(),
        "declared_source_id": source_id, "publisher_id_claimed": publisher,
        "declared_retrieved_at": retrieved.isoformat(),
        "retrospective_retrieval": not historical_retrieval,
        "identity_row_count": len(identities), "identity_record_count": len(versions),
        "identity_revision_after_decision_count": future_revision_count,
        "independently_usable_asof_identity_count": 0,
        "claimed_asof_active_identity_count": len(active),
        "claimed_distinct_active_permanent_ids": len({r["security_id"] for r in active}),
        "active_ticker_conflict_count": len(collisions),
        "active_ticker_conflict_sample": collisions[:sample_limit],
        "declared_historical_ticker_reuse_count": len(reuses),
        "declared_historical_reuse_sample": reuses[:sample_limit],
        "asof_known_event_count_claimed": asof_event_count,
        "corporate_events_with_unknown_parent_count": len(missing_parent),
        "corporate_events_with_missing_successor_count": len(missing_successor),
        "cash_exit_events_without_verified_proceeds_count": len(unknown_settlement),
        "observed_ticker_count": len(observations),
        "observed_tickers_unmatched_count": len(absent),
        "observed_tickers_ambiguous_count": len(ambiguous),
        "observed_tickers_unmatched_sample": absent[:sample_limit],
        "observed_tickers_ambiguous_sample": ambiguous[:sample_limit],
        "historic_membership_pit_certified": False,
        "permanent_identity_independently_verified": False,
        "corporate_action_completeness_verified": False,
        "delisting_settlement_verified": False,
        "warnings": [
            "Source and retrieval timestamps are supplier assertions, not independent PIT proof",
            "Ticker may be reused by different legal issuers; no automatic security ID join",
            "Corporate events missing successors or cash proceeds remain unresolved",
            "A matching ticker cannot certify a survivor-free listed universe",
        ],
    }
