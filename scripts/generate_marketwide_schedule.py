#!/usr/bin/env python3
"""Prepare an owner-only weekday launchd plist for local KR research refresh.

This command never installs, starts or loads a job. Installation is a
separate operational decision. It neither calls market APIs nor places orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eraleader.marketwide_schedule import generate_marketwide_plist


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--hour", type=int, default=18,
                        help="Mac local time, Asia/Seoul on configured Mac")
    parser.add_argument("--minute", type=int, default=40)
    args = parser.parse_args(argv)
    try:
        state = generate_marketwide_plist(
            project=args.project, source_root=args.source_root,
            destination=args.out, hour=args.hour, minute=args.minute,
        )
    except (ValueError, OSError, TypeError):
        print("KR_MARKETWIDE_SCHEDULE_NOT_PREPARED", file=sys.stderr)
        return 2
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
