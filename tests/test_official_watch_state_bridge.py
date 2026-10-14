"""Actual Stage4 state history integration with checksum-verified price WATCH."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest
from eraleader import official_watch_state_bridge as bridge
from eraleader.official_marketwide_coverage import SCHEMA
from eraleader.official_company_explorer import canonical
from eraleader.state_history import StateHistory

NOW = datetime(2026,10,14,13,tzinfo=timezone.utc)


def _source(tmp_path, day="2026-10-08", *, newest=False, price=23.4, built=NOW):
    rows=[]
    for pos in range(1,21):
        n=pos+(1 if newest else 0)
        rows.append({
            "security_id":f"{n:06}","name":f"KR Price Issuer {n}",
            "price_top20_watch_rank":pos,
            "price_strength_25":price if pos==1 else 20.0,
            "verified_leader_state":None,"formal_leader_score_100":None,"revenue_yoy":None,"industry_code":None,
        })
    payload={
        "schema":SCHEMA,"market":"KR","market_session":day,
        "source_watch_run_id":"watch-"+day,"official_krx_observed":20,"current_dart_directory_matched":0,"financial_factors_observed":0,"industry_factors_observed":0,"flow_factors_observed":0,
        "source_decision_at_utc":"2026-10-13T10:00:00+00:00",
        "built_at_utc":built.isoformat(),
        "research_only":True,"official_leaders":0,
        "full_market_composite_rank_available":False,
        "securities":rows,
    }
    payload["content_sha256"]=sha256(canonical(payload)).hexdigest()
    dest=tmp_path/(day+"_"+str(price)+"_"+str(built.minute)+".json")
    dest.write_bytes(canonical(payload)+b"\n")
    return dest


def test_state_history_two_source_days_retains_watch_and_no_synthetic_exit(tmp_path):
    root=tmp_path/"research"
    root.mkdir(mode=0o700)
    db=root/bridge.LEDGER_NAME
    old=_source(root)
    a=bridge.record_official_watch_history(old,db,clock=NOW)
    assert a["recorded_watch_count"]==20
    assert a["state_counts"]["CONFIRMED"]==0
    assert a["state_history_events"]==0
    assert a["orders_enabled"] is False
    assert bridge.record_official_watch_history(old,db,clock=NOW)==a
    newer=_source(root,day="2026-10-13",newest=True)
    b=bridge.record_official_watch_history(newer,db,clock=NOW)
    assert b["recorded_watch_count"]==20
    ledger=StateHistory(db)
    try:
        assert [x["state"] for x in ledger.history("KR","KR_PRICE_OBSERVED:000002")]==[
            "WATCH","WATCH"]
        assert len(ledger.history("KR","KR_PRICE_OBSERVED:000001"))==1
        assert ledger.history("KR","KR_PRICE_OBSERVED:000021")[-1]["state"]=="WATCH"
        assert ledger.db.execute("SELECT COUNT(*) FROM state_events").fetchone()[0]==0
        assert ledger.db.execute("SELECT COUNT(*) FROM state_history").fetchone()[0]==40
    finally: ledger.close()


def test_later_fundamental_report_same_watch_does_not_mutate_history(tmp_path):
    root=tmp_path/"research"
    root.mkdir(mode=0o700)
    db=root/bridge.LEDGER_NAME
    old=_source(root)
    bridge.record_official_watch_history(old,db,clock=NOW)
    republished=_source(root,built=NOW+timedelta(minutes=10))
    bridge.record_official_watch_history(republished,db,clock=NOW+timedelta(minutes=10))
    ledger=StateHistory(db)
    try:
        assert len(ledger.history("KR","KR_PRICE_OBSERVED:000001"))==1
    finally: ledger.close()
    tampered=_source(root,price=18.5)
    with pytest.raises(ValueError,match="mutation"):
        bridge.record_official_watch_history(tampered,db,clock=NOW)


def test_cannot_promote_price_only_or_use_existing_foreign_ledger(tmp_path):
    root=tmp_path/"research"
    root.mkdir(mode=0o700)
    path=_source(root)
    source=json.loads(path.read_bytes())
    source["official_leaders"]=1
    source.pop("content_sha256")
    source["content_sha256"]=sha256(canonical(source)).hexdigest()
    path.write_bytes(canonical(source)+b"\n")
    with pytest.raises(ValueError,match="SOURCE_SHA_INVALID"):
        bridge.record_official_watch_history(path,root/bridge.LEDGER_NAME,clock=NOW)
    good=_source(root,price=22)
    with pytest.raises(ValueError,match="LEDGER_UNSAFE"):
        bridge.record_official_watch_history(good,root/"state_history.sqlite",clock=NOW)
    with pytest.raises(ValueError,match="AWARE_CLOCK"):
        bridge.record_official_watch_history(good,root/bridge.LEDGER_NAME,
                                            clock=datetime(2026,10,14))


def test_existing_marketwide_publisher_opt_in_stage4_watch_sqlite(
        tmp_path,monkeypatch,capsys):
    from scripts import publish_official_marketwide_coverage as publisher
    root=tmp_path/"output"
    root.mkdir(mode=0o700)
    cohort=_source(root,built=datetime.now(timezone.utc)-timedelta(minutes=2))
    source=json.loads(cohort.read_bytes())
    monkeypatch.setattr(publisher,"ROOT",tmp_path)
    monkeypatch.setattr(publisher,"refresh_saved_marketwide_flow",
                        lambda *_a,**_kw:source)
    ledger=root/bridge.LEDGER_NAME
    result=publisher.main([
        "--verified-marketwide-report",str(cohort),
        "--kiwoom-flow-folder",str(root),
        "--watch-state-ledger",str(ledger),
        "--out",str(root/"report")])
    assert result==0
    published=json.loads(capsys.readouterr().out)
    assert published["watch_state"]=={
        "watch":20,"selected":0,"orders_enabled":False}
    assert ledger.stat().st_mode & 0o777 == 0o600
    a=StateHistory(ledger)
    try:
        assert a.db.execute("SELECT COUNT(*) FROM state_history").fetchone()[0]==20
        assert a.db.execute("SELECT COUNT(*) FROM state_events").fetchone()[0]==0
    finally:a.close()
