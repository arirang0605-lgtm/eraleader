#!/usr/bin/env python3
"""Explicit independent-PIN cold ZIP -> authenticated original WATCH replay DRILL.

No private key is loaded when verifying history. Real replay requires --private-key,
a private scratch on a separate device, and an already enrolled first SHA PIN.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    p=argparse.ArgumentParser(
        description="EraLeader independent cold native original replay rehearsal")
    p.add_argument("--action",choices=("run","verify-history"),required=True)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--pin-root",type=Path,required=True,
                   help="Existing private first SHA registry; never re-enroll")
    p.add_argument("--scratch-root",type=Path,required=True,
                   help="Existing owner-only 0700 separate-device temporary workspace")
    p.add_argument("--name",help="Original independent PIN record alias for run")
    p.add_argument("--slot",help="Original KR/US SHA-hashed native model slot for run")
    p.add_argument("--private-key",type=Path,
                   help="Explicit mode0600 existing RSA key; NEVER scheduled or logged")
    p.add_argument("--max-gap-hours",type=int,default=48)
    p.add_argument("--allow-colocated-research-only",action="store_true",
                   help="Synthetic research on only two devices; NOT operational offsite")
    args=p.parse_args(argv)
    if args.action=="run":
        if not args.name or not args.slot or args.private_key is None:
            p.error("Explicit run requires --name, --slot, --private-key")
    elif args.name is not None or args.slot is not None or args.private_key is not None:
        p.error("verify-history must never access private key, model slot or alias")
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.native_cold_replay_drill import (
        run_cold_replay_drill,verify_cold_replay_history,STATUS)
    common={"max_gap_hours":args.max_gap_hours,
            "allow_colocated_research":args.allow_colocated_research_only}
    if args.action=="run":
        report=run_cold_replay_drill(
            project,args.pin_root,args.name,args.slot,
            args.private_key,args.scratch_root,**common)
    else:
        report=verify_cold_replay_history(
            project,args.pin_root,args.scratch_root,**common)
    if (report.get("messages_sent")!=0 or report.get("external_api_calls")!=0 or
            report.get("official_leader_promotions")!=0):
        raise RuntimeError("Unsafe original cold replay result")
    print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
    if args.action=="run":
        if (report.get("status")!=STATUS or
                report.get("latest",{}).get("outcome")!="PASSED"):
            return 2
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as exc:
        # Do not reveal original private archive paths or key material in stderr.
        print("EraLeader cold replay rejected unsafe evidence: "+
              type(exc).__name__,file=sys.stderr)
        raise SystemExit(2) from exc
