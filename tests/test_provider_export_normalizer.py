"""KRX/DART and US SEC/exchange STAGED (not direct API) translation tests."""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import copy,json,sqlite3

import pytest

from eraleader.provider_export_normalizer import (
    normalize_provider_export, STAGE_SCHEMA, EXPORT_STATUS,
)
from eraleader.provider_pit_adapter import import_provider_bundle,inspect_provider_bundle
from eraleader.offline_pit import OfflineLedger

NOW=datetime(2026,10,11,7,0,tzinfo=timezone.utc)
RETRIEVED="2026-10-11T14:00:00+09:00"
PUBLISHED="2025-03-01T12:00:00+09:00"
DOC="SYNTHETIC_DOC_NOT_OFFICIAL"
PROFILE={"KR":"KRX_DART_STAGED_V1","US":"SEC_EXCHANGE_STAGED_V1"}
KIND_ORDER=("membership","actions","fundamentals","industry")


def rows_for(market="KR"):
    if market=="KR":
        identity={"corp_code":"00001234","issue_uid":"ISSUE_A"}
        extras={"stock_code":"123456","industry_code":"C27"}
        sector={"industry_code":"C27"}
    else:
        identity={"cik":"12345","share_class_uid":"CLASS_A"}
        extras={"ticker":"EXA.A","sic":"3571"}
        sector={"sic":"3571"}
    base={"revision":1,"source_document_id":DOC}
    membership={**base,**identity,**extras,
                "listed_on":"2024-01-02","delisted_on":None,
                "published_at":"2025-01-03T10:00:00+09:00"}
    action={**base,**identity,"event_uid":"SPLIT_A","action_type":"split",
            "effective_on":"2025-06-01","published_at":PUBLISHED,"ratio":2}
    fact={**base,**identity,"metric":"revenue","period_end":"2024-12-31",
          "published_at":PUBLISHED,"value":123.0,"unit":"MILLIONS_LOCAL"}
    industry={**base,**sector,"metric":"orders","period_end":"2024-12-31",
              "published_at":PUBLISHED,"value":321.0,"unit":"MILLIONS_LOCAL"}
    return {"membership":[membership],"actions":[action],
            "fundamentals":[fact],"industry":[industry]}


def stage_fixture(tmp_path, market="KR", *, rows=None, retrieved=RETRIEVED):
    folder=tmp_path/"raw"
    folder.mkdir(parents=True,exist_ok=True)
    allrows=copy.deepcopy(rows or rows_for(market))
    streams=[]
    for kind in KIND_ORDER:
        if kind not in allrows:continue
        file=folder/f"{kind}.jsonl"
        raw=b"".join(json.dumps(x,sort_keys=True).encode()+b"\n" for x in allrows[kind])
        file.write_bytes(raw)
        streams.append({"kind":kind,"file":file.name,
                        "sha256":sha256(raw).hexdigest(),
                        "record_count":len(allrows[kind])})
    manifest={
        "schema_version":STAGE_SCHEMA,
        "market":market,"profile":PROFILE[market],
        "source_id":"SYNTHETIC_STAGED_SOURCE",
        "publisher_id_claimed":"SYNTHETIC_NOT_KRX_NOT_SEC",
        "vintage_id":"LOCAL_TEST_20261011",
        "retrieved_at_claimed":retrieved,
        "streams":streams,
    }
    path=folder/"manifest.json"
    path.write_text(json.dumps(manifest,sort_keys=True))
    return path


def revise_stream(manifest,kind,callback,*,rehash=True):
    file=manifest.parent/f"{kind}.jsonl"
    rows=[json.loads(s) for s in file.read_text().splitlines()]
    callback(rows)
    raw=b"".join(json.dumps(x,sort_keys=True).encode()+b"\n" for x in rows)
    file.write_bytes(raw)
    if rehash:
        obj=json.loads(manifest.read_text())
        spec=next(s for s in obj["streams"] if s["kind"]==kind)
        spec["sha256"]=sha256(raw).hexdigest()
        spec["record_count"]=len(rows)
        manifest.write_text(json.dumps(obj,sort_keys=True))


def convert(tmp_path,market="KR",**kw):
    mf=stage_fixture(tmp_path,market=market,**kw)
    out=tmp_path/"normalized"
    result=normalize_provider_export(mf,out,clock=NOW)
    return mf,out,result


