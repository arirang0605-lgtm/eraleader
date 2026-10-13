"""ER-NC-06 PIT event→market and anomaly→news-query regression tests."""
import copy
import hashlib
import json

import pytest

from eraleader.news_catalyst_adapter import NewsCatalystEvents, record_sha256
from eraleader.news_market_response import (
    LocalAnomalyQueryCache,
    diagnose_news_market_response,
    make_anomaly_news_query,
)

T0 = "2026-10-12T08:00:00Z"
T1 = "2026-10-12T08:10:00Z"
PRICE = "2026-10-12T08:30:00Z"
ASOF = "2026-10-12T09:00:00Z"


def news(*, status="VERIFIED", state="CONFIRMED", novelty="NEW",
         event_type="NEW_CONTRACT", available=T1, first=T1,
         version=1, issuer="ISSUER.A"):
    row = {
        "schema_version": "1.0.0",
        "export_id": "fixture_er_nc06",
        "event_id": "verified.event.1",
        "event_version": version,
        "event_type": event_type,
        "published_at": T0,
        "first_seen_at": first,
        "available_at": available,
        "verification_status": status,
        "novelty": novelty,
        "catalyst_state": state,
        "evidence_ids": ["evidence.source.sha"],
        "source_refs": [{"url": "https://example.org/fact", "source_id": "source"}],
        "related_issuer_ids": [issuer],
        "beneficiary_candidates": [],
        "theme_hints": ["AI.DATA_CENTER"],
        "model_version": "fixture1",
        "extractor_version": "fixture1",
        "data_cutoff": available,
        "license_profile": {
            "research_allowed": True,
            "derived_storage_allowed": True,
            "redistribution_allowed": False,
        },
        "quality_flags": [],
    }
    if version > 1:
        row["revised_at"] = first
    row["record_sha256"] = record_sha256(row)
    return row


def feed(*events, as_of=ASOF):
    collection = NewsCatalystEvents(
        list(events), source_sha256="a" * 64, source_name="synthetic.jsonl"
    )
    return collection.snapshot(as_of)


def diagnose(snapshot, *, excess=4.0, turnover=1.5, **overrides):
    arguments = {
        "security_id": "SHARE.A",
        "issuer_id": "ISSUER.A",
        "issuer_mapping_available_at": T0,
        "as_of": ASOF,
        "market_session": "2026-10-12",
        "market_data_available_at": PRICE,
        "news_snapshot": snapshot,
        "excess_return_pct": excess,
        "turnover_multiple": turnover,
    }
    arguments.update(overrides)
    return diagnose_news_market_response(**arguments)


def test_verified_catalyst_then_positive_excess_price_is_explanation_only():
    result = diagnose(feed(news()), excess=4.5)
    assert result["diagnosis"] == "positive_news_positive_price"
    assert result["research_only"] is True
    assert result["official_leaders"] == 0
    assert result["recommendation"] is None
    assert result["event_evidence_ids"] == ["verified.event.1"]


def test_positive_catalyst_negative_price_is_risk_diagnostic_not_exit_order():
    result = diagnose(feed(news()), excess=-7)
    assert result["diagnosis"] == "positive_news_negative_price"
    assert result["recommendation"] is None


def test_repeated_material_does_not_look_new():
    result = diagnose(feed(news(novelty="REPEATED")))
    assert result["diagnosis"] == "repeated_news"


def test_invalidated_later_revision_must_not_leave_positive_catalyst():
    old = news()
    invalid = news(
        status="INVALIDATED", state="INVALIDATED", version=2,
        first="2026-10-12T08:20:00Z", available="2026-10-12T08:25:00Z",
    )
    result = diagnose(feed(old, invalid))
    assert result["diagnosis"] == "stale_or_unknown"
    assert "MATERIAL_FACT_INVALIDATED" in " ".join(result["reason_codes"])


