"""KR KRX+DART daily capture must not require unrelated SEC receipts."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest
from eraleader.kiwoom_investor_flow import canonical
from scripts import publish_basic_company_screen as subject

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def setup(tmp_path, *, lone_sec=False):
    private = tmp_path / "first"
    private.mkdir()
    pins = {}

    def first(name, payload=b"first-original"):
        folder = private / name
        folder.mkdir()
        raw = folder / "first_receipt.json"
        raw.write_bytes(payload + name.encode())
        pin = sha256(raw.read_bytes()).hexdigest()
        pins[name] = pin
        return pin

    for tag in ("krx-kospi", "krx-kosdaq", "dart-disclosures"):
        first(tag)
    first("dart_directory")
    for stock in ("005930", "000660"):
        for year in (2024, 2025):
            first("dart_fin_" + sha256((stock + str(year)).encode()).hexdigest()[:32])
    manifest = private / "dart_full_x"
    manifest.mkdir()
    dart_full = manifest / "manifest.json"
    dart_full.write_bytes(canonical({"market_day": "2026-10-13", "pages": 1}))
    full_sha = sha256(dart_full.read_bytes()).hexdigest()
    sources = [
        {"source": key, "first_receipt_sha256": pins[key]}
        for key in ("krx-kospi", "krx-kosdaq", "dart-disclosures")]
    if lone_sec:
        first("sec-submissions")
        sources.append({"source": "sec-submissions",
                        "first_receipt_sha256": pins["sec-submissions"]})
    official = tmp_path / "official.json"
    official.write_bytes(canonical({
        "schema": "eraleader.official_api_pit_research_bridge.v1",
        "historic_universe_pit_verified": False,
        "official_leaders": 0,
        "sources": sources,
        "dart_current_directory": {"first_receipt_sha256": pins["dart_directory"]},
        "dart_full_day": {"market_day": "2026-10-13", "manifest_sha256": full_sha},
    }))
    companies = []
    for stock in ("005930", "000660"):
        annual = []
        for year in (2024, 2025):
            name = "dart_fin_" + sha256((stock + str(year)).encode()).hexdigest()[:32]
            annual.append({
                "fiscal_year": year,
                "status": "FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY",
                "pit_certified": False,
                "capture_id": name, "first_receipt_sha256": pins[name]})
        companies.append({
            "stock_code": stock,
            "research_annual_cfs_complete": True,
            "annual_reports": annual,
        })
    research = tmp_path / "finance.json"
    research.write_bytes(canonical({
        "schema": subject.MULTI_SCHEMA, "research_only": True,
        "real_investment_leader_ranked": False,
        "companies_requested": 2, "companies": companies,
        "fiscal_years": [2024, 2025],
        "official_market": {"market_session": "2026-10-13"},
    }))
    return official, research, private


def test_three_kr_sources_reuse_existing_builder_no_sec(tmp_path, monkeypatch):
    official, research, private = setup(tmp_path)
    calls = []
    def fake_build(**kw):
        calls.append(kw)
        return {"synthetic_validated_snapshot": True,
                "official_financial_research_observations": [{}, {}],
                "research_candidate_price_factors": [{}, {}]}
    def fake_run(snapshot, out, *, basic_candidates):
        assert basic_candidates and snapshot["synthetic_validated_snapshot"]
        return {
            "official_leaders": 0, "messages_sent": 0,
            "basic_candidate_html": str(out / "site/basic_candidates_kr.html"),
            "krx_rows": 3, "dart_full_rows": 10,
            "dart_financial_comparable_companies": 2,
            "basic_candidate_evaluable": 2, "watch_count": 2,
            "reports": 3,
        }
    monkeypatch.setattr(subject, "build_official_price_snapshot", fake_build)
    monkeypatch.setattr(subject, "run_official_research", fake_run)
    result = subject.publish_basic_company_screen(
        official_source=official, financial_manifest=research,
        private_root=private, new_output=tmp_path / "new", clock=NOW)
    assert result["status"] == "OFFICIAL_MULTICOMPANY_PRICE_EARNINGS_RESEARCH_PUBLISHED"
    assert [p[0] for p in calls[0]["auxiliary"]] == ["dart-disclosures"]
    assert result["official_leaders"] == 0


def test_partial_sec_receipt_rejected_before_research_writes(tmp_path, monkeypatch):
    official, research, private = setup(tmp_path, lone_sec=True)
    monkeypatch.setattr(subject, "build_official_price_snapshot",
                        lambda **kw: pytest.fail("should block before stock research"))
    with pytest.raises(ValueError, match="partial SEC"):
        subject.publish_basic_company_screen(
            official_source=official, financial_manifest=research,
            private_root=private, new_output=tmp_path / "blocked", clock=NOW)
    assert not (tmp_path / "blocked").exists()
