"""Offline CLI: data -> quality -> screen -> event ledger -> web/report."""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from . import __version__
from .data import LEGACY_DEFAULT, read_market_bars
from .discovery import score_price_observations, detect_watch_changes,run_id_for
from .pit import LocalStore
from .delivery import write_dashboard,make_report,write_integrated_dashboard
from .backtest import delayed_momentum_baseline
from .offline_pit import OfflineLedger
from .offline_features import financial_snapshot
from .research import integrated_snapshot
from .discovery_metrics import evaluate_early_discovery
from .walkforward import walk_forward_split
from .state_history import StateHistory

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"output"
def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

def execute_run(args) -> dict:
    asof=date.fromisoformat(args.as_of)
    data,quality=read_market_bars(args.market,asof,days=args.days,
                      legacy_root=Path(args.legacy),tickers=args.tickers)
    snap=score_price_observations(data,args.market,args.as_of,args.top)
    snap["data_source"]=quality["source"]
    snap["quality_flags"]=quality
    rid=run_id_for(args.market,args.as_of,snap["rows"])
    snap["run_id"]=rid
    store=LocalStore(Path(args.out)/"state.sqlite")
    try:
        before=store.recent(args.market)
        events=detect_watch_changes(before,snap,rid)
        store.save_snapshot(rid,args.market,snap["market_last_observation"],snap,events)
    finally:
        store.close()
    dest=Path(args.out)/"runs"/f"{rid}.json"
    write_json(dest,snap)
    write_json(Path(args.out)/f"{args.market.lower()}_latest.json",snap)
    page=write_dashboard(snap,Path(args.out)/"site")
    return {"status":"PRICE_ONLY_RESEARCH","run_id":rid,
            "source":quality["source"],"market":args.market,
            "as_of":snap["market_last_observation"],"rows":snap["shown"],
            "events_attempted":len(events),"snapshot":str(dest),"dashboard":str(page),
            "limitation":"Fundamentals, historic membership, corporate actions/PIT not certified"}

def execute_baseline(args):
    bars,q=read_market_bars(args.market,date.fromisoformat(args.as_of),
                    days=args.days,legacy_root=Path(args.legacy),tickers=args.tickers)
    results=delayed_momentum_baseline(bars,lookback=args.lookback,
                                      top_n=args.top,rebalance=args.rebalance,
                                      weekly=(args.market=="US"))
    results["market"]=args.market;results["data_source"]=q["source"]
    results["as_of_requested"]=args.as_of
    dest=Path(args.out)/"baseline_research.json"
    write_json(dest,results)
    return {"path":str(dest),**results}

def execute_report(args) -> dict:
    db=LocalStore(Path(args.out)/"state.sqlite")
    try:snap=db.recent(args.market)
    finally:db.close()
    if not snap:
        raise RuntimeError(f"No saved market snapshot for {args.market}; run command first")
    path=Path(args.out)/"reports"/f"{args.market.lower()}_{args.period}_{snap['market_last_observation']}.md"
    make_report(snap,args.period,path)
    return {"status":"LOCAL_MARKDOWN_CREATED","path":str(path),
            "data_as_of":snap["market_last_observation"]}

def execute_alerts(args):
    db=LocalStore(Path(args.out)/"state.sqlite")
    try:
        events=db.events(pending_only=True)
        # Real delivery not connected; only write an offline preview.
        target=Path(args.out)/"alerts_preview.json"
        write_json(target,events)
        for ev in events:db.mark_dry_run(ev["event_id"])
        return {"status":"DRY_RUN_ONLY_NO_MESSAGE_SENT","count":len(events),"path":str(target)}
    finally:db.close()

def execute_offline_import(args) -> dict:
    ledger=OfflineLedger(Path(args.out)/"offline.sqlite")
    try:
        summary=ledger.import_file(Path(args.file),kind=args.kind,provenance=args.provenance)
        return {"status":"OFFLINE_IMPORT_DONE_NOT_CERTIFIED","summary":summary,
                "database":str(ledger.path),"disclaimer":"No evidence of complete point-in-time universe"}
    finally:ledger.close()