def test_correction_after_market_observation_cannot_rewrite_earlier_candle():
    old = news()
    correction = news(
        status="INVALIDATED", state="INVALIDATED", version=2,
        first="2026-10-12T08:35:00Z", available="2026-10-12T08:40:00Z",
    )
    before = diagnose(feed(old, correction, as_of=PRICE))
    after = diagnose(feed(old, correction))
    assert before["diagnosis"] == "positive_news_positive_price"
    assert "verified.event.1" in before["event_evidence_ids"]
    assert after["diagnosis"] == "stale_or_unknown"
    assert "NEWS_FIRST_SEEN_AFTER_PRICE_OBSERVATION" in after["reason_codes"]


def test_news_first_received_after_candle_is_not_causal():
    late = news(first="2026-10-12T08:35:00Z",
                available="2026-10-12T08:40:00Z")
    result = diagnose(feed(late))
    assert result["diagnosis"] == "stale_or_unknown"
    assert "NEWS_FIRST_SEEN_AFTER_PRICE_OBSERVATION" in result["reason_codes"]


def test_future_news_vintage_refused():
    future = feed(news())
    future["as_of"] = "2026-10-13T00:00:00Z"
    with pytest.raises(ValueError, match="Future news vintage"):
        diagnose(future)


def test_future_price_availability_refused():
    with pytest.raises(ValueError, match="Future market"):
        diagnose(feed(news()), market_data_available_at="2026-10-14T00:00:00Z")


def test_missing_issuer_mapping_never_promotes_news_to_company_claim():
    out = diagnose(feed(news()), issuer_id=None)
    assert out["diagnosis"] == "stale_or_unknown"
    assert "ISSUER_SECURITY_MAPPING_REQUIRED" in out["reason_codes"]


def test_issuer_mapping_learned_after_price_is_not_backfilled():
    out = diagnose(
        feed(news()), issuer_mapping_available_at="2026-10-12T08:45:00Z"
    )
    assert out["diagnosis"] == "stale_or_unknown"
    assert "ISSUER_SECURITY_MAPPING_NOT_KNOWN_AT_PRICE" in out["reason_codes"]


def test_unrelated_issuer_does_not_benefit_from_same_security_ticker():
    out = diagnose(feed(news(issuer="ISSUER.OTHER")))
    assert out["diagnosis"] == "stale_or_unknown"
    assert "NO_VERIFIED_NEWS" in " ".join(out["reason_codes"])


def test_potential_beneficiary_does_not_become_confirmed_positive_cause():
    ev = news(issuer="ISSUER.OTHER")
    ev["beneficiary_candidates"] = [{
        "issuer_id": "ISSUER.A",
        "relation": "POTENTIAL",
        "first_known_at": T1,
        "evidence_ids": [],
    }]
    ev["record_sha256"] = record_sha256(ev)
    out = diagnose(feed(ev))
    assert out["diagnosis"] == "stale_or_unknown"


def test_unverified_event_never_becomes_positive_cause():
    event = news(status="OBSERVED_UNVERIFIED", state="UNKNOWN")
    out = diagnose(feed(event))
    assert out["diagnosis"] == "stale_or_unknown"


def test_revision_pending_before_verification_stops_positive_assertion():
    old = news()
    pending = news(
        version=2, first="2026-10-12T08:20:00Z",
        available="2026-10-12T09:20:00Z",
        status="OBSERVED_UNVERIFIED", state="UNKNOWN",
    )
    out = diagnose(feed(old, pending))
    assert out["diagnosis"] == "stale_or_unknown"
    assert "NEWS_REVISION_PENDING" in out["reason_codes"]


def test_no_verified_news_cannot_claim_news_absence_without_coverage():
    out = diagnose(feed(), excess=12.0, turnover=3.0)
    assert out["diagnosis"] == "stale_or_unknown"
    assert "PRICE_ANOMALY_NEWS_COVERAGE_INSUFFICIENT" in out["reason_codes"]


def test_asserted_coverage_without_signed_witness_is_not_enough():
    snap = feed()
    snap["coverage_status"] = "COMPLETE_VERIFIED_AS_OF"
    out = diagnose(snap, excess=10)
    assert out["diagnosis"] == "stale_or_unknown"


