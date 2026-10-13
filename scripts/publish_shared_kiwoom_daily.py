#!/usr/bin/env python3
"""Create one immutable daily batch of selected demo investor-flow research."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, "/Volumes/T5DATA/SharedBrokerAPI/src")
from eraleader.kiwoom_shared_daily_batch import daily_batch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", required=True, help="Explicit KR market day YYYYMMDD")
    ap.add_argument("--codes", required=True, help="1..5 selected 6-digit KR security codes")
    ap.add_argument("--candidate-json", type=Path, required=True)
    ap.add_argument("--industry-json", type=Path, required=True)
    ap.add_argument("--site", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        from shared_broker_api.client import ReadOnlyClient
        client = ReadOnlyClient("eraleader")
        status = client.status()
        if (status.get("orders_enabled") is not False or
                status.get("configured", {}).get("demo") is not True):
            raise ValueError("DEMO_GATEWAY_UNAVAILABLE")
        output = daily_batch(
            client=client, stock_codes=args.codes.split(","), market_day=args.day,
            candidates=args.candidate_json, industries=args.industry_json,
            site=args.site,
        )
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError, ImportError) as exc:
        # Only emit allowlisted internal error codes. Never log provider payloads.
        safe_codes = {"Future/retrospective shared receipt denied",
                      "FLOW_NOT_YET_AVAILABLE_AT_DECISION_TIME",
                      "SELECTED_STOCK_FLOW_REQUIRES_AWARE_CLOCK",
                      "SOURCE_CONTRADICTION", "FUTURE_COHORT_DATE",
                      "DAILY_BATCH_ALREADY_PUBLISHED",
                      "Expected bounded 20-observation research source",
                      "PROVIDER_UNAVAILABLE", "MAIN_INDEX_NOT_LINKABLE"}
        detail = str(exc) if str(exc) in safe_codes else type(exc).__name__
        print("KIWOOM_DAILY_RESEARCH_BLOCKED:" + detail, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
