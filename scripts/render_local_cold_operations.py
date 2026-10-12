#!/usr/bin/env python3
"""Render read-only operations + original cold replay SHA history.

Explicit PIN/scratch paths required; no user private key, network or scheduler.
"""
from __future__ import annotations
from argparse import ArgumentParser
from pathlib import Path
import json
import sys


def main(argv=None):
    parser=ArgumentParser(description="EraLeader local operations + cold-native recovery evidence")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--pin-root",type=Path,required=True)
    parser.add_argument("--scratch-root",type=Path,required=True)
    parser.add_argument("--max-gap-hours",type=int,default=48)
    parser.add_argument("--due-days",type=int,default=30)
    parser.add_argument("--warn-days",type=int,default=7)
    parser.add_argument("--allow-colocated-research-only",action="store_true",
                        help="Synthetic local trial, NOT production offsite readiness")
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.operations_cold_bridge import publish_operations_cold_bridge,STATUS
    result=publish_operations_cold_bridge(
        project,args.pin_root,args.scratch_root,
        due_days=args.due_days,warn_days=args.warn_days,
        max_gap_hours=args.max_gap_hours,
        allow_colocated_research=args.allow_colocated_research_only)
    if (result.get("status")!=STATUS or
            result.get("source_pit_certified") is not False or
            result.get("actual_future_leader_skill_certified") is not False or
            result.get("live_notifications_sent")!=0 or
            result.get("external_api_calls")!=0):
        raise RuntimeError("Unsafe local cold evidence report")
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as exc:
        # Never print private PIN/scratch paths in stderr.
        print("EraLeader local cold operations audit failed: "+
              type(exc).__name__,file=sys.stderr)
        raise SystemExit(2) from exc
