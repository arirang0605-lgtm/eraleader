#!/usr/bin/env python3
"""Explicit local encrypted-first-native backup, verification and NEW restore."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline AES-256-GCM/RSA-OAEP private native evidence vault, never uploads")
    parser.add_argument("--action", required=True, choices=("backup", "verify", "restore"))
    parser.add_argument("--project", type=Path, help="Required only for first backup")
    parser.add_argument("--plan", type=Path, help="Original pinned native plan, backup only")
    parser.add_argument("--capture-root", type=Path, help="Original first native captures root")
    parser.add_argument("--vault-root", type=Path, required=True,
                        help="Separate private local filesystem, mode 700")
    parser.add_argument("--witness-root", type=Path, required=True,
                        help="Existing first cross-volume SHA-only witness, mode 700")
    parser.add_argument("--recipient-cert", type=Path, required=True,
                        help="Public RSA recipient certificate; no private key on backup")
    parser.add_argument("--slot", help="Hashed market/model slot shown after first backup")
    parser.add_argument("--private-key", type=Path,
                        help="Restore ONLY: mode-600 RSA recipient private key")
    parser.add_argument("--target", type=Path,
                        help="Restore ONLY: new previously nonexistent private folder")
    args = parser.parse_args(argv)
    if args.action == "backup":
        if (args.project is None or args.plan is None or args.slot is not None or
                args.target is not None or args.private_key is not None):
            parser.error("backup requires --project and --plan, without restore/key options")
    elif args.action == "verify":
        if (args.slot is None or args.plan is not None or args.capture_root is not None or
                args.private_key is not None or args.target is not None):
            parser.error("verify requires --slot and no restore or first-capture inputs")
    else:
        if (args.slot is None or args.target is None or args.private_key is None or
                args.plan is not None or args.capture_root is not None):
            parser.error("restore requires --slot, --target, --private-key; no --plan")
    # When SSD has been lost, recover from a separate Mac volume: no project needed.
    code_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(code_root / "src"))
    from eraleader.native_encrypted_vault import (
        backup_encrypted_native_original, verify_encrypted_native_original,
        restore_encrypted_native_original,
    )
    if args.action == "backup":
        project = args.project.resolve(strict=True)
        capture = args.capture_root if args.capture_root is not None else (
            project / "output" / "native_first_captures")
        result = backup_encrypted_native_original(
            project, args.plan, capture, args.witness_root, args.vault_root,
            args.recipient_cert)
    elif args.action == "verify":
        result = verify_encrypted_native_original(
            args.vault_root, args.slot, args.witness_root, args.recipient_cert)
    else:
        result = restore_encrypted_native_original(
            args.vault_root, args.slot, args.witness_root, args.recipient_cert,
            args.private_key, args.target, project=args.project)
    if (result.get("messages_sent") != 0 or result.get("external_api_calls") != 0 or
            result.get("official_leader_promotions") != 0 or
            result.get("real_future_leader_accuracy_certified") is not False):
        raise RuntimeError("Original native encrypted vault result not safe")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, FileExistsError) as exc:
        # Never emit subprocess stderr or a raw original/source path.
        print("EraLeader encrypted original vault: local validation failed ("
              + type(exc).__name__ + ")", file=sys.stderr)
        raise SystemExit(2) from exc
