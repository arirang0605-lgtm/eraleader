#!/usr/bin/env python3
"""Explicit offline encrypted first-native SHA DRY-RUN alert monitor.

Only checks hashed ciphertext receipts and the already pinned external first
witness. Requires no private key and never transmits, repairs, or installs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="EraLeader local-only encrypted original SHA watchdog")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--slot", action="append", required=True,
                        help="Hashed first-native KR/US market-model slot; repeat per cohort")
    parser.add_argument("--vault-root", type=Path, required=True,
                        help="Separate-device encrypted first ZIP root")
    parser.add_argument("--witness-root", type=Path, required=True,
                        help="Original separate-device first SHA witness root")
    parser.add_argument("--recipient-cert", type=Path, required=True,
                        help="Original RSA public certificate only; never private key")
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.native_encrypted_watchdog import run_native_encrypted_watchdog
    result = run_native_encrypted_watchdog(
        project, args.slot, args.vault_root, args.witness_root,
        args.recipient_cert)
    if (result.get("status") != "LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED" or
            result.get("local_artifacts_only") is not True or
            result.get("authenticated_plaintext_verified") is not False or
            result.get("messages_sent") != 0 or
            result.get("external_api_calls") != 0 or
            result.get("official_leader_promotions") != 0 or
            result.get("real_future_leader_accuracy_certified") is not False):
        raise RuntimeError("Unsafe encrypted original DRY-RUN summary")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        # Intentionally do not output local vault/source/cert/private paths.
        print("EraLeader encrypted DRY-RUN monitor rejected unsafe state: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
