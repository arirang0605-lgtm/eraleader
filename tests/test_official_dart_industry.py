"""Actual DART industry profile parser + bounded current-issuer capture tests.

Synthetic only: real official 10-company receipt replay is run separately.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from eraleader import official_dart_industry as ind

NOW=datetime(2026,10,13,10,tzinfo=timezone.utc)
CORP="00126380"
PIN="d"*64


def profile(stock="005930",corp=CORP,sector="264",market="Y"):
    return json.dumps({"status":"000","corp_code":corp,
        "stock_code":stock,"corp_cls":market,"induty_code":sector},
        ensure_ascii=False).encode()


def test_official_company_json_parser_current_industry_only():
    actual=ind.parse_company_profile(profile(),stock_code="005930",corp_code=CORP)
    assert actual["current_dart_industry_code"]=="264"
    assert actual["current_dart_listed_class"]=="Y"
    assert actual["historic_industry_pit_certified"] is False
    assert actual["official_leader"] is False


@pytest.mark.parametrize("raw",[
    profile(stock="000660"),profile(corp="99999999"),
    profile(sector="26ABC"),profile(sector="26"),
    profile(market="E"),
    profile().replace(b'"status": "000"',b'"status": "013"'),
    b'{"status":"000","status":"000","stock_code":"005930","corp_code":"00126380"}',
    b'{bad}',
])
def test_bad_or_wrong_issuer_profile_cannot_join_market(raw):
    with pytest.raises(ValueError):
        ind.parse_company_profile(raw,stock_code="005930",corp_code=CORP)


@pytest.fixture
def capture_stub(tmp_path,monkeypatch):
    root=tmp_path/"capture"
    root.mkdir(mode=0o700);root.chmod(0o700)
    monkeypatch.setattr(ind,"verify_dart_corp_directory",
        lambda *_a,**_k:{"mapping":{"005930":CORP,"000660":"00164779"},
                         "first_receipt_sha256":PIN})
    return root


def test_real_raw_byte_capture_original_sha_and_asof_validation(capture_stub):
    received=ind.capture_company_profile(
        capture_stub,stock_code="005930",
        directory=(capture_stub,PIN),creds={"ERALEADER_DART_API_KEY":"a"*40},
        clock=lambda:NOW,fetch=lambda *_:profile())
    assert received["status"]=="CURRENT_DART_COMPANY_INDUSTRY_RESEARCH_ONLY"
    assert received["pit_certified"] is False
    path=capture_stub/received["capture_id"]
    assert path.is_dir()
    original=path/"first_receipt.json"
    assert sha256(original.read_bytes()).hexdigest()==received["first_receipt_sha256"]
    verified=ind.verify_company_profile(
        path,received["first_receipt_sha256"],directory=(capture_stub,PIN),
        decision_at=NOW)
    assert verified["current_dart_industry_code"]=="264"
    with pytest.raises(ValueError,match="first|conflict"):
        ind.verify_company_profile(
            path,received["first_receipt_sha256"],directory=(capture_stub,PIN),
            decision_at=datetime(2026,10,12,tzinfo=timezone.utc))


def test_modified_raw_must_fail_source_sha(capture_stub):
    received=ind.capture_company_profile(
        capture_stub,stock_code="005930",
        directory=(capture_stub,PIN),creds={"ERALEADER_DART_API_KEY":"a"*40},
        clock=lambda:NOW,fetch=lambda *_:profile())
    where=capture_stub/received["capture_id"]
    (where/"raw_response.json").write_bytes(profile(sector="261"))
    with pytest.raises(ValueError,match="conflict"):
        ind.verify_company_profile(where,received["first_receipt_sha256"],
                                   directory=(capture_stub,PIN),decision_at=NOW)


def test_collector_reuses_first_original_without_http(capture_stub):
    first=ind.capture_company_profile(
        capture_stub,stock_code="005930",
        directory=(capture_stub,PIN),creds={"ERALEADER_DART_API_KEY":"a"*40},
        clock=lambda:NOW,fetch=lambda *_:profile())
    actual=ind.collect_industry_profiles(
        private_root=capture_stub,directory=(capture_stub,PIN),
        stock_codes=("005930",),creds={},existing_only=True,clock=lambda:NOW,
        fetch=lambda *_a:pytest.fail("Existing first SHA forbids API re-fetch"))
    assert actual["industry_profiles_verified"]==1
    assert actual["companies"][0]["existing_original"] is True
    assert actual["companies"][0]["first_receipt_sha256"]==first["first_receipt_sha256"]


def test_missing_profile_is_null_and_does_not_trigger_http(capture_stub):
    result=ind.collect_industry_profiles(
        private_root=capture_stub,directory=(capture_stub,PIN),
        stock_codes=("005930",),creds={},existing_only=True,clock=lambda:NOW,
        fetch=lambda *_a:pytest.fail("Dry-run cannot fetch"))
    assert result["industry_profiles_verified"]==0
    assert result["companies"][0]["current_dart_industry_code"] is None
    assert result["companies"][0]["status"]=="PROFILE_NOT_CAPTURED"


def test_multiple_profile_first_receipts_are_revision_conflict(capture_stub):
    for _ in range(2):
        ind.capture_company_profile(
            capture_stub,stock_code="005930",
            directory=(capture_stub,PIN),creds={"ERALEADER_DART_API_KEY":"a"*40},
            clock=lambda:NOW,fetch=lambda *_:profile())
    with pytest.raises(ValueError,match="revision review"):
        ind.collect_industry_profiles(
            private_root=capture_stub,directory=(capture_stub,PIN),
            stock_codes=("005930",),creds={},
            existing_only=True,clock=lambda:NOW)
