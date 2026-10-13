"""Official API receipts into existing technical WATCH path, no PIT promotion."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import json

import pandas as pd
import pytest

from eraleader.official_api_capture import capture_official_api
from eraleader import official_api_pit_bridge as bridge

DAY = "2026-10-08"
STAMP = datetime(2026, 10, 12, 11, 3, tzinfo=timezone.utc)
DECISION = "2026-10-12T20:10:00+09:00"
CREDS = {"ERALEADER_KRX_AUTH_KEY": "a" * 40,
         "ERALEADER_DART_API_KEY": "b" * 40,
         "ERALEADER_SEC_USER_AGENT": "EraLeader Research contact@example.com"}


def _row(code, name):
    return {"BAS_DD": "20261008", "ISU_CD": code, "ISU_NM": name,
            "TDD_OPNPRC": "10,000", "TDD_HGPRC": "11,000",
            "TDD_LWPRC": "9,000", "TDD_CLSPRC": "10,500",
            "ACC_TRDVOL": "10,000", "ACC_TRDVAL": "105,000,000",
            "MKTCAP": "5,000,000,000"}


def _capture(root, source, payload, *, day=DAY, cik=None):
    result = capture_official_api(
        source, root, day=day, cik=cik, creds=CREDS,
        fetch=lambda _url, _headers: json.dumps(payload).encode("utf8"),
        clock=lambda: STAMP)
    folder = root / result["capture_id"]
    # Some external SSD formats present owner-only files as 0700, despite
    # open(0600). Both remain inaccessible by group and others.
    return folder, result["first_receipt_sha256"]


@pytest.fixture
def packs(tmp_path):
    root = tmp_path / "captures"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    kospi = _capture(root, "krx-kospi", {"OutBlock_1": [_row("005930", "AAA")]})
    kosdaq = _capture(root, "krx-kosdaq", {"OutBlock_1": [_row("A23456", "BBB")]})
    return kospi, kosdaq


@pytest.fixture
def cached(monkeypatch):
    days = pd.bdate_range(end="2026-10-02", periods=260)
    records = []
    for code, name in (("005930", "AAA"), ("A23456", "BBB")):
        for idx, day in enumerate(days):
            close = 8000 + idx * 8
            records.append({"security_id":code, "name":name,
                            "venue":"CACHED_NOT_PIT", "session":day,
                            "open":close, "high":close + 200,
                            "low":close - 200, "close":close,
                            "volume":100, "turnover":close*100,
                            "market_cap":100000000})
    cached_bars = pd.DataFrame(records)
    def read(market, asof, **_kwargs):
        assert market == "KR"
        return cached_bars.copy(), {"source":"unverified local history",
                                      "price_adjustments_verified":False}
    monkeypatch.setattr(bridge, "read_market_bars", read)


def _build(packs, **kw):
    return bridge.build_official_price_snapshot(
        kospi=packs[0], kosdaq=packs[1], decision_at=DECISION,
        as_of="2026-10-12", top=2, **kw)


def test_received_official_rows_combine_with_unverified_cache_research_only(packs, cached):
    snap = _build(packs)
    assert snap["quality_flags"]["official_daily_rows"] == 2
    assert snap["market_last_observation"] == DAY
    assert snap["official_api_evidence"]["official_leaders"] == 0
    assert snap["classification_quality"] == "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"
    assert all(r["state"] == "WATCH" and r["total_score_100"] is None for r in snap["rows"])
    assert set(r["security_id"] for r in snap["rows"]) == {"005930", "A23456"}


def test_first_receipt_pin_tamper_blocks_before_watch(packs, cached, tmp_path):
    a, b = packs
    with pytest.raises(ValueError, match="SHA pin"):
        bridge.build_official_price_snapshot(
            kospi=(a[0], "0"*64), kosdaq=b,
            decision_at=DECISION, as_of="2026-10-12")
    assert not (tmp_path / "output").exists()


def test_raw_tamper_rejected_even_when_first_receipt_unchanged(packs, cached):
    first = packs[0][0] / "raw_response.json"
    first.write_bytes(first.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="evidence invalid"):
        _build(packs)


def test_first_local_receipt_is_not_backdated(packs, cached):
    with pytest.raises(ValueError, match="not locally available"):
        bridge.build_official_price_snapshot(
            kospi=packs[0], kosdaq=packs[1],
            decision_at="2026-10-08T16:00:00+09:00",
            as_of=DAY)


def test_same_market_session_required(packs, cached, tmp_path):
    root = tmp_path / "more"
    root.mkdir(mode=0o700);root.chmod(0o700)
    later = _capture(root, "krx-kosdaq", {"OutBlock_1": [
        {**_row("A23456", "BBB"), "BAS_DD":"20261009"}]}, day="2026-10-09")
    with pytest.raises(ValueError, match="same session"):
        bridge.build_official_price_snapshot(kospi=packs[0], kosdaq=later,
                                             decision_at=DECISION, as_of="2026-10-12")


def test_duplicate_cross_exchange_identity_blocks(packs, cached, tmp_path):
    root = tmp_path / "dup"
    root.mkdir(mode=0o700);root.chmod(0o700)
    duplicate = _capture(root, "krx-kosdaq", {"OutBlock_1": [_row("005930", "BAD")]})
    with pytest.raises(ValueError, match="cross-exchange duplicate"):
        bridge.build_official_price_snapshot(kospi=packs[0], kosdaq=duplicate,
                                             decision_at=DECISION, as_of="2026-10-12")


@pytest.mark.parametrize("bad", [
    {"TDD_CLSPRC":"0"}, {"TDD_OPNPRC":"bad"},
    {"TDD_HGPRC":"9,000"}, {"ISU_CD":"!"},
])
def test_bad_trade_fields_fail_closed(packs, cached, tmp_path, bad):
    root = tmp_path / "bad"
    root.mkdir(mode=0o700);root.chmod(0o700)
    bad_capture = _capture(root,"krx-kospi",
                           {"OutBlock_1":[{**_row("005930","BAD"),**bad}]})
    with pytest.raises(ValueError):
        bridge.build_official_price_snapshot(kospi=bad_capture, kosdaq=packs[1],
                                             decision_at=DECISION, as_of="2026-10-12")


def test_incomplete_dart_and_sec_are_evidence_not_rank_inputs(packs, cached, tmp_path):
    root=tmp_path/"extra";root.mkdir(mode=0o700);root.chmod(0o700)
    dart=_capture(root,"dart-disclosures",{"status":"000","total_count":"999",
                 "list":[{"rcept_dt":"20261008","rcept_no":"20261008000001"}]})
    sec=_capture(root,"sec-submissions",{"cik":320193,
                 "filings":{"recent":{"accessionNumber":["0001"],
                 "acceptanceDateTime":["2026-10-08T09:00:00Z"]}}},day=None,cik="320193")
    snap=_build(packs,auxiliary=(("dart-disclosures",*dart),
                                 ("sec-submissions",*sec)))
    assert len(snap["official_api_evidence"]["sources"]) == 4
    assert snap["official_api_evidence"]["sources"][2]["quality"] == "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY"
    assert not snap["official_api_evidence"]["dart_sec_financial_pit_joined"]
    assert all(x["total_score_100"] is None for x in snap["rows"])


def test_watch_sqlite_dashboard_reports_and_dry_run_no_live_notification(packs,cached,tmp_path):
    snap=_build(packs)
    out=tmp_path/"research"
    result=bridge.run_official_research(snap,out)
    assert result["watch_count"] == 2 and result["reports"] == 3
    assert result["alert_dry_run_count"] == 2 and result["messages_sent"] == 0
    assert result["official_leaders"] == 0 and result["pit_certified"] is False
    assert (out/"state.sqlite").is_file()
    assert (out/"site"/"official_api.html").is_file()
    assert (out/"site"/"kr.html").is_file()
    assert "공식 API" in (out/"site"/"index.html").read_text()
    assert "factor_readiness_kr.html" in (out/"site"/"index.html").read_text()
    assert "factor_readiness_kr.html" in (out/"site"/"kr.html").read_text()
    assert (out/"site"/"factor_readiness_kr.html").is_file()
    assert (out/"factor_readiness_kr.json").is_file()
    assert len(list((out/"reports").glob("*.md"))) == 3
    alert_rows=json.loads((out/"alerts_preview.json").read_text())
    assert len(alert_rows) == 2
    assert all(ev["recorded_at_date"] == "2026-10-12" and
               ev["observed_market_session"] == DAY and
               ev["historical_backfill"] is True and
               ev["prospective_leadtime_eligible"] is False and
               ev["first_local_received_at_utc"] == STAMP.isoformat()
               for ev in alert_rows)
    with sqlite3.connect(out/"state.sqlite") as db:
        assert {day for (day,) in db.execute("SELECT as_of FROM events")} == {"2026-10-12"}
    with pytest.raises(ValueError, match="fresh output"):
        bridge.run_official_research(snap,out)


def test_no_silent_future_price_or_future_request_day(packs,cached):
    with pytest.raises(ValueError, match="not backdate"):
        bridge.build_official_price_snapshot(kospi=packs[0],kosdaq=packs[1],
             decision_at=DECISION,as_of="2026-10-13")


def test_capture_permissions_fail_closed(packs, cached):
    file=packs[0][0]/"first_receipt.json"
    file.chmod(0o644)
    with pytest.raises(ValueError,match="owner-only"):
        _build(packs)


def test_existing_pit_ledger_join_is_read_only_and_not_certified(packs,cached,tmp_path):
    from eraleader.offline_pit import OfflineLedger
    p=tmp_path/"offline.sqlite"
    ledger=OfflineLedger(p)
    try:
        ledger.import_rows("membership",[{
            "source_id":"synthetic_fixture","revision":1,
            "security_id":"kr:issuer:demo","market":"KR","ticker":"005930",
            "industry_id":"semi", "valid_from":"2026-01-01",
            "known_at":"2026-10-08T10:00:00+09:00",
        }],"synthetic_fixture")
    finally:
        ledger.close()
    before=sha256(p.read_bytes()).hexdigest()
    result=bridge.run_official_research(_build(packs),tmp_path/"with_pit",
                                         pit_ledger=p)
    assert result["pit_join_status"] == "PIT_LEDGER_RESEARCH_ONLY_NOT_CERTIFIED"
    assert result["pit_company_count"] == 1
    assert (tmp_path/"with_pit"/"site"/"research_kr.html").is_file()
    assert (tmp_path/"with_pit"/"official_pit_integrated_research.json").is_file()
    assert sha256(p.read_bytes()).hexdigest()==before
    obj=json.loads((tmp_path/"with_pit"/"official_pit_integrated_research.json").read_text())
    assert obj["confirmed_leaders"] == 0 and obj["pit_certified"] is False


def test_missing_explicit_pit_ledger_blocks_without_creating_watch(packs,cached,tmp_path):
    with pytest.raises(ValueError,match="PIT ledger required"):
        bridge.run_official_research(_build(packs),tmp_path/"must_not_create",
                                     pit_ledger=tmp_path/"missing.sqlite")
    assert not (tmp_path/"must_not_create").exists()


def test_conservative_actual_dart_annual_research_join_never_promotes(
        packs,cached,monkeypatch,tmp_path):
    """Only pinned CFS annual rows after observed first receipt can annotate WATCH."""
    from eraleader import official_dart_corp_directory as directory_mod
    from eraleader import official_dart_financials as fin_mod
    monkeypatch.setattr(directory_mod,"verify_dart_corp_directory",
        lambda *_a,**_k:{
            "mapping":{"005930":"00126380"},"ambiguous_stock_codes":set(),
            "total_corporations":100,"listed_security_code_count":1,
            "first_local_received_at_utc":"2026-10-12T11:00:00+00:00",
            "first_receipt_sha256":"f"*64})
    def verified(_folder,pin,**kwargs):
        year=2024 if pin=="a"*64 else 2025
        return {"stock_code":"005930","corp_code":"00126380",
                "report_code":"11011","statement":"CFS",
                "year":year,"first_local_received_at_utc":"2026-10-12T11:00:00+00:00",
                "metrics":{"revenue":{"value":100 if year==2024 else 120},
                           "operating_income":{"value":15 if year==2024 else 20}}}
    monkeypatch.setattr(fin_mod,"verify_dart_financial",verified)
    snap=bridge.build_official_price_snapshot(
        kospi=packs[0],kosdaq=packs[1],decision_at=DECISION,
        as_of="2026-10-12",top=2,
        dart_directory=(tmp_path/"ignored","f"*64),
        dart_financial_receipts=((tmp_path/"yr2024","a"*64),
                                 (tmp_path/"yr2025","b"*64)))
    assert snap["official_api_evidence"]["dart_financial_comparable_companies"]==1
    row=next(x for x in snap["rows"] if x["security_id"]=="005930")
    assert row["dart_financial_annual_growth_research"]["revenue_yoy"] == pytest.approx(.2)
    assert row["dart_financial_pit_certified"] is False and row["total_score_100"] is None
    out=tmp_path/"with_research"
    res=bridge.run_official_research(snap,out)
    assert res["dart_financial_comparable_companies"]==1
    assert "DART 매출 YoY" in (out/"site"/"kr.html").read_text()
    assert "20.0%" in (out/"site"/"kr.html").read_text()
    assert res["official_leaders"]==0


def test_actual_two_year_cfs_outside_price_topn_gets_independent_research_page(
        packs, cached, monkeypatch, tmp_path):
    """A financially observed company is never erased merely by price TOP-N."""
    from eraleader import official_dart_corp_directory as directory_mod
    from eraleader import official_dart_financials as fin_mod
    from eraleader.official_factor_readiness import factor_coverage_from_official_snapshot

    original_history = bridge.read_market_bars

    def differing_history(*args, **kwargs):
        prices, quality = original_history(*args, **kwargs)
        prices.loc[prices["security_id"] == "A23456", ["open", "high", "low", "close"]] = (
            4200, 4300, 3900, 4100
        )
        return prices, quality

    monkeypatch.setattr(bridge, "read_market_bars", differing_history)
    monkeypatch.setattr(directory_mod, "verify_dart_corp_directory",
        lambda *_a, **_k: {
            "mapping": {"005930": "00126380"}, "ambiguous_stock_codes": set(),
            "total_corporations": 100,
            "listed_security_code_count": 1,
            "first_local_received_at_utc": "2026-10-12T11:00:00+00:00",
            "first_receipt_sha256": "f"*64,
        })

    def verified(_folder, pin, **_kwargs):
        year = 2024 if pin == "a"*64 else 2025
        return {
            "stock_code": "005930", "corp_code": "00126380",
            "report_code": "11011", "statement": "CFS", "year": year,
            "first_local_received_at_utc": "2026-10-12T11:00:00+00:00",
            "metrics": {
                "revenue": {"value": 100 if year == 2024 else 120},
                "operating_income": {"value": 15 if year == 2024 else 20},
                "net_income": {"value": 9 if year == 2024 else 10},
            },
        }

    monkeypatch.setattr(fin_mod, "verify_dart_financial", verified)
    snap = bridge.build_official_price_snapshot(
        kospi=packs[0], kosdaq=packs[1],
        decision_at=DECISION, as_of="2026-10-12", top=1,
        dart_directory=(tmp_path/"directory_receipt", "f"*64),
        dart_financial_receipts=(
            (tmp_path/"fy2024", "a"*64),
            (tmp_path/"fy2025", "b"*64),
        ),
    )
    assert snap["shown"] == 1 and snap["rows"][0]["security_id"] == "A23456"
    financial = snap["official_financial_research_observations"]
    assert len(financial) == 1 and financial[0]["security_id"] == "005930"
    assert financial[0]["rank_in_price_top20"] is None
    assert financial[0]["research_metrics"]["revenue_yoy"] == pytest.approx(.2)
    result = factor_coverage_from_official_snapshot(snap)
    assert result["annual_cfs_comparable_companies"] == 1
    assert result["annual_cfs_in_price_top20"] == 0
    assert result["valid_full_leader_scores"] == result["official_leaders"] == 0
    out = tmp_path / "actual_research_data_flow"
    finished = bridge.run_official_research(snap, out)
    page = (out/"site"/"factor_readiness_kr.html").read_text()
    assert "005930" in page and "+20.00%" in page
    assert "투자 우선순위는 산출하지 않습니다" in page
    assert "factor_readiness_kr.html" in (out/"site"/"index.html").read_text()
    assert "20위 밖 실적 관찰 기업 보기" in (out/"site"/"kr.html").read_text()
    assert finished["financial_comparables_not_in_price_top"] == 1
    assert len(json.loads((out/"kr_latest.json").read_text())["rows"]) == 1
    assert finished["official_leaders"] == finished["messages_sent"] == 0