def execute_offline_features(args) -> dict:
    ledger=OfflineLedger(Path(args.out)/"offline.sqlite")
    try:
        snap=ledger.snapshot(args.as_of,market=args.market)
        scored=financial_snapshot(snap)
        # Freeze every research run. Never erase older vintages of early
        # signals; otherwise prospective detection cannot be audited.
        import hashlib
        encoded=json.dumps(scored,ensure_ascii=False,sort_keys=True)
        signature=hashlib.sha256(encoded.encode()).hexdigest()[:16]
        stamp=snap["as_of"][:16].replace("-","").replace(":","").replace("T","_")
        audit_path=Path(args.out)/"runs"/f"offline_{args.market.lower()}_{stamp}_{signature}.json"
        write_json(audit_path,scored)
        destination=Path(args.out)/f"offline_{args.market.lower()}_features.json"
        write_json(destination,scored)
        return {"status":"RESEARCH_ONLY_PIT_SOURCE_NOT_CERTIFIED",
                "path":str(destination),"immutable_run":str(audit_path),
                "companies":scored["company_count"],
                "heuristic_screen_hits":scored["research_screen_count"],
                "quality":scored["quality"]}
    finally:ledger.close()

def execute_integrated(args) -> dict:
    source=OfflineLedger(Path(args.out)/"offline.sqlite")
    try:
        offline=source.snapshot(args.as_of,market=args.market)
        price=json.loads(Path(args.price_json).read_text(encoding="utf-8")) if args.price_json else None
        result=integrated_snapshot(offline,price,args.as_of)
    finally:
        source.close()
    target=Path(args.out)/"runs"/f"joined_{args.market.lower()}_{result['run_id']}.json"
    if target.exists():
        existing=json.loads(target.read_text(encoding="utf-8"))
        if existing!=result:
            raise ValueError("Existing immutable run differs from candidate")
    else:
        write_json(target,result)
    page=write_integrated_dashboard(result,Path(args.out)/'site')
    ledger=StateHistory(Path(args.out)/'state_history.sqlite')
    try:
        observations=[{"security_id":row["security_id"],"components":{},
                       "evidence":{"financial_pit":False,
                                   "historic_universe_pit":False,
                                   "corporate_actions_pit":False},
                       "input_run_id":result["run_id"]}
                      for row in result["company_rows"]]
        tracked=ledger.record(args.market,args.as_of,observations)
    finally:
        ledger.close()
    return {"status":"OFFLINE_INTEGRATION_RESEARCH_ONLY",
            "state_events":len(tracked["new_state_events"]),"dashboard":str(page),
            "path":str(target),"company_count":result["company_count"],
            "growth_screen_hits":result["research_growth_screen_count"],
            "official_leaders":0,"pit_certified":False}

def execute_validation(args) -> dict:
    signals=json.loads(Path(args.signals).read_text(encoding="utf-8"))
    outcomes=json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    if not isinstance(signals,list) or not isinstance(outcomes,list):
        raise ValueError("Evaluation requires two JSON arrays")
    result=evaluate_early_discovery(signals,outcomes,evaluated_at=args.evaluated_at,
                                    horizon_days=args.horizon_days)
    target=Path(args.out)/"validation_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "true_early_discoveries":result["true_early_discoveries"],
            "false_discoveries":result["false_discoveries"],
            "censored":result["censored"],"note":"Synthetic/partial outcomes not performance certification"}

def execute_walkforward(args) -> dict:
    samples=json.loads(Path(args.snapshots).read_text(encoding="utf-8"))
    outcomes=json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    if not isinstance(samples,list) or not isinstance(outcomes,list):
        raise ValueError("Walkforward input must be lists")
    result=walk_forward_split(samples,outcomes,train_ends_at=args.train_ends_at,
                               test_ends_at=args.test_ends_at,embargo_days=args.embargo_days)
    target=Path(args.out)/"walkforward_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "train_samples":len(result["training"]),
            "test_candidates":len(result["test_candidates"]),
            "historic_universe_certified":False}

