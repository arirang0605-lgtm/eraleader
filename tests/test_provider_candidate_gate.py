"""Opt-in two-provider PIT evidence MUST gate actual offline-integrated WATCH writes.

The paired input is synthetic and can only permit LOCAL research WATCH, never
legal permanent-issuer PIT or official candidate promotion.
"""
from __future__ import annotations

from datetime import timedelta, datetime, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json,sqlite3
import pytest

from eraleader.offline_pit import OfflineLedger
from eraleader.provider_candidate_gate import (
    audit_candidate_provider_gate,GATE_WATCH,GATE_BLOCK,
)
from test_provider_dual_source_audit import (
    make_pair,edit_stream,FIRST,
)

ASOF="2026-10-11T14:00:00+09:00"
NOW=FIRST+timedelta(hours=3)
FIXTURE=Path(__file__).parent/"fixtures/offline_synthetic.json"


def setup_case(tmp_path,*,change_b=None,b_clock=FIRST,change_market=None):
    root=tmp_path/"out"
    root.mkdir()
    writer=OfflineLedger(root/"offline.sqlite")
    try:
        writer.import_file(FIXTURE)
    finally:
        writer.close()
    pair=make_pair(tmp_path/"pair",
                   mutate_b=change_b,b_clock=b_clock,
                   market_b=change_market)
    return root,pair


def args(root,pair,*,market="KR",asof=ASOF):
    a,ha,b,hb=pair
    return ["offline-integrated","--market",market,
            "--as-of",asof,"--out",str(root),
            "--provider-ledger-a",str(a),"--provider-bundle-a",ha,
            "--provider-ledger-b",str(b),"--provider-bundle-b",hb]


def cohort(root,pair,*,market="KR",asof=ASOF,members=None):
    if members is None:
        db=OfflineLedger.open_readonly(root/"offline.sqlite")
        try:members=db.snapshot(asof,market=market)["members"]
        finally:db.close()
    return audit_candidate_provider_gate(
        pair[0],pair[1],pair[2],pair[3],
        market=market,decision_at=asof,candidate_members=members,clock=NOW,
    )


def test_consistent_dual_pit_can_only_permit_local_watch_not_official_promotion(tmp_path):
    root,pair=setup_case(tmp_path)
    r=cohort(root,pair)
    assert r["status"]==GATE_WATCH
    assert r["research_watch_allowed"] is True
    assert r["candidate_issuer_count"]==2
    assert r["locally_correlated_candidate_issuer_count"]==2
    assert r["source_consistency_only"] is True
    assert r["legal_issuer_identity_independently_verified"] is False
    assert r["historic_membership_pit_certified"] is False
    assert r["official_candidate_promotion_allowed"] is False
    assert r["leader_accuracy_certified"] is False
    assert r["official_leader_promotions"]==0
    assert r["blocker_count"]==0


def test_missing_in_both_sources_new_cohort_issuer_is_blocked(tmp_path):
    root,pair=setup_case(tmp_path)
    original=cohort(root,pair)
    member=json.loads(json.dumps(
        OfflineLedger.open_readonly(root/"offline.sqlite").snapshot(ASOF,market="KR")["members"]))
    member["NEW-CORP"]={**member["SYN-A"],"security_id":"NEW-CORP"}
    denied=cohort(root,pair,members=member)
    assert denied["status"]==GATE_BLOCK
    assert "CANDIDATE_MISSING_FROM_PROVIDER_A_AND_B" in denied["blocker_counts"]
    assert denied["research_watch_allowed"] is False


@pytest.mark.parametrize("field,changed",[
    ("ticker","CHANGED"),("industry_id","ANOTHER-INDUSTRY"),
    ("valid_from","2023-02-01"),("valid_to","2026-10-31"),
])
def test_offline_issuer_coverage_must_equal_both_provider_membership_claims(
    tmp_path,field,changed
):
    root,pair=setup_case(tmp_path)
    conn=OfflineLedger.open_readonly(root/"offline.sqlite")
    try:members=conn.snapshot(ASOF,market="KR")["members"]
    finally:conn.close()
    members["SYN-A"]={**members["SYN-A"],field:changed}
    r=cohort(root,pair,members=members)
    assert r["status"]==GATE_BLOCK
    assert r["blocker_counts"]["CANDIDATE_ISSUER_FIELD_MISMATCH"]==1


