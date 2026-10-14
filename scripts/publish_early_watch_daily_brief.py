#!/usr/bin/env python3
"""Publish local annual-change snapshot as a daily WATCH JSON/HTML brief."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.early_watch_daily_brief import publish_daily_brief

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--watch-manifest",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        result=publish_daily_brief(project=args.project,
                                   watch_manifest=args.watch_manifest)
    except (ValueError,OSError,KeyError,TypeError,OverflowError):
        print("DAILY_WATCH_BRIEF_BLOCKED",file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
