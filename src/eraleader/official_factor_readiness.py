"""Official-source factor coverage: show known vs missing, never invent ranking.

Reads only the already-verified KRX/DART research snapshot. The observation
universe is *not* a certified historical listed-company/security-class universe.
Research-only FY growth is shown even if its issuer is outside price TOP-N.
No buy ranking, automated orders, provider fetches or retrospective credit.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from math import isfinite
from pathlib import Path
from typing import Any
import json
import os
import re

from .delivery import BASE_CSS

SCHEMA = "eraleader.official_factor_coverage.v1"
API_SCHEMA = "eraleader.official_api_pit_research_bridge.v1"
PIN = re.compile(r"[0-9a-f]{64}\Z")
FACTORS = ("industry_growth", "competitiveness", "earnings", "price_momentum", "institutional_flow")
FIELDS = ("revenue_yoy", "operating_income_yoy", "net_income_yoy")


def _time(value: object) -> datetime:
    if type(value) is not str or len(value) > 70:
        raise ValueError("Source evidence requires a bounded timezone-aware clock")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Malformed receipt timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Naive source timestamp must not be accepted")
    return dt.astimezone(timezone.utc)


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Invalid observed count " + label)
    return value


def _number(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Financial diagnostic requires observed finite numbers or N/A")
    return float(value)


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def factor_coverage_from_official_snapshot(snapshot: dict) -> dict:
    """Make a deterministic sidecar without modifying the price ranking."""
    if (type(snapshot) is not dict or snapshot.get("source_market") != "KR" or
            snapshot.get("classification_quality") !=
            "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("Expected official KR price-only unpromoted research")
    evidence = snapshot.get("official_api_evidence")
    if (type(evidence) is not dict or evidence.get("schema") != API_SCHEMA or
            evidence.get("official_leaders") != 0 or
            evidence.get("historic_universe_pit_verified") is not False or
            evidence.get("issuer_share_class_verified") is not False):
        raise ValueError("Cannot promote unverified issuer/leader evidence")
    decision = _time(evidence["decision_at"])
    market_day = date.fromisoformat(evidence["api_observation_day"])
    if market_day > decision.date():
        raise ValueError("Future official KRX market session")
    if date.fromisoformat(snapshot["as_of_requested"]) < market_day:
        raise ValueError("Price ranking cannot predate official market session")
    if snapshot.get("market_last_observation") != market_day.isoformat():
        raise ValueError("Ranked watch session disagrees with KRX first original")
    sources = evidence.get("sources")
    if type(sources) is not list:
        raise ValueError("Official receipt source list required")
    original = {}
    for item in sources:
        if type(item) is not dict:
            raise ValueError("Malformed official receipt summary")
        src = item.get("source")
        if src in ("krx-kospi", "krx-kosdaq"):
            if src in original or not PIN.fullmatch(str(item.get("first_receipt_sha256", ""))):
                raise ValueError("Duplicate/missing official KRX source witness")
            received = _time(item["first_local_received_at_utc"])
            if received > decision:
                raise ValueError("KRX source first received after decision")
            original[src] = _nonnegative_int(item.get("row_count"), src)
    if set(original) != {"krx-kospi", "krx-kosdaq"}:
        raise ValueError("Both KRX official market originals are mandatory")
    universe_size = sum(original.values())
    if universe_size <= 0:
        raise ValueError("Empty original KRX observation universe")
    rows = snapshot.get("rows")
    if type(rows) is not list or len(rows) != snapshot.get("shown") or len(rows) > 100:
        raise ValueError("Price observation rows mismatch")
    codes = set()
    for i, row in enumerate(rows, 1):
        if (type(row) is not dict or row.get("rank") != i or
                row.get("total_score_100") is not None or row.get("state") != "WATCH"):
            raise ValueError("Price screen contains unsupported investment ranking")
        code = row.get("security_id")
        if type(code) is not str or not re.fullmatch("[A-Za-z0-9]{6}", code) or code in codes:
            raise ValueError("Duplicate or malformed price-ranked share class")
        codes.add(code)
        score = row.get("price_strength_25")
        if (type(score) not in (int, float) or not isfinite(score) or
                score < 0 or score > 25):
            raise ValueError("Missing or invalid computed price observation strength")
        if date.fromisoformat(row["observed_at"]) != market_day:
            raise ValueError("Price-ranked row contains nonofficial or future market session")
    directory = evidence.get("dart_current_directory")
    mapped = 0
    if directory is not None:
        if type(directory) is not dict or directory.get("historical_pit_certified") is not False:
            raise ValueError("DART present issuer data cannot certify historical class")
        if _nonnegative_int(directory.get("krx_total_observed"), "directory total") != universe_size:
            raise ValueError("DART directory coverage universe mismatch")
        mapped = _nonnegative_int(directory.get("matched_unique_dart_corporation"), "directory matched")
        if mapped > universe_size:
            raise ValueError("DART mapping exceeds original KRX universe")
        if _time(directory["first_local_received_at_utc"]) > decision:
            raise ValueError("Future current DART issuer directory")
    financial_count = _nonnegative_int(evidence.get("dart_financial_comparable_companies", 0), "annual CFS")
    if financial_count > universe_size:
        raise ValueError("Financial evidence exceeds observed issue count")
    receipts = evidence.get("dart_financial_first_receipts", [])
    if type(receipts) is not list:
        raise ValueError("Malformed financial first-original receipts")
    financial_by_code: dict[str, list[dict]] = {}
    for receipt in receipts:
        if (type(receipt) is not dict or
                type(receipt.get("stock_code")) is not str or
                not re.fullmatch("[A-Za-z0-9]{6}", receipt["stock_code"]) or
                type(receipt.get("report_year")) is not int or
                not PIN.fullmatch(str(receipt.get("first_receipt_sha256", ""))) or
                receipt.get("pit_certified") is not False):
            raise ValueError("DART financial receipt proof missing")
        if _time(receipt["first_local_received_at_utc"]) > decision:
            raise ValueError("Future first receipt cannot enter historical view")
        financial_by_code.setdefault(receipt["stock_code"], []).append(receipt)
    observations = snapshot.get("official_financial_research_observations", [])
    if type(observations) is not list:
        raise ValueError("Financial research observations must be structured rows")
    if observations and len(observations) != financial_count:
        raise ValueError("Receipt-verified financial universe count disagrees with row evidence")
    details = []
    emitted = set()
    for observed in observations:
        if type(observed) is not dict:
            raise ValueError("Invalid financial observation")
        code = observed.get("security_id")
        if code in emitted or code not in financial_by_code:
            raise ValueError("Finance observation not tied to original DART receipts")
        parts = financial_by_code[code]
        year = observed.get("reported_financial_year")
        if (type(year) is not int or len(parts) != 2 or
                sorted(p["report_year"] for p in parts) != [year - 1, year]):
            raise ValueError("Incomplete consecutive CFS evidence")
        if (observed.get("historic_issuer_class_pit_certified") is not False or
                observed.get("formal_score_100") is not None or
                observed.get("official_leader") is not False or
                observed.get("rank_in_price_top20") != next(
                    (r["rank"] for r in rows if r["security_id"] == code), None) or
                not PIN.fullmatch(str(observed.get("evidence_sha256", ""))) or
                _time(observed["source_first_received_at_utc"]) > decision):
            raise ValueError("Financial row carries retrospective leader claim")
        factors = observed.get("research_metrics")
        if type(factors) is not dict or set(factors) != set(FIELDS):
            raise ValueError("Incomplete annual company diagnostic fields")
        emitted.add(code)
        details.append({
            "security_id": code, "name": observed["name"],
            "reported_financial_year": observed["reported_financial_year"],
            "revenue_yoy": _number(factors["revenue_yoy"]),
            "operating_income_yoy": _number(factors["operating_income_yoy"]),
            "net_income_yoy": _number(factors["net_income_yoy"]),
            "first_local_received_at_utc": observed["source_first_received_at_utc"],
            "price_watch_rank": observed["rank_in_price_top20"],
            "independent_history_pit_certified": False,
            "full_investment_score": None,
        })
    if not observations and financial_count:
        # Old published result formats did not retain all-company YoY figures.
        # Use receipt metadata to preserve coverage, never invent financial YoY.
        for code, parts in sorted(financial_by_code.items()):
            if len(parts) != 2 or sorted(p["report_year"] for p in parts)[1] != (
                    sorted(p["report_year"] for p in parts)[0] + 1):
                continue
            details.append({
                "security_id": code, "name": None,
                "reported_financial_year": max(p["report_year"] for p in parts),
                "revenue_yoy": None, "operating_income_yoy": None,
                "net_income_yoy": None,
                "first_local_received_at_utc": max(p["first_local_received_at_utc"]
                                                    for p in parts),
                "price_watch_rank": next((r["rank"] for r in rows
                                          if r["security_id"] == code), None),
                "independent_history_pit_certified": False,
                "full_investment_score": None,
            })
        if len(details) != financial_count:
            raise ValueError("Old financial original receipts lack full company pairing")
    if not observations and not financial_count and receipts:
        raise ValueError("Unexpected CFS receipts without comparison count")
    details.sort(key=lambda x:x["security_id"])
    report = {
        "schema": SCHEMA, "market": "KR",
        "decision_at": decision.isoformat(),
        "market_session": market_day.isoformat(),
        "source_is_historic_pit_certified": False,
        "observed_krx_market_rows": universe_size,
        "current_dart_mapping_observed": mapped,
        "annual_cfs_comparable_companies": financial_count,
        "annual_cfs_in_price_top20": sum(row["price_watch_rank"] is not None
                                         for row in details),
        "price_watch_shown": len(rows),
        "official_leaders": 0,
        "valid_full_leader_scores": 0,
        "factors": {
            "industry_growth": {"observed_issues": 0, "official_pit_certified": False},
            "competitiveness": {"observed_issues": 0, "official_pit_certified": False},
            "earnings": {"observed_issues": financial_count, "official_pit_certified": False},
            "price_momentum": {"observed_issues": len(rows), "official_pit_certified": False},
            "institutional_flow": {"observed_issues": 0, "official_pit_certified": False},
        },
        "financial_research": details,
        "source_watch_run_id": snapshot.get("run_id"),
        "rank_basis": snapshot.get("scoring_policy"),
        "investment_priority_ranking_available": False,
        "research_only": True,
        "limitations": [
            "PRICE_TOP_N is a 3/6-month momentum observation, not investment priority.",
            "KRX is one official trading day; older price history is not provider-PIT-certified.",
            "DART issuer mapping is current and does not certify historical classes or delistings.",
            "Two annual CFS vintages measure one YoY interval; earnings acceleration requires additional years.",
            "Missing industry, competitiveness and flow never count as zero or fabricated rank factors.",
            "No total 100-point score, leader promotion, orders or investment performance here.",
        ],
    }
    report["content_sha256"] = sha256(_canonical(report)).hexdigest()
    return report


def _safe(value: object) -> str:
    return escape("N/A" if value is None else str(value), quote=True)


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:+.2f}%"


def render_factor_readiness(report: dict) -> str:
    """Display actual evidence coverage and research examples, NOT investment rank."""
    if (type(report) is not dict or report.get("schema") != SCHEMA or
            report.get("official_leaders") != 0 or
            report.get("valid_full_leader_scores") != 0 or
            report.get("investment_priority_ranking_available") is not False or
            report.get("source_is_historic_pit_certified") is not False or
            report.get("research_only") is not True):
        raise ValueError("Uncertified coverage cannot be promoted to leader ranking")
    sealed = dict(report)
    pinned = sealed.pop("content_sha256", None)
    if type(pinned) is not str or sha256(_canonical(sealed)).hexdigest() != pinned:
        raise ValueError("Factor coverage report has changed since evidence sealing")
    titles = {
        "industry_growth": "산업 성장성",
        "competitiveness": "기업 경쟁력",
        "earnings": "연결재무 실적(연간 YoY 연구)",
        "price_momentum": "3·6개월 가격 관찰",
        "institutional_flow": "기관·외국인 수급",
    }
    cells = []
    for key in FACTORS:
        item = report["factors"][key]
        if (item.get("official_pit_certified") is not False or
                type(item.get("observed_issues")) is not int):
            raise ValueError("PIT coverage factors may not be certified")
        cells.append(
            "<tr><td>"+_safe(titles[key])+"</td><td>"+
            _safe(item["observed_issues"])+"/"+
            _safe(report["observed_krx_market_rows"])+
            "</td><td>공식 역사 PIT 인증 전</td></tr>"
        )
    finance = []
    for row in report["financial_research"]:
        finance.append(
            "<tr>" + "".join("<td>"+_safe(v)+"</td>" for v in (
                row["security_id"], row["name"], row["reported_financial_year"],
                _percent(row["revenue_yoy"]),
                _percent(row["operating_income_yoy"]),
                _percent(row["net_income_yoy"]),
                row["price_watch_rank"],
                row["first_local_received_at_utc"],
                "연구 전용·실전 순위 아님",
            ))+"</tr>"
        )
    text = (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 실제 데이터 충족도 · 연구</title><style>"+BASE_CSS+"</style>"
        "</head><body><header><h1>EraLeader · 대장주 데이터 충족도</h1>"
        "<nav><a href='index.html'>메인</a><a href='kr.html'>가격 관찰 1~20위</a>"
        "<a href='official_api.html'>API 원문 수신 요약</a></nav></header>"
        "<main><div class='note'><strong>현재 투자 우선순위는 산출하지 않습니다.</strong><br>"
        "1~20위는 3개월 40% + 6개월 60% 수익률 백분위에 기반한 25점 가격 관찰 순위입니다."
        "종합 100점과 대장주 확정은 PIT·산업·수급·기업행동/상폐 검증 이전이므로 N/A입니다."
        "</div>"
        "<div class='stats'>"
        "<div class='stat'>공식 KRX 당일 관측행<br><strong>"+
        _safe(report["observed_krx_market_rows"])+"</strong></div>"
        "<div class='stat'>현재 DART 기업코드 일치<br><strong>"+
        _safe(report["current_dart_mapping_observed"])+"</strong></div>"
        "<div class='stat'>연결재무 연속 2개 연도 비교 가능한 주권<br><strong>"+
        _safe(report["annual_cfs_comparable_companies"])+"</strong></div>"
        "<div class='stat'>가격 WATCH 표본<br><strong>"+
        _safe(report["price_watch_shown"])+"</strong></div></div>"
        "<h2>5가지 평가 요소별 실제 자료 확보 현황 (공식 역사 PIT 인증 전)</h2>"
        "<div class='wrap'><table><thead><tr><th>평가 요소</th><th>자료 관측 수/공식 당일 거래 관측 수</th>"
        "<th>판정</th></tr></thead><tbody>"+"".join(cells)+"</tbody></table></div>"
        "<h2>공식 DART 연속 2개 사업연도 CFS 연구 대상 (가격 20위 외 기업도 포함)</h2>"
        "<p>성장률은 당초 사업보고서 2개만으로 계산되는 연간 YoY입니다. "
        "3개 연도의 성장 가속도는 아직 검증하지 않았으며, 최초 로컬 확보일 이전 예측으로 기록하지 않습니다.</p>"
        "<div class='wrap'><table><thead><tr>"
        "<th>종목코드</th><th>회사명</th><th>사업연도</th><th>매출 YoY</th>"
        "<th>영업익 YoY</th><th>순이익 YoY</th><th>가격 WATCH 순위</th>"
        "<th>최초 로컬 확보시각</th><th>등급</th></tr></thead><tbody>"+
        "".join(finance)+"</tbody></table></div>"
        "<p><small>시장 관측일 "+_safe(report["market_session"])+
        " / 연구 판단 "+_safe(report["decision_at"])+
        " · 이전 결과 파일에는 수치가 보존되지 않았을 수 있어 N/A로 남깁니다.</small></p>"
        "<p><small>종합 100점/실전 우선순위/전향적 대장주 예측 정확도: N/A</small></p>"
        "</main><footer>EraLeader local-first · 실전 알림 0 · 주문 0</footer></body></html>"
    )
    return text


def write_factor_readiness(report: dict, folder: Path) -> tuple[Path, Path]:
    """Exclusive new JSON+HTML sidecar in the existing new research site.

    Never changes WATCH ranking, the previous generated site or API originals.
    The outer official_kr_daily_pipeline publishes the entire stage atomically.
    """
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir() or any(
            parent.is_symlink() for parent in folder.parents):
        raise ValueError("Readiness output requires an existing unlinked site")
    html = render_factor_readiness(report).encode("utf-8")
    raw = json.dumps(report, ensure_ascii=False, sort_keys=True,
                     indent=2, allow_nan=False).encode("utf-8")+b"\n"
    paths = (folder / "factor_readiness_kr.html", folder.parent / "factor_readiness_kr.json")
    created = []
    try:
        for path, payload in zip(paths, (html, raw)):
            fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        for new_path in created:
            new_path.unlink(missing_ok=True)
        raise
    return paths
