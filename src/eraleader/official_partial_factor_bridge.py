"""Derive a conservative, partial five-factor candidate input from verified KR data.

Never convert DART industry *codes* to an industry growth score, or Kiwoom
share flows to a 0-10 investment score. These remain None until a grounded,
validated factor model is actually supplied. Original PIT flags stay false.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import re

from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search
from .factor_selection_pipeline import (SCHEMA, ASSESSMENT, EVIDENCE,
                                        SCORE_MAX, _read_assessment)
from .official_company_explorer import canonical

MAX_COHORT = 500
PROVIDER = "LOCAL_MARKETWIDE_DERIVED_NOT_INDEPENDENT_PIT"
FOLDER = "partial_factor_inputs"


def derive_partial_factor_input(*, marketwide: Path, project: Path,
                                clock: datetime | None = None,
                                limit: int = MAX_COHORT) -> dict:
    now = clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("PARTIAL_FACTOR_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if type(limit) is not int or not 1<=limit<=MAX_COHORT:
        raise ValueError("PARTIAL_FACTOR_LIMIT_INVALID")
    output = _owned_output(project)
    report,raw = _source(marketwide)
    from zoneinfo import ZoneInfo
    today = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    manifest, _ = prepare_search(report,request_day=today,clock=now)
    # 2+ weekdays behind => observe as stale, do not emit new factor inputs.
    if manifest["stale_warning"]:
        return {
            "status":"PARTIAL_FACTOR_STALE_MARKET_HOLD",
            "source_market_session":manifest["source_market_session"],
            "research_candidates":0,
            "formal_candidates":0,
            "orders_enabled":False,
        }
    stamp = report["built_at_utc"]
    first_available = datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if first_available.tzinfo is None or first_available > now:
        raise ValueError("PARTIAL_FACTOR_FUTURE_RECEIPT")

    selected=[]
    for stock in report["securities"]:
        mom=stock["price_strength_25"]
        financial=stock.get("earnings_research_25")
        two=stock.get("two_factor_research_50")
        # This arithmetic is an existing research factor, not a newly invented
        # industry/competitiveness or institutional investor scoring model.
        if financial is not None:
            if (type(financial) not in (int,float)
                or not math.isfinite(financial) or not 0<=financial<=25
                or type(mom) not in (float,int)
                or type(two) not in (float,int)
                or not math.isclose(mom+financial,two,abs_tol=0.000003)
                or stock["revenue_yoy"] is None
                or stock["operating_income_yoy"] is None):
                raise ValueError("PARTIAL_FACTOR_EARNINGS_SOURCE_MISMATCH")
        elif two is not None:
            raise ValueError("PARTIAL_FACTOR_FINANCIAL_INCOMPLETE")
        if mom is None:
            if financial is not None:
                raise ValueError("PARTIAL_FACTOR_UNPAIRED_EARNINGS")
            continue
        if type(mom) not in (float,int) or not math.isfinite(mom) or not 0<=mom<=25:
            raise ValueError("PARTIAL_FACTOR_MOMENTUM_INVALID")
        selected.append((stock,mom,financial))
    selected.sort(key=lambda item:(
        0 if item[2] is not None else 1,
        0 if item[0].get("price_top20_watch_rank") is not None else 1,
        -item[1], item[0]["security_id"],
    ))
    rows=[]
    for stock,mom,earn in selected[:limit]:
        components={
            "industry":None,
            "competitiveness":None,
            "earnings":round(float(earn),6) if earn is not None else None,
            "momentum":float(mom),
            "flow":None,
        }
        receipts={name:(
            {"sha256":report["content_sha256"],
             "available_at_utc":first_available.isoformat(),
             "provider":PROVIDER}
            if value is not None else None)
            for name,value in components.items()}
        rows.append({
            "security_id":stock["security_id"],
            "ticker":stock["security_id"],
            # A current DART company-code match is NOT historical issuer PIT.
            "issuer_id_validated_as_of":False,
            "components":components,
            "evidence":{key:False for key in EVIDENCE},
            "factor_receipts":receipts,
        })
    if not rows:
        return {
            "status":"PARTIAL_FACTOR_NO_EVALUABLE_PRICES",
            "source_market_session":manifest["source_market_session"],
            "research_candidates":0,
            "formal_candidates":0,"orders_enabled":False,
        }
    statement={
        "schema":SCHEMA,
        "market":"KR",
        "market_session":report["market_session"],
        "source_marketwide_sha256":report["content_sha256"],
        # Source built time is the earliest time *this complete report* can
        # claim to have existed, never its historical candle date.
        "decision_at_utc":first_available.isoformat(),
        "certification_level":ASSESSMENT,
        "factor_rows":rows,
    }
    statement["content_sha256"]=sha256(canonical(statement)).hexdigest()
    parent=output/FOLDER
    if parent.is_symlink():
        raise ValueError("PARTIAL_FACTOR_OUTPUT_SYMLINK")
    parent.mkdir(mode=0o700,exist_ok=True)
    if parent.is_symlink() or parent.stat().st_uid!=os.geteuid():
        raise ValueError("PARTIAL_FACTOR_OUTPUT_UNSAFE")
    filename=("KR_"+report["market_session"].replace("-","")+"_"
              +report["content_sha256"][:16]+"_PARTIAL_"+str(limit)+".json")
    target=parent/filename
    body=canonical(statement)+b"\n"
    if target.is_symlink():
        raise ValueError("PARTIAL_FACTOR_TARGET_SYMLINK")
    if target.exists():
        if _read_assessment(target)!=statement or target.read_bytes()!=body:
            raise ValueError("PARTIAL_FACTOR_EXISTING_CONFLICT")
        state="ALREADY_DERIVED"
    else:
        # Check source did not change between first SHA read and publication.
        recheck,_=_source(marketwide)
        if raw!=marketwide.read_bytes() or (
                recheck["content_sha256"]!=report["content_sha256"]):
            raise ValueError("PARTIAL_FACTOR_SOURCE_CHANGED")
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as sink:
            sink.write(body)
            sink.flush()
            os.fsync(sink.fileno())
        state="PARTIAL_FACTOR_DERIVED"
    return {
        "status":state,
        "input_file":str(target),
        "source_market_session":report["market_session"],
        "decision_at_utc":first_available.isoformat(),
        "source_sha256":report["content_sha256"],
        "research_candidates":len(rows),
        "momentum_available":sum(x["components"]["momentum"] is not None for x in rows),
        "earnings_available":sum(x["components"]["earnings"] is not None for x in rows),
        "industry_growth_scored":0,
        "competitiveness_scored":0,
        "institutional_flow_scored":0,
        "unscored_price_observations":max(0,len(selected)-len(rows)),
        "formal_candidates":0,
        "original_pit_certified":False,
        "orders_enabled":False,
    }
