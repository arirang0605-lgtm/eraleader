#!/usr/bin/env python3
"""Collect a SMALL KRX+DART verified cross-industry CFS comparison batch.

Real 2024/2025 FY originals are preserved in the existing owner-only cache.
Outputs a new manifest, never market orders or investment leader rankings.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_api_capture import KEYS, credentials
from eraleader.official_dart_multi_company import (
    collect_multi_company_cfs, choose_price_watch_company_batch, source_eligible_universe
)
from datetime import datetime, timezone


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-evidence",type=Path,required=True)
    p.add_argument("--capture-root",type=Path,
                   default=ROOT/"output"/"official_api_capture")
    p.add_argument("--code",action="append",
                   help="One present, first-received KRX+DART six-digit code; max 12")
    p.add_argument("--auto-price-watch",type=Path,
                   help="Existing signed KRX price WATCH snapshot, for automatic bounded CFS queue")
    p.add_argument("--auto-start-rank",type=int,default=1)
    p.add_argument("--auto-limit",type=int,default=12)
    p.add_argument("--year",type=int,action="append",default=[])
    p.add_argument("--out",type=Path,required=True,
                   help="NEW local research manifest, in git-ignored output/")
    p.add_argument("--credentials-file",type=Path)
    p.add_argument("--only-existing",action="store_true",
                   help="Verify available originals without sending new API requests")
    p.add_argument("--delay",type=float,default=0.75,
                   help="Minimum seconds between newly collected first receipts")
    a=p.parse_args(argv)
    try:
        saved=(Path.home()/"Library"/"Application Support"/"EraLeader"/
               "api-credentials"/"official_api.env")
        user_creds=a.credentials_file
        if user_creds is None and not any(os.environ.get(k) for k in KEYS) and saved.is_file():
            user_creds=saved
        if (not a.out.is_absolute() or a.out.exists() or a.out.is_symlink() or
                not a.out.parent.is_dir() or a.out.parent.is_symlink() or
                a.out.suffix!=".json"):
            raise ValueError("Output manifest must be new absolute private JSON path")
        years=tuple(a.year) if a.year else (2024,2025)
        if (a.code is None) == (a.auto_price_watch is None):
            raise ValueError("Use explicit codes OR verified price-watch auto queue")
        if a.auto_price_watch is not None:
            if not a.auto_price_watch.is_absolute() or a.auto_price_watch.is_symlink():
                raise ValueError("Price source path must be absolute regular source")
            snapshot=json.loads(a.auto_price_watch.read_bytes())
            evidence=json.loads(a.official_evidence.read_bytes())
            market,_,_=source_eligible_universe(
                a.official_evidence,a.capture_root,
                decision=datetime.now(timezone.utc))
            codes=choose_price_watch_company_batch(
                snapshot,evidence,market,start_rank=a.auto_start_rank,
                limit=a.auto_limit)
        else:
            codes=tuple(a.code)
        result=collect_multi_company_cfs(
            evidence_file=a.official_evidence,
            private_root=a.capture_root,
            codes=codes,years=years,
            credentials={} if a.only_existing else credentials(user_creds),
            existing_only=a.only_existing,delay_seconds=a.delay)
        fd=os.open(a.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write((json.dumps(result,sort_keys=True,
                ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode())
            f.flush();os.fsync(f.fileno())
    except (OSError,TypeError,ValueError,KeyError) as exc:
        print("DART_MULTI_CFS_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2
    summary={
        "status":"OFFICIAL_DART_MULTICOMPANY_CFS_RESEARCH",
        "companies_requested":result["companies_requested"],
        "companies_with_complete_annual_cfs":result["companies_with_complete_annual_cfs"],
        "verified_first_receipts":sum(
            "first_receipt_sha256" in row for c in result["companies"]
            for row in c["annual_reports"]),
        "market_session":result["official_market"]["market_session"],
        "investment_rank_ready":False,
        "original_cache_and_json_updated_only":True,
    }
    print(json.dumps(summary,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