def test_attested_local_coverage_can_research_unexplained_price():
    snap = feed()
    snap.update({
        "coverage_status": "COMPLETE_VERIFIED_AS_OF",
        "coverage_witness_sha256": "a" * 64,
        "coverage_available_at": T0,
    })
    out = diagnose(snap, excess=11.0, trusted_coverage_sha256="a" * 64)
    assert out["diagnosis"] == "strong_price_no_verified_news"
    assert out["research_only"] is True


def test_local_coverage_witness_after_candle_is_not_eligible():
    snap = feed()
    snap.update({
        "coverage_status": "COMPLETE_VERIFIED_AS_OF",
        "coverage_witness_sha256": "a" * 64,
        "coverage_available_at": "2026-10-12T08:45:00Z",
    })
    out = diagnose(snap, excess=11.0)
    assert out["diagnosis"] == "stale_or_unknown"


def test_forged_event_contents_fail_sha_validation():
    snap = feed(news())
    snap["events"][0]["event_type"] = "EARNINGS_BEAT"
    with pytest.raises(ValueError, match="SHA"):
        diagnose(snap)


def test_future_session_refused():
    with pytest.raises(ValueError, match="Future market session"):
        diagnose(feed(news()), market_session="2026-10-14")


def test_non_finite_or_boolean_prices_rejected():
    with pytest.raises(ValueError, match="invalid"):
        diagnose(feed(news()), excess=float("nan"))
    with pytest.raises(ValueError, match="invalid"):
        diagnose(feed(news()), turnover=True)


def test_error_or_outage_news_is_degraded_research_only():
    broken = feed(news())
    broken["quality_status"] = "STALE"
    out = diagnose(broken)
    assert out["diagnosis"] == "stale_or_unknown"
    assert "NEWS_INPUT_DEGRADED" in out["reason_codes"]


def test_history_replay_without_independent_witness_is_not_live():
    historical = NewsCatalystEvents(
        [news()], source_sha256="a" * 64, source_name="synthetic.jsonl"
    ).snapshot(ASOF, mode="HISTORICAL_PUBLIC_REPLAY")
    out = diagnose(historical)
    assert out["diagnosis"] == "stale_or_unknown"


def test_anomaly_query_is_deterministic_and_cannot_call_remote():
    first = make_anomaly_news_query(
        security_id="SHARE.A", theme_id=None, as_of=ASOF,
        anomaly_type="STRONG_EXCESS_RETURN", window_days=5,
    )
    again = make_anomaly_news_query(
        security_id="SHARE.A", theme_id=None, as_of=ASOF,
        anomaly_type="STRONG_EXCESS_RETURN", window_days=5,
    )
    assert first == again and first["remote_search_permitted"] is False
    assert first["read_only"] is True and first["estimated_network_calls"] == 0


def test_idempotent_local_queue_and_caller_mutation_does_not_edit_cache():
    cache = LocalAnomalyQueryCache()
    original = make_anomaly_news_query(
        security_id=None, theme_id="AI.DATA_CENTER", as_of=ASOF,
        anomaly_type="TURNOVER_SPIKE",
    )
    before = copy.deepcopy(original)
    assert cache.request(original)["duplicate"] is False
    original["query"]["as_of"] = "2027-01-01T00:00:00Z"
    assert cache.request(before)["duplicate"] is True
    assert cache.request(before)["queued_unique_count"] == 1
    assert cache.request(before)["remote_api_calls"] == 0


def test_tampered_or_permissioned_query_rejected():
    query = make_anomaly_news_query(
        security_id="SHARE.A", theme_id=None, as_of=ASOF,
        anomaly_type="STRONG_EXCESS_RETURN",
    )
    unauthorized = copy.deepcopy(query)
    unauthorized["remote_search_permitted"] = True
    with pytest.raises(ValueError):
        LocalAnomalyQueryCache().request(unauthorized)
    altered = copy.deepcopy(query)
    altered["query"]["anomaly_type"] = "TURNOVER_SPIKE"
    with pytest.raises(ValueError, match="tampered"):
        LocalAnomalyQueryCache().request(altered)


