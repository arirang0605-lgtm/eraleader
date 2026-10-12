#!/usr/bin/env python3
"""Optional periodic encrypted-native cold ZIP verification; never decrypt/emit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    p = argparse.ArgumentParser(description="First native encrypted cold evidence independent SHA")
    p.add_argument("--action", choices=("enroll","scan","verify-history"), required=True)
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--pin-root", type=Path, required=True,
                   help="Already-existing owner 0700 private PIN root (other filesystem)")
    p.add_argument("--name", help="Immutable alias (enroll only)")
    p.add_argument("--archive", type=Path, help="Original portable encrypted-only ZIP (enroll only)")
    p.add_argument("--expected-sha256", help="Trusted ORIGINAL package SHA (enroll only)")
    p.add_argument("--max-gap-hours", type=int, default=48)
    p.add_argument("--allow-colocated-research-only", action="store_true",
                   help="Synthetic development: disables independent volume claims")
    args = p.parse_args(argv)
    if args.action == "enroll":
        if not args.name or not args.archive or not args.expected_sha256:
            p.error("First enrollment needs --name, --archive and independent original SHA256")
    elif any((args.name, args.archive, args.expected_sha256)):
        p.error("Periodic scan only reads the original PINs; no new ZIP/SHA input allowed")
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project/"src"))
    from eraleader.native_cold_integrity import (
        enroll_cold_integrity, scan_cold_integrity, verify_cold_integrity_history)
    opts = {"max_gap_hours":args.max_gap_hours,
            "allow_colocated_research":args.allow_colocated_research_only}
    if args.action == "enroll":
        result = enroll_cold_integrity(
            project,args.pin_root,args.name,args.archive,args.expected_sha256,**opts)
    elif args.action == "scan":
        result = scan_cold_integrity(project,args.pin_root,**opts)
    else:
        result = verify_cold_integrity_history(project,args.pin_root,**opts)
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    if args.action == "scan" and result["warning_count"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        # Do not disclose protected paths, certificate or private key in stderr.
        print("EraLeader encrypted native cold SHA audit rejected: "+
              type(exc).__name__,file=sys.stderr)
        raise SystemExit(2) from exc
