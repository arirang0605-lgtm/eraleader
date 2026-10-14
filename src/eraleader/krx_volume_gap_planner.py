"""Find only missing original KRX volumes for dated, already-saved demo flow.

No network calls, no trading, no direct edits to original raw captures.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from .marketwide_dated_volume import evaluate_exact_volume
from .data import LEGACY_DEFAULT
from .marketwide_live_search import _source
from .official_krx_volume_overlay import _receipt_index,SOURCES
from .official_api_pit_bridge import verified_capture,_krx_frame

MAX_REQUESTS = 6


def plan_dated_krx_volume_gaps(*, marketwide:Path,project:Path,
                               capture_root:Path,stock_code:str,
                               clock:datetime|None=None,
                               max_requests:int=MAX_REQUESTS,
                               legacy_root:Path=LEGACY_DEFAULT)->dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("KRX_VOLUME_GAP_CLOCK_UNAWARE")
    now=now.astimezone(timezone.utc)
    if type(max_requests) is not int or not 1<=max_requests<=MAX_REQUESTS:
        raise ValueError("KRX_VOLUME_GAP_REQUEST_CAP_INVALID")
    source,_=_source(marketwide)
    try:
        assessment=evaluate_exact_volume(
            marketwide=marketwide,project=project,code=stock_code,clock=now,
            legacy_root=legacy_root)
    except ValueError as exc:
        if str(exc)=="DATED_FLOW_NO_PREVIOUS_20_ROW_RECEIPT":
            return {"status":"KRX_VOLUME_GAP_NO_DATED_FLOW",
                    "api_calls":0,"planned_requests":[],"orders_enabled":False}
        raise
    if assessment.get("status")=="EXACT_VOLUME_DATED_EVIDENCE_NOT_AVAILABLE":
        return {"status":"KRX_VOLUME_GAP_NO_DATED_FLOW",
                "api_calls":0,"planned_requests":[],"orders_enabled":False}
    absent=sorted(set(assessment["periods"]["20"]["missing_price_volume_dates"]))
    pinned=_receipt_index(capture_root,now)
    local_verified=[]
    queued=[]
    if len(absent)>20:
        raise ValueError("KRX_VOLUME_GAP_TOO_MANY_DATES")
    for day in absent:
        pairs=[]
        missing=[]
        for venue in SOURCES:
            first=pinned.get((day,venue))
            if first is None:
                missing.append(venue)
                continue
            _,folder,sha=first
            metadata,reply=verified_capture(folder,venue,sha,now)
            frame=_krx_frame(venue,metadata,reply)
            if metadata["request_value"]!=day:
                raise ValueError("KRX_VOLUME_GAP_CAPTURE_SESSION_MISMATCH")
            pairs.append((venue,frame))
        if missing:
            queued.extend({"market_day":day,"source":venue} for venue in missing)
            continue
        by_stock=[]
        for venue,frame in pairs:
            matching=frame.loc[frame["security_id"]==stock_code]
            if len(matching)>1:
                raise ValueError("KRX_VOLUME_GAP_DUPLICATE_SECURITY")
            if len(matching)==1:
                volume=matching.iloc[0]["volume"]
                if int(volume)<=0:
                    raise ValueError("KRX_VOLUME_GAP_ZERO_VOLUME")
                by_stock.append((venue,int(volume)))
        if len(by_stock)!=1:
            raise ValueError("KRX_VOLUME_GAP_LISTING_NOT_UNIQUE")
        local_verified.append(day)
    planned=queued[:max_requests]
    return {
        "status":("KRX_VOLUME_GAP_EXISTING_RECEIPTS_READY"
                  if not queued else "KRX_VOLUME_GAP_REQUESTS_READY"),
        "stock_code":stock_code,
        "source_market_session":source["market_session"],
        "source_marketwide_sha256":source["content_sha256"],
        "marcap_missing_dates":absent,
        "already_receipted_dates":local_verified,
        "all_missing_receipt_requests":len(queued),
        "planned_requests":planned,
        "requests_held_by_maximum":max(0,len(queued)-len(planned)),
        "market_pit_independently_certified":False,
        "api_calls":0,
        "orders_enabled":False,
        "formal_leaders":0,
    }