def main(argv=None):
    parser=argparse.ArgumentParser(prog="eraleader",description="Offline EraLeader prototype (APIs disabled)")
    parser.add_argument("--version",action="version",version=__version__)
    sub=parser.add_subparsers(dest="command",required=True)
    def common(name):
        p=sub.add_parser(name)
        p.add_argument("--market",choices=["KR","US"],default="KR")
        p.add_argument("--as-of",default="2026-10-02" if name!="baseline" else "2025-12-30")
        p.add_argument("--legacy",default=str(LEGACY_DEFAULT))
        p.add_argument("--out",default=str(OUT))
        p.add_argument("--days",type=int,default=550)
        p.add_argument("--tickers",nargs="*")
        return p
    run=common("run")
    run.add_argument("--top",type=int,default=20)
    baseline=common("baseline")
    baseline.add_argument("--top",type=int,default=3)
    baseline.add_argument("--lookback",type=int,default=26)
    baseline.add_argument("--rebalance",type=int,default=4)
    rep=sub.add_parser("report")
    rep.add_argument("period",choices=["daily","weekly","monthly"])
    rep.add_argument("--market",choices=["KR","US"],default="KR")
    rep.add_argument("--out",default=str(OUT))
    al=sub.add_parser("alerts-preview")
    al.add_argument("--out",default=str(OUT))
    srv=sub.add_parser("serve")
    srv.add_argument("--out",default=str(OUT))
    srv.add_argument("--port",type=int,default=8765)
    importer=sub.add_parser("offline-import",help="Import locally available CSV/JSON without API calls")
    importer.add_argument("--file",required=True)
    importer.add_argument("--kind",choices=["membership","actions","fundamentals","industry"])
    importer.add_argument("--provenance",choices=["synthetic_fixture","external_public_file","user_supplied"])
    importer.add_argument("--out",default=str(OUT))
    features=sub.add_parser("offline-features",help="Research-only PIT-aware growth diagnostics")
    features.add_argument("--market",choices=["KR","US"],default="KR")
    features.add_argument("--as-of",required=True,help="Timezone-aware ISO timestamp")
    features.add_argument("--out",default=str(OUT))
    join=sub.add_parser('offline-integrated',help='PIT-aligned research join')
    join.add_argument('--market',choices=['KR','US'],default='KR')
    join.add_argument('--as-of',required=True)
    join.add_argument('--price-json')
    join.add_argument('--out',default=str(OUT))
    evaluate=sub.add_parser("validate-discovery",help="Post hoc early detection quality, research only")
    evaluate.add_argument("--signals",required=True)
    evaluate.add_argument("--outcomes",required=True)
    evaluate.add_argument("--evaluated-at",required=True)
    evaluate.add_argument("--horizon-days",type=int,default=180)
    evaluate.add_argument("--out",default=str(OUT))
    wf=sub.add_parser("walkforward",help="Horizon/embargo PIT split; research only")
    wf.add_argument("--snapshots",required=True)
    wf.add_argument("--outcomes",required=True)
    wf.add_argument("--train-ends-at",required=True)
    wf.add_argument("--test-ends-at",required=True)
    wf.add_argument("--embargo-days",type=int,default=7)
    wf.add_argument("--out",default=str(OUT))
    batch=sub.add_parser("batch",help="Explicit-date offline KR+US reporting batch")
    batch.add_argument("--kr-as-of",required=True)
    batch.add_argument("--us-as-of",required=True)
    batch.add_argument("--out",default=str(OUT))
    batch.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    batch.add_argument("--days",type=int,default=550)
    batch.add_argument("--top",type=int,default=20)
    args=parser.parse_args(argv)
    try:
        if args.command=="run":result=execute_run(args)
        elif args.command=="baseline":result=execute_baseline(args)
        elif args.command=="report":result=execute_report(args)
        elif args.command=="alerts-preview":result=execute_alerts(args)
        elif args.command=="offline-import":result=execute_offline_import(args)
        elif args.command=="offline-features":result=execute_offline_features(args)
        elif args.command=="offline-integrated":result=execute_integrated(args)
        elif args.command=="validate-discovery":result=execute_validation(args)
        elif args.command=="walkforward":result=execute_walkforward(args)
        elif args.command=="batch":
            from .batch import execute_local_batch
            result=execute_local_batch(args)
        else:
            site=Path(args.out)/"site"
            site.mkdir(parents=True,exist_ok=True)
            handler=partial(SimpleHTTPRequestHandler,directory=str(site))
            with ThreadingHTTPServer(("127.0.0.1",args.port),handler) as httpd:
                print(f"EraLeader local: http://127.0.0.1:{args.port}/",flush=True)
                httpd.serve_forever()
            return
    except (ValueError,FileNotFoundError,RuntimeError) as exc:
        parser.exit(2,f"EraLeader ERROR: {exc}\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
