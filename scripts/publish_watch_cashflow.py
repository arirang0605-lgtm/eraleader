#!/usr/bin/env python3
"""Publish annual cashflow details for an existing verified WATCH edition."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from eraleader.dart_cashflow_watch import publish_watch_cashflow
from eraleader.operations_overview import publish_operations_overview


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--marketwide-report", type=Path, required=True)
    parser.add_argument("--watch-manifest", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = publish_watch_cashflow(project=args.project,
            marketwide=args.marketwide_report, watch_manifest=args.watch_manifest,
            capture_root=args.capture_root)
        result["operations"] = publish_operations_overview(args.project)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError):
        print("WATCH_ANNUAL_CASHFLOW_BLOCKED: verified source/publication", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
