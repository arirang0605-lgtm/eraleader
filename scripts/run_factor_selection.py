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
    p.add_argument("--factor-input",type=Path)
    args=p.parse_args(argv)
    try:
        state=run_factor_selection(
            marketwide=args.marketwide_report,
            project=args.project,assessment_file=args.factor_input)
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        print("FIVE_FACTOR_SELECTION_RESEARCH_BLOCKED",file=sys.stderr)
        return 2
    print(json.dumps(state,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
