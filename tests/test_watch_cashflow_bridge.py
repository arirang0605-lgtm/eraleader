from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from eraleader.dart_cashflow_watch import publish_watch_cashflow, read_cashflow, CASH_FIELDS
from eraleader.dart_profitability_watch import dart_annual_margin_context
from eraleader.early_leader_watch_queue import publish_early_watch, _validated, watch_version
from eraleader.watch_cashflow_bridge import publish_watch_cashflow_fields, merge_cashflow_fields
from eraleader.early_watch_daily_brief import publish_daily_brief, read_daily_brief
from eraleader.operations_overview import audit_local_operations
from test_early_leader_watch_queue import setup, NOW
from test_dart_cashflow_watch import original_vault


def inputs(tmp_path, monkeypatch):
    _, project, market, partial = setup(tmp_path)
    vault = original_vault(tmp_path, monkeypatch)
    original = publish_early_watch(project=project, marketwide=market,
        factor_input=partial, dart_cfs_capture_root=vault, clock=NOW)
    watch = Path(original["manifest"])
    cash = publish_watch_cashflow(project=project, marketwide=market,
        watch_manifest=watch, capture_root=vault, clock=NOW)
    return project, market, vault, watch, Path(cash["manifest"])


def connect(values, *, now=NOW+timedelta(minutes=1)):
    project, market, vault, watch, cash = values
    return publish_watch_cashflow_fields(project=project, marketwide=market,
        watch_manifest=watch, cashflow_manifest=cash, capture_root=vault, clock=now)


def test_original_receipts_attach_to_existing_neutral_watch_and_daily_report(tmp_path, monkeypatch):
    values = inputs(tmp_path, monkeypatch)
    project, _, _, watch, cash = values
    old_watch, old_cash = watch.read_bytes(), cash.read_bytes()
    base = _validated(watch, clock=NOW)
    result = connect(values)
    annotated = _validated(Path(result["manifest"]), clock=NOW+timedelta(minutes=1))
    assert result["watch_rows"] == 2 and result["cfo_available"] == 1
    assert annotated["source_market_session"] == base["source_market_session"]
    assert annotated["source_first_assessed_at_utc"] == base["source_first_assessed_at_utc"]
    assert annotated["original_watch_published_at_utc"] == base["watch_published_at_utc"]
    assert annotated["source_original_watch_sha256"] == base["content_sha256"]
    assert annotated["selected_candidates"] == [] and annotated["state_changes"] == []
    assert annotated["archived_watch_annotation_only"] is True
    assert [r["security_id"] for r in annotated["review_queue"]] == [
        r["security_id"] for r in base["review_queue"]]
    first = annotated["review_queue"][0]
    assert first["dart_cfs_operating_cashflow_krw"] == 300
    assert first["dart_cfs_cash_after_ppe_intangibles_krw"] == 200
    assert first["dart_cashflow_first_receipt_sha256"] == first["dart_cfs_first_receipt_sha256"]
    assert first["dart_cashflow_issuer_corp_code"] == first["dart_cfs_issuer_corp_code"]
    assert annotated["review_queue"][1]["dart_cfs_operating_cashflow_krw"] is None
    assert "영업현금(억원)" in Path(result["site"]).read_text()
    brief = publish_daily_brief(project=project, watch_manifest=Path(result["manifest"]),
                                clock=NOW+timedelta(minutes=1))
    report = read_daily_brief(Path(brief["manifest"]), clock=NOW+timedelta(minutes=1))
    assert report["entries"][0]["dart_cfs_operating_cashflow_krw"] == 300
    assert report["dart_cashflow_cfo_available"] == 1
    assert report["source_watch_first_published_at_utc"] == annotated["watch_published_at_utc"]
    assert report["source_original_watch_first_published_at_utc"] == base["watch_published_at_utc"]
    assert report["leader_state_events"] == [] and report["orders_enabled"] is False
    assert "영업현금(억원)" in Path(brief["site"]).read_text()
    dashboard = audit_local_operations(project, clock=NOW+timedelta(minutes=1))
    assert dashboard["kr_early_leader_watch"]["href"].endswith(
        Path(result["site"]).parent.name+"/index.html")
    assert watch.read_bytes() == old_watch and cash.read_bytes() == old_cash
    repeat = connect(values, now=NOW+timedelta(minutes=2))
    assert repeat["status"] == "ALREADY_PUBLISHED"
    assert repeat["manifest"] == result["manifest"]


