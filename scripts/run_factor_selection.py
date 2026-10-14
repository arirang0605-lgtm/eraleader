#!/usr/bin/env python3
"""Operational local 5-factor input gate -> StateHistory -> neutral JSON.

Without --factor-input, inspect real coverage and report why candidates are
not ready. With explicit locally attested input, publish RESEARCH-ONLY states.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.factor_selection_pipeline import run_factor_selection


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--project",required=True,type=Path)
    group=p.add_mutually_exclusive_group()
    group.add_argument("--factor-input",type=Path)
    group.add_argument("--derive-official-partial",action="store_true",
                       help="Use only existing SHA-verified price/earnings research; all remaining factors N/A")
    p.add_argument("--max-research-rows",type=int,default=500,
                   help="For --derive-official-partial only, 1..500 observed research stocks")
    args=p.parse_args(argv)
    if args.max_research_rows!=500 and not args.derive_official_partial:
        print("FIVE_FACTOR_SELECTION_RESEARCH_BLOCKED",file=sys.stderr)
        return 2
    try:
        derived=None
        factor_input=args.factor_input
        if args.derive_official_partial:
            from eraleader.official_partial_factor_bridge import derive_partial_factor_input
            derived=derive_partial_factor_input(
                marketwide=args.marketwide_report,project=args.project,
                limit=args.max_research_rows)
            factor_input=Path(derived["input_file"]) if derived.get("input_file") else None
        state=run_factor_selection(
            marketwide=args.marketwide_report,
            project=args.project,assessment_file=factor_input)
        if derived is not None:
            state["partial_factor_derivation"]=derived
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        print("FIVE_FACTOR_SELECTION_RESEARCH_BLOCKED",file=sys.stderr)
        return 2
    print(json.dumps(state,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
