#!/usr/bin/env python3
"""Publish real KRX price + multiple receipt-pinned DART annual CFS candidates.

Use ONLY already verified first-received official API originals, with no API
requests. One new read-only research website; keeps existing 20 WATCH unchanged.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_api_pit_bridge import (
    build_official_price_snapshot,run_official_research,
)
from eraleader.official_dart_multi_company import SCHEMA as MULTI_SCHEMA


def _input(path: Path) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("Pinned original input must be a real absolute file")
    data=json.loads(path.read_bytes())
    if not isinstance(data,dict):
        raise ValueError("Original report must be a JSON object")
    return data


def publish_basic_company_screen(
        *, official_source: Path, financial_manifest: Path,
        private_root: Path, new_output: Path,
        clock: datetime | None=None) -> dict:
    source=_input(official_source)
    research=_input(financial_manifest)
    if (source.get("schema")!="eraleader.official_api_pit_research_bridge.v1" or
            source.get("historic_universe_pit_verified") is not False or
            source.get("official_leaders")!=0 or
            research.get("schema")!=MULTI_SCHEMA or
            research.get("research_only") is not True or
            research.get("real_investment_leader_ranked") is not False):
        raise ValueError("Only prior official CFS/market research proof permitted")
    if (not isinstance(private_root,Path) or private_root.is_symlink()
            or not private_root.is_absolute() or not private_root.is_dir()):
        raise ValueError("Private first-original capture root required")
    if (not new_output.is_absolute() or new_output.exists() or
            new_output.is_symlink() or new_output.parent.is_symlink() or
            not new_output.parent.is_dir()):
        raise ValueError("Only a new result directory, never override WATCH")
    first={}
    for file in private_root.glob("*/first_receipt.json"):
        if file.is_symlink():
            raise ValueError("First receipt cannot be a symlink")
        pin=sha256(file.read_bytes()).hexdigest()
        if pin in first:
            raise ValueError("Duplicate first-receipt SHA")
        first[pin]=file.parent
    def bound(pin):
        if type(pin) is not str or not re.fullmatch("[a-f0-9]{64}",pin) or pin not in first:
            raise ValueError("First original receipt SHA unavailable")
        return first[pin],pin
    providers={}
    for source_row in source.get("sources",[]):
        tag=source_row.get("source")
        if tag in ("krx-kospi","krx-kosdaq","dart-disclosures",
                   "sec-submissions","sec-companyfacts"):
            if tag in providers:
                raise ValueError("Duplicate official source receipt")
            providers[tag]=bound(source_row["first_receipt_sha256"])
    required={"krx-kospi","krx-kosdaq","dart-disclosures"}
    sec={"sec-submissions","sec-companyfacts"}
    # Daily KR capture can be KRX+DART only. A pair of SEC receipts is
    # optional, but accepting a lone SEC source would create mixed evidence.
    if (not required.issubset(providers) or
            set(providers) not in (required,required|sec)):
        raise ValueError("Core KR/DART original evidence missing or partial SEC evidence")
    directory=bound(source["dart_current_directory"]["first_receipt_sha256"])
    d=source.get("dart_full_day")
    if not isinstance(d,dict) or not isinstance(d.get("manifest_sha256"),str):
        raise ValueError("DART disclosure day manifest missing")
    complete=[p.parent for p in private_root.glob("dart_full_*/manifest.json")
              if sha256(p.read_bytes()).hexdigest()==d["manifest_sha256"]]
    if len(complete)!=1:
        raise ValueError("Official DART complete-day manifest must be pinned")
    if (research.get("companies_requested")!=len(research.get("companies",[])) or
            not 2<=research["companies_requested"]<=12 or
            research.get("official_market",{}).get("market_session")!=d["market_day"]):
        raise ValueError("Financial cohort and KRX day mismatch")
    used=set()
    financial=[]
    for company in research["companies"]:
        code=company["stock_code"]
        if code in used or type(code) is not str or not re.fullmatch("[0-9]{6}",code):
            raise ValueError("Duplicate/malformed official candidate security")
        used.add(code)
        if not company.get("research_annual_cfs_complete"):
            continue
        annual=company["annual_reports"]
        if sorted(row["fiscal_year"] for row in annual)!=research["fiscal_years"]:
            raise ValueError("Company statements differ from fixed two-year official cohort")
        for year in annual:
            if (year["status"]!="FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY" or
                    year.get("pit_certified") is not False or
                    not re.fullmatch(r"dart_fin_[a-f0-9]{32}",year["capture_id"])):
                raise ValueError("Invalid original annual research report")
            path,pin=bound(year["first_receipt_sha256"])
            if path.name!=year["capture_id"]:
                raise ValueError("FY original PIN identity differs from receipt")
            financial.append((path,pin))
    if len(financial)<4 or len(financial)>24:
        raise ValueError("At least two independently verified CFS companies required")
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Research clock must be timezone aware")
    localday=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    snap=build_official_price_snapshot(
        kospi=providers["krx-kospi"],kosdaq=providers["krx-kosdaq"],
        as_of=localday,decision_at=now.astimezone(timezone.utc).isoformat(),
        days=550,top=20,
        auxiliary=tuple((name,*providers[name])
            for name in ("dart-disclosures","sec-submissions","sec-companyfacts")
            if name in providers),
        dart_complete=(complete[0],d["manifest_sha256"],*providers["dart-disclosures"]),
        dart_directory=directory,
        dart_financial_receipts=tuple(financial),
        basic_candidate_screen=True,
    )
    if (len(snap.get("official_financial_research_observations",[]))<2 or
            len(snap.get("research_candidate_price_factors",[]))<2):
        raise ValueError("No comparative independently sourced CFS candidate rows")
    result=run_official_research(snap,new_output,basic_candidates=True)
    if (result["official_leaders"]!=0 or result["messages_sent"]!=0 or
            not result.get("basic_candidate_html")):
        raise ValueError("Research shortlist publication must never trade/promote")
    return {
        "status":"OFFICIAL_MULTICOMPANY_PRICE_EARNINGS_RESEARCH_PUBLISHED",
        "krx_daily_rows":result["krx_rows"],
        "dart_daily_disclosures":result["dart_full_rows"],
        "annual_cfs_research_companies":result["dart_financial_comparable_companies"],
        "fully_evaluable_price_earnings":result["basic_candidate_evaluable"],
        "price_watch_count":result["watch_count"],
        "daily_weekly_monthly_reports":result["reports"],
        "actual_messages_sent":result["messages_sent"],
        "official_leaders":result["official_leaders"],
        "research_only":True,
        "market_session":d["market_day"],
        "basic_candidates_path":result["basic_candidate_html"],
        "output_name":new_output.name,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-source",type=Path,required=True)
    parser.add_argument("--financial-manifest",type=Path,required=True)
    parser.add_argument("--private-root",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        output=publish_basic_company_screen(
            official_source=args.official_source,
            financial_manifest=args.financial_manifest,
            private_root=args.private_root,new_output=args.out)
    except (ValueError,FileExistsError,TypeError,KeyError,OSError) as exc:
        print("OFFICIAL_BASIC_CANDIDATE_SCREEN_BLOCKED: "+type(exc).__name__,
              file=sys.stderr)
        return 2
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
