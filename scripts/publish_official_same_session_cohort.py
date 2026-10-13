#!/usr/bin/env python3
"""Compose already captured KRX/DART/CFS/industry into a fresh research screen.

No live HTTP, trading, credentials or source-file modifications.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from eraleader.official_same_session_cohort import publish


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-out", type=Path, required=True)
    parser.add_argument("--financial-manifest", type=Path, required=True)
    parser.add_argument("--industry-manifest", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--codes", required=True, help="1-5 comma separated codes")
    args = parser.parse_args(argv)
    try:
        result = publish(
            official_out=args.official_out,
            financial_manifest=args.financial_manifest,
            industry_manifest=args.industry_manifest,
            private_root=args.private_root,
            new_output=args.out,
            codes=args.codes.split(","))
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AssertionError):
        print("SAME_SESSION_COHORT_BLOCKED", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
