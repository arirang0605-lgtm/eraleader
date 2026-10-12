#!/usr/bin/env python3
"""Read-only local archive SHA continuity check using another filesystem.

Does not read future outcome labels, send messages, mint new first receipts,
copy source files off the SSD or claim independently attested time.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description="Verify local cross-volume first-native ZIP SHA witness")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--capture-root",type=Path,required=True)
    parser.add_argument("--witness-root",type=Path,required=True)
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.native_sha_witness import verify_native_sha_witness
    report=verify_native_sha_witness(
        project,args.plan,args.capture_root,args.witness_root)
    if (report.get("status")!="SEPARATE_VOLUME_NATIVE_SHA_VERIFIED_NOT_ATTESTED" or
            report.get("source_archive_verified") is not True or
            report.get("separate_device_checked") is not True or
            report.get("independent_timestamp_attested") is not False or
            report.get("real_future_leader_accuracy_certified") is not False or
            report.get("messages_sent")!=0 or
            report.get("external_api_calls")!=0 or
            report.get("official_leader_promotions")!=0):
        raise RuntimeError("Unsafe cross-volume research witness verification")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError) as exc:
        print("EraLeader local native SHA witness: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
