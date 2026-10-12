#!/usr/bin/env python3
"""Safe local SHA-only cold restore readiness gate; no key or decrypt."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="EraLeader cold first native restoration readiness")
    parser.add_argument("--action",choices=("scan","verify-history"),default="scan")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--pin-root",type=Path,required=True)
    parser.add_argument("--scratch-root",type=Path,required=True)
    parser.add_argument("--due-days",type=int,default=30)
    parser.add_argument("--warn-days",type=int,default=7)
    parser.add_argument("--max-gap-hours",type=int,default=48)
    parser.add_argument("--allow-colocated-research-only",action="store_true",
                        help="Synthetic local research, never offsite readiness")
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.native_cold_restore_gate import (
        run_cold_restore_gate, verify_restore_gate_history, STATUS)
    opts={"due_days":args.due_days,"warn_days":args.warn_days,
          "max_gap_hours":args.max_gap_hours,
          "allow_colocated_research":args.allow_colocated_research_only}
    if args.action=="scan":
        result=run_cold_restore_gate(project,args.pin_root,args.scratch_root,**opts)
        if (result.get("status")!=STATUS or
                result.get("private_key_accessed") is not False or
                result.get("plaintext_decrypted") is not False or
                result.get("local_artifacts_only") is not True):
            raise RuntimeError("Unsafe cold readiness response")
    else:
        result=verify_restore_gate_history(project,args.pin_root,args.scratch_root,**opts)
    if (result.get("external_api_calls")!=0 or
            result.get("messages_sent")!=0 or
            result.get("official_leader_promotions")!=0):
        raise RuntimeError("Cold gate must not dispatch or promote")
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,TypeError,KeyError) as exc:
        # Original PIN archive paths and any optional secret paths are not echoed.
        print("EraLeader cold restore readiness rejected: "+type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2) from exc
