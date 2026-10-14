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
    args=parser.parse_args(argv)
    root=args.project.resolve(strict=True)
    sys.path.insert(0,str(root/"src"))
    refresh=None
    if args.marketwide_source_root is not None:
        from eraleader.marketwide_auto_refresh import refresh_latest_marketwide
        refresh=refresh_latest_marketwide(source_root=args.marketwide_source_root,
                                         project=root,request_day="today")
    if args.include_local_outbox:
        from eraleader.operations_alert_bridge import publish_operations_alert_dashboard
        report=publish_operations_alert_dashboard(root)
    else:
        from eraleader.operations_overview import publish_operations_overview
        report=publish_operations_overview(root)
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
