from datetime import date
import json
import pandas as pd
import pytest
from eraleader.pit_coverage import reconcile_membership_to_prices
from eraleader.offline_pit import OfflineLedger
from eraleader.cli import main

AS_OF=date(2024,9,1)
def make_snapshot():
    return {"market":"KR","trading_day":"2024-09-01",
            "members":{"A":{},"B":{},"D":{}},
            "exit_security_ids":["E"],
            "quality":{"provenances":["synthetic_fixture"],
                       "historic_membership_pit_verified":False}}
def bars():
    return pd.DataFrame([
        {"security_id":"A","session":pd.Timestamp("2024-08-30"),"is_suspended":False},
        {"security_id":"A","session":pd.Timestamp("2024-09-01"),"is_suspended":False},
        {"security_id":"B","session":pd.Timestamp("2024-09-01"),"is_suspended":True},
        {"security_id":"C","session":pd.Timestamp("2024-09-01"),"is_suspended":False},
        {"security_id":"E","session":pd.Timestamp("2024-09-01"),"is_suspended":False},
    ])

def test_membership_price_reconciliation_never_upgrades_certification():
    report=reconcile_membership_to_prices(make_snapshot(), bars(),as_of=AS_OF)
    assert report["matching_count"]==2
    assert report["pit_member_count"]==3
    assert report["observed_price_security_count"]==4
    assert report["member_without_price_count"]==1
    assert report["price_without_member_count"]==2
    assert report["observed_suspended_count"]==1
    assert report["observed_exited_count"]==1
    assert report["members_missing_from_feed_sample"]==["D"]
    assert report["exited_but_observed_sample"]==["E"]
    assert report["member_price_overlap_fraction"]==round(2/3,6)
    assert report["historic_membership_pit_certified"] is False

def test_no_membership_does_not_infer_complete_universe():
    s=make_snapshot()
    s["members"]={}
    report=reconcile_membership_to_prices(s,bars(),as_of=AS_OF)
    assert report["member_price_overlap_fraction"] is None
    assert report["matching_count"]==0
    assert report["historic_membership_pit_certified"] is False

@pytest.mark.parametrize("change,exception", [
    (lambda df: df.assign(session=pd.Timestamp("2024-09-02")), "Future"),
    (lambda df: pd.concat([df,df.iloc[[0]]],ignore_index=True), "Duplicated"),
    (lambda df: df.drop(columns=["is_suspended"]), "Missing bar field"),
])
def test_future_duplicate_or_missing_price_fields_rejected(change,exception):
    with pytest.raises(ValueError,match=exception):
        reconcile_membership_to_prices(make_snapshot(), change(bars()),as_of=AS_OF)

def test_asof_mismatch_or_inconsistent_exited_identity_rejected():
    with pytest.raises(ValueError,match="trading day"):
        reconcile_membership_to_prices(make_snapshot(),bars(),as_of=date(2024,9,2))
    s=make_snapshot()
    s["exit_security_ids"]=["A"]
    with pytest.raises(ValueError,match="known exited"):
        reconcile_membership_to_prices(s,bars(),as_of=AS_OF)

def test_cli_reconciliation_uses_existing_offline_ledger(tmp_path,monkeypatch,capsys):
    original=json.loads((__import__("pathlib").Path(__file__).parent/"fixtures/offline_synthetic.json").read_text())
    ledger=OfflineLedger(tmp_path/"ledger.sqlite")
    try:
        ledger.import_rows("membership",original["records"]["membership"],"synthetic_fixture")
    finally:ledger.close()
    def reader(market,asof,*,days,legacy_root):
        assert market=="KR" and asof==AS_OF
        frame=pd.DataFrame([
            {"security_id":"SYN-A","session":pd.Timestamp("2024-08-30"),"is_suspended":False},
            {"security_id":"SYN-A","session":pd.Timestamp("2024-09-01"),"is_suspended":False},
            {"security_id":"EXTRA","session":pd.Timestamp("2024-09-01"),"is_suspended":False},
        ])
        return frame,{"source":"SYNTHETIC_CACHE"}
    monkeypatch.setattr("eraleader.cli.read_market_bars",reader)
    main(["audit-pit-coverage","--market","KR",
          "--as-of","2024-09-01T17:00:00+09:00",
          "--ledger",str(tmp_path/"ledger.sqlite"),"--out",str(tmp_path)])
    printed=json.loads(capsys.readouterr().out)
    assert printed["matching_count"]==1
    report=json.loads((tmp_path/"pit_coverage_kr.json").read_text())
    assert report["price_feed_source"]=="SYNTHETIC_CACHE"
    assert report["historic_membership_pit_certified"] is False
