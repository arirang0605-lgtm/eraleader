#!/usr/bin/env python3
"""External/offline recipient public-certificate key escrow.

No external private key is generated, read or copied for 'export'/'verify'.
An external private key is ONLY read temporarily during an explicit drill.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.dart_cfs_external_key_escrow import (
    prepare_external_key_escrow, verify_external_key_escrow,
    drill_external_key_escrow,
)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    exp=sub.add_parser("export",help="Encrypt original private recovery key for an independent recipient")
    exp.add_argument("--original-private-key",type=Path,required=True)
    exp.add_argument("--original-public-cert",type=Path,required=True)
    exp.add_argument("--external-public-cert",type=Path,required=True)
    exp.add_argument("--escrow-root",type=Path,required=True)
    verify=sub.add_parser("verify",help="Read-only SHA/independent public cert gate")
    verify.add_argument("--escrow",type=Path,required=True)
    verify.add_argument("--original-public-cert",type=Path,required=True)
    verify.add_argument("--external-public-cert",type=Path,required=True)
    drill=sub.add_parser("drill",help="Actual external private-key -> original CFS backup restore")
    drill.add_argument("--escrow",type=Path,required=True)
    drill.add_argument("--original-public-cert",type=Path,required=True)
    drill.add_argument("--external-public-cert",type=Path,required=True)
    drill.add_argument("--external-private-key",type=Path,required=True)
    drill.add_argument("--ssd-snapshot",type=Path,required=True)
    drill.add_argument("--mac-snapshot",type=Path,required=True)
    drill.add_argument("--scratch-root",type=Path,required=True)
    a=parser.parse_args(argv)
    try:
        if a.action=="export":
            result=prepare_external_key_escrow(
                a.original_private_key,a.original_public_cert,
                a.external_public_cert,a.escrow_root)
        elif a.action=="verify":
            result=verify_external_key_escrow(
                a.escrow,a.original_public_cert,a.external_public_cert)
        else:
            result=drill_external_key_escrow(
                a.escrow,a.original_public_cert,a.external_public_cert,
                a.external_private_key,a.ssd_snapshot,a.mac_snapshot,
                a.scratch_root)
    except (ValueError,OSError,TypeError,KeyError,sqlite3.DatabaseError,
            RuntimeError) as exc:
        # Do not show raw key, key path, CMS error text, credentials or source DB.
        print("EXTERNAL_KEY_ESCROW_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