@pytest.mark.parametrize("invalid", [
    {"security_id": None, "theme_id": None},
    {"security_id": "SHARE.A", "theme_id": "AI.DATA_CENTER"},
    {"security_id": "../secret", "theme_id": None},
])
def test_query_requires_exactly_one_valid_identity(invalid):
    with pytest.raises(ValueError):
        make_anomaly_news_query(
            **invalid, as_of=ASOF, anomaly_type="TURNOVER_SPIKE",
        )


@pytest.mark.parametrize("days", [0, 31, True, 1.4])
def test_query_window_must_be_bounded_calendar_days(days):
    with pytest.raises(ValueError):
        make_anomaly_news_query(
            security_id="SHARE.A", theme_id=None, as_of=ASOF,
            anomaly_type="TURNOVER_SPIKE", window_days=days,
        )


def test_query_malformed_naive_time_rejected():
    with pytest.raises(ValueError):
        make_anomaly_news_query(
            security_id=None, theme_id="AI.DATA_CENTER",
            as_of="2026-10-12T16:00:00", anomaly_type="TURNOVER_SPIKE",
        )


def test_news_observed_before_candle_but_verified_after_is_separate_from_late_news():
    delayed = news(
        first="2026-10-12T08:20:00Z",
        available="2026-10-12T08:40:00Z",
    )
    result = diagnose(feed(delayed))
    assert result["diagnosis"] == "stale_or_unknown"
    assert "NEWS_VERIFICATION_AFTER_PRICE_OBSERVATION" in result["reason_codes"]


def test_mixed_timezones_sort_by_absolute_available_time_not_iso_text():
    early = news(
        novelty="REPEATED",
        first="2026-10-12T18:00:00+09:00",
        available="2026-10-12T18:00:00+09:00",
    )
    later = news(
        first="2026-10-12T09:30:00Z",
        available="2026-10-12T09:30:00Z",
    )
    later["event_id"] = "verified.event.2"
    later["record_sha256"] = record_sha256(later)
    result = diagnose(
        feed(early, later, as_of="2026-10-12T11:00:00Z"),
        as_of="2026-10-12T11:00:00Z",
        market_data_available_at="2026-10-12T10:00:00Z",
    )
    assert result["diagnosis"] == "positive_news_positive_price"
    assert result["event_evidence_ids"][-1] == "verified.event.2"


def test_local_coverage_claim_alone_even_with_sha_cannot_be_trusted():
    snap = feed()
    snap.update({
        "coverage_status": "COMPLETE_VERIFIED_AS_OF",
        "coverage_witness_sha256": "a" * 64,
        "coverage_available_at": T0,
    })
    out = diagnose(snap, excess=12.0)
    assert out["diagnosis"] == "stale_or_unknown"
    assert "PRICE_ANOMALY_NEWS_COVERAGE_INSUFFICIENT" in out["reason_codes"]


def test_mismatched_external_coverage_pin_never_attests_absence():
    snap = feed()
    snap.update({
        "coverage_status": "COMPLETE_VERIFIED_AS_OF",
        "coverage_witness_sha256": "a" * 64,
        "coverage_available_at": T0,
    })
    out = diagnose(snap, excess=12.0, trusted_coverage_sha256="b" * 64)
    assert out["diagnosis"] == "stale_or_unknown"


def test_snapshot_event_count_cannot_claim_empty_with_actual_event():
    snap = feed(news())
    snap["quality_status"] = "NO_VISIBLE_EVENTS"
    with pytest.raises(ValueError, match="event count/status mismatch"):
        diagnose(snap)


def test_snapshot_count_tamper_is_rejected():
    snap = feed(news())
    snap["event_count"] = 0
    with pytest.raises(ValueError, match="event count/status mismatch"):
        diagnose(snap)


def test_event_evidence_status_tamper_is_rejected():
    snap = feed(news())
    snap["events"][0]["evidence_status"] = "INVALIDATED"
    with pytest.raises(ValueError, match="evidence status mismatch"):
        diagnose(snap)


def test_source_data_are_not_mutated_by_anomaly_diagnostic():
    snap = feed(news())
    before = json.dumps(snap, sort_keys=True)
    result = diagnose(snap)
    assert result["recommendation"] is None
    assert json.dumps(snap, sort_keys=True) == before
