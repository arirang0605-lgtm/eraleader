#!/usr/bin/env python3
"""Publish a real-source KR early leader WATCH intake to local HTML + neutral JSON."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.early_leader_watch_queue import publish_early_watch

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--factor-input",required=True,type=Path)
    p.add_argument("--top",type=int,default=50)
    args=p.parse_args(argv)
    try:
        published=publish_early_watch(
            marketwide=args.marketwide_report,project=args.project,
            factor_input=args.factor_input,top=args.top)
        print(json.dumps(published,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,KeyError,TypeError,OSError,OverflowError):
        print("EARLY_LEADER_WATCH_PUBLICATION_BLOCKED",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
