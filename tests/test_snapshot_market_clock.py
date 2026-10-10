"""2_3 PIT regression: exchange-local date must not follow caller's offset.

These cases use only synthetic records; they do not establish authentic
historical exchange listings, corporate actions, or investment results.
"""
from __future__ import annotations

import pytest

from eraleader.offline_pit import OfflineLedger


def _member(sec: str, market: str, begins: str) -> dict:
    return {
        "security_id": sec, "ticker": sec, "industry_id": "SYNTH",
        "market": market, "valid_from": begins, "valid_to": None,
        "known_at": "2026-04-28T00:00:00Z",
        "source_id": "synthetic-exchange-date", "revision": 1,
    }


def _delist(sec: str, day: str) -> dict:
    return {
        "security_id": sec, "action_id": "delist-test",
        "action_type": "delist", "effective_on": day,
        "known_at": "2026-04-29T00:00:00Z",
        "source_id": "synthetic-exchange-date", "revision": 1,
    }


def test_us_future_listing_and_delist_never_leak_from_kst_cutoff(tmp_path):
    ledger = OfflineLedger(tmp_path / "exchange_us.sqlite")
    try:
        ledger.import_rows("membership", [
            _member("EXISTING", "US", "2026-04-01"),
            _member("NEW", "US", "2026-05-01"),
        ], "synthetic_fixture")
        ledger.import_rows("actions", [_delist("EXISTING", "2026-05-01")],
                           "synthetic_fixture")
        # This +09 timestamp is still April 30 during the US trading day.
        early = ledger.snapshot("2026-05-01T00:30:00+09:00", market="US")
        equivalent = ledger.snapshot("2026-04-30T11:30:00-04:00", market="US")
        assert early == equivalent
        assert early["trading_day"] == "2026-04-30"
        assert set(early["members"]) == {"EXISTING"}
        assert early["exit_security_ids"] == []
        assert early["actions"] == []
        assert [r["action_type"] for r in early["announced_future_actions"]] == ["delist"]

        active = ledger.snapshot("2026-05-01T00:01:00-04:00", market="US")
        assert active["trading_day"] == "2026-05-01"
        assert set(active["members"]) == {"NEW"}
        assert active["exit_security_ids"] == ["EXISTING"]
        assert [r["action_type"] for r in active["actions"]] == ["delist"]
    finally:
        ledger.close()


def test_kr_listing_activates_at_seoul_midnight_even_when_input_is_us_offset(tmp_path):
    ledger = OfflineLedger(tmp_path / "exchange_kr.sqlite")
    try:
        ledger.import_rows("membership", [_member("KR-NEW", "KR", "2026-05-02")],
                           "synthetic_fixture")
        before = ledger.snapshot("2026-05-01T23:30:00+09:00", market="KR")
        assert before["trading_day"] == "2026-05-01"
        assert before["members"] == {}
        after = ledger.snapshot("2026-05-01T11:30:00-04:00", market="KR")
        same = ledger.snapshot("2026-05-02T00:30:00+09:00", market="KR")
        assert after == same
        assert after["trading_day"] == "2026-05-02"
        assert set(after["members"]) == {"KR-NEW"}
    finally:
        ledger.close()


@pytest.mark.parametrize("cutoff,exchange_day,present", [
    ("2026-03-08T12:30:00+09:00", "2026-03-07", False),
    ("2026-03-08T15:30:00+09:00", "2026-03-08", True),
])
def test_us_dst_transition_respects_new_york_calendar(tmp_path, cutoff, exchange_day, present):
    ledger = OfflineLedger(tmp_path / "exchange_dst.sqlite")
    try:
        row = _member("DST-NEW", "US", "2026-03-08")
        row["known_at"] = "2026-03-01T00:00:00Z"
        ledger.import_rows("membership", [row], "synthetic_fixture")
        snapshot = ledger.snapshot(cutoff, market="US")
        assert snapshot["trading_day"] == exchange_day
        assert ("DST-NEW" in snapshot["members"]) is present
    finally:
        ledger.close()


def test_snapshot_cutoff_requires_timezone(tmp_path):
    ledger = OfflineLedger(tmp_path / "exchange_naive.sqlite")
    try:
        with pytest.raises(ValueError, match="timezone"):
            ledger.snapshot("2026-05-01T00:30:00", market="US")
    finally:
        ledger.close()
