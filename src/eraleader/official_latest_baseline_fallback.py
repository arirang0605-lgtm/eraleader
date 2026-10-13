"""Use the latest *verified* official KR research baseline when today is unavailable.

A fallback is an immutable, clearly dated research carry-forward. It cannot
create new trading signals, call Kiwoom, backdate first receipt, or promote WATCH.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import os
import re
import shutil
import tempfile

from .delivery import BASE_CSS
from .kiwoom_investor_flow import canonical
from .official_kiwoom_daily_bridge import advance, _inspect_cohort, _inspect_official
from scripts.publish_kiwoom_flow_overlay import read

SCHEMA = "eraleader.latest_verified_kr_baseline_carry_forward.v1"
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
RECOVERABLE = {
    "WAIT_OFFICIAL_KRX_DART_RESEARCH",
    "WAIT_SAME_DAY_CFS_INDUSTRY_COHORT",
    "HOLD_MARKET_RESEARCH_CUTOFF_19_KST",
    "HOLD_WEEKEND",
}
KRX_EMPTY = "OFFICIAL_KRX_DAILY_ROWS_NOT_YET_AVAILABLE"


def _safe_dir(path: Path) -> None:
    if (not path.is_absolute() or path.is_symlink() or
            not path.is_dir() or
            any(part.is_symlink() for part in path.parents) or
            path.stat().st_uid != os.geteuid()):
        raise ValueError("FALLBACK_DIRECTORY_UNSAFE")


def discover_archived_cohorts(history_dir: Path) -> list[Path]:
    """Find immutable candidate+industry archive folders without guessing dates.

    Root, immediate children and one further directory level are accepted;
    symlinks and incomplete folders are never candidates. Each recognized folder is independently PIN-audited
    later. This allows daily archived cohorts to be discovered automatically.
    """
    _safe_dir(history_dir)
    required = ("official_api_pit_research.json",
                "basic_candidates_kr.json", "industry_peers_kr.json")
    folders = [history_dir]
    # A dated archive may have one grouping directory between history and
    # the immutable "cohort" folder. Never recurse beyond these two levels.
    def add(child: Path) -> bool:
        if (child.name.startswith(".") or child.is_symlink()
                or not child.is_dir()):
            return False
        folders.append(child)
        if len(folders) > 366:
            raise ValueError("FALLBACK_HISTORY_TOO_MANY_COHORT_DIRECTORIES")
        return True

    for child in sorted(history_dir.iterdir()):
        if add(child):
            for nested in sorted(child.iterdir()):
                add(nested)
    return [
        folder for folder in folders
        if all((folder / name).is_file() for name in required)
    ]


def _eligible(path: Path, requested: date, now: datetime,
              codes: list[str]) -> dict | None:
    _safe_dir(path)
    src = path / "official_api_pit_research.json"
    basic = path / "basic_candidates_kr.json"
    peers = path / "industry_peers_kr.json"
    if not (src.exists() and basic.exists() and peers.exists()):
        # An unfinished old research folder is never accepted as complete.
        return None
    if any(not f.is_file() or f.is_symlink() or
           f.stat().st_uid != os.geteuid() for f in (src, basic, peers)):
        raise ValueError("FALLBACK_EVIDENCE_UNSAFE")
    original = read(src)
    day = original.get("api_observation_day")
    if type(day) is not str or not DAY.fullmatch(day):
        raise ValueError("FALLBACK_OFFICIAL_MARKET_DAY_INVALID")
    observed = date.fromisoformat(day)
    if observed > requested:
        # Future observations must never substitute for an earlier request.
        raise ValueError("FALLBACK_MARKET_DAY_FUTURE")
    official = _inspect_official(path, day, now)
    if official is None:
        raise ValueError("FALLBACK_OFFICIAL_EVIDENCE_UNAVAILABLE")
    verified = _inspect_cohort(path, day, now, official, codes)
    if verified is None:
        raise ValueError("FALLBACK_COHORT_SESSION_MISMATCH")
    candidate = read(basic)
    industry = read(peers)
    if (candidate.get("official_future_leaders") != 0 or
            candidate.get("full_ranked_investment_priority_available") is not False or
            industry.get("official_leaders") != 0):
        raise ValueError("FALLBACK_INVESTMENT_PROMOTION_FORBIDDEN")
    rows = candidate.get("comparisons")
    if type(rows) is not list:
        raise ValueError("FALLBACK_CANDIDATES_INVALID")
    chosen = [r for r in rows if r.get("security_id") in codes]
    if len(chosen) != len(codes):
        raise ValueError("FALLBACK_SELECTED_COHORT_INCOMPLETE")
    from .kiwoom_investor_flow import utc
    last_decision = utc(industry["as_of_utc"])
    return {
        "root": path,
        "session": observed,
        "source": official,
        "candidate": candidate,
        "industry": industry,
        "selected": sorted(chosen, key=lambda r: codes.index(r["security_id"])),
        "last_decision": last_decision,
    }


def _render(result: dict) -> str:
    def x(value):
        return escape("N/A" if value is None else str(value), quote=True)

    def pct(value):
        return "N/A" if value is None else f"{value * 100:+.1f}%"

    rows = "".join(
        "<tr><td>" + x(r["security_id"]) + "</td><td>" + x(r["name"]) +
        "</td><td>" + x(pct(r.get("return_3m"))) + "</td><td>" +
        x(pct(r.get("revenue_yoy"))) + "</td><td>" +
        x(pct(r.get("operating_income_yoy"))) + "</td><td>" +
        x(pct(r.get("revenue_yoy_acceleration"))) + "</td></tr>"
        for r in result["selected_research_rows"]
    )
    lag = result["calendar_days_since_market_observation"]
    weekdays = result["estimated_weekday_sessions_since_market_observation"]
    warning = (
        ("자료 지연 경고: " if result["stale_warning"] else
         "최근 검증자료 표시: ") +
        "달력 " + str(lag) + "일, 평일 기준 추정 " + str(weekdays) +
        "일. 거래소 휴장일을 반영한 실제 거래세션 지연은 미인증입니다."
    )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 최근 검증 거래일 자료</title><style>" + BASE_CSS +
        "</style></head><body><header><h1>EraLeader · 최근 검증 연구자료</h1></header>"
        "<main><div class='note'><b>" + x(result["quality_status"]) +
        "</b><p>" + x(warning) + "</p>"
        "<p>요청일: " + x(result["request_day"]) +
        " · 실제 가격 관측 거래일: " + x(result["source_market_session"]) +
        " · 이번 화면 발행 UTC: " + x(result["published_at_utc"]) + "</p>"
        "<p>공식 최초 공개시각 및 역사 PIT는 미인증. 기존 자료의 관찰값을 그대로 유지하며"
        " 오늘 신규 종합점수/대장주 확정/매수매도/키움 동일일자 결합은 하지 않습니다.</p></div>"
        "<table><thead><tr><th>코드</th><th>기업</th><th>3개월 가격</th>"
        "<th>매출 YoY</th><th>영업익 YoY</th><th>매출성장 가속</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
        "<p>지난 검증 자료 그대로입니다. 수치 결손은 N/A로 유지하며"
        " 이전 가격·재무·업종 순위 또는 WATCH 이력을 수정하지 않습니다.</p></main>"
        "<footer>Research only · live orders 0 · official leaders 0</footer>"
        "</body></html>"
    )


def choose_and_publish(*, request_day: str, archived_roots: list[Path],
                       output: Path, codes: list[str],
                       reason: str, clock: datetime | None = None) -> dict:
    """Publish a date-labeled snapshot; never mutate earlier research evidence."""
    from .official_kiwoom_daily_bridge import KST
    if type(request_day) is not str or not DAY.fullmatch(request_day):
        raise ValueError("FALLBACK_REQUEST_DAY_INVALID")
    requested = date.fromisoformat(request_day)
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("FALLBACK_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if requested > now.astimezone(KST).date():
        raise ValueError("FALLBACK_REQUEST_DAY_FUTURE")
    if (type(archived_roots) is not list or not 0 <= len(archived_roots) <= 366
            or any(not isinstance(p, Path) for p in archived_roots)
            or len(set(archived_roots)) != len(archived_roots)):
        raise ValueError("EXPLICIT_DISTINCT_FALLBACK_SOURCES_REQUIRED")
    if (type(codes) is not list or not 1 <= len(codes) <= 5 or
            len(set(codes)) != len(codes) or
            any(type(x) is not str or not re.fullmatch(r"[0-9]{6}", x)
                for x in codes)):
        raise ValueError("INVALID_FALLBACK_RESEARCH_SECURITIES")
    if (not isinstance(output, Path) or not output.is_absolute() or
            output.is_symlink() or
            any(parent.is_symlink() for parent in output.parents) or
            not output.parent.is_dir() or
            output.parent.stat().st_uid != os.geteuid()):
        raise ValueError("FALLBACK_OUTPUT_MUST_BE_NEW_PRIVATE_DIRECTORY")
    for src in archived_roots:
        if output == src or src in output.parents or output in src.parents:
            raise ValueError("FALLBACK_INPUT_OUTPUT_OVERLAP")
    valid = []
    for path in archived_roots:
        try:
            picked = _eligible(path, requested, now, codes)
        except ValueError as exc:
            # A valid archived research cohort for another stock may not
            # contain this requested security; all other integrity failures
            # remain fatal and cannot be hidden by an older candidate.
            if str(exc) == "SELECTED_SECURITIES_OUTSIDE_COHORT":
                continue
            raise
        if picked is not None:
            valid.append(picked)
    if not valid:
        return {
            "status": "NO_VERIFIED_RESEARCH_BASELINE",
            "request_day": request_day,
            "broker_network_calls": 0,
            "orders_enabled": False,
            "official_leaders": 0,
            "historical_pit_certified": False,
        }
    # Session outranks receipt freshness; for a tie prefer later cohort
    # receipt, so the richer FY3 research can replace a FY2 cohort.
    selected = max(valid, key=lambda r: (r["session"], r["last_decision"]))
    lag = (requested - selected["session"]).days
    # Weekdays are an estimate, not an authenticated exchange calendar.
    # Friday -> Monday is 1 estimated session, not three calendar days.
    estimated_weekdays = sum(
        (selected["session"] + timedelta(days=i)).weekday() < 5
        for i in range(1, lag + 1))
    quality = ("CURRENT_DAY_RESEARCH_ONLY" if lag == 0 else
               "NO_NEW_WEEKDAY_CARRY_FORWARD" if estimated_weekdays == 0 else
               "RECENT_PRIOR_WEEKDAY_RESEARCH_ONLY" if estimated_weekdays == 1 else
               "STALE_RESEARCH_WARNING")
    candidate = selected["candidate"]
    industry = selected["industry"]
    result = {
        "schema": SCHEMA,
        "status": "VERIFIED_PRIOR_BASELINE_CARRIED_FORWARD",
        "reason": reason,
        "request_day": request_day,
        "source_market_session": selected["session"].isoformat(),
        "source_first_research_decision_at_utc": selected["source"]["official_decision_at"].isoformat(),
        "source_last_research_decision_at_utc": selected["last_decision"].isoformat(),
        "published_at_utc": now.isoformat(),
        "quality_status": quality,
        "calendar_days_since_market_observation": lag,
        "estimated_weekday_sessions_since_market_observation": estimated_weekdays,
        "trading_session_lag": None,
        "exchange_calendar_pit_certified": False,
        "stale_warning": estimated_weekdays >= 2,
        "source_candidate_sha256": candidate["content_sha256"],
        "source_industry_sha256": industry["content_sha256"],
        "source_official_first_receipts_sha256": selected["source"]["source_pins"],
        "source_dart_complete_manifest_sha256": selected["source"]["dart_manifest_sha256"],
        "selected_research_rows": [{
            "security_id": x["security_id"],
            "name": x["name"],
            "return_3m": x.get("return_3m"),
            "revenue_yoy": x.get("revenue_yoy"),
            "operating_income_yoy": x.get("operating_income_yoy"),
            "revenue_yoy_acceleration": x.get("revenue_yoy_acceleration"),
            "market_session": selected["session"].isoformat(),
        } for x in selected["selected"]],
        "data_recomputed_as_today": False,
        "candidate_rank_changed": False,
        "official_leaders": 0,
        "historical_pit_certified": False,
        "trade_signal": None,
        "same_day_kiwoom_combined": False,
        "broker_network_calls": 0,
        "orders_enabled": False,
    }
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    if output.exists():
        from .official_latest_baseline_replay import verify_existing_publication
        prior = verify_existing_publication(
            output=output, proposed=result, now=now, render=_render,
            allowed_reasons=frozenset(RECOVERABLE))
        # The immutable source must still be identical to what was audited
        # before serving a cached result; a replay never hides source damage.
        again = _eligible(selected["root"], requested, now, codes)
        if (again is None or
                again["candidate"]["content_sha256"] != result["source_candidate_sha256"] or
                again["industry"]["content_sha256"] != result["source_industry_sha256"] or
                again["source"]["source_pins"] != result["source_official_first_receipts_sha256"]):
            raise ValueError("FALLBACK_REPLAY_SOURCE_CHANGED_DURING_VERIFY")
        return prior
    folder = Path(tempfile.mkdtemp(prefix=".fallback_inflight_", dir=output.parent))
    try:
        os.chmod(folder, 0o700)
        for filename, payload in (
            ("report.json", canonical(result) + b"\n"),
            ("index.html", _render(result).encode("utf-8")),
        ):
            path = folder / filename
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        # Re-evaluate input hashes before finalizing an immutable output.
        again = _eligible(selected["root"], requested, datetime.now(timezone.utc)
                          if clock is None else now, codes)
        if (again is None or
                again["candidate"]["content_sha256"] != result["source_candidate_sha256"] or
                again["industry"]["content_sha256"] != result["source_industry_sha256"] or
                again["source"]["source_pins"] != result["source_official_first_receipts_sha256"]):
            raise ValueError("FALLBACK_ORIGINAL_CHANGED_BEFORE_PUBLICATION")
        if output.exists() or output.is_symlink():
            raise FileExistsError("FALLBACK_OUTPUT_ALREADY_EXISTS")
        os.rename(folder, output)
    finally:
        if folder.exists():
            shutil.rmtree(folder)
    return result


def advance_with_fallback(*, market_day: str, official_out: Path,
                          cohort_root: Path, codes: list[str],
                          archived_roots: list[Path], fallback_out: Path,
                          clock: datetime | None = None,
                          capture_official=None, apply_capture: bool = False,
                          apply_kiwoom: bool = False, client_factory=None) -> dict:
    """Retain the original strict current-day path; only recover known gaps."""
    try:
        current = advance(
            market_day=market_day, official_out=official_out,
            cohort_root=cohort_root, codes=codes, clock=clock,
            capture_official=capture_official, apply_capture=apply_capture,
            apply_kiwoom=apply_kiwoom, client_factory=client_factory)
    except ValueError as exc:
        # Not an auth, SHA, permission or issuer error; only the already
        # diagnosed official KRX response containing zero daily rows.
        if str(exc) != KRX_EMPTY:
            raise
        current = {
            "status": "WAIT_OFFICIAL_KRX_DART_RESEARCH",
            "market_day": market_day,
            "broker_orders": 0,
            "investment_rank_changed": False,
            "official_pit_certified": False,
        }
    if current["status"] not in RECOVERABLE:
        return current
    carried = choose_and_publish(
        request_day=market_day, archived_roots=archived_roots,
        output=fallback_out, codes=codes, clock=clock,
        reason=current["status"])
    if carried["status"] == "NO_VERIFIED_RESEARCH_BASELINE":
        return {**current, "fallback_status": carried["status"],
                "broker_requests": 0}
    return carried
