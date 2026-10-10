"""Observed-symbol continuity audit on local daily market cache.

Observations are NOT official point-in-time listing/delisting registries.
They are a useful discrepancy detector before any survivor-free backtest.
"""
from __future__ import annotations
from datetime import date
import pandas as pd

def audit_observed_universe(bars: pd.DataFrame, as_of: date) -> dict:
    required={"security_id","session","close","is_suspended"}
    if not required.issubset(set(bars.columns)):
        raise ValueError("Missing market bars audit columns")
    if bars.empty:
        raise ValueError("No market bars for universe audit")
    frame=bars.copy()
    frame["session"]=pd.to_datetime(frame["session"])
    if frame["session"].isna().any() or frame["security_id"].isna().any():
        raise ValueError("Missing security/date in audit")
    if (frame["session"].dt.date>as_of).any():
        raise ValueError("Future market bars not permitted in audit")
    if frame.duplicated(["security_id","session"]).any():
        raise ValueError("Duplicate symbol/session observations")
    sessions=sorted(frame["session"].unique())
    if len(sessions)<2:
        raise ValueError("Need two observed market sessions")
    previous,current=sessions[-2:]
    prior=frame.loc[frame["session"]==previous]
    recent=frame.loc[frame["session"]==current]
    a=set(prior["security_id"])
    b=set(recent["security_id"])
    appeared=sorted(b-a)
    disappeared=sorted(a-b)
    halted=sorted(set(recent.loc[recent["is_suspended"],"security_id"]))
    stale=max(0,(as_of-pd.Timestamp(current).date()).days)
    return {
        "status":"OBSERVED_DAILY_UNIVERSE_AUDIT_NOT_CERTIFIED",
        "requested_as_of":as_of.isoformat(),
        "prior_observation":pd.Timestamp(previous).date().isoformat(),
        "last_observation":pd.Timestamp(current).date().isoformat(),
        "observation_staleness_calendar_days":stale,
        "observed_symbols_prior":len(a),
        "observed_symbols_current":len(b),
        "appeared":appeared,"disappeared":disappeared,
        "halted_or_no_trade":halted,
        "appeared_count":len(appeared),"disappeared_count":len(disappeared),
        "halted_count":len(halted),
        "historic_membership_certified":False,
        "delisting_events_certified":False,
        "corporate_actions_certified":False,
        "warnings":[
            "Disappearance from price observations is NOT proof of delisting",
            "Missing bars may be vendor gaps, trading suspension, merger or ticker migration",
            "Use exchange listing/delisting and corporate action PIT records to certify coverage",
        ],
    }
