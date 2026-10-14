#!/usr/bin/env python3
"""Publish actual five-factor coverage / N/A gates for EraLeader KR research."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_p2_readiness import build_p2_readiness,publish_p2_readiness


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--watch-state-ledger",type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=build_p2_readiness(args.marketwide_report,
                                  state_history=args.watch_state_ledger)
        paths=publish_p2_readiness(report,args.out)
        print(json.dumps({
            "status":"P2_FIVE_FACTOR_READINESS_PUBLISHED_RESEARCH_ONLY",
            "market_session":report["market_session"],
            "observed":report["observed_market_securities"],
            "factors":report["observed_factor_counts"],
            "research_two_factor":report["two_factor_research_evaluable"],
            "official_selected":0,"files":[str(x) for x in paths]},
            ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,TypeError,OSError,KeyError):
        print("P2_READINESS_SOURCE_OR_OUTPUT_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
