#!/usr/bin/env python3
"""Private on-device first-WATCH/native Top-K source archive, SHA check, restore.

Not a timestamp authority or official PIT evidence. Never sends messages or
uploads original issuer/market files. CLI summaries contain no original paths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="Original native prospective evidence private vault")
    parser.add_argument("--action",required=True,choices=("create","verify","restore"))
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--plan",type=Path)
    parser.add_argument("--capture-root",type=Path)
    parser.add_argument("--target",type=Path)
    parser.add_argument("--expected-sha256",type=str)
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.native_evidence_archive import (
        create_native_evidence_archive,verify_native_evidence_archive,
        restore_native_evidence_archive,
    )
    if args.action=="create":
        if (args.plan is None or args.capture_root is None or
                args.target is not None or args.expected_sha256 is not None):
            parser.error("create requires --plan + --capture-root and no restore/expected SHA inputs")
        result=create_native_evidence_archive(
            args.plan,args.capture_root,args.archive,project=project)
    elif args.action=="verify":
        if args.plan is not None or args.capture_root is not None or args.target is not None:
            parser.error("verify accepts only --archive and optional --expected-sha256")
        result=verify_native_evidence_archive(args.archive,expected_sha256=args.expected_sha256)
    else:
        if args.plan is not None or args.capture_root is not None or args.target is None:
            parser.error("restore requires --target and must not reissue an original capture")
        result=restore_native_evidence_archive(
            args.archive,args.target,project=project,
            expected_sha256=args.expected_sha256,
        )
    if (result.get("real_future_leader_accuracy_certified") is not False or
            result.get("messages_sent")!=0 or
            result.get("external_api_calls")!=0 or
            result.get("official_leader_promotions")!=0):
        raise RuntimeError("Unsafe native first-write private archive result")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,FileExistsError) as exc:
        print("EraLeader private native source vault: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
