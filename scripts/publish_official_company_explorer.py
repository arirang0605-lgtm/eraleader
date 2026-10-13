#!/usr/bin/env python3
"""Publish a searchable KR stock-detail site from an EXISTING verified cohort.

No provider requests or market DB changes. This exposes actual price+earnings+
industry research with explicit observation and receipt times.
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
from eraleader.official_company_explorer import publish_company_explorer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path,
                        help="Previously published complete KR price+CFS+industry cohort directory")
    parser.add_argument("--out", required=True, type=Path,
                        help="New HTML+JSON research directory. Existing folders are preserved.")
    parser.add_argument("--day", default="today",
                        help="Requested KST research date YYYY-MM-DD or today")
    args = parser.parse_args(argv)
    try:
        day = (datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
               if args.day == "today" else args.day)
        result = publish_company_explorer(cohort=args.cohort, output=args.out,
                                          request_day=day)
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        print("OFFICIAL_COMPANY_EXPLORER_BLOCKED", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "RESEARCH_COMPANY_SEARCH_READY",
        "market_session": result["source_market_session"],
        "requested_day": result["request_day"],
        "research_companies": result["research_company_count"],
        "companies_with_peer_comparisons": result["companies_with_peers"],
        "stale_warning": result["stale_warning"],
        "official_leaders": 0,
        "output": str(args.out / "index.html"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
