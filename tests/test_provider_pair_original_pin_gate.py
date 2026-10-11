"""2_2/2_5: original first-ingest PIN gate for dual suppliers and actual WATCH.

All cases use synthetic, claimed publishers. No independent PIT certificate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json, sqlite3
import pytest

from eraleader.cli import main
from eraleader.offline_pit import OfflineLedger
from eraleader.provider_candidate_gate import audit_candidate_provider_gate
from eraleader.provider_dual_source_audit import audit_provider_source_pair
from eraleader.provider_export_normalizer import normalize_provider_export
from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_provider_export_normalizer import (
    NOW, stage_fixture, rows_for, revise_stream,
)
from test_provider_dual_source_audit import make_pair

DECISION=(NOW+timedelta(minutes=15)).isoformat()
AUDIT=NOW+timedelta(hours=2)


def rich_rows(market="KR"):
    data=rows_for(market)
    f=data["fundamentals"][0]
    i=data["industry"][0]
    data["fundamentals"]=[
        {**f,"metric":metric,"period_end":period,
         "published_at":released,"value":value}
        for metric,low,high in (
            ("revenue",100,150),("operating_income",10,18)
        )
        for period,released,value in (
            ("2025-06-30","2025-09-01T12:00:00+09:00",low),
            ("2026-06-30","2026-08-01T12:00:00+09:00",high),
        )
    ]
    data["industry"]=[
        {**i,"metric":"revenue","period_end":period,
         "published_at":released,"value":value}
        for period,released,value in (
            ("2025-06-30","2025-09-01T12:00:00+09:00",100),
            ("2026-06-30","2026-08-01T12:00:00+09:00",140),
        )
    ]
    return data


def case(tmp_path,market="KR", *, pinned_a=True,pinned_b=True,
         b_document_id=None):
    paths=[]
    for label,pinned in (("A",pinned_a),("B",pinned_b)):
        home=tmp_path/("provider_"+label)
        data=rich_rows(market)
        if label=="B" and b_document_id is not None:
            for domain in data.values():
                for item in domain:
                    item["source_document_id"]=b_document_id
        raw=stage_fixture(home,market=market,rows=data)
        raw_manifest=json.loads(raw.read_text())
        raw_manifest["source_id"]="CLAIMED_SOURCE_"+label
        raw_manifest["publisher_id_claimed"]="CLAIMED_PUBLISHER_"+label
        raw.write_text(json.dumps(raw_manifest,sort_keys=True))
        norm=home/"normalized"
        normalize_provider_export(raw,norm,clock=NOW)
        ledger=home/"registered.sqlite"
        bundle=import_provider_bundle(
            norm/"manifest.json",ledger,clock=NOW,
            staged_manifest=raw if pinned else None,
        )
        paths.append((ledger,bundle["bundle_sha256"],raw,norm/"manifest.json"))
    return paths[0],paths[1]


def orig(pair):
    return ((pair[0][2],pair[0][3]),(pair[1][2],pair[1][3]))


def strict(pair,*,clock=AUDIT,decision=DECISION):
    return audit_provider_source_pair(
        pair[0][0],pair[0][1],pair[1][0],pair[1][1],
        decision_at=decision,clock=clock,
        require_original_pins=True,original_sources=orig(pair),
    )


def candidate(pair, market="KR",*,at=DECISION,clock=AUDIT):
    source=OfflineLedger.open_readonly(pair[0][0])
    try:
        local=source.snapshot(at,market=market)
    finally:
        source.close()
    return audit_candidate_provider_gate(
        pair[0][0],pair[0][1],pair[1][0],pair[1][1],
        market=market,decision_at=at,
        candidate_members=local["members"],
        candidate_facts=local["fundamentals"],
        candidate_industry=local["industry"],
        candidate_actions=local["actions"]+local["announced_future_actions"],
        clock=clock,require_original_pins=True,original_sources=orig(pair),
    )


def options(pair):
    return [
        "--provider-ledger-a",str(pair[0][0]),
        "--provider-bundle-a",pair[0][1],
        "--provider-ledger-b",str(pair[1][0]),
        "--provider-bundle-b",pair[1][1],
        "--require-provider-original-pins",
        "--provider-staged-manifest-a",str(pair[0][2]),
        "--provider-normalized-manifest-a",str(pair[0][3]),
        "--provider-staged-manifest-b",str(pair[1][2]),
        "--provider-normalized-manifest-b",str(pair[1][3]),
    ]


@pytest.mark.parametrize("market",("KR","US"))
def test_two_first_pinned_raw_sources_local_agreement_only(tmp_path,market):
    pair=case(tmp_path,market)
    files=[side[0] for side in pair]
    before=[sha256(p.read_bytes()).hexdigest() for p in files]
    result=strict(pair)
    assert result["status"]=="LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED"
    assert result["local_original_first_ingest_pins_required"] is True
    assert result["original_first_ingest_pins_locally_consistent"] is True
    assert result["source_a_original_first_pin_matched"] is True
    assert result["source_b_original_first_pin_matched"] is True
    assert len(result["original_source_pair_witness_sha256"])==64
    assert result["matched_corporate_event_count"]==1
    assert result["matched_fundamental_fact_count"]==4
    assert result["matched_industry_fact_count"]==2
    assert result["publisher_independently_authenticated"] is False
    assert result["historic_pit_certified"] is False
    assert result["official_leader_promotions"]==0
    assert [sha256(p.read_bytes()).hexdigest() for p in files]==before
    candidate_result=candidate(pair,market)
    assert candidate_result["research_watch_allowed"] is True
    assert candidate_result["original_first_ingest_pins_locally_consistent"] is True
    assert candidate_result["source_pair_original_pin_sha256"]==result["original_source_pair_witness_sha256"]
    assert candidate_result["historic_membership_pit_certified"] is False
    assert candidate_result["official_leader_promotions"]==0


def test_unpinned_legacy_second_provider_must_not_pass_strict(tmp_path):
    pair=case(tmp_path,pinned_b=False)
    with pytest.raises(ValueError,match="original|pin|first"):
        strict(pair)
    with pytest.raises(ValueError,match="original|pin|first"):
        candidate(pair)


def test_deleted_original_pin_row_cannot_downgrade_to_legacy(tmp_path):
    pair=case(tmp_path)
    with sqlite3.connect(pair[1][0]) as db:
        db.execute("DELETE FROM provider_staged_original_receipts")
    with pytest.raises(ValueError,match="original|pin|missing"):
        strict(pair)


def test_rehashed_raw_document_claim_and_witness_bypass_blocked(tmp_path):
    pair=case(tmp_path)
    raw=pair[1][2]
    revise_stream(raw,"membership",lambda rows:rows[0].update(
        source_document_id="FAKE_REPLACED_DOC"))
    regenerate=raw.parent/"rebuilt"
    normalize_provider_export(raw,regenerate,clock=NOW)
    assert (regenerate/"manifest.json").read_bytes()==pair[1][3].read_bytes()
    (pair[1][3].parent/"normalization_witnesses.jsonl").write_bytes(
        (regenerate/"normalization_witnesses.jsonl").read_bytes())
    with pytest.raises(ValueError,match="original|pin|first|witness"):
        strict(pair)


def test_source_a_raw_and_b_normalized_cross_swap_rejected(tmp_path):
    pair=case(tmp_path)
    sources=((pair[0][2],pair[1][3]),orig(pair)[1])
    with pytest.raises(ValueError,match="source|normalized|original|manifest"):
        audit_provider_source_pair(
            pair[0][0],pair[0][1],pair[1][0],pair[1][1],
            decision_at=DECISION,clock=AUDIT,
            require_original_pins=True,original_sources=sources,
        )


def test_require_flag_or_paths_incomplete_never_ignored(tmp_path):
    pair=case(tmp_path)
    for paths,required in (
        (None,True),(orig(pair),False),((pair[0][2],pair[0][3]),True)
    ):
        with pytest.raises(ValueError,match="original|pin|both|paths|pair"):
            audit_provider_source_pair(
                pair[0][0],pair[0][1],pair[1][0],pair[1][1],
                decision_at=DECISION,clock=AUDIT,
                original_sources=paths,require_original_pins=required)


def test_strict_pair_fails_if_decision_precedes_both_first_imports(tmp_path):
    pair=case(tmp_path)
    with pytest.raises(ValueError,match="original|decision|first|available|late"):
        strict(pair,decision=(NOW-timedelta(minutes=1)).isoformat())


def test_existing_plain_pair_remains_backwards_compatible(tmp_path):
    legacy=make_pair(tmp_path/"old")
    result=audit_provider_source_pair(
        legacy[0],legacy[1],legacy[2],legacy[3],
        decision_at="2026-10-11T14:00:00+09:00",clock=AUDIT)
    assert result["status"]=="LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED"
    assert result["local_original_first_ingest_pins_required"] is False
    assert result["original_first_ingest_pins_locally_consistent"] is False
    assert result["publisher_independently_authenticated"] is False


def test_offline_integrated_strict_cli_issues_positive_watch_and_verified_derived_backup(tmp_path,capsys):
    pair=case(tmp_path)
    out=tmp_path/"candidate_run"
    out.mkdir()
    import_provider_bundle(pair[0][3],out/"offline.sqlite",clock=NOW)
    before=[sha256(p.read_bytes()).hexdigest() for p in (
        pair[0][0],pair[1][0],out/"offline.sqlite"
    )]
    main(["offline-integrated","--market","KR","--as-of",DECISION,
          "--out",str(out),*options(pair)])
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert result["new_prospective_research_signals"]==1
    assert result["official_leaders"]==0
    assert result["pit_certified"] is False
    gate=json.loads((out/"provider_candidate_gate_research.json").read_text())
    assert gate["research_watch_allowed"] is True
    assert gate["original_first_ingest_pins_locally_consistent"] is True
    assert gate["official_candidate_promotion_allowed"] is False
    with sqlite3.connect(out/"prospective.sqlite") as db:
        assert db.execute("SELECT count(*) FROM prospective_signals").fetchone()[0]==1
    assert [sha256(p.read_bytes()).hexdigest() for p in (
        pair[0][0],pair[1][0],out/"offline.sqlite"
    )]==before
    # Back up only the derived summary, never the supplier original bytes.
    derived=tmp_path/"derived_only"
    derived.mkdir()
    (derived/"provider_candidate_gate_research.json").write_bytes(
        (out/"provider_candidate_gate_research.json").read_bytes())
    archive=tmp_path/"derived.zip"
    create_backup(derived,archive)
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    restore_backup(archive,tmp_path/"restored")
    assert (tmp_path/"restored"/"provider_candidate_gate_research.json").read_bytes()==(
        derived/"provider_candidate_gate_research.json").read_bytes()


def test_strict_cli_missing_pin_emits_no_watch_state_site_or_run(tmp_path):
    pair=case(tmp_path,pinned_b=False)
    out=tmp_path/"no_publish"
    out.mkdir()
    import_provider_bundle(pair[0][3],out/"offline.sqlite",clock=NOW)
    before=sha256((out/"offline.sqlite").read_bytes()).hexdigest()
    with pytest.raises(SystemExit) as blocked:
        main(["offline-integrated","--market","KR","--as-of",DECISION,
              "--out",str(out),*options(pair)])
    assert blocked.value.code==2
    assert not (out/"prospective.sqlite").exists()
    assert not (out/"state_history.sqlite").exists()
    assert not (out/"runs").exists()
    assert not (out/"site").exists()
    assert sha256((out/"offline.sqlite").read_bytes()).hexdigest()==before


def test_cli_partial_original_flags_and_missing_require_fail_before_write(tmp_path):
    pair=case(tmp_path)
    out=tmp_path/"incomplete"
    out.mkdir()
    base=["offline-integrated","--market","KR","--as-of",DECISION,"--out",str(out),
          "--provider-ledger-a",str(pair[0][0]),"--provider-bundle-a",pair[0][1],
          "--provider-ledger-b",str(pair[1][0]),"--provider-bundle-b",pair[1][1]]
    with pytest.raises(SystemExit) as missing:
        main(base+["--require-provider-original-pins"])
    assert missing.value.code==2
    with pytest.raises(SystemExit) as partial:
        main(base+["--provider-staged-manifest-a",str(pair[0][2])])
    assert partial.value.code==2
    assert not (out/"offline.sqlite").exists()


def test_cli_direct_pair_strict_and_report_no_raw_vendor_content(tmp_path,capsys):
    pair=case(tmp_path)
    out=tmp_path/"derived_pair"
    main(["audit-provider-source-pair",
          "--ledger-a",str(pair[0][0]),"--bundle-a",pair[0][1],
          "--ledger-b",str(pair[1][0]),"--bundle-b",pair[1][1],
          "--decision-at",DECISION,"--require-original-pins",
          "--staged-manifest-a",str(pair[0][2]),
          "--normalized-manifest-a",str(pair[0][3]),
          "--staged-manifest-b",str(pair[1][2]),
          "--normalized-manifest-b",str(pair[1][3]),
          "--out",str(out)])
    info=json.loads(capsys.readouterr().out)
    assert info["original_first_ingest_pins_locally_consistent"] is True
    report=json.loads((out/"provider_source_pair_research.json").read_text())
    assert report["historic_pit_certified"] is False
    assert "00001234" not in json.dumps(report)
    assert "SYNTHETIC_DOC_NOT_OFFICIAL" not in json.dumps(report)


def test_same_normalized_scores_but_distinct_first_pinned_document_claim_changes_run_digest(tmp_path):
    first=case(tmp_path/"first")
    second=case(tmp_path/"second",b_document_id="ALT_ORIGINAL_DOCUMENT_CLAIM")
    assert first[1][1]==second[1][1]  # economically identical normalized source
    assert first[0][1]==second[0][1]
    base=candidate(first)
    alternate=candidate(second)
    assert base["research_watch_allowed"] is True
    assert alternate["research_watch_allowed"] is True
    assert base["source_pair_original_pin_sha256"]!=alternate["source_pair_original_pin_sha256"]
    assert base["source_pair_digest_sha256"]!=alternate["source_pair_digest_sha256"]
    assert base["official_leader_promotions"]==0


def test_raw_document_pin_revised_during_candidate_domain_scan_never_permits_watch(tmp_path,monkeypatch):
    import eraleader.provider_candidate_gate as module
    pair=case(tmp_path)
    truth=module._full_receipt_source
    calls=[0]

    def change_claim_after_first_source_read(*args,**kwargs):
        rows=truth(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            original=pair[1][2]
            revise_stream(original,"membership",lambda items:items[0].update(
                source_document_id="RACED_PIN_DOC_ID"))
            fresh=original.parent/"raced_regeneration"
            normalize_provider_export(original,fresh,clock=NOW)
            assert (fresh/"manifest.json").read_bytes()==pair[1][3].read_bytes()
            (pair[1][3].parent/"normalization_witnesses.jsonl").write_bytes(
                (fresh/"normalization_witnesses.jsonl").read_bytes())
        return rows

    monkeypatch.setattr(module,"_full_receipt_source",change_claim_after_first_source_read)
    with pytest.raises(ValueError,match="original|pin|first|witness"):
        candidate(pair)
    assert calls[0]>=1
