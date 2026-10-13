"""Real-use searchable KR company detail page from existing verified sources."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader import official_company_explorer as exp

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
DAY = "2026-10-14"
CODES = ("005930", "000660", "035420")


def signed(value):
    result = deepcopy(value)
    result["content_sha256"] = sha256(exp.canonical(result)).hexdigest()
    return result


def pair():
    companies = []
    peers = []
    for pos, (code, name, venue, division, sales, price) in enumerate((
        ("005930", "삼성전자", "KOSPI", "26", .24, .20),
        ("000660", "SK하이닉스", "KOSPI", "26", .35, .32),
        ("035420", "NAVER", "KOSPI", "63", None, -.04),
    ), start=1):
        row = {
            "security_id": code, "name": name, "venue": venue,
            "comparison_order": pos, "financial_year": 2025,
            "return_3m": price, "return_6m": price * 1.5,
            "price_strength_25": 18., "revenue_yoy": sales,
            "operating_income_yoy": .43, "revenue_yoy_acceleration": .03,
            "observed_direction": "가격·매출·영업이익 동시 개선 관찰",
            "positive_concordance_of_three": 3 if sales else None,
            "total_score_100": None, "official_leader": False,
            "first_financial_locally_received_at_utc": "2026-10-13T08:20:00+00:00",
        }
        companies.append(row)
        peers.append({
            "stock_code": code, "name": name, "basic_observation_order": pos,
            "return_3m": price, "revenue_yoy": sales,
            "operating_income_yoy": .43, "price_strength_25": 18.,
            "industry_division_code": division,
            "current_industry_code": division + "10",
            "peer_cohort_size": 2 if division == "26" else 1,
            "revenue_yoy_peer_position": pos if division == "26" else None,
            "operating_income_yoy_peer_position": pos if division == "26" else None,
            "return_3m_peer_position": pos if division == "26" else None,
            "profile_first_received_at_utc": "2026-10-13T09:20:00+00:00",
            "total_score_100": None, "official_leader": False,
        })
    basic = signed({
        "schema": exp.BASIC,
        "market_session": "2026-10-08",
        "decision_at_utc": "2026-10-13T09:00:00+00:00",
        "partial_research_screen_only": True,
        "full_ranked_investment_priority_available": False,
        "official_future_leaders": 0,
        "financial_companies_observed": len(companies),
        "comparisons": companies,
    })
    industry = signed({
        "schema": exp.PEER, "market": "KR",
        "market_session": "2026-10-08",
        "as_of_utc": "2026-10-13T10:00:00+00:00",
        "baseline_candidate_sha256": basic["content_sha256"],
        "current_classification_only": True,
        "historic_sector_pit_certified": False,
        "full_investment_priority_ranking_ready": False,
        "official_leaders": 0,
        "selected_companies": len(peers), "companies": peers,
    })
    return basic, industry


def source(tmp_path):
    cohort = tmp_path / "cohort"
    cohort.mkdir()
    basic, industry = pair()
    for name, value in (("basic_candidates_kr.json", basic),
                        ("industry_peers_kr.json", industry)):
        (cohort / name).write_bytes(exp.canonical(value) + b"\n")
    return cohort


def test_searchable_website_and_three_stock_profile_links(tmp_path):
    cohort = source(tmp_path)
    output = tmp_path / "explorer"
    report = exp.publish_company_explorer(cohort=cohort, output=output,
                                          request_day=DAY, clock=NOW)
    assert report["research_company_count"] == 3
    assert report["companies_with_peers"] == 2
    assert report["official_leaders"] == 0
    assert report["stale_warning"]
    assert report["source_market_session"] == "2026-10-08"
    assert report["formal_leader_score_100"] is None
    assert report["content_sha256"] == sha256(exp.canonical({
        key: value for key, value in report.items() if key != "content_sha256"
    })).hexdigest()
    assert set(p.name for p in output.iterdir()) == {
        "index.html", "report.json", "005930.html", "000660.html", "035420.html"}
    html = (output / "index.html").read_text()
    assert "id='search'" in html and "id='division'" in html
    assert "삼성전자" in html and "000660.html" in html
    detail = (output / "005930.html").read_text()
    assert "SK하이닉스" in detail and "000660.html" in detail
    assert "동종 표본 매출순서" in detail
    assert "10월" not in detail  # market observation always shown in ISO form
    single = (output / "035420.html").read_text()
    assert "비교 가능한 기업 N/A" in single and "N/A" in single
    assert json.loads((output / "report.json").read_bytes()) == report
    assert (cohort / "basic_candidates_kr.json").is_file()


def test_unsafe_html_name_is_escaped_on_all_pages():
    basic, peers = pair()
    basic["comparisons"][0]["name"] = "<img src=x onerror=alert(1)>"
    peers["companies"][0]["name"] = basic["comparisons"][0]["name"]
    basic = signed({k:v for k,v in basic.items() if k != "content_sha256"})
    peers["baseline_candidate_sha256"] = basic["content_sha256"]
    peers = signed({k:v for k,v in peers.items() if k != "content_sha256"})
    report = exp.build_explorer(basic, peers, request_day=DAY, now=NOW)
    html = exp.render_index(report) + exp.render_company(report, report["companies"][0])
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img" in html


@pytest.mark.parametrize("change", [
    "candidate_sha", "industry_sha", "future_observation", "bad_profile",
    "wrong_peer_value", "duplicate_identity", "changed_decision", "formal_rank",
])
def test_data_conflict_blocks_new_explorer_without_mutating_evidence(tmp_path, change):
    cohort = source(tmp_path)
    left = cohort / "basic_candidates_kr.json"
    right = cohort / "industry_peers_kr.json"
    a = json.loads(left.read_bytes())
    b = json.loads(right.read_bytes())
    if change == "candidate_sha":
        a["comparisons"][0]["name"] = "FAKE"
    elif change == "industry_sha":
        b["companies"][0]["name"] = "FAKE"
    elif change == "future_observation":
        a["market_session"] = "2026-10-15"
        a = signed({k:v for k,v in a.items() if k != "content_sha256"})
        b["market_session"] = "2026-10-15"
        b["baseline_candidate_sha256"] = a["content_sha256"]
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    elif change == "bad_profile":
        b["companies"][0]["name"] = "OTHER ISSUER"
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    elif change == "wrong_peer_value":
        b["companies"][0]["revenue_yoy"] = -.9
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    elif change == "duplicate_identity":
        b["companies"][0]["stock_code"] = b["companies"][1]["stock_code"]
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    elif change == "changed_decision":
        b["as_of_utc"] = "2026-10-13T08:00:00+00:00"
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    elif change == "formal_rank":
        a["comparisons"][0]["total_score_100"] = 100
        a = signed({k:v for k,v in a.items() if k != "content_sha256"})
        b["baseline_candidate_sha256"] = a["content_sha256"]
        b = signed({k:v for k,v in b.items() if k != "content_sha256"})
    left.write_bytes(exp.canonical(a) + b"\n")
    right.write_bytes(exp.canonical(b) + b"\n")
    old = (left.read_bytes(), right.read_bytes())
    out = tmp_path / "fresh"
    with pytest.raises(ValueError):
        exp.publish_company_explorer(cohort=cohort, output=out,
                                     request_day=DAY, clock=NOW)
    assert not out.exists()
    assert old == (left.read_bytes(), right.read_bytes())


def test_reject_existing_path_and_keep_old_page(tmp_path):
    cohort = source(tmp_path)
    output = tmp_path / "out"
    exp.publish_company_explorer(cohort=cohort, output=output,
                                 request_day=DAY, clock=NOW)
    before = (output / "index.html").read_bytes()
    with pytest.raises(ValueError, match="ALREADY_EXISTS"):
        exp.publish_company_explorer(cohort=cohort, output=output,
                                     request_day=DAY, clock=NOW)
    assert (output / "index.html").read_bytes() == before


def test_simplified_cli_executes_data_to_site(tmp_path, capsys):
    from scripts.publish_official_company_explorer import main
    cohort = source(tmp_path)
    out = tmp_path / "site"
    assert main(["--cohort", str(cohort), "--out", str(out),
                 "--day", DAY]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["research_companies"] == 3
    assert result["companies_with_peer_comparisons"] == 2
    assert result["market_session"] == "2026-10-08"
    assert (out / "005930.html").exists()


def test_missing_cohort_shows_explicit_error_without_creating_output(tmp_path, capsys):
    from scripts.publish_official_company_explorer import main
    out = tmp_path / "new"
    assert main(["--cohort", str(tmp_path / "missing"),
                 "--out", str(out), "--day", DAY]) == 2
    assert "BLOCKED" in capsys.readouterr().err
    assert not out.exists()
