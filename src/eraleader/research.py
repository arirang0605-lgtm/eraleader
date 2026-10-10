"""Join price and industry/earnings on the SAME decision snapshot.

This is descriptive until independent evidence proves PIT completeness.
No model promotions from synthetic or incomplete historical coverage.
"""
from __future__ import annotations
from datetime import datetime, date
from hashlib import sha256
import json

from .offline_features import financial_snapshot
from .states import evaluate_leader_state

RESEARCH_VERSION="era-offline-join-0.1"

def integrated_snapshot(offline: dict, price: dict | None, decision_at: str) -> dict:
    """PIT-clamped explanatory output with per-factor missingness.

    Price input is an independently timestamped run from the same market.
    Ticker join is observational, not certified permanent security identity.
    """
    moment=datetime.fromisoformat(decision_at.replace("Z","+00:00"))
    if moment.tzinfo is None:
        raise ValueError("decision_at requires timezone")
    asof=moment.date()
    if moment.astimezone(__import__("datetime").timezone.utc).isoformat()!=offline["as_of"]:
        raise ValueError("Offline PIT cutoff does not match decision_at")
    market=offline["market"]
    if price is not None:
        if price["source_market"]!=market:
            raise ValueError("Cross-market data join forbidden")
        requested=date.fromisoformat(price["as_of_requested"])
        observed=date.fromisoformat(price["market_last_observation"])
        if requested!=asof or observed>requested:
            raise ValueError("Price screen decision date does not match offline PIT time")
        if (asof-observed).days>10:
            raise ValueError("Price data too stale to join; research blocked")
        unique_ids=set()
        for bar in price.get("rows",[]):
            row_day=date.fromisoformat(bar["observed_at"])
            if row_day>observed or row_day>asof:
                raise ValueError("Future price row found inside stale screen header")
            if bar["security_id"] in unique_ids:
                raise ValueError("Duplicate price observation securities")
            unique_ids.add(bar["security_id"])
    fundamentals=financial_snapshot(offline)
    price_rows={r["security_id"]:r for r in (price or {}).get("rows",[])}
    result=[]
    for c in fundamentals["companies"]:
        p=price_rows.get(c["ticker"])
        # This ticker join is an observable lookup only. Corporate actions,
        # delisting, price adjustment and permanent identity require proof.
        flags=list(c["quality_flags"])
        if p is None:
            flags.append("NO_PRICE_OBSERVATION_ASOF")
        else:
            flags.append("TICKER_JOIN_IDENTITY_UNVERIFIED")
        missing_factors=["industry_score","competitive_score","earnings_score","flow_score"]
        if p is None:missing_factors.append("price_momentum")
        quality=offline["quality"]
        verified=(quality.get("financial_pit_complete_verified") is True and
                  quality.get("historic_membership_pit_verified") is True and
                  quality.get("corporate_actions_complete_verified") is True and
                  "synthetic_fixture" not in quality.get("provenances",[]))
        # Do not pass a fabricated 0 or inferred fraction as a full 100pt score.
        components={"industry":None,"competitiveness":None,
                    "earnings":None,"momentum":None,"flow":None}
        gates={"financial_pit":verified,"historic_universe_pit":verified,
               "corporate_actions_pit":verified,
               "fundamental_growth":bool(c["screen_hit_heuristic"]),
               "confirmed_weekly_trend":False}
        state=evaluate_leader_state(components,gates)
        result.append({
          "security_id":c["security_id"],"ticker":c["ticker"],
          "market":market,"industry_id":c["industry_id"],
          "as_of":decision_at,"state":state["state"],
          "state_reason":state["reason"],
          "research_growth_screen_hit":bool(c["screen_hit_heuristic"]),
          "research_screen_evaluated":c["screen_evaluated"],
          "financial_period_age_days":c["financial_period_age_days"],
          "revenue_yoy":c["revenue_yoy"],
          "revenue_yoy_acceleration":c["revenue_yoy_acceleration"],
          "operating_income_yoy":c["operating_income_yoy"],
          "industry_revenue_yoy":c["industry_revenue_yoy"],
          "momentum_6m":p.get("return_6m") if p else None,
          "price_observed_at":p["observed_at"] if p else None,
          "missing_factors":missing_factors,"quality_flags":flags,
          "full_score":None,"verified_future_leader_candidate":False
        })
    run_payload={"version":RESEARCH_VERSION,"as_of":decision_at,
                 "market":market,"company_rows":result,
                 "price_run_id":price.get("run_id") if price else None,
                 "offline_provenance":offline["quality"]["provenances"]}
    signature=sha256(json.dumps(run_payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    return {
      **run_payload,"run_id":signature,
      "company_count":len(result),
      "research_growth_screen_count":sum(x["research_growth_screen_hit"] for x in result),
      "research_screen_deferred_count":sum(not x["research_screen_evaluated"] for x in result),
      "confirmed_leaders":0,"potential_leaders":0,
      "pit_certified":False,
      "limitation":"Supplier universe/financial/adjustment completeness not verified. No leader promotion.",
      "quality":offline["quality"]
    }