@pytest.mark.parametrize("market,prefix,issuer",[
    ("KR","KR:CORP00001234:ISSUE:ISSUE_A","00001234"),
    ("US","US:CIK0000012345:CLASS:CLASS_A","12345"),
])
def test_profile_normalizes_all_four_kinds_into_existing_atomic_pit_contract(
    tmp_path,market,prefix,issuer,
):
    mf,out,result=convert(tmp_path,market)
    assert result["status"]==EXPORT_STATUS
    assert result["market"]==market
    assert result["profile"]==PROFILE[market]
    assert result["source_raw_manifest_sha256"]==sha256(mf.read_bytes()).hexdigest()
    assert result["normalized_row_count"]==4
    assert result["publisher_independently_authenticated"] is False
    assert result["official_leader_promotions"]==0
    assert result["historic_pit_certified"] is False
    payload=json.loads((out/"membership.jsonl").read_text().strip())
    assert payload["security_id"]==prefix
    assert payload["source_id"]=="SYNTHETIC_STAGED_SOURCE"
    assert payload["market"]==market
    assert payload["valid_from"]=="2024-01-02"
    assert payload["known_at"]=="2025-01-03T01:00:00+00:00"
    assert "corp_code" not in payload and "cik" not in payload
    assert (out/"normalization_witnesses.jsonl").is_file()
    imported=import_provider_bundle(out/"manifest.json",tmp_path/"offline.sqlite",clock=NOW)
    assert imported["rows_received"]==4
    assert imported["rows_inserted"]==4
    store=OfflineLedger.open_readonly(tmp_path/"offline.sqlite")
    try:
        older=store.snapshot("2025-09-01T17:00:00+09:00",market=market)
        assert older["members"]=={}
        latest=store.snapshot("2026-10-11T18:00:00+09:00",market=market)
        assert prefix in latest["members"]
        assert latest["quality"]["historic_membership_pit_verified"] is False
    finally:store.close()


def test_kr_corpcodestockcode_are_distinct_from_required_issue_identity(tmp_path):
    raw=rows_for()
    del raw["membership"][0]["issue_uid"]
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="issue_uid|identity|missing"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)
    assert not (tmp_path/"normalized").exists()


def test_us_cik_alone_cannot_stand_in_for_share_class_identity(tmp_path):
    raw=rows_for("US")
    del raw["membership"][0]["share_class_uid"]
    mf=stage_fixture(tmp_path,market="US",rows=raw)
    with pytest.raises(ValueError,match="share_class_uid|identity|missing"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_us_two_distinct_share_classes_with_one_cik_not_collapsed_by_ticker(tmp_path):
    raw=rows_for("US")
    extra=copy.deepcopy(raw["membership"][0])
    extra["share_class_uid"]="CLASS_B"
    extra["ticker"]="EXA.B"
    raw["membership"].append(extra)
    mf=stage_fixture(tmp_path,market="US",rows=raw)
    result=normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)
    ids=[json.loads(s)["security_id"] for s in
         (tmp_path/"normalized"/"membership.jsonl").read_text().splitlines()]
    assert len(set(ids))==2
    assert result["normalized_row_count"]==5


