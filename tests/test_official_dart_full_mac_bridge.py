"""Mac internal 0600 bridge for actual SSD first DART receipt.

Synthetic transport only; the original SSD files are never rewritten.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile
import pytest

from eraleader.official_api_capture import capture_official_api
from eraleader.official_dart_daily import verify_dart_day
from eraleader.official_dart_full_mac_bridge import (
    mirror_first_page, complete_day_from_ssd
)

STAMP=datetime(2026,10,13,11,tzinfo=timezone.utc)
CREDS={"ERALEADER_DART_API_KEY":"B"*40}
DAY="2026-10-13"

def _records(first:int,last:int):
    return [{"rcept_dt":"20261013","rcept_no":f"20261013{i:06d}",
             "corp_code":"00000001"} for i in range(first,last+1)]

def _payload(page,total=201):
    start=1+100*(page-1)
    last=min(total,page*100)
    rows=_records(start,last)
    return {"status":"000","total_count":str(total),
            "total_page":str((total+99)//100),
            "page_no":str(page),"page_count":"100","list":rows}

@pytest.fixture
def prepared(tmp_path):
    source_root=Path("/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output")
    if source_root.stat().st_dev == tmp_path.stat().st_dev:
        pytest.skip("Mac internal and SSD test filesystems must differ")
    with tempfile.TemporaryDirectory(prefix="eraleader-dart-bridge-test-",dir=source_root) as temp:
        external=Path(temp)
        original=capture_official_api(
            "dart-disclosures",external,day=DAY,creds=CREDS,
            fetch=lambda url,headers:json.dumps(_payload(1)).encode(),
            clock=lambda:STAMP)
        folder=external/original["capture_id"]
        files={f.name:sha256(f.read_bytes()).hexdigest() for f in folder.iterdir()}
        mac=tmp_path/"mac-dart";mac.mkdir(mode=0o700)
        yield folder,original["first_receipt_sha256"],mac,files
        assert {f.name:sha256(f.read_bytes()).hexdigest() for f in folder.iterdir()}==files

def fetch_page(url,headers):
    from urllib.parse import urlparse,parse_qs
    value=int(parse_qs(urlparse(url).query)["page_no"][0])
    return json.dumps(_payload(value)).encode()

def test_mirror_strict_file_modes_and_full_dart_original_verified(prepared):
    folder,pin,mac,files=prepared
    result=complete_day_from_ssd(folder,pin,private_root=mac,
        credential_path=None,fetch=fetch_page,
        clock=lambda:STAMP,max_pages=4)
    assert result["status"]=="DART_COMPLETE_RETRIEVED_DAY_RESEARCH_ONLY"
    assert result["total_rows"]==201 and result["pages"]==3
    assert result["captured_new_pages"]==2 and result["pit_certified"] is False
    copied=mac/folder.name
    assert copied.is_dir()
    assert (copied/"first_receipt.json").stat().st_mode & 0o777 == 0o600
    assert sha256((copied/"first_receipt.json").read_bytes()).hexdigest()==pin
    verified=verify_dart_day(mac/result["capture_id"],result["manifest_sha256"],
                             first_folder=copied,first_sha=pin,decision_at=STAMP)
    assert verified["total_rows"]==201 and len(verified["rows"])==201
    before=[p.name for p in mac.glob("dart_full_*")]
    again=complete_day_from_ssd(folder,pin,private_root=mac,
                                fetch=lambda *_:(_ for _ in ()).throw(AssertionError("quota")),
                                clock=lambda:STAMP)
    assert again["status"]=="DART_COMPLETE_REUSED_VERIFIED"
    assert again["captured_new_pages"]==0
    assert [p.name for p in mac.glob("dart_full_*")]==before

def test_bad_source_sha_fails_before_creating_mirror(prepared):
    folder,pin,mac,_=prepared
    with pytest.raises(ValueError):
        mirror_first_page(folder,"0"*64,mac,STAMP)
    assert list(mac.iterdir())==[]

def test_missing_page_limit_refuses_without_full_result(prepared):
    folder,pin,mac,_=prepared
    with pytest.raises(ValueError,match="more pages"):
        complete_day_from_ssd(folder,pin,private_root=mac,
                               fetch=lambda *_: (_ for _ in ()).throw(AssertionError("no HTTP")),
                               clock=lambda:STAMP,max_pages=2)
    assert not list(mac.glob("dart_full_*"))

def test_modified_first_mirror_cannot_be_reused(prepared):
    folder,pin,mac,_=prepared
    copied=mirror_first_page(folder,pin,mac,STAMP)
    (copied/"raw_response.json").write_bytes(b"tampered")
    with pytest.raises(ValueError,match="differs"):
        mirror_first_page(folder,pin,mac,STAMP)

def test_changed_pagination_total_does_not_publish(prepared):
    folder,pin,mac,_=prepared
    def changing(url,headers):
        return json.dumps(_payload(2,total=202)).encode()
    with pytest.raises(ValueError):
        complete_day_from_ssd(folder,pin,private_root=mac,
                               fetch=changing,clock=lambda:STAMP,max_pages=4)
    assert not list(mac.glob("dart_full_*"))


def test_full_dart_verified_can_clear_only_dart_blocker(prepared,tmp_path):
    from eraleader.official_three_provider_session_gate import verify_live_captures
    from test_official_three_provider_session_gate import capture_triplet
    from test_kiwoom_live_research_panel import sample_flow
    folder,pin,mac,_=prepared
    full=complete_day_from_ssd(folder,pin,private_root=mac,
                               fetch=fetch_page,clock=lambda:STAMP)
    originals=capture_triplet(tmp_path)
    result=verify_live_captures(
        krx_kospi=originals["krx-kospi"],
        krx_kosdaq=originals["krx-kosdaq"],
        dart_disclosures=(folder,pin),
        dart_complete=(mac/full["capture_id"],full["manifest_sha256"]),
        market_day=DAY,security_id="005930",
        flow=sample_flow(),decision_at=STAMP)
    assert result["flags"]["dart_full_listing_sha_verified"] is True
    assert result["flags"]["dart_first_page_complete_for_day"] is False
    assert result["flags"]["dart_day_coverage_verified"] is True
    assert result["dart_complete_daily_proof"]["total_count"]==201
    assert result["readiness"]=="SAME_DAY_RESEARCH_OBSERVABLE_NOT_CERTIFIED"
    assert result["official_leaders"]==0 and result["orders_enabled"] is False
    assert result["investment_leader_score_available"] is False
    with pytest.raises(ValueError):
        verify_live_captures(
            krx_kospi=originals["krx-kospi"],
            krx_kosdaq=originals["krx-kosdaq"],
            dart_disclosures=(folder,pin),
            dart_complete=(mac/full["capture_id"],"0"*64),
            market_day=DAY,security_id="005930",
            flow=sample_flow(),decision_at=STAMP)

def test_full_dart_without_verified_receipt_cannot_clear_blocker():
    from test_official_three_provider_session_gate import originals,calc
    candidates=originals(dart_all=False)
    no_full=calc(candidates)
    assert "DART_DAY_NOT_COMPLETE_OR_PROVIDER_NO_DATA" in no_full["blockers"]


def test_caller_cannot_inject_full_dart_without_page_sha_verification():
    from test_official_three_provider_session_gate import originals
    from eraleader.official_three_provider_session_gate import evaluate
    from test_kiwoom_live_research_panel import sample_flow
    synthetic={
        "market_day":"2026-10-13","total_rows":201,"total_pages":3,
        "manifest_sha256":"a"*64,"last_received_at_utc":STAMP.isoformat(),
        "rows":[{} for _ in range(201)],
        "issuer_class_pit_verified":False,"financial_pit_verified":False,
    }
    with pytest.raises(ValueError,match="Unverified full DART"):
        evaluate(requested_day=DAY,security_id="005930",
                 originals=originals(dart_all=False),flow=sample_flow(),
                 decision_at=STAMP,complete_dart=synthetic)
