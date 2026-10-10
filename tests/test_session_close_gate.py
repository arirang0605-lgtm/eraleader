"""2_3/2_5: fail closed on a declared close clock and premature closing prices."""
from copy import deepcopy
import json
import pytest
from eraleader.session_close_gate import audit_declared_session_close
from eraleader.cli import main

SID = "SYN-US-CLOSE"
SIGNAL = "2024-03-11T20:30:00Z"
EVAL = "2024-03-12T21:00:00Z"
BARS = [
    {"security_id": SID, "session": day, "close": 100. + i, "tradable": True,
     "available_at": day + "T16:05:00-04:00"}
    for i, day in enumerate(("2024-03-11", "2024-03-12"))
]
INDEX = [{"session": row["session"], "index": 100. + i,
          "available_at": row["available_at"]} for i, row in enumerate(BARS)]
CLOCK = {
    "schema_version": "eraleader.session_close_manifest.v1", "market": "US",
    "source_id": "SYN-CALENDAR", "publisher_id_claimed": "SYNTHETIC",
    "published_at": "2024-03-01T10:00:00Z", "retrieved_at": "2024-03-01T10:10:00Z",
    "sessions": [{"session": day, "close_at": day + "T16:00:00-04:00"}
                 for day in ("2024-03-11", "2024-03-12")],
}

def verify(bars=None, index=None, clock=None, **kwargs):
    return audit_declared_session_close(
        BARS if bars is None else bars, INDEX if index is None else index,
        CLOCK if clock is None else clock, market="US", raw_source_id="SYN-RAW",
        reference_source_id="SYN-INDEX", decision_at=SIGNAL,
        evaluated_at=kwargs.get("evaluated_at", EVAL))


def test_us_dst_declared_close_passes_only_as_research():
    result = verify()
    assert result["sessions_checked"] == 2
    assert len(result["declared_clock_sha256"]) == 64
    assert result["historic_pit_certified"] is False
    assert result["independent_exchange_clock_verified"] is False


@pytest.mark.parametrize("kind", ["price", "reference"])
def test_preclose_claimed_available_at_denied(kind):
    prices, indexes = deepcopy(BARS), deepcopy(INDEX)
    records = prices if kind == "price" else indexes
    records[1]["available_at"] = "2024-03-12T09:00:00-04:00"
    with pytest.raises(ValueError, match="before declared session close"):
        verify(prices, indexes)


def test_us_dst_fall_back_clock_is_new_york_local():
    bars, refs, clock = deepcopy(BARS), deepcopy(INDEX), deepcopy(CLOCK)
    bars[1]["session"] = refs[1]["session"] = clock["sessions"][1]["session"] = "2024-11-04"
    bars[1]["available_at"] = refs[1]["available_at"] = "2024-11-04T16:05:00-05:00"
    clock["sessions"][1]["close_at"] = "2024-11-04T16:00:00-05:00"
    assert verify(bars, refs, clock, evaluated_at="2024-11-05T00:00:00Z")["sessions_checked"] == 2


@pytest.mark.parametrize("edit,reason", [
    (lambda c: c["sessions"].pop(), "coverage"),
    (lambda c: c["sessions"].append(c["sessions"][-1]), "Duplicate"),
    (lambda c: c.update(market="KR"), "market"),
    (lambda c: c["sessions"][1].update(close_at="2024-03-13T04:05:00Z"), "market day"),
    (lambda c: c["sessions"][1].update(close_at="2024-03-12T16:00:00"), "timezone"),
    (lambda c: c.update(retrieved_at="2024-03-12T22:00:00Z"), "decision"),
    (lambda c: c.update(published_at="2024-03-05T00:00:00Z",
                        retrieved_at="2024-03-02T00:00:00Z"), "publication"),
    (lambda c: c.update(source_id="SYN-RAW"), "distinct"),
])
def test_malformed_or_retrospective_clock_rejected(edit, reason):
    clock = deepcopy(CLOCK)
    edit(clock)
    with pytest.raises(ValueError, match=reason):
        verify(clock=clock)


def test_kr_utc_clock_matches_seoul_local_day():
    bars, refs, clock = deepcopy(BARS), deepcopy(INDEX), deepcopy(CLOCK)
    clock["market"] = "KR"
    for i in range(2):
        day = f"2024-04-0{i+1}"
        bars[i]["session"] = refs[i]["session"] = clock["sessions"][i]["session"] = day
        bars[i]["available_at"] = refs[i]["available_at"] = day + "T07:05:00Z"
        clock["sessions"][i]["close_at"] = day + "T15:30:00+09:00"
    got = audit_declared_session_close(
        bars, refs, clock, market="KR", raw_source_id="SYN-RAW",
        reference_source_id="SYN-INDEX", decision_at="2024-04-01T07:30:00Z",
        evaluated_at="2024-04-02T07:30:00Z")
    assert got["sessions_checked"] == 2


def test_cli_clock_option_fails_before_publishing_results(tmp_path, capsys):
    bundle = {
        "schema_version": "total_return_crosscheck_v1", "provenance": "synthetic_fixture",
        "price_basis": "raw_unadjusted", "raw_source_id": "SYN-RAW",
        "bars": deepcopy(BARS), "actions": [],
        "reference": {"source_id": "SYN-INDEX", "basis": "total_return_reinvested_index",
                      "bars": deepcopy(INDEX)},
    }
    data_path, clock_path = tmp_path / "bundle.json", tmp_path / "clock.json"
    output = tmp_path / "research"
    data_path.write_text(json.dumps(bundle))
    clock_path.write_text(json.dumps(CLOCK))
    command = ["audit-total-return", "--file", str(data_path),
               "--session-clock", str(clock_path), "--security-id", SID,
               "--market", "US", "--decision-at", SIGNAL,
               "--evaluated-at", EVAL, "--out", str(output)]
    main(command)
    published = output / "total_return_crosscheck_research.json"
    result = json.loads(published.read_text())
    assert result["declared_session_close_audit"]["sessions_checked"] == 2
    assert result["historic_price_actions_pit_certified"] is False
    bundle["reference"]["bars"][1]["available_at"] = "2024-03-12T09:00:00-04:00"
    data_path.write_text(json.dumps(bundle))
    published.unlink()
    with pytest.raises(SystemExit) as error:
        main(command)
    assert error.value.code == 2
    assert not published.exists()
