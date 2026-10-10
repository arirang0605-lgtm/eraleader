"""2_2/2_5: separate declared calendar catches missing or contradictory close sessions."""
from copy import deepcopy
import json

import pytest

from eraleader.cli import main
from eraleader.session_calendar_crosscheck import corroborate_declared_closes

CLOCK = {
    "schema_version": "eraleader.session_close_manifest.v1", "market": "US",
    "source_id": "SYN-CLOCK", "publisher_id_claimed": "UNVERIFIED",
    "published_at": "2024-03-01T10:00:00Z",
    "retrieved_at": "2024-03-01T10:10:00Z",
    "sessions": [
        {"session": day, "close_at": day + "T16:00:00-04:00"}
        for day in ("2024-03-11", "2024-03-12")
    ],
}
CAL = {
    "schema_version": "eraleader.exchange_calendar_reference.v1", "market": "US",
    "source_id": "SYN-CALENDAR", "publisher_id_claimed": "UNVERIFIED",
    "retrieved_at": "2024-03-01T11:00:00Z",
    "asserted_complete": True,
    "coverage_start": "2024-03-11", "coverage_end": "2024-03-12",
    "trading_sessions": ["2024-03-11", "2024-03-12"], "closed_sessions": [],
    "trading_session_closes": {
        day: day + "T16:00:00-04:00"
        for day in ("2024-03-11", "2024-03-12")
    },
}
SIGNAL = "2024-03-11T20:30:00Z"
EVAL = "2024-03-12T21:00:00Z"
BARS = [
    {"security_id": "SYN-US", "session": day, "close": 100.0 + i,
     "tradable": True, "available_at": day + "T16:05:00-04:00"}
    for i, day in enumerate(CAL["trading_sessions"])
]
INDEX = [
    {"session": row["session"], "index": 100.0 + i,
     "available_at": row["available_at"]}
    for i, row in enumerate(BARS)
]


def verify(calendar=None, clock=None):
    return corroborate_declared_closes(
        CLOCK if clock is None else clock, CAL if calendar is None else calendar,
        market="US", decision_at=SIGNAL, raw_source_id="SYN-RAW",
        reference_source_id="SYN-INDEX")


def test_exact_local_calendar_agreement_is_still_not_independently_verified():
    got = verify()
    assert got["matched_sessions"] == 2
    assert len(got["calendar_manifest_sha256"]) == 64
    assert got["historic_pit_certified"] is False
    assert got["independent_calendar_verified"] is False


@pytest.mark.parametrize("edit,reason", [
    (lambda c: c.update(source_id="SYN-CLOCK"), "distinct"),
    (lambda c: c.update(source_id="SYN-RAW"), "distinct"),
    (lambda c: c.update(market="KR"), "market"),
    (lambda c: c.update(retrieved_at="2024-03-12T22:00:00Z"), "after decision"),
    (lambda c: c.update(asserted_complete=False), "Complete calendar"),
    (lambda c: c["trading_sessions"].append("2024-03-12"), "duplicate"),
    (lambda c: c["trading_session_closes"].pop("2024-03-12"), "cover"),
    (lambda c: c["trading_session_closes"].update({"2024-03-12": "2024-03-12T15:00:00-04:00"}), "disagreement"),
    (lambda c: c["trading_session_closes"].update({"2024-03-12": "2024-03-13T04:05:00Z"}), "wrong exchange-local"),
    (lambda c: c["closed_sessions"].append("2024-03-11"), "conflict"),
    (lambda c: c["trading_sessions"].remove("2024-03-12"), "cover"),
])
def test_bad_calendar_contract_fails_closed(edit, reason):
    calendar = deepcopy(CAL)
    edit(calendar)
    with pytest.raises(ValueError, match=reason):
        verify(calendar)


