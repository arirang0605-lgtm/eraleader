"""Real-data evidence coverage is separate from investment priorities/rank.

Synthetic fixtures protect first-received clocks, source PINs and population
coverage; actual official KRX+DART artifact is checked with a separate smoke.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json

import pytest

from eraleader.official_factor_readiness import (
    factor_coverage_from_official_snapshot, render_factor_readiness,
    write_factor_readiness,
)

NOW = "2026-10-12T12:00:00+00:00"
KNOWN = "2026-10-12T11:00:00+00:00"
SESSION = "2026-10-08"


def source():
    return {
        "schema_version": "1.0", "model_version": "price-score-fixture",
        "as_of_requested": "2026-10-12",
        "source_market": "KR", "market_last_observation": SESSION,
        "classification_quality": "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
        "shown": 1, "run_id": "test-unchanged",
        "scoring_policy": "3개월 RS 40% + 6개월 RS 60%, 가격 부분 점수 최대 25점; 임시 연구식",
        "rows": [{
            "rank": 1, "security_id": "A23456",
            "name": "Price leader", "observed_at": SESSION,
            "total_score_100": None, "price_strength_25": 24.5,
            "state": "WATCH",
        }],
        "official_api_evidence": {
            "schema": "eraleader.official_api_pit_research_bridge.v1",
            "decision_at": NOW, "api_observation_day": SESSION,
            "sources": [
                {"source": "krx-kospi", "row_count": 1,
                 "first_receipt_sha256": "a" * 64,
                 "first_local_received_at_utc": KNOWN},
                {"source": "krx-kosdaq", "row_count": 1,
                 "first_receipt_sha256": "b" * 64,
                 "first_local_received_at_utc": KNOWN},
            ],
            "dart_current_directory": {
                "krx_total_observed": 2,
                "matched_unique_dart_corporation": 1,
                "historical_pit_certified": False,
                "first_local_received_at_utc": KNOWN,
            },
            "dart_financial_first_receipts": [
                {"stock_code": "005930", "report_year": 2024,
                 "first_receipt_sha256": "c" * 64,
                 "first_local_received_at_utc": KNOWN, "pit_certified": False},
                {"stock_code": "005930", "report_year": 2025,
                 "first_receipt_sha256": "d" * 64,
                 "first_local_received_at_utc": KNOWN, "pit_certified": False},
            ],
            "dart_financial_comparable_companies": 1,
            "official_leaders": 0,
            "historic_universe_pit_verified": False,
            "issuer_share_class_verified": False,
        },
        "official_financial_research_observations": [{
            "security_id": "005930", "name": "Financial watch company",
            "venue": "KOSPI", "reported_financial_year": 2025,
            "research_metrics": {
                "revenue_yoy": .1088,
                "operating_income_yoy": .3323,
                "net_income_yoy": .3122,
            },
            "source_first_received_at_utc": KNOWN,
            "evidence_sha256": "e" * 64,
            "historic_issuer_class_pit_certified": False,
            "formal_score_100": None, "official_leader": False,
            "rank_in_price_top20": None,
        }],
    }


def test_cfs_company_outside_price_topn_is_visible_without_reranking():
    original = source()
    before = json.dumps(original, sort_keys=True)
    report = factor_coverage_from_official_snapshot(original)
    assert json.dumps(original, sort_keys=True) == before
    assert report["observed_krx_market_rows"] == 2
    assert report["current_dart_mapping_observed"] == 1
    assert report["annual_cfs_comparable_companies"] == 1
    assert report["annual_cfs_in_price_top20"] == 0
    assert report["price_watch_shown"] == 1
    assert report["financial_research"][0]["security_id"] == "005930"
    assert report["financial_research"][0]["revenue_yoy"] == pytest.approx(.1088)
    assert report["financial_research"][0]["price_watch_rank"] is None
    assert report["official_leaders"] == report["valid_full_leader_scores"] == 0
    assert report["investment_priority_ranking_available"] is False
    page = render_factor_readiness(report)
    assert "005930" in page and "+10.88%" in page
    assert "현재 투자 우선순위는 산출하지 않습니다" in page
    assert "공식 역사 PIT 인증 전" in page


def test_same_snapshot_is_deterministic_and_verifiably_sha_sealed():
    first = factor_coverage_from_official_snapshot(source())
    second = factor_coverage_from_official_snapshot(source())
    assert first == second
    assert len(first["content_sha256"]) == 64
    attacked = deepcopy(first)
    attacked["factors"]["industry_growth"]["observed_issues"] = 999
    with pytest.raises(ValueError, match="changed since"):
        render_factor_readiness(attacked)


def test_old_saved_output_recovered_without_inventing_financial_yoy():
    old = source()
    del old["official_financial_research_observations"]
    report = factor_coverage_from_official_snapshot(old)
    assert report["annual_cfs_comparable_companies"] == 1
    assert report["financial_research"][0]["revenue_yoy"] is None
    assert report["financial_research"][0]["name"] is None
    assert "N/A" in render_factor_readiness(report)


def test_no_cfs_cannot_be_displayed_as_zero_growth():
    empty = source()
    empty["official_api_evidence"]["dart_financial_first_receipts"] = []
    empty["official_api_evidence"]["dart_financial_comparable_companies"] = 0
    empty["official_financial_research_observations"] = []
    report = factor_coverage_from_official_snapshot(empty)
    assert report["annual_cfs_comparable_companies"] == 0
    assert report["financial_research"] == []
    assert report["factors"]["earnings"]["observed_issues"] == 0
    assert report["official_leaders"] == 0


def test_html_injection_from_financial_company_name_is_escaped():
    snap = source()
    snap["official_financial_research_observations"][0]["name"] = "<script>alert(99)</script>"
    report = factor_coverage_from_official_snapshot(snap)
    page = render_factor_readiness(report)
    assert "<script>alert(99)</script>" not in page
    assert "&lt;script&gt;" in page


def test_fresh_write_is_readonly_no_overwrite(tmp_path):
    snap = source()
    report = factor_coverage_from_official_snapshot(snap)
    site = tmp_path / "site"
    site.mkdir()
    html, manifest = write_factor_readiness(report, site)
    assert html.is_file() and manifest.is_file()
    assert "Financial watch company" in html.read_text()
    saved = manifest.read_bytes()
    assert json.loads(saved)["content_sha256"] == report["content_sha256"]
    with pytest.raises(FileExistsError):
        write_factor_readiness(report, site)
    assert manifest.read_bytes() == saved


def test_symlinked_site_must_not_be_written(tmp_path):
    site = tmp_path / "site"
    site.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="unlinked"):
        write_factor_readiness(factor_coverage_from_official_snapshot(source()), site)


@pytest.mark.parametrize("which,key,value", [
    ("api", "official_leaders", 1),
    ("api", "historic_universe_pit_verified", True),
    ("api", "issuer_share_class_verified", True),
    ("api", "api_observation_day", "2026-10-13"),
    ("api", "dart_financial_comparable_companies", 3),
    ("row", "total_score_100", 98),
    ("row", "state", "CONFIRMED"),
    ("row", "rank", 2),
    ("row", "observed_at", "2026-10-13"),
    ("row", "price_strength_25", 27.0),
    ("financial", "formal_score_100", 100),
    ("financial", "official_leader", True),
    ("financial", "rank_in_price_top20", 1),
    ("financial", "source_first_received_at_utc", "2026-10-13T13:00:00Z"),
    ("financial", "reported_financial_year", 2028),
    ("financial", "evidence_sha256", "not_a_pin"),
    ("financial", "research_metrics", {"revenue_yoy": float("nan"),
                                         "operating_income_yoy": .3,
                                         "net_income_yoy": .1}),
])
def test_future_or_invented_leader_or_bad_receipt_fails_closed(which, key, value):
    snap = source()
    if which == "api":
        snap["official_api_evidence"][key] = value
    elif which == "row":
        snap["rows"][0][key] = value
    else:
        snap["official_financial_research_observations"][0][key] = value
    with pytest.raises((ValueError, TypeError, OverflowError)):
        factor_coverage_from_official_snapshot(snap)


def test_late_first_source_receipt_rejected():
    snap = source()
    snap["official_api_evidence"]["sources"][0]["first_local_received_at_utc"] = (
        "2026-10-13T12:00:00Z"
    )
    with pytest.raises(ValueError, match="after decision"):
        factor_coverage_from_official_snapshot(snap)


def test_corporate_mapping_mismatch_does_not_silently_claim_coverage():
    snap = source()
    snap["official_api_evidence"]["dart_current_directory"]["krx_total_observed"] = 9
    with pytest.raises(ValueError, match="universe mismatch"):
        factor_coverage_from_official_snapshot(snap)


def test_future_dart_financial_receipt_fails_asof():
    snap = source()
    snap["official_api_evidence"]["dart_financial_first_receipts"][1][
        "first_local_received_at_utc"
    ] = "2026-10-13T12:00:00Z"
    with pytest.raises(ValueError, match="Future first receipt"):
        factor_coverage_from_official_snapshot(snap)


def test_duplicate_price_identity_rejected():
    snap = source()
    second = deepcopy(snap["rows"][0])
    second["rank"] = 2
    snap["rows"].append(second)
    snap["shown"] = 2
    with pytest.raises(ValueError, match="Duplicate"):
        factor_coverage_from_official_snapshot(snap)


def test_duplicate_receipts_or_nonconsecutive_years_cannot_supply_growth():
    snap = source()
    snap["official_api_evidence"]["dart_financial_first_receipts"][0]["report_year"] = 2025
    with pytest.raises(ValueError, match="consecutive CFS"):
        factor_coverage_from_official_snapshot(snap)
