#!/usr/bin/env python3
"""Run existing strict DART daily full pagination using a Mac 0600 first mirror."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from eraleader.official_dart_full_mac_bridge import complete_day_from_ssd

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first",required=True,type=Path)
    parser.add_argument("--first-sha",required=True)
    parser.add_argument("--max-pages",type=int,default=40)
    options=parser.parse_args(argv)
    try:
        result=complete_day_from_ssd(options.first.absolute(),options.first_sha,
                                     max_pages=options.max_pages)
        print(json.dumps(result,sort_keys=True,ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        print("DART_FULL_MAC_BRIDGE_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
