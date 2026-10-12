#!/usr/bin/env python3
"""Explicit native encrypted original recovery drill, with disposable plaintext.

Actual AES-GCM decrypt + original WATCH/score/census replay occurs only with
--action run AND an explicitly supplied owner-only private key. No network,
hardware unplug/reboot, launchd installation or live notification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local original encrypted evidence recovery rehearsal")
    parser.add_argument("--action", choices=("run", "verify-history"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--slot", help="Hashed KR/US first native model slot")
    parser.add_argument("--vault-root", type=Path, required=True)
    parser.add_argument("--witness-root", type=Path, required=True)
    parser.add_argument("--recipient-cert", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True,
                        help="Existing mode-0700 location on different filesystem")
    parser.add_argument("--private-key", type=Path, help="Required ONLY for run; never logged")
    args = parser.parse_args(argv)
    if args.action == "run":
        if args.slot is None or args.private_key is None:
            parser.error("run requires explicit original --slot and --private-key")
    elif args.slot is not None or args.private_key is not None:
        parser.error("verify-history does not access a slot or any private key")
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.native_recovery_drill import (
        run_native_recovery_drill, verify_native_recovery_drill_history,
        STATUS,
    )
    if args.action == "verify-history":
        report = verify_native_recovery_drill_history(
            project, args.vault_root, args.witness_root,
            args.recipient_cert, args.scratch_root)
    else:
        report = run_native_recovery_drill(
            project, args.slot, args.vault_root, args.witness_root,
            args.recipient_cert, args.private_key, args.scratch_root)
    if (report.get("messages_sent") != 0 or report.get("external_api_calls") != 0 or
            report.get("official_leader_promotions") != 0):
        raise RuntimeError("Unsafe first native recovery drill result")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if args.action == "run" and (
            report.get("status") != STATUS or
            report.get("latest", {}).get("outcome") != "PASSED"):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, FileExistsError) as exc:
        # Do not display local certificate/private-key/backup source paths.
        print("EraLeader local recovery drill failed validation: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
