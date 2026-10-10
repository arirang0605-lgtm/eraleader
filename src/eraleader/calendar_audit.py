"""Offline exchange-session reference vs existing KR daily / US weekly price observations.

A user-supplied exchange calendar is an *assertion*, not independent PIT
evidence. This module audits missing whole-market observed periods without
inventing official delistings, closures, or external data.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

MARKET_ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
SCHEMA = "eraleader.exchange_calendar_reference.v1"


def _aware(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timezone-aware source timestamp is required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid source timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Timezone-aware source timestamp is required")
    return stamp.astimezone(timezone.utc)


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("Calendar session must be ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid calendar ISO session date") from exc


def _dates(values: object, label: str, limit: int = 10000) -> list[date]:
    if not isinstance(values, list) or not len(values) <= limit:
        raise ValueError(f"Invalid {label} session list")
    result = [_date(x) for x in values]
    if len(result) != len(set(result)):
        raise ValueError(f"Duplicate {label} session date")
    if result != sorted(result):
        raise ValueError(f"Unsorted {label} session dates")
    return result


def audit_exchange_calendar(calendar_file: Path, bars: pd.DataFrame, *,
                            market: str, as_of: date, sample_limit: int = 20) -> dict:
    """Compare *within price-feed first and last observations* only.

    US vendor weekly bars carry differing weekday stamps. A week is expected
    when >=1 claimed exchange open session exists within that week.
    """
    if market not in MARKET_ZONES:
        raise ValueError("Market must be KR or US")
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError("Invalid sample limit")
    file = Path(calendar_file)
    raw = file.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("Oversized calendar reference")
    calendar = json.loads(raw)
    if not isinstance(calendar, dict) or calendar.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported exchange calendar reference schema")
    if calendar.get("market") != market:
        raise ValueError("Exchange calendar market mismatch")
    for key in ("source_id", "publisher_id_claimed"):
        if not isinstance(calendar.get(key), str) or not calendar[key].strip():
            raise ValueError(f"Missing calendar {key}")
    if type(calendar.get("asserted_complete")) is not bool:
        raise ValueError("Calendar completeness claim must be boolean")
    retrieved = _aware(calendar.get("retrieved_at"))
    start = _date(calendar.get("coverage_start"))
    end = _date(calendar.get("coverage_end"))
    if start > end or end > as_of:
        raise ValueError("Calendar coverage must be ordered and no later than cutoff")
    expected = _dates(calendar.get("trading_sessions"), "trading")
    closed = _dates(calendar.get("closed_sessions", []), "closed")
    if not expected:
        raise ValueError("No declared trading sessions")
    if set(expected) & set(closed):
        raise ValueError("Calendar date cannot be both open and closed")
    if any(x < start or x > end for x in expected + closed):
        raise ValueError("Calendar session outside declared coverage")

    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValueError("No observed price bars")
    if not {"security_id", "session"}.issubset(bars.columns):
        raise ValueError("Price security/session columns required")
    frame = bars[["security_id", "session"]].copy()
    if frame["security_id"].isna().any() or not frame["security_id"].map(
            lambda s: isinstance(s, str) and bool(s.strip())).all():
        raise ValueError("Invalid price security identity")
    frame["session"] = pd.to_datetime(frame["session"], errors="coerce", format="mixed")
    if frame["session"].isna().any() or (frame["session"].dt.normalize() != frame["session"]).any():
        raise ValueError("Invalid market observation session")
    if (frame["session"].dt.date > as_of).any():
        raise ValueError("Future price session")
    if frame.duplicated(["security_id", "session"]).any():
        raise ValueError("Duplicate security/session")
    observed_first = frame["session"].min().date()
    observed_last = frame["session"].max().date()
    if start > observed_first or end < observed_last:
        raise ValueError("Calendar does not cover entire observed market window")

    def bucket(day: date) -> date:
        if market == "KR":
            return day
        return date.fromordinal(day.toordinal() - day.weekday())

    # Never compare US individual ticker weekdays as if they were daily bars.
    observed = {bucket(x) for x in frame["session"].dt.date}
    first_bucket, last_bucket = bucket(observed_first), bucket(observed_last)
    asserted = {bucket(x) for x in expected if first_bucket <= bucket(x) <= last_bucket}
    missing = sorted(asserted - observed)
    unexpected = sorted(observed - asserted)
    # For US the final week may be partially covered. We compare only weeks
    # intersecting the feed's actual observed envelope, not later weeks.
    retrospective = retrieved > datetime.combine(as_of, datetime.max.time(),
                            tzinfo=MARKET_ZONES[market]).astimezone(timezone.utc)
    return {
        "status": "LOCAL_CALENDAR_COMPARISON_NOT_PIT_CERTIFIED",
        "market": market,
        "observation_cadence": "daily" if market == "KR" else "weekly",
        "cutoff": as_of.isoformat(),
        "first_price_observation": observed_first.isoformat(),
        "last_price_observation": observed_last.isoformat(),
        "reference_source_id_claimed": calendar["source_id"],
        "publisher_id_claimed": calendar["publisher_id_claimed"],
        "calendar_file_sha256": sha256(raw).hexdigest(),
        "calendar_retrieved_at_claimed": retrieved.isoformat(),
        "calendar_retrospectively_retrieved": retrospective,
        "calendar_complete_claimed": calendar["asserted_complete"],
        "calendar_independently_attested": False,
        "calendar_pit_certified": False,
        "historic_universe_pit_certified": False,
        "observed_periods": len(observed),
        "reference_expected_periods": len(asserted),
        "reference_only_missing_market_periods": len(missing),
        "feed_only_unexpected_periods": len(unexpected),
        "missing_period_samples": [x.isoformat() for x in missing[:sample_limit]],
        "unexpected_period_samples": [x.isoformat() for x in unexpected[:sample_limit]],
        "verified_delisting_count": None,
        "warning": ("Calendar is user-declared. Matching dates do NOT prove market-wide "
                    "completeness or an authentic historical calendar. "
                    "US timestamps may be vendor week labels, not actual trading days."),
    }


def load_calendar_manifest(path: Path) -> dict:
    """Load, but never authenticate, a locally declared exchange calendar."""
    raw=Path(path).read_bytes()
    if len(raw)>2_000_000:
        raise ValueError("Oversized calendar manifest")
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("schema_version")!=SCHEMA:
        raise ValueError("Unsupported exchange calendar reference schema")
    return obj


def compare_calendar_periods(calendar_manifest: dict, *, market: str,
                             as_of: date, observed_period_dates: list[date],
                             raw_observation_dates: list[date],
                             price_source: str | None = None,
                             sample_limit: int = 20) -> dict:
    """Compatibility with continuity_audit's optional exchange calendar slot.

    These dates are already aligned to KR daily or US Monday weekly buckets.
    No source is independently certified by this in-memory comparison.
    """
    if market not in MARKET_ZONES:
        raise ValueError("Market must be KR or US")
    if type(sample_limit) is not int or not 1<=sample_limit<=100:
        raise ValueError("Invalid sample limit")
    c=calendar_manifest
    if not isinstance(c,dict) or c.get("schema_version")!=SCHEMA or c.get("market")!=market:
        raise ValueError("Calendar manifest version/market mismatch")
    if type(c.get("asserted_complete")) is not bool:
        raise ValueError("Calendar completeness must be boolean")
    if any(not isinstance(c.get(k),str) or not c[k].strip()
           for k in ("source_id","publisher_id_claimed")):
        raise ValueError("Missing declared calendar source identity")
    retrieved=_aware(c.get("retrieved_at"))
    start,end=_date(c.get("coverage_start")),_date(c.get("coverage_end"))
    if start>end or end>as_of:
        raise ValueError("Invalid calendar coverage versus decision")
    opened=_dates(c.get("trading_sessions"),"trading")
    closed=_dates(c.get("closed_sessions",[]),"closed")
    if not opened or set(opened)&set(closed):
        raise ValueError("Calendar open/closed session contradiction")
    if any(not start<=day<=end for day in opened+closed):
        raise ValueError("Calendar session outside coverage")
    if not raw_observation_dates or not observed_period_dates:
        raise ValueError("Missing observed price sessions")
    lo,hi=min(raw_observation_dates),max(raw_observation_dates)
    if start>lo or end<hi or hi>as_of:
        raise ValueError("Calendar coverage does not include entire observed window")
    def period(day: date) -> date:
        return day if market=="KR" else date.fromordinal(day.toordinal()-day.weekday())
    expected={period(day) for day in opened if period(lo)<=period(day)<=period(hi)}
    observed=set(observed_period_dates)
    if any(not isinstance(x,date) for x in observed) or any(period(x)!=x for x in observed):
        raise ValueError("Invalid pre-aligned observed calendar period")
    missing=sorted(expected-observed)
    extra=sorted(observed-expected)
    retrospective=retrieved>datetime.combine(as_of,datetime.max.time(),
                              tzinfo=MARKET_ZONES[market]).astimezone(timezone.utc)
    return {
        "status":"LOCAL_CALENDAR_COMPARISON_NOT_PIT_CERTIFIED",
        "whole_market_missing_period_count":len(missing),
        "whole_market_missing_period_samples":[x.isoformat() for x in missing[:sample_limit]],
        "feed_only_unexpected_period_count":len(extra),
        "feed_only_unexpected_period_samples":[x.isoformat() for x in extra[:sample_limit]],
        "observed_period_count":len(observed),
        "reference_expected_period_count":len(expected),
        "reference_source_id_claimed":c["source_id"],
        "reference_publisher_claimed":c["publisher_id_claimed"],
        "reference_retrieved_retrospectively":retrospective,
        "reference_completeness_claimed":c["asserted_complete"],
        "cached_price_source":price_source,
        "calendar_independently_attested":False,
        "calendar_pit_certified":False,
        "historic_universe_pit_certified":False,
    }
