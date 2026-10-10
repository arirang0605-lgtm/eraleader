from datetime import date
from argparse import Namespace
import json
import pandas as pd
import pytest

from eraleader.universe_audit import audit_observed_universe
from eraleader.cli import execute_universe_audit

def _bars():
    return pd.DataFrame([
       {"security_id":"A","session":"2024-09-02","close":100,"is_suspended":False},
       {"security_id":"B","session":"2024-09-02","close":50,"is_suspended":False},
       {"security_id":"A","session":"2024-09-03","close":102,"is_suspended":False},
       {"security_id":"C","session":"2024-09-03","close":70,"is_suspended":True},
    ])

def test_observation_change_does_not_claim_delisting():
    audit=audit_observed_universe(_bars(),date(2024,9,3))
    assert audit["prior_observation"]=="2024-09-02"
    assert audit["last_observation"]=="2024-09-03"
    assert audit["appeared"]==["C"]
    assert audit["disappeared"]==["B"]
    assert audit["halted_or_no_trade"]==["C"]
    assert audit["historic_membership_certified"] is False
    assert audit["delisting_events_certified"] is False
    assert "NOT proof of delisting" in audit["warnings"][0]

def test_audit_rejects_future_and_duplicates():
    a=_bars()
    with pytest.raises(ValueError,match="Future"):
        audit_observed_universe(a,date(2024,9,2))
    with pytest.raises(ValueError,match="Duplicate"):
        audit_observed_universe(pd.concat([a,a.iloc[:1]]),date(2024,9,3))

def test_audit_requires_two_market_sessions_and_fields():
    with pytest.raises(ValueError,match="Missing"):
        audit_observed_universe(pd.DataFrame({"security_id":["A"]}),date(2024,9,3))
    with pytest.raises(ValueError,match="two"):
        audit_observed_universe(_bars().iloc[:2],date(2024,9,2))

def test_cli_audit_serialization_keeps_certification_false(tmp_path,monkeypatch):
    sample=_bars()
    sample["session"]=pd.to_datetime(sample["session"])
    monkeypatch.setattr("eraleader.cli.read_market_bars",lambda *args,**kwargs:(
        sample,{"source":"UNIT_FIXTURE","financial_pit_verified":False}))
    out=execute_universe_audit(Namespace(as_of="2024-09-03",days=30,
                       legacy=str(tmp_path),out=str(tmp_path)))
    payload=json.loads((tmp_path/"universe_observation_audit.json").read_text())
    assert payload["disappeared"]==["B"]
    assert out["historic_membership_certified"] is False
    assert out["halted_count"]==1
