"""Atomic research-only snapshot of multiple selected Kiwoom demo observations.

The batch refuses to publish partial cohorts, never opens broker credentials,
and does not modify any ranking or order permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import os
import re
import shutil
import tempfile

from .kiwoom_investor_flow import canonical
from .kiwoom_shared_research_sidecar import make_sidecar, render
from .official_kiwoom_flow_overlay import build_overlay
from scripts.publish_kiwoom_flow_overlay import read, _swap

SCHEMA = "eraleader.shared_kiwoom_daily_cohort.v1"
CODE = re.compile(r"[0-9]{6}\Z")
DAY = re.compile(r"[0-9]{8}\Z")


def daily_batch(*, client, stock_codes: list[str], market_day: str,
                candidates: Path, industries: Path, site: Path,
                now: datetime | None = None) -> dict:
    if (getattr(client, "project", None) != "eraleader"
            or type(stock_codes) is not list
            or not 1 <= len(stock_codes) <= 5
            or any(type(code) is not str or not CODE.fullmatch(code)
                   for code in stock_codes)
            or len(set(stock_codes)) != len(stock_codes)
            or type(market_day) is not str or not DAY.fullmatch(market_day)):
        raise ValueError("INVALID_DAILY_COHORT")
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("AWARE_DAILY_CLOCK_REQUIRED")
    stamp = stamp.astimezone(timezone.utc)
    site = Path(site)
    index = site / "index.html"
    if (not site.is_absolute() or site.is_symlink() or not site.is_dir()
            or any(part.is_symlink() for part in site.parents)
            or index.is_symlink() or not index.is_file()):
        raise ValueError("SAFE_LOCAL_RESEARCH_SITE_REQUIRED")
    # One day's complete batch is a single immutable publication.
    if list(site.glob("kiwoom_daily_" + market_day + "_*")):
        raise FileExistsError("DAILY_BATCH_ALREADY_PUBLISHED")
    original_index = index.read_bytes()
    if (not original_index.startswith(b"<!doctype html>")
            or original_index.count(b"</body>") != 1):
        raise ValueError("MAIN_INDEX_NOT_LINKABLE")
    basic, peer = read(Path(candidates)), read(Path(industries))
    neutral = build_overlay(basic, peer, flows={}, decision_at=stamp)
    approved = {r["security_id"] for r in neutral["comparisons"]}
    if not set(stock_codes).issubset(approved):
        raise ValueError("OUTSIDE_ORIGINAL_COHORT")
    if market_day > stamp.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"):
        raise ValueError("FUTURE_COHORT_DATE")

    # Source requests all complete before any site file or ledger is written.
    pending = []
    for code in stock_codes:
        source = client.selected_flow_research(
            stock_code=code, day=market_day, mode="demo",
            recent_sessions=20, max_pages=1,
        )
        pending.append((code, source))
    # With a live gateway, receipts arrive AFTER the request started. The
    # actual research decision must be set only once all pages were received.
    if now is None:
        stamp = datetime.now(timezone.utc)
    observations = []
    for code, source in pending:
        report = make_sidecar(
            basic, peer, source, stock_code=code,
            market_day=market_day, clock=stamp,
        )
        usable = all(report[k] is not None for k in (
            "foreign_net_20_shares", "institution_net_20_shares"))
        observations.append((code, report, usable))
    summary = {
        "schema": SCHEMA, "market": "KR", "mode": "demo",
        "source": "SHARED_KIWOOM_KA10059_READ_ONLY",
        "market_day": market_day, "run_at_utc": stamp.isoformat(),
        "baseline_market_session": neutral["market_session"],
        "selected_stock_count": len(observations),
        "twenty_observations_complete": sum(x[2] for x in observations),
        "basic_candidates_sha256": basic["content_sha256"],
        "industry_peers_sha256": peer["content_sha256"],
        "items": [
            {
                "stock_code": code, "source_sha256": report["source_sha256"],
                "research_report_sha256": report["content_sha256"],
                "has_20_observed_share_quantities": usable,
                "baseline_session_equal": report["sessions_match"],
                "page": code + ".html",
            }
            for code, report, usable in observations
        ],
        "historical_pit_certified": False, "investment_ranking_available": False,
        "official_leaders": 0, "score_changed": False,
        "orders_enabled": False, "trade_signal": None,
    }
    summary["content_sha256"] = sha256(canonical(summary)).hexdigest()
    directory = ("kiwoom_daily_" + market_day + "_" + summary["content_sha256"][:12])
    destination = site / directory
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("DAILY_DIGEST_COLLISION")
    link = ("<p><a href='" + directory +
            "/index.html'>키움 모의 수급 일별 연구 " + market_day +
            " (매매/점수 제외)</a></p>").encode("utf-8")
    updated_index = original_index.replace(b"</body>", link + b"</body>", 1)

    stage = Path(tempfile.mkdtemp(prefix=".kiwoom_daily_", dir=site))
    os.chmod(stage, 0o700)
    committed = False
    def fresh(path: Path, value: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
    try:
        fresh(stage / "report.json", canonical(summary) + b"\n")
        rows = []
        for code, report, usable in observations:
            fresh(stage / (code + ".json"), canonical(report) + b"\n")
            fresh(stage / (code + ".html"), render(report).encode("utf-8"))
            rows.append(
                "<li><a href='" + code + ".html'>" + code + "</a> — " +
                ("최근20 관측(미인증)" if usable else "최근20 관측 N/A") +
                " · " + escape(report["research_status"]) + "</li>"
            )
        html = (
            "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<title>EraLeader 공통 키움 일별 연구</title></head><body>"
            "<h1>모의투자 선정종목 수급 일별 기록</h1><p>기준일 " +
            market_day + " · 점수/투자 순위/주문 미반영 · 독립 PIT 미인증</p>"
            "<ul>" + "".join(rows) + "</ul></body></html>"
        )
        fresh(stage / "index.html", html.encode("utf-8"))
        os.rename(stage, destination)
        committed = True
        _swap(index, original_index, updated_index)
    except BaseException:
        if committed:
            shutil.rmtree(destination)
        else:
            shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "status": "SHARED_KIWOOM_DAILY_RESEARCH_PUBLISHED",
        "market_day": market_day, "companies": len(observations),
        "usable_20_observation_companies": summary["twenty_observations_complete"],
        "page": directory + "/index.html",
        "content_sha256": summary["content_sha256"],
        "orders": 0, "score_changed": False, "official_leaders": 0,
    }
