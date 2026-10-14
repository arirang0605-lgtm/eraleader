#!/usr/bin/env python3
"""Dated Kiwoom selected-stock flow witness. Default ZERO network.

--apply-demo must be explicit; only SharedBrokerAPI ReadOnlyClient is used.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.marketwide_dated_flow import plan_dated_capture,capture_dated_flow


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--code",required=True)
    p.add_argument("--apply-demo",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.apply_demo:
            shared=Path("/Volumes/T5DATA/SharedBrokerAPI/src")
            if not shared.is_dir() or shared.is_symlink():
                raise ValueError("Shared client unavailable")
            sys.path.insert(0,str(shared))
            from shared_broker_api.client import ReadOnlyClient
            state=capture_dated_flow(
                marketwide=args.marketwide_report,project=args.project,
                stock_code=args.code,client=ReadOnlyClient("eraleader"))
        else:
            state=plan_dated_capture(
                marketwide=args.marketwide_report,project=args.project,
                stock_code=args.code)
        print(json.dumps(state,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError,ImportError,OverflowError):
        print("DATED_FLOW_RESEARCH_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
