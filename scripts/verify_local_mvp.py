#!/usr/bin/env python3
"""Offline whole-path smoke: saved analyses, reports, local web HTTP, event ledger."""
from pathlib import Path
import json
import sqlite3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output"

def main() -> None:
    for market in ("kr","us"):
        snap=json.loads((OUT/f"{market}_latest.json").read_text())
        assert snap["classification_quality"]=="PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"
        assert snap["shown"]==20, market
        assert all(row["total_score_100"] is None and row["state"]=="WATCH" for row in snap["rows"])
        assert snap["source_market"]==market.upper()
        assert not snap["quality_flags"]["financial_pit_verified"]
    kr=json.loads((OUT/"kr_latest.json").read_text())
    assert kr["quality_flags"]["halted_observation_rows"]>100
    assert kr["quality_flags"]["excluded_anomalous_rows"]>=1
    for name in ("kr_daily_2026-10-02.md","kr_weekly_2026-10-02.md",
                 "kr_monthly_2026-10-02.md","us_weekly_2026-02-23.md"):
        content=(OUT/"reports"/name).read_text()
        assert "검증" in content
    conn=sqlite3.connect(OUT/"state.sqlite")
    try:
        events=conn.execute("select count(*) from events").fetchone()[0]
        unique=conn.execute("select count(distinct event_id) from events").fetchone()[0]
        assert events==unique and events>=40
    finally: conn.close()
    handler=partial(SimpleHTTPRequestHandler,directory=str(OUT/"site"))
    server=ThreadingHTTPServer(("127.0.0.1",0),handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for page in ("index.html","kr.html","us.html"):
            with urlopen(f"http://127.0.0.1:{server.server_port}/{page}",timeout=5) as r:
                data=r.read().decode("utf-8")
                assert r.status==200 and "EraLeader" in data
    finally:
        server.shutdown();thread.join(timeout=4);server.server_close()
    print(json.dumps({
        "status":"PASS_LOCAL_END_TO_END",
        "country_pages_tested":2,
        "reports_checked":4,
        "alert_events_unique":events,
        "api_calls":0,"http_paths_verified":3,
        "official_leaders_confirmed":0,
        "limitations":"PRICE_ONLY, NO_FUNDAMENTAL_PIT, NO_CERTIFIED_BACKTEST"
    },ensure_ascii=False))

if __name__=="__main__":
    main()
