#!/usr/bin/env python3
"""Re-audit an immutable staged PIT pair at an explicit as-of cutoff.

The original first-pair SHA must have been retained independently from its
private source folder. No external APIs, raw issuer output or WATCH writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="EraLeader offline first-pinned provider pair PIT as-of audit")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--pair-root",type=Path,required=True,
                        help="Existing private atomically published pair directory")
    parser.add_argument("--first-pair-sha256",required=True,
                        help="Original pair receipt digest retained separately")
    parser.add_argument("--as-of",required=True,
                        help="Decision time with timezone, after first local intake")
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.provider_pair_asof_seal import (
        audit_atomic_provider_pair_asof, READY)
    result=audit_atomic_provider_pair_asof(
        args.pair_root,args.first_pair_sha256,decision_at=args.as_of)
    if (result.get("official_pit_certified") is not False or
            result.get("permanent_issuer_and_class_attested") is not False or
            result.get("real_future_leader_precision") is not None or
            result.get("official_leader_promotions")!=0 or
            result.get("external_api_calls")!=0 or
            result.get("messages_sent")!=0):
        raise RuntimeError("Unsafe first-pair source audit")
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2))
    return 0 if result["status"]==READY else 2


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,TypeError,KeyError) as exc:
        # No raw source paths or private values in stderr.
        print("EraLeader paired PIT first-SHA audit blocked: "+type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2) from exc
