#!/usr/bin/env python3
"""Publish verified locally saved official KRX 1-day volume into research layer.

No KRX network request, no order, no mutation of raw first receipts.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_krx_volume_overlay import publish_volume_overlay


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--marketwide-report",type=Path,required=True)
    p.add_argument("--capture-root",type=Path,required=True)
    p.add_argument("--code",required=True)
    args=p.parse_args(argv)
    try:
        report=publish_volume_overlay(
            marketwide=args.marketwide_report,project=args.project,
            capture_root=args.capture_root,stock_code=args.code)
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        print("KRX_ORIGINAL_VOLUME_RESEARCH_BLOCKED",file=sys.stderr)
        return 2
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