def test_old_market_annotation_keeps_original_date_instead_of_making_new_current_watch(tmp_path, monkeypatch):
    values = inputs(tmp_path, monkeypatch)
    now = NOW+timedelta(days=3)
    result = connect(values, now=now)
    doc = _validated(Path(result["manifest"]), clock=now)
    assert doc["source_market_session"] == "2026-10-13"
    assert doc["archived_watch_annotation_only"] is True
    brief = publish_daily_brief(project=values[0], watch_manifest=Path(result["manifest"]), clock=now)
    report = read_daily_brief(Path(brief["manifest"]), clock=now)
    assert report["report_is_same_session_market_update"] is False
    assert report["source_market_session"] == "2026-10-13"


@pytest.mark.parametrize("change", ["stock", "name", "receipt", "value", "source"])
def test_wrong_company_or_different_source_facts_are_refused(tmp_path, monkeypatch, change):
    values = inputs(tmp_path, monkeypatch)
    _, market, vault, watch, cash = values
    import json
    doc = read_cashflow(cash, clock=NOW)
    base = _validated(watch, clock=NOW)
    context = dart_annual_margin_context(market=json.loads(market.read_bytes()),
        capture_root=vault, now=NOW, include_cashflow=True)
    broken = deepcopy(doc)
    if change == "stock":
        broken["entries"][0]["security_id"] = "999999"
    elif change == "name":
        broken["entries"][0]["name"] = "다른 회사"
    elif change == "receipt":
        broken["entries"][0]["first_receipt_sha256"] = "b"*64
    elif change == "value":
        broken["entries"][0]["dart_cfs_operating_cashflow_krw"] += 1
    else:
        broken["source_watch_sha256"] = "b"*64
    with pytest.raises(ValueError):
        merge_cashflow_fields(base, broken, context, NOW)


def test_future_receipt_cannot_be_attached_even_if_test_context_repeats_it(tmp_path, monkeypatch):
    values = inputs(tmp_path, monkeypatch)
    _, market, vault, watch, cash = values
    import json
    base = _validated(watch, clock=NOW)
    doc = read_cashflow(cash, clock=NOW)
    context = dart_annual_margin_context(market=json.loads(market.read_bytes()),
        capture_root=vault, now=NOW, include_cashflow=True)
    future = (NOW+timedelta(days=1)).isoformat()
    doc["entries"][0]["first_received_at_utc"] = future
    context["005930"]["dart_cfs_first_received_at_utc"] = future
    with pytest.raises(ValueError, match="FUTURE"):
        merge_cashflow_fields(base, doc, context, NOW)


def test_existing_watch_version_stays_compatible_and_cash_fields_get_a_new_edition(tmp_path, monkeypatch):
    values = inputs(tmp_path, monkeypatch)
    base = _validated(values[3], clock=NOW)
    assert values[3].parent.name.endswith(watch_version(base))
    result = connect(values)
    annotated = _validated(Path(result["manifest"]), clock=NOW+timedelta(minutes=1))
    assert watch_version(base) != watch_version(annotated)


def test_daily_reader_refuses_future_cash_receipt_even_with_a_recomputed_report_hash(tmp_path, monkeypatch):
    import json
    from hashlib import sha256
    from eraleader.official_company_explorer import canonical
    values=inputs(tmp_path,monkeypatch)
    connected=connect(values)
    now=NOW+timedelta(minutes=1)
    brief=publish_daily_brief(project=values[0],watch_manifest=Path(connected["manifest"]),clock=now)
    path=Path(brief["manifest"])
    doc=json.loads(path.read_bytes())
    doc["entries"][0]["dart_cashflow_first_received_at_utc"]=(now+timedelta(days=1)).isoformat()
    doc.pop("content_sha256")
    doc["content_sha256"]=sha256(canonical(doc)).hexdigest()
    path.write_bytes(canonical(doc)+b"\n")
    with pytest.raises(ValueError,match="FUTURE"):
        read_daily_brief(path,clock=now)
