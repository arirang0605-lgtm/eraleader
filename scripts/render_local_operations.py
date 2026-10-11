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
    args=parser.parse_args(argv)
    root=args.project.resolve(strict=True)
    sys.path.insert(0,str(root/"src"))
    if args.include_local_outbox:
        from eraleader.operations_alert_bridge import publish_operations_alert_dashboard
        report=publish_operations_alert_dashboard(root)
    else:
        from eraleader.operations_overview import publish_operations_overview
        report=publish_operations_overview(root)
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print("EraLeader local operations research error: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
