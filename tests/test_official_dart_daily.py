"""Offline HTTP mocks only; real first receipts are never rewritten."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import json
import pytest

from eraleader.official_api_capture import capture_official_api
from eraleader.official_dart_daily import (
    capture_dart_day, verify_dart_day, observed_dart_stock_links,
)
from eraleader import official_dart_daily as mod

DAY="2026-10-08"
NOW=datetime(2026,10,12,11,10,tzinfo=timezone.utc)
CREDS={"ERALEADER_DART_API_KEY":"A"*40}

def row(i, *, code="005930",corp="00126380"):
    return {"rcept_dt":"20261008", "rcept_no":f"{i:014d}",
            "stock_code":code,"corp_code":corp}

def page(i, *, total=201, mutate=None):
    rows=[row(j) for j in range((i-1)*100+1,min(i*100,total)+1)]
    if mutate: rows=mutate(rows)
    return {"status":"000","total_count":str(total),
            "page_count":"100","page_no":str(i),
            "total_page":str((total+99)//100),"list":rows}

@pytest.fixture
def roots(tmp_path):
    raw=tmp_path/"raw";raw.mkdir(mode=0o700);raw.chmod(0o700)
    output=tmp_path/"full";output.mkdir(mode=0o700);output.chmod(0o700)
    return raw,output

def first(raw,payload):
    res=capture_official_api("dart-disclosures",raw,day=DAY,creds=CREDS,
                             fetch=lambda _u,_h:json.dumps(payload).encode(),
                             clock=lambda:NOW)
    return raw/res["capture_id"],res["first_receipt_sha256"]

def fetcher(**overrides):
    calls=[]
    def fetch(url,headers):
        assert headers["Accept"] == "application/json"
        assert "crtfc_key" in parse_qs(urlsplit(url).query)
        n=int(parse_qs(urlsplit(url).query)["page_no"][0])
        calls.append(n)
        body=page(n,**overrides)
        return json.dumps(body).encode()
    return fetch,calls

def complete(roots,**kw):
    original,pin=first(roots[0],page(1))
    fetch,calls=fetcher()
    out=capture_dart_day(original,pin,roots[1],creds=CREDS,
                         fetch=fetch,clock=lambda:NOW+timedelta(seconds=1),**kw)
    return original,pin,out,calls

def test_full_day_verified_three_pages_and_no_first_overwrite(roots):
    original,pin,receipt,calls=complete(roots)
    assert calls==[2,3]
    assert receipt["total_rows"]==201 and receipt["pages"]==3
    assert sha256((original/"first_receipt.json").read_bytes()).hexdigest()==pin
    finished=roots[1]/receipt["capture_id"]
    summary=verify_dart_day(finished,receipt["manifest_sha256"],
                            first_folder=original,first_sha=pin,
                            decision_at=NOW+timedelta(seconds=2))
    assert len(summary["rows"])==201
    assert len({x["rcept_no"] for x in summary["rows"]})==201
    assert summary["financial_pit_verified"] is False
    assert summary["issuer_class_pit_verified"] is False


@pytest.mark.parametrize("disturb",[
    "page_number","total","duplicated_receipt","last_short","cross_day","bad_json",
])
def test_inconsistent_dart_pages_fail_closed_no_partial_publish(roots,disturb):
    original,pin=first(roots[0],page(1))
    def fail(url,headers):
        n=int(parse_qs(urlsplit(url).query)["page_no"][0])
        payload=page(n)
        if disturb=="page_number":payload["page_no"]="1"
        if disturb=="total":payload["total_count"]="202"
        if disturb=="duplicated_receipt":payload["list"][0]["rcept_no"]=f"{1:014d}"
        if disturb=="last_short":payload["list"].pop()
        if disturb=="cross_day":payload["list"][0]["rcept_dt"]="20261009"
        if disturb=="bad_json":return b'{"status":"000","status":"000"}'
        return json.dumps(payload).encode()
    with pytest.raises(ValueError):
        capture_dart_day(original,pin,roots[1],creds=CREDS,fetch=fail,
                         clock=lambda:NOW+timedelta(seconds=1))
    assert not list(roots[1].iterdir())


def test_fails_with_wrong_original_first_sha(roots):
    original,pin=first(roots[0],page(1))
    with pytest.raises(ValueError,match="SHA pin"):
        capture_dart_day(original,"0"*64,roots[1],creds=CREDS,
                         fetch=lambda *_:b"{}",clock=lambda:NOW)
    assert not list(roots[1].iterdir())


def test_incomplete_limit_never_starts_network(roots):
    original,pin=first(roots[0],page(1))
    with pytest.raises(ValueError,match="safe cap"):
        capture_dart_day(original,pin,roots[1],creds=CREDS,
                         max_pages=2,fetch=lambda *_:pytest.fail("fetched"))


def test_tampered_original_or_any_page_is_detected(roots):
    original,pin,receipt,_=complete(roots)
    target=roots[1]/receipt["capture_id"]
    page2=target/"page_002.json"
    page2.write_bytes(page2.read_bytes()+b" ")
    with pytest.raises(ValueError,match="page SHA"):
        verify_dart_day(target,receipt["manifest_sha256"])
    page2.write_bytes(page2.read_bytes()[:-1])
    assert verify_dart_day(target,receipt["manifest_sha256"])["total_rows"]==201
    (original/"raw_response.json").write_bytes(b"changed")
    with pytest.raises(ValueError,match="Malformed official capture JSON"):
        verify_dart_day(target,receipt["manifest_sha256"],
                        first_folder=original,first_sha=pin)


def test_future_first_reception_cannot_enter_past(roots):
    original,pin,receipt,_=complete(roots)
    with pytest.raises(ValueError,match="not received by decision"):
        verify_dart_day(roots[1]/receipt["capture_id"],receipt["manifest_sha256"],
                        decision_at=NOW-timedelta(seconds=2))


def test_manifest_first_receipt_changed_or_extra_file_blocks(roots):
    _,_,receipt,_=complete(roots)
    target=roots[1]/receipt["capture_id"]
    with pytest.raises(ValueError,match="manifest SHA"):
        verify_dart_day(target,"0"*64)
    (target/"unexpected.json").write_text("1")
    with pytest.raises(ValueError,match="unaccounted"):
        verify_dart_day(target,receipt["manifest_sha256"])


def test_claimed_complete_from_partial_first_day_is_rejected(roots):
    original,pin=first(roots[0],page(1))
    with pytest.raises(ValueError):
        capture_dart_day(original,pin,roots[1],creds=CREDS,fetch=lambda *_:b'{}')


def test_single_page_zero_disclosures_is_complete_and_empty(roots):
    original,pin=first(roots[0],{"status":"013","message":"no data"})
    result=capture_dart_day(original,pin,roots[1],creds=CREDS,
                             fetch=lambda *_:pytest.fail("network on zero records"),
                             clock=lambda:NOW)
    assert result["total_rows"]==0
    assert verify_dart_day(roots[1]/result["capture_id"],result["manifest_sha256"])["rows"]==[]


def test_pit_stock_join_ambiguous_and_unusable_never_certified():
    report=observed_dart_stock_links(
        [row(1),row(2,corp="00000002"),row(3,code="A23456",corp="00000003"),
         row(4,code="123456",corp="???")],
        {"005930","A23456","123456"})
    assert report["observed_matching_security_count"]==1
    assert report["ambiguous_security_count"]==1
    assert report["unusable_rows"]==1
    assert report["issuer_class_pit_certified"] is False
