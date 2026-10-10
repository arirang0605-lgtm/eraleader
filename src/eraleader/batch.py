"""One offline batch entry point for both markets, reports and alert previews.

No scheduler is installed, no live notifications, no external API.
Explicit as-of dates prevent silent assumptions of real-time prices.
"""
from __future__ import annotations
from argparse import Namespace
from pathlib import Path
from datetime import datetime, timezone
from .cli import execute_run, execute_report, execute_alerts, write_json

PERIODS=("daily","weekly","monthly")

def execute_local_batch(args: Namespace) -> dict:
    manifests=[]
    for market,asof in (("KR",args.kr_as_of),("US",args.us_as_of)):
        result=execute_run(Namespace(market=market,as_of=asof,days=args.days,
                                     legacy=args.legacy,out=args.out,
                                     tickers=None,top=args.top))
        reports=[]
        for period in PERIODS:
            report=execute_report(Namespace(market=market,period=period,out=args.out))
            reports.append(str(report["path"]))
        manifests.append({
            "market":market,"requested_date":asof,"market_observation_at":result["as_of"],
            "run_id":result["run_id"],"research_rows":result["rows"],
            "reports":reports, "dashboard":result["dashboard"]})
    preview=execute_alerts(Namespace(out=args.out))
    summary={
        "status":"OFFLINE_BATCH_RESEARCH_ONLY",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "markets":manifests,
        "alert_preview_count":preview["count"],
        "dry_run_only":True, "external_api_calls":0, "messages_sent":0,
        "note":"Historical price caches may be stale. This batch does not issue live leader recommendations."
    }
    target=Path(args.out)/"batch_manifest.json"
    write_json(target,summary)
    return {"status":summary["status"],"manifest":str(target),
            "market_count":len(manifests),"reports_created":len(manifests)*3,
            "alerts_dry_run":preview["count"]}
