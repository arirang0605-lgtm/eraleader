from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import os

import pytest

from eraleader.dart_cashflow_watch import (
    parse_annual_cashflow, publish_watch_cashflow, read_cashflow, ACCOUNTS)
from eraleader.dart_profitability_watch import dart_annual_margin_context
from eraleader.official_dart_financials import parse_dart_financial
from eraleader.early_leader_watch_queue import publish_early_watch
from eraleader.operations_overview import audit_local_operations, render_operations_overview
from test_early_leader_watch_queue import setup, NOW


def raw_cfs(year=2025, cfo=300, ppe=90, intangible=10, net=100):
    rows = []
    for account, section, value in [
        ("ifrs-full_Revenue", "IS", 1000),
        ("dart_OperatingIncomeLoss", "IS", 200),
        ("ifrs-full_ProfitLoss", "IS", net),
        (ACCOUNTS["dart_cfs_operating_cashflow_krw"], "CF", cfo),
        (ACCOUNTS["dart_cfs_ppe_purchase_raw_krw"], "CF", ppe),
        (ACCOUNTS["dart_cfs_intangible_purchase_raw_krw"], "CF", intangible)]:
        if value is None:
            continue
        rows.append({"corp_code": "00126380", "bsns_year": str(year),
            "reprt_code": "11011", "rcept_no": f"{year+1}0314000001",
            "fs_div": "CFS", "sj_div": section, "currency": "KRW",
            "account_id": account, "thstrm_amount": str(value)})
    return json.dumps({"status": "000", "list": rows}).encode()


def parse(raw):
    return parse_annual_cashflow(raw, corp_code="00126380", year=2025)


def test_exact_cfo_and_acquisition_accounts_calculate_bounded_cash_observation():
    row = parse(raw_cfs())
    assert row["dart_cfs_operating_cashflow_krw"] == 300
    assert row["dart_cfs_cash_after_ppe_intangibles_krw"] == 200
    assert row["dart_cfs_operating_cash_to_revenue_pct"] == 30
    assert row["dart_cfs_operating_cash_to_net_income_ratio"] == 3


@pytest.mark.parametrize("raw_value", [90, -90])
def test_purchase_sign_preserves_raw_and_normalizes_only_named_outflows(raw_value):
    row = parse(raw_cfs(ppe=raw_value))
    assert row["dart_cfs_ppe_purchase_raw_krw"] == raw_value
    assert row["dart_cfs_ppe_purchase_outflow_krw"] == 90
    assert row["dart_cfs_cash_after_ppe_intangibles_krw"] == 200


def test_missing_purchase_is_not_zero_filled_but_reported_zero_is_valid():
    missing = parse(raw_cfs(intangible=None))
    assert missing["dart_cfs_cash_after_ppe_intangibles_krw"] is None
    actual_zero = parse(raw_cfs(intangible=0))
    assert actual_zero["dart_cfs_cash_after_ppe_intangibles_krw"] == 210


def test_loss_does_not_generate_misleading_cash_to_profit_ratio():
    row = parse(raw_cfs(net=-100))
    assert row["dart_cfs_operating_cash_to_net_income_ratio"] is None


@pytest.mark.parametrize("change", ["issuer", "statement", "conflict"])
def test_wrong_company_statement_or_ambiguous_cf_accounts_block(change):
    doc = json.loads(raw_cfs())
    if change == "issuer":
        doc["list"][-1]["corp_code"] = "00999999"
    elif change == "statement":
        doc["list"][-1]["fs_div"] = "OFS"
    else:
        row = deepcopy(doc["list"][3])
        row["thstrm_amount"] = "301"
        doc["list"].append(row)
    with pytest.raises(ValueError):
        parse(json.dumps(doc).encode())


def test_currency_and_segment_rows_cannot_supply_the_total_cfo():
    doc = json.loads(raw_cfs())
    doc["list"][3]["currency"] = "USD"
    row = parse(json.dumps(doc).encode())
    assert row["dart_cfs_operating_cashflow_krw"] is None
    doc["list"][3]["currency"] = "KRW"
    doc["list"][3]["account_detail"] = "부문A"
    assert parse(json.dumps(doc).encode())["dart_cfs_operating_cashflow_krw"] is None


