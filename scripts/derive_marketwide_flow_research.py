#!/usr/bin/env python3
"""Build source-verified KR flow research heuristic and partial factor join.

No provider fetch, no portfolio selections, no Stage4 SQLite writes, no orders.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.marketwide_flow_research_score import (
    build_flow_research,join_flow_into_partial,
)


def _pair(item:str):
    code,_,file=item.partition("=")
    if not code.isascii() or not code.isdigit() or len(code)!=6 or not file:
        raise argparse.ArgumentTypeError("Use exactly SIX-DIGIT-CODE=/abs/path/manifest.json")
    return code,Path(file)


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path)
    parser.add_argument("--marketwide-report",required=True,type=Path)
    parser.add_argument("--base-partial-assessment",required=True,type=Path)
    parser.add_argument("--code-overlay",type=_pair,required=True,action="append",
                        help="Repeat CODE=/absolute/first_krx_volume_overlay/manifest.json")
    args=parser.parse_args(argv)
    try:
        selected=dict(args.code_overlay)
        if len(selected)!=len(args.code_overlay):
            raise ValueError("FLOW_RESEARCH_DUPLICATE_CODE")
        flow=build_flow_research(
            marketwide=args.marketwide_report,project=args.project,sources=selected)
        joined=join_flow_into_partial(
            base_assessment=args.base_partial_assessment,
            flow_file=Path(flow["file"]),project=args.project)
        print(json.dumps({
            "status":"FLOW_RESEARCH_PARTIAL_FIVE_FACTOR_PREPARED",
            "research_flow_scores":flow["scores"],
            "flow_evidence":flow["file"],
            "partial_input":joined["file"],
            "partial_rows_scored":joined["scored_in_partial"],
            "factor_input_first_usable_utc":joined["factor_input_first_usable_utc"],
            "same_day_state_history_overwrite":False,
            "formal_leaders":0,"orders":0,
        },sort_keys=True,ensure_ascii=False))
        return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError):
        print("FLOW_RESEARCH_PARTIAL_JOIN_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
