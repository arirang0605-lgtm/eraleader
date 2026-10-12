"""ER-NC-02: PIT-only experimental market-regime observations and entry policy.

NO modification of author's original strategy signals. Requires session-final
index bars + audited same-session universe/constituent histories. No trading.
"""
from __future__ import annotations
from datetime import date,datetime,timezone
from math import isfinite
from statistics import mean
from zoneinfo import ZoneInfo

MARKETS={"KR_KOSPI":"Asia/Seoul","KR_KOSDAQ":"Asia/Seoul",
         "US_SP500":"America/New_York","US_NASDAQ100":"America/New_York"}
STATES={"RISING","SIDEWAYS","FALLING","TRANSITION","UNKNOWN"}
POLICIES={"BASE_AUTHOR_ORIGINAL","GATE_STRICT_UPTREND_V1"}
RESEARCH_THRESHOLDS={
    "adx_trend":25.0,"adx_range":23.0,"breadth_rise":0.55,
    "breadth_fall":0.45,"slope_rise_20":0.01,"slope_fall_20":-0.01,
}


def _aware(value: str) -> datetime:
    if not isinstance(value,str):
        raise ValueError("Regime requires aware timestamp")
    try: moment=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("Invalid regime timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Regime timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc)


def _price(x, label: str) -> float:
    if type(x) not in (int,float) or not isfinite(x) or x<=0:
        raise ValueError("Invalid "+label+" price")
    return float(x)


def _session(value: str) -> date:
    if type(value) is not str: raise ValueError("Invalid session")
    return date.fromisoformat(value)


def _wilder_adx(bars: list[dict], n: int=14) -> tuple[float,float,float] | None:
    if len(bars)<2*n+1:return None
    tr=[]; plus=[]; minus=[]
    for prev,now in zip(bars,bars[1:]):
        up=now["high"]-prev["high"]
        down=prev["low"]-now["low"]
        plus.append(up if up>down and up>0 else 0.0)
        minus.append(down if down>up and down>0 else 0.0)
        tr.append(max(now["high"]-now["low"],
                      abs(now["high"]-prev["close"]),abs(now["low"]-prev["close"])))
    smtr=sum(tr[:n]); smplus=sum(plus[:n]);smminus=sum(minus[:n])
    dx=[]
    di_plus=di_minus=0.0
    for i in range(n-1,len(tr)):
        if i>=n:
            smtr=smtr-smtr/n+tr[i]
            smplus=smplus-smplus/n+plus[i]
            smminus=smminus-smminus/n+minus[i]
        if smtr<=0:return None
        di_plus=100*smplus/smtr
        di_minus=100*smminus/smtr
        total=di_plus+di_minus
        dx.append(100*abs(di_plus-di_minus)/total if total else 0.0)
    if len(dx)<n:return None
    adx=mean(dx[:n])
    for value in dx[n:]:
        adx=((n-1)*adx+value)/n
    return round(adx,3),round(di_plus,3),round(di_minus,3)


def _pit_breadth(members: dict | None, *, last_session: date,
                 as_of: datetime) -> tuple[float|None,str,int]:
    if type(members) is not dict or members.get("universe_pit_certified") is not True:
        return None,"UNVERIFIED_HISTORIC_UNIVERSE",0
    if _session(members.get("session"))!=last_session:
        return None,"UNIVERSE_SESSION_NOT_ALIGNED",0
    listing=members.get("constituents")
    if not isinstance(listing,list) or not listing:
        return None,"EMPTY_PIT_UNIVERSE",0
    counted=set();above=0
    for member in listing:
        if not isinstance(member,dict):
            return None,"MALFORMED_PIT_MEMBER",len(counted)
        code=member.get("security_id")
        if type(code) is not str or not code or code in counted:
            return None,"DUPLICATE_OR_UNKNOWN_PIT_SECURITY",len(counted)
        counted.add(code)
        if (_aware(member["member_first_known_at"])>as_of or
                _session(member["effective_from"])>last_session or
                member.get("effective_to") and _session(member["effective_to"])<last_session):
            return None,"MEMBERSHIP_FUTURE_OR_NOT_EFFECTIVE",len(counted)
        history=member.get("bars")
        if not isinstance(history,list):
            return None,"MISSING_PIT_CONSTITUENT_BARS",len(counted)
        available=[];previous=None
        for bar in history:
            day=_session(bar["session"])
            if previous is not None and day<=previous:
                return None,"NONMONOTONIC_MEMBER_BARS",len(counted)
            previous=day
            if day<=last_session and _aware(bar["available_at"])<=as_of:
                available.append((day,_price(bar["close"],"constituent")))
        if len(available)<60 or available[-1][0]!=last_session:
            return None,"INCOMPLETE_60_SESSION_BREADTH",len(counted)
        avg=mean(x for _,x in available[-60:])
        if available[-1][1]>avg:
            above+=1
    return round(above/len(counted),6),"PIT_UNIVERSE_OBSERVED",len(counted)


def market_regime_snapshot(*, market: str, decision_at: str,
                           index_bars: list[dict], pit_universe: dict | None) -> dict:
    """Five-state, fail-closed research diagnosis. Session time + PIT inputs."""
    if market not in MARKETS:
        raise ValueError("Unsupported index market")
    now=_aware(decision_at)
    result={"schema":"eraleader.er_nc_market_regime.v1","market":market,
            "market_timezone":MARKETS[market],"regime_as_of":now.isoformat(),
            "state":"UNKNOWN","quality_status":"INSUFFICIENT_PIT_COVERAGE",
            "reason_codes":[],"research_only":True,
            "thresholds_are_unvalidated_hypotheses":True,
            "market_session":None,"input_cutoff":None,"features":{}}
    if not isinstance(index_bars,list):
        raise ValueError("Index bars must be a list")
    historical=[];last_day=None
    for raw in index_bars:
        if type(raw) is not dict:raise ValueError("Malformed index bar")
        day=_session(raw["session"])
        if last_day is not None and day<=last_day:
            result["reason_codes"]=["NONMONOTONIC_INDEX_SESSION"]
            return result
        last_day=day
        high=_price(raw["high"],"high"); low=_price(raw["low"],"low")
        close=_price(raw["close"],"close")
        if low>close or close>high:
            result["reason_codes"]=["OHLC_INCONSISTENT"];return result
        finished=_aware(raw["finalized_at"])
        if finished>now:
            continue   # Future or unfinished daily candles cannot enter as-of.
        if finished.astimezone(ZoneInfo(MARKETS[market])).date()!=day:
            result["reason_codes"]=["INDEX_CLOSE_SESSION_TIMEZONE_MISMATCH"]
            return result
        historical.append({"session":day,"high":high,"low":low,
                           "close":close,"finalized_at":finished})
    if len(historical)<170:
        result["reason_codes"]=["INDEX_HISTORY_LT_170_FINAL_SESSIONS"]
        return result
    last=historical[-1]
    session=last["session"]
    result["market_session"]=session.isoformat()
    if (now.astimezone(ZoneInfo(MARKETS[market])).date()-session).days>7:
        result["reason_codes"]=["STALE_INDEX_SESSION_GT_7_CALENDAR_DAYS"]
        return result
    if session>now.astimezone(ZoneInfo(MARKETS[market])).date():
        result["reason_codes"]=["FUTURE_MARKET_SESSION"]
        return result
    values=[row["close"] for row in historical]
    ma150=mean(values[-150:])
    ma150_prior=mean(values[-170:-20])
    ma20=mean(values[-20:])
    ma60=mean(values[-60:])
    slope=ma150/ma150_prior-1
    adx=_wilder_adx(historical)
    if adx is None:
        result["reason_codes"]=["ADX_INPUT_INCOMPLETE"]
        return result
    breadth,breadth_status,member_count=_pit_breadth(
        pit_universe,last_session=session,as_of=now)
    result["input_cutoff"]=last["finalized_at"].isoformat()
    result["features"]={
        "close":last["close"],"ma150":round(ma150,4),
        "ma150_20session_slope":round(slope,6),
        "ma20":round(ma20,4),"ma60":round(ma60,4),
        "adx14":adx[0],"di_plus14":adx[1],"di_minus14":adx[2],
        "breadth_above_ma60":breadth,
        "breadth_member_count":member_count,
        "breadth_status":breadth_status}
    if breadth is None:
        result["reason_codes"]=[breadth_status]
        return result
    close=last["close"]
    th=RESEARCH_THRESHOLDS
    positive=(close>ma150 and slope>=th["slope_rise_20"] and ma20>ma60
              and adx[0]>=th["adx_trend"] and adx[1]>adx[2]
              and breadth>=th["breadth_rise"])
    negative=(close<ma150 and slope<=th["slope_fall_20"] and ma20<ma60
              and adx[0]>=th["adx_trend"] and adx[2]>adx[1]
              and breadth<=th["breadth_fall"])
    sideways=(adx[0]<th["adx_range"] and abs(slope)<0.03
              and abs(ma20/ma60-1)<0.04
              and abs(close/ma150-1)<0.08
              and 0.3<=breadth<=0.7)
    result["state"]=("RISING" if positive else "FALLING" if negative else
                     "SIDEWAYS" if sideways else "TRANSITION")
    result["quality_status"]="RESEARCH_PIT_INPUTS_PRESENT_NOT_PERFORMANCE_VERIFIED"
    result["reason_codes"]=[
       {"RISING":"UPTREND_MULTI_SIGNAL","FALLING":"DOWNTREND_MULTI_SIGNAL",
        "SIDEWAYS":"LOW_TREND_RANGE","TRANSITION":"CONFLICTING_OR_AMBIGUOUS_SIGNALS"}[result["state"]]]
    return result


def entry_permission(regime: dict, *, policy: str="GATE_STRICT_UPTREND_V1",
                     action: str="NEW_BUY") -> dict:
    """Study permission only. Never edit original strategy or stops/exits."""
    if policy not in POLICIES:
        raise ValueError("Unknown experiment policy")
    if action not in {"NEW_BUY","EXIT","STOP","RISK_REDUCE"}:
        raise ValueError("Unknown trade action for paper policy")
    if action!="NEW_BUY":
        return {"policy":policy,"action":action,"permission":"AUTHOR_OR_RISK_RULE",
                "original_signal_unchanged":True,"blocked_by_new_entry_gate":False}
    if policy=="BASE_AUTHOR_ORIGINAL":
        return {"policy":policy,"action":action,"permission":"AUTHOR_ORIGINAL_ONLY",
                "original_signal_unchanged":True,"blocked_by_new_entry_gate":False}
    state=regime.get("state")
    allowed=state=="RISING" and regime.get("quality_status")==(
        "RESEARCH_PIT_INPUTS_PRESENT_NOT_PERFORMANCE_VERIFIED")
    return {"policy":policy,"action":action,
            "permission":"ALLOW_NEW_BUY_RESEARCH_ONLY" if allowed else "DENY_NEW_BUY_RESEARCH_ONLY",
            "original_signal_unchanged":True, "blocked_by_new_entry_gate":not allowed,
            "research_only":True}
