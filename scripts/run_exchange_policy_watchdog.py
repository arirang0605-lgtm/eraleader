#!/usr/bin/env python3
"""Offline read-only sticky roster policy DRY-RUN monitor; no messages sent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="Local-only exchange roster policy SHA watchdog")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--policy-out",type=Path,required=True,
                        help="Original offline-integrated WATCH output root, not the observer root")
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.exchange_policy_watchdog import run_exchange_policy_watchdog
    result=run_exchange_policy_watchdog(project,args.policy_out)
    if (result.get("status")!="LOCAL_EXCHANGE_POLICY_DRY_RUN_RECORDED" or
            result.get("messages_sent")!=0 or result.get("external_api_calls")!=0 or
            result.get("official_leader_promotions")!=0):
        raise RuntimeError("Exchange policy local monitor result not safely verified")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError) as exc:
        print("EraLeader exchange policy DRY-RUN: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