def test_kr_stock_code_collision_different_issuer_overlap_censored(tmp_path):
    raw=rows_for()
    alt=copy.deepcopy(raw["membership"][0])
    alt["corp_code"]="00005678"
    raw["membership"].append(alt)
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="overlapping|ticker|identity"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_known_publication_after_claimed_retrieval_is_not_pit(tmp_path):
    mf=stage_fixture(tmp_path)
    revise_stream(mf,"membership",lambda rows: rows[0].update(
        published_at="2026-10-12T12:00:00+09:00"))
    with pytest.raises(ValueError,match="retriev|after|future"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_claimed_retrieval_after_local_clock_not_backdateable(tmp_path):
    mf=stage_fixture(tmp_path,retrieved="2026-10-12T12:00:00+09:00")
    with pytest.raises(ValueError,match="retriev|future"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_forged_source_file_sha_is_rejected_before_any_output(tmp_path):
    mf=stage_fixture(tmp_path)
    revise_stream(mf,"actions",lambda rows:rows[0].update(ratio=4),rehash=False)
    with pytest.raises(ValueError,match="SHA|digest|sha"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)
    assert not (tmp_path/"normalized").exists()


def test_source_data_remains_byte_identical_during_translation(tmp_path):
    mf=stage_fixture(tmp_path)
    digest={f:sha256(f.read_bytes()).hexdigest()
            for f in mf.parent.iterdir() if f.is_file()}
    normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)
    assert {f:sha256(f.read_bytes()).hexdigest() for f in digest}==digest


@pytest.mark.parametrize("field,wrong",[
    ("corp_code","12"),("stock_code","abc"),("issue_uid","../BAD"),
    ("industry_code","bad|industry"),("source_document_id",""),
])
def test_kr_invalid_staged_identity_or_document_id_fails_closed(tmp_path,field,wrong):
    raw=rows_for()
    raw["membership"][0][field]=wrong
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="invalid|Invalid|identity|document|code|Unsafe"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


@pytest.mark.parametrize("field,wrong",[
    ("cik","not-cik"),("share_class_uid","../../class"),("ticker","INVALID TICKER"),
    ("sic",""),("source_document_id",""),
])
def test_us_invalid_staged_identity_or_document_id_fails_closed(tmp_path,field,wrong):
    raw=rows_for("US")
    raw["membership"][0][field]=wrong
    mf=stage_fixture(tmp_path,market="US",rows=raw)
    with pytest.raises(ValueError,match="invalid|Invalid|identity|document|code|Unsafe"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_cross_market_profile_swap_rejected(tmp_path):
    mf=stage_fixture(tmp_path)
    obj=json.loads(mf.read_text())
    obj["profile"]=PROFILE["US"]
    mf.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="profile|market"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_issuer_missing_for_action_never_becomes_silent_raw_ticker_join(tmp_path):
    raw=rows_for()
    raw["actions"][0]["issue_uid"]="UNKNOWN_ISSUE"
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="issuer|membership|identity"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_missing_industry_id_in_membership_blocks_industry_fact(tmp_path):
    raw=rows_for()
    raw["industry"][0]["industry_code"]="MISSING_SECTOR"
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="industry|membership"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_extra_unsupported_api_field_is_not_guessed(tmp_path):
    raw=rows_for()
    raw["membership"][0]["live_stock_price"]=100
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="field|Unsupported|unknown"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_missing_or_symlink_staged_export_does_not_follow(tmp_path):
    mf=stage_fixture(tmp_path)
    sym=tmp_path/"alias.json"
    sym.symlink_to(mf)
    with pytest.raises(ValueError,match="symlink"):
        normalize_provider_export(sym,tmp_path/"normalized",clock=NOW)
    src=mf.parent/"membership.jsonl"
    real=mf.parent/"hold.jsonl"
    src.rename(real)
    src.symlink_to(real)
    with pytest.raises(ValueError,match="symlink"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_different_staged_source_with_same_target_no_overwrite(tmp_path):
    mf,out,_=convert(tmp_path)
    original={x.name:sha256(x.read_bytes()).hexdigest() for x in out.iterdir()}
    with pytest.raises(ValueError,match="exist|overwrite|target"):
        normalize_provider_export(mf,out,clock=NOW)
    assert {x.name:sha256(x.read_bytes()).hexdigest() for x in out.iterdir()}==original


def test_two_revision_fact_rows_have_distinct_original_publication_times(tmp_path):
    raw=rows_for()
    fact=copy.deepcopy(raw["fundamentals"][0])
    fact["revision"]=2
    fact["value"]=124.5
    fact["published_at"]="2025-03-10T12:00:00+09:00"
    raw["fundamentals"].append(fact)
    mf=stage_fixture(tmp_path,rows=raw)
    normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)
    facts=[json.loads(s) for s in (tmp_path/"normalized"/"fundamentals.jsonl").read_text().splitlines()]
    assert len(facts)==2
    assert facts[0]["available_at"]<facts[1]["available_at"]


def test_reversed_revision_published_at_rejected(tmp_path):
    raw=rows_for()
    fact=copy.deepcopy(raw["fundamentals"][0])
    fact["revision"]=2
    fact["published_at"]="2025-02-01T12:00:00+09:00"
    raw["fundamentals"].append(fact)
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="revision|chronolog"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_invalid_action_cash_payout_without_source_label_refused(tmp_path):
    raw=rows_for()
    raw["actions"][0]["cash_amount"]=2.5
    mf=stage_fixture(tmp_path,rows=raw)
    with pytest.raises(ValueError,match="action|optional|field"):
        normalize_provider_export(mf,tmp_path/"normalized",clock=NOW)


def test_local_cli_and_derived_only_backup_restore(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    mf=stage_fixture(tmp_path)
    dst=tmp_path/"normalized"
    derived=tmp_path/"derived"
    main(["normalize-provider-export","--manifest",str(mf),
          "--stage-dir",str(dst),"--out",str(derived)])
    meta=json.loads(capsys.readouterr().out)
    assert meta["historic_pit_certified"] is False
    assert meta["normalized_row_count"]==4
    report=derived/"provider_stage_normalization_research.json"
    assert report.is_file()
    assert not any("corp_code" in s or "cik" in s for s in report.read_text().splitlines())
    verify=inspect_provider_bundle(dst/"manifest.json")
    assert verify["rows_received"]==4
    ledger=tmp_path/"ledger.sqlite"
    imported=import_provider_bundle(dst/"manifest.json",ledger)
    assert imported["historic_pit_certified"] is False
    zip_path=tmp_path/"derived_only.zip"
    result=create_backup(derived,zip_path)
    assert result["file_count"]==1
    assert verify_backup(zip_path)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(zip_path) as z:
        assert z.namelist()==["provider_stage_normalization_research.json","MANIFEST.json"]
        assert not any(x.endswith(".jsonl") or x.endswith(".sqlite") for x in z.namelist())
    restore_backup(zip_path,tmp_path/"restored")
    assert (tmp_path/"restored"/report.name).read_bytes()==report.read_bytes()
