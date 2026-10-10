import json
from argparse import Namespace
from datetime import date
from pathlib import Path
import pandas as pd
import pytest

from eraleader.data import validate_bars,read_market_bars,LEGACY_DEFAULT
from eraleader.discovery import score_price_observations,detect_watch_changes,run_id_for
from eraleader.backtest import delayed_momentum_baseline
from eraleader.delivery import render_dashboard,make_report
from eraleader.cli import execute_run,execute_report,execute_alerts


def sample_bars(n=310):
    records=[]
    for code,multiple in [("AAA",1.03),("BBB",1.01),("CCC",0.995)]:
        prices=[100.0*multiple**(i/10) for i in range(n)]
        for i,(day,price) in enumerate(zip(pd.bdate_range("2024-01-01",periods=n),prices)):
            records.append(dict(security_id=code,session=day,name=code,venue="KOSPI",
              open=price,high=price*1.01,low=price*.99,close=price,volume=100,
              turnover=price*100,market_cap=1e10))
    return pd.DataFrame(records)

def test_validate_future_price_and_duplicate():
    bars=sample_bars(n=40)
    dt=bars.session.max().date()
    assert len(validate_bars(bars,dt))==len(bars)
    with pytest.raises(ValueError,match="Lookahead"):
        validate_bars(bars,dt.replace(year=dt.year-1))
    with pytest.raises(ValueError,match="Duplicate"):
        validate_bars(pd.concat([bars,bars.iloc[:1]]),dt)

def test_invalid_ohlcv_rejected():
    bars=sample_bars(n=30)
    bars.loc[0,"high"]=-9
    with pytest.raises(ValueError,match="Invalid"):
        validate_bars(bars,bars.session.max().date())

def test_price_only_never_claims_leader():
    bars=sample_bars()
    cutoff=str(bars.session.max().date())
    rank=score_price_observations(bars,"KR",cutoff,limit=3)
    assert rank["shown"]==3
    assert all(row["state"]=="WATCH" for row in rank["rows"])
    assert all(row["total_score_100"] is None for row in rank["rows"])
    assert len(rank["rows"])==3 and rank["rows"][0]["rank"]==1
    assert score_price_observations(bars,"KR",cutoff,limit=3)==rank
    with pytest.raises(ValueError,match="LOOKAHEAD"):
        score_price_observations(bars,"KR","2020-01-01")

def test_research_only_delayed_baseline():
    bars=sample_bars(n=310)
    out=delayed_momentum_baseline(bars,lookback=15,top_n=1,rebalance=5,weekly=True)
    assert out["observations"]>10
    assert out["status"]=="RESEARCH_ONLY_NOT_PIT_CERTIFIED"
    assert out["costs_included"] is False
    # no backtest future label is ever included in score_price_observations output
    snap=score_price_observations(bars,"KR",str(bars.session.max().date()))
    assert "future_leader_label" not in json.dumps(snap)

def test_dashboard_and_report_escape(tmp_path):
    snap=score_price_observations(sample_bars(),"KR","2025-03-07")
    snap["data_source"]="TEST_LOCAL"
    snap["rows"][0]["name"]='<script>alert("x")</script>'
    html=render_dashboard(snap)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    file=make_report(snap,"weekly",tmp_path/"report.md")
    assert file.is_file() and "재무·산업" in file.read_text()
    with pytest.raises(ValueError):make_report(snap,"yearly",tmp_path/"bad.md")

def test_complete_offline_run_and_duplicate_alerts(tmp_path,monkeypatch):
    bars=sample_bars()
    def fake_loader(market,asof,days,legacy_root,tickers):
        return bars,{"source":"UNIT_FIXTURE","price_only":True}
    monkeypatch.setattr("eraleader.cli.read_market_bars",fake_loader)
    as_of=str(bars.session.max().date())
    args=Namespace(market="KR",as_of=as_of,days=550,legacy=str(tmp_path),
                   tickers=None,top=3,out=str(tmp_path/"out"))
    first=execute_run(args)
    second=execute_run(args)
    assert first["run_id"]==second["run_id"]
    assert Path(first["dashboard"]).is_file()
    report=execute_report(Namespace(market="KR",period="daily",out=args.out))
    assert Path(report["path"]).is_file()
    alerts=execute_alerts(Namespace(out=args.out))
    assert alerts["count"]==3
    assert execute_alerts(Namespace(out=args.out))["count"]==0

@pytest.mark.skipif(not LEGACY_DEFAULT.exists(),reason="SSD legacy data not mounted")
def test_kr_legacy_sample_18_sessions():
    try:bars,quality=read_market_bars("KR",date(2025,1,31),days=30,tickers=["005930"])
    except (FileNotFoundError,ImportError) as exc:pytest.skip(str(exc))
    assert len(bars)==18
    assert quality["financial_pit_verified"] is False
    assert bars.session.max().date()==date(2025,1,31)
