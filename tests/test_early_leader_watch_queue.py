"""Operational WATCH intake: real observed research, never synthetic leaders."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
from zoneinfo import ZoneInfo

import pytest

from eraleader.official_company_explorer import canonical
from eraleader.early_leader_watch_queue import (
    create_early_watch, publish_early_watch, _validated
)
from eraleader.official_partial_factor_bridge import derive_partial_factor_input
from eraleader.factor_selection_pipeline import _read_assessment
from eraleader.operations_overview import audit_local_operations,render_operations_overview
from test_official_partial_factor_bridge import source
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,6,tzinfo=timezone.utc)


def setup(tmp_path, *,with_flow=False,clock=None):
    source_root,project=fixture(tmp_path)
    market,_=source(project/"output",
                    **({"market_date":clock.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),
                        "clock":clock} if clock is not None else {}))
    part=derive_partial_factor_input(marketwide=market,project=project,clock=clock or NOW)
    input_path=Path(part["input_file"])
    if with_flow:
        original=_read_assessment(input_path)
        r=next(row for row in original["factor_rows"] if row["security_id"]=="000660")
        r["components"]["flow"]=7.3
        r["factor_receipts"]["flow"]={
            "provider":"LOCAL_FLOW_RESEARCH_NOT_VALIDATED",
            "sha256":"a"*64,
            "available_at_utc":"2026-10-14T01:00:00+00:00",
        }
        original.pop("content_sha256")
        original["content_sha256"]=sha256(canonical(original)).hexdigest()
        input_path=project/"output"/"partial_factor_inputs"/"signed_flow_partial.json"
        input_path.write_bytes(canonical(original)+b"\n")
    return source_root,project,market,input_path


def publish(project,market,partial,*,top=50,clock=NOW):
    return publish_early_watch(
        marketwide=market,project=project,factor_input=partial,
        top=top,clock=clock)


def test_early_watch_readonly_neutral_queue_with_price_earnings(tmp_path):
    _,project,market,partial=setup(tmp_path)
    sent=publish(project,market,partial)
    assert sent["status"]=="PUBLISHED"
    assert sent["watch_queue_count"]==2
    assert sent["observed_candidates"]==2
    assert sent["receiver_neutral"] is True
    assert sent["consumer_project"] is None
    assert sent["official_leaders"]==0 and sent["orders"]==0
    payload=_validated(Path(sent["manifest"]),clock=NOW)
    assert payload["source_market_session"]=="2026-10-13"
    assert payload["watch_only"] is True
    assert payload["formal_leader_selection_count"]==0
    assert payload["selected_candidates"]==[]
    assert payload["state_changes"]==[]
    assert payload["order_instruction"] is False
    assert [x["security_id"] for x in payload["review_queue"]]==["005930","000660"]
    assert payload["review_queue"][0]["watch_tier"]=="A_PRICE_EARNINGS_OBSERVED"
    assert payload["review_queue"][0]["observed_component_count"]==2
    assert payload["review_queue"][0]["missing_for_5factor"]==[
        "industry","competitiveness","flow"]
    assert all(x["investment_rank"] is None and x["eligible_to_order"] is False
               for x in payload["review_queue"])
    assert "종목" in Path(sent["site"]).read_text()


def test_tier_B_flow_research_is_separate_from_financial_group(tmp_path):
    _,project,market,partial=setup(tmp_path,with_flow=True)
    result=publish(project,market,partial)
    doc=_validated(Path(result["manifest"]),clock=NOW)
    assert [row["watch_tier"] for row in doc["review_queue"]]==[
        "A_PRICE_EARNINGS_OBSERVED","B_PRICE_FLOW_OBSERVED"]
    assert doc["review_queue"][1]["flow_research_10"]==7.3
    assert doc["review_queue"][1]["earnings_research_25"] is None
    assert doc["review_queue"][1]["investment_rank"] is None
    assert doc["tier_available_counts"]["B_PRICE_FLOW_OBSERVED"]==1


def test_repeated_run_is_idempotent_without_extra_version(tmp_path):
    _,project,market,partial=setup(tmp_path)
    one=publish(project,market,partial)
    doc=Path(one["manifest"])
    before=doc.read_bytes()
    later=publish(project,market,partial,clock=NOW+timedelta(minutes=8))
    assert later["status"]=="ALREADY_PUBLISHED"
    assert later["manifest"]==one["manifest"]
    assert doc.read_bytes()==before
    assert len(list(doc.parent.parent.glob("KR_*")))==1


def test_different_top_creates_new_immutable_candidate_queue(tmp_path):
    _,project,market,partial=setup(tmp_path)
    one=publish(project,market,partial,top=1)
    two=publish(project,market,partial,top=2)
    assert one["watch_queue_count"]==1
    assert two["watch_queue_count"]==2
    assert one["manifest"]!=two["manifest"]
    assert Path(one["manifest"]).exists()


@pytest.mark.parametrize("bad",[-1,0,101,True,1.3])
def test_bad_requested_top_is_rejected(tmp_path,bad):
    _,project,market,partial=setup(tmp_path)
    with pytest.raises(ValueError,match="TOP_OUT_OF_RANGE"):
        publish(project,market,partial,top=bad)
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))


def test_future_assessment_and_stale_market_cannot_publish(tmp_path):
    _,project,market,partial=setup(tmp_path)
    original=_read_assessment(partial)
    original["decision_at_utc"]=(NOW+timedelta(hours=3)).isoformat()
    original.pop("content_sha256")
    original["content_sha256"]=sha256(canonical(original)).hexdigest()
    altered=project/"output"/"partial_factor_inputs"/"future.json"
    altered.write_bytes(canonical(original)+b"\n")
    with pytest.raises(ValueError):
        publish(project,market,altered)
    old=publish(project,market,partial,clock=NOW+timedelta(days=15))
    assert old["status"]=="EARLY_WATCH_STALE_MARKET_HOLD"


def test_tampered_existing_watch_queue_blocked(tmp_path):
    _,project,market,partial=setup(tmp_path)
    original=publish(project,market,partial)
    file=Path(original["manifest"])
    file.write_bytes(file.read_bytes()+b"forged")
    with pytest.raises(ValueError):
        publish(project,market,partial)
    assert file.read_bytes().endswith(b"forged")
    assert audit_local_operations(project,clock=NOW)["kr_early_leader_watch"] is None


def test_operational_dashboard_uses_sha_valid_queue_and_safe_link(tmp_path):
    _,project,market,partial=setup(tmp_path)
    assert audit_local_operations(project,clock=NOW)["kr_early_leader_watch"] is None
    one=publish(project,market,partial)
    snap=audit_local_operations(project,clock=NOW)
    entry=snap["kr_early_leader_watch"]
    assert entry["count"]==2
    assert entry["tier_counts"]["A_PRICE_EARNINGS_OBSERVED"]==1
    assert entry["receiver_neutral"] is True
    html=render_operations_overview(snap)
    assert "한국 대장주 후보 관찰 우선목록 보기" in html
    assert "공식 선정 0 / 주문 0" in html
    snap["kr_early_leader_watch"]["href"]="../../../../secrets"
    with pytest.raises(ValueError,match="Unsafe early leader watch"):
        render_operations_overview(snap)
    Path(one["site"]).write_bytes(b"MUTATION")
    assert audit_local_operations(project,clock=NOW)["kr_early_leader_watch"] is None


def test_explicit_cli_publishes_without_network_and_next_run_reuses(tmp_path):
    root,project,market,partial=setup(tmp_path,clock=datetime.now(timezone.utc))
    script=Path(__file__).resolve().parents[1]/"scripts"/"publish_early_leader_watch.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-report",str(market),"--factor-input",str(partial)]
    status=subprocess.run(cmd,capture_output=True,text=True)
    assert status.returncode==0,status.stderr
    d=json.loads(status.stdout)
    assert d["orders"]==0 and d["external_api_calls"]==0
    again=subprocess.run(cmd,capture_output=True,text=True)
    assert again.returncode==0,again.stderr
    assert json.loads(again.stdout)["status"]=="ALREADY_PUBLISHED"


def test_optional_operations_auto_refresh_includes_early_queue(tmp_path):
    root,project,market,partial=setup(tmp_path,clock=datetime.now(timezone.utc))
    # Source finder probes one-level child folders, not output itself.
    source_directory=root/"market_20261013"
    source_directory.mkdir()
    (source_directory/"marketwide_kr.json").write_bytes(market.read_bytes())
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-source-root",str(root),
         "--marketwide-watch-queue-input",str(partial)]
    first=subprocess.run(cmd,capture_output=True,text=True)
    assert first.returncode==0,first.stderr
    doc=json.loads(first.stdout)
    assert doc["marketwide_early_watch_count"]==2
    assert doc["marketwide_early_watch_orders"]==0
    page=(project/"output"/"operations"/"site"/"index.html").read_text()
    assert "한국 대장주 후보 관찰 우선목록 보기" in page


def test_optional_queue_requires_explicit_source_and_never_contacts_api(tmp_path):
    _,project,market,partial=setup(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-watch-queue-input",str(partial)]
    missing=subprocess.run(cmd,capture_output=True,text=True)
    assert missing.returncode!=0
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))


def test_forged_earnings_component_blocked_even_when_assessment_sha_is_recomputed(tmp_path):
    _,project,market,partial=setup(tmp_path)
    original=_read_assessment(partial)
    original["factor_rows"][0]["components"]["earnings"]=3.0
    original.pop("content_sha256")
    original["content_sha256"]=sha256(canonical(original)).hexdigest()
    forged=project/"output"/"partial_factor_inputs"/"tampered_earnings.json"
    forged.write_bytes(canonical(original)+b"\n")
    with pytest.raises(ValueError,match="FINANCIAL_NOT_MARKET_VERIFIED"):
        publish(project,market,forged)
    assert not list((project/"output").glob("early_leader_watch_queue/KR_*"))


def test_same_industry_dart_growth_reaches_watch_fields_only_when_observed(tmp_path):
    from eraleader.early_leader_watch_queue import _observed_peer_context
    rows=[
        {"security_id":"100001","industry_code":"2612",
         "current_dart_directory_matched":True,"revenue_yoy":0.30,
         "operating_income_yoy":0.40},
        {"security_id":"100002","industry_code":"2612",
         "current_dart_directory_matched":True,"revenue_yoy":0.10,
         "operating_income_yoy":0.20},
        {"security_id":"100003","industry_code":"2613",
         "current_dart_directory_matched":True,"revenue_yoy":0.80,
         "operating_income_yoy":0.40},
        {"security_id":"100004","industry_code":"2612",
         "current_dart_directory_matched":False,"revenue_yoy":0.99,
         "operating_income_yoy":0.99},
    ]
    enriched=_observed_peer_context({"securities":rows})
    assert set(enriched)=={"100001","100002"}
    first=enriched["100001"]
    assert first["industry_sample_peer_count"]==2
    assert first["industry_sample_revenue_growth_median_pct"]==20.0
    assert first["company_revenue_growth_pct"]==30.0
    assert first["company_revenue_growth_vs_peers_pp"]==10.0
    assert first["company_operating_growth_vs_peers_pp"]==10.0
    assert enriched["100002"]["company_revenue_growth_vs_peers_pp"]==-10.0


def test_missing_operating_yoy_keeps_competitive_execution_as_na():
    from eraleader.early_leader_watch_queue import _observed_peer_context
    pair=[
        {"security_id":"100001","industry_code":"29271",
         "current_dart_directory_matched":True,"revenue_yoy":0.20,
         "operating_income_yoy":None},
        {"security_id":"100002","industry_code":"29271",
         "current_dart_directory_matched":True,"revenue_yoy":0.10,
         "operating_income_yoy":0.30},
    ]
    got=_observed_peer_context({"securities":pair})
    assert got["100001"]["industry_sample_revenue_growth_median_pct"]==15.0
    assert got["100001"]["company_operating_growth_vs_peers_pp"] is None
    assert got["100002"]["company_operating_growth_vs_peers_pp"] is None


def test_peer_enriched_watch_still_retains_nil_industry_and_competitive_scores(tmp_path):
    from eraleader.early_leader_watch_queue import SECTOR_CONTEXT
    _,project,market,partial=setup(tmp_path)
    made=publish(project,market,partial)
    doc=_validated(Path(made["manifest"]),clock=NOW)
    assert doc["sector_peer_context_method"]==SECTOR_CONTEXT
    assert doc["sector_peer_comparable_in_watch"]==0
    assert doc["company_operating_peer_comparable_in_watch"]==0
    for row in doc["review_queue"]:
        assert row["industry_and_competitive_score_20_available"] is False
        assert row["industry_sample_growth_is_entire_industry"] is False
        assert row["independent_competitive_moat_verified"] is False
        assert "industry" in row["missing_for_5factor"]
        assert "competitiveness" in row["missing_for_5factor"]
    html=Path(made["site"]).read_text()
    assert "업종표본 매출성장 중간" in html
