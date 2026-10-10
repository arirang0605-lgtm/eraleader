"""Offline PIT industry and company growth diagnostics — descriptive, not certified.

Only sees records provided by OfflineLedger.snapshot(as_of); no raw history
or future label can enter its calculations.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any
import math
from zoneinfo import ZoneInfo

# Research-only tolerance for annual/quarterly reporting mixes. An observation
# older than fifteen months must not be revived as a current growth candidate.
MAX_RESEARCH_FISCAL_AGE_DAYS = 450
MARKET_ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}


def _period_age(value: str | None, as_of: date) -> int | None:
    if value is None:
        return None
    age = (as_of-date.fromisoformat(value)).days
    if age < 0:
        raise ValueError("Future fiscal period leaked into research snapshot")
    return age


def compare_year(a: str, prior: str) -> bool:
    """Compare period ends at same fiscal date one year apart."""
    d=date.fromisoformat(a)
    p=date.fromisoformat(prior)
    try:
        return d.replace(year=d.year-1)==p
    except ValueError:
        return d.month==2 and d.day==29 and p==date(d.year-1,2,28)

def ratio_growth(value: float, past: float) -> float | None:
    if past<=0:
        # Negative and zero baselines make ordinary YoY comparison misleading.
        return None
    return round(value/past-1,6)

def by_period(rows: list[dict], key: str) -> dict[str,dict]:
    return {r["period_end"]:r for r in rows if r["metric"]==key}

def year_on_year(facts: list[dict], metric: str) -> tuple[float|None,str|None]:
    by_date=by_period(facts,metric)
    if not by_date:
        return None,None
    latest=max(by_date)
    prior=next((v for v in by_date if compare_year(latest,v)),None)
    if prior is None:
        return None, latest
    new,old=by_date[latest],by_date[prior]
    if new["unit"]!=old["unit"]:
        return None,latest
    return ratio_growth(float(new["value"]),float(old["value"])), latest

def acceleration(facts: list[dict], metric: str) -> float|None:
    """Compare two consecutive YoY readings. Not every dataset has enough history."""
    by_date=by_period(facts,metric)
    dates=sorted(by_date,reverse=True)
    if len(dates)<4:
        return None
    curr=dates[0]
    last_year=next((x for x in dates if compare_year(curr,x)),None)
    # A prior quarter's comparable date and its own prior year must both exist.
    previous=dates[1]
    previous_last_year=next((x for x in dates if compare_year(previous,x)),None)
    if not last_year or not previous_last_year:
        return None
    a,b,c,d=[by_date[k] for k in (curr,last_year,previous,previous_last_year)]
    if len({v["unit"] for v in (a,b,c,d)})!=1:
        return None
    r1=ratio_growth(a["value"],b["value"])
    r2=ratio_growth(c["value"],d["value"])
    return round(r1-r2,6) if r1 is not None and r2 is not None else None

def financial_snapshot(offline_snapshot: dict) -> dict:
    """Generate conservative, reproducible empirical descriptors.

    A full factor score requires normalized peer universe, independently
    verified PIT sources, flow and corporate actions, so none is produced.
    """
    market=offline_snapshot["market"]
    if market not in MARKET_ZONES:
        raise ValueError("Unsupported market for fiscal freshness")
    stamp=datetime.fromisoformat(offline_snapshot["as_of"].replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Fiscal research requires timezone-aware PIT cutoff")
    cutoff_day=stamp.astimezone(MARKET_ZONES[market]).date()
    members=offline_snapshot["members"]
    facts=offline_snapshot["fundamentals"]
    groups:dict[str,list[dict]]={}
    for row in facts:
        groups.setdefault(row["security_id"],[]).append(row)
    industries:dict[str,list[dict]]={}
    for row in offline_snapshot["industry"]:
        industries.setdefault(row["industry_id"],[]).append(row)

    companies=[]
    for code,row in sorted(members.items()):
        vals=groups.get(code,[])
        rev,rev_period=year_on_year(vals,"revenue")
        profit,profit_period=year_on_year(vals,"operating_income")
        ramp=acceleration(vals,"revenue")
        byrev=by_period(vals,"revenue")
        byprofit=by_period(vals,"operating_income")
        latest_revenue_date=max(byrev) if byrev else None
        latest_profit=byprofit.get(latest_revenue_date) if latest_revenue_date else None
        latest_rev=byrev.get(latest_revenue_date) if latest_revenue_date else None
        margin=(round(latest_profit["value"]/latest_rev["value"],6)
                if latest_rev and latest_profit and latest_rev["value"]>0
                and latest_profit["unit"]==latest_rev["unit"] else None)
        industry=industries.get(row["industry_id"],[])
        industry_yoy,industry_period=year_on_year(industry,"revenue")
        ages={"revenue":_period_age(rev_period,cutoff_day),
              "operating_income":_period_age(profit_period,cutoff_day),
              "industry_revenue":_period_age(industry_period,cutoff_day)}
        fresh={key:age is not None and age<=MAX_RESEARCH_FISCAL_AGE_DAYS
               for key,age in ages.items()}
        flags=[]
        for key,age in ages.items():
            if age is not None and not fresh[key]:
                flags.append(f"STALE_{key.upper()}_PERIOD")
        if rev is None:flags.append("REVENUE_YOY_MISSING")
        if profit is None:flags.append("OPERATING_YOY_MISSING")
        if ramp is None:flags.append("REVENUE_ACCELERATION_MISSING")
        if industry_yoy is None:flags.append("INDUSTRY_GROWTH_MISSING")
        if latest_rev and latest_rev["provenance"]=="synthetic_fixture":
            flags.append("SYNTHETIC_DATA")
        same_report_period=(rev_period is not None and rev_period==profit_period)
        if rev_period and profit_period and not same_report_period:
            flags.append("FUNDAMENTAL_REPORT_PERIOD_MISMATCH")
        evaluated=(all(fresh.values()) and same_report_period and rev is not None and
                   profit is not None and industry_yoy is not None)
        candidates=(evaluated and rev>=0.20 and profit>=0.30 and industry_yoy>0)
        companies.append({
          "security_id":code,"ticker":row["ticker"],"market":row["market"],
          "industry_id":row["industry_id"],
          "latest_revenue_period":rev_period,
          "revenue_yoy":rev,"operating_income_yoy":profit,
          "revenue_yoy_acceleration":ramp,"operating_margin":margin,
          "industry_revenue_yoy":industry_yoy,
          "screen_hit_heuristic":bool(candidates),
          "screen_evaluated":bool(evaluated),
          "financial_period_age_days":ages,
          "fundamental_periods_aligned":bool(same_report_period),
          "model_status":"OFFLINE_EVIDENCE_RESEARCH_ONLY",
          "leader_state":"WATCH",
          "certified_pit":False,
          "quality_flags":flags,
        })
    by_industry={}
    for code,rows in sorted(industries.items()):
        growth,period=year_on_year(rows,"revenue")
        capex,_=year_on_year(rows,"capex")
        by_industry[code]={"industry_id":code,"latest_period":period,
                           "revenue_growth_yoy":growth,"capex_growth_yoy":capex,
                           "label":"RESEARCH_ONLY_PIT_NOT_CERTIFIED"}
    return {
        "as_of":offline_snapshot["as_of"],"market":offline_snapshot["market"],
        "schema_version":"offline_research_v1",
        "quality":offline_snapshot["quality"],
        "company_count":len(companies),
        "research_screen_count":sum(x["screen_hit_heuristic"] for x in companies),
        "research_screens_evaluated":sum(x["screen_evaluated"] for x in companies),
        "research_screens_deferred":sum(not x["screen_evaluated"] for x in companies),
        "max_research_fiscal_age_days":MAX_RESEARCH_FISCAL_AGE_DAYS,
        "companies":companies,"industries":list(by_industry.values()),
        "warning":"Scored candidates NOT certified: industry, fundamentals, actions and full universe provenance incomplete",
    }
