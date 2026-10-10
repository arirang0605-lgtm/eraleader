"""Isolated synthetic issuer-identity audit; NOT a historical listing proof."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pytest
from eraleader.issuer_lineage import audit_issuer_lineage, SCHEMA
from eraleader.cli import main

AT = "2024-06-01T17:00:00+09:00"


def base():
    def ident(id_, sec, ticker, start, end=None, known="2024-02-01T10:00:00+09:00"):
        return {"record_id":id_,"security_id":sec,"ticker":ticker,
                "market":"KR","source_id":"SYN-SUPPLIER",
                "valid_from":start,"valid_to":end,
                "known_at":known,"revision":1}
    def event(id_, sec, typ, successor=None):
        e={"event_id":id_,"security_id":sec,"action_type":typ,
           "source_id":"SYN-SUPPLIER",
           "effective_on":"2024-06-10",
           "known_at":"2024-05-10T12:00:00+09:00"}
        if successor is not None:
            e["successor_security_id"]=successor
        return e
    return {
        "schema_version":SCHEMA,
        "market":"KR","source_id":"SYN-SUPPLIER",
        "publisher_id_claimed":"UNVERIFIED_RESEARCH_ONLY",
        "retrieved_at":"2024-05-25T12:00:00+09:00",
        "identities":[
            ident("ROW-A","PERM-A","AAA","2024-01-01","2024-05-01"),
            ident("ROW-B","PERM-B","AAA","2024-05-02",None,
                  "2024-04-20T10:00:00+09:00"),
            ident("ROW-C","PERM-C","CCC","2024-02-01")
        ],
        "events":[event("MISSING-SUCC","PERM-B","merger","UNKNOWN-PERM"),
                  event("UNMATCHED-PARENT","UNKNOWN-PERM","split"),
                  event("CASH-UNPRICED","PERM-B","cash_delist")],
        "observed_tickers":["AAA","CCC","MISSING"]
    }


def write(tmp_path, data=None):
    f=tmp_path/"identity.json"
    f.write_text(json.dumps(data if data is not None else base()),
                 encoding="utf-8")
    return f


def audit(tmp_path,data=None,at=AT):
    return audit_issuer_lineage(write(tmp_path,data),decision_at=at)


def test_legitimate_sequential_ticker_reuse_does_not_join_issuers(tmp_path):
    result=audit(tmp_path)
    assert result["declared_historical_ticker_reuse_count"]==1
    assert result["active_ticker_conflict_count"]==0
    assert result["claimed_asof_active_identity_count"]==2
    assert result["claimed_distinct_active_permanent_ids"]==2
    assert result["observed_tickers_unmatched_count"]==1
    assert result["observed_tickers_unmatched_sample"]==["MISSING"]
    assert result["corporate_events_with_unknown_parent_count"]==1
    assert result["corporate_events_with_missing_successor_count"]==1
    assert result["cash_exit_events_without_verified_proceeds_count"]==1
    assert result["historic_membership_pit_certified"] is False
    assert result["independently_usable_asof_identity_count"]==0


def test_concurrent_same_ticker_different_issuers_is_flagged(tmp_path):
    data=base()
    data["identities"][0]["valid_to"]=None
    result=audit(tmp_path,data)
    assert result["active_ticker_conflict_sample"]==["AAA"]
    assert result["active_ticker_conflict_count"]==1
    assert result["observed_tickers_ambiguous_count"]==1


def test_retrospective_source_never_claims_usable_historical_membership(tmp_path):
    data=base()
    data["retrieved_at"]="2026-10-10T16:00:00+09:00"
    out=audit(tmp_path,data)
    assert out["retrospective_retrieval"] is True
    assert out["claimed_asof_active_identity_count"]==0
    assert out["independently_usable_asof_identity_count"]==0
    assert out["status"]=="RESEARCH_RETROSPECTIVE_IDENTITY_NOT_PIT"
    assert out["historic_membership_pit_certified"] is False


def test_early_correction_only_visible_when_known_asof(tmp_path):
    data=base()
    revised=deepcopy(data["identities"][1])
    revised["revision"]=2
    revised["ticker"]="BBB"
    revised["known_at"]="2024-05-20T12:00:00+09:00"
    data["identities"].append(revised)
    out=audit(tmp_path,data)
    assert out["identity_row_count"]==4
    assert out["identity_record_count"]==3
    assert out["observed_tickers_unmatched_count"]==2
    assert out["active_ticker_conflict_count"]==0


def test_post_asof_revision_not_credited_even_if_retrieved_later(tmp_path):
    data=base()
    data["retrieved_at"]="2024-07-01T12:00:00+09:00"
    revised=deepcopy(data["identities"][1])
    revised["revision"]=2
    revised["ticker"]="BBB"
    revised["known_at"]="2024-06-20T12:00:00+09:00"
    data["identities"].append(revised)
    out=audit(tmp_path,data)
    assert out["identity_revision_after_decision_count"]==1
    assert out["claimed_asof_active_identity_count"]==0


@pytest.mark.parametrize("mutate,pattern", [
    (lambda data:data["identities"][0].update(security_id=""),"security_id"),
    (lambda data:data["identities"][0].update(source_id="OTHER"),"cross-source"),
    (lambda data:data["identities"][0].update(market="US"),"Cross-market"),
    (lambda data:data["identities"][0].update(revision=True),"positive integer"),
    (lambda data:data["identities"][0].update(valid_to="2023-12-31"),"after valid_from"),
    (lambda data:data["identities"][0].update(known_at="2024-01-01T10:00:00"),"Timezone"),
    (lambda data:data["identities"][0].update(known_at="2024-08-01T10:00:00+09:00"),"after declared retrieval"),
    (lambda data:data["events"][0].update(action_type="spin_off"),"Unsupported"),
    (lambda data:data["events"][0].update(known_at="2024-09-01T12:00:00+09:00"),"after source retrieval"),
    (lambda data:data["observed_tickers"].append("AAA"),"Duplicate observed ticker"),
    (lambda data:data.update(market="XX"),"KR or US"),
])
def test_invalid_contract_fails_closed(tmp_path,mutate,pattern):
    data=base()
    mutate(data)
    with pytest.raises(ValueError,match=pattern):
        audit(tmp_path,data)


def test_revision_cannot_change_permanent_owner(tmp_path):
    data=base()
    revised=deepcopy(data["identities"][0])
    revised["revision"]=2
    revised["security_id"]="PERM-MIGRATED"
    data["identities"].append(revised)
    with pytest.raises(ValueError,match="switched permanent"):
        audit(tmp_path,data)


def test_revision_known_timestamp_must_not_go_backwards(tmp_path):
    data=base()
    revised=deepcopy(data["identities"][1])
    revised["revision"]=2
    revised["known_at"]="2024-03-01T10:00:00+09:00"
    data["identities"].append(revised)
    with pytest.raises(ValueError,match="chronology reversed"):
        audit(tmp_path,data)


def test_duplicate_record_revision_and_event_refused(tmp_path):
    data=base()
    data["identities"].append(deepcopy(data["identities"][1]))
    with pytest.raises(ValueError,match="Duplicate identity revision"):
        audit(tmp_path,data)
    data=base()
    data["events"].append(deepcopy(data["events"][0]))
    with pytest.raises(ValueError,match="Duplicate corporate event"):
        audit(tmp_path,data)


def test_cli_does_not_invent_certified_permanent_identity(tmp_path,capsys):
    path=write(tmp_path)
    main(["audit-issuer-lineage","--file",str(path),
          "--decision-at",AT,"--out",str(tmp_path/"derived")])
    printed=json.loads(capsys.readouterr().out)
    result=json.loads(Path(printed["path"]).read_text())
    assert result["registry_sha256"]==sha256(path.read_bytes()).hexdigest()
    assert result["permanent_identity_independently_verified"] is False
    assert result["cash_exit_events_without_verified_proceeds_count"]==1
    assert printed["historic_membership_pit_certified"] is False


def test_sample_limit_invalid_type_or_range(tmp_path):
    for value in (True,0,101,1.5):
        with pytest.raises(ValueError,match="sample_limit"):
            audit_issuer_lineage(write(tmp_path),decision_at=AT,sample_limit=value)


def test_us_market_cutoff_day_uses_new_york_not_utc(tmp_path):
    data=base()
    data["market"]="US"
    data["retrieved_at"]="2024-05-31T19:00:00-04:00"
    for row in data["identities"]:
        row["market"]="US"
    # June 1 02:00 UTC is May 31 22:00 in New York. A new security
    # valid only from June 1 must not be included on May 31 local.
    data["identities"].append({
        "record_id":"US-NEW","security_id":"US-NEW","ticker":"NEW",
        "market":"US","source_id":"SYN-SUPPLIER","valid_from":"2024-06-01",
        "valid_to":None,"known_at":"2024-05-31T13:00:00-04:00","revision":1})
    result=audit(tmp_path,data,at="2024-06-01T02:00:00+00:00")
    assert result["claimed_asof_active_identity_count"]==2
    assert result["historic_membership_pit_certified"] is False


def test_first_known_revision_does_not_change_older_decision(tmp_path):
    data=base()
    data["retrieved_at"]="2024-07-01T09:00:00+09:00"
    data["identities"][1]["known_at"]="2024-06-10T10:00:00+09:00"
    out=audit(tmp_path,data,at=AT)
    assert out["claimed_asof_active_identity_count"]==0
    assert out["identity_revision_after_decision_count"]==1


def test_future_planned_ticker_reuse_not_counted_as_historical(tmp_path):
    data=base()
    data["identities"][1]["valid_from"]="2024-08-01"
    out=audit(tmp_path,data)
    assert out["declared_historical_ticker_reuse_count"]==0
    assert out["claimed_asof_active_identity_count"]==1
    assert out["observed_tickers_unmatched_count"]==2


def test_known_effective_delisting_excludes_open_ended_issuer(tmp_path):
    data=base()
    data["events"].append({
        "event_id":"EXPIRED-B","security_id":"PERM-B","action_type":"delist",
        "source_id":"SYN-SUPPLIER","effective_on":"2024-05-22",
        "known_at":"2024-05-10T12:00:00+09:00"})
    out=audit(tmp_path,data)
    assert out["declared_effective_exited_permanent_id_count"]==1
    assert out["claimed_asof_active_identity_count"]==1
    assert out["observed_tickers_unmatched_count"]==2
    assert out["cash_exit_events_without_verified_proceeds_count"]==2
    assert out["delisting_settlement_verified"] is False


def test_announced_merger_not_effective_until_its_local_market_date(tmp_path):
    data=base()
    event=data["events"][0]
    event["successor_security_id"]="PERM-C"
    event["effective_on"]="2024-06-02"
    before=audit(tmp_path,data)
    assert before["claimed_asof_active_identity_count"]==2
    assert before["declared_effective_exited_permanent_id_count"]==0
    event["effective_on"]="2024-06-01"
    after=audit(tmp_path,data)
    assert after["declared_effective_exited_permanent_id_count"]==1
    assert after["claimed_asof_active_identity_count"]==1
    assert after["corporate_events_with_missing_successor_count"]==0
