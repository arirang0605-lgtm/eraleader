"""Opt-in hourly readiness/reconciliation for Kiwoom DEMO read-only research.

This module never installs jobs, backdates PIT, imports broker secrets, or
publishes without same-day official baseline and an explicit apply switch.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import fcntl
import json
import os
import re
import stat

from .kiwoom_investor_flow import canonical
from .kiwoom_shared_daily_batch import daily_batch, SCHEMA as BATCH_SCHEMA
from .kiwoom_shared_research_sidecar import render as render_observation
from .official_kiwoom_flow_overlay import build_overlay
from scripts.publish_kiwoom_flow_overlay import read, _swap

KST = ZoneInfo("Asia/Seoul")
CODE = re.compile(r"[0-9]{6}\Z")


def _safe_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
    return path.read_bytes()


def _publication(site: Path, market_day: str, codes: list[str],
                 basic: dict, industry: dict) -> tuple[Path, dict] | None:
    matches = list(site.glob("kiwoom_daily_" + market_day + "_*"))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("AMBIGUOUS_PRIOR_DAILY_EVIDENCE")
    folder = matches[0]
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
    original_payload = _safe_regular(folder / "report.json")
    payload = json.loads(original_payload)
    if (not isinstance(payload, dict) or
            original_payload != canonical(payload) + b"\n"):
        raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
    pin = payload.get("content_sha256")
    clean = {k: v for k, v in payload.items() if k != "content_sha256"}
    expected = {
        "schema": BATCH_SCHEMA, "market_day": market_day,
        "mode": "demo", "source": "SHARED_KIWOOM_KA10059_READ_ONLY",
        "basic_candidates_sha256": basic["content_sha256"],
        "industry_peers_sha256": industry["content_sha256"],
        "historical_pit_certified": False,
        "investment_ranking_available": False, "orders_enabled": False,
        "official_leaders": 0, "score_changed": False, "trade_signal": None,
    }
    if (type(pin) is not str or sha256(canonical(clean)).hexdigest() != pin
            or folder.name != "kiwoom_daily_" + market_day + "_" + pin[:12]
            or any(payload.get(k) != v or type(payload.get(k)) is not type(v)
                   for k, v in expected.items())
            or type(payload.get("items")) is not list
            or any(type(x) is not dict for x in payload["items"])
            or [x.get("stock_code") for x in payload["items"]] != codes
            or payload.get("selected_stock_count") != len(codes)):
        raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
    for item in payload["items"]:
        code = item["stock_code"]
        raw_report = _safe_regular(folder / (code + ".json"))
        report = json.loads(raw_report)
        if (not isinstance(report, dict) or raw_report != canonical(report) + b"\n"
                or report.get("content_sha256") != item.get("research_report_sha256")
                or report.get("stock_code") != code
                or report.get("source_sha256") != item.get("source_sha256")
                or report.get("orders_enabled") is not False
                or report.get("score_changed") is not False
                or report.get("historical_pit_certified") is not False
                or report.get("basic_candidates_sha256") != basic["content_sha256"]
                or report.get("industry_peers_sha256") != industry["content_sha256"]):
            raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
        expected_html = render_observation(report).encode("utf-8")
        if _safe_regular(folder / (code + ".html")) != expected_html:
            raise ValueError("ALTERED_PRIOR_DAILY_HTML")
    old_index = _safe_regular(folder / "index.html")
    if (not old_index.startswith(b"<!doctype html>")
            or any(("<a href='" + code + ".html'>").encode() not in old_index
                   for code in codes)):
        raise ValueError("INVALID_PRIOR_DAILY_EVIDENCE")
    return folder, payload


@contextmanager
def _exclusive(site: Path):
    # One global site lock prevents simultaneous runs for different days.
    lock = site / ".kiwoom_daily_runner.lock"
    if lock.is_symlink():
        raise ValueError("UNSAFE_RUNNER_LOCK")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(lock, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("UNSAFE_RUNNER_LOCK")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def run(*, site: Path, candidates: Path, industries: Path,
        stock_codes: list[str], client_factory=None,
        clock: datetime | None = None, apply: bool = False,
        cutoff_hour: int = 18) -> dict:
    """Hourly-safe entrypoint; dry-run default does not access the broker."""
    if (type(stock_codes) is not list or not 1 <= len(stock_codes) <= 5
            or len(set(stock_codes)) != len(stock_codes)
            or any(type(x) is not str or not CODE.fullmatch(x) for x in stock_codes)
            or type(cutoff_hour) is not int or not 16 <= cutoff_hour <= 22):
        raise ValueError("INVALID_RUNNER_CONFIG")
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("AWARE_RUNNER_CLOCK_REQUIRED")
    local = now.astimezone(KST)
    site = Path(site)
    if (not site.is_absolute() or site.is_symlink() or not site.is_dir()
            or any(p.is_symlink() for p in site.parents)):
        raise ValueError("UNSAFE_RUNNER_SITE")
    basic = read(Path(candidates))
    industry = read(Path(industries))
    neutral = build_overlay(basic, industry, flows={}, decision_at=now)
    day = neutral["market_session"].replace("-", "")
    if not re.fullmatch(r"[0-9]{8}", day):
        raise ValueError("INVALID_BASELINE_DAY")
    approved = {r["security_id"] for r in neutral["comparisons"]}
    if not set(stock_codes).issubset(approved):
        raise ValueError("OUTSIDE_OFFICIAL_BASELINE")
    def result(status):
        return {"status": status, "market_day": day, "companies": len(stock_codes),
                "mode": "demo", "orders_enabled": False, "score_changed": False,
                "network_calls": 0 if status != "PUBLISHED" else None}
    if local.weekday() >= 5:
        return result("SKIPPED_WEEKEND")
    if day != local.strftime("%Y%m%d"):
        return result("SKIPPED_STALE_OR_FUTURE_BASELINE")
    if local.hour < cutoff_hour:
        return result("SKIPPED_BEFORE_CUTOFF")
    if not apply:
        prior = _publication(site, day, stock_codes, basic, industry)
        if prior:
            folder, _ = prior
            link = ("href='" + folder.name + "/index.html'").encode("utf-8")
            return result("CHECK_ALREADY_PUBLISHED" if link in _safe_regular(site / "index.html")
                          else "CHECK_NEEDS_LINK_REPAIR")
        return result("CHECK_READY_NO_NETWORK")
    with _exclusive(site) as acquired:
        if not acquired:
            return result("SKIPPED_CONCURRENT_RUN")
        prior = _publication(site, day, stock_codes, basic, industry)
        if prior:
            folder, _ = prior
            index = site / "index.html"
            raw = _safe_regular(index)
            link = ("<p><a href='" + folder.name +
                    "/index.html'>키움 모의 수급 일별 연구 " + day +
                    " (매매/점수 제외)</a></p>").encode("utf-8")
            if link in raw:
                if raw.count(link) != 1:
                    raise ValueError("DUPLICATE_DAILY_INDEX_LINK")
                return result("SKIPPED_ALREADY_PUBLISHED")
            if (raw.count(b"</body>") != 1 or not raw.startswith(b"<!doctype html>")):
                raise ValueError("MAIN_INDEX_NOT_LINKABLE")
            # Crash recovery: completed immutable folder, missing link only.
            _swap(index, raw, raw.replace(b"</body>", link + b"</body>", 1))
            return result("REPAIRED_MISSING_DASHBOARD_LINK")
        if any(p.name.startswith(".kiwoom_daily_") and
               p.name != ".kiwoom_daily_runner.lock" for p in site.iterdir()):
            raise ValueError("ORPHAN_DAILY_SCRATCH_REQUIRES_REVIEW")
        if client_factory is None:
            raise ValueError("BROKER_CLIENT_FACTORY_REQUIRED")
        client = client_factory()
        status = client.status()
        if (status.get("configured", {}).get("demo") is not True
                or status.get("orders_enabled") is not False):
            raise ValueError("DEMO_READ_ONLY_GATEWAY_NOT_READY")
        published = daily_batch(
            client=client, stock_codes=stock_codes, market_day=day,
            candidates=Path(candidates), industries=Path(industries), site=site,
            now=clock,  # production uses actual AFTER-last-HTTP decision time
        )
        if published.get("status") != "SHARED_KIWOOM_DAILY_RESEARCH_PUBLISHED":
            raise ValueError("DAILY_PUBLICATION_NOT_CONFIRMED")
        return {**result("PUBLISHED"), "requested_securities": len(stock_codes)}
