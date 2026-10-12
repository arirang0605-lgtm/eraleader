#!/usr/bin/env python3
"""Explicit local recovery rehearsal cadence check; SHA-only, never decrypt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="EraLeader native original recovery DRY-RUN due review")
    parser.add_argument("--action", choices=("audit", "verify-history"), default="audit")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--slot", action="append", help="KR/US hashed first model; repeat")
    parser.add_argument("--vault-root", required=True, type=Path)
    parser.add_argument("--witness-root", required=True, type=Path)
    parser.add_argument("--recipient-cert", required=True, type=Path)
    parser.add_argument("--scratch-root", required=True, type=Path,
                        help="Existing private 0700 recovery scratch location")
    parser.add_argument("--due-days", type=int, default=30,
                        help="First verified drill expires after N calendar days")
    parser.add_argument("--warn-days", type=int, default=7,
                        help="Days before expiry to show local warning")
    args = parser.parse_args(argv)
    if args.action == "audit" and not args.slot:
        parser.error("audit needs explicit --slot (repeat for all cohorts)")
    if args.action == "verify-history" and args.slot:
        parser.error("verify-history audits existing first SHA chain without --slot")
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.native_recovery_due import (
        run_recovery_due_watchdog, verify_recovery_due_history, STATUS,
    )
    if args.action == "audit":
        result = run_recovery_due_watchdog(
            project, args.slot, args.vault_root, args.witness_root,
            args.recipient_cert, args.scratch_root,
            due_days=args.due_days, warn_days=args.warn_days)
        if result.get("status") != STATUS or result.get("local_artifacts_only") is not True:
            raise RuntimeError("Recovery due observer failed")
    else:
        result = verify_recovery_due_history(
            project, args.vault_root, args.witness_root,
            args.recipient_cert, args.scratch_root,
            due_days=args.due_days, warn_days=args.warn_days)
    if (result.get("messages_sent") != 0 or
            result.get("external_api_calls") != 0 or
            result.get("official_leader_promotions") != 0):
        raise RuntimeError("Unsafe recovery due status")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        # No original source paths or private key filenames in CLI stderr.
        print("EraLeader recovery due DRY-RUN rejected unsafe evidence: "+
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
