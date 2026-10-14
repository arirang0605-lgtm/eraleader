#!/usr/bin/env python3
"""Generate a read-only LOCAL operations status page. No live APIs or alerts."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys


def main(argv=None):
    parser=ArgumentParser(description="Offline EraLeader research operations health")
    parser.add_argument("--project",type=Path,required=True,
                        help="Existing EraLeader root (report writes only under output/operations)")
    parser.add_argument("--include-local-outbox",action="store_true",
                        help="Opt-in read-only joined operations/outbox page, no delivery")
    parser.add_argument("--marketwide-source-root",type=Path,default=None,
                        help="Opt-in refresh of latest already-verified KR marketwide research under a source output folder")
    parser.add_argument("--marketwide-publish-outbox",action="store_true",
                        help="Opt-in project-neutral PRICE WATCH20 JSON only; no recipient or orders")
    parser.add_argument("--marketwide-record-watch-history",action="store_true",
                        help="Opt-in price-only WATCH StateHistory in own SQLite; no formal leader transitions")
    args=parser.parse_args(argv)
    if args.marketwide_record_watch_history and not args.marketwide_publish_outbox:
        raise ValueError("State history requires explicit --marketwide-publish-outbox")
    if args.marketwide_publish_outbox and args.marketwide_source_root is None:
        raise ValueError("Research outbox requires --marketwide-source-root")
    root=args.project.resolve(strict=True)
    sys.path.insert(0,str(root/"src"))
    refresh=None
    if args.marketwide_source_root is not None:
        if args.marketwide_publish_outbox:
            from eraleader.marketwide_handoff_bridge import publish_latest_marketwide_handoff
            handoff=publish_latest_marketwide_handoff(
                source_root=args.marketwide_source_root,project=root,request_day="today",
                record_watch_history=args.marketwide_record_watch_history)
            refresh={
                "status":handoff.get("search_status",handoff["status"]),
                "source_market_session":handoff.get("source_market_session"),
            }
        else:
            from eraleader.marketwide_auto_refresh import refresh_latest_marketwide
            refresh=refresh_latest_marketwide(source_root=args.marketwide_source_root,
                                             project=root,request_day="today")
    if args.include_local_outbox:
        from eraleader.operations_alert_bridge import publish_operations_alert_dashboard
        report=publish_operations_alert_dashboard(root)
    else:
        from eraleader.operations_overview import publish_operations_overview
        report=publish_operations_overview(root)
    if args.marketwide_publish_outbox:
        report["marketwide_handoff_status"]=handoff["status"]
        report["marketwide_handoff_watchlist_count"]=handoff["watchlist_count"]
        report["marketwide_handoff_selected_count"]=0
        report["marketwide_handoff_orders"]=0
        report["marketwide_watch_state_status"]=handoff.get("watch_history_status","NOT_REQUESTED")
        report["marketwide_watch_state_rows"]=handoff.get("watch_history_rows",0)
        report["marketwide_verified_leader_events"]=0
    if refresh is not None:
        report["marketwide_refresh_status"]=refresh["status"]
        report["marketwide_observation_session"]=refresh.get("source_market_session")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print("EraLeader local operations research error: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
