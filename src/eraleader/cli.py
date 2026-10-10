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
from .delivery import write_dashboard,make_report
from .backtest import delayed_momentum_baseline

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
    args=parser.parse_args(argv)
    try:
        if args.command=="run":result=execute_run(args)
        elif args.command=="baseline":result=execute_baseline(args)
        elif args.command=="report":result=execute_report(args)
        elif args.command=="alerts-preview":result=execute_alerts(args)
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
