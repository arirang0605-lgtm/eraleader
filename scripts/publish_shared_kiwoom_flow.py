#!/usr/bin/env python3
"""Publish selected live Kiwoom demo flow in EraLeader as separate read-only evidence."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
# Direct `python scripts/...py` must also resolve the existing `scripts` package.
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, "/Volumes/T5DATA/SharedBrokerAPI/src")
from eraleader.kiwoom_shared_research_sidecar import publish


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", required=True)
    parser.add_argument("--day", required=True)
    parser.add_argument("--candidate-json", type=Path, required=True)
    parser.add_argument("--industry-json", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from shared_broker_api.client import ReadOnlyClient
        client = ReadOnlyClient("eraleader")
        state = client.status()
        if (state.get("configured", {}).get("demo") is not True
                or state.get("orders_enabled") is not False):
            raise ValueError("Read-only demo gateway unavailable")
        outcome = publish(
            client=client, stock_code=args.code, market_day=args.day,
            candidates=args.candidate_json,
            industries=args.industry_json, site=args.site,
        )
        print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ImportError):
        # Neither profile secrets nor upstream error bodies go to user logs.
        print("SHARED_KIWOOM_DEMO_SIDECAR_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
