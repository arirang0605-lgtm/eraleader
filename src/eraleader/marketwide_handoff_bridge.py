"""Opt-in, receiver-neutral export of actual latest KR PRICE WATCH observations.

Reuses marketwide auto-refresh and the existing source-SHA validated handoff.
Incomplete price/earnings/industry/flow inputs NEVER become formal leaders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os

from .marketwide_auto_refresh import refresh_latest_marketwide, _owned_output
from .strategy_handoff import (
    marketwide_research_handoff, publish_versioned_handoff, verify_handoff,
)


def publish_latest_marketwide_handoff(*, source_root: Path, project: Path,
                                    request_day: str = "today",
                                    clock: datetime | None = None) -> dict:
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("MARKETWIDE_HANDOFF_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    result = refresh_latest_marketwide(
        source_root=source_root,project=project,
        request_day=request_day,clock=now)
    if result["status"] == "NO_VERIFIED_KR_MARKETWIDE_SOURCE":
        return {"status": "NO_VERIFIED_KR_MARKETWIDE_SOURCE",
                "watchlist_count":0,"selected_count":0,
                "execution_authority":False,"orders":0}

    source = Path(result["source_report_file"])
    # The refresh itself has already validated the full-universe source SHA.
    # The handoff re-checks the same source from disk immediately before send.
    handoff = marketwide_research_handoff(
        source, request_day=result["requested_day"], clock=now)
    if (handoff["source_sha256"]!=result["source_marketwide_sha256"] or
            handoff["source_observed_as_of"]!=result["source_market_session"] or
            handoff["market"]!="KR" or handoff["source_kind"] !=
            "MARKETWIDE_KRX_DART_COVERAGE_RESEARCH" or
            handoff["research_only"] is not True or
            handoff["execution_authority"] is not False or
            handoff["order_instruction"] is not False or
            handoff["selection_count"]!=0 or
            handoff["selected_candidates"] or
            handoff["state_changes"] or
            handoff["watchlist_count"]!=20):
        raise ValueError("MARKETWIDE_HANDOFF_NOT_PRICE_WATCH_ONLY")
    output = _owned_output(project)
    outbox = output/"strategy_outbox"
    if outbox.is_symlink():
        raise ValueError("MARKETWIDE_HANDOFF_UNSAFE_OUTBOX")
    if not outbox.exists():
        outbox.mkdir(mode=0o700)
    if (not outbox.is_dir() or outbox.stat().st_uid != os.geteuid()
            or outbox.is_symlink()):
        raise ValueError("MARKETWIDE_HANDOFF_UNSAFE_OUTBOX")
    # A source revision has a different source SHA -> different immutable
    # filename. An unchanged source on a later calendar day must *not*
    # rewrite or falsely refresh the original signal timestamp.
    release = outbox/(
        "KR_"+handoff["source_observed_as_of"].replace("-","")+"_"
        +handoff["source_sha256"][:16]+".json")
    if release.exists() or release.is_symlink():
        previous = verify_handoff(release,expected_market="KR")
        if (previous.get("source_sha256")!=handoff["source_sha256"] or
                previous.get("source_observed_as_of")!=handoff["source_observed_as_of"] or
                previous.get("source_kind")!=handoff["source_kind"] or
                previous.get("execution_authority") is not False or
                previous.get("order_instruction") is not False or
                previous.get("selection_count")!=0 or
                previous.get("selected_candidates") or
                previous.get("state_changes") or
                previous.get("watchlist_count")!=20):
            raise ValueError("MARKETWIDE_HANDOFF_EXISTING_VERSION_CONFLICT")
        delivery_status="ALREADY_DELIVERED"
    else:
        published=publish_versioned_handoff(handoff,outbox)
        previous=verify_handoff(Path(published["path"]),expected_market="KR")
        if previous["source_sha256"]!=result["source_marketwide_sha256"]:
            raise ValueError("MARKETWIDE_HANDOFF_PUBLISHED_SOURCE_CHANGED")
        delivery_status=published["status"]
    return {
        "status":"KR_LATEST_PRICE_WATCH_RESEARCH_HANDOFF",
        "delivery_status":delivery_status,
        "source_market_session":result["source_market_session"],
        "requested_day":result["requested_day"],
        "source_sha256":result["source_marketwide_sha256"],
        "outbox_file":str(release),
        "search_status":result["status"],
        "search_site":result["site"],
        "watchlist_count":20,
        "selected_count":0,
        "state_changes":0,
        "research_only":True,
        "data_stale":result["stale_warning"],
        "historical_pit_certified":False,
        "execution_authority":False,
        "orders":0,
    }
