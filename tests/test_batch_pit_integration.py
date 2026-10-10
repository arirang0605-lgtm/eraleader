"""Opt-in offline PIT research batch integration; all inputs are synthetic."""
import json
from pathlib import Path
import pytest
from eraleader.cli import main
from eraleader.offline_pit import OfflineLedger
from test_batch import fixture_bars

KR="2024-09-01T17:00:00+09:00"
US="2024-08-30T17:00:00-04:00"

@pytest.fixture
def src(tmp_path,monkeypatch):
    db=OfflineLedger(tmp_path/"offline.sqlite")
    try:
        db.import_file(Path(__file__).parent/"fixtures/offline_synthetic.json")
        db.import_rows("membership",[{"security_id":"SYN-US","ticker":"SYN-US",
            "industry_id":"TECH","market":"US","valid_from":"2024-01-01",
            "valid_to":None,"known_at":"2024-01-02T10:00:00-05:00",
            "source_id":"SYNTHETIC-US","revision":1}],"synthetic_fixture")
    finally:db.close()
    bars=fixture_bars()
    def reader(market,asof,*,days,legacy_root,tickers):
        frame=bars[bars.session.dt.date<=asof].copy()
        return frame,{"source":"SYNTHETIC","price_only":True,
            "historic_membership_verified":False,"corporate_actions_verified":False,
            "financial_pit_verified":False}
    monkeypatch.setattr("eraleader.cli.read_market_bars",reader)
    return tmp_path

def base(root):
    return ["batch","--kr-as-of","2024-09-01","--us-as-of","2024-08-30",
            "--out",str(root),"--top","2"]

def optin(root):
    return base(root)+["--integrate-pit-research",
                       "--kr-decision-at",KR,"--us-decision-at",US]

def test_full_optin_offline_batch_two_markets_and_idempotence(src,capsys):
    main(optin(src))
    result=json.loads(capsys.readouterr().out)
    assert result["integrated_research_markets"]==2
    assert result["reports_created"]==6
    manifest=json.loads((src/"batch_manifest.json").read_text())
    assert manifest["explicit_offline_pit_research"] is True
    assert manifest["official_leaders_confirmed"]==0
    assert manifest["messages_sent"]==0 and manifest["external_api_calls"]==0
    for market in manifest["markets"]:
        pit=market["pit_research"]
        assert pit["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
        assert pit["pit_certified"] is False and pit["official_leaders"]==0
        assert Path(pit["research_dashboard"]).is_file()
    main(optin(src))
    capsys.readouterr()
    latest=json.loads((src/"batch_manifest.json").read_text())
    assert all(x["pit_research"]["new_watch_research_signals"]==0
               for x in latest["markets"])

def test_default_batch_never_loads_offline_financials(src,capsys):
    main(base(src))
    report=json.loads(capsys.readouterr().out)
    assert report["integrated_research_markets"]==0
    data=json.loads((src/"batch_manifest.json").read_text())
    assert data["explicit_offline_pit_research"] is False
    assert all(x["pit_research"] is None for x in data["markets"])
    assert not (src/"prospective.sqlite").exists()

@pytest.mark.parametrize("extra",[
    ["--kr-decision-at",KR],
    ["--integrate-pit-research","--kr-decision-at",KR],
    ["--integrate-pit-research","--kr-decision-at",KR,
     "--us-decision-at","2024-09-01T17:00:00+09:00"],
    ["--integrate-pit-research","--kr-decision-at","2024-09-01T17:00:00",
     "--us-decision-at",US],
])
def test_invalid_or_missing_decision_time_no_price_side_effect(src,extra):
    with pytest.raises(SystemExit) as failure:
        main(base(src)+extra)
    assert failure.value.code==2
    assert not (src/"state.sqlite").exists()

def test_missing_ledger_refuses_before_any_price_run(tmp_path,monkeypatch):
    monkeypatch.setattr("eraleader.cli.read_market_bars",
                        lambda *a,**k: pytest.fail("price read must not execute"))
    with pytest.raises(SystemExit) as failure:
        main(optin(tmp_path))
    assert failure.value.code==2
    assert not (tmp_path/"state.sqlite").exists()

def test_pit_batch_requires_then_known_us_membership(src):
    db=OfflineLedger(src/"offline.sqlite")
    try:
        db.import_rows("membership",[{"security_id":"SYN-US","ticker":"SYN-US",
            "industry_id":"TECH","market":"US","valid_from":"2024-01-01",
            "valid_to":"2024-08-01","known_at":"2024-08-02T10:00:00-04:00",
            "source_id":"SYNTHETIC-US","revision":2}],"synthetic_fixture")
    finally:db.close()
    with pytest.raises(SystemExit) as failure:
        main(optin(src))
    assert failure.value.code==2
    assert not (src/"state.sqlite").exists()
