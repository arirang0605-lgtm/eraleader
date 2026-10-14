#!/usr/bin/env python3
"""Plan missing KRX daily volume original captures; NEVER calls official APIs."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.krx_volume_gap_planner import plan_dated_krx_volume_gaps,MAX_REQUESTS
from eraleader.data import LEGACY_DEFAULT

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--capture-root",required=True,type=Path)
    p.add_argument("--code",required=True)
    p.add_argument("--legacy-root",type=Path,default=LEGACY_DEFAULT)
    p.add_argument("--max-requests",type=int,default=MAX_REQUESTS)
    args=p.parse_args(argv)
    try:
        result=plan_dated_krx_volume_gaps(
            marketwide=args.marketwide_report,project=args.project,
            capture_root=args.capture_root,stock_code=args.code,
            legacy_root=args.legacy_root,max_requests=args.max_requests)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        print("KRX_VOLUME_GAP_PLAN_BLOCKED",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
