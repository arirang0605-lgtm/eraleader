"""One offline batch entry point for both markets, reports and alert previews.

No scheduler is installed, no live notifications, no external API.
Explicit as-of dates prevent silent assumptions of real-time prices.
"""
from __future__ import annotations
from argparse import Namespace
from pathlib import Path
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from .cli import (execute_run, execute_report, execute_alerts, execute_integrated,
                  read_market_bars, score_price_observations, run_id_for,
                  integrated_snapshot, write_json)
from .offline_pit import OfflineLedger

PERIODS=("daily","weekly","monthly")

def execute_local_batch(args: Namespace) -> dict:
    # Explicit opt-in only. Scheduled price-only reporting does NOT silently
    # convert its cache into corporate PIT/fundamental research candidates.
    integrate=getattr(args,"integrate_pit_research",False)
    decisions={"KR":getattr(args,"kr_decision_at",None),
               "US":getattr(args,"us_decision_at",None)}
    if type(integrate) is not bool:
        raise ValueError("PIT batch integration opt-in must be boolean")
    if not integrate and any(x is not None for x in decisions.values()):
        raise ValueError("Decision timestamps require explicit PIT research opt-in")
    prepared={}
    if integrate:
        if not all(isinstance(x,str) and x.strip() for x in decisions.values()):
            raise ValueError("Both market-local decision timestamps are required")
        for market,day in (("KR",args.kr_as_of),("US",args.us_as_of)):
            try:
                stamp=datetime.fromisoformat(decisions[market].replace("Z","+00:00"))
            except ValueError as exc:
                raise ValueError("Invalid PIT batch decision timestamp") from exc
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("PIT batch decisions must be timezone-aware")
            zone=ZoneInfo("Asia/Seoul" if market=="KR" else "America/New_York")
            if stamp.astimezone(zone).date().isoformat()!=day:
                raise ValueError("PIT batch decision disagrees with exchange-local market day")
        db=Path(args.out)/"offline.sqlite"
        if not db.is_file() or db.is_symlink():
            raise FileNotFoundError("Existing local offline.sqlite required for PIT batch")
        ledger=OfflineLedger(db)
        try:
            # Preflight BOTH markets before creating any dashboards, state
            # events, WATCH records or dry-run alerts. A bad second-market
            # price/PIT join must never leave a partial first-market run.
            for market,asof in (("KR",args.kr_as_of),("US",args.us_as_of)):
                snapshot=ledger.snapshot(decisions[market],market=market)
                if not snapshot["members"]:
                    raise ValueError(f"Missing usable then-known {market} PIT membership")
                bars,quality=read_market_bars(
                    market,date.fromisoformat(asof),
                    days=args.days,legacy_root=Path(args.legacy),tickers=None)
                price=score_price_observations(bars,market,asof,args.top)
                price["data_source"]=quality["source"]
                price["quality_flags"]=quality
                price["run_id"]=run_id_for(market,asof,price["rows"])
                candidate=integrated_snapshot(snapshot,price,decisions[market])
                if candidate.get("pit_certified") is not False or candidate.get("confirmed_leaders") != 0:
                    raise ValueError("Uncertified PIT preflight cannot promote leaders")
                prepared[market]=price
        finally:
            ledger.close()
    manifests=[]
    for market,asof in (("KR",args.kr_as_of),("US",args.us_as_of)):
        result=execute_run(Namespace(market=market,as_of=asof,days=args.days,
                                     legacy=args.legacy,out=args.out,
                                     tickers=None,top=args.top,
                                     prepared_snapshot=prepared.get(market)))
        integrated=None
        if integrate:
            integrated=execute_integrated(Namespace(
                market=market,as_of=decisions[market],out=args.out,
                price_json=result["snapshot"]))
            if integrated.get("official_leaders") != 0 or integrated.get("pit_certified") is not False:
                raise ValueError("Uncertified PIT batch cannot publish official leaders")
        reports=[]
        for period in PERIODS:
            report=execute_report(Namespace(market=market,period=period,out=args.out))
            reports.append(str(report["path"]))
        manifests.append({
            "market":market,"requested_date":asof,"market_observation_at":result["as_of"],
            "run_id":result["run_id"],"research_rows":result["rows"],
            "reports":reports, "dashboard":result["dashboard"],
            "pit_research":({
                "status":integrated["status"],
                "as_of":decisions[market],
                "deferred_screens":integrated["deferred_research_screens"],
                "new_watch_research_signals":integrated["new_prospective_research_signals"],
                "research_dashboard":integrated["dashboard"],
                "official_leaders":0,"pit_certified":False,
            } if integrate else None)})
    preview=execute_alerts(Namespace(out=args.out))
    summary={
        "status":"OFFLINE_BATCH_RESEARCH_ONLY",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "markets":manifests,
        "alert_preview_count":preview["count"],
        "dry_run_only":True, "external_api_calls":0, "messages_sent":0,
        "explicit_offline_pit_research":integrate,
        "official_leaders_confirmed":0,
        "note":"Historical price caches may be stale. This batch does not issue live leader recommendations."
    }
    target=Path(args.out)/"batch_manifest.json"
    write_json(target,summary)
    return {"status":summary["status"],"manifest":str(target),
            "market_count":len(manifests),"reports_created":len(manifests)*3,
            "alerts_dry_run":preview["count"],
            "integrated_research_markets":len(manifests) if integrate else 0}
