"""Longitudinal observation-gap audit for existing KR/US local cache (2_2/2_5).

Never infer an exchange delisting, legal listing, executable payout, or
PIT-certified historical universe from vendor bar presence/absence.
"""
from __future__ import annotations

from datetime import date
import pandas as pd


def audit_observation_continuity(bars: pd.DataFrame, *, market: str,
                                 as_of: date, sample_limit: int = 20) -> dict:
    if market not in ("KR", "US"):
        raise ValueError("market must be KR or US")
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError("sample_limit must be 1..100")
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValueError("Empty price observation audit input")
    required = {"security_id", "session", "is_suspended"}
    if not required.issubset(bars.columns):
        raise ValueError("Missing continuity audit columns")
    frame = bars.loc[:, ["security_id", "session", "is_suspended"]].copy()
    if frame["security_id"].isna().any() or not frame["security_id"].map(
        lambda x: isinstance(x, str) and bool(x.strip())).all():
        raise ValueError("Missing/invalid permanent security identity")
    frame["session"] = pd.to_datetime(frame["session"], errors="coerce", format="mixed")
    if frame["session"].isna().any():
        raise ValueError("Invalid session dates")
    if (frame["session"].dt.normalize() != frame["session"]).any():
        raise ValueError("Unnormalized session timestamp")
    if (frame["session"].dt.date > as_of).any():
        raise ValueError("Future market session is not permitted")
    if frame.duplicated(["security_id", "session"]).any():
        raise ValueError("Duplicate security/session observation")
    if not frame["is_suspended"].map(lambda x: type(x) is bool).all():
        # numpy.bool_ is ordinary pandas output; permit only a real bool dtype,
        # rather than free text such as "False" or an unknown null.
        if not (pd.api.types.is_bool_dtype(frame["is_suspended"])
                and not frame["is_suspended"].isna().any()):
            raise ValueError("Invalid suspension observation")
    # US legacy cache contains one observation per security per week, often
    # stamped on DIFFERENT weekdays for different tickers. Comparing exact
    # timestamps as daily sessions creates tens of thousands of fake gaps.
    # Treat every Monday--Sunday interval as one observed weekly bucket.
    period_unit = "weekly" if market == "US" else "daily"
    frame["period"] = (frame["session"].dt.to_period("W-SUN").dt.start_time
                       if market == "US" else frame["session"])
    if frame.duplicated(["security_id", "period"]).any():
        raise ValueError("Duplicate security/observation period")
    sessions = pd.DatetimeIndex(sorted(frame["period"].unique()))
    if len(sessions) < 3:
        raise ValueError("At least three observed sessions required")
    if len(frame) < 3:
        raise ValueError("Too few bars")
    # Use only observed feed sessions. A missing *whole-market* session is
    # undetectable without an independently maintained exchange calendar.
    positions = pd.Series(range(len(sessions)), index=sessions)
    frame["session_idx"] = frame["period"].map(positions).astype("int64")
    frame = frame.sort_values(["security_id", "session_idx"])
    first = frame.groupby("security_id")["session_idx"].min()
    last = frame.groupby("security_id")["session_idx"].max()
    last_idx = len(sessions) - 1
    left_censored = first[first > 0]
    right_censored = last[last < last_idx]
    # An interior gap has recorded observations on both sides. No gap is
    # synthesized for a symbol before its first or after its last bar.
    frame["previous_idx"] = frame.groupby("security_id")["session_idx"].shift(1)
    gap_rows = frame.loc[(frame["session_idx"] - frame["previous_idx"]) > 1].copy()
    gap_rows["missing_sessions"] = (
        gap_rows["session_idx"] - gap_rows["previous_idx"] - 1).astype("int64")
    samples = []
    for row in gap_rows.sort_values(
            ["missing_sessions", "security_id"], ascending=[False, True]
    ).head(sample_limit).itertuples():
        prev_idx = int(row.previous_idx)
        current_idx = int(row.session_idx)
        samples.append({
            "security_id": row.security_id,
            "last_seen_before_gap": sessions[prev_idx].date().isoformat(),
            "first_seen_after_gap": sessions[current_idx].date().isoformat(),
            "missing_observed_market_sessions": int(row.missing_sessions),
        })
    # An explicit halted/no-trade observation is *not* an absent bar.
    suspended = frame.loc[frame["is_suspended"] == True, "security_id"]
    summary = {
        "status": "LOCAL_OBSERVATION_CONTINUITY_NOT_PIT_CERTIFIED",
        "market": market,
        "as_of_requested": as_of.isoformat(),
        "observed_first_session": sessions[0].date().isoformat(),
        "observed_last_session": sessions[-1].date().isoformat(),
        "last_raw_observation": frame["session"].max().date().isoformat(),
        "observation_cadence": period_unit,
        "observed_raw_timestamp_count": int(frame["session"].nunique()),
        "observed_market_session_count": len(sessions),
        "observed_security_count": int(len(first)),
        "observation_row_count": int(len(frame)),
        "internal_gap_event_count": int(len(gap_rows)),
        "internal_missing_bar_slots": int(gap_rows["missing_sessions"].sum()),
        "securities_with_internal_gaps": int(gap_rows["security_id"].nunique()),
        "left_boundary_first_observations": int(len(left_censored)),
        "right_boundary_last_observations": int(len(right_censored)),
        "suspended_bar_observations": int(frame["is_suspended"].sum()),
        "securities_ever_suspended": int(suspended.nunique()),
        "gap_samples": samples,
        "right_boundary_samples": sorted(right_censored.index.tolist())[:sample_limit],
        "suspected_delistings_certified": False,
        "historic_universe_pit_certified": False,
        "exchange_calendar_completeness_verified": False,
        "corporate_actions_verified": False,
        "warnings": [
            "Internal missing bars may be feed gaps, ticker changes, suspensions or other events",
            "First/last observation within the window does NOT establish listing/delisting",
            "Suspended observations are retained, not counted as absent",
            "An entire absent exchange session needs an independent calendar to detect",
            "US cached WEEKLY bars are grouped by week; within-week dates may differ by ticker",
            "US current-constituent historical cache is survivor affected and NOT PIT certified",
        ],
    }
    return summary
