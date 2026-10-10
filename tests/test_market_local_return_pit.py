"""Regression: exchange-local session dates, not caller/UTC calendar dates (2_3/2_5)."""
from copy import deepcopy

import pytest

from eraleader.adjusted_crosscheck import compare_total_return_indexes
from eraleader.corporate_returns import reconstruct_total_return

SID = "SYN-US-LOCAL-DATE"
SIGNAL = "2024-03-12T00:30:00Z"   # March 11, 20:30 New York (EDT)
EVALUATED = "2024-03-13T00:30:00Z"  # March 12, 20:30 New York
BARS = [
    {"security_id": SID, "session": "2024-03-11", "close": 100.0,
     "tradable": True, "available_at": "2024-03-11T16:05:00-04:00"},
    {"security_id": SID, "session": "2024-03-12", "close": 101.0,
     "tradable": True, "available_at": "2024-03-12T16:05:00-04:00"},
]


def price_result(bars, *, evaluated_at=EVALUATED):
    return reconstruct_total_return(
        bars, [], decision_at=SIGNAL, evaluated_at=evaluated_at,
        security_id=SID, market="US", price_basis="raw_unadjusted",
    )


def reference_result(reference):
    return compare_total_return_indexes(
        BARS, [], reference, decision_at=SIGNAL, evaluated_at=EVALUATED,
        security_id=SID, market="US", raw_source_id="SYN-RAW",
    )


def valid_reference():
    return {
        "source_id": "SYN-OTHER", "basis": "total_return_reinvested_index",
        "bars": [
            {"session": row["session"], "index": 100.0 + i,
             "available_at": row["available_at"]}
            for i, row in enumerate(BARS)
        ],
    }


def test_utc_midnight_next_day_is_still_previous_new_york_session():
    result = price_result(BARS)
    assert result["start_session"] == "2024-03-11"
    assert result["last_session"] == "2024-03-12"
    assert result["total_return"] == 0.01


def test_future_us_bar_claimed_published_prior_local_day_rejected():
    bars = deepcopy(BARS)
    # UTC date = March 12, but local NY date = March 11 (before session).
    bars[1]["available_at"] = "2024-03-12T00:05:00Z"
    with pytest.raises(ValueError, match="(market session|local session)"):
        price_result(bars)


def test_future_us_bar_cannot_enter_evaluation_cutoff_on_previous_local_day():
    bars = deepcopy(BARS)
    bars[1]["available_at"] = "2024-03-12T00:05:00Z"
    # Evaluation cutoff is March 11, 20:30 NY, not trading day March 12.
    with pytest.raises(ValueError, match="(market session|Future price evidence)"):
        price_result(bars, evaluated_at="2024-03-12T00:30:00Z")


def test_us_reference_index_utc_date_cannot_mask_prior_local_day():
    reference = valid_reference()
    reference["bars"][1]["available_at"] = "2024-03-12T00:05:00Z"
    with pytest.raises(ValueError, match="before its observed session"):
        reference_result(reference)


def test_dst_fall_back_us_reference_is_checked_in_new_york():
    autumn_bars = [
        {"security_id": SID, "session": "2024-11-01", "close": 100.,
         "tradable": True, "available_at": "2024-11-01T16:05:00-04:00"},
        {"security_id": SID, "session": "2024-11-04", "close": 100.,
         "tradable": True, "available_at": "2024-11-04T16:05:00-05:00"},
    ]
    ref = {
        "source_id": "SYN-OTHER", "basis": "total_return_reinvested_index",
        "bars": [
            {"session": "2024-11-01", "index": 100., "available_at": autumn_bars[0]["available_at"]},
            # Nov 4 UTC is still Nov 3 in New York after DST ends.
            {"session": "2024-11-04", "index": 100., "available_at": "2024-11-04T01:30:00Z"},
        ],
    }
    with pytest.raises(ValueError, match="before its observed session"):
        compare_total_return_indexes(
            autumn_bars, [], ref, decision_at="2024-11-01T21:30:00Z",
            evaluated_at="2024-11-04T22:00:00Z",
            security_id=SID, market="US", raw_source_id="SYN-RAW",
        )


def test_valid_kr_utc_timestamps_use_korea_calendar_day():
    bars = [
        {"security_id": "SYN-KR", "session": "2024-04-01", "close": 100.,
         "available_at": "2024-04-01T07:05:00Z", "tradable": True},
        {"security_id": "SYN-KR", "session": "2024-04-02", "close": 100.,
         "available_at": "2024-04-02T07:05:00Z", "tradable": True},
    ]
    result = reconstruct_total_return(
        bars, [], decision_at="2024-04-01T07:30:00Z",
        evaluated_at="2024-04-02T07:30:00Z",
        security_id="SYN-KR", market="KR", price_basis="raw_unadjusted",
    )
    assert result["total_return"] == 0
