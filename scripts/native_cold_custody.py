#!/usr/bin/env python3
"""Export or reconstitute original native first evidence as ENCRYPTED-ONLY ZIP.

A separately stored SHA256 pin is mandatory to verify or reconstruct. No key,
plaintext, network, native WATCH re-issue, alerts or scheduled auto install.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="EraLeader encrypted-only offline custody")
    parser.add_argument("--action", choices=("export","verify","restore"), required=True)
    parser.add_argument("--project", type=Path, help="Original project root, export only")
    parser.add_argument("--slot", action="append", help="Original first hashed KR/US model slot; export only")
    parser.add_argument("--vault-root", type=Path, help="Original encrypted first-native vault, export only")
    parser.add_argument("--witness-root", type=Path, help="Original SHA-only first witness, export only")
    parser.add_argument("--recipient-cert", type=Path, help="Original PUBLIC X509 cert, export only")
    parser.add_argument("--archive", type=Path, required=True,
                        help="Original portable encrypted-only ZIP package")
    parser.add_argument("--expected-sha256", type=str,
                        help="Separately pinned ZIP SHA256 REQUIRED for verify/restore")
    parser.add_argument("--target", type=Path,
                        help="Restore ONLY: new private (0700 parent) directory")
    parser.add_argument("--allow-colocated-research-only", action="store_true",
                        help="Explicit synthetic local trial when third filesystem not mounted; NOT offsite")
    args = parser.parse_args(argv)
    if args.action == "export":
        if (not args.project or not args.slot or not args.vault_root or
                not args.witness_root or not args.recipient_cert or
                args.expected_sha256 is not None or args.target is not None):
            parser.error("export needs original --project, --slot, vault, witness, cert; no pin/target")
    elif args.action == "verify":
        if (args.project or args.slot or args.vault_root or args.witness_root or
                args.recipient_cert or args.target or not args.expected_sha256 or
                args.allow_colocated_research_only):
            parser.error("verify requires ONLY --archive and original --expected-sha256")
    else:
        if (args.project or args.slot or args.vault_root or args.witness_root or
                args.recipient_cert or not args.target or not args.expected_sha256 or
                args.allow_colocated_research_only):
            parser.error("restore needs --archive, independent --expected-sha256 and NEW --target")
    if args.action == "export":
        project = args.project.resolve(strict=True)
        sys.path.insert(0, str(project/"src"))
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.native_cold_custody import (
        create_portable_native_custody, check_portable_native_custody,
    )
    if args.action == "export":
        result = create_portable_native_custody(
            project, args.slot, args.vault_root, args.witness_root,
            args.recipient_cert, args.archive,
            allow_colocated_research=args.allow_colocated_research_only)
    else:
        result = check_portable_native_custody(
            args.archive, args.expected_sha256,
            restore_target=args.target if args.action == "restore" else None)
    if (result.get("official_leader_promotions") != 0 or
            result.get("messages_sent") != 0 or result.get("external_api_calls") != 0 or
            result.get("independent_market_pit_certified") is not False):
        raise RuntimeError("Unsafe encrypted custody status")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, FileExistsError) as exc:
        # Intentionally conceal absolute private filesystem paths in errors.
        print("EraLeader portable encrypted custody validation failed: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
