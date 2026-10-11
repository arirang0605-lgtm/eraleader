"""2_2/2_5 third DECLARED full-exchange class source, never official PIT."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader.exchange_roster_crosscheck import (
    audit_declared_exchange_roster,
    MATCH, BLOCKED, CENSORED,
)
from eraleader.issuer_class_bridge import _entity
from eraleader.issuer_lineage import ZONES
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_issuer_class_bridge import fixture as issuer_fixture,DECISION,CLOCK
from test_provider_export_normalizer import rows_for

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"audit_exchange_roster.py"


def fixture(tmp_path,market="KR",*,rows=None):
    stage,reference=issuer_fixture(tmp_path,market,rows=rows)
    source=json.loads(reference.read_text())
    local=datetime.fromisoformat(DECISION).astimezone(ZONES[market]).date()
    identities=[{
        "security_id":row["security_id"],
        "ticker":row["ticker"],
        "valid_from":row["valid_from"],
        "valid_to":row["valid_to"],
    } for row in source["identities"] if
        row["valid_from"]<=local.isoformat() and
        (row["valid_to"] is None or row["valid_to"]>local.isoformat())]
    roster={
        "schema_version":"eraleader.declared_exchange_roster.v1",
        "market":market,"source_id":"THIRD_DECLARED_EXCHANGE_SCOPE_SOURCE",
        "publisher_id_claimed":"INDEPENDENT_CLAIMED_EXCHANGE_INVENTORY",
        "scope_id":"ALL_LISTED_EQUITY_CLASSES",
        "complete_scope_claimed":True,
        "session_day":local.isoformat(),
        "published_at":"2026-10-11T14:10:00+09:00",
        "retrieved_at":"2026-10-11T14:20:00+09:00",
        "security_classes":identities,
    }
    file=tmp_path/"claimed_exchange_roster.json"
    file.write_text(json.dumps(roster,sort_keys=True))
    return stage,reference,file


def mutate(roster,fn):
    doc=json.loads(roster.read_text())
    fn(doc)
    roster.write_text(json.dumps(doc,sort_keys=True))


def audit(paths,*,decision=DECISION,clock=CLOCK):
    return audit_declared_exchange_roster(
        *paths,decision_at=decision,clock=clock)


@pytest.mark.parametrize("market",["KR","US"])
def test_all_class_match_is_never_official_complete_pit(tmp_path,market):
    inputs=fixture(tmp_path,market)
    originals={str(p):sha256(p.read_bytes()).hexdigest() for p in inputs}
    report=audit(inputs)
    assert report["status"]==MATCH
    assert report["market"]==market
    assert report["locally_matched_full_scope_classes"]==1
    assert report["declared_exchange_class_count"]==1
    assert report["staged_asof_class_count"]==1
    assert report["issuer_lineage_asof_class_count"]==1
    assert report["blocker_count"]==0
    assert report["asof_roster_retrieved_claimed"] is True
    assert report["three_distinct_publishers_claimed"] is True
    assert report["historical_exchange_universe_pit_certified"] is False
    assert report["legal_security_class_independently_authenticated"] is False
    assert report["claimed_publication_clock_independently_attested"] is False
    assert report["official_leader_promotions"]==0
    assert report["real_future_leader_precision"] is None
    assert report["external_api_calls"]==0
    assert "KR:CORP00001234" not in json.dumps(report)
    assert "US:CIK0000012345" not in json.dumps(report)
    assert originals=={str(p):sha256(p.read_bytes()).hexdigest() for p in inputs}


def test_us_two_share_classes_under_one_issuer_both_required_in_full_scope(tmp_path):
    raw=rows_for("US")
    second=deepcopy(raw["membership"][0])
    second.update(share_class_uid="CLASS_B",ticker="EXA.B",
                  source_document_id="SECOND_CLASS_IN_FULL_MARKET")
    raw["membership"].append(second)
    inputs=fixture(tmp_path,"US",rows=raw)
    result=audit(inputs)
    assert result["status"]==MATCH
    assert result["declared_exchange_class_count"]==2
    assert result["locally_matched_full_scope_classes"]==2


@pytest.mark.parametrize("edit,code",[
    (lambda d:d["security_classes"].clear(),"PIT_PAIR_CLASS_MISSING_FROM_EXCHANGE_ROSTER"),
    (lambda d:d["security_classes"].append({
        "security_id":"KR:CORP99999999:ISSUE:EXTRA",
        "ticker":"999999","valid_from":"2020-01-01","valid_to":None
    }),"EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE"),
    (lambda d:d["security_classes"][0].update(ticker="999999"),
     "EXCHANGE_CLASS_TICKER_CONFLICT"),
    (lambda d:d["security_classes"][0].update(valid_from="2020-02-02"),
     "EXCHANGE_CLASS_LISTING_INTERVAL_CONFLICT"),
])
def test_roster_coverage_ticker_and_interval_conflicts_block(tmp_path,edit,code):
    inputs=fixture(tmp_path)
    mutate(inputs[2],edit)
    # Empty universe cannot establish a real exchange roster at all.
    if code=="PIT_PAIR_CLASS_MISSING_FROM_EXCHANGE_ROSTER":
        with pytest.raises(ValueError,match="contract|roster"):
            audit(inputs)
    else:
        result=audit(inputs)
        assert result["status"]==BLOCKED
        assert result["blocker_counts"][code]>=1
        assert result["locally_matched_full_scope_classes"]==0


@pytest.mark.parametrize("row_update",[
    {"security_id":"KR:CORP99999999:ISSUE:ALIAS"},
    {"security_id":"KR:CORP00001234:ISSUE:DIFFERENT"},
])
def test_same_ticker_not_same_issuer_or_share_class(tmp_path,row_update):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d["security_classes"][0].update(row_update))
    result=audit(inputs)
    assert result["status"]==BLOCKED
    assert result["blocker_counts"]["PIT_PAIR_CLASS_MISSING_FROM_EXCHANGE_ROSTER"]==1
    assert result["blocker_counts"]["EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE"]==1


@pytest.mark.parametrize("field",["source_id","publisher_id_claimed"])
def test_same_claimed_origin_is_censored_even_when_all_rows_equal(tmp_path,field):
    inputs=fixture(tmp_path)
    reference=json.loads(inputs[1].read_text())
    mutate(inputs[2],lambda d:d.update({field:reference[field]}))
    result=audit(inputs)
    assert result["status"]==CENSORED
    assert "NOT_THREE_DISTINCT_CLAIMED_" in " ".join(result["blocker_counts"])
    assert result["locally_matched_full_scope_classes"]==0


def test_publisher_casefold_alias_does_not_bypass_independence(tmp_path):
    inputs=fixture(tmp_path)
    reference=json.loads(inputs[1].read_text())
    mutate(inputs[2],lambda d:d.update(
        {"publisher_id_claimed":reference["publisher_id_claimed"].upper()}))
    result=audit(inputs)
    assert result["status"]==CENSORED
    assert result["blocker_counts"]["NOT_THREE_DISTINCT_CLAIMED_PUBLISHERS"]==1


@pytest.mark.parametrize("field,new,expected",[
    ("published_at","2026-10-11T14:40:00+09:00","ROSTER_NOT_PUBLISHED_BY_DECISION"),
    ("retrieved_at","2026-10-11T14:50:00+09:00","ROSTER_NOT_RETRIEVED_BY_DECISION"),
])
def test_source_obtained_after_decision_is_retrospective_censored(tmp_path,field,new,expected):
    inputs=fixture(tmp_path)
    if field=="published_at":
        mutate(inputs[2],lambda d:d.update(
            {"published_at":new,"retrieved_at":"2026-10-11T14:55:00+09:00"}))
    else:
        mutate(inputs[2],lambda d:d.update({field:new}))
    result=audit(inputs)
    assert result["status"]==CENSORED
    assert result["blocker_counts"][expected]==1
    assert result["historical_exchange_universe_pit_certified"] is False


def test_retrieval_before_publication_is_rejected(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d.update(
        {"published_at":"2026-10-11T14:25:00+09:00",
         "retrieved_at":"2026-10-11T14:05:00+09:00"}))
    with pytest.raises(ValueError,match="order"):
        audit(inputs)


def test_future_local_exchange_session_blocked_before_looking_at_members(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d.update({"session_day":"2026-10-12"}))
    with pytest.raises(ValueError,match="Future"):
        audit(inputs)


def test_older_exchange_day_cannot_claim_current_complete_market(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d.update({"session_day":"2026-10-10"}))
    with pytest.raises(ValueError,match="Different"):
        audit(inputs)


def test_incomplete_exchange_scope_claim_is_blocked_not_promoted(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d.update({"complete_scope_claimed":False}))
    result=audit(inputs)
    assert result["status"]==BLOCKED
    assert result["blocker_counts"]["ROSTER_NOT_CLAIMED_COMPLETE_EXCHANGE_SCOPE"]==1


@pytest.mark.parametrize("invalid",[
    {"valid_from":"2027-01-01"},
    {"valid_to":"2025-01-01"},
    {"ticker":"NOT_A_STOCK"},
])
def test_invalid_class_interval_or_security_code_fails_closed(tmp_path,invalid):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d["security_classes"][0].update(invalid))
    with pytest.raises(ValueError,match="not-yet-listed|interval|ticker"):
        audit(inputs)


def test_exchange_roster_duplicate_security_class_cannot_inflate_denominator(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d["security_classes"].append(
        deepcopy(d["security_classes"][0])))
    with pytest.raises(ValueError,match="Duplicate"):
        audit(inputs)


def test_exchange_roster_duplicate_active_ticker_rejected(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d["security_classes"].append({
        "security_id":"KR:CORP99999999:ISSUE:OTHER",
        "ticker":d["security_classes"][0]["ticker"],
        "valid_from":"2020-01-01","valid_to":None,
    }))
    with pytest.raises(ValueError,match="Duplicate active exchange ticker"):
        audit(inputs)


def test_wrong_market_and_missing_class_id_refused(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d.update({"market":"US"}))
    with pytest.raises(ValueError,match="market"):
        audit(inputs)
    inputs=fixture(tmp_path/"separate")
    mutate(inputs[2],lambda d:d["security_classes"][0].update({"security_id":"KR:TICKER_ONLY"}))
    with pytest.raises(ValueError,match="class"):
        audit(inputs)


def test_rehashing_untrusted_lineage_without_consistent_roster_does_not_pass(tmp_path):
    inputs=fixture(tmp_path)
    data=json.loads(inputs[1].read_text())
    data["identities"][0]["ticker"]="777777"
    inputs[1].write_text(json.dumps(data))
    result=audit(inputs)
    assert result["status"]==BLOCKED
    assert result["staged_issuer_bridge_status"]=="BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"
    assert result["locally_matched_full_scope_classes"]==0


def test_mid_audit_roster_change_fails_even_when_rest_of_sources_unchanged(tmp_path,monkeypatch):
    import eraleader.exchange_roster_crosscheck as mod
    inputs=fixture(tmp_path)
    first=mod._one_pass
    calls=[0]
    def revise(*args,**kwargs):
        value=first(*args,**kwargs)
        calls[0]+=1
        if calls[0]==1:
            inputs[2].write_bytes(inputs[2].read_bytes()+b" ")
        return value
    monkeypatch.setattr(mod,"_one_pass",revise)
    with pytest.raises(ValueError,match="revised"):
        audit(inputs)
    assert calls[0]==2


def test_reject_roster_symlink_and_duplicate_json_keys(tmp_path):
    stage,ref,roster=fixture(tmp_path)
    duplicate=roster.read_text().replace('"schema_version":','"schema_version":"spoof", "schema_version":',1)
    roster.write_text(duplicate)
    with pytest.raises(ValueError,match="Duplicate|JSON|duplicate"):
        audit((stage,ref,roster))
    stage,ref,roster=fixture(tmp_path/"second")
    copy=roster.parent/"outside.json"
    roster.rename(copy)
    roster.symlink_to(copy)
    with pytest.raises(ValueError,match="unsafe|Missing"):
        audit((stage,ref,roster))


def test_cli_sanitized_derived_backup_and_new_location_restore(tmp_path):
    inputs=fixture(tmp_path)
    before={str(p):sha256(p.read_bytes()).hexdigest() for p in inputs}
    out=tmp_path/"derived"
    cmd=[sys.executable,str(SCRIPT),"--staged-manifest",str(inputs[0]),
         "--issuer-lineage",str(inputs[1]),"--exchange-roster",str(inputs[2]),
         "--decision-at",DECISION,"--out",str(out)]
    done=subprocess.run(cmd,capture_output=True,text=True)
    assert done.returncode==0,done.stderr
    report=json.loads(done.stdout)
    assert report["status"]==MATCH
    file=out/"exchange_roster_coverage_research.json"
    assert json.loads(file.read_text())==report
    assert "CORP00001234" not in file.read_text()
    assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in inputs}
    archive=tmp_path/"backup"/"roster.zip"
    assert create_backup(out,archive)["file_count"]==1
    assert verify_backup(archive)["file_count"]==1
    restored=tmp_path/"restored"
    assert restore_backup(archive,restored)["status"]=="LOCAL_BACKUP_RESTORED"
    assert (restored/file.name).read_bytes()==file.read_bytes()


def test_cli_corrupt_roster_never_writes_success_report(tmp_path):
    inputs=fixture(tmp_path)
    mutate(inputs[2],lambda d:d["security_classes"][0].update(
        {"security_id":"KR:TICKER:FAKE"}))
    out=tmp_path/"out"
    run=subprocess.run([sys.executable,str(SCRIPT),
        "--staged-manifest",str(inputs[0]),
        "--issuer-lineage",str(inputs[1]),
        "--exchange-roster",str(inputs[2]),
        "--decision-at",DECISION,"--out",str(out)],capture_output=True,text=True)
    assert run.returncode==2
    assert not out.exists()


def test_clock_future_decision_is_refused(tmp_path):
    inputs=fixture(tmp_path)
    with pytest.raises(ValueError,match="Future"):
        audit(inputs,clock=datetime(2026,10,10,tzinfo=timezone.utc))


def test_forward_dated_market_roster_cannot_be_published_before_session(tmp_path):
    inputs=fixture(tmp_path,"US")
    # 2026-11-01 America/New_York is a DST transition day. Claimed
    # whole-session roster must NOT have been published in October.
    mutate(inputs[2],lambda d:d.update({"session_day":"2026-11-01"}))
    with pytest.raises(ValueError,match="Future"):
        audit(inputs)
    # The decision is later, so the session now matches; the impossible
    # source vintage must still be rejected before identity comparison.
    with pytest.raises(ValueError,match="published before"):
        audit(inputs,decision="2026-11-01T22:00:00-05:00",
              clock=datetime(2026,11,2,4,tzinfo=timezone.utc))


def test_us_market_local_dst_clock_and_future_listing_exclusion(tmp_path):
    inputs=fixture(tmp_path,"US")
    # The local time changes from -04 to -05 on Nov 1, but as-of is
    # decided by the exchange-local calendar day, not UTC midnight.
    mutate(inputs[2],lambda d:d.update({
        "session_day":"2026-11-01",
        "published_at":"2026-11-01T15:00:00-05:00",
        "retrieved_at":"2026-11-01T15:10:00-05:00",
    }))
    report=audit(inputs,decision="2026-11-01T16:00:00-05:00",
                 clock=datetime(2026,11,2,4,tzinfo=timezone.utc))
    assert report["status"]==MATCH
    assert report["declared_exchange_session_day"]=="2026-11-01"
    assert report["historical_exchange_universe_pit_certified"] is False


def test_known_terminal_exit_invalidates_pair_even_if_roster_still_lists_class(tmp_path):
    from test_provider_export_normalizer import revise_stream
    inputs=fixture(tmp_path)
    def add_event(rows):
        rows.append({
            "corp_code":"00001234","issue_uid":"ISSUE_A",
            "source_document_id":"TERMINAL_EXIT",
            "revision":1,"published_at":"2026-09-30T10:00:00+09:00",
            "event_uid":"DELIST_ACTION","action_type":"delist",
            "effective_on":"2026-10-01",
        })
    revise_stream(inputs[0],"actions",add_event)
    result=audit(inputs)
    assert result["status"]==BLOCKED
    assert result["blocker_counts"]["PAIR_STAGED_TERMINAL_EXIT_CONFLICT"]>=1
    assert result["locally_matched_full_scope_classes"]==0
