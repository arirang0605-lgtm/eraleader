"""Browsable Korean company research from existing price/CFS/industry receipts.

No new price downloads, orders, score promotion, PIT backdating or mutation
of the original WATCH. This is a functional, data-backed research UI.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os
import re
import shutil
import tempfile

from .delivery import BASE_CSS
from .official_basic_candidates import SCHEMA as BASIC
from .official_industry_peer_screen import SCHEMA as PEER

SCHEMA = "eraleader.kr_company_research_explorer.v1"
CODE = re.compile(r"[0-9]{6}\Z")


def canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _moment(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("RESEARCH_SOURCE_TIMESTAMP_MISSING")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("RESEARCH_SOURCE_TIMESTAMP_INVALID") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("RESEARCH_SOURCE_TIMESTAMP_UNAWARE")
    return dt.astimezone(timezone.utc)


def _verified(path: Path, schema: str) -> tuple[dict, bytes]:
    if (not path.is_absolute() or path.is_symlink() or
            not path.is_file() or any(p.is_symlink() for p in path.parents) or
            path.stat().st_uid != os.geteuid() or path.stat().st_size > 2_000_000):
        raise ValueError("RESEARCH_SOURCE_UNSAFE")
    raw = path.read_bytes()

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("RESEARCH_SOURCE_DUPLICATE_JSON_FIELD")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           ValueError("RESEARCH_SOURCE_NONFINITE")))
    if type(value) is not dict or value.get("schema") != schema:
        raise ValueError("RESEARCH_SOURCE_SCHEMA_MISMATCH")
    proof = value.get("content_sha256")
    material = dict(value)
    material.pop("content_sha256", None)
    if proof != sha256(canonical(material)).hexdigest():
        raise ValueError("RESEARCH_SOURCE_SHA_MISMATCH")
    return value, raw


def build_explorer(basic: dict, peers: dict, *, request_day: str,
                   now: datetime | None = None) -> dict:
    """Cross-join two already witnessed research reports without ranking anew."""
    if (basic.get("schema") != BASIC or peers.get("schema") != PEER or
            basic.get("partial_research_screen_only") is not True or
            basic.get("full_ranked_investment_priority_available") is not False or
            basic.get("official_future_leaders") != 0 or
            peers.get("current_classification_only") is not True or
            peers.get("historic_sector_pit_certified") is not False or
            peers.get("full_investment_priority_ranking_ready") is not False or
            peers.get("official_leaders") != 0 or
            peers.get("baseline_candidate_sha256") != basic.get("content_sha256") or
            peers.get("market") != "KR" or
            peers.get("market_session") != basic.get("market_session")):
        raise ValueError("RESEARCH_CANDIDATE_PEER_MISMATCH")
    if type(request_day) is not str:
        raise ValueError("RESEARCH_REQUEST_DAY_INVALID")
    try:
        requested = date.fromisoformat(request_day)
        observed = date.fromisoformat(basic["market_session"])
    except (ValueError, TypeError, KeyError):
        raise ValueError("RESEARCH_MARKET_DAY_INVALID") from None
    if (requested.isoformat() != request_day or
            observed.isoformat() != basic["market_session"] or
            observed > requested):
        raise ValueError("RESEARCH_FUTURE_MARKET_DAY")
    present = (now or datetime.now(timezone.utc))
    if present.tzinfo is None or present.utcoffset() is None:
        raise ValueError("RESEARCH_AWARE_CLOCK_REQUIRED")
    present = present.astimezone(timezone.utc)
    from zoneinfo import ZoneInfo
    if requested > present.astimezone(ZoneInfo("Asia/Seoul")).date():
        raise ValueError("RESEARCH_REQUEST_DAY_FUTURE")
    candidate_at = _moment(basic["decision_at_utc"])
    industry_at = _moment(peers["as_of_utc"])
    if industry_at < candidate_at or industry_at > present:
        raise ValueError("RESEARCH_SOURCE_AVAILABILITY_INVALID")
    candidates = basic.get("comparisons")
    companies = peers.get("companies")
    if (type(candidates) is not list or type(companies) is not list or
            not 2 <= len(candidates) <= 20 or len(candidates) != len(companies) or
            basic.get("financial_companies_observed") != len(candidates) or
            peers.get("selected_companies") != len(companies)):
        raise ValueError("RESEARCH_COHORT_INCOMPLETE")
    index = {}
    for company in companies:
        key = company.get("stock_code")
        if type(key) is not str or not CODE.fullmatch(key) or key in index:
            raise ValueError("RESEARCH_PEER_ID_DUPLICATE_OR_INVALID")
        index[key] = company
    merged = []
    for candidate in candidates:
        key = candidate.get("security_id")
        if type(key) is not str or not CODE.fullmatch(key) or key not in index:
            raise ValueError("RESEARCH_CANDIDATE_ID_MISSING")
        company = index.pop(key)
        if (candidate.get("name") != company.get("name") or
                company.get("basic_observation_order") != candidate.get("comparison_order") or
                candidate.get("total_score_100") is not None or
                candidate.get("official_leader") is not False or
                company.get("total_score_100") is not None or
                company.get("official_leader") is not False):
            raise ValueError("RESEARCH_PEER_IDENTITY_CONTRADICTION")
        for field in ("return_3m", "revenue_yoy", "operating_income_yoy",
                      "price_strength_25"):
            a, b = candidate.get(field), company.get(field)
            if (a is None) != (b is None):
                raise ValueError("RESEARCH_PEER_METRIC_MISMATCH")
            if a is not None and (type(a) not in (float, int) or
                                  type(b) not in (float, int) or
                                  not math.isfinite(a) or not math.isfinite(b) or
                                  not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)):
                raise ValueError("RESEARCH_PEER_METRIC_MISMATCH")
        first = _moment(candidate["first_financial_locally_received_at_utc"])
        if first > candidate_at:
            raise ValueError("RESEARCH_FINANCIAL_FIRST_RECEIPT_FUTURE")
        if company.get("profile_first_received_at_utc") is not None:
            if _moment(company["profile_first_received_at_utc"]) > industry_at:
                raise ValueError("RESEARCH_INDUSTRY_FIRST_RECEIPT_FUTURE")
        merged.append({
            "code": key, "name": candidate["name"], "venue": candidate["venue"],
            "observed_order": candidate["comparison_order"],
            "financial_year": candidate["financial_year"],
            "return_3m": candidate.get("return_3m"),
            "return_6m": candidate.get("return_6m"),
            "price_strength_25": candidate.get("price_strength_25"),
            "revenue_yoy": candidate.get("revenue_yoy"),
            "operating_income_yoy": candidate.get("operating_income_yoy"),
            "revenue_yoy_acceleration": candidate.get("revenue_yoy_acceleration"),
            "direction": candidate.get("observed_direction"),
            "positive_concordance_of_three": candidate.get("positive_concordance_of_three"),
            "industry_code": company.get("current_industry_code"),
            "industry_division": company.get("industry_division_code"),
            "peer_sample_count": company.get("peer_cohort_size"),
            "revenue_peer_position": company.get("revenue_yoy_peer_position"),
            "operating_peer_position": company.get("operating_income_yoy_peer_position"),
            "price_peer_position": company.get("return_3m_peer_position"),
            "financial_first_received_at_utc": first.isoformat(),
            "industry_first_received_at_utc": company.get("profile_first_received_at_utc"),
        })
    if index:
        raise ValueError("RESEARCH_UNMATCHED_COMPANY")
    lag = (requested - observed).days
    weekdays = sum((observed + timedelta(days=i)).weekday() < 5
                   for i in range(1, lag + 1))
    report = {
        "schema": SCHEMA, "request_day": request_day,
        "source_market_session": observed.isoformat(),
        "candidate_decision_at_utc": candidate_at.isoformat(),
        "industry_decision_at_utc": industry_at.isoformat(),
        "published_at_utc": present.isoformat(),
        "source_candidate_sha256": basic["content_sha256"],
        "source_industry_sha256": peers["content_sha256"],
        "research_company_count": len(merged),
        "observed_concordance_all_three": sum(
            row["positive_concordance_of_three"] == 3 for row in merged),
        "companies_with_peers": sum((row["peer_sample_count"] or 0) >= 2
                                    for row in merged),
        "calendar_days_lag": lag, "estimated_weekdays_lag": weekdays,
        "trading_session_lag": None, "exchange_calendar_verified": False,
        "stale_warning": weekdays >= 2,
        "companies": merged,
        "formal_leader_score_100": None,
        "official_leaders": 0,
        "full_market_universe_verified": False,
        "historical_pit_certified": False,
        "research_only": True,
    }
    report["content_sha256"] = sha256(canonical(report)).hexdigest()
    return report


def _x(value: object) -> str:
    return escape("N/A" if value is None else str(value), quote=True)


def _pct(value: object) -> str:
    return "N/A" if value is None else f"{value * 100:+.1f}%"


def _peer(row: dict, key: str) -> str:
    pos = row[key]
    count = row["peer_sample_count"]
    return f"{pos}/{count}" if pos is not None and count and count >= 2 else "N/A"


def _top(report: dict, title: str) -> str:
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>" + _x(title) + "</title><style>" + BASE_CSS +
        "</style></head><body><header><h1>" + _x(title) +
        "</h1><nav><a href='index.html'>종목 검색·전체 비교</a></nav></header>"
        "<main><div class='note'><b>시장 데이터 관측일 " +
        _x(report["source_market_session"]) + "</b> · 요청일 " +
        _x(report["request_day"]) + " · 분석 확인 UTC " +
        _x(report["industry_decision_at_utc"]) + "<p>" +
        ("자료 지연 경고: 과거 검증된 연구 데이터입니다." if report["stale_warning"]
         else "선택 시장세션의 검증된 연구 데이터입니다.") +
        "</p>표본 " + _x(report["research_company_count"]) +
        "개사 한정, 전체 대장주 투자순위가 아닙니다. 시장 전체 PIT·주권 동일성 미인증."
        " 지연 자료를 오늘 가격이나 신규 매수신호로 사용하지 않습니다.</div>")


def render_index(report: dict) -> str:
    rows = []
    for row in report["companies"]:
        filter_text = _x(row["code"] + " " + row["name"] + " " +
                         (row["industry_division"] or ""))
        rows.append(
            "<tr data-search='" + filter_text + "' data-division='" +
            _x(row["industry_division"] or "") + "'><td>" +
            _x(row["observed_order"]) + "</td><td><a href='" +
            _x(row["code"]) + ".html'>" + _x(row["name"]) + " (" +
            _x(row["code"]) + ")</a></td><td>" + _x(row["industry_division"]) +
            "</td><td>" + _pct(row["return_3m"]) + "</td><td>" +
            _pct(row["revenue_yoy"]) + "</td><td>" +
            _pct(row["operating_income_yoy"]) + "</td><td>" +
            _pct(row["revenue_yoy_acceleration"]) + "</td><td>" +
            _peer(row, "revenue_peer_position") + "</td></tr>")
    divisions = sorted({c["industry_division"] for c in report["companies"]
                        if c["industry_division"]})
    opts = "".join("<option value='" + _x(code) + "'>" + _x(code) +
                   "</option>" for code in divisions)
    return (_top(report, "EraLeader · 한국 종목 검색 및 상세 분석") +
            "<div class='stats'><div class='stat'>분석 종목<br><strong>" +
            _x(report["research_company_count"]) +
            "</strong></div><div class='stat'>비교 동종 표본 확보<br><strong>" +
            _x(report["companies_with_peers"]) +
            "</strong></div><div class='stat'>가격·매출·영업익 동시 개선<br><strong>" +
            _x(report["observed_concordance_all_three"]) +
            "</strong></div></div>"
            "<p><label for='search'>종목명/종목코드 검색</label> "
            "<input id='search' type='search' placeholder='예: 삼성전자, 005930'></p>"
            "<p><label for='division'>업종 대분류</label> "
            "<select id='division'><option value=''>전체 업종</option>" +
            opts + "</select></p>"
            "<p id='count' aria-live='polite'>표시 " +
            _x(len(rows)) + "개 종목</p>"
            "<div class='wrap'><table><thead><tr><th>연구 관찰순서</th>"
            "<th>종목 상세</th><th>업종대분류</th><th>3개월 가격</th>"
            "<th>매출 YoY</th><th>영업익 YoY</th><th>매출성장 가속</th>"
            "<th>동종 표본 매출순서</th></tr></thead><tbody id='results'>" +
            "".join(rows) + "</tbody></table></div>"
            "<p>관찰 순서는 일부 표본의 연구 비교순서이며 투자 1위가 아닙니다. "
            "원본 데이터가 없는 실적·수급은 N/A로 표시합니다.</p>"
            "<script>const input=document.getElementById('search');"
            "const division=document.getElementById('division');"
            "function filterRows(){let n=0;const query=input.value.trim().toLocaleLowerCase();"
            "for(const tr of document.querySelectorAll('#results tr')){"
            "const show=tr.dataset.search.toLocaleLowerCase().includes(query)"
            "&&(!division.value||tr.dataset.division===division.value);"
            "tr.hidden=!show;if(show)n++;}"
            "document.getElementById('count').textContent='표시 '+n+'개 종목';}"
            "input.addEventListener('input',filterRows);"
            "division.addEventListener('change',filterRows);</script>"
            "</main><footer>EraLeader 연구용 · 투자우선순위 N/A</footer>"
            "</body></html>")


def render_company(report: dict, company: dict) -> str:
    division = company["industry_division"]
    neighbors = [x for x in report["companies"]
                 if division and x["industry_division"] == division and
                 x["code"] != company["code"]]
    peers = "".join(
        "<li><a href='" + _x(p["code"]) + ".html'>" + _x(p["name"]) +
        "</a> · 매출 " + _pct(p["revenue_yoy"]) +
        " · 3개월 " + _pct(p["return_3m"]) + "</li>" for p in neighbors)
    stats = [
        ("시장 구분", company["venue"]),
        ("기준 회계연도", company["financial_year"]),
        ("3개월 가격", _pct(company["return_3m"])),
        ("6개월 가격", _pct(company["return_6m"])),
        ("기존 가격 강도(25점 만점)", company["price_strength_25"]),
        ("매출 YoY", _pct(company["revenue_yoy"])),
        ("영업이익 YoY", _pct(company["operating_income_yoy"])),
        ("매출 성장률 가속", _pct(company["revenue_yoy_acceleration"])),
        ("가격·매출·영업이익 개선 수(0~3)", company["positive_concordance_of_three"]),
        ("연구 관찰 상태", company["direction"]),
        ("현재 DART 업종코드", company["industry_code"]),
        ("업종 대분류", division),
        ("동종 표본 매출순서", _peer(company, "revenue_peer_position")),
        ("동종 표본 영업익순서", _peer(company, "operating_peer_position")),
        ("동종 표본 3개월 가격순서", _peer(company, "price_peer_position")),
        ("재무 최초 로컬 수신 UTC", company["financial_first_received_at_utc"]),
        ("업종 최초 로컬 수신 UTC", company["industry_first_received_at_utc"]),
    ]
    table = "".join("<tr><th>" + _x(k) + "</th><td>" + _x(v) +
                    "</td></tr>" for k, v in stats)
    return (_top(report, "EraLeader 종목 상세 · " + company["name"]) +
            "<p><a href='index.html'>← 전체 종목 검색</a></p><h2>" +
            _x(company["name"]) + " (" + _x(company["code"]) + ")</h2>"
            "<table><tbody>" + table + "</tbody></table>"
            "<h2>동일 업종 대분류의 다른 관찰 기업</h2><ul>" +
            (peers if peers else "<li>비교 가능한 기업 N/A</li>") +
            "</ul><p>업종 대분류가 같아도 직접 경쟁사는 아닐 수 있습니다."
            " 동종 순서는 관찰된 소규모 표본에 한합니다.</p>"
            "<p>종합 100점, 기관·외국인 공식 수급, 정식 대장주 확정, "
            "전향 예측 적중률은 미인증(N/A).</p>"
            "</main><footer>EraLeader 연구용 · 투자권유 아님</footer></body></html>")


def publish_company_explorer(*, cohort: Path, output: Path,
                             request_day: str, clock: datetime | None = None) -> dict:
    if (not isinstance(cohort, Path) or not cohort.is_absolute() or
            cohort.is_symlink() or not cohort.is_dir() or
            not isinstance(output, Path) or not output.is_absolute() or
            output.is_symlink() or output.exists() or
            not output.parent.is_dir() or
            any(path.is_symlink() for path in (*cohort.parents, *output.parents)) or
            cohort == output or cohort in output.parents or output in cohort.parents):
        raise ValueError("RESEARCH_EXPLORER_PATH_UNSAFE_OR_ALREADY_EXISTS")
    basic_path = cohort / "basic_candidates_kr.json"
    peer_path = cohort / "industry_peers_kr.json"
    basic, initial_basic = _verified(basic_path, BASIC)
    peers, initial_peer = _verified(peer_path, PEER)
    result = build_explorer(basic, peers, request_day=request_day, now=clock)
    scratch = Path(tempfile.mkdtemp(prefix=".explorer_inflight_", dir=output.parent))
    try:
        os.chmod(scratch, 0o700)
        pages = [("index.html", render_index(result).encode("utf-8")),
                 ("report.json", canonical(result) + b"\n")]
        pages += [(c["code"] + ".html", render_company(result, c).encode("utf-8"))
                  for c in result["companies"]]
        for filename, blob in pages:
            fd = os.open(scratch / filename,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(blob)
        if (basic_path.read_bytes() != initial_basic or
                peer_path.read_bytes() != initial_peer):
            raise ValueError("RESEARCH_SOURCE_CHANGED_DURING_PUBLICATION")
        _verified(basic_path, BASIC)
        _verified(peer_path, PEER)
        if output.exists() or output.is_symlink():
            raise ValueError("RESEARCH_EXPLORER_DESTINATION_APPEARED")
        os.rename(scratch, output)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
    return result
