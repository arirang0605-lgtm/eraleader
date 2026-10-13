"""Bounded multi-company DART annual CFS collection from real KRX observations.

Core EraLeader research: use the ORIGINAL KRX/DART first SHA receipts, then
reuse capture_dart_financial, never fabricate ratios or investment priorities.
No auth material/raw financial statement is written to public Git.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import time
import pandas as pd

from .official_api_pit_bridge import verified_capture, _krx_frame
from .official_dart_corp_directory import verify_dart_corp_directory
from .official_dart_financials import capture_dart_financial,verify_dart_financial

SCHEMA="eraleader.dart_bounded_multi_company_cfs.v1"
CODE=re.compile(r"[0-9]{6}\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
MAX_COMPANIES=12


def _read_json(path: Path) -> dict:
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not p.is_absolute():
        raise ValueError("Official private source input must be a regular absolute file")
    obj=json.loads(p.read_bytes())
    if type(obj) is not dict:
        raise ValueError("Official evidence must be a dict")
    return obj


def _all_pinned(root: Path) -> dict[str, Path]:
    if (root.is_symlink() or not root.is_dir() or
            not root.is_absolute() or
            os.stat(root).st_uid!=os.geteuid()):
        raise ValueError("Original source root must be private")
    found={}
    for file in root.glob("*/first_receipt.json"):
        if file.is_symlink() or file.parent.is_symlink():
            raise ValueError("Original receipt symlink not allowed")
        if len(found)>1000:
            raise ValueError("Too many first-receipt records")
        pin=sha256(file.read_bytes()).hexdigest()
        if pin in found:
            raise ValueError("Ambiguous original receipt SHA")
        found[pin]=file.parent
    return found


def source_eligible_universe(evidence_file: Path, private_root: Path, *,
                             decision: datetime) -> tuple[dict,tuple[Path,str],dict]:
    """Actual trading-day KRX share codes intersect current DART directory."""
    evidence=_read_json(evidence_file)
    if (evidence.get("schema")!="eraleader.official_api_pit_research_bridge.v1" or
            evidence.get("official_leaders")!=0 or
            evidence.get("historic_universe_pit_verified") is not False):
        raise ValueError("Research-only real provider original summary required")
    sources=evidence.get("sources")
    if type(sources) is not list:
        raise ValueError("Official KRX first-source receipt summary missing")
    pins=_all_pinned(private_root)
    market={}
    sessions=set()
    for row in sources:
        if row.get("source") not in ("krx-kospi","krx-kosdaq"):
            continue
        pin=row.get("first_receipt_sha256")
        if pin not in pins or not SHA.fullmatch(pin):
            raise ValueError("Unknown first KRX original receipt")
        original,payload=verified_capture(pins[pin],row["source"],pin,decision)
        frame=_krx_frame(row["source"],original,payload)
        sessions.update(str(pd.Timestamp(s).date()) for s in frame["session"].unique())
        for ticker,name,venue in frame[["security_id","name","venue"]].itertuples(index=False,name=None):
            if ticker in market:
                raise ValueError("Duplicate KRX issuer ticker across markets")
            market[ticker]={"name":name,"venue":venue}
    if len(sessions)!=1 or not market:
        raise ValueError("Official single KRX trading session required")
    d=evidence.get("dart_current_directory")
    if type(d) is not dict or d.get("historical_pit_certified") is not False:
        raise ValueError("Current DART directory must be unpromoted")
    pin=d["first_receipt_sha256"]
    if pin not in pins or not SHA.fullmatch(pin):
        raise ValueError("Unknown DART current issuer original receipt")
    directory=(pins[pin],pin)
    checked=verify_dart_corp_directory(*directory,decision_at=decision)
    matched={key:val for key,val in market.items() if key in checked["mapping"]}
    if not matched:
        raise ValueError("No real official KRX+DART intersection")
    return matched,directory,{"market_session":next(iter(sessions)),
         "krx_rows":len(market),"dart_unique_matches":len(matched),
         "current_issuer_class_pit_certified":False}



def choose_price_watch_company_batch(snapshot: dict, official_evidence: dict,
                                     eligible: dict, *, start_rank: int = 1,
                                     limit: int = 12) -> tuple[str, ...]:
    """Reuse the existing real KRX price WATCH order to automate bounded CFS batches.

    This is an API collection queue, never investment priority. An unmatched
    share class is skipped rather than mapped to a similarly named company.
    """
    if (type(start_rank) is not int or not 1 <= start_rank <= 3000 or
            type(limit) is not int or not 1 <= limit <= MAX_COMPANIES):
        raise ValueError("Bounded price watch capture page required")
    current = snapshot.get("official_api_evidence")
    if (type(current) is not dict or
            current != official_evidence or
            current.get("historic_universe_pit_verified") is not False or
            current.get("official_leaders") != 0 or
            snapshot.get("classification_quality") !=
            "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("Price-watch input not backed by the same official receipt")
    rows = snapshot.get("rows")
    if type(rows) is not list or not rows:
        raise ValueError("Actual price-watch observation is required")
    from .discovery import run_id_for
    if (run_id_for("KR",snapshot["as_of_requested"],rows)
            != snapshot.get("run_id")):
        raise ValueError("Price-watch row integrity mismatch")
    ordered = sorted(rows, key=lambda x:x["rank"])
    if (len({r["rank"] for r in ordered}) != len(ordered) or
            len({r["security_id"] for r in ordered}) != len(ordered)):
        raise ValueError("Duplicate source observation rank/security")
    if [r["rank"] for r in ordered] != list(range(1,len(ordered)+1)):
        raise ValueError("Incomplete price-watch ordering")
    choices=[]
    for row in ordered:
        if row["rank"] < start_rank:
            continue
        code=row["security_id"]
        if code not in eligible:
            continue
        if row["name"] != eligible[code]["name"] or (
                row["venue"] != eligible[code]["venue"]):
            raise ValueError("Price-watch security/issuer identity mismatch")
        if CODE.fullmatch(code):
            choices.append(code)
        if len(choices) == limit:
            break
    if not choices:
        raise ValueError("No eligible current DART company in requested price page")
    return tuple(choices)


def choose_marketwide_turnover_cfs_batch(report: dict, official_evidence: dict,
                                         eligible: dict, *, offset: int = 0,
                                         limit: int = 12) -> tuple[str, ...]:
    """Next DART annual CFS queue from the whole pinned KRX market, by turnover.

    Existing comparable companies are skipped, missing-company facts remain
    N/A, and turnover is NOT treated as leadership/investment rank.
    """
    import math
    from .official_company_explorer import canonical
    from .official_marketwide_coverage import SCHEMA as COVERAGE
    if (type(offset) is not int or not 0 <= offset <= 5000 or
            type(limit) is not int or not 1 <= limit <= MAX_COMPANIES):
        raise ValueError("Bounded marketwide batch offset/limit required")
    original = dict(report)
    digest = original.pop("content_sha256",None)
    if (report.get("schema") != COVERAGE or
            type(digest) is not str or
            sha256(canonical(original)).hexdigest() != digest or
            report.get("market") != "KR" or
            report.get("research_only") is not True or
            report.get("official_leaders") != 0 or
            report.get("full_market_composite_rank_available") is not False or
            report.get("market_session") != official_evidence.get("api_observation_day") or
            official_evidence.get("historic_universe_pit_verified") is not False):
        raise ValueError("Marketwide KRX source must be unpromoted, pinned and same session")
    rows = report.get("securities")
    if type(rows) is not list or len(rows) != report.get("official_krx_observed"):
        raise ValueError("Whole-market KRX rows/count missing")
    seen = set()
    pool = []
    for row in rows:
        code = row.get("security_id")
        if code in seen or type(code) is not str:
            raise ValueError("Marketwide KRX duplicate security code")
        seen.add(code)
        if code not in eligible:
            continue
        if (row.get("name") != eligible[code]["name"] or
                row.get("venue") != eligible[code]["venue"] or
                row.get("current_dart_directory_matched") is not True):
            raise ValueError("Marketwide issuer name/venue mismatch")
        amount = row.get("turnover")
        cap = row.get("market_cap")
        if (type(amount) not in (int,float) or not math.isfinite(amount) or
                type(cap) not in (int,float) or not math.isfinite(cap) or
                amount < 0 or cap < 0):
            raise ValueError("Invalid KRX turnover/market cap")
        if (CODE.fullmatch(code) and row.get("revenue_yoy") is None and
                row.get("market_traded") is True and amount > 0):
            pool.append((code,float(amount),float(cap)))
    pool.sort(key=lambda x:(-x[1],-x[2],x[0]))
    batch = tuple(row[0] for row in pool[offset:offset+limit])
    if not batch:
        raise ValueError("No uncovered current DART issuers in marketwide batch")
    return batch

def collect_multi_company_cfs(*, evidence_file: Path, private_root: Path,
                              codes: tuple[str,...], credentials: dict,
                              years: tuple[int,...]=(2024,2025),
                              delay_seconds: float=0.75, fetch=None,
                              clock=None, existing_only: bool=False) -> dict:
    """Keep bounded 2/3-year origins; no historical score promotion.

    A conflicting repeat of the same FY is a manual revision-review blocker.
    Existing originals are reused rather than silently overwritten.
    """
    if (not isinstance(codes,tuple) or not 1<=len(codes)<=MAX_COMPANIES or
            any(type(c) is not str or not CODE.fullmatch(c) for c in codes) or
            len(set(codes))!=len(codes)):
        raise ValueError("Require 1..12 unique six-digit KR stock codes")
    if (not isinstance(years,tuple) or years not in
            ((2024,2025),(2023,2024,2025)) or
            type(delay_seconds) not in (int,float) or
            not 0<=delay_seconds<=10):
        raise ValueError("Only bounded FY 2024/25 or 2023/24/25 CFS annual batch")
    decision=(clock or (lambda:datetime.now(timezone.utc)))()
    if decision.tzinfo is None or decision.utcoffset() is None:
        raise ValueError("Multi-company CFS decision needs timezone")
    market,directory,coverage=source_eligible_universe(
        Path(evidence_file),Path(private_root),decision=decision)
    if any(code not in market for code in codes):
        raise ValueError("Requested stock must exist in both actual KRX and DART originals")
    # Inspect ALL existing FY receipt identities before expensive verification.
    # Never choose one version of a revised filing based on scan order.
    existing_raw={}
    for file in Path(private_root).glob("dart_fin_*/first_receipt.json"):
        receipt=_read_json(file)
        key=(receipt.get("stock_code"),receipt.get("bsns_year"))
        if key[0] not in codes or key[1] not in years:
            continue
        if (receipt.get("statement")!="CFS" or receipt.get("reprt_code")!="11011"):
            continue
        if key in existing_raw:
            raise ValueError("Same-company FY has multiple original versions; revision review required")
        existing_raw[key]=(file.parent,sha256(file.read_bytes()).hexdigest())
    existing={}
    for key,(folder,pin) in existing_raw.items():
        verified=verify_dart_financial(folder,pin,
                    decision_at=decision,directory=directory)
        existing[key]=(folder,pin,verified)
    results=[]
    for code in codes:
        report_rows=[]
        for year in years:
            key=(code,year)
            if key in existing:
                folder,pin,verified=existing[key]
                reused=True
            elif existing_only:
                report_rows.append({"fiscal_year":year,"status":"NOT_CAPTURED",
                                    "existing_original":False})
                continue
            else:
                fresh=capture_dart_financial(
                    Path(private_root),stock_code=code,
                    directory=directory,year=year,report="11011",
                    statement="CFS",creds=credentials,fetch=fetch,clock=clock)
                folder=Path(private_root)/fresh["capture_id"]
                pin=fresh["first_receipt_sha256"]
                verified=verify_dart_financial(folder,pin,decision_at=(
                    clock or (lambda:datetime.now(timezone.utc)))(),directory=directory)
                reused=False
                if delay_seconds:
                    time.sleep(delay_seconds)
            report_rows.append({
                "fiscal_year":year, "status":verified["status"],
                "first_receipt_sha256":pin,"capture_id":folder.name,
                "original_first_received_at_utc":verified["first_local_received_at_utc"],
                "existing_original":reused,
                "observed_account_count":len(verified["metrics"]),
                "pit_certified":False,
            })
        results.append({
            "stock_code":code,"name":market[code]["name"],
            "venue":market[code]["venue"],
            "annual_reports":report_rows,
            "research_annual_cfs_complete":all(
                row["status"]=="FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY" and
                row["observed_account_count"]>=2 for row in report_rows)
                and len(report_rows)==len(years),
            "confirmed_future_leader":False,
        })
    output={
        "schema":SCHEMA,"decision_at_utc":(
            (clock or (lambda:datetime.now(timezone.utc)))()
            .astimezone(timezone.utc).isoformat()),
        "official_market":coverage,"fiscal_years":list(years),
        "companies_requested":len(codes),
        "companies_with_complete_annual_cfs":sum(x["research_annual_cfs_complete"]
                                                 for x in results),
        "companies":results,"research_only":True,
        "all_company_historic_pit_certified":False,
        "real_investment_leader_ranked":False,
        "warnings":[
            "DART first receipt is not independent earliest public filing timestamp",
            "KRX prior 3/6-month price lookback is local cache, not independently certified",
            "No issuer/share-class/delisting/corporate action historical PIT proof",
        ],
    }
    return output
