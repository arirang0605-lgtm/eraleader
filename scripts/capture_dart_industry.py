#!/usr/bin/env python3
"""Capture official DART current industry codes for the EXISTING KR candidates.

This is a bounded industry research component, not a historical sector model.
"""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_api_capture import credentials,KEYS
from eraleader.official_dart_multi_company import _all_pinned
from eraleader.official_dart_industry import collect_industry_profiles


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-source",required=True,type=Path)
    p.add_argument("--candidate-json",required=True,type=Path)
    p.add_argument("--capture-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--only-existing",action="store_true")
    p.add_argument("--credentials-file",type=Path)
    args=p.parse_args(argv)
    try:
        if (not args.out.is_absolute() or args.out.is_symlink() or args.out.exists()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()
                or args.out.suffix!=".json"):
            raise ValueError("New owner-only industry manifest required")
        official=json.loads(args.official_source.read_bytes())
        baseline=json.loads(args.candidate_json.read_bytes())
        if (official.get("schema")!="eraleader.official_api_pit_research_bridge.v1" or
                official.get("official_leaders")!=0 or
                official.get("historic_universe_pit_verified") is not False or
                baseline.get("schema")!="eraleader.official_basic_discovery_candidates.v1" or
                baseline.get("full_ranked_investment_priority_available") is not False):
            raise ValueError("Industry research requires current unpromoted KR/DART originals")
        witnessed=baseline["content_sha256"]
        sealed=dict(baseline);sealed.pop("content_sha256")
        encoded=json.dumps(sealed,ensure_ascii=False,sort_keys=True,
                           separators=(",",":"),allow_nan=False).encode("utf-8")
        if sha256(encoded).hexdigest()!=witnessed:
            raise ValueError("Basic original candidate evidence SHA mismatch")
        pins=_all_pinned(args.capture_root)
        sha=official["dart_current_directory"]["first_receipt_sha256"]
        if sha not in pins:
            raise ValueError("DART company-code first SHA original not located")
        selected=tuple(row["security_id"] for row in baseline["comparisons"])
        if len(selected)!=baseline["financial_companies_observed"]:
            raise ValueError("Industry panel must cover the FULL observed financial sample")
        saved=(Path.home()/"Library"/"Application Support"/"EraLeader"/
               "api-credentials"/"official_api.env")
        config=args.credentials_file
        if config is None and saved.is_file() and not any(os.environ.get(k) for k in KEYS):
            config=saved
        result=collect_industry_profiles(
            private_root=args.capture_root,directory=(pins[sha],sha),
            stock_codes=selected,
            creds={} if args.only_existing else credentials(config),
            existing_only=args.only_existing)
        fd=os.open(args.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as dest:
            dest.write((json.dumps(result,ensure_ascii=False,sort_keys=True,
                 indent=2,allow_nan=False)+"\n").encode("utf-8"))
            dest.flush();os.fsync(dest.fileno())
        summary={"status":"DART_CURRENT_INDUSTRY_BATCH_VERIFIED_RESEARCH",
                 "companies":result["companies_requested"],
                 "profiles_verified":result["industry_profiles_verified"],
                 "first_source_receipts":sum(bool(row.get("first_receipt_sha256"))
                                            for row in result["companies"]),
                 "historic_industry_pit_certified":False,
                 "investment_priority_ready":False,
                 "network_calls_not_logged":True}
        print(json.dumps(summary,sort_keys=True,ensure_ascii=False))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print("DART_INDUSTRY_CAPTURE_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
