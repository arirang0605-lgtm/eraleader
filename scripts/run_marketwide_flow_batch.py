#!/usr/bin/env python3
"""Plan bounded KR selected-stock investor flow from official marketwide data.

Default NO NETWORK. With --apply-demo only, calls the existing shared
ReadOnlyClient('eraleader') for up to 5 symbols; never uses real credentials.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.marketwide_flow_batch import plan_marketwide_flow,capture_marketwide_demo_flow


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--max-codes",type=int,default=3,help="1-5, selected-stock research only")
    p.add_argument("--apply-demo",action="store_true",
                   help="Explicit limited DEMO shared-gateway read only; never real account/orders")
    args=p.parse_args(argv)
    try:
        if args.apply_demo:
            # This connector module is shared read-only and remains outside
            # EraLeader's Git and data directory.
            shared=Path("/Volumes/T5DATA/SharedBrokerAPI/src")
            if not shared.is_dir() or shared.is_symlink():
                raise ValueError("Shared read-only adapter unavailable")
            sys.path.insert(0,str(shared))
            from shared_broker_api.client import ReadOnlyClient
            result=capture_marketwide_demo_flow(
                marketwide=args.marketwide_report,project=args.project,
                client=ReadOnlyClient("eraleader"),limit=args.max_codes)
        else:
            result=plan_marketwide_flow(
                marketwide=args.marketwide_report,project=args.project,
                limit=args.max_codes)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,KeyError,TypeError,ImportError,OSError,OverflowError):
        print("KR_FLOW_BATCH_RESEARCH_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