def test_other_company_action_ratio_conflict_blocks_whole_research_run(tmp_path):
    root,pair=setup_case(tmp_path,change_b=lambda m:edit_stream(
        m,"actions",lambda rows:rows[0].update(ratio=4)))
    denied=cohort(root,pair)
    assert denied["status"]==GATE_BLOCK
    assert denied["blocker_counts"]["PAIR_SPLIT_RATIO_CONFLICT"]==1
    assert denied["research_watch_allowed"] is False


def test_late_second_provider_blocks_even_if_both_agree(tmp_path):
    root,pair=setup_case(tmp_path,b_clock=FIRST+timedelta(hours=2))
    r=cohort(root,pair)
    assert r["status"]==GATE_BLOCK
    assert "PAIR_SOURCE_B_FIRST_REGISTERED_AFTER_DECISION" in r["blocker_counts"]
    assert r["locally_correlated_candidate_issuer_count"]==0


def test_no_offline_candidates_cannot_be_claimed_corroborated(tmp_path):
    root,pair=setup_case(tmp_path)
    r=cohort(root,pair,members={})
    assert r["status"]==GATE_BLOCK
    assert "NO_CANDIDATES_TO_CORROBORATE" in r["blocker_counts"]


def test_wrong_market_fails_before_promoting(tmp_path):
    root,pair=setup_case(tmp_path)
    with pytest.raises(ValueError,match="market|KR|US"):
        cohort(root,pair,market="US")


def test_cli_consistent_sources_write_research_watch_but_no_candidate_promotion(tmp_path,capsys):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    original=sha256((root/"offline.sqlite").read_bytes()).hexdigest()
    main(args(root,pair))
    data=json.loads(capsys.readouterr().out)
    assert data["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert data["official_leaders"]==0 and data["pit_certified"] is False
    assert data["provider_research_watch_allowed"] is True
    gate=json.loads((root/"provider_candidate_gate_research.json").read_text())
    assert gate["status"]==GATE_WATCH
    assert gate["official_candidate_promotion_allowed"] is False
    body=json.loads(Path(data["path"]).read_text())
    assert body["pit_certified"] is False
    assert body["provider_pair_gate"]["research_watch_allowed"] is True
    assert body["provider_pair_gate"]["historic_membership_pit_certified"] is False
    assert body["confirmed_leaders"]==0
    with sqlite3.connect(root/"state_history.sqlite") as db:
        assert {r[0] for r in db.execute("SELECT current FROM state_history")}=={"WATCH"}
    assert sha256((root/"offline.sqlite").read_bytes()).hexdigest()==original
    assert len(list((root/"runs").glob("joined_kr_*.json")))==1


def test_cli_conflicting_sources_do_not_publish_run_dashboard_or_watch_history(tmp_path,capsys):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path,change_b=lambda m:edit_stream(
        m,"actions",lambda rows:rows[0].update(ratio=4)))
    before=sha256((root/"offline.sqlite").read_bytes()).hexdigest()
    main(args(root,pair))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert result["new_prospective_research_signals"]==0
    assert result["official_leaders"]==0
    assert result["blocker_counts"]["PAIR_SPLIT_RATIO_CONFLICT"]==1
    assert (root/"provider_candidate_gate_research.json").is_file()
    assert not (root/"prospective.sqlite").exists()
    assert not (root/"state_history.sqlite").exists()
    assert not (root/"runs").exists()
    assert not (root/"site").exists()
    assert sha256((root/"offline.sqlite").read_bytes()).hexdigest()==before


def test_cli_late_claimed_provider_does_not_publish_synthetic_signals(tmp_path,capsys):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path,b_clock=FIRST+timedelta(hours=2))
    main(args(root,pair))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert result["new_prospective_research_signals"]==0
    assert not (root/"prospective.sqlite").exists()


def test_four_provider_flags_are_all_or_none_and_must_precede_file_creation(tmp_path,capsys):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    with pytest.raises(SystemExit) as error:
        main(["offline-integrated","--market","KR","--as-of",ASOF,
              "--out",str(root),"--provider-ledger-a",str(pair[0])])
    assert error.value.code==2
    assert "All four provider PIT flags" in capsys.readouterr().err
    assert not (root/"runs").exists()
    assert not (root/"prospective.sqlite").exists()


