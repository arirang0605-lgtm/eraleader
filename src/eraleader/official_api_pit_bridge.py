"""Receipt-verified official observations -> existing price WATCH research pipeline.

KRX daily trading data is a single-day observation, NOT a historic PIT universe.
DART and SEC are linked as evidence only until issuers/classes and disclosure
release times can be independently joined. No backfilled first-WATCH claims.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import stat

import pandas as pd

from .data import LEGACY_DEFAULT, read_market_bars, validate_bars
from .discovery import score_price_observations, run_id_for
from .official_api_capture import _canonical, _decoded, SCHEMA as RAW_SCHEMA
from .cli import execute_run, execute_report, execute_alerts, write_json
from .offline_pit import OfflineLedger
from .research import integrated_snapshot
from .delivery import write_integrated_dashboard

SCHEMA = "eraleader.official_api_pit_research_bridge.v1"
NUMBERS = ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "TDD_CLSPRC",
           "ACC_TRDVOL", "ACC_TRDVAL", "MKTCAP")


def _private_file(path: Path, mode: int) -> bytes:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_uid != os.geteuid() or
            stat.S_IMODE(path.stat().st_mode) & 0o077 or
            not (stat.S_IMODE(path.stat().st_mode) & stat.S_IRUSR)):
        raise ValueError("Official evidence must be owner-only, no symlinks")
    return path.read_bytes()


def verified_capture(folder: Path, expected_source: str, expected_sha: str,
                     decision: datetime) -> tuple[dict, dict]:
    """Requires a supplied SHA of the original first receipt; never backdates."""
    folder = Path(folder)
    if (not folder.is_absolute() or folder.is_symlink() or
            not folder.is_dir() or folder.stat().st_uid != os.geteuid() or
            stat.S_IMODE(folder.stat().st_mode) != 0o700 or
            folder.parent.is_symlink() or
            not isinstance(expected_sha, str) or
            not re.fullmatch("[0-9a-f]{64}", expected_sha)):
        raise ValueError("Private capture directory and first receipt PIN required")
    first = _private_file(folder / "first_receipt.json", 0o600)
    raw = _private_file(folder / "raw_response.json", 0o600)
    if sha256(first).hexdigest() != expected_sha:
        raise ValueError("Official first receipt SHA pin mismatch")
    try:
        receipt = json.loads(first)
        body = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Malformed official capture JSON") from exc
    if (receipt.get("schema") != RAW_SCHEMA or
            receipt.get("source") != expected_source or
            receipt.get("raw_sha256") != sha256(raw).hexdigest() or
            receipt.get("raw_length_bytes") != len(raw) or
            receipt.get("official_leader_promotions") != 0 or
            receipt.get("full_historic_universe_pit_certified") is not False):
        raise ValueError("Official first receipt evidence invalid")
    observed = datetime.fromisoformat(receipt["first_local_received_at_utc"].replace("Z", "+00:00"))
    if (observed.tzinfo is None or observed > decision or
            observed.year < 2000):
        raise ValueError("Official source was not locally available at decision timestamp")
    val = receipt.get("request_value")
    if expected_source.startswith("krx-") or expected_source == "dart-disclosures":
        date.fromisoformat(val)
        count, quality = _decoded(raw, expected_source, day=val, cik=None)
    else:
        count, quality = _decoded(raw, expected_source, day=None, cik=str(val))
    if count != receipt.get("provider_row_count") or quality != receipt.get("quality"):
        raise ValueError("Official receipt contents differ from original API response")
    return receipt, body


def _number(value: object, *, nonnegative: bool = False) -> int:
    if type(value) is not str or not re.fullmatch(r"(0|[1-9][0-9]{0,18})(,[0-9]{3})*", value):
        raise ValueError("Invalid KRX numeric field")
    number = int(value.replace(",", ""))
    if number < 0 or (not nonnegative and number == 0):
        raise ValueError("Invalid KRX positive field")
    return number


def _krx_frame(source: str, meta: dict, payload: dict) -> pd.DataFrame:
    day = meta["request_value"]
    venue = "KOSPI" if source == "krx-kospi" else "KOSDAQ"
    used = set()
    rows = []
    for r in payload["OutBlock_1"]:
        code = r["ISU_CD"]
        if (type(code) is not str or not re.fullmatch(r"[A-Za-z0-9]{6}", code) or
                code in used or r["BAS_DD"] != day.replace("-", "") or
                type(r.get("ISU_NM")) is not str or not r["ISU_NM"].strip()):
            raise ValueError("KRX duplicate/invalid identity or date")
        used.add(code)
        nums = [_number(r.get(k), nonnegative=k in (
            "TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "ACC_TRDVOL", "ACC_TRDVAL"))
            for k in NUMBERS]
        op, high, low, close, volume, turnover, cap = nums
        halted = op == high == low == volume == 0 and close > 0
        if not halted and (op <= 0 or high < max(op, low, close) or
                           low <= 0 or low > min(op, high, close)):
            raise ValueError("KRX nontradable/invalid OHLC must not rank")
        rows.append({"security_id":code, "name":r["ISU_NM"], "venue":venue,
                     "session":pd.Timestamp(day), "open":op, "high":high,
                     "low":low, "close":close, "volume":volume,
                     "turnover":turnover, "market_cap":cap})
    if not rows:
        raise ValueError("Official KRX daily capture contains no observations")
    return pd.DataFrame(rows)


def build_official_price_snapshot(*, kospi: tuple[Path, str],
                                  kosdaq: tuple[Path, str],
                                  decision_at: str, as_of: str,
                                  legacy_root: Path = LEGACY_DEFAULT,
                                  days: int = 550, top: int = 20,
                                  auxiliary: tuple[tuple[str, Path, str], ...] = (),
                                  dart_complete: tuple[Path, str, Path, str] | None = None,
                                  dart_directory: tuple[Path,str] | None = None,
                                  dart_financial_receipts: tuple[tuple[Path,str],...] = ()) -> dict:
    """All evidence is fully preflighted before any public research writes."""
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    if decision.tzinfo is None or decision.utcoffset() is None:
        raise ValueError("Explicit timezone-aware decision is required")
    decision = decision.astimezone(timezone.utc)
    asof_day = date.fromisoformat(as_of)
    if asof_day != decision.astimezone(ZoneInfo("Asia/Seoul")).date():
        raise ValueError("KR decision as-of must equal first published research day, not backdate")
    captures = []
    frames = []
    for src, spec in (("krx-kospi", kospi), ("krx-kosdaq", kosdaq)):
        meta, payload = verified_capture(spec[0], src, spec[1], decision)
        if date.fromisoformat(meta["request_value"]) > asof_day:
            raise ValueError("Future KRX session compared with requested as-of")
        frames.append(_krx_frame(src, meta, payload))
        captures.append({"source":src, "first_receipt_sha256":spec[1],
                         "raw_sha256":meta["raw_sha256"],
                         "row_count":meta["provider_row_count"],
                         "first_local_received_at_utc":meta["first_local_received_at_utc"],
                         "quality":meta["quality"]})
    if captures[0]["row_count"] + captures[1]["row_count"] != sum(len(x) for x in frames):
        raise ValueError("Official KRX daily totals mismatch")
    if frames[0]["session"].iloc[0] != frames[1]["session"].iloc[0]:
        raise ValueError("KRX two exchanges must share the same session")
    current = pd.concat(frames, ignore_index=True)
    if current.duplicated(["security_id", "session"]).any():
        raise ValueError("KRX cross-exchange duplicate security identifier")
    session = current["session"].iloc[0].date()
    if (asof_day - session).days > 10:
        raise ValueError("Official KRX daily price too stale for a research decision")
    extra = []
    for source, folder, pinned in auxiliary:
        if source not in ("dart-disclosures", "sec-submissions", "sec-companyfacts"):
            raise ValueError("Unsupported secondary official source")
        meta, _ = verified_capture(folder, source, pinned, decision)
        extra.append({"source":source, "first_receipt_sha256":pinned,
                      "raw_sha256":meta["raw_sha256"],
                      "row_count":meta["provider_row_count"],
                      "quality":meta["quality"],
                      "first_local_received_at_utc":meta["first_local_received_at_utc"],
                      "pit_fact_joined":False})
    dart_full = None
    dart_code_map = {}
    observed_day_codes = set()
    if dart_complete is not None:
        from .official_dart_daily import (
            verify_dart_day, observed_dart_stock_links, observed_dart_unique_corp_map,
        )
        if len(dart_complete) != 4:
            raise ValueError("DART complete receipt needs original first-pinned capture")
        full_path, full_sha, original_path, original_pin = dart_complete
        for source in extra:
            if (source["source"] == "dart-disclosures" and
                    source["first_receipt_sha256"] != original_pin):
                raise ValueError("DART first receipt differs between auxiliary and full-day evidence")
        full = verify_dart_day(full_path, full_sha, first_folder=original_path,
                               first_sha=original_pin, decision_at=decision)
        if full["market_day"] != session.isoformat():
            raise ValueError("DART/KRX observed market session must match")
        krx_codes = set(current["security_id"].tolist())
        links = observed_dart_stock_links(full["rows"], krx_codes)
        dart_code_map = observed_dart_unique_corp_map(full["rows"], krx_codes)
        observed_day_codes = set(dart_code_map)
        if len(dart_code_map) != links["observed_matching_security_count"]:
            raise ValueError("DART observed issuer overlap count inconsistent")
        dart_full = {
            "source":"dart-complete-day", "market_day":full["market_day"],
            "manifest_sha256":full_sha, "first_receipt_sha256":original_pin,
            "row_count":full["total_rows"], "page_count":full["total_pages"],
            "first_available_after_page":full["last_received_at_utc"],
            "issuer_links":links,
            "historic_pit_certified":False,
            "financial_pit_joined":False,
        }
    directory_audit = None
    if dart_directory is not None:
        from .official_dart_corp_directory import (
            verify_dart_corp_directory, match_krx_codes,
        )
        if len(dart_directory)!=2:
            raise ValueError("DART directory capture and SHA required")
        d=verify_dart_corp_directory(dart_directory[0],dart_directory[1],
                                      decision_at=decision)
        all_codes=set(current["security_id"])
        directory_audit={
            "source":"dart-current-corp-directory",
            "first_receipt_sha256":d["first_receipt_sha256"],
            "first_local_received_at_utc":d["first_local_received_at_utc"],
            "total_corporations":d["total_corporations"],
            **match_krx_codes(d,all_codes),
        }
        for code,corp in dart_code_map.items():
            # A same-day DART disclosure and today's master file conflict:
            # never invent which legal issuer identity is right.
            if code in d["mapping"] and d["mapping"][code] != corp:
                raise ValueError("DART day and current directory corp IDs disagree")
        dart_code_map={**d["mapping"],**dart_code_map}
    # Optional, individually first-received CFS report receipts for exact
    # current matched DART companies. Missing reports remain N/A, not zero.
    dart_financial_stats = {}
    dart_financial_receipts_info = []
    if dart_financial_receipts:
        if dart_directory is None or len(dart_financial_receipts)>100:
            raise ValueError("DART financial statements need current pinned company directory")
        from .official_dart_financials import (
            verify_dart_financial, annual_growth_diagnostic,
        )
        by_ticker={}
        for folder,pin in dart_financial_receipts:
            report=verify_dart_financial(folder,pin,decision_at=decision,
                                         directory=dart_directory)
            ticker=report["stock_code"]
            if (ticker not in set(current["security_id"]) or
                    dart_code_map.get(ticker)!=report["corp_code"] or
                    report.get("statement")!="CFS" or
                    report.get("report_code")!="11011"):
                raise ValueError("DART annual CFS report source not matched to KRX code")
            key=(report["year"],report["report_code"])
            if key in by_ticker.setdefault(ticker,{}):
                raise ValueError("Duplicate annual DART first-report vintage")
            by_ticker[ticker][key]=report
            dart_financial_receipts_info.append({"stock_code":ticker,
                "report_year":report["year"],"first_receipt_sha256":pin,
                "first_local_received_at_utc":report["first_local_received_at_utc"],
                "reported_accounts":len(report["metrics"]), "pit_certified":False})
        for ticker,years in by_ticker.items():
            complete=sorted(y for y,form in years if form=="11011")
            if len(complete)==2 and complete[1]==complete[0]+1:
                dart_financial_stats[ticker]=annual_growth_diagnostic(
                    years[(complete[0],"11011")],years[(complete[1],"11011")])
    # Prior cache observations provide *research lookback*, not official PIT
    # provenance. Never silently select a cached bar over an official session.
    bars, quality = read_market_bars("KR", asof_day, days=days, legacy_root=legacy_root)
    old = bars.loc[bars["session"].dt.date < session].copy()
    merged = pd.concat([old, current], ignore_index=True)
    merged = validate_bars(merged, asof_day, quarantine=False)
    snap = score_price_observations(merged, "KR", as_of, top)
    snap["data_source"] = "KRX official single-day daily trade + prior unverified local marcap lookback"
    quality["source"] = snap["data_source"]
    quality["official_daily_rows"] = len(current)
    quality["official_first_received_after_market_session"] = True
    quality["api_pit_certified"] = False
    quality["official_market_day"] = session.isoformat()
    quality["local_cache_lookback_unverified"] = True
    snap["quality_flags"] = quality
    # Bind existing run-ID calculation to the immutable API evidence chain.
    # Identical prices re-published with different first receipts are different runs.
    pin_digest = sha256(_canonical({"sources": captures + extra, "dart_full":dart_full,
                                    "dart_directory":directory_audit,
                                    "dart_financial_receipts":dart_financial_receipts_info})).hexdigest()
    for row in snap["rows"]:
        row["official_api_source_digest_sha256"] = pin_digest
        if dart_complete is not None or dart_directory is not None:
            # Observed corporate code only from a receipt-pinned current DART vintage.
            # A missing disclosure never disproves listing or identity.
            row["observed_dart_corp_code"] = dart_code_map.get(row["security_id"])
            row["observed_dart_corp_code_pit_certified"] = False
            if dart_financial_receipts:
                row["dart_financial_annual_growth_research"] = (
                    dart_financial_stats[row["security_id"]]["research_metrics"]
                    if row["security_id"] in dart_financial_stats else None
                )
                row["dart_financial_pit_certified"] = False
            row["observed_dart_corp_code_source"] = (
                "day-disclosure" if row["security_id"] in observed_day_codes
                else "current-directory"
            ) if row["observed_dart_corp_code"] else None
    snap["run_id"] = run_id_for("KR", as_of, snap["rows"])
    snap["official_api_evidence"] = {
        "schema": SCHEMA, "decision_at": decision.isoformat(),
        "api_observation_day": session.isoformat(),
        "sources": captures + extra,
        "dart_full_day": dart_full,
        "dart_current_directory":directory_audit,
        "dart_financial_first_receipts":dart_financial_receipts_info,
        "dart_financial_comparable_companies":len(dart_financial_stats),
        "historic_universe_pit_verified": False,
        "issuer_share_class_verified": False,
        "dart_sec_financial_pit_joined": False,
        "official_leaders": 0,
        "watch_type": "PRICE_ONLY_RESEARCH_NOT_CERTIFIED",
    }
    snap["note"] += " | 공식 일봉 1일 외 이력은 미인증 캐시이며 최초 API 수신 이전 성과는 소급하지 않습니다."
    return snap


def run_official_research(snapshot: dict, out: Path, *, pit_ledger: Path | None = None) -> dict:
    """Reuse exactly the existing WATCH/SQLite, dashboards and report generators."""
    out = Path(out)
    if not out.is_absolute() or out.is_symlink():
        raise ValueError("Research output must be an absolute nonlinked path")
    ev = snapshot["official_api_evidence"]
    as_of = snapshot["as_of_requested"]
    if ev["official_leaders"] != 0 or ev["historic_universe_pit_verified"]:
        raise ValueError("Official API alone cannot promote leader status")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a fresh output folder for first API evidence, no overwrite")
    # Existing PIT contract is read-only and explicitly optional. A raw KRX
    # 6-character exchange code is NOT proof of a permanent issuer/class ID.
    joined = None
    if pit_ledger is not None:
        ledger = OfflineLedger.open_readonly(Path(pit_ledger))
        try:
            offline = ledger.snapshot(ev["decision_at"], market="KR")
            joined = integrated_snapshot(offline, snapshot, ev["decision_at"])
        finally:
            ledger.close()
        if joined["pit_certified"] or joined["confirmed_leaders"]:
            raise ValueError("Raw KRX evidence cannot certify an issuer/class PIT snapshot")
    result = execute_run(Namespace(market="KR", as_of=as_of, out=out,
                                   prepared_snapshot=snapshot, days=550, top=snapshot["shown"]))
    reports = [execute_report(Namespace(market="KR", period=p, out=out))["path"]
               for p in ("daily", "weekly", "monthly")]
    alerts = execute_alerts(Namespace(out=out))
    write_json(out / "official_api_pit_research.json", ev)
    if joined is not None:
        write_json(out / "official_pit_integrated_research.json", joined)
        write_integrated_dashboard(joined, out / "site")
    page = out / "site" / "official_api.html"
    c = ev["sources"]
    lines = "".join("<tr><td>"+escape(s["source"])+"</td><td>"+
                    str(s["row_count"])+"</td><td>"+escape(s["quality"])+
                    "</td></tr>" for s in c)
    page.write_text(
        "<!doctype html><html lang='ko'><meta charset='utf-8'><title>EraLeader API 연구 증거</title>"
        "<style>body{font:16px sans-serif;max-width:1000px;margin:40px auto;line-height:1.7}"
        "th,td{padding:8px;border:1px solid #aaa}table{border-collapse:collapse}</style>"
        "<h1>EraLeader 공식 API 수신 연구</h1><p>KRX 일봉: " +
        escape(ev["api_observation_day"]) + " / 최초 관측 이후 판단: " +
        escape(ev["decision_at"]) + "</p><p><strong>WATCH = 가격 관찰만 가능.</strong> "
        "상장/주권 클래스/기업행동/공시 PIT 인증 없음. DART/SEC 재무 반영 없음. "
        "과거 캐시는 공식 API 관측 이력이 아니며 전향적 적중률은 N/A.</p>"
        "<table><tr><th>공급자</th><th>확보된 원본 행/항목</th><th>품질</th></tr>" +
        lines + "</table>" +
        ("<p>최초수신 DART 연결재무제표 연간 성장률 비교 가능 종목 " +
         str(ev["dart_financial_comparable_companies"]) +
         "개 (관측일 이후 연구용; 역사적 공시 PIT 인증 전).</p>"
         if ev.get("dart_financial_first_receipts") else "") +
        ("<p>DART 공시대상 기업 현재 고유번호 목록 " +
         str(ev["dart_current_directory"]["total_corporations"]) +
         "개, KRX 종목코드와 현재 교집합 " +
         str(ev["dart_current_directory"]["matched_unique_dart_corporation"]) +
         "개 (역사적 상장·주권 식별 인증 아님).</p>"
         if ev.get("dart_current_directory") else "") +
        ("<p>DART 일자 전체 공시 " + str(ev["dart_full_day"]["row_count"]) +
         "건 / " + str(ev["dart_full_day"]["page_count"]) +
         "페이지 검증 완료. 같은 거래일 관측 주권코드 교집합 " +
         str(ev["dart_full_day"]["issuer_links"]["observed_matching_security_count"]) +
         "종목 (법적 issuer/share class 인증·재무 PIT 아님).</p>"
         if ev.get("dart_full_day") else "") +
        "<p><a href='kr.html'>한국 WATCH 목록</a></p></html>",
        encoding="utf-8")
    index = out / "site" / "index.html"
    pit_link = (" <a href='research_kr.html'>PIT 원장·가격 시점결합 연구</a>" if joined is not None else "")
    index.write_text(index.read_text(encoding="utf-8").replace(
        "</body>", "<p><a href='official_api.html'>공식 API 최초 수신·PIT 제한</a>"+pit_link+"</p></body>"),
        encoding="utf-8")
    return {"status": "OFFICIAL_API_TO_RESEARCH_WATCH_AND_REPORTS",
            "krx_rows": sum(s["row_count"] for s in c if s["source"].startswith("krx")),
            "watch_count": snapshot["shown"], "reports": len(reports),
            "reports_paths": [str(x) for x in reports],
            "alert_dry_run_count": alerts["count"], "messages_sent": 0,
            "official_leaders": 0, "pit_certified": False,
            "dashboard": str(page), "market_dashboard": result["dashboard"],
            "dart_full_rows": ev["dart_full_day"]["row_count"] if ev.get("dart_full_day") else 0,
            "dart_observed_matching_codes": (ev["dart_full_day"]["issuer_links"]["observed_matching_security_count"]
                                             if ev.get("dart_full_day") else 0),
            "pit_join_status": ("PIT_LEDGER_RESEARCH_ONLY_NOT_CERTIFIED" if joined is not None
                                else "NO_HISTORIC_ISSUER_CLASS_PIT_LEDGER"),
            "dart_financial_comparable_companies": ev.get("dart_financial_comparable_companies",0),
            "dart_directory_matching_codes": (
                ev["dart_current_directory"]["matched_unique_dart_corporation"]
                if ev.get("dart_current_directory") else 0),
            "pit_company_count": joined["company_count"] if joined is not None else 0,
            "evidence_json": str(out / "official_api_pit_research.json"),
            "api_first_observation": ev["decision_at"]}
