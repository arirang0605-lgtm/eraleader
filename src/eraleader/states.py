"""Validated-evidence leader transitions, usable with future PIT fundamentals.

Price-only cache never satisfies the required evidence gates. This module
is tested with synthetic fixtures, not yet connected to a live feed.
"""
from __future__ import annotations

SCORE_MAX={"industry":20,"competitiveness":20,"earnings":25,"momentum":25,"flow":10}
PRIMARY={"WATCH","POTENTIAL","CONFIRMED","WEAKENING","PAUSED","EXITED"}

def evaluate_leader_state(
    components: dict[str,float|None], evidence: dict[str,bool],
    *, previous: str="WATCH", continuous_confirmations: int=1
) -> dict:
    if previous not in PRIMARY:
        raise ValueError("Unknown prior state")
    if previous=="EXITED":
        return {"state":"EXITED","total":None,"reason":"historical delisting/exit"}
    if evidence.get("suspended") or evidence.get("data_quality_failed"):
        return {"state":"PAUSED","total":None,"reason":"Missing or paused market data"}
    missing=[key for key in SCORE_MAX if components.get(key) is None]
    # If any vital evidence is absent: no official candidates/promotions.
    pit_ok=all(evidence.get(k,False) for k in (
        "financial_pit","historic_universe_pit","corporate_actions_pit"))
    if missing or not pit_ok:
        return {"state":"WATCH","total":None,
                "reason":"Unverified or incomplete PIT evidence; no candidate promotion",
                "missing":missing,"pit_verified":False}
    for k,maxval in SCORE_MAX.items():
        v=components[k]
        if not 0<=v<=maxval:
            raise ValueError(f"Invalid component score {k}={v}")
    total=round(sum(components.values()),2)
    fundamental_ok=(components["earnings"]>=17 and
                    components["competitiveness"]>=13 and
                    evidence.get("fundamental_growth",False))
    trend_ok=components["momentum"]>=19 and evidence.get("confirmed_weekly_trend",False)
    if previous=="CONFIRMED" and (total<65 or not fundamental_ok or not trend_ok):
        return {"state":"WEAKENING","total":total,
                "reason":"Former leader lost verified earnings or trend strength","pit_verified":True}
    if total>=80 and fundamental_ok and trend_ok and continuous_confirmations>=2:
        return {"state":"CONFIRMED","total":total,
                "reason":"Strong multi-factor PIT evidence and confirmed weekly trend","pit_verified":True}
    if total>=65 and evidence.get("fundamental_growth",False):
        return {"state":"POTENTIAL","total":total,
                "reason":"Early verified financial acceleration plus supporting score","pit_verified":True}
    return {"state":"WATCH","total":total,
            "reason":"Insufficient independent evidence for promotion","pit_verified":True}

def replacement_signal(incumbent: dict, challenger: dict, *, repeats: int) -> dict | None:
    """Requires two consecutive verified observations and same industry."""
    if repeats<2 or not (incumbent.get("pit_verified") and challenger.get("pit_verified")):
        return None
    if incumbent.get("industry")!=challenger.get("industry"):
        return None
    if not (challenger["earnings"]>incumbent["earnings"] and
            challenger["momentum"]>incumbent["momentum"]):
        return None
    return {
      "kind":"REPLACEMENT_SIGNAL",
      "incumbent_id":incumbent["security_id"],
      "challenger_id":challenger["security_id"],
      "status":"RESEARCH_SIGNAL_NOT_A_TRADE",
      "reason":"2+ independent observations of stronger PIT earnings and relative momentum",
    }
