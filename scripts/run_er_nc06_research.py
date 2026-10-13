#!/usr/bin/env python3
"""Run ER-NC-06 against one pinned local NewsCatalystOS export, without API calls.

Never emits article text, trading instructions or provider credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from eraleader.news_catalyst_adapter import NewsCatalystEvents
from eraleader.news_market_response import (
    LocalAnomalyQueryCache, diagnose_news_market_response, make_anomaly_news_query,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local PIT news↔market research, no network")
    parser.add_argument("--news-export", required=True, type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--market-session", required=True)
    parser.add_argument("--market-data-available-at", required=True)
    parser.add_argument("--security-id", required=True)
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--issuer-mapping-available-at", required=True)
    parser.add_argument("--excess-return-pct", type=float, required=True)
    parser.add_argument("--turnover-multiple", type=float, required=True)
    parser.add_argument("--anomaly-type", choices=(
        "STRONG_EXCESS_RETURN", "TURNOVER_SPIKE", "PRICE_NEWS_DIVERGENCE"
    ), default="STRONG_EXCESS_RETURN")
    parser.add_argument("--query-window-days", type=int, default=5)
    return parser


def run_study(args: argparse.Namespace) -> dict:
    # A caller-maintained SHA PIN must match bytes verified by the read-only
    # adapter. This does not independently certify historic publication rights.
    pinned = args.expected_source_sha256
    if type(pinned) is not str or re.fullmatch(r"[0-9a-f]{64}", pinned) is None:
        raise ValueError("Expected independent SHA256 pin")
    collection = NewsCatalystEvents.load(args.news_export)
    if collection.source_sha256 != pinned:
        raise ValueError("News export SHA256 differs from independent pin")
    snapshot = collection.snapshot(args.as_of, mode="LIVE_OBSERVED")
    response = diagnose_news_market_response(
        security_id=args.security_id,
        issuer_id=args.issuer_id,
        issuer_mapping_available_at=args.issuer_mapping_available_at,
        news_snapshot=snapshot,
        as_of=args.as_of,
        market_session=args.market_session,
        market_data_available_at=args.market_data_available_at,
        excess_return_pct=args.excess_return_pct,
        turnover_multiple=args.turnover_multiple,
    )
    query = make_anomaly_news_query(
        security_id=args.security_id, theme_id=None, as_of=args.as_of,
        anomaly_type=args.anomaly_type, window_days=args.query_window_days,
    )
    queued = LocalAnomalyQueryCache().request(query)
    return {
        "schema": "eraleader.er_nc06_local_research.v1",
        "export_source_sha256": collection.source_sha256,
        "news_snapshot_quality": snapshot["quality_status"],
        "news_snapshot_as_of": snapshot["as_of"],
        "market_diagnostic": response,
        "anomaly_local_query": query,
        "query_cache_receipt": queued,
        "network_calls": 0,
        "research_only": True,
        "trading_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = run_study(args)
    except (ValueError, TypeError, KeyError, OSError, IndexError) as exc:
        # No raw file path, source URL, license text or API token in stderr.
        print("ER_NC06_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