def test_added_calendar_open_session_detects_missing_reference_index_day():
    calendar = deepcopy(CAL)
    calendar["coverage_end"] = "2024-03-13"
    calendar["trading_sessions"].insert(1, "2024-03-12")
    calendar["trading_sessions"].pop()
    calendar["trading_sessions"].append("2024-03-13")
    calendar["trading_session_closes"]["2024-03-13"] = "2024-03-13T16:00:00-04:00"
    # The existing two-day clock is missing the declared 03/13 end, outside its envelope:
    # this is allowed because the audit only claims the observed window.
    assert verify(calendar)["matched_sessions"] == 2
    clock = deepcopy(CLOCK)
    clock["sessions"][-1]["session"] = "2024-03-13"
    clock["sessions"][-1]["close_at"] = "2024-03-13T16:00:00-04:00"
    calendar["trading_sessions"] = ["2024-03-11", "2024-03-12", "2024-03-13"]
    calendar["trading_session_closes"]["2024-03-12"] = "2024-03-12T16:00:00-04:00"
    with pytest.raises(ValueError, match="Missing open exchange session"):
        verify(calendar, clock)


def test_us_early_close_matches_only_when_both_separate_inputs_agree():
    clock, cal = deepcopy(CLOCK), deepcopy(CAL)
    clock["sessions"][1]["close_at"] = "2024-03-12T13:00:00-04:00"
    cal["trading_session_closes"]["2024-03-12"] = "2024-03-12T13:00:00-04:00"
    assert verify(cal, clock)["matched_sessions"] == 2


def test_cli_opt_in_corroboration_and_holiday_reject_before_publish(tmp_path):
    raw = {"schema_version": "total_return_crosscheck_v1",
           "provenance": "synthetic_fixture", "price_basis": "raw_unadjusted",
           "raw_source_id": "SYN-RAW", "bars": BARS, "actions": [],
           "reference": {"source_id": "SYN-INDEX", "basis": "total_return_reinvested_index", "bars": INDEX}}
    paths = [tmp_path / name for name in ("raw.json", "clock.json", "calendar.json")]
    for path, value in zip(paths, (raw, CLOCK, CAL)):
        path.write_text(json.dumps(value))
    output = tmp_path / "out"
    args = ["audit-total-return", "--file", str(paths[0]), "--session-clock", str(paths[1]),
            "--exchange-calendar", str(paths[2]), "--security-id", "SYN-US", "--market", "US",
            "--decision-at", SIGNAL, "--evaluated-at", EVAL, "--out", str(output)]
    main(args)
    result_path = output / "total_return_crosscheck_research.json"
    result = json.loads(result_path.read_text())
    assert result["declared_calendar_corroboration_audit"]["matched_sessions"] == 2
    assert result["historic_price_actions_pit_certified"] is False
    result_path.unlink()
    bad = deepcopy(CAL)
    bad["closed_sessions"] = ["2024-03-12"]
    paths[2].write_text(json.dumps(bad))
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert not result_path.exists()


def test_cli_calendar_requires_clock(tmp_path, capsys):
    bundle = {"schema_version": "total_return_crosscheck_v1",
              "provenance": "synthetic_fixture", "price_basis": "raw_unadjusted",
              "raw_source_id": "SYN-RAW", "bars": BARS, "actions": [],
              "reference": {"source_id": "SYN-INDEX", "bars": INDEX}}
    path = tmp_path / "valid_input.json"
    path.write_text(json.dumps(bundle))
    with pytest.raises(SystemExit) as error:
        main(["audit-total-return", "--file", str(path), "--security-id", "SYN-US",
              "--market", "US", "--decision-at", SIGNAL, "--evaluated-at", EVAL,
              "--exchange-calendar", str(tmp_path / "calendar.json"), "--out", str(tmp_path)])
    assert error.value.code == 2
    assert "--exchange-calendar requires --session-clock" in capsys.readouterr().err
    assert not (tmp_path / "total_return_crosscheck_research.json").exists()
