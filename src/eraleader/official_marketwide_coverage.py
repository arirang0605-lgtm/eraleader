"""KRX-wide observed securities joined to available DART finance/industry facts.

This is a *coverage* ledger, not an investment ranking. Missing factors stay
None; a ten-company financial sample is not silently extended to the market.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os
import re

from .delivery import BASE_CSS
from .official_api_pit_bridge import verified_capture, _krx_frame
from .official_dart_multi_company import _all_pinned, source_eligible_universe
from .official_company_explorer import _verified, BASIC, PEER, canonical
from .official_dart_financials import verify_dart_financial, annual_growth_diagnostic
from .official_dart_industry import verify_company_profile
from .discovery import run_id_for

SCHEMA = "eraleader.official_kr_marketwide_factor_coverage.v1"
CODE = re.compile(r"[A-Za-z0-9]{6}\Z")


def build_marketwide_coverage(cohort: Path, capture_root: Path, *,
                              clock: datetime | None = None,
                              extra_cfs_manifests: tuple[Path, ...] = (),
                              extra_industry_manifests: tuple[Path, ...] = ()) -> dict:
    """Recheck pinned originals and join every observed KRX issue exactly once."""
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("MARKETWIDE_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if (not cohort.is_absolute() or cohort.is_symlink() or not cohort.is_dir() or
            not capture_root.is_absolute() or capture_root.is_symlink() or
            any(p.is_symlink() for p in cohort.parents) or
            any(p.is_symlink() for p in capture_root.parents)):
        raise ValueError("MARKETWIDE_SOURCE_DIRECTORY_UNSAFE")
    basic, _ = _verified(cohort / "basic_candidates_kr.json", BASIC)
    peers, _ = _verified(cohort / "industry_peers_kr.json", PEER)
    snapshot = json.loads((cohort / "kr_latest.json").read_bytes())
    evidence = snapshot.get("official_api_evidence")
    if (not isinstance(evidence, dict) or
            evidence.get("historic_universe_pit_verified") is not False or
            evidence.get("official_leaders") != 0 or
            snapshot.get("classification_quality") !=
            "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("MARKETWIDE_SOURCE_NOT_RESEARCH")
    if (run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
            != snapshot.get("run_id")):
        raise ValueError("MARKETWIDE_PRICE_SNAPSHOT_TAMPERED")
    observed = evidence["api_observation_day"]
    if (basic["market_session"] != observed or peers["market_session"] != observed or
            basic["source_watch_run_id"] != snapshot.get("run_id") or
            peers["baseline_candidate_sha256"] != basic["content_sha256"]):
        raise ValueError("MARKETWIDE_COHORT_SOURCE_MISMATCH")
    decision = datetime.fromisoformat(evidence["decision_at"].replace("Z", "+00:00"))
    if decision.tzinfo is None or decision > now:
        raise ValueError("MARKETWIDE_SOURCE_FUTURE")
    matched, directory, audit = source_eligible_universe(
        cohort / "official_api_pit_research.json", capture_root, decision=now)
    if audit["market_session"] != observed:
        raise ValueError("MARKETWIDE_SOURCE_DAY_MISMATCH")
    pins = _all_pinned(capture_root)
    all_rows = {}
    for source in ("krx-kospi", "krx-kosdaq"):
        records = [x for x in evidence["sources"] if x["source"] == source]
        if len(records) != 1 or records[0]["first_receipt_sha256"] not in pins:
            raise ValueError("MARKETWIDE_KRX_PIN_MISSING")
        pin = records[0]["first_receipt_sha256"]
        meta, payload = verified_capture(pins[pin], source, pin, now)
        frame = _krx_frame(source, meta, payload)
        if len(frame) != records[0]["row_count"]:
            raise ValueError("MARKETWIDE_KRX_ROW_MISMATCH")
        for row in frame.itertuples(index=False):
            code = row.security_id
            if (not CODE.fullmatch(code) or code in all_rows or
                    row.session.date().isoformat() != observed):
                raise ValueError("MARKETWIDE_SECURITY_DUPLICATE_OR_WRONG_DATE")
            all_rows[code] = {
                "security_id": code, "name": row.name, "venue": row.venue,
                "market_session": observed, "close": float(row.close),
                "turnover": float(row.turnover), "market_cap": float(row.market_cap),
                "market_traded": bool(row.volume > 0),
                "current_dart_directory_matched": code in matched,
                "revenue_yoy": None, "operating_income_yoy": None,
                "revenue_growth_acceleration": None,
                "industry_code": None, "institutional_flow": None,
                "foreign_flow": None, "price_top20_watch_rank": None,
                "price_strength_25": None, "earnings_research_25": None,
                "two_factor_research_50": None, "two_factor_research_rank": None,
                "partial_financial_observation_order": None,
                "formal_leader_score_100": None, "verified_leader_state": None,
            }
    if len(all_rows) != audit["krx_rows"]:
        raise ValueError("MARKETWIDE_OBSERVED_COUNT_MISMATCH")
    prices = snapshot["rows"]
    if (len({p["security_id"] for p in prices}) != len(prices) or
            len({p["security_id"] for p in basic["comparisons"]}) !=
            len(basic["comparisons"])):
        raise ValueError("MARKETWIDE_DUPLICATE_ANALYSIS")
    for price in prices:
        item=all_rows[price["security_id"]]
        item["price_top20_watch_rank"] = price["rank"]
        item["price_strength_25"] = price.get("price_strength_25")
    for company in basic["comparisons"]:
        code = company["security_id"]
        if code not in matched or company["name"] != all_rows[code]["name"]:
            raise ValueError("MARKETWIDE_FINANCIAL_ISSUER_MISMATCH")
        if datetime.fromisoformat(company[
                "first_financial_locally_received_at_utc"]) > now:
            raise ValueError("MARKETWIDE_FUTURE_FINANCIAL")
        item = all_rows[code]
        item["price_strength_25"] = company.get("price_strength_25")
        item["revenue_yoy"] = company["revenue_yoy"]
        item["operating_income_yoy"] = company["operating_income_yoy"]
        item["revenue_growth_acceleration"] = company["revenue_yoy_acceleration"]
        item["partial_financial_observation_order"] = company["comparison_order"]
    observed_industry = set()
    for company in peers["companies"]:
        code = company["stock_code"]
        if (code in observed_industry or code not in all_rows or
                all_rows[code]["revenue_yoy"] is None):
            raise ValueError("MARKETWIDE_INDUSTRY_JOIN_INVALID")
        observed_industry.add(code)
        all_rows[code]["industry_code"] = company["current_industry_code"]
    if (observed_industry != {x["security_id"] for x in basic["comparisons"]} or
            peers["selected_companies"] != len(observed_industry)):
        raise ValueError("MARKETWIDE_FINANCE_INDUSTRY_COHORT_MISMATCH")
    extras = set()
    incomplete = set()
    manifest_pins = []
    for manifest_file in extra_cfs_manifests:
        if (not manifest_file.is_absolute() or manifest_file.is_symlink() or
                not manifest_file.is_file() or
                any(p.is_symlink() for p in manifest_file.parents)):
            raise ValueError("MARKETWIDE_EXTRA_MANIFEST_UNSAFE")
        raw = manifest_file.read_bytes()
        source = json.loads(raw)
        if (source.get("schema") != "eraleader.dart_bounded_multi_company_cfs.v1" or
                source.get("official_market", {}).get("market_session") != observed or
                source.get("research_only") is not True or
                source.get("real_investment_leader_ranked") is not False):
            raise ValueError("MARKETWIDE_EXTRA_CFS_SOURCE_INVALID")
        manifest_pins.append(sha256(raw).hexdigest())
        for firm in source["companies"]:
            code = firm["stock_code"]
            if (code in extras or code not in matched or
                    code not in all_rows or
                    all_rows[code]["revenue_yoy"] is not None or
                    firm["name"] != all_rows[code]["name"] or
                    code in incomplete):
                raise ValueError("MARKETWIDE_EXTRA_CFS_IDENTITY_OR_DUPLICATE")
            if not firm["research_annual_cfs_complete"]:
                incomplete.add(code)
                continue
            annual = {}
            for receipt in firm["annual_reports"]:
                year = receipt["fiscal_year"]
                pin = receipt["first_receipt_sha256"]
                if year in annual or pin not in pins:
                    raise ValueError("MARKETWIDE_EXTRA_CFS_RECEIPT_MISSING")
                verified = verify_dart_financial(pins[pin], pin,
                                                 decision_at=now,
                                                 directory=directory)
                if (verified["stock_code"] != code or
                        verified["year"] != year or
                        verified["statement"] != "CFS" or
                        verified["report_code"] != "11011"):
                    raise ValueError("MARKETWIDE_EXTRA_CFS_WRONG_ISSUER")
                annual[year] = verified
            years = sorted(annual)
            if len(years) != 2 or years[1] != years[0] + 1:
                raise ValueError("MARKETWIDE_EXTRA_CFS_TWO_CONSECUTIVE_YEARS_REQUIRED")
            growth = annual_growth_diagnostic(annual[years[0]],annual[years[1]])
            item = all_rows[code]
            item["revenue_yoy"] = growth["research_metrics"]["revenue_yoy"]
            item["operating_income_yoy"] = growth["research_metrics"]["operating_income_yoy"]
            item["financial_receipt_years"] = years
            extras.add(code)
    extra_industry = set()
    industry_pins = []
    for manifest_file in extra_industry_manifests:
        if (not manifest_file.is_absolute() or manifest_file.is_symlink() or
                not manifest_file.is_file() or
                any(p.is_symlink() for p in manifest_file.parents)):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_UNSAFE")
        raw = manifest_file.read_bytes()
        source = json.loads(raw)
        if (source.get("schema") != "eraleader.dart_industry_profile_cohort.v1" or
                source.get("source_directory_sha256") != directory[1] or
                source.get("historic_industry_pit_certified") is not False):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_INVALID")
        industry_pins.append(sha256(raw).hexdigest())
        if (source.get("companies_requested") != len(source.get("companies",[]))):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_COUNT")
        for firm in source["companies"]:
            code = firm["stock_code"]
            if (code not in matched or code in extra_industry or
                    code in observed_industry or code not in extras):
                raise ValueError("MARKETWIDE_INDUSTRY_COMPANY_NOT_FINANCIAL")
            extra_industry.add(code)
            pin=firm.get("first_receipt_sha256")
            if pin is None:
                continue
            if pin not in pins:
                raise ValueError("MARKETWIDE_INDUSTRY_FIRST_PIN_MISSING")
            profile = verify_company_profile(pins[pin],pin,
                       directory=directory,decision_at=now)
            if (profile["stock_code"] != code or
                    profile["current_dart_industry_code"] != firm.get(
                        "current_dart_industry_code") or
                    profile["current_dart_industry_code"] is None):
                raise ValueError("MARKETWIDE_INDUSTRY_RECEIPT_MISMATCH")
            all_rows[code]["industry_code"] = profile["current_dart_industry_code"]
    # P2 first executable comparison: observed momentum+earnings only.
    # Missing industry growth, competitive moat or institution flows must NEVER
    # be zero-filled into the official 100-point leader model.
    comparable=[]
    for item in all_rows.values():
        a,b,p=(item["revenue_yoy"],item["operating_income_yoy"],
               item["price_strength_25"])
        if any(x is None for x in (a,b,p)):
            continue
        if any(type(x) not in (int,float) or not math.isfinite(x)
               for x in (a,b,p)) or not 0 <= p <= 25:
            raise ValueError("MARKETWIDE_PARTIAL_SCORE_INVALID_INPUT")
        earnings=round(12.5*min(max(a,0)/0.40,1)+
                       12.5*min(max(b,0)/0.60,1),6)
        item["earnings_research_25"]=earnings
        item["two_factor_research_50"]=round(p+earnings,6)
        comparable.append(item)
    comparable.sort(key=lambda x:(-x["two_factor_research_50"],
                                  -x["price_strength_25"],x["security_id"]))
    for ix,item in enumerate(comparable,1):
        item["two_factor_research_rank"]=ix
    rows = [all_rows[k] for k in sorted(all_rows)]
    result = {
        "schema": SCHEMA, "market": "KR", "market_session": observed,
        "source_decision_at_utc": decision.isoformat(),
        "built_at_utc": now.isoformat(),
        "source_watch_run_id": snapshot["run_id"],
        "source_basic_sha256": basic["content_sha256"],
        "source_industry_sha256": peers["content_sha256"],
        "official_krx_observed": len(rows),
        "current_dart_directory_matched": len(matched),
        "financial_factors_observed": len(basic["comparisons"]) + len(extras),
        "extra_cfs_manifests_sha256": manifest_pins,
        "incomplete_additional_financial_companies": len(incomplete),
        "industry_factors_observed": sum(
            x["industry_code"] is not None for x in rows),
        "extra_industry_manifests_sha256": industry_pins,
        "flow_factors_observed": 0,
        "two_factor_research_evaluable":len(comparable),
        "two_factor_research_top20":[
            {"research_order":x["two_factor_research_rank"],
             "security_id":x["security_id"],"name":x["name"],
             "observed_score_50":x["two_factor_research_50"],
             "official_leader":False} for x in comparable[:20]],
        "two_factor_scoring_note":(
            "RESEARCH ONLY. Price: existing 0..25 momentum; "
            "earnings: sales YoY capped 40% (12.5pt), operating YoY "
            "capped 60% (12.5pt); negative growth floor 0. "
            "Industry/competition/flow unscored N/A. Not a 100-point rank."),
        "official_leaders": 0, "research_only": True,
        "full_market_composite_rank_available": False,
        "warning": ("KRX prices are a pinned single-day observation. "
                    "Financial/industry facts were received later than the price date; "
                    "historic issuer/class and availability PIT are not certified."),
        "securities": rows,
    }
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    return result


def publish_marketwide_coverage(report: dict, dest: Path) -> tuple[Path, Path]:
    """Write separate immutable JSON and HTML without altering WATCH history."""
    digest = report.get("content_sha256")
    original = dict(report)
    original.pop("content_sha256", None)
    if (report.get("schema") != SCHEMA or
            report.get("full_market_composite_rank_available") is not False or
            report.get("official_leaders") != 0 or
            sha256(canonical(original)).hexdigest() != digest):
        raise ValueError("MARKETWIDE_REPORT_INVALID")
    if (not dest.is_absolute() or dest.exists() or dest.is_symlink() or
            not dest.parent.is_dir() or dest.parent.is_symlink() or
            any(p.is_symlink() for p in dest.parents)):
        raise ValueError("MARKETWIDE_DESTINATION_UNSAFE")
    dest.mkdir(mode=0o700)
    jsonfile, page = dest / "marketwide_kr.json", dest / "index.html"
    highlights = sorted((r for r in report["securities"]
                         if r["price_top20_watch_rank"] is not None),
                        key=lambda r: r["price_top20_watch_rank"])
    body = "".join(
        "<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in (
            r["price_top20_watch_rank"], r["security_id"], r["name"],
            "Y" if r["revenue_yoy"] is not None else "N/A",
            r["industry_code"] or "N/A", "N/A")) + "</tr>"
        for r in highlights)
    research_rows = "".join("<tr>"+"".join("<td>"+
        escape(str(value))+"</td>" for value in
        (x["research_order"],x["security_id"],x["name"],x["observed_score_50"]))+
        "</tr>" for x in report.get("two_factor_research_top20",[]))
    html = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>EraLeader KR 전시장 자료 결합 현황</title><style>" + BASE_CSS +
        "</style><main><h1>한국 전체시장 자료 결합 현황</h1><p>실제 거래관측일 " +
        escape(report["market_session"]) + " / 기준 UTC " +
        escape(report["built_at_utc"]) + "</p><p>KRX " +
        str(report["official_krx_observed"]) + "종목 · DART 현재 기업매칭 " +
        str(report["current_dart_directory_matched"]) + " · 재무 " +
        str(report["financial_factors_observed"]) + " · 산업 " +
        str(report["industry_factors_observed"]) + " · 공식 수급 " +
        str(report["flow_factors_observed"]) + "</p><p><strong>"
        "가격 관찰 TOP20은 투자/대장주 종합 순위가 아닙니다. "
        "자료 부족 종목·분야는 N/A, 확정 대장주 0.</strong></p>"
        "<table><thead><tr><th>가격 관찰순서</th><th>종목코드</th>"
        "<th>종목명</th><th>재무 확보</th><th>산업코드</th><th>수급</th>"
        "</tr></thead><tbody>" + body + "</tbody></table>"
        "<h2>가격·실적 2요소 연구 비교 TOP20 (50점, 투자 우선순위 아님)</h2>"
        "<p>2요소 평가 가능 "+str(report.get("two_factor_research_evaluable",0))+
        "종목 한정. 산업성장·기업경쟁력·외국인기관 수급은 N/A.</p>"
        "<table><thead><tr><th>비교 순서</th><th>종목</th><th>회사</th>"
        "<th>관측점수 /50</th></tr></thead><tbody>"+research_rows+"</tbody></table>"
        "<p>전체 KRX 종목별 자료 확보 여부: marketwide_kr.json (동일 폴더). "
        "재무/산업은 현재 수집 표본이며 과거 주권 PIT 인증은 N/A.</p>"
        "</main></html>")
    try:
        jsonfile.write_bytes(canonical(report) + b"\n")
        page.write_text(html, encoding="utf-8")
        os.chmod(jsonfile, 0o600)
        os.chmod(page, 0o600)
    except BaseException:
        jsonfile.unlink(missing_ok=True)
        page.unlink(missing_ok=True)
        dest.rmdir()
        raise
    return jsonfile, page
