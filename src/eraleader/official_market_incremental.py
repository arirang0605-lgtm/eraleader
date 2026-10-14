"""Incremental official KRX sessions into the existing research coverage contract.

New captures and publications are private/versioned. Financial facts retain
their verified cache provenance; dated broker flow is never carried forward.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import fcntl
import json
import os
import tempfile

import pandas as pd

from .data import LEGACY_DEFAULT, read_market_bars, validate_bars
from .discovery import run_id_for, score_price_observations
from .marketwide_auto_refresh import _owned_output, _safe_directory
from .marketwide_live_search import _source, prepare_search
from .official_api_capture import capture_official_api, credentials, _root
from .official_api_pit_bridge import verified_capture, _krx_frame
from .official_company_explorer import canonical
from .official_marketwide_coverage import publish_marketwide_coverage

KST = ZoneInfo("Asia/Seoul")
SOURCES = ("krx-kospi", "krx-kosdaq")
FOLDER = "official_daily_marketwide"


def _latest(roots, now):
    choices = []
    for index, root in enumerate(roots):
        _safe_directory(root)
        for path in sorted(root.glob("*/marketwide_kr.json")):
            try:
                report, _ = _source(path)
                prepare_search(report, request_day=now.astimezone(KST).date().isoformat(),
                               clock=now)
            except (ValueError, OSError, KeyError, TypeError):
                # Source archives include earlier schema versions. Match the
                # existing refresh selection; never ignore a damaged new checkpoint.
                if index == 0:
                    continue
                raise
            choices.append(((report["market_session"],
                             report["financial_factors_observed"],
                             report["built_at_utc"]), path, report))
    if not choices:
        raise ValueError("KR_INCREMENTAL_VERIFIED_BASELINE_REQUIRED")
    _, path, report = max(choices, key=lambda x: x[0])
    # An existing checkpoint must still match its original receipts and cache.
    if report.get("incremental_krx_receipts"):
        origin, _ = _source(Path(report["cached_financial_source_file"]))
        if origin["content_sha256"] != report["cached_financial_source_sha256"]:
            raise ValueError("KR_INCREMENTAL_FINANCIAL_CACHE_CHANGED")
        for pin in report["incremental_krx_receipts"]:
            verified_capture(Path(pin["folder"]), pin["source"],
                             pin["first_receipt_sha256"], now)
    return path, report


def _receipts(roots, now, end):
    found = {}
    for root in roots:
        _safe_directory(root)
        _root(root)
        for folder in sorted(root.glob("first_*")):
            first = folder / "first_receipt.json"
            if first.is_symlink() or not first.is_file():
                raise ValueError("KR_INCREMENTAL_RECEIPT_UNSAFE")
            meta = json.loads(first.read_bytes())
            if meta.get("source") not in SOURCES:
                continue
            day = date.fromisoformat(meta["request_value"])
            if day > end or (end - day).days > 550:
                continue
            pin = sha256(first.read_bytes()).hexdigest()
            checked, body = verified_capture(folder, meta["source"], pin, now)
            found.setdefault((day.isoformat(), meta["source"]), []).append(
                (folder, pin, checked, body))
    return found


def _choose(items):
    positive = [x for x in items if x[2]["provider_row_count"] > 0]
    candidates = positive or items
    if positive and len({x[2]["raw_sha256"] for x in positive}) != 1:
        raise ValueError("KR_INCREMENTAL_CONFLICTING_OFFICIAL_RECEIPTS")
    return min(candidates, key=lambda x: x[2]["first_local_received_at_utc"]) if candidates else None


def _pin(source, item):
    folder, pin, meta, _ = item
    return {"source": source, "folder": str(folder),
            "first_receipt_sha256": pin, "raw_sha256": meta["raw_sha256"],
            "first_local_received_at_utc": meta["first_local_received_at_utc"],
            "market_session": meta["request_value"],
            "row_count": meta["provider_row_count"]}


def _build(base, origin_path, origin, pair, history, now):
    frames = [_krx_frame(source, item[2], item[3])
              for source, item in zip(SOURCES, pair)]
    current = pd.concat(frames, ignore_index=True)
    day = current["session"].iloc[0].date()
    if current.duplicated(["security_id", "session"]).any():
        raise ValueError("KR_INCREMENTAL_DUPLICATE_SECURITY")
    old = history.loc[history["session"].dt.date < day]
    bars = validate_bars(pd.concat([old, current], ignore_index=True),
                         now.astimezone(KST).date(), quarantine=False)
    prices = score_price_observations(bars, "KR", now.astimezone(KST).date().isoformat(),
                                      len(current))
    if prices["market_last_observation"] != day.isoformat():
        raise ValueError("KR_INCREMENTAL_PRICE_SESSION_MISMATCH")
    previous = {r["security_id"]: r for r in origin["securities"]}
    scored = {r["security_id"]: r for r in prices["rows"]}
    rows = []
    for row in current.itertuples(index=False):
        cache = previous.get(row.security_id)
        # Current issuer/class PIT is unverified. Name+venue changes cannot
        # inherit a previous company's financial observations.
        if cache and (cache["name"], cache["venue"]) != (row.name, row.venue):
            cache = None
        item = {key: None for key in (
            "revenue_yoy", "operating_income_yoy", "revenue_growth_acceleration",
            "industry_code", "price_strength_25", "earnings_research_25",
            "two_factor_research_50", "two_factor_research_rank",
            "price_top20_watch_rank", "institutional_flow", "foreign_flow",
            "formal_leader_score_100", "verified_leader_state")}
        if cache:
            for key in ("revenue_yoy", "operating_income_yoy",
                        "revenue_growth_acceleration", "industry_code",
                        "financial_receipt_years"):
                if key in cache:
                    item[key] = cache[key]
        item.update(security_id=row.security_id, name=row.name, venue=row.venue,
                    market_session=day.isoformat(), close=float(row.close),
                    turnover=float(row.turnover), market_cap=float(row.market_cap),
                    market_traded=bool(row.volume > 0),
                    current_dart_directory_matched=bool(cache and cache[
                        "current_dart_directory_matched"]),
                    cached_financial_market_session=origin["market_session"] if cache else None)
        price = scored.get(row.security_id)
        if price:
            item["price_strength_25"] = price["price_strength_25"]
            item["price_top20_watch_rank"] = price["rank"] if price["rank"] <= 20 else None
            a, b = item["revenue_yoy"], item["operating_income_yoy"]
            if a is not None and b is not None:
                earnings = round(12.5 * min(max(a, 0) / .40, 1)
                                 + 12.5 * min(max(b, 0) / .60, 1), 6)
                item["earnings_research_25"] = earnings
                item["two_factor_research_50"] = round(earnings + item["price_strength_25"], 6)
        rows.append(item)
    comparable = sorted((x for x in rows if x["two_factor_research_50"] is not None),
                        key=lambda x: (-x["two_factor_research_50"],
                                       -x["price_strength_25"], x["security_id"]))
    for rank, item in enumerate(comparable, 1):
        item["two_factor_research_rank"] = rank
    report = deepcopy(base)
    for key in list(report):
        if key.startswith("flow_"):
            report.pop(key)
    report.update(
        market_session=day.isoformat(), built_at_utc=now.isoformat(),
        source_decision_at_utc=now.isoformat(),
        source_watch_run_id=run_id_for("KR", now.astimezone(KST).date().isoformat(), prices["rows"]),
        securities=sorted(rows, key=lambda x: x["security_id"]),
        official_krx_observed=len(rows),
        current_dart_directory_matched=sum(x["current_dart_directory_matched"] for x in rows),
        financial_factors_observed=sum(x["revenue_yoy"] is not None for x in rows),
        industry_factors_observed=sum(x["industry_code"] is not None for x in rows),
        flow_factors_observed=0, two_factor_research_evaluable=len(comparable),
        local_price_lookback_enabled=True, local_price_lookback_evaluable=len(scored),
        two_factor_research_top20=[
            {"research_order": x["two_factor_research_rank"], "security_id": x["security_id"],
             "name": x["name"], "observed_score_50": x["two_factor_research_50"],
             "official_leader": False} for x in comparable[:20]],
        incremental_krx_receipts=[_pin(s, x) for s, x in zip(SOURCES, pair)],
        cached_financial_source_file=str(origin_path),
        cached_financial_source_sha256=origin["content_sha256"],
        cached_financial_source_market_session=origin["market_session"],
        cached_financial_available_at_utc=origin["built_at_utc"],
        financial_cache_refreshed=False,
        warning=("Official KRX daily prices updated; DART financial/industry facts are "
                 "previous verified cached observations, NOT newly retrieved disclosures. "
                 "Dated broker flow reset to N/A. Historical PIT/leader certification unavailable."))
    report.pop("content_sha256", None)
    report["content_sha256"] = sha256(canonical(report)).hexdigest()
    prepare_search(report, request_day=now.astimezone(KST).date().isoformat(), clock=now)
    return report, bars


def update_official_market(*, project: Path, source_root: Path, capture_root: Path,
                          existing_capture_roots: tuple[Path, ...] = (),
                          through_day: str = "today", apply_official: bool = False,
                          legacy_root: Path = LEGACY_DEFAULT, creds=None,
                          fetch=None, clock=None) -> dict:
    """Acquire only missing closed weekday candidates; actual rows define sessions.

    Both-empty responses are retained as observations, never a holiday/calendar
    certification. Empty/partial days retry at most once per local calendar day.
    A process lock prevents simultaneous scheduled/manual acquisitions.
    """
    now_fn = clock or (lambda: datetime.now(timezone.utc))
    now = now_fn()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("KR_INCREMENTAL_AWARE_CLOCK_REQUIRED")
    local = now.astimezone(KST)
    closed = local.date() - timedelta(days=int(local.hour < 19))
    end = closed if through_day == "today" else date.fromisoformat(through_day)
    if end > closed:
        raise ValueError("KR_INCREMENTAL_DAY_NOT_CLOSED")
    output = _owned_output(project)
    target_root = output / FOLDER
    target_root.mkdir(mode=0o700, exist_ok=True)
    _safe_directory(target_root)
    _root(capture_root)
    lock = output / ".official_market_daily.lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "KR_INCREMENTAL_ALREADY_RUNNING", "external_api_calls": 0}
        path, base = _latest((source_root, target_root), now)
        if date.fromisoformat(base["market_session"]) > end:
            raise ValueError("KR_INCREMENTAL_BASELINE_AFTER_REQUEST")
        origin_path = Path(base.get("cached_financial_source_file", str(path)))
        origin, _ = _source(origin_path)
        if datetime.fromisoformat(origin["built_at_utc"]).astimezone(timezone.utc) > now:
            raise ValueError("KR_INCREMENTAL_FUTURE_FINANCIAL_CACHE")
        start = date.fromisoformat(base["market_session"]) + timedelta(days=1)
        if (end - start).days >= 10:
            raise ValueError("KR_INCREMENTAL_GAP_OVER_10_DAYS")
        found = _receipts((capture_root, *existing_capture_roots), now, end)
        # Verify checkpoint pins even on a no-op; no unnecessary cache scan/run.
        result = {"status": "KR_INCREMENTAL_ALREADY_CURRENT",
                  "source_report_file": str(path), "source_root": str(path.parent.parent),
                  "source_market_session": base["market_session"],
                  "through_day": end.isoformat(), "external_api_calls": 0,
                  "published_sessions": [], "no_row_days": [], "delayed_days": [],
                  "financial_cache_refreshed": False, "orders": 0}
        history = None
        for offset in range(max(0, (end - start).days + 1)):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            pair = []
            for source in SOURCES:
                key = (day.isoformat(), source)
                items = found.get(key, [])
                chosen = _choose(items)
                today_empty = any(x[2]["provider_row_count"] == 0 and
                    datetime.fromisoformat(x[2]["first_local_received_at_utc"]).astimezone(KST).date()
                    == local.date() for x in items)
                if (chosen is None or chosen[2]["provider_row_count"] == 0 and not today_empty):
                    if not apply_official:
                        result["status"] = "KR_INCREMENTAL_MISSING_RECEIPTS"
                        result["delayed_days"].append(day.isoformat())
                        return result
                    if creds is None:
                        saved = (Path.home() / "Library" / "Application Support" / "EraLeader"
                                 / "api-credentials" / "official_api.env")
                        creds = credentials(saved if saved.is_file() else None)
                    captured = capture_official_api(source, capture_root, day=day.isoformat(),
                                                    creds=creds, fetch=fetch, clock=now_fn)
                    result["external_api_calls"] += 1
                    folder = capture_root / captured["capture_id"]
                    stamp = now_fn()
                    meta, body = verified_capture(folder, source,
                                                   captured["first_receipt_sha256"], stamp)
                    chosen = (folder, captured["first_receipt_sha256"], meta, body)
                    found.setdefault(key, []).append(chosen)
                pair.append(chosen)
            counts = [x[2]["provider_row_count"] for x in pair]
            if counts == [0, 0]:
                result["no_row_days"].append(day.isoformat())
                continue
            if 0 in counts:
                result["status"] = "KR_INCREMENTAL_PROVIDER_DELAYED"
                result["delayed_days"].append(day.isoformat())
                break
            if history is None:
                history, _ = read_market_bars("KR", local.date(), days=550, legacy_root=legacy_root)
                historical = []
                for earlier in sorted({k[0] for k in found if k[0] < day.isoformat()}):
                    prior = [_choose(found.get((earlier, s), [])) for s in SOURCES]
                    if all(x is not None and x[2]["provider_row_count"] > 0 for x in prior):
                        historical += [_krx_frame(s, x[2], x[3]) for s, x in zip(SOURCES, prior)]
                if historical:
                    official = pd.concat(historical, ignore_index=True)
                    history = pd.concat([history, official], ignore_index=True).drop_duplicates(
                        ["security_id", "session"], keep="last")
            report, history = _build(base, origin_path, origin, pair, history, now_fn())
            destination = target_root / ("KR_" + day.strftime("%Y%m%d") + "_"
                                         + report["content_sha256"][:16])
            rechecked, _ = _source(origin_path)
            if rechecked["content_sha256"] != origin["content_sha256"]:
                raise ValueError("KR_INCREMENTAL_FINANCIAL_CACHE_CHANGED")
            for pin in report["incremental_krx_receipts"]:
                verified_capture(Path(pin["folder"]), pin["source"],
                                 pin["first_receipt_sha256"], now_fn())
            with tempfile.TemporaryDirectory(prefix=".market_inflight_", dir=target_root) as scratch:
                stage = Path(scratch) / "report"
                publish_marketwide_coverage(report, stage)
                if destination.exists() or destination.is_symlink():
                    raise ValueError("KR_INCREMENTAL_EXISTING_PUBLICATION")
                os.rename(stage, destination)
            path = destination / "marketwide_kr.json"
            base = report
            result.update(status="KR_INCREMENTAL_UPDATED", source_report_file=str(path),
                          source_root=str(target_root), source_market_session=day.isoformat())
            result["published_sessions"].append(day.isoformat())
        if result["no_row_days"] and not result["published_sessions"] and not result["delayed_days"]:
            result["status"] = "KR_INCREMENTAL_NO_DAILY_ROWS"
        return result
