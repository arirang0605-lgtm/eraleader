#!/usr/bin/env python3
"""Read-only local recovery certificate/key and first ciphertext readiness audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="EraLeader local encrypted original recovery readiness, not a restore")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--slot", action="append", required=True,
                        help="Hashed native market-model slot, may repeat for KR/US")
    parser.add_argument("--vault-root", required=True, type=Path)
    parser.add_argument("--witness-root", required=True, type=Path)
    parser.add_argument("--recipient-cert", required=True, type=Path)
    parser.add_argument("--private-key", type=Path,
                        help="Optional local mode-600 key PUBLIC match check only")
    parser.add_argument("--warn-days", type=int, default=90)
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.native_recovery_readiness import (
        inspect_native_recovery_readiness, STATUS,
    )
    info = inspect_native_recovery_readiness(
        project, args.slot, args.vault_root, args.witness_root,
        args.recipient_cert, key=args.private_key, warning_days=args.warn_days)
    if (info.get("status") != STATUS or info.get("messages_sent") != 0 or
            info.get("external_api_calls") != 0 or
            info.get("official_leader_promotions") != 0 or
            info.get("recovery_drill_executed") is not False or
            info.get("real_future_leader_accuracy_certified") is not False):
        raise RuntimeError("Unsafe or incomplete native recovery readiness output")
    print(json.dumps(info, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        # Fail without showing key/cert/source paths or subprocess stderr.
        print("EraLeader local recovery readiness failed: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
