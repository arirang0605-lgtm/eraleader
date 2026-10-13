"""Immutable read-only SharedBrokerAPI sidecar; never alters leader ranks."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import os
import re
import shutil
import tempfile

from .kiwoom_investor_flow import canonical, utc
from .official_kiwoom_flow_overlay import BASE_CSS, build_overlay

SCHEMA = "eraleader.shared_kiwoom_selected_flow_sidecar.v1"
SHARED_SCHEMA = "sharedbroker.selected_security_flow_research.v1"
HEX = re.compile(r"[a-f0-9]{64}\Z")
CODE = re.compile(r"[0-9]{6}\Z")
DAY = re.compile(r"[0-9]{8}\Z")


def _verify_shared(source: dict, code: str, market_day: str, *, now: datetime) -> None:
    if type(source) is not dict:
        raise ValueError("Expected immutable shared research JSON")
    sealed = dict(source)
    digest = sealed.pop("content_sha256", None)
    if digest != sha256(canonical(sealed)).hexdigest():
        raise ValueError("Shared research content SHA invalid")
    expected = {
        "schema": SHARED_SCHEMA, "project": "eraleader", "market": "KR",
        "stock_code": code, "market_session": market_day, "mode": "demo",
        "source": "KIWOOM_KA10059", "units": "shares",
        "orders_enabled": False, "trade_signal": None,
        "historical_pit_certified": False,
        "whole_market_foreign_flow_equivalent": False,
        "can_fill_coreastock_macro_foreign_flow_20d": False,
        "can_unlock_new_risk": False,
    }
    if any(source.get(k) != v or type(source.get(k)) is not type(v)
           for k, v in expected.items()):
        raise ValueError("Shared source identity or no-trading boundary invalid")
    received = utc(source["first_gateway_received_at_utc"])
    decision = utc(source["decision_at_utc"])
    if received > decision or decision > now:
        raise ValueError("Future/retrospective shared receipt denied")
    witnesses = source.get("page_sha256_witnesses")
    pages = source.get("page_count")
    observed = source.get("observed_sessions")
    if (type(pages) is not int or type(observed) is not int or pages < 1
            or observed < 20 or type(witnesses) is not list or len(witnesses) != pages
            or source.get("recent_window_only") is not True
            or source.get("provider_history_complete") is not False):
        raise ValueError("Expected bounded 20-observation research source")
    for item in witnesses:
        if (type(item) is not dict or type(item.get("source_payload_sha256")) is not str
                or not HEX.fullmatch(item["source_payload_sha256"])
                or utc(item["gateway_first_received_at_utc"]) > decision):
            raise ValueError("Shared original page receipt missing or unsafe")
    for key in ("foreign_net_5_sessions", "institution_net_5_sessions",
                "foreign_net_20_sessions", "institution_net_20_sessions"):
        value = source.get(key)
        if value is not None and type(value) is not int:
            raise ValueError("Net shares must be an integer or N/A")


def make_sidecar(basic: dict, industries: dict, source: dict, *,
                 stock_code: str, market_day: str,
                 clock: datetime | None = None) -> dict:
    if (type(stock_code) is not str or not CODE.fullmatch(stock_code)
            or type(market_day) is not str or not DAY.fullmatch(market_day)):
        raise ValueError("Invalid read-only security or market day")
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Aware current decision time required")
    now = now.astimezone(timezone.utc)
    baseline = build_overlay(basic, industries, flows={}, decision_at=now)
    companies = [r for r in baseline["comparisons"] if r["security_id"] == stock_code]
    if len(companies) != 1:
        raise ValueError("Selected security is not in original verified cohort")
    _verify_shared(source, stock_code, market_day, now=now)
    matched = baseline["market_session"].replace("-", "") == market_day
    status = ("SAME_SESSION_RESEARCH_ONLY_NOT_PIT_CERTIFIED" if matched
              else "DIFFERENT_SESSION_NOT_JOINED")
    report = {
        "schema": SCHEMA, "stock_code": stock_code,
        "company": companies[0]["name"], "market": "KR",
        "source": "KIWOOM_KA10059_SHARED_READ_ONLY",
        "profile": "demo", "units": "shares",
        "requested_session": market_day,
        "baseline_session": baseline["market_session"],
        "sessions_match": matched, "research_status": status,
        "published_at_utc": now.isoformat(),
        "source_first_gateway_received_at_utc": source["first_gateway_received_at_utc"],
        "source_decision_at_utc": source["decision_at_utc"],
        "source_sha256": source["content_sha256"],
        "source_page_sha256_witnesses": source["page_sha256_witnesses"],
        "source_recent_window_only": True, "history_complete": False,
        "observed_sessions": source["observed_sessions"],
        "basic_candidates_sha256": basic["content_sha256"],
        "industry_peers_sha256": industries["content_sha256"],
        "foreign_net_5_shares": source.get("foreign_net_5_sessions"),
        "institution_net_5_shares": source.get("institution_net_5_sessions"),
        "foreign_net_20_shares": source.get("foreign_net_20_sessions"),
        "institution_net_20_shares": source.get("institution_net_20_sessions"),
        "historical_pit_certified": False,
        "investment_ranking_available": False,
        "official_leaders": 0, "score_changed": False,
        "can_unlock_new_risk": False, "trade_signal": None,
        "orders_enabled": False,
    }
    report["content_sha256"] = sha256(canonical(report)).hexdigest()
    return report


def render(report: dict) -> str:
    data = dict(report)
    digest = data.pop("content_sha256", None)
    if (digest != sha256(canonical(data)).hexdigest()
            or report.get("schema") != SCHEMA
            or report.get("orders_enabled") is not False
            or report.get("investment_ranking_available") is not False
            or report.get("official_leaders") != 0):
        raise ValueError("Unsafe sidecar output")
    esc = lambda v: escape(str(v), quote=True)
    num = lambda v: "N/A" if v is None else f"{v:+,d}"
    columns = (
        ("외국인 최근5 (주)", report["foreign_net_5_shares"]),
        ("기관 최근5 (주)", report["institution_net_5_shares"]),
        ("외국인 최근20 (주)", report["foreign_net_20_shares"]),
        ("기관 최근20 (주)", report["institution_net_20_shares"]),
    )
    cells = "".join(f"<tr><th>{esc(title)}</th><td>{esc(num(value))}</td></tr>"
                    for title, value in columns)
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<title>EraLeader · 공통 키움 수급 연구</title><style>" + BASE_CSS +
        "</style></head><body><header><h1>키움증권 모의투자 수급 연구</h1>"
        "<p>공통 API · 읽기 전용 · 실제 매매/대장주 점수 반영 금지</p></header>"
        "<main><p>종목 " + esc(report["stock_code"]) + " · " +
        esc(report["company"]) + "</p><p>수급 관측 기준일 " +
        esc(report["requested_session"]) + " / 기존 분석 기준일 " +
        esc(report["baseline_session"]) + "</p><p>판정 " +
        esc(report["research_status"]) + "</p><table>" + cells + "</table>"
        "<p>단위: 주식 수량(주), 원화 매매대금이 아닙니다.</p>"
        "<p>API 최초 로컬 수신 " +
        esc(report["source_first_gateway_received_at_utc"]) + "</p>"
        "<p>최신 20개 관측만 평가. 전체 페이지·독립 PIT·시장 전체 연속성 미인증.</p>"
        "<p>기존 투자순위/점수 불변 · 자동주문 0 · 공식 확정 대장주 0.</p>"
        "</main></body></html>"
    )


def _new(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def publish(*, client, stock_code: str, market_day: str,
            candidates: Path, industries: Path, site: Path,
            now: datetime | None = None) -> dict:
    """Fetch one bounded selected-stock page and publish a new immutable research snapshot."""
    from scripts.publish_kiwoom_flow_overlay import read, _swap
    site = Path(site)
    if (not site.is_absolute() or not site.is_dir() or site.is_symlink()
            or any(p.is_symlink() for p in site.parents)):
        raise ValueError("Expected existing local research site")
    index = site / "index.html"
    if index.is_symlink() or not index.is_file():
        raise ValueError("Original research index missing")
    if getattr(client, "project", None) != "eraleader":
        raise ValueError("Shared client project must match EraLeader")
    source = client.selected_flow_research(
        stock_code=stock_code, day=market_day, mode="demo",
        max_pages=1, recent_sessions=20,
    )
    basic = read(Path(candidates))
    peer = read(Path(industries))
    report = make_sidecar(
        basic, peer, source, stock_code=stock_code, market_day=market_day,
        clock=now or datetime.now(timezone.utc),
    )
    folder = "kiwoom_shared_" + market_day + "_" + stock_code + "_" + report["content_sha256"][:12]
    destination = site / folder
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Immutable shared snapshot already exists")
    original = index.read_bytes()
    if not original.startswith(b"<!doctype html>") or original.count(b"</body>") != 1:
        raise ValueError("Main research index cannot be safely linked")
    link = ("<p><a href='" + folder + "/index.html'>"
            "공통 키움 모의 수급 " + market_day + " · " + stock_code +
            " (투자순위 미반영)</a></p>").encode()
    updated = original.replace(b"</body>", link + b"</body>", 1)
    scratch = Path(tempfile.mkdtemp(prefix=".kiwoom_shared_", dir=site))
    os.chmod(scratch, 0o700)
    created = False
    try:
        _new(scratch / "index.html", render(report).encode())
        _new(scratch / "report.json", canonical(report) + b"\n")
        # This new private folder is the append-only evidence ledger entry.
        os.rename(scratch, destination)
        created = True
        _swap(index, original, updated)
    except BaseException:
        if created:
            shutil.rmtree(destination)
        else:
            shutil.rmtree(scratch, ignore_errors=True)
        raise
    return {
        "status": "SHARED_KIWOOM_DEMO_RESEARCH_PUBLISHED",
        "stock_code": stock_code, "market_day": market_day,
        "sessions_match": report["sessions_match"],
        "evidence_sha256": report["content_sha256"],
        "page": folder + "/index.html",
        "orders": 0, "score_changed": False, "official_leaders": 0,
    }
