#!/usr/bin/env python3
"""Publish EraLeader candidate universe to a receiver-neutral JSON outbox.

Two source modes:
  --research-cohort : preliminary WATCH research, *never* qualified leaders.
  --state-ledger    : state history POTENTIAL/CONFIRMED leaders, weaken/exit.
A consumer still makes all strategy, risk and broker decisions independently.
"""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.strategy_handoff import (
    publish_handoff, research_cohort_handoff, state_history_handoff,
    marketwide_research_handoff, publish_versioned_handoff, verify_handoff,
)


def main(argv=None) -> int:
    parser = ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--research-cohort",type=Path,
                       help="Existing signed KR candidates+industry research folder")
    group.add_argument("--marketwide-report",type=Path,
                       help="Observed complete KRX price WATCH20 with available partial DART")
    group.add_argument("--state-ledger",type=Path,
                       help="Existing local Stage4 state_history.sqlite, read-only")
    parser.add_argument("--market",choices=["KR","US"],default="KR")
    parser.add_argument("--identity-ledger",type=Path,
                        help="Optional existing PIT membership SQLite for permanent ID to ticker lookup (read-only)")
    parser.add_argument("--as-of",default="today",
                        help="Requested date or timezone-aware decision timestamp")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out",type=Path,
                        help="New EraLeader-owned JSON publication file; recipient integration is deferred")
    destination.add_argument("--outbox-dir",type=Path,
                        help="Existing EraLeader-owned directory: immutable source-date version files")
    args = parser.parse_args(argv)
    try:
        as_of = args.as_of
        if as_of == "today":
            zone = ZoneInfo("Asia/Seoul" if args.market == "KR" else "America/New_York")
            as_of = datetime.now(zone).date().isoformat()
        if args.marketwide_report:
            if args.identity_ledger is not None or args.market != "KR" or len(as_of) != 10:
                raise ValueError("MARKETWIDE_KR_RESEARCH_ONLY")
            report = marketwide_research_handoff(args.marketwide_report,
                                                 request_day=as_of)
        elif args.research_cohort:
            if args.identity_ledger is not None:
                raise ValueError("RESEARCH_COHORT_IDENTITY_LEDGER_NOT_APPLICABLE")
            if args.market != "KR" or len(as_of) != 10:
                raise ValueError("KR_RESEARCH_COHORT_NEEDS_MARKET_LOCAL_DATE")
            report = research_cohort_handoff(args.research_cohort,request_day=as_of)
        else:
            report = state_history_handoff(args.state_ledger,market=args.market,
                                           as_of=as_of,identity_ledger=args.identity_ledger)
        delivery = (publish_versioned_handoff(report,args.outbox_dir)
                    if args.outbox_dir is not None
                    else publish_handoff(report,args.out))
        print(json.dumps({
            **delivery, "market":report["market"],
            "feed_status":report["status"],
            "execution_authority":False,
            "source_kind":report["source_kind"],
        },ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,OSError,TypeError,KeyError,OverflowError):
        print("ERALEADER_STRATEGY_HANDOFF_BLOCKED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
