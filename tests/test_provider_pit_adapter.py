"""Untrusted offline provider bundle intake tests: no network or genuine vendor files."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json, sqlite3

import pytest
from eraleader.provider_pit_adapter import (
    inspect_provider_bundle, import_provider_bundle, audit_registered_provider_asof,
    BUNDLE_SCHEMA, INTAKE_STATUS, ASOF_STATUS,
)
from eraleader.offline_pit import OfflineLedger

UTC=timezone.utc
FIRST=datetime(2026,10,11,4,30,tzinfo=UTC)
FIXTURE=Path(__file__).parent/"fixtures/offline_synthetic.json"
CLAIMED="2026-10-11T12:30:00+09:00"


def make_bundle(root:Path, *, market="KR", source="synthetic-exchange-v1",
                retrieved=CLAIMED, only_members=False):
    root.mkdir(parents=True,exist_ok=True)
    original=json.loads(FIXTURE.read_text())["records"]
    streams=[]
    payloads={}
    for kind in ("membership","actions","fundamentals","industry"):
        if only_members and kind!="membership":continue
        records=[dict(item,source_id=source) for item in original[kind]]
        if market=="US":
            if kind=="membership":
                for row in records:
                    row["market"]="US"
                    row["ticker"]=row["ticker"]+"_US"
        raw=b"".join(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()+b"\n"
                     for record in records)
        file=root/f"{kind}.jsonl"
        file.write_bytes(raw)
        streams.append({"kind":kind,"file":file.name,
                        "sha256":sha256(raw).hexdigest(),
                        "record_count":len(records)})
        payloads[kind]=records
    manifest={
        "schema_version":BUNDLE_SCHEMA,
        "market":market,
        "source_id":source,
        "publisher_id_claimed":"SYNTHETIC_EXCHANGE_NOT_REAL",
        "vintage_id":"v20261011",
        "retrieved_at_claimed":retrieved,
        "streams":streams,
    }
    mf=root/"manifest.json"
    mf.write_text(json.dumps(manifest,indent=2,sort_keys=True))
    return mf,payloads


def edit_manifest(manifest,callback):
    document=json.loads(manifest.read_text())
    callback(document)
    manifest.write_text(json.dumps(document,indent=2,sort_keys=True))


def edit_stream(manifest,kind,callback,*,rehash=True):
    root=manifest.parent
    path=root/f"{kind}.jsonl"
    rows=[json.loads(line) for line in path.read_bytes().splitlines()]
    callback(rows)
    raw=b"".join(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()+b"\n" for row in rows)
    path.write_bytes(raw)
    if rehash:
        edit_manifest(manifest,lambda obj:next(
            item for item in obj["streams"] if item["kind"]==kind
        ).update(sha256=sha256(raw).hexdigest(),record_count=len(rows)))


def ingest(tmp_path,manifest,*,as_clock=FIRST,market=None):
    return import_provider_bundle(
        manifest,tmp_path/"provider_offline.sqlite",
        clock=as_clock,
    )


def check(tmp_path,bundle_digest,decision,clock=FIRST+timedelta(days=1)):
    return audit_registered_provider_asof(
        tmp_path/"provider_offline.sqlite",bundle_digest,
        decision_at=decision,clock=clock,
    )


def test_valid_bundle_all_four_domains_single_transaction_and_prospective_receipt(tmp_path):
    manifest,_=make_bundle(tmp_path/"sources")
    result=ingest(tmp_path,manifest)
    assert result["status"]==INTAKE_STATUS
    assert result["market"]=="KR"
    assert result["rows_received"]==sum(result["by_kind_received"].values())
    assert result["rows_inserted"]==result["rows_received"]
    assert result["first_registered_at_utc"]==FIRST.isoformat()
    assert result["original_publisher_independently_authenticated"] is False
    assert result["historic_pit_certified"] is False
    assert result["official_leader_promotions"]==0
    conn=OfflineLedger.open_readonly(tmp_path/"provider_offline.sqlite")
    try:
        snap=conn.snapshot("2024-09-01T21:00:00+09:00",market="KR")
        assert "SYN-A" not in snap["members"]
        assert snap["quality"]["provider_rows_unavailable_at_decision_excluded"]>0
        assert snap["quality"]["historic_membership_pit_verified"] is False
        later=conn.snapshot("2026-10-12T12:00:00+09:00",market="KR")
        assert "SYN-A" in later["members"]
    finally:conn.close()
    assert check(tmp_path,result["bundle_sha256"],"2024-09-01T21:00:00+09:00")[
        "eligible_for_contemporaneous_research"] is False
    assert check(tmp_path,result["bundle_sha256"],"2026-10-12T12:00:00+09:00")[
        "eligible_for_contemporaneous_research"] is True


def test_stored_registered_time_cannot_be_rewritten_by_reimport(tmp_path):
    manifest,_=make_bundle(tmp_path/"sources")
    before=ingest(tmp_path,manifest)
    after=ingest(tmp_path,manifest,as_clock=FIRST+timedelta(minutes=25))
    assert after["status"]=="ALREADY_RECORDED_IDENTICAL_PROVIDER_BUNDLE"
    assert after["first_registered_at_utc"]==before["first_registered_at_utc"]
    assert after["rows_inserted"]==0


def test_bundle_is_research_only_even_claims_external_public_publisher(tmp_path):
    manifest,_=make_bundle(tmp_path/"sources")
    row=ingest(tmp_path,manifest)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        tags={r[0] for r in db.execute("SELECT DISTINCT provenance FROM offline_records")}
    assert tags=={"user_supplied"}
    assert row["source_retrieval_time_independently_attested"] is False


def test_provider_retrieved_at_claim_must_not_be_in_future(tmp_path):
    mf,_=make_bundle(tmp_path/"sources",retrieved="2026-10-12T14:00:00+09:00")
    with pytest.raises(ValueError,match="future|after|clock"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()


def test_future_dated_source_row_rejected_before_any_database_creation(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"membership",lambda rows:rows[0].update(
        known_at="2026-10-12T09:00:00+09:00"))
    with pytest.raises(ValueError,match="retriev|available|later"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()


def test_row_sha_corruption_cannot_partially_import_membership(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"industry",lambda rows:rows[0].update(value=999),rehash=False)
    with pytest.raises(ValueError,match="SHA|sha|hash"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()


def test_bundle_market_conflict_with_membership_blocked(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_manifest(mf,lambda data:data.update(market="US"))
    with pytest.raises(ValueError,match="market|KR|US"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()


def test_unknown_action_issuer_must_be_in_membership_batch(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"actions",lambda rows:rows[0].update(security_id="ANOTHER"))
    with pytest.raises(ValueError,match="membership|issuer|identity"):
        ingest(tmp_path,mf)


def test_unknown_industry_fact_must_link_declared_membership(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"industry",lambda rows:rows[0].update(industry_id="MISSING"))
    with pytest.raises(ValueError,match="industry|membership"):
        ingest(tmp_path,mf)


def test_cross_domain_source_id_mismatch_not_permitted(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"fundamentals",lambda rows:rows[0].update(source_id="OTHER"))
    with pytest.raises(ValueError,match="source_id|source"):
        ingest(tmp_path,mf)


def test_duplicate_stored_record_key_with_different_payload_rolls_back_all(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    ingest(tmp_path,mf)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        n=db.execute("SELECT COUNT(*) FROM offline_records").fetchone()[0]
    changed,_=make_bundle(tmp_path/"second",source="synthetic-exchange-v1")
    edit_manifest(changed,lambda m:m.update(vintage_id="v20261011-fix"))
    edit_stream(changed,"fundamentals",lambda r:r[0].update(value=987654))
    with pytest.raises(ValueError,match="Conflicting|conflict|immutable"):
        ingest(tmp_path,changed,as_clock=FIRST+timedelta(minutes=10))
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM offline_records").fetchone()[0]==n
        assert db.execute("SELECT COUNT(*) FROM provider_ingest_receipts").fetchone()[0]==1


def test_same_vintage_with_changed_manifest_is_conflict_without_overwrite(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    first=ingest(tmp_path,mf)
    edit_manifest(mf,lambda m:m.update(publisher_id_claimed="FORGED"))
    with pytest.raises(ValueError,match="vintage|Conflicting"):
        ingest(tmp_path,mf)
    assert check(tmp_path,first["bundle_sha256"],"2026-10-12T12:00:00+09:00")["status"]==ASOF_STATUS


def test_retrieval_claim_postdecision_excludes_contemporaneous_pit(tmp_path):
    mf,_=make_bundle(tmp_path/"sources",retrieved="2026-10-11T12:45:00+09:00")
    r=ingest(tmp_path,mf)
    audit=check(tmp_path,r["bundle_sha256"],"2026-10-11T12:35:00+09:00")
    assert audit["eligible_for_contemporaneous_research"] is False
    assert audit["retrospective_provider_retrieval"] is True
    assert audit["official_leader_promotions"]==0


def test_asof_report_never_certifies_history_when_clock_is_after_retrieved(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    r=ingest(tmp_path,mf)
    report=check(tmp_path,r["bundle_sha256"],"2026-10-12T12:00:00+09:00")
    assert report["eligible_for_contemporaneous_research"] is True
    assert report["publisher_independently_authenticated"] is False
    assert report["original_clock_independently_attested"] is False
    assert report["historic_universe_pit_certified"] is False
    assert report["true_future_leader_precision"] is None


def test_asof_future_cutoff_forbidden(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    r=ingest(tmp_path,mf)
    with pytest.raises(ValueError,match="future|Future"):
        check(tmp_path,r["bundle_sha256"],"2030-01-01T00:00:00+09:00")


@pytest.mark.parametrize("invalid",[
    "../../secret.jsonl", ".hidden.jsonl", "/tmp/raw.jsonl","bad name.jsonl",
])
def test_unsafe_manifest_file_basename_does_not_open(invalid,tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_manifest(mf,lambda m:m["streams"][0].update(file=invalid))
    with pytest.raises(ValueError,match="Unsafe|file|path"):
        ingest(tmp_path,mf)


def test_symlink_manifest_or_payload_rejected(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    link=tmp_path/"alias.json"
    link.symlink_to(mf)
    with pytest.raises(ValueError,match="symlink"):
        ingest(tmp_path,link)
    source=mf.parent/"membership.jsonl"
    renamed=source.with_name("actual.jsonl")
    source.rename(renamed)
    source.symlink_to(renamed)
    with pytest.raises(ValueError,match="symlink"):
        ingest(tmp_path,mf)


def test_duplicate_json_key_even_if_rehashed_file_rejected(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    path=mf.parent/"membership.jsonl"
    lines=path.read_text().splitlines()
    lines[0]=lines[0][:-1]+',"security_id":"ANOTHER"}'
    path.write_text("\n".join(lines)+"\n")
    edit_manifest(mf,lambda m:m["streams"][0].update(
        sha256=sha256(path.read_bytes()).hexdigest()))
    with pytest.raises(ValueError,match="Duplicate|duplicate"):
        ingest(tmp_path,mf)


def test_claimed_ticker_is_not_legal_permanent_issuer_certification(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    r=inspect_provider_bundle(mf,clock=FIRST)
    assert r["market"]=="KR"
    assert r["issuer_identity_independently_verified"] is False
    assert r["licensed_official_feed_verified"] is False
    assert r["ready_to_promote_leaders"] is False


def test_strict_date_order_revisions_must_be_monotonic(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    def append_old_revision(rows):
        row=dict(rows[0],revision=2,known_at="2023-01-01T10:00:00+09:00")
        rows.append(row)
    edit_stream(mf,"membership",append_old_revision)
    with pytest.raises(ValueError,match="revision|chronolog"):
        ingest(tmp_path,mf)


def test_duplicate_stream_kind_and_extra_manifest_fields_rejected(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_manifest(mf,lambda m:m["streams"].append(dict(m["streams"][0])))
    with pytest.raises(ValueError,match="Duplicate|kind"):
        ingest(tmp_path,mf)
    fresh,_=make_bundle(tmp_path/"second")
    edit_manifest(fresh,lambda m:m.update(secret_token="DO_NOT_ALLOW"))
    with pytest.raises(ValueError,match="schema|field|manifest"):
        ingest(tmp_path,fresh)


def test_readonly_asof_receipt_does_not_update_source_sqlite(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    r=ingest(tmp_path,mf)
    path=tmp_path/"provider_offline.sqlite"
    before=sha256(path.read_bytes()).hexdigest()
    check(tmp_path,r["bundle_sha256"],"2026-10-12T12:00:00+09:00")
    assert sha256(path.read_bytes()).hexdigest()==before


def test_cli_provider_import_and_asof_audit_output_are_derived_only(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    mf,_=make_bundle(tmp_path/"sources")
    result_dir=tmp_path/"out"
    main(["import-provider-pit","--manifest",str(mf),
          "--ledger",str(tmp_path/"provider_offline.sqlite"),
          "--out",str(result_dir)])
    meta=json.loads(capsys.readouterr().out)
    assert meta["historic_pit_certified"] is False
    assert meta["rows_inserted"]>0
    snap_before=sha256((tmp_path/"provider_offline.sqlite").read_bytes()).hexdigest()
    main(["audit-provider-pit-asof","--ledger",str(tmp_path/"provider_offline.sqlite"),
          "--bundle-sha256",meta["bundle_sha256"],
          "--decision-at","2024-09-01T21:00:00+09:00",
          "--out",str(result_dir)])
    report=json.loads(capsys.readouterr().out)
    assert report["eligible_for_contemporaneous_research"] is False
    assert report["official_leader_promotions"]==0
    assert sha256((tmp_path/"provider_offline.sqlite").read_bytes()).hexdigest()==snap_before
    arch=tmp_path/"derived.zip"
    backup=create_backup(result_dir,arch)
    assert backup["file_count"]==2
    assert verify_backup(arch)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(arch) as z:
        names=z.namelist()
        assert "provider_pit_import_research.json" in names
        assert "provider_pit_asof_research.json" in names
        assert "provider_offline.sqlite" not in names
    dst=tmp_path/"restored"
    restore_backup(arch,dst)
    for f in result_dir.iterdir():
        assert (dst/f.name).read_bytes()==f.read_bytes()


def test_rehashed_mutated_provider_row_after_import_is_rejected_by_asof_receipt(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    imported=ingest(tmp_path,mf)
    path=tmp_path/"provider_offline.sqlite"
    with sqlite3.connect(path) as db:
        row=db.execute("SELECT record_key,payload FROM offline_records WHERE kind='membership' LIMIT 1").fetchone()
        key,old=row
        updated=json.loads(old)
        updated["ticker"]="FORGED-SYMBOL"
        changed=json.dumps(updated,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        db.execute("UPDATE offline_records SET payload=?,fingerprint=? WHERE kind='membership' AND record_key=?",
                   (changed,sha256(changed.encode()).hexdigest(),key))
    with pytest.raises(ValueError,match="receipt|digest|changed|mismatch"):
        check(tmp_path,imported["bundle_sha256"],"2026-10-12T12:00:00+09:00")


def test_provider_asof_checks_deleted_source_row_against_first_import_receipt(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    imported=ingest(tmp_path,mf)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        db.execute("DELETE FROM offline_records WHERE kind='fundamentals' AND record_key=(SELECT min(record_key) FROM offline_records WHERE kind='fundamentals')")
    with pytest.raises(ValueError,match="receipt|row|missing|mismatch"):
        check(tmp_path,imported["bundle_sha256"],"2026-10-12T12:00:00+09:00")


def test_rehashed_forged_receipt_row_descriptor_cannot_pass_stored_bundle_digest(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    imported=ingest(tmp_path,mf)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        db.execute("""UPDATE provider_ingest_rows SET normalized_sha256=?
                      WHERE bundle_sha256=? AND kind='membership'""",
                   ("0"*64,imported["bundle_sha256"]))
    with pytest.raises(ValueError,match="receipt|digest|integrity|mismatch"):
        check(tmp_path,imported["bundle_sha256"],"2026-10-12T12:00:00+09:00")


def test_prospective_receipt_records_all_normalized_rows_in_db(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    imported=ingest(tmp_path,mf)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        rows=db.execute("SELECT kind,record_key,normalized_sha256 FROM provider_ingest_rows").fetchall()
    assert len(rows)==imported["rows_received"]
    assert all(len(h)==64 for _,_,h in rows)


def test_existing_unreceipted_source_is_not_blessed_as_new_provider_import(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    rows=json.loads(FIXTURE.read_text())["records"]
    store=OfflineLedger(tmp_path/"provider_offline.sqlite")
    try:
        for kind,items in rows.items():
            if kind=="membership":
                source=[dict(item,source_id="synthetic-exchange-v1") for item in items]
                store.import_rows(kind,source,"synthetic_fixture")
    finally:store.close()
    with pytest.raises(ValueError,match="preexisting|provenance|receipt|legacy"):
        ingest(tmp_path,mf)


def test_bundle_us_market_only_issuer_ids_never_certifies_cross_market_listing(tmp_path):
    mf,_=make_bundle(tmp_path/"sources",market="US")
    result=ingest(tmp_path,mf)
    assert result["market"]=="US"
    store=OfflineLedger.open_readonly(tmp_path/"provider_offline.sqlite")
    try:
        us=store.snapshot("2026-10-12T12:00:00+09:00",market="US")
        kr=store.snapshot("2026-10-12T12:00:00+09:00",market="KR")
        assert "SYN-A" in us["members"]
        assert not kr["members"]
    finally:store.close()
    assert result["historic_pit_certified"] is False


def test_no_second_issuer_can_reuse_overlapping_ticker_in_provider_batch(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    def collide(rows):
        rows[1]["ticker"]=rows[0]["ticker"]
    edit_stream(mf,"membership",collide)
    with pytest.raises(ValueError,match="overlapping|ticker"):
        ingest(tmp_path,mf)


def test_only_membership_bundle_is_valid_input_but_not_complete_pit(tmp_path):
    mf,_=make_bundle(tmp_path/"sources",only_members=True)
    r=ingest(tmp_path,mf)
    assert r["rows_inserted"]==3
    assert r["by_kind_received"]["actions"]==0
    assert r["historic_pit_certified"] is False


def test_import_existing_bundle_keeps_receipt_identity_in_one_transaction(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    first=ingest(tmp_path,mf)
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        before=db.execute("SELECT first_registered_at_utc FROM provider_ingest_receipts").fetchone()[0]
    replay=ingest(tmp_path,mf,as_clock=FIRST+timedelta(hours=3))
    assert replay["rows_inserted"]==0
    with sqlite3.connect(tmp_path/"provider_offline.sqlite") as db:
        assert db.execute("SELECT count(*) FROM provider_ingest_rows").fetchone()[0]==first["rows_received"]
        assert db.execute("SELECT first_registered_at_utc FROM provider_ingest_receipts").fetchone()[0]==before


def test_new_provider_vintage_can_reuse_identical_membership_and_append_revision(tmp_path):
    original,_=make_bundle(tmp_path/"v1")
    first=ingest(tmp_path,original)
    new,_=make_bundle(tmp_path/"v2")
    edit_manifest(new,lambda obj:obj.update(vintage_id="v20261011-corrected"))
    def add_revision(rows):
        rows.append(dict(rows[0],revision=2,
                         known_at="2024-07-22T12:00:00+09:00",
                         ratio=3))
    edit_stream(new,"actions",add_revision)
    added=ingest(tmp_path,new,as_clock=FIRST+timedelta(minutes=15))
    assert added["rows_inserted"]==1
    assert added["rows_received"]==first["rows_received"]+1
    assert added["status"]==INTAKE_STATUS
    assert check(tmp_path,first["bundle_sha256"],"2026-10-12T12:00:00+09:00")[
        "eligible_for_contemporaneous_research"] is True
    assert check(tmp_path,added["bundle_sha256"],"2026-10-12T12:00:00+09:00")[
        "eligible_for_contemporaneous_research"] is True


def test_revision_no_older_retrieval_or_future_date_can_override_older_decision(tmp_path):
    mf,_=make_bundle(tmp_path/"v1")
    first=ingest(tmp_path,mf)
    archived=check(tmp_path,first["bundle_sha256"],"2024-09-01T21:00:00+09:00")
    assert archived["retrospective_local_ingestion"] is True
    assert archived["rows_first_imported_local"]==first["rows_received"]
    assert archived["historic_universe_pit_certified"] is False


def test_denied_provider_retrospective_replay_even_with_valid_sha_and_old_known_at(tmp_path):
    mf,_=make_bundle(tmp_path/"sources",retrieved="2025-01-01T09:00:00+09:00")
    first=ingest(tmp_path,mf)
    audit=check(tmp_path,first["bundle_sha256"],"2025-02-01T09:00:00+09:00")
    assert audit["retrospective_provider_retrieval"] is False
    assert audit["retrospective_local_ingestion"] is True
    assert audit["eligible_for_contemporaneous_research"] is False


def test_missing_original_member_file_never_creates_offline_db(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    edit_manifest(mf,lambda obj:obj.__setitem__(
        "streams",[v for v in obj["streams"] if v["kind"]!="membership"]))
    with pytest.raises(ValueError,match="membership"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()


def test_prospectively_received_provider_rows_cannot_leak_into_legacy_2024_asof_snapshot(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    imported=ingest(tmp_path,mf)
    viewer=OfflineLedger.open_readonly(tmp_path/"provider_offline.sqlite")
    try:
        past=viewer.snapshot("2024-09-01T21:00:00+09:00",market="KR")
        assert past["members"]=={}
        assert past["fundamentals"]==[]
        assert past["quality"]["provider_rows_unavailable_at_decision_excluded"]>0
        today=viewer.snapshot("2026-10-12T12:00:00+09:00",market="KR")
        assert "SYN-A" in today["members"]
        assert today["quality"]["provider_rows_unavailable_at_decision_excluded"]==0
        assert today["quality"]["historic_membership_pit_verified"] is False
    finally:
        viewer.close()
    assert imported["first_registered_at_utc"]==FIRST.isoformat()


def test_plain_legacy_offline_ledger_unchanged_by_provider_vintage_filter(tmp_path):
    f=tmp_path/"legacy.sqlite"
    led=OfflineLedger(f)
    try:led.import_file(FIXTURE)
    finally:led.close()
    existing=OfflineLedger.open_readonly(f)
    try:
        historical=existing.snapshot("2024-09-01T21:00:00+09:00",market="KR")
        assert "SYN-A" in historical["members"]
        assert historical["quality"]["provider_rows_unavailable_at_decision_excluded"]==0
        assert historical["quality"]["historic_membership_pit_verified"] is False
    finally:existing.close()


def test_provider_source_not_available_at_decision_even_when_claimed_retrieval_in_future(tmp_path):
    mf,_=make_bundle(tmp_path/"sources")
    ingest(tmp_path,mf)
    ledger=OfflineLedger.open_readonly(tmp_path/"provider_offline.sqlite")
    try:
        before=ledger.snapshot("2026-10-11T12:29:59+09:00",market="KR")
        assert not before["members"]
        after=ledger.snapshot("2026-10-11T14:00:00+09:00",market="KR")
        assert "SYN-A" in after["members"]
    finally:ledger.close()


@pytest.mark.parametrize("field,value",[
    ("security_id","REUSE|FALSE"),
    ("ticker",True),
    ("industry_id","NE\u0000W"),
])
def test_issuer_joins_cannot_accept_ambiguous_key_delimiters_or_types(tmp_path,field,value):
    mf,_=make_bundle(tmp_path/"sources")
    edit_stream(mf,"membership",lambda r:r[0].update({field:value}))
    with pytest.raises(ValueError,match="identity|delimiter|type"):
        ingest(tmp_path,mf)
    assert not (tmp_path/"provider_offline.sqlite").exists()