def test_invalid_source_original_receipt_rehash_cannot_write_watch(tmp_path,capsys):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    with sqlite3.connect(pair[2]) as db:
        db.execute("""UPDATE offline_records SET fingerprint=?
                      WHERE kind='membership'""",("0"*64,))
    with pytest.raises(SystemExit) as error:
        main(args(root,pair))
    assert error.value.code==2
    assert "fingerprint integrity mismatch" in capsys.readouterr().err
    assert not (root/"prospective.sqlite").exists()
    assert not (root/"runs").exists()


def test_gate_artifact_rejects_fake_authenticated_flags_in_wrapped_pair(tmp_path):
    root,pair=setup_case(tmp_path)
    gate=cohort(root,pair)
    assert gate["publisher_independently_authenticated"] is False
    assert gate["historic_membership_pit_certified"] is False
    assert gate["official_candidate_promotion_allowed"] is False
    assert gate["official_leader_promotions"]==0


def test_existing_price_only_research_cli_remains_backwards_compatible(tmp_path,capsys):
    from eraleader.cli import main
    root,_=setup_case(tmp_path)
    main(["offline-integrated","--market","KR","--as-of",ASOF,
          "--out",str(root)])
    normal=json.loads(capsys.readouterr().out)
    assert normal["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert not (root/"provider_candidate_gate_research.json").exists()
    assert normal["official_leaders"]==0
    assert normal["pit_certified"] is False


def test_derived_gate_only_backup_no_raw_sqlite_or_publisher_receipts(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    root,pair=setup_case(tmp_path,change_b=lambda m:edit_stream(
        m,"actions",lambda rows:rows[0].update(ratio=4)))
    main(args(root,pair))
    capsys.readouterr()
    derived=tmp_path/"derived"
    derived.mkdir()
    report=root/"provider_candidate_gate_research.json"
    (derived/report.name).write_bytes(report.read_bytes())
    zip_path=tmp_path/"safe_derived.zip"
    archived=create_backup(derived,zip_path)
    assert archived["file_count"]==1
    assert verify_backup(zip_path)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(zip_path) as z:
        assert z.namelist()==["provider_candidate_gate_research.json","MANIFEST.json"]
        assert all(not entry.endswith(".sqlite") for entry in z.namelist())
    restore_backup(zip_path,tmp_path/"restored")
    assert (tmp_path/"restored"/report.name).read_bytes()==report.read_bytes()


def test_pair_gate_report_is_tied_to_pinned_bundle_digests(tmp_path):
    root,pair=setup_case(tmp_path)
    r=cohort(root,pair)
    assert r["source_pair_bundle_sha256_a"]==pair[1]
    assert r["source_pair_bundle_sha256_b"]==pair[3]
    assert len(r["source_pair_digest_sha256"])==64
    assert r["source_pair_consistency_only"] is True
    assert r["historic_membership_pit_certified"] is False


def test_cli_target_has_issuer_not_in_either_provider_and_never_registers_watch(
    tmp_path,capsys,
):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    writer=OfflineLedger(root/"offline.sqlite")
    try:
        writer.import_rows("membership",[{
            "security_id":"EXTRA-LOCAL",
            "market":"KR","ticker":"777777","industry_id":"SYN-TECH",
            "valid_from":"2024-01-01","valid_to":None,
            "known_at":"2024-02-01T10:00:00+09:00",
            "source_id":"fixture2","revision":1,
        }],"synthetic_fixture")
    finally:writer.close()
    main(args(root,pair))
    outcome=json.loads(capsys.readouterr().out)
    assert outcome["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert outcome["blocker_counts"]["CANDIDATE_MISSING_FROM_PROVIDER_A_AND_B"]==1
    assert not (root/"prospective.sqlite").exists()
    assert not (root/"state_history.sqlite").exists()
    assert not (root/"runs").exists()


def test_delisted_source_membership_claim_cannot_be_eligible_local_watch(tmp_path):
    root,pair=setup_case(tmp_path)
    row={
        "security_id":"SYN-B","market":"KR","ticker":"222222",
        "industry_id":"SYN-TECH","valid_from":"2023-01-01",
        "valid_to":"2024-07-01",
    }
    report=cohort(root,pair,members={"SYN-B":row})
    assert report["status"]==GATE_BLOCK
    assert report["research_watch_allowed"] is False
    assert "CANDIDATE_ISSUER_NOT_ACTIVE_AT_DECISION" in report["blocker_counts"]


def test_cli_provider_pair_pins_a_different_research_run_id_than_ungated_baseline(
    tmp_path,capsys,
):
    from eraleader.cli import main
    normal,pair=setup_case(tmp_path)
    main(["offline-integrated","--market","KR","--as-of",ASOF,
          "--out",str(normal)])
    ungated=json.loads(capsys.readouterr().out)
    baseline=json.loads(Path(ungated["path"]).read_text())
    # New independent namespace avoids mutating an already registered
    # same-day source_run_id for the same actual existing WATCH research.
    gated=tmp_path/"gated"
    gated.mkdir()
    (gated/"offline.sqlite").write_bytes((normal/"offline.sqlite").read_bytes())
    main(args(gated,pair))
    paired=json.loads(capsys.readouterr().out)
    with_provenance=json.loads(Path(paired["path"]).read_text())
    assert paired["status"]=="OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert baseline["run_id"]!=with_provenance["run_id"]
    assert "provider_pair_gate" not in baseline
    assert with_provenance["provider_pair_gate"]["historic_membership_pit_certified"] is False


def _tamper_local_source_row(path,kind,mutator):
    with sqlite3.connect(path) as con:
        identity,payload=con.execute(
            "SELECT record_key,payload FROM offline_records WHERE kind=? LIMIT 1",
            (kind,),
        ).fetchone()
        row=json.loads(payload)
        mutator(row)
        value=json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        con.execute(
            """UPDATE offline_records SET payload=?,fingerprint=?
               WHERE kind=? AND record_key=?""",
            (value,sha256(value.encode()).hexdigest(),kind,identity),
        )


@pytest.mark.parametrize("kind,mutation,reason",[
    ("fundamentals",lambda r:r.update(value=1999),"CANDIDATE_FUNDAMENTAL_VALUE_MISMATCH"),
    ("industry",lambda r:r.update(value=1999),"CANDIDATE_INDUSTRY_VALUE_MISMATCH"),
    ("actions",lambda r:r.update(ratio=8) if r.get("action_type")=="split"
     else r.update(effective_on="2024-06-29"),"CANDIDATE_ACTION_SOURCE_MISMATCH"),
])
def test_original_candidate_fact_conflict_with_two_consistent_sources_blocks_watch(
    tmp_path,capsys,kind,mutation,reason,
):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    _tamper_local_source_row(root/"offline.sqlite",kind,mutation)
    main(args(root,pair))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert result["new_prospective_research_signals"]==0
    assert any(key.startswith(reason) for key in result["blocker_counts"])
    assert not (root/"prospective.sqlite").exists()
    assert not (root/"runs").exists()
    assert not (root/"state_history.sqlite").exists()


def test_candidate_offline_missing_disclosed_quarter_is_not_a_matching_financial_source(
    tmp_path,capsys,
):
    from eraleader.cli import main
    root,pair=setup_case(tmp_path)
    with sqlite3.connect(root/"offline.sqlite") as con:
        con.execute("""DELETE FROM offline_records
                       WHERE kind='fundamentals'
                         AND record_key=(SELECT min(record_key) FROM offline_records
                                         WHERE kind='fundamentals')""")
    main(args(root,pair))
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert "CANDIDATE_FUNDAMENTAL_COVERAGE_MISMATCH" in result["blocker_counts"]
    assert not (root/"prospective.sqlite").exists()


def test_model_cannot_supply_only_financial_records_without_industry_and_action_crosscheck(
    tmp_path,
):
    root,pair=setup_case(tmp_path)
    ledger=OfflineLedger.open_readonly(root/"offline.sqlite")
    try:source=ledger.snapshot(ASOF,market="KR")
    finally:ledger.close()
    with pytest.raises(ValueError,match="all|three|domains"):
        audit_candidate_provider_gate(
            pair[0],pair[1],pair[2],pair[3],
            market="KR",decision_at=ASOF,
            candidate_members=source["members"],
            candidate_facts=source["fundamentals"],clock=NOW,
        )
