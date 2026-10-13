"""DART financial first receipts -> append-only, as-of vintage ledger tests."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import json
import os
import sqlite3
import subprocess
import sys

import pytest

from test_official_dart_financials import zipped,statement,CREDS,NOW
from eraleader.official_dart_corp_directory import capture_dart_corp_directory
from eraleader.official_dart_financials import capture_dart_financial
from eraleader.official_dart_vintage_registry import DartCFSVintageRegistry

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def fx(tmp_path):
    root=tmp_path/"private_originals"
    root.mkdir(mode=0o700);root.chmod(0o700)
    directory=capture_dart_corp_directory(
        root,creds=CREDS,fetch=lambda *_:zipped(),clock=lambda:NOW)
    pin=(root/directory["capture_id"],directory["first_receipt_sha256"])
    return {"root":root,"directory":pin,"db":tmp_path/"vintage.sqlite"}


def capture(fx, year=2025, amount="12,000", *,
            nonce=0, accession=None):
    def fetch(*args):
        data=statement(year,amount)
        if accession:
            for row in data["list"]:
                row["rcept_no"]=accession
        return json.dumps(data).encode()
    new=capture_dart_financial(
        fx["root"],stock_code="005930",directory=fx["directory"],
        year=year,report="11011",statement="CFS",creds=CREDS,
        fetch=fetch,clock=lambda:NOW+timedelta(seconds=nonce+1))
    return fx["root"]/new["capture_id"],new["first_receipt_sha256"]


def reg(fx, *original, seconds=30):
    with DartCFSVintageRegistry(fx["db"]) as db:
        return db.register_verified(*original,directory=fx["directory"],
                                    clock=NOW+timedelta(seconds=seconds))


def asof(fx, seconds=60,year=2025):
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        return db.review_as_of(
            stock_code="005930",corp_code="00126380",fiscal_year=year,
            decision_at=(NOW+timedelta(seconds=seconds)).isoformat())


def test_real_verified_fixture_register_then_asof_never_backdates(fx):
    original=capture(fx)
    first=reg(fx,*original)
    assert first["new_event"] is True
    assert first["official_leaders"] == 0
    assert first["simulated"] is True
    before=asof(fx,seconds=20)
    assert before["registered_vintages_available"]==0
    assert before["research_metrics"] is None
    now=asof(fx)
    assert now["registered_vintages_available"] == 1
    assert now["status"]=="SINGLE_LOCAL_VINTAGE_HISTORIC_PUBLICATION_UNKNOWN"
    assert now["research_metrics"]["revenue"]["value"]==12000
    assert now["historical_first_publication_certified"] is False
    assert now["revision_history_complete"] is False
    assert now["prospective_early_discovery_certified"] is False


def test_identical_replay_keeps_first_registration_and_hash_chain(fx):
    old=capture(fx)
    added=reg(fx,*old,seconds=30)
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        first=db.checksum()
    replay=reg(fx,*old,seconds=300)
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        after=db.checksum()
    assert replay["new_event"] is False
    assert replay["first_registered_at_utc"]==added["first_registered_at_utc"]
    assert first==after and after["records"]==1
    assert first["tail_chain_sha256"]!="0"*64


def test_separate_years_can_be_reviewed_without_inventing_original_publication(fx):
    for ix,fy in enumerate((2023,2024,2025)):
        original=capture(fx,year=fy,nonce=ix)
        reg(fx,*original,seconds=20+ix)
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        checksum=db.checksum()
    assert checksum["records"]==3
    assert all(asof(fx,year=yr)["registered_vintages_available"]==1
               for yr in (2023,2024,2025))
    assert asof(fx,year=2022)["status"]=="NO_PIT_VINTAGE_AS_OF"


def test_same_filing_response_changed_refuses_silent_overwrite(fx):
    prior=capture(fx,amount="12,000",nonce=0)
    altered=capture(fx,amount="13,000",nonce=1)
    reg(fx,*prior,seconds=20)
    assert asof(fx,seconds=25)["research_metrics"]["revenue"]["value"]==12000
    reg(fx,*altered,seconds=30)
    result=asof(fx,seconds=35)
    assert result["status"]=="SAME_ACCESSION_CHANGED_UNVERIFIED"
    assert result["registered_vintages_available"]==2
    assert result["research_metrics"] is None
    assert result["official_leader"] is False
    assert asof(fx,seconds=25)["research_metrics"]["revenue"]["value"]==12000


def test_changed_cfs_accession_requires_revision_reconciliation(fx):
    old=capture(fx,accession="20260109000001")
    corrected=capture(fx,amount="11,000",nonce=1,
                      accession="20260330000001")
    reg(fx,*old,seconds=20)
    reg(fx,*corrected,seconds=40)
    after=asof(fx,seconds=41)
    assert after["registered_vintages_available"]==2
    assert after["status"]=="MULTIPLE_ACCESSIONS_REVISION_RECONCILIATION_REQUIRED"
    assert after["research_metrics"] is None
    assert asof(fx,seconds=25)["registered_vintages_available"]==1


def test_late_received_original_cannot_be_inserted_at_prior_time(fx):
    src=capture(fx,nonce=14)
    with DartCFSVintageRegistry(fx["db"]) as db:
        with pytest.raises(ValueError,match="not locally available"):
            db.register_verified(*src,directory=fx["directory"],
                                 clock=NOW+timedelta(seconds=4))
        assert db.checksum()["records"]==0


def test_out_of_order_clock_cannot_insert_new_original(fx):
    earlier=capture(fx,nonce=0)
    later=capture(fx,year=2024,nonce=1)
    reg(fx,*earlier,seconds=30)
    with pytest.raises(ValueError,match="backdate"):
        reg(fx,*later,seconds=28)
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        assert db.checksum()["records"]==1


def test_source_pin_tamper_and_raw_mutation_fail_without_insert(fx):
    src=capture(fx)
    with pytest.raises(ValueError,match="first receipt"):
        reg(fx,src[0],"f"*64)
    assert asof(fx)["registered_vintages_available"]==0
    raw=src[0]/"raw_response.json"
    raw.write_bytes(raw.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="lineage|tampered|changed"):
        reg(fx,*src)
    assert asof(fx)["registered_vintages_available"]==0


def test_sqlite_triggers_deny_update_and_delete(fx):
    src=capture(fx);reg(fx,*src)
    with sqlite3.connect(fx["db"]) as db:
        with pytest.raises(sqlite3.DatabaseError,match="cannot update"):
            db.execute("UPDATE dart_cfs_vintages SET identity='FORGED'")
        with pytest.raises(sqlite3.DatabaseError,match="cannot delete"):
            db.execute("DELETE FROM dart_cfs_vintages")
    assert asof(fx)["registered_vintages_available"]==1


def test_file_tampering_fails_hash_chain_audit(fx):
    src=capture(fx);reg(fx,*src)
    with sqlite3.connect(fx["db"]) as db:
        db.execute("DROP TRIGGER dart_cfs_no_update")
        db.execute("UPDATE dart_cfs_vintages SET event_payload='{\"fake\":true}'")
        db.commit()
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        with pytest.raises(ValueError,match="corrupted"):
            db.checksum()


def test_read_only_registry_refuses_write_and_does_not_create_file(fx):
    with pytest.raises(ValueError,match="non-existent"):
        DartCFSVintageRegistry(fx["db"],read_only=True)
    assert not fx["db"].exists()
    src=capture(fx);reg(fx,*src)
    with DartCFSVintageRegistry(fx["db"],read_only=True) as db:
        with pytest.raises(ValueError,match="read-only"):
            db.register_verified(*src,directory=fx["directory"])


def test_no_credentials_raw_returned_by_registry(fx):
    src=capture(fx);result=reg(fx,*src)
    assert "ERALEADER_DART_API_KEY" not in json.dumps(result)
    assert "A"*40 not in json.dumps(result)
    assert str(src[0]) not in json.dumps(result)
    assert "raw_response.json" not in json.dumps(asof(fx))
