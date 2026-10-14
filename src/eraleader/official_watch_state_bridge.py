"""Daily real KRX PRICE WATCH20 -> existing Stage4 StateHistory (research-only).

Tracks which observed share classes were reviewed on each source market day.
No PIT-complete factor set, no POTENTIAL/CONFIRMED and no synthetic EXIT
on disappearance from price TOP20. StateHistory may later hold distinct
verified permanent IDs when a true issuer identity source is available.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import stat

from .official_company_explorer import canonical
from .state_history import StateHistory
from .strategy_handoff import marketwide_research_handoff

LEDGER_NAME = "official_price_watch_state_history.sqlite"
CODE = re.compile(r"[A-Za-z0-9]{6}\Z")


def record_official_watch_history(report_file: Path, ledger_file: Path, *,
                                  clock: datetime | None = None) -> dict:
    now = clock or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("WATCH_STATE_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if (not report_file.is_absolute() or report_file.is_symlink() or
            not report_file.is_file() or
            any(p.is_symlink() for p in report_file.parents)):
        raise ValueError("WATCH_STATE_SOURCE_UNSAFE")
    if (not ledger_file.is_absolute() or ledger_file.is_symlink() or
            ledger_file.name != LEDGER_NAME or not ledger_file.parent.is_dir() or
            ledger_file.parent.is_symlink() or
            any(p.is_symlink() for p in ledger_file.parents) or
            ledger_file.parent.stat().st_uid != os.geteuid() or
            stat.S_IMODE(ledger_file.parent.stat().st_mode) & 0o022 or
            (ledger_file.exists() and
             (not ledger_file.is_file() or
              ledger_file.stat().st_uid != os.geteuid() or
              stat.S_IMODE(ledger_file.stat().st_mode) & 0o077))):
        raise ValueError("WATCH_STATE_LEDGER_UNSAFE")
    source = json.loads(report_file.read_bytes())
    digest = source.get("content_sha256")
    body = dict(source)
    body.pop("content_sha256", None)
    if (type(digest) is not str or
            sha256(canonical(body)).hexdigest() != digest or
            source.get("official_leaders") != 0 or
            source.get("full_market_composite_rank_available") is not False):
        raise ValueError("WATCH_STATE_SOURCE_SHA_INVALID")
    # The existing project-neutral feed is our validated watcher, so do not
    # duplicate or weaken the existing WATCH contract.
    handoff = marketwide_research_handoff(
        report_file,request_day=now.astimezone(
            ZoneInfo("Asia/Seoul")).date().isoformat(),
        clock=now)
    if (handoff["selection_count"] != 0 or handoff["selected_candidates"] or
            handoff["state_changes"] or
            handoff["watchlist_count"] != 20):
        raise ValueError("WATCH_STATE_NOT_PRICE_ONLY")
    by_code = {}
    for row in source["securities"]:
        code = row["security_id"]
        if code in by_code:
            raise ValueError("WATCH_STATE_DUPLICATE_SOURCE_SECURITY")
        by_code[code] = row
    observations = []
    for entry in handoff["research_watchlist"]:
        code = entry["security_id"]
        matched = by_code.get(code)
        price = matched.get("price_strength_25") if matched else None
        if (type(code) is not str or CODE.fullmatch(code) is None or
                type(price) not in (float, int) or not 0 <= price <= 25 or
                entry["source_market_session"] != source["market_session"]):
            raise ValueError("WATCH_STATE_PRICE_OR_IDENTITY_INVALID")
        observations.append({
            "security_id": "KR_PRICE_OBSERVED:" + code,
            "source_watch_run_id": source["source_watch_run_id"],
            "observed_market_session": source["market_session"],
            "price_watch_rank": entry["research_order"],
            "components": {"momentum": float(price)},
            "evidence": {
                "financial_pit": False,
                "historic_universe_pit": False,
                "corporate_actions_pit": False,
            },
        })
    was_present=ledger_file.exists()
    ledger = StateHistory(ledger_file)
    if not was_present:
        os.chmod(ledger_file,0o600)
    try:
        run = ledger.record("KR",source["market_session"],observations)
        states = [ledger.history("KR",obs["security_id"])[-1]["state"]
                  for obs in observations]
    finally:
        ledger.close()
    if states != ["WATCH"] * len(states) or run["new_state_events"]:
        raise ValueError("WATCH_STATE_UNEXPECTED_PROMOTION")
    result = {
        "schema": "eraleader.official_price_watch_state_bridge.v1",
        "market": "KR",
        "market_session": source["market_session"],
        "input_marketwide_sha256": digest,
        "source_watch_run_id": source["source_watch_run_id"],
        "recorded_watch_count": len(observations),
        "state_counts": {"WATCH":len(states),"POTENTIAL":0,"CONFIRMED":0,
                         "WEAKENING":0,"EXITED":0},
        "state_history_events": 0,
        "leader_selection_count": 0,
        "historical_issuer_pit_certified": False,
        "is_price_only_observation_ledger": True,
        "orders_enabled": False,
    }
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    return result
