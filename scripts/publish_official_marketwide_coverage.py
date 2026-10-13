#!/usr/bin/env python3
"""Publish observed whole-KRX coverage using already-pinned KRX/DART receipts."""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_marketwide_coverage import (
    build_marketwide_coverage, publish_marketwide_coverage,
    refresh_saved_marketwide_flow,
)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument("--cohort",type=Path)
    source.add_argument("--verified-marketwide-report",type=Path,
                        help="Reuse existing SHA-verified KR marketwide report to join new Kiwoom flow")
    p.add_argument("--capture-root",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--extra-cfs-manifest",type=Path,action="append",default=[],
                   help="Additional verified existing bounded CFS batch (FY consecutive)")
    p.add_argument("--extra-industry-manifest",type=Path,action="append",default=[],
                   help="Additional verified DART industry first-receipt batch")
    p.add_argument("--full-price-lookback",action="store_true",
                   help="Opt in to existing uncertified local marcap price-history percentiles")
    p.add_argument("--kiwoom-flow-folder",type=Path,
                   help="Existing read-only Kiwoom selected-flow capture; exact KRX session only")
    a=p.parse_args(argv)
    if a.verified_marketwide_report is not None:
        if (a.kiwoom_flow_folder is None or a.capture_root is not None or
                a.extra_cfs_manifest or a.extra_industry_manifest or
                a.full_price_lookback):
            p.error("Saved report mode only accepts --kiwoom-flow-folder and --out")
        result=refresh_saved_marketwide_flow(
            a.verified_marketwide_report,a.kiwoom_flow_folder)
    else:
        if a.capture_root is None:
            p.error("Official KRX/DART capture-root is required")
        result=build_marketwide_coverage(a.cohort,a.capture_root,
                                          extra_cfs_manifests=tuple(a.extra_cfs_manifest),
                                          extra_industry_manifests=tuple(a.extra_industry_manifest),
                                          full_price_lookback=a.full_price_lookback,
                                          kiwoom_flow_folder=a.kiwoom_flow_folder)
    paths=publish_marketwide_coverage(result,a.out)
    print(json.dumps({"status":"RESEARCH_COVERAGE_PUBLISHED",
          "observed":result["official_krx_observed"],
          "finance":result["financial_factors_observed"],
          "industry":result["industry_factors_observed"],
          "formal_leaders":0,"files":[str(x) for x in paths]},
          ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
