#!/usr/bin/env python3
"""Create an all-stock searchable research site from completed KR marketwide JSON.

Never calls KRX/DART or touches WATCH, scores, strategy outboxes or accounts.
The data may be historical; its actual market observation date is prominent.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import json
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eraleader.marketwide_live_search import publish_search


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path,
                   help="Completed, SHA-verified existing marketwide_kr.json")
    p.add_argument("--out", required=True, type=Path,
                   help="Brand-new folder for self-contained HTML and report manifest")
    p.add_argument("--day", default="today",
                   help="Requested Korean date YYYY-MM-DD or today; does not change source market date")
    args = p.parse_args(argv)
    day = (datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
           if args.day == "today" else args.day)
    try:
        result = publish_search(input_report=args.source, output=args.out,
                                request_day=day)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        # Do not print private raw source paths/provider data on error.
        print("KR_MARKETWIDE_SEARCH_BLOCKED", file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
