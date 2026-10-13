"""Bounded multi-company first-received DART CFS research collector tests."""
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import json
import pytest

from eraleader import official_dart_multi_company as multi

NOW=datetime(2026,10,13,10,tzinfo=timezone.utc)


def fake_universe(*_a,**_k):
    return ({
        "000660":{"name":"Company A","venue":"KOSPI"},
        "005930":{"name":"Company B","venue":"KOSPI"},
    },(Path("/secure/dartdir"),"d"*64),{
        "market_session":"2026-10-08",
        "krx_rows":2765,
        "dart_unique_matches":2651,
        "current_issuer_class_pit_certified":False,
    })


@pytest.fixture
def corpus(tmp_path,monkeypatch):
    root=tmp_path/"private"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(multi,"source_eligible_universe",fake_universe)
    return root


def test_annual_two_company_fetch_calls_legacy_cfs_once_each(corpus,monkeypatch):
    calls=[]
    def capture(root,*,stock_code,year,**_):
        calls.append((stock_code,year))
        folder=f"dart_fin_{len(calls):032x}"
        (root/folder).mkdir()
        (root/folder/"first_receipt.json").write_text("{}")
        return {"capture_id":folder,"first_receipt_sha256":f"{len(calls):064x}"}
    def verify(folder,pin,**_):
        return {
            "stock_code":"005930","status":"FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY",
            "year":2025,
            "first_local_received_at_utc":"2026-10-13T10:00:00Z",
            "metrics":{"revenue":1,"operating_income":2,"net_income":3},
        }
    monkeypatch.setattr(multi,"capture_dart_financial",capture)
    monkeypatch.setattr(multi,"verify_dart_financial",verify)
    payload=multi.collect_multi_company_cfs(
        evidence_file=corpus/"evidence.json",private_root=corpus,
        codes=("000660","005930"),years=(2024,2025),
        credentials={},delay_seconds=0,clock=lambda:NOW)
    assert calls==[("000660",2024),("000660",2025),("005930",2024),("005930",2025)]
    assert payload["companies_requested"]==2
    assert payload["companies_with_complete_annual_cfs"]==2
    assert payload["real_investment_leader_ranked"] is False
    assert payload["all_company_historic_pit_certified"] is False


def test_only_existing_yields_explicit_not_captured_instead_of_fake_zero(corpus,monkeypatch):
    monkeypatch.setattr(multi,"capture_dart_financial",
                        lambda *_a,**_k:pytest.fail("offline must never fetch"))
    out=multi.collect_multi_company_cfs(
        evidence_file=corpus/"unneeded.json",private_root=corpus,
        codes=("000660","005930"),credentials={},delay_seconds=0,
        existing_only=True,clock=lambda:NOW)
    assert out["companies_with_complete_annual_cfs"]==0
    assert all(row["status"]=="NOT_CAPTURED"
               for company in out["companies"] for row in company["annual_reports"])


@pytest.mark.parametrize("codes,years",[
    (("005930","005930"),(2024,2025)),
    (("999999",),(2024,2025)),
    (tuple(f"{n:06}" for n in range(13)),(2024,2025)),
    (("005930",),(2025,)),
    (("005930",),(2025,2024)),
    (("005930",),(2023,2025)),
])
def test_missing_fy_or_unverified_stock_rejected(corpus,monkeypatch,codes,years):
    with pytest.raises(ValueError):
        multi.collect_multi_company_cfs(
            evidence_file=corpus/"nothing.json",private_root=corpus,
            codes=codes,years=years,credentials={},clock=lambda:NOW)


def test_conflicting_same_fy_first_receipts_never_auto_choose(corpus,monkeypatch):
    for i in range(2):
        folder=corpus/f"dart_fin_{i:032x}"
        folder.mkdir()
        (folder/"first_receipt.json").write_text(
            json.dumps({"stock_code":"005930","bsns_year":2025,
                        "reprt_code":"11011","statement":"CFS"}))
    monkeypatch.setattr(multi,"verify_dart_financial",
                        lambda *_a,**_k:pytest.fail("conflict must stop first"))
    with pytest.raises(ValueError,match="multiple original versions"):
        multi.collect_multi_company_cfs(
            evidence_file=corpus/"nothing.json",private_root=corpus,
            codes=("005930",),credentials={},clock=lambda:NOW)
