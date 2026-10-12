"""ER-NC-01 PIT, rights, revision, first-seen, duplicate & NEWS_OFF tests."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from eraleader.news_catalyst_adapter import (
    NewsCatalystEvents, attach_news_evidence, news_enabled, record_sha256,
)
from eraleader.delivery import render_dashboard


def event(*, version=1, published="2026-10-12T09:10:00+09:00",
          first="2026-10-12T09:12:00+09:00",
          available="2026-10-12T09:14:00+09:00",
          state="CONFIRMED", verified="VERIFIED", issuer="005930"):
    item = {
        "schema_version":"1.0.0", "export_id":"fixture_20261013",
        "event_id":"event.DART.0001", "event_version":version,
        "event_type":"MATERIAL_DISCLOSURE",
        "published_at":published, "first_seen_at":first,
        "available_at":available, "verification_status":verified,
        "novelty":"NEW", "catalyst_state":state,
        "evidence_ids":["sha.darta1"],
        "source_refs":[{"url":"https://example.org/dart/1","source_id":"dart"}],
        "related_issuer_ids":[issuer],
        "beneficiary_candidates":[{
            "issuer_id":issuer,"relation":"DIRECT_VERIFIED",
            "first_known_at":available,"evidence_ids":["sha.darta1"]
        }],
        "theme_hints":["semiconductors"],
        "model_version":"nc-mock-1","extractor_version":"extractor-fixture-1",
        "data_cutoff":available,
        "license_profile":{"research_allowed":True,
                           "derived_storage_allowed":True,
                           "redistribution_allowed":False},
        "quality_flags":[],
    }
    if version>1:
        item["revised_at"]=first
    item["record_sha256"]=record_sha256(item)
    return item


def seal(item):
    item["record_sha256"]=record_sha256(item)
    return item


def write(tmp_path, *events, as_jsonl=True):
    root=tmp_path/("events.jsonl" if as_jsonl else "events.json")
    if as_jsonl:
        root.write_text("\n".join(json.dumps(ev,sort_keys=True) for ev in events)+"\n",
                        encoding="utf-8")
    else:
        root.write_text(json.dumps({"events":list(events)},sort_keys=True),encoding="utf-8")
    return root


def store(tmp_path,*events):
    return NewsCatalystEvents.load(write(tmp_path,*events))


def baseline():
    return {"source_market":"KR","source_market_name":"KR","market_last_observation":"2026-10-08",
            "source_market_days":1,"source_day":"2026-10-08","as_of_requested":"2026-10-13",
            "note":"PRICE_ONLY_RESEARCH", "source":"test","data_source":"synthetic",
            "shown":1,"model_version":"baseline_v1",
            "rows":[{"rank":1,"security_id":"005930","name":"synthetic fixture",
                     "venue":"KRX","price_strength_25":23,
                     "return_6m":0.12,"total_score_100":None,"state":"WATCH"}]}


def test_0911_before_first_seen_invisible(tmp_path):
    s=store(tmp_path,event())
    report=s.snapshot("2026-10-12T09:11:00+09:00")
    assert report["events"]==[] and report["event_count"]==0


def test_0913_observed_but_not_verified_only_placeholder(tmp_path):
    report=store(tmp_path,event()).snapshot("2026-10-12T09:13:00+09:00")
    assert report["events"][0]["verification_status"]=="OBSERVED_UNVERIFIED"
    assert report["events"][0]["related_issuer_ids"]==[]
    assert "record_sha256" not in report["events"][0]
    assert report["observed_unverified_count"]==1


def test_0915_visible_verified_and_linked_watch(tmp_path):
    store_=store(tmp_path,event())
    report=store_.snapshot("2026-10-12T09:15:00+09:00")
    assert report["event_count"]==1
    assert report["events"][0]["evidence_status"]=="VERIFIED_AS_OF"
    assert len(store_.related_events("005930","2026-10-12T09:15:00+09:00"))==1
    watch=attach_news_evidence(baseline(),report,enabled=True)
    assert watch["rows"][0]["news_evidence"][0]["event_id"]=="event.DART.0001"
    assert watch["rows"][0]["rank"]==1 and watch["rows"][0]["state"]=="WATCH"
    assert watch["rows"][0]["total_score_100"] is None


def test_available_at_later_cannot_backfill_published_at(tmp_path):
    e=event(available="2026-10-13T18:00:00+09:00")
    report=store(tmp_path,e).snapshot("2026-10-12T20:00:00+09:00")
    assert report["events"][0]["evidence_status"]=="NOT_YET_AVAILABLE"


def test_revision_previous_positive_unchanged_until_new_available(tmp_path):
    old=event()
    correction=event(version=2,first="2026-10-19T10:00:00+09:00",
                     available="2026-10-19T10:05:00+09:00",
                     state="INVALIDATED",verified="INVALIDATED")
    s=store(tmp_path,old,correction)
    prior=s.snapshot("2026-10-18T16:00:00+09:00")["events"][0]
    pending=s.snapshot("2026-10-19T10:03:00+09:00")["events"][0]
    after=s.snapshot("2026-10-19T10:06:00+09:00")["events"][0]
    assert prior["event_version"]==1 and prior["catalyst_state"]=="CONFIRMED"
    assert pending["event_version"]==1 and "REVISION_PENDING" in pending["quality_flags"]
    assert after["event_version"]==2 and after["catalyst_state"]=="INVALIDATED"
    assert s.snapshot("2026-10-18T16:00:00+09:00")["events"][0]==prior


def test_six_month_later_beneficiary_not_backfilled(tmp_path):
    old=event()
    new=event(version=2,first="2027-04-01T09:00:00+09:00",
              available="2027-04-01T09:15:00+09:00")
    new["related_issuer_ids"]=["005930","123456"]
    new["beneficiary_candidates"].append({"issuer_id":"123456",
            "relation":"DIRECT_VERIFIED",
            "first_known_at":"2027-04-01T09:14:00+09:00",
            "evidence_ids":["independent.evidence"]})
    seal(new)
    s=store(tmp_path,old,new)
    before=s.snapshot("2026-11-01T10:00:00+09:00")["events"][0]
    assert "123456" not in before["related_issuer_ids"]
    assert not s.related_events("123456","2026-11-01T10:00:00+09:00")
    assert s.related_events("123456","2027-04-02T10:00:00+09:00")


def test_late_beneficiary_embedded_in_old_version_blocked(tmp_path):
    e=event()
    e["beneficiary_candidates"][0]["first_known_at"]="2027-04-01T09:10:00+09:00"
    seal(e)
    with pytest.raises(ValueError,match="late-confirmed"):
        store(tmp_path,e)


def test_duplicate_identical_event_version_idempotent(tmp_path):
    e=event()
    s=store(tmp_path,e,e)
    assert s.unique_events==1 and s.snapshot("2026-10-12T09:15:00+09:00")["event_count"]==1


def test_duplicate_version_different_hash_fail_closed(tmp_path):
    e=event(); changed=deepcopy(e)
    changed["novelty"]="REPEATED";seal(changed)
    with pytest.raises(ValueError,match="collision"):
        store(tmp_path,e,changed)


def test_wrong_record_sha_blocks_entire_export(tmp_path):
    e=event();e["record_sha256"]="0"*64
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        store(tmp_path,e)


def test_unsupported_schema_major_fails(tmp_path):
    e=event();e["schema_version"]="2.0.0";seal(e)
    with pytest.raises(ValueError,match="unsupported schema"):
        store(tmp_path,e)


def test_bad_rights_or_unknown_license_fails(tmp_path):
    e=event();e["license_profile"]["research_allowed"]=False;seal(e)
    with pytest.raises(ValueError,match="rights"):
        store(tmp_path,e)


def test_unverified_claimed_catalyst_denied(tmp_path):
    e=event(verified="OBSERVED_UNVERIFIED",state="CONFIRMED")
    with pytest.raises(ValueError,match="unverified material"):
        store(tmp_path,e)


def test_invalidated_version_cannot_claim_confirmed(tmp_path):
    e=event(verified="INVALIDATED",state="CONFIRMED")
    with pytest.raises(ValueError,match="invalidated event"):
        store(tmp_path,e)


def test_unknown_raw_article_body_rejected(tmp_path):
    e=event();e["article_full_text"]="Licensed source data should not be copied here";seal(e)
    with pytest.raises(ValueError,match="unexpected raw article"):
        store(tmp_path,e)


def test_symlink_source_is_rejected(tmp_path):
    origin=write(tmp_path,event())
    symlink=tmp_path/"linked.jsonl";symlink.symlink_to(origin)
    with pytest.raises(ValueError,match="nonlinked"):
        NewsCatalystEvents.load(symlink)


def test_duplicate_json_keys_refused(tmp_path):
    path=tmp_path/"invalid.jsonl"
    path.write_text('{"event_id":"one","event_id":"two"}\n')
    with pytest.raises(ValueError,match="invalid complete JSON"):
        NewsCatalystEvents.load(path)


def test_historical_mode_requires_independent_publication_witness(tmp_path):
    result=store(tmp_path,event()).snapshot("2026-10-12T09:15:00+09:00",
                                            "HISTORICAL_PUBLIC_REPLAY")
    assert result["events"]==[]
    assert result["quality_status"]=="INDEPENDENT_PUBLICATION_WITNESS_REQUIRED"


def test_json_and_jsonl_same_record_count(tmp_path):
    e=event()
    a=store(tmp_path,e)
    path=write(tmp_path,e,as_jsonl=False)
    b=NewsCatalystEvents.load(path)
    assert a.unique_events==b.unique_events==1
    assert a.snapshot("2026-10-12T09:15:00+09:00")["events"]==b.snapshot("2026-10-12T09:15:00+09:00")["events"]


def test_bad_datetime_timezone_rejected(tmp_path):
    e=event();e["first_seen_at"]="2026-10-12T09:12:00";seal(e)
    with pytest.raises(ValueError,match="timezone"):
        store(tmp_path,e)


def test_source_correction_time_order_invalid(tmp_path):
    a=event()
    b=event(version=2,first="2026-10-11T09:00:00+09:00",
            available="2026-10-20T09:05:00+09:00")
    with pytest.raises(ValueError):
        store(tmp_path,a,b)


def test_news_off_noop_preserves_legacy_snapshot_and_html_hash(tmp_path):
    base=baseline()
    content=render_dashboard(base)
    sha=sha256(content.encode()).hexdigest()
    no_news=attach_news_evidence(base,
       store(tmp_path,event()).snapshot("2026-10-12T09:15:00+09:00"),enabled=False)
    assert no_news is base
    assert sha256(render_dashboard(no_news).encode()).hexdigest()==sha
    assert no_news["rows"]==base["rows"]
    assert not news_enabled({"NEWS_ENABLED":"false"})
    assert news_enabled({"NEWS_ENABLED":"true"})


def test_news_error_degrades_only_sidecar_and_not_price_state():
    base=baseline()
    report=attach_news_evidence(base,{"quality_status":"UNAVAILABLE"},enabled=True)
    assert report["news_quality_status"]=="DEGRADED_NEWS_UNAVAILABLE"
    assert report["rows"]==base["rows"] and "news_quality_status" not in base


def test_no_events_does_not_invalidate_old_watch(tmp_path):
    path=tmp_path/"empty.json";path.write_text("[]",encoding="utf-8")
    s=NewsCatalystEvents.load(path)
    report=attach_news_evidence(baseline(),s.snapshot("2026-10-12T10:00:00+09:00"),enabled=True)
    assert report["rows"][0]["state"]=="WATCH"
    assert report["rows"][0]["news_evidence"]==[]


def test_synthetic_fixture_has_correct_sha_and_no_live_eligibility():
    fixture=(Path(__file__).parent/"fixtures"/"news_events"/"verified_research.json").absolute()
    store_=NewsCatalystEvents.load(fixture)
    assert store_.unique_events==1
    asof=store_.snapshot("2026-10-12T09:15:00+09:00")
    assert asof["research_only"] is True
    raw={k:v for k,v in asof["events"][0].items() if k!="evidence_status"}
    assert raw["record_sha256"]==record_sha256(raw)
