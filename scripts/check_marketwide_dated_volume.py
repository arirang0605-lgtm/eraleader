#!/usr/bin/env python3
"""Compare one verified dated Kiwoom witness with exact local price-volume days.

This is read-only research, never any broker or provider API request.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.marketwide_dated_volume import publish_exact_dated_volume
from eraleader.data import LEGACY_DEFAULT


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--marketwide-report",type=Path,required=True)
    p.add_argument("--code",required=True)
    p.add_argument("--legacy-root",type=Path,default=LEGACY_DEFAULT)
    p.add_argument("--official-volume-overlay",type=Path,default=None,
                   help="Optional SHA-verified official KRX first-receipt volume supplement")
    args=p.parse_args(argv)
    try:
        result=publish_exact_dated_volume(
            marketwide=args.marketwide_report,project=args.project,
            code=args.code,legacy_root=args.legacy_root,
            official_volume_overlay=args.official_volume_overlay)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (KeyError,ValueError,TypeError,OSError,OverflowError):
        print("DATED_EXACT_VOLUME_RESEARCH_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
