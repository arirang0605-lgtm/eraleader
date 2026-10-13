"""Actual EraLeader CLI must ask SharedBrokerAPI status, never read API keys."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys

import pytest
from scripts import capture_kiwoom_investor_flow as cli

SHARED="/Volumes/T5DATA/SharedBrokerAPI/src"
if SHARED not in sys.path:
    sys.path.insert(0,SHARED)
import shared_broker_api.client as api


class FakeGateway:
    seen=[]
    configured={"demo": False, "real": False}
    orders=False
    def __init__(self, project):
        assert project == "eraleader"
    def status(self):
        self.seen.append("status")
        return {"configured":self.configured.copy(),
                "orders_enabled":self.orders,
                "project":"eraleader"}


def test_check_config_reads_no_secrets_and_contacts_local_status(monkeypatch,capsys):
    FakeGateway.seen=[]
    monkeypatch.setattr(api, "ReadOnlyClient", FakeGateway)
    for mode in ("demo","real"):
        code=cli.main(["--check-config","--profile",mode])
        parsed=json.loads(capsys.readouterr().out)
        assert code==0
        assert parsed["gateway_reachable"] is True
        assert parsed["credentials_configured"] is False
        assert parsed["network_calls"]==0 and parsed["orders_enabled"] is False
    assert FakeGateway.seen==["status","status"]


def test_configured_broker_status_proceeds_without_accessing_key_file(monkeypatch,tmp_path,capsys):
    FakeGateway.seen=[]
    FakeGateway.configured={"demo":True,"real":False}
    monkeypatch.setattr(api, "ReadOnlyClient", FakeGateway)
    monkeypatch.setattr(api, "eraleader_compatible_post",
                        lambda _client,_mode: lambda *_args: ({},{}))
    sentinel={}
    def fake_capture(**kw):
        sentinel.update(kw)
        return {"status":"TEST_ONLY","companies":1}
    monkeypatch.setattr(cli,"capture",fake_capture)
    out=tmp_path/"new_run"
    assert cli.main(["--profile","demo","--codes","005930",
                     "--day","20261008","--out",str(out)])==0
    assert sentinel["codes"] == ["005930"]
    assert sentinel["environment_mode"]=="demo"
    assert sentinel["token"]=="INTERNAL_LOCAL_GATEWAY_NO_PROVIDER_TOKEN"
    assert "appkey" not in sentinel and "secretkey" not in sentinel
    assert FakeGateway.seen==["status"]
    response=capsys.readouterr().out
    assert "TEST_ONLY" in response


def test_fail_closed_when_broker_down_or_claims_orders(monkeypatch,tmp_path,capsys):
    FakeGateway.configured={"demo":True,"real":True}
    FakeGateway.orders=True
    monkeypatch.setattr(api, "ReadOnlyClient", FakeGateway)
    failed=cli.main(["--profile","real","--codes","005930",
                     "--day","20261008","--out",str(tmp_path/"new")])
    assert failed==2
    assert not (tmp_path/"new").exists()
    assert "KIWOOM_READ_ONLY_BLOCKED" in capsys.readouterr().err
    FakeGateway.orders=False
    class Offline:
        def __init__(self, _project): pass
        def status(self): raise ConnectionError("socket offline")
    monkeypatch.setattr(api, "ReadOnlyClient",Offline)
    assert cli.main(["--check-config","--profile","demo"])==0
    data=json.loads(capsys.readouterr().out)
    assert data["gateway_reachable"] is False and data["credentials_configured"] is False
