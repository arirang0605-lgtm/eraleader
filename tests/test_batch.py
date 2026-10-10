from datetime import date
import json
import pandas as pd
from eraleader.cli import main

def fixture_bars():
    rows=[]
    for sec,mult in (("SYN1",1.02),("SYN2",1.03)):
        for i,dt in enumerate(pd.bdate_range("2024-01-02",periods=320)):
            close=100*mult**(i/15)
            rows.append({"security_id":sec,"session":dt,"name":sec,
                         "venue":"LOCAL_FIXTURE","close":close,"volume":100})
    return pd.DataFrame(rows)

def test_kr_us_full_offline_batch_without_api_calls(tmp_path,monkeypatch,capsys):
    bars=fixture_bars()
    loader_calls=[]
    def loader(market,asof,*,days,legacy_root,tickers):
        loader_calls.append(market)
        return bars,{"source":"SYNTHETIC_TEST","price_only":True,
                     "financial_pit_verified":False,"historic_membership_verified":False,
                     "corporate_actions_verified":False}
    monkeypatch.setattr("eraleader.cli.read_market_bars",loader)
    args=["batch","--kr-as-of","2025-03-31","--us-as-of","2025-03-31",
          "--out",str(tmp_path),"--top","2"]
    main(args)
    result=json.loads(capsys.readouterr().out)
    assert result["market_count"]==2
    assert result["reports_created"]==6
    assert sorted(loader_calls)==["KR","US"]
    manifest=json.loads((tmp_path/"batch_manifest.json").read_text())
    assert manifest["dry_run_only"]
    assert manifest["external_api_calls"]==0
    assert manifest["messages_sent"]==0
    assert len(manifest["markets"])==2
    for market in ("kr","us"):
        assert (tmp_path/"site"/f"{market}.html").is_file()
        assert (tmp_path/f"{market}_latest.json").is_file()
    first=result["alerts_dry_run"]
    assert first==4
    main(args)
    second=json.loads(capsys.readouterr().out)
    assert second["alerts_dry_run"]==0
