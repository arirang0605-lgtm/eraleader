"""Source coverage reconciliation between PIT membership and cached observations.

Never turns a price-feed observation into official listing membership, or
certifies an imported ledger solely because it matches a price feed.
"""
from __future__ import annotations
from datetime import date
import pandas as pd

def reconcile_membership_to_prices(snapshot: dict, bars: pd.DataFrame, *, as_of: date) -> dict:
    if snapshot.get("market") not in ("KR", "US"):
        raise ValueError("PIT snapshot requires KR/US market")
    if snapshot.get("trading_day") != as_of.isoformat():
        raise ValueError("PIT snapshot trading day does not match price audit cutoff")
    members = snapshot.get("members")
    if not isinstance(members, dict):
        raise ValueError("Missing PIT membership snapshot")
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        raise ValueError("No observed price bars to reconcile")
    for key in ("security_id", "session", "is_suspended"):
        if key not in bars.columns:
            raise ValueError(f"Missing bar field {key}")
    sessions = pd.to_datetime(bars["session"], errors="coerce")
    if sessions.isna().any() or (sessions.dt.date > as_of).any():
        raise ValueError("Future or invalid price sessions in PIT audit")
    if bars.duplicated(["security_id","session"]).any():
        raise ValueError("Duplicated price observations")
    current = bars.loc[sessions == sessions.max()]
    observed = set(current["security_id"].astype(str))
    expected = set(members)
    overlap = observed & expected
    inactive = set(snapshot.get("exit_security_ids", []))
    if expected & inactive:
        raise ValueError("PIT membership includes known exited identities")
    suspended = set(current.loc[current["is_suspended"] == True, "security_id"].astype(str))
    if any(not sec for sec in expected | observed):
        raise ValueError("Empty security identity")
    quality = snapshot.get("quality", {})
    is_certified = False
    return {
        "status": "PIT_MEMBERSHIP_OBSERVATION_AUDIT_NOT_CERTIFIED",
        "market": snapshot["market"],
        "requested_as_of": as_of.isoformat(),
        "last_price_observation": sessions.max().date().isoformat(),
        "pit_member_count": len(expected),
        "observed_price_security_count": len(observed),
        "matching_count": len(overlap),
        "member_without_price_count": len(expected - observed),
        "price_without_member_count": len(observed - expected),
        "observed_suspended_count": len(suspended),
        "observed_exited_count": len(observed & inactive),
        "member_price_overlap_fraction": round(len(overlap)/len(expected), 6) if expected else None,
        "observation_membership_fraction": round(len(overlap)/len(observed), 6) if observed else None,
        "members_missing_from_feed_sample": sorted(expected - observed)[:25],
        "unmatched_price_id_sample": sorted(observed - expected)[:25],
        "exited_but_observed_sample": sorted(observed & inactive)[:25],
        "synthetic_or_uncertified_input": (
            "synthetic_fixture" in quality.get("provenances", [])
            or quality.get("historic_membership_pit_verified") is not True
        ),
        "historic_membership_pit_certified": is_certified,
        "price_availability_pit_certified": False,
        "corporate_actions_pit_certified": False,
        "warnings": [
            "Price feed observation != official active-listing registry",
            "Coverage may differ due to vendor exchange scope, trading halts, or listing timing",
            "Observed exited identities are audit exceptions, not inferred payouts",
            "Security identity/corporate-action source provenance requires independent verification",
        ],
    }
