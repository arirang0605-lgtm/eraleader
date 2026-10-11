"""2_2/2_5: genuinely distinct *claimed* provider streams, PIT same issuer vs ticker.

All local evidence is synthetic; no upstream identity, acquisition timestamp,
publisher independence, universe completeness, or leader skill certified.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest
from eraleader.provider_dual_source_audit import (
    audit_provider_source_pair,STATUS_CONSISTENT,STATUS_BLOCKED,STATUS_LATE,
)
from eraleader.provider_pit_adapter import import_provider_bundle
from test_provider_pit_adapter import make_bundle,edit_manifest,edit_stream,FIRST

DECISION="2026-10-11T14:00:00+09:00"
NOW=FIRST+timedelta(hours=3)


def make_pair(tmp_path,*,market="KR",market_b=None,publisher_b="PROVIDER_B",
              mutate_a=None,mutate_b=None,b_clock=FIRST,b_members_only=False):
    ma,_=make_bundle(tmp_path/"left_source",market=market,source="CLAIMED_SOURCE_A")
    mb,_=make_bundle(tmp_path/"right_source",market=market_b or market,
                     source="CLAIMED_SOURCE_B",only_members=b_members_only)
    edit_manifest(ma,lambda item:item.update(publisher_id_claimed="PROVIDER_A"))
    edit_manifest(mb,lambda item:item.update(publisher_id_claimed=publisher_b))
    if mutate_a:mutate_a(ma)
    if mutate_b:mutate_b(mb)
    a=tmp_path/"a.sqlite"
    b=tmp_path/"b.sqlite"
    aa=import_provider_bundle(ma,a,clock=FIRST)
    bb=import_provider_bundle(mb,b,clock=b_clock)
    return a,aa["bundle_sha256"],b,bb["bundle_sha256"]


def audit(pair,*,decision=DECISION,clock=NOW,sample_limit=12):
    a,da,b,db=pair
    return audit_provider_source_pair(
        a,da,b,db,decision_at=decision,clock=clock,sample_limit=sample_limit)


def test_exact_two_declared_providers_agree_without_independent_pit_claim(tmp_path):
    pair=make_pair(tmp_path)
    r=audit(pair)
    assert r["status"]==STATUS_CONSISTENT
    assert r["market"]=="KR"
    assert r["distinct_claimed_publishers"]==2
    assert r["matched_active_issuer_count"]==2
    assert r["matched_known_issuer_count"]==3
    assert r["matched_corporate_event_count"]==2
    assert r["source_a_first_registration_by_decision"] is True
    assert r["source_b_first_registration_by_decision"] is True
    assert r["source_consistency_only"] is True
    assert r["publisher_independently_authenticated"] is False
    assert r["permanent_issuer_identity_independently_attested"] is False
    assert r["official_historical_universe_pit_certified"] is False
    assert r["corporate_action_cash_settlement_verified"] is False
    assert r["historic_pit_certified"] is False
    assert r["real_future_leader_precision"] is None
    assert r["official_leader_promotions"]==0
    assert r["problem_count"]==0
    assert r["blocker_counts"]=={}
    assert all("source_id" not in row for row in r["problem_sample"])


def test_two_distinct_sources_with_different_issuer_ticker_are_blocked(tmp_path):
    def changed(m):edit_stream(m,"membership",lambda rows:rows[0].update(ticker="999999"))
    result=audit(make_pair(tmp_path,mutate_b=changed))
    assert result["status"]==STATUS_BLOCKED
    assert result["blocker_counts"]["MEMBERSHIP_TICKER_CONFLICT"]==1
    assert result["matched_active_issuer_count"]<2
    assert result["official_leader_promotions"]==0


def test_same_ticker_different_issuer_across_providers_never_auto_joins(tmp_path):
    def changed(m):
        edit_stream(m,"membership",lambda rows:rows[0].update(security_id="OTHER-ID"))
        edit_stream(m,"actions",lambda rows:rows[0].update(security_id="OTHER-ID"))
        edit_stream(m,"fundamentals",lambda rows:[
            row.update(security_id="OTHER-ID") for row in rows
            if row["security_id"]=="SYN-A"])
    result=audit(make_pair(tmp_path,mutate_b=changed))
    assert result["status"]==STATUS_BLOCKED
    assert result["blocker_counts"]["CROSS_PROVIDER_TICKER_ISSUER_CONFLICT"]==1
    assert result["matched_known_issuer_count"]<3


def test_same_declared_publisher_under_different_source_ids_cannot_fake_two_feeds(tmp_path):
    pair=make_pair(tmp_path,publisher_b="PROVIDER_A")
    with pytest.raises(ValueError,match="publisher|distinct|independ"):
        audit(pair)


def test_same_sqlite_two_bundles_cannot_be_misreported_independent(tmp_path):
    pair=make_pair(tmp_path)
    a,da,_,_=pair
    with pytest.raises(ValueError,match="different|independent|ledger"):
        audit((a,da,a,da))


def test_market_mismatch_fails_even_when_security_id_strings_match(tmp_path):
    pair=make_pair(tmp_path,market_b="US")
    with pytest.raises(ValueError,match="market|KR|US"):
        audit(pair)


def test_older_source_first_registered_later_than_decision_is_censored(tmp_path):
    pair=make_pair(tmp_path,b_clock=FIRST+timedelta(hours=2))
    r=audit(pair)
    assert r["status"]==STATUS_LATE
    assert r["matched_active_issuer_count"]==0
    assert r["matched_corporate_event_count"]==0
    assert "SOURCE_B_FIRST_REGISTERED_AFTER_DECISION" in r["blocker_counts"]
    assert r["locally_eligible_contemporaneous_provider_pair"] is False
    assert r["real_future_leader_precision"] is None


def test_claimed_source_retrieval_after_decision_is_censored(tmp_path):
    def delayed(m):edit_manifest(m,lambda r:r.update(
        retrieved_at_claimed="2026-10-11T14:45:00+09:00"))
    pair=make_pair(tmp_path,mutate_b=delayed,b_clock=FIRST+timedelta(hours=1,minutes=25))
    r=audit(pair)
    assert r["status"]==STATUS_LATE
    assert "SOURCE_B_RETRIEVED_AFTER_DECISION" in r["blocker_counts"]
    assert r["matched_known_issuer_count"]==0


def test_missing_b_member_is_not_inferred_from_ticker_price(tmp_path):
    def missing(m):edit_stream(m,"membership",lambda rows:rows.pop(-1))
    # Left source has SYN-C; one fewer right-source issuer is insufficient.
    r=audit(make_pair(tmp_path,mutate_b=missing))
    assert r["status"]==STATUS_BLOCKED
    assert "MEMBERSHIP_ONLY_A" in r["blocker_counts"]
    assert r["publisher_independently_authenticated"] is False


def test_missing_all_action_rows_in_one_feed_is_indeterminate_not_zero_success(tmp_path):
    r=audit(make_pair(tmp_path,b_members_only=True))
    assert r["status"]==STATUS_BLOCKED
    assert "ACTION_ONLY_A" in r["blocker_counts"]
    assert "FUNDAMENTAL_ONLY_A" in r["blocker_counts"]
    assert r["matched_corporate_event_count"]==0
    assert r["historic_pit_certified"] is False


def test_split_ratio_difference_is_action_conflict_not_censored_as_no_action(tmp_path):
    def amount(m):edit_stream(m,"actions",lambda rows:rows[0].update(ratio=4))
    r=audit(make_pair(tmp_path,mutate_b=amount))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["SPLIT_RATIO_CONFLICT"]==1
    assert r["matched_corporate_event_count"]==1


def test_corporate_event_record_ids_may_differ_if_effective_semantics_same(tmp_path):
    def rename(m):edit_stream(m,"actions",lambda rows:rows[0].update(action_id="PROVIDER_EVENT_B"))
    r=audit(make_pair(tmp_path,mutate_b=rename))
    assert r["status"]==STATUS_CONSISTENT
    assert r["matched_corporate_event_count"]==2


def test_same_day_action_same_type_two_separate_ids_is_ambiguous_and_blocked(tmp_path):
    def extra(m):
        def add(rows):
            rows.append({**rows[0],"action_id":"SECOND_SPLIT","ratio":3.0})
        edit_stream(m,"actions",add)
    # Valid provider JSONL may contain two same-day corporate actions, but a
    # semantic comparison must NOT silently merge them by action ID or date.
    r=audit(make_pair(tmp_path,mutate_b=extra))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["AMBIGUOUS_ACTION_SEMANTIC_KEY"]>=1


def test_difference_in_undelisted_membership_end_day_blocks_pit_identity(tmp_path):
    def modify(m):
        edit_stream(m,"membership",lambda rows:rows[1].update(valid_to="2024-07-05"))
    r=audit(make_pair(tmp_path,mutate_b=modify))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["MEMBERSHIP_VALID_TO_CONFLICT"]==1


def test_disagreeing_industry_code_on_issuer_blocks_sector_comparison(tmp_path):
    def sector(m):
        edit_stream(m,"membership",lambda rows:rows[0].update(industry_id="OTHER-INDUSTRY"))
        edit_stream(m,"industry",lambda rows:rows.append(
            {**rows[0],"industry_id":"OTHER-INDUSTRY"}))
    r=audit(make_pair(tmp_path,mutate_b=sector))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["MEMBERSHIP_INDUSTRY_CONFLICT"]==1


def test_revenue_revision_value_difference_blocks_fundamental_claim(tmp_path):
    def revenue(m):
        edit_stream(m,"fundamentals",lambda rows:rows[0].update(value=999))
    r=audit(make_pair(tmp_path,mutate_b=revenue))
    assert r["status"]==STATUS_BLOCKED
    assert "FUNDAMENTAL_VALUE_CONFLICT" in r["blocker_counts"]


def test_same_number_but_fundamental_unit_difference_does_not_match(tmp_path):
    def unit(m):edit_stream(m,"fundamentals",lambda rows:rows[0].update(unit="USD"))
    r=audit(make_pair(tmp_path,mutate_b=unit))
    assert r["status"]==STATUS_BLOCKED
    assert "FUNDAMENTAL_UNIT_CONFLICT" in r["blocker_counts"]


def test_source_b_membership_future_revision_after_cutoff_not_leaked(tmp_path):
    def late_revision(m):
        edit_stream(m,"membership",lambda rows:rows.append(
            {**rows[0],"revision":2,"known_at":"2026-10-11T15:00:00+09:00",
             "ticker":"444444"}))
        # Claimed retrieval must be >= 15:00 for a future correction but
        # cannot pretend it existed before the 14:00 decision.
        edit_manifest(m,lambda obj:obj.update(
            retrieved_at_claimed="2026-10-11T15:05:00+09:00"))
    pair=make_pair(tmp_path,mutate_b=late_revision,b_clock=FIRST+timedelta(hours=3))
    r=audit(pair,clock=FIRST+timedelta(hours=4))
    assert r["status"]==STATUS_LATE
    assert r["matched_active_issuer_count"]==0


def test_invalid_future_or_naive_decision_timestamp_refused(tmp_path):
    pair=make_pair(tmp_path)
    with pytest.raises(ValueError,match="future|Future"):
        audit(pair,decision="2030-01-01T00:00:00+09:00")
    with pytest.raises(ValueError,match="timezone|timestamp|ISO"):
        audit(pair,decision="2026-10-11T14:00:00")


def test_compromised_rehashed_pit_source_is_not_cross_verified(tmp_path):
    pair=make_pair(tmp_path)
    left,sha_a,*_=pair
    with sqlite3.connect(left) as db:
        key,payload=db.execute(
            "SELECT record_key,payload FROM offline_records WHERE kind='membership' LIMIT 1"
        ).fetchone()
        obj=json.loads(payload);obj["ticker"]="999999"
        data=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        db.execute("""UPDATE offline_records SET payload=?,fingerprint=?
                      WHERE kind='membership' AND record_key=?""",
                   (data,sha256(data.encode()).hexdigest(),key))
    with pytest.raises(ValueError,match="receipt|integrity|mismatch|digest"):
        audit(pair)


def test_missing_receipt_link_or_row_cannot_produce_correspondence(tmp_path):
    pair=make_pair(tmp_path)
    with sqlite3.connect(pair[2]) as db:
        db.execute("""DELETE FROM provider_ingest_rows
                      WHERE kind='actions' AND
                            rowid=(SELECT min(rowid) FROM provider_ingest_rows
                                   WHERE kind='actions')""")
    with pytest.raises(ValueError,match="receipt|row|count|mismatch"):
        audit(pair)


def test_sample_truncation_does_not_hide_total_blocker_count(tmp_path):
    def change(m):
        edit_stream(m,"membership",lambda rows:rows[0].update(ticker="999999"))
        edit_stream(m,"fundamentals",lambda rows:rows[0].update(value=9999))
    r=audit(make_pair(tmp_path,mutate_b=change),sample_limit=1)
    assert r["problem_count"]>=2
    assert len(r["problem_sample"])==1
    assert r["problem_sample_truncated"] is True
    assert sum(r["blocker_counts"].values())==r["problem_count"]


def test_readonly_two_ledgers_and_no_publishing_side_effect(tmp_path):
    pair=make_pair(tmp_path)
    left,right=Path(pair[0]),Path(pair[2])
    before=(sha256(left.read_bytes()).hexdigest(),
            sha256(right.read_bytes()).hexdigest())
    audit(pair)
    after=(sha256(left.read_bytes()).hexdigest(),
           sha256(right.read_bytes()).hexdigest())
    assert before==after


def test_cli_writes_safe_derived_json_and_backup_restores_only_report(tmp_path,capsys):
    from eraleader.cli import main
    from eraleader.local_backup import create_backup,verify_backup,restore_backup
    from zipfile import ZipFile
    pair=make_pair(tmp_path)
    destination=tmp_path/"derived"
    main(["audit-provider-source-pair",
          "--ledger-a",str(pair[0]),"--bundle-a",pair[1],
          "--ledger-b",str(pair[2]),"--bundle-b",pair[3],
          "--decision-at",DECISION,"--out",str(destination)])
    meta=json.loads(capsys.readouterr().out)
    assert meta["historic_pit_certified"] is False
    assert meta["official_leader_promotions"]==0
    report=destination/"provider_source_pair_research.json"
    obj=json.loads(report.read_text())
    assert obj["status"]==STATUS_CONSISTENT
    assert obj["publisher_independently_authenticated"] is False
    archive=tmp_path/"derived.zip"
    created=create_backup(destination,archive)
    assert created["file_count"]==1
    assert verify_backup(archive)["status"]=="LOCAL_BACKUP_VERIFIED"
    with ZipFile(archive) as zipf:
        names=zipf.namelist()
        assert names==["provider_source_pair_research.json","MANIFEST.json"]
        assert not any(".sqlite" in s or ".jsonl" in s for s in names)
    restored=tmp_path/"restored"
    restore_backup(archive,restored)
    assert (restored/report.name).read_bytes()==report.read_bytes()


def test_us_two_claimed_feeds_compare_security_class_without_kr_ticker_mapping(tmp_path):
    pair=make_pair(tmp_path,market="US")
    r=audit(pair)
    assert r["status"]==STATUS_CONSISTENT
    assert r["market"]=="US"
    assert r["matched_active_issuer_count"]==2
    assert r["official_historical_universe_pit_certified"] is False


def test_industry_revisions_value_contradiction_blocks_sector_growth_evidence(tmp_path):
    def adjust(m):
        edit_stream(m,"industry",lambda rows:rows[0].update(value=654321))
    r=audit(make_pair(tmp_path,mutate_b=adjust))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["INDUSTRY_VALUE_CONFLICT"]==1
    assert r["matched_industry_fact_count"]<4


def test_dividend_payouts_are_not_accepted_when_claimed_cash_does_not_match(tmp_path):
    def add_dividend(manifest,amount):
        def append(rows):
            rows.append({
                "source_id":rows[0]["source_id"],
                "revision":1,"security_id":"SYN-A",
                "action_id":"DIV-ONE","action_type":"dividend",
                "effective_on":"2024-08-30",
                "known_at":"2024-07-21T12:00:00+09:00",
                "cash_amount":amount,
            })
        edit_stream(manifest,"actions",append)
    pair=make_pair(tmp_path,
                   mutate_a=lambda m:add_dividend(m,1.0),
                   mutate_b=lambda m:add_dividend(m,1.5))
    r=audit(pair)
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["DIVIDEND_CASH_AMOUNT_CONFLICT"]==1
    assert r["corporate_action_cash_settlement_verified"] is False


def test_a_new_industry_fact_missing_in_other_source_is_a_gap_not_consensus(tmp_path):
    def missing(m):edit_stream(m,"industry",lambda rows:rows.pop(-1))
    r=audit(make_pair(tmp_path,mutate_b=missing))
    assert r["status"]==STATUS_BLOCKED
    assert r["blocker_counts"]["INDUSTRY_ONLY_A"]==1
    assert r["problem_count"]>=1


def test_declared_source_id_alone_must_be_distinct_even_when_publisher_strings_differ(tmp_path):
    def source_b_same(m):
        edit_manifest(m,lambda data:data.update(source_id="CLAIMED_SOURCE_A"))
        for k in ("membership","actions","fundamentals","industry"):
            edit_stream(m,k,lambda rows:[
                r.update(source_id="CLAIMED_SOURCE_A") for r in rows])
    pair=make_pair(tmp_path,mutate_b=source_b_same)
    with pytest.raises(ValueError,match="distinct"):
        audit(pair)


@pytest.mark.parametrize("sample_limit",[0,-1,False,201])
def test_invalid_audit_sample_limit_fails_early(tmp_path,sample_limit):
    pair=make_pair(tmp_path)
    with pytest.raises(ValueError,match="sample limit"):
        audit(pair,sample_limit=sample_limit)
