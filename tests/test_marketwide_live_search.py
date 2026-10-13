"""The complete observed KR stock list is searchable without inventing leaders."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from eraleader import marketwide_live_search as search
from eraleader.official_company_explorer import canonical

NOW = datetime(2026, 10, 14, 1, 30, tzinfo=timezone.utc)


def sample() -> dict:
    rows = []
    for code, name, venue, price, rev, op, ind, score, rank, watch in (
            ("005930", "삼성전자", "KOSPI", 20., .4, .7, "2612", 42.5, 1, 1),
            ("000660", "SK하이닉스", "KOSPI", 14., None, None, None, None, None, None),
            ("123456", "코스닥기업", "KOSDAQ", None, -.1, None, None, None, None, None),
    ):
        rows.append({
            "security_id":code,"name":name,"venue":venue,
            "market_session":"2026-10-08","close":50000.,
            "market_cap":10_000_000_000., "turnover":100_000_000.,
            "market_traded":True,"current_dart_directory_matched":True,
            "price_strength_25":price,"revenue_yoy":rev,
            "operating_income_yoy":op,"revenue_growth_acceleration":None,
            "industry_code":ind,"two_factor_research_50":score,
            "two_factor_research_rank":rank,"price_top20_watch_rank":watch,
            "formal_leader_score_100":None,"verified_leader_state":None,
            "institutional_flow":None,"foreign_flow":None,
        })
    value = {
        "schema":search.SCHEMA,"market":"KR",
        "market_session":"2026-10-08",
        "built_at_utc":"2026-10-13T23:00:00+00:00",
        "source_decision_at_utc":"2026-10-13T21:00:00+00:00",
        "source_watch_run_id":"a"*20,
        "official_krx_observed":3,
        "financial_factors_observed":2,
        "industry_factors_observed":1,
        "local_price_lookback_evaluable":2,
        "two_factor_research_evaluable":1,
        "two_factor_research_top20":[{"security_id":"005930",
             "research_order":1,"observed_score_50":42.5}],
        "research_only":True,"official_leaders":0,
        "full_market_composite_rank_available":False,"securities":rows,
    }
    value["content_sha256"] = sha256(canonical(value)).hexdigest()
    return value


def file(tmp_path, value=None):
    path = tmp_path / "marketwide_kr.json"
    path.write_bytes(canonical(value or sample()) + b"\n")
    return path


def repin(report):
    copy = deepcopy(report)
    copy.pop("content_sha256",None)
    copy["content_sha256"] = sha256(canonical(copy)).hexdigest()
    return copy


def build(tmp_path):
    source = file(tmp_path)
    target = tmp_path/"new_search"
    result = search.publish_search(input_report=source,output=target,
                                   request_day="2026-10-14",clock=NOW)
    return source,target,result


def test_searchable_full_market_ui_and_actual_completeness(tmp_path):
    source,target,result = build(tmp_path)
    assert result["status"] == "KR_MARKETWIDE_SEARCH_PUBLISHED"
    assert result["observed"]==3 and result["financial"]==2
    assert result["two_factor_evaluable"]==1 and result["formal_selected"]==0
    report=json.loads((target/"manifest.json").read_bytes())
    assert report["research_only"] and report["stale_warning"]
    assert report["source_market_session"]=="2026-10-08"
    signed=dict(report); digest=signed.pop("content_sha256")
    assert sha256(canonical(signed)).hexdigest()==digest
    html=(target/"index.html").read_text()
    for text in ("종목명 / 코드 검색","시장","자료 충족","정렬 (매수순위 아님)",
                 "id=\"results\"","id=\"stock-meta\"","id=\"stock-data\"",
                 "id=\"previous\"","id=\"next\"","삼성전자","123456",
                 "자료 지연 경고","정식 대장주"):
        assert text in html
    assert source.exists()
    assert sorted(x.name for x in target.iterdir())==["index.html","manifest.json"]


def test_untrusted_issuer_name_cannot_inject_script(tmp_path):
    data = sample()
    data["securities"][0]["name"] = "</script><script>alert(1)</script>"
    data["two_factor_research_top20"][0]["name"] = data["securities"][0]["name"]
    data = repin(data)
    source = file(tmp_path,data)
    target = tmp_path/"render"
    search.publish_search(input_report=source,output=target,
                          request_day="2026-10-14",clock=NOW)
    html=(target/"index.html").read_text()
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c" in html and "textContent" in html


@pytest.mark.parametrize("change", [
    "sha","duplicate","future","missing_observation","fake_leader",
    "wrong_top20","missing_finance","bad_venue","finance_wrong_count",
])
def test_inaccurate_source_cannot_publish_as_complete_research(tmp_path, change):
    data=sample()
    if change=="sha":
        data["securities"][0]["name"]="TAMPERED WITHOUT SHA"
    elif change=="duplicate":
        data["securities"][1]["security_id"]="005930"
    elif change=="future":
        data["market_session"]="2026-10-15"
        for row in data["securities"]:
            row["market_session"]="2026-10-15"
    elif change=="missing_observation":
        data["securities"].pop()
    elif change=="fake_leader":
        data["securities"][0]["formal_leader_score_100"]=100.
    elif change=="wrong_top20":
        data["two_factor_research_top20"][0]["security_id"]="000660"
    elif change=="missing_finance":
        data["securities"][0]["operating_income_yoy"]=None
    elif change=="bad_venue":
        data["securities"][0]["venue"]="NYSE"
    elif change=="finance_wrong_count":
        data["financial_factors_observed"]=99
    if change!="sha":
        data=repin(data)
    src=file(tmp_path,data)
    out=tmp_path/"blocked"
    with pytest.raises((ValueError,TypeError)):
        search.publish_search(input_report=src,output=out,
                              request_day="2026-10-14",clock=NOW)
    assert not out.exists()


def test_prior_page_not_overwritten_even_with_valid_new_source(tmp_path):
    src,out,_=build(tmp_path)
    old=(out/"index.html").read_bytes()
    with pytest.raises(ValueError,match="NEW_OUTPUT_DIR_REQUIRED"):
        search.publish_search(input_report=src,output=out,
                              request_day="2026-10-14",clock=NOW)
    assert (out/"index.html").read_bytes()==old


def test_future_request_date_is_blocked_without_site(tmp_path):
    src=file(tmp_path)
    with pytest.raises(ValueError,match="FUTURE"):
        search.publish_search(input_report=src,output=tmp_path/"after_today",
                              request_day="2026-10-15",clock=NOW)
    assert not (tmp_path/"after_today").exists()


def test_cli_offline_source_to_search_site(tmp_path,capsys):
    from scripts.publish_marketwide_search import main
    src=file(tmp_path)
    out=tmp_path/"cli_site"
    assert main(["--source",str(src),"--day","2026-10-14",
                 "--out",str(out)]) == 0
    value=json.loads(capsys.readouterr().out)
    assert value["observed"] == 3
    assert value["two_factor_evaluable"] == 1
    assert (out/"index.html").exists()
    assert main(["--source",str(src),"--day","2026-10-14",
                 "--out",str(out)]) == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_missing_source_returns_clear_error_without_output(tmp_path,capsys):
    from scripts.publish_marketwide_search import main
    out=tmp_path/"site"
    assert main(["--source",str(tmp_path/"missing.json"),"--day","2026-10-14",
                 "--out",str(out)]) == 2
    assert "BLOCKED" in capsys.readouterr().err
    assert not out.exists()


def test_readonly_original_preserved(tmp_path):
    src=file(tmp_path)
    raw=src.read_bytes()
    result=search.publish_search(input_report=src,output=tmp_path/"view",
                                 request_day="2026-10-14",clock=NOW)
    assert result["formal_selected"] == 0
    assert src.read_bytes() == raw
    assert not list(tmp_path.glob(".search_publish_*"))


def test_older_marketwide_without_full_price_lookup_still_searchable(tmp_path):
    # With full price lookback OFF, older reports only carry price WATCH/
    # financial subsets. The UI must not require a fictional 2,765-row score.
    data = sample()
    data["local_price_lookback_enabled"] = False
    data["local_price_lookback_evaluable"] = 0
    src = file(tmp_path, repin(data))
    out = tmp_path / "partial"
    result = search.publish_search(
        input_report=src, output=out, request_day="2026-10-14", clock=NOW)
    assert result["observed"] == 3
    assert result["two_factor_evaluable"] == 1
    assert json.loads((out/"manifest.json").read_bytes())["price_lookback_available"] == 2