def original_vault(tmp_path, monkeypatch, future=False):
    from eraleader import dart_profitability_watch as part
    vault = tmp_path/"originals"
    vault.mkdir(mode=0o700)
    directory = vault/"dart_directory_test"
    directory.mkdir(mode=0o700)
    (directory/"first_receipt.json").write_bytes(b"original directory witness")
    directory_pin = sha256((directory/"first_receipt.json").read_bytes()).hexdigest()
    monkeypatch.setattr(part, "verify_dart_corp_directory",
                        lambda *a, **k: {"mapping": {"005930": "00126380"}})
    for year in (2024, 2025):
        folder = vault/("dart_fin_"+str(year))
        folder.mkdir(mode=0o700)
        raw = raw_cfs(year=year, cfo=200 if year==2024 else 300)
        checked = parse_dart_financial(raw, corp_code="00126380", year=year,
                                      report="11011", statement="CFS")
        metadata = {
            "schema": part.FIN_SCHEMA, "stock_code": "005930",
            "corp_code": "00126380", "statement": "CFS", "reprt_code": "11011",
            "bsns_year": year, "source_directory_sha256": directory_pin,
            "raw_sha256": sha256(raw).hexdigest(), "raw_length": len(raw),
            "reported_row_count": checked["financial_rows"],
            "financial_quality": checked["status"],
            "observed_account_count": len(checked["metrics"]),
            "report_accessions": checked["report_accessions"], "official_leaders": 0,
            "first_local_received_at_utc": (
                (NOW+timedelta(days=1)).isoformat() if future and year==2025
                else (NOW-timedelta(hours=2)).isoformat())}
        for name, data in [("raw_response.json", raw),
                           ("first_receipt.json", json.dumps(metadata).encode())]:
            path = folder/name
            path.write_bytes(data)
            os.chmod(path, 0o600)
    return vault


def test_two_year_original_cash_context_is_optin_and_previous_margin_contract_is_preserved(tmp_path, monkeypatch):
    vault = original_vault(tmp_path, monkeypatch)
    market = {"securities": [{"security_id": "005930", "current_dart_directory_matched": True}]}
    old = dart_annual_margin_context(market=market, capture_root=vault, now=NOW)
    assert "dart_cfs_operating_cashflow_krw" not in old["005930"]
    enriched = dart_annual_margin_context(market=market, capture_root=vault, now=NOW,
                                          include_cashflow=True)["005930"]
    assert enriched["dart_cfs_operating_cashflow_krw"] == 300
    assert enriched["dart_previous_cfs_operating_cashflow_krw"] == 200
    assert enriched["dart_cfs_operating_cash_positive_two_years"] is True
    assert old == dart_annual_margin_context(market=market, capture_root=vault, now=NOW)


def test_real_contract_originals_reach_cash_report_neutral_json_and_operations(tmp_path, monkeypatch):
    _, project, market, partial = setup(tmp_path)
    watch = publish_early_watch(project=project, marketwide=market, factor_input=partial, clock=NOW)
    watch_path = Path(watch["manifest"])
    before = watch_path.read_bytes()
    vault = original_vault(tmp_path, monkeypatch)
    result = publish_watch_cashflow(project=project, marketwide=market,
        watch_manifest=watch_path, capture_root=vault, clock=NOW)
    assert result["watch_rows"] == 2
    assert result["cfo_available"] == result["cash_after_purchases_available"] == 1
    doc = read_cashflow(Path(result["manifest"]), clock=NOW)
    assert doc["selected_candidates"] == [] and doc["orders_enabled"] is False
    assert doc["entries"][1]["dart_cfs_operating_cashflow_krw"] is None
    assert doc["entries"][0]["competitive_advantage_score_20"] is None
    assert "영업현금−유형·무형취득" in Path(result["site"]).read_text()
    snapshot = audit_local_operations(project, clock=NOW)
    assert snapshot["kr_watch_annual_cashflow"]["cfo_available"] == 1
    assert "WATCH 연간 현금창출 관찰 보기" in render_operations_overview(snapshot)
    snapshot["kr_watch_annual_cashflow"]["href"] = "../../../../secret"
    with pytest.raises(ValueError, match="Unsafe WATCH annual cashflow"):
        render_operations_overview(snapshot)
    repeat = publish_watch_cashflow(project=project, marketwide=market,
        watch_manifest=watch_path, capture_root=vault, clock=NOW+timedelta(minutes=1))
    assert repeat["status"] == "ALREADY_PUBLISHED"
    assert watch_path.read_bytes() == before


def test_future_cash_receipt_is_not_used_as_latest_fiscal_year(tmp_path, monkeypatch):
    vault = original_vault(tmp_path, monkeypatch, future=True)
    market = {"securities": [{"security_id": "005930", "current_dart_directory_matched": True}]}
    row = dart_annual_margin_context(market=market, capture_root=vault, now=NOW,
                                    include_cashflow=True)["005930"]
    assert row["dart_latest_cfs_business_year"] == 2024
    assert row["dart_cfs_operating_cashflow_krw"] == 200
    assert row["dart_cfs_operating_cash_positive_two_years"] is None
