"""DART original annual profit margins -> early WATCH JSON/HTML positive path."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path

import pytest

from eraleader.dart_profitability_watch import dart_annual_margin_context,RESEARCH_SOURCE
from eraleader.early_leader_watch_queue import publish_early_watch,_validated
from eraleader.operations_overview import audit_local_operations
from test_early_leader_watch_queue import setup,NOW


def actual_style(code="005930",when="2026-10-14T02:00:00+00:00"):
    return {
        code:{
            "dart_latest_cfs_business_year":2025,
            "dart_cfs_revenue_krw":100_000_000,
            "dart_cfs_operating_income_krw":23_000_000,
            "dart_cfs_net_income_krw":12_000_000,
            "dart_cfs_operating_margin_pct":23.0,
            "dart_cfs_net_margin_pct":12.0,
            "dart_cfs_first_receipt_sha256":"a"*64,
            "dart_cfs_first_received_at_utc":when,
            "dart_cfs_issuer_corp_code":"00126380",
            "dart_cfs_margin_source":RESEARCH_SOURCE,
            "dart_cfs_independent_pit_certified":False,
        }
    }


def test_signed_verified_positive_company_margin_reaches_neutral_watch_and_html(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    vault=tmp_path/"private_source";vault.mkdir()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style())
    published=publish_early_watch(marketwide=market,project=project,
                                  factor_input=partial,dart_cfs_capture_root=vault,
                                  clock=NOW)
    assert published["status"]=="PUBLISHED" and published["orders"]==0
    doc=_validated(Path(published["manifest"]),clock=NOW)
    assert doc["dart_profitability_companies_in_watch"]==1
    assert doc["dart_profitability_originals_available"]==1
    assert doc["receiver_project"] is None
    assert doc["selected_candidates"]==[]
    assert doc["formal_leader_selection_count"]==0
    mapping={r["security_id"]:r for r in doc["review_queue"]}
    good=mapping["005930"]
    assert good["dart_cfs_revenue_krw"]==100_000_000
    assert good["dart_cfs_operating_margin_pct"]==23.0
    assert good["dart_cfs_net_margin_pct"]==12.0
    assert good["competitive_advantage_score_20"] is None
    assert "competitiveness" in good["missing_for_5factor"]
    other=mapping["000660"]
    assert other["dart_cfs_operating_margin_pct"] is None
    assert other["dart_cfs_margin_source"] is None
    page=Path(published["site"]).read_text()
    assert "DART 연결재무 실적 수익성" in page
    assert "23.0" in page
    linked=audit_local_operations(project,clock=NOW)["kr_early_leader_watch"]
    assert linked is not None and linked["count"]==2
    assert Path(published["manifest"]).exists()
    replay=publish_early_watch(marketwide=market,project=project,
                               factor_input=partial,dart_cfs_capture_root=vault,
                               clock=NOW+timedelta(minutes=2))
    assert replay["status"]=="ALREADY_PUBLISHED"


def test_existing_watch_is_not_overwritten_by_dart_profitability_version(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    previous=publish_early_watch(marketwide=market,project=project,
                                 factor_input=partial,clock=NOW)
    frozen=Path(previous["manifest"]).read_bytes()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style())
    vault=tmp_path/"private_source";vault.mkdir()
    new=publish_early_watch(marketwide=market,project=project,
                            factor_input=partial,dart_cfs_capture_root=vault,
                            clock=NOW)
    assert new["manifest"]!=previous["manifest"]
    assert Path(previous["manifest"]).read_bytes()==frozen


def test_future_receipt_cannot_enter_watch(tmp_path,monkeypatch):
    from eraleader import dart_profitability_watch
    _,project,market,partial=setup(tmp_path)
    vault=tmp_path/"source";vault.mkdir()
    monkeypatch.setattr(dart_profitability_watch,"dart_annual_margin_context",
                        lambda **kw:actual_style(when="2026-10-15T00:00:00+00:00"))
    with pytest.raises(ValueError,match="FUTURE_OR_UNVERIFIED"):
        publish_early_watch(marketwide=market,project=project,
                            factor_input=partial,dart_cfs_capture_root=vault,
                            clock=NOW)
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))


def test_private_root_absent_prevents_fake_margin_without_stopping_default_watch(tmp_path):
    _,project,market,partial=setup(tmp_path)
    import json
    s=json.loads(market.read_bytes())
    with pytest.raises(ValueError,match="PRIVATE_ROOT"):
        dart_annual_margin_context(market=s,capture_root=tmp_path/"missing",
                                   now=NOW)
    normal=publish_early_watch(marketwide=market,project=project,
                               factor_input=partial,clock=NOW)
    assert normal["watch_queue_count"]==2


def test_cli_optin_requires_actual_files(tmp_path):
    import subprocess,sys
    from pathlib import Path
    _,project,market,partial=setup(tmp_path)
    runner=Path(__file__).resolve().parents[1]/"scripts"/"publish_early_leader_watch.py"
    cmd=[sys.executable,str(runner),"--project",str(project),
         "--marketwide-report",str(market),"--factor-input",str(partial),
         "--dart-cfs-capture-root",str(tmp_path/"absent")]
    p=subprocess.run(cmd,capture_output=True,text=True)
    assert p.returncode==2
    assert "EARLY_LEADER_WATCH_PUBLICATION_BLOCKED" in p.stderr


def _two_year_originals(tmp_path,monkeypatch,years=(2024,2025),*,future_year=None):
    """Exact shape of original first-receipt CFS files, without external APIs."""
    import os,json
    from hashlib import sha256
    from eraleader import dart_profitability_watch as part
    root=tmp_path/"owner_first_receipts"
    root.mkdir(mode=0o700)
    corp=root/"dart_directory_test"
    corp.mkdir(mode=0o700)
    original=b"test unique directory first-original"
    (corp/"first_receipt.json").write_bytes(original)
    corp_pin=sha256(original).hexdigest()
    monkeypatch.setattr(part,"verify_dart_corp_directory",lambda *args,**kw:{
        "mapping":{"005930":"00126380"}})
    for year in years:
        folder=root/("dart_fin_"+str(year))
        folder.mkdir(mode=0o700)
        raw=json.dumps({"year":year}).encode()
        first_date=("2026-10-15T02:00:00+00:00"
                    if year==future_year else "2026-10-14T01:00:00+00:00")
        meta={
            "schema":part.FIN_SCHEMA,
            "stock_code":"005930","corp_code":"00126380",
            "statement":"CFS","reprt_code":"11011","bsns_year":year,
            "first_local_received_at_utc":first_date,
            "source_directory_sha256":corp_pin,
            "raw_sha256":sha256(raw).hexdigest(),"raw_length":len(raw),
            "reported_row_count":2,
            "financial_quality":"FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY",
            "report_accessions":["00000000000001"],
            "observed_account_count":3,"official_leaders":0,
        }
        for name,data in (("raw_response.json",raw),
                          ("first_receipt.json",json.dumps(meta).encode())):
            f=folder/name
            f.write_bytes(data)
            os.chmod(f,0o600)
    def fake_parser(raw,*,corp_code,year,report,statement):
        assert corp_code=="00126380" and report=="11011" and statement=="CFS"
        assert json.loads(raw)["year"]==year
        amounts={2024:(1000,100,70),2025:(2000,400,280)}
        rev,op,net=amounts[year]
        return {"status":"FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY",
                "financial_rows":2,
                "report_accessions":["00000000000001"],
                "metrics":{"revenue":{"value":rev},
                           "operating_income":{"value":op},
                           "net_income":{"value":net}}}
    monkeypatch.setattr(part,"parse_dart_financial",fake_parser)
    return root,{"securities":[{"security_id":"005930",
                                "current_dart_directory_matched":True}]}


def test_2024_and_2025_verified_originals_calculate_profit_margin_trend(tmp_path,monkeypatch):
    root,market=_two_year_originals(tmp_path,monkeypatch)
    from eraleader.dart_profitability_watch import dart_annual_margin_context
    row=dart_annual_margin_context(market=market,capture_root=root,now=NOW)["005930"]
    assert row["dart_latest_cfs_business_year"]==2025
    assert row["dart_previous_cfs_business_year"]==2024
    assert row["dart_cfs_operating_margin_pct"]==20
    assert row["dart_previous_cfs_operating_margin_pct"]==10
    assert row["dart_cfs_operating_margin_change_pp"]==10
    assert row["dart_cfs_net_margin_change_pp"]==7
    assert row["dart_cfs_operating_margin_positive_two_years"] is True
    assert row["dart_cfs_two_year_comparable"] is True
    assert len(row["dart_cfs_previous_first_receipt_sha256"])==64


def test_one_year_only_does_not_invent_previous_profit_trend(tmp_path,monkeypatch):
    root,market=_two_year_originals(tmp_path,monkeypatch,years=(2025,))
    from eraleader.dart_profitability_watch import dart_annual_margin_context
    row=dart_annual_margin_context(market=market,capture_root=root,now=NOW)["005930"]
    assert row["dart_cfs_operating_margin_pct"]==20
    assert row["dart_cfs_operating_margin_change_pp"] is None
    assert row["dart_cfs_operating_margin_positive_two_years"] is None
    assert row["dart_cfs_two_year_comparable"] is False


def test_first_receipt_missing_at_decision_cannot_create_two_year_trend(tmp_path,monkeypatch):
    root,market=_two_year_originals(tmp_path,monkeypatch,future_year=2025)
    from eraleader.dart_profitability_watch import dart_annual_margin_context
    row=dart_annual_margin_context(market=market,capture_root=root,now=NOW)["005930"]
    assert row["dart_latest_cfs_business_year"]==2024
    assert row["dart_cfs_operating_margin_change_pp"] is None


def test_two_year_report_rejects_corrupted_original(tmp_path,monkeypatch):
    root,market=_two_year_originals(tmp_path,monkeypatch)
    from eraleader.dart_profitability_watch import dart_annual_margin_context
    (root/"dart_fin_2024"/"raw_response.json").write_bytes(b"corrupted")
    import os
    os.chmod(root/"dart_fin_2024"/"raw_response.json",0o600)
    with pytest.raises(ValueError,match="ORIGINAL_RECEIPT_CONFLICT"):
        dart_annual_margin_context(market=market,capture_root=root,now=NOW)
