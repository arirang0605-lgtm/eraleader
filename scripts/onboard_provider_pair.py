#!/usr/bin/env python3
"""Explicit offline dual-provider staged PIT first-ingest; publish only both.

No API, no trading, no official source endorsement. Use a NEW private output
directory outside any Git tracked/raw source directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    p=argparse.ArgumentParser(description="Offline KR/US staged source pair first-write intake")
    p.add_argument("--staged-a",type=Path,required=True,
                   help="First separate provider's existing absolute staged manifest.json")
    p.add_argument("--staged-b",type=Path,required=True,
                   help="Second separate provider's existing absolute staged manifest.json")
    p.add_argument("--target",type=Path,required=True,
                   help="NEW private directory, under existing owner-only parent (0700)")
    p.add_argument("--project",type=Path,required=True,
                   help="Original source package/module path, NOT a live API")
    args=p.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.provider_pair_atomic_onboard import (
        onboard_staged_provider_pair, STATUS)
    report=onboard_staged_provider_pair(args.staged_a,args.staged_b,args.target)
    if (report.get("status")!=STATUS or
            report.get("all_or_nothing_published") is not True or
            report.get("two_original_first_ingest_receipts_pinned") is not True or
            report.get("actual_future_leader_skill_certified") is not False or
            report.get("legal_issuer_security_class_pit_certified") is not False or
            report.get("external_api_calls")!=0 or
            report.get("messages_sent")!=0 or
            report.get("official_leader_promotions")!=0):
        raise RuntimeError("Unsafe paired PIT onboarding status")
    print(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,TypeError,KeyError) as exc:
        # Do NOT expose user-supplied provider filenames, issuer IDs or values.
        print("EraLeader offline paired onboarding failed: "+
              type(exc).__name__,file=sys.stderr)
        raise SystemExit(2) from exc
