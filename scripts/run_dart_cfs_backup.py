#!/usr/bin/env python3
"""Independent encrypted first-seen DART CFS SQLite snapshots and restore tests.

No vendor API, emails, broker calls, or raw-market data in printed output.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.dart_cfs_vintage_backup import (
    create_recovery_keypair, backup_vintage_ledger,
    verify_recovery_copies, verify_authenticated_recovery,
    SLOT,
)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    setup=sub.add_parser("init-keys")
    setup.add_argument("--new-key-dir",type=Path,required=True)
    backup=sub.add_parser("backup")
    backup.add_argument("--db",type=Path,required=True)
    backup.add_argument("--ssd-root",type=Path,required=True)
    backup.add_argument("--mac-root",type=Path,required=True)
    backup.add_argument("--public-cert",type=Path,required=True)
    for action in ("verify","restore-test"):
        r=sub.add_parser(action)
        r.add_argument("--ssd-snapshot",type=Path,required=True)
        r.add_argument("--mac-snapshot",type=Path,required=True)
        r.add_argument("--public-cert",type=Path,required=True)
        if action=="restore-test":
            r.add_argument("--private-key",type=Path,required=True)
            r.add_argument("--scratch-root",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.action=="init-keys":
            result=create_recovery_keypair(args.new_key_dir)
        elif args.action=="backup":
            result=backup_vintage_ledger(
                args.db,args.ssd_root,args.mac_root,args.public_cert)
        elif args.action=="verify":
            result=verify_recovery_copies(
                args.ssd_snapshot,args.mac_snapshot,args.public_cert)
        else:
            result=verify_authenticated_recovery(
                args.ssd_snapshot,args.mac_snapshot,args.public_cert,
                args.private_key,args.scratch_root)
    except (ValueError, OSError, TypeError, KeyError,
            sqlite3.DatabaseError, RuntimeError) as exc:
        # Do not expose private key path, plaintext DB, crypto CLI or tokens.
        print("DART_CFS_ENCRYPTED_RECOVERY_BLOCKED: "+
              type(exc).__name__,file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
