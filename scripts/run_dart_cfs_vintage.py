#!/usr/bin/env python3
"""Register DART fiscal report *vintages*, review what EraLeader actually knew.

No provider HTTP calls, no credentials, no historical PIT promotion.
DART original source paths and SHA pins are explicitly supplied by operator.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sqlite3
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.official_dart_vintage_registry import DartCFSVintageRegistry


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_subparsers(dest="command",required=True)
    record=group.add_parser("register",help="Append one SHA-verified FY CFS capture")
    record.add_argument("--db",required=True,type=Path)
    record.add_argument("--first-capture",required=True,type=Path)
    record.add_argument("--first-sha256",required=True)
    record.add_argument("--directory",required=True,type=Path)
    record.add_argument("--directory-sha256",required=True)
    check=group.add_parser("as-of",help="Review available first source vintages")
    check.add_argument("--db",required=True,type=Path)
    check.add_argument("--decision-at",required=True)
    check.add_argument("--stock-code",required=True)
    check.add_argument("--corp-code",required=True)
    check.add_argument("--fiscal-year",required=True,type=int)
    head=group.add_parser("checksum",help="Audit local append-only hash chain")
    head.add_argument("--db",required=True,type=Path)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=="register" and not args.db.exists():
            # Preserve fail-closed source semantics even before making an
            # empty local research database. Only a pinned original qualifies.
            from eraleader.official_dart_financials import verify_dart_financial
            verify_dart_financial(args.first_capture,args.first_sha256,
                                  decision_at=datetime.now(timezone.utc),
                                  directory=(args.directory,args.directory_sha256))
        with DartCFSVintageRegistry(args.db,read_only=args.command!="register") as db:
            if args.command=="register":
                result=db.register_verified(
                    args.first_capture,args.first_sha256,
                    directory=(args.directory,args.directory_sha256))
            elif args.command=="as-of":
                result=db.review_as_of(decision_at=args.decision_at,
                                       stock_code=args.stock_code,
                                       corp_code=args.corp_code,
                                       fiscal_year=args.fiscal_year)
            else:
                result=db.checksum()
        print(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False))
        return 0
    except (ValueError,KeyError,TypeError,OSError,RuntimeError,sqlite3.DatabaseError) as exc:
        # Never expose a token, licensed raw financial body, or private path.
        print("DART_VINTAGE_RESEARCH_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
