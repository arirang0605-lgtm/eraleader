"""Synthetic as-of cross-section: never a measured leader forecast."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import pytest
from eraleader.peer_normalization import normalize_growth_peers, normalize_peer_file
from eraleader.cli import main


def fixture(market="KR"):
    cutoff = "2025-04-01T16:00:00+09:00" if market == "KR" else "2025-04-01T16:00:00-04:00"
    age = (date(2025, 4, 1) - date(2024, 12, 31)).days
    companies = []
    for sid, sector, revenue, profit in (
        ("A", "SEMICON", .10, .20), ("B", "SEMICON", .20, .30),
        ("C", "SEMICON", .30, .40), ("D", "ENERGY", .80, .90)):
        companies.append({"security_id": sid, "industry_id": sector, "market": market,
                          "screen_evaluated": True, "fundamental_periods_aligned": True,
                          "latest_revenue_period": "2024-12-31",
                          "financial_period_age_days": {"revenue": age,
                              "operating_income": age, "industry_revenue": age},
                          "revenue_yoy": revenue, "operating_income_yoy": profit})
    return {"schema_version": "offline_research_v1", "market": market,
            "as_of": cutoff, "company_count": len(companies), "companies": companies}


def lookup(report, security_id):
    return next(x for x in report["companies"] if x["security_id"] == security_id)


def test_sector_only_stable_percentiles_and_minimum_peers():
    report = normalize_growth_peers(fixture())
    assert [lookup(report, sid)["mean_peer_percentile"] for sid in ("A", "B", "C")] == [0, 50, 100]
    assert lookup(report, "D")["status"] == "DEFERRED"
    assert lookup(report, "D")["reasons"] == ["INSUFFICIENT_SAME_INDUSTRY_ASOF_PEERS"]
    assert report["normalized_count"] == 3 and report["deferred_count"] == 1
    assert report["official_leader_promotions"] == 0
    assert report["independent_historical_pit_certified"] is False


def test_tied_peers_get_identical_midrank():
    x = fixture()
    for row in x["companies"][:3]:
        row["revenue_yoy"] = .2
        row["operating_income_yoy"] = .3
    r = normalize_growth_peers(x)
    assert {lookup(r, sid)["mean_peer_percentile"] for sid in "ABC"} == {50}


def test_deferred_high_growth_cannot_influence_denominator():
    x = fixture()
    x["companies"][2]["screen_evaluated"] = False
    x["companies"][2]["revenue_yoy"] = 999
    r = normalize_growth_peers(x)
    assert r["normalized_count"] == 0
    assert lookup(r, "C")["status"] == "DEFERRED"
    assert lookup(r, "A")["peer_count"] == 2
    assert lookup(r, "A")["percentiles"] is None


def test_old_or_missing_company_never_assumed_a_weak_signal():
    x = fixture()
    x["companies"][0]["screen_evaluated"] = False
    x["companies"][0]["financial_period_age_days"]["industry_revenue"] = 451
    x["companies"][0]["revenue_yoy"] = None
    r = normalize_growth_peers(x)
    assert "MISSING_OR_STALE_INDUSTRY_REVENUE" in lookup(r, "A")["reasons"]
    assert lookup(r, "A")["mean_peer_percentile"] is None
    assert r["official_leader_promotions"] == 0

@pytest.mark.parametrize("change,reason", [
    (lambda x: x.__setitem__("as_of", "2025-04-01T16:00:00"), "timezone"),
    (lambda x: x["companies"][0].__setitem__("market", "US"), "mixed-market"),
    (lambda x: x["companies"][0].__setitem__("security_id", "B"), "Duplicate"),
    (lambda x: x["companies"][0].__setitem__("latest_revenue_period", "2025-04-02"), "Future"),
    (lambda x: x["companies"][0]["financial_period_age_days"].__setitem__("revenue", 0), "inconsistent"),
    (lambda x: x.__setitem__("company_count", 2), "Incomplete"),
    (lambda x: x["companies"][0].__setitem__("screen_evaluated", None), "quality gate"),
])
def test_malformed_pit_identity_time_or_quality_fails_closed(change, reason):
    x = fixture()
    change(x)
    with pytest.raises(ValueError, match=reason):
        normalize_growth_peers(x)


def test_us_and_kr_separate_market_snapshots():
    us = normalize_growth_peers(fixture("US"))
    assert us["market"] == "US" and us["normalized_count"] == 3
    assert us["as_of"].endswith("+00:00")


def test_all_nan_missing_factors_defer_without_contamination():
    x = fixture()
    x["companies"][0]["operating_income_yoy"] = float("nan")
    assert normalize_growth_peers(x)["normalized_count"] == 0


@pytest.mark.parametrize("min_peers", [0, 2, 101, True, 3.0])
def test_invalid_min_peers_rejected(min_peers):
    with pytest.raises(ValueError, match="min_peers"):
        normalize_growth_peers(fixture(), min_peers=min_peers)


def test_file_derivation_is_exclusive_and_preserves_source(tmp_path):
    source = tmp_path / "source.json"
    target = tmp_path / "derived.json"
    raw = json.dumps(fixture(), sort_keys=True).encode()
    source.write_bytes(raw)
    receipt = normalize_peer_file(source, target)
    assert receipt["normalized"] == 3
    assert receipt["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert source.read_bytes() == raw
    assert json.loads(target.read_text())["official_leader_promotions"] == 0
    with pytest.raises(FileExistsError):
        normalize_peer_file(source, target)
    with pytest.raises(ValueError, match="overwrite"):
        normalize_peer_file(source, source)


def test_cli_research_runs_with_no_api_or_market_feed(tmp_path, capsys):
    source = tmp_path / "pit_features.json"
    target = tmp_path / "sector_peers.json"
    source.write_text(json.dumps(fixture()))
    main(["audit-peer-normalization", "--input", str(source), "--out", str(target)])
    output = json.loads(capsys.readouterr().out)
    assert output["normalized"] == 3
    assert output["future_leader_skill_certified"] is False
    assert target.exists()
