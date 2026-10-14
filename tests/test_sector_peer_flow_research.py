"""Source-pinned sector peer/flow research; never certified factor scores."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json

import pytest

from eraleader.sector_peer_flow_research import (
    analyze_marketwide_peer_flow,publish_marketwide_peer_flow
)
from eraleader.official_company_explorer import canonical
from test_marketwide_live_search import sample,repin
from test_marketwide_auto_refresh import fixture

NOW=datetime(2026,10,14,3,tzinfo=timezone.utc)


def report_file(tmp_path):
    root,project=fixture(tmp_path)
    source=root/"report"
    source.mkdir()
    report=sample()
    names=["005930","000660","123456"]
    for i,item in enumerate(report["securities"]):
        item["name"]=["삼성전자","SK하이닉스","코스닥기업"][i]
        item["industry_code"]="29271"
        item["revenue_yoy"]=[.4,.2,-.1][i]
        item["operating_income_yoy"]=[.7,.3,-.2][i]
        item["peer_revenue_yoy_rank"]=i+1
        item["peer_revenue_yoy_denominator"]=3
        item["peer_operating_yoy_rank"]=i+1
        item["peer_operating_yoy_denominator"]=3
        item["observed_industry_sample_size"]=3
    report["financial_factors_observed"]=3
    report["industry_factors_observed"]=3
    report["securities"][0]["institutional_flow"]=-100
    report["securities"][0]["foreign_flow"]=200
    report["flow_factors_observed"]=1
    report["flow_matched_session_companies"]=1
    report["flow_certification"]="FIRST_LOCAL_RECEIPT_RESEARCH_ONLY_NOT_HISTORIC_PIT"
    report["flow_source_manifest_sha256"]="a"*64
    report=repin(report)
    path=source/"marketwide_kr.json"
    path.write_bytes(canonical(report)+b"\n")
    return project,path,report


def test_peer_flow_actual_ranks_and_small_sample_sector_growth(tmp_path):
    project,path,report=report_file(tmp_path)
    result=analyze_marketwide_peer_flow(path,clock=NOW)
    assert result["sector_profile_count"]==3
    assert result["sector_groups_with_at_least_three_observed"]==1
    assert result["observed_revenue_peer_ranks"]==3
    assert result["observed_operating_peer_ranks"]==3
    assert result["relative_revenue_sample_ge3"]==3
    assert result["same_session_raw_broker_flow"]==1
    group=result["partial_sector_medians"][0]
    assert group["sample_revenue_yoy_median"]==.2
    assert group["sample_operating_yoy_median"]==.3
    assert group["independent_industry_growth_score_20"] is None
    ranks={c["security_id"]:c for c in result["companies"]}
    assert ranks["005930"]["peer_revenue_relative_position"]==1.
    assert ranks["123456"]["peer_revenue_relative_position"]==0.
    assert ranks["005930"]["foreign_net_shares"]==200
    assert all(c["industry_growth_score_20"] is None and
               c["competitiveness_score_20"] is None and
               c["investor_flow_score_10"] is None
               for c in result["companies"])
    assert result["formal_leaders"]==0
    assert result["execution_authority"] is False


def test_publish_static_html_and_immutable_repeat(tmp_path):
    project,path,_=report_file(tmp_path)
    first=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    assert first["status"]=="PUBLISHED"
    page=Path(first["site"])
    source=Path(first["manifest"])
    assert page.is_file() and source.is_file()
    assert "자료" not in page.read_text() or "성장" in page.read_text()
    assert "기관 순매매(주)" in page.read_text()
    before=(page.read_bytes(),source.read_bytes())
    repeat=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    assert repeat["status"]=="ALREADY_PUBLISHED"
    assert (page.read_bytes(),source.read_bytes())==before


@pytest.mark.parametrize("change",["rank_duplicate","rank_reversed","denominator","out_of_range","missing_source_pin"])
def test_modified_peer_evidence_blocked(tmp_path,change):
    project,path,report=report_file(tmp_path)
    if change=="rank_duplicate":
        report["securities"][1]["peer_revenue_yoy_rank"]=1
    elif change=="rank_reversed":
        report["securities"][1]["peer_revenue_yoy_rank"]=3
        report["securities"][2]["peer_revenue_yoy_rank"]=2
    elif change=="denominator":
        report["securities"][1]["peer_revenue_yoy_denominator"]=4
    elif change=="out_of_range":
        report["securities"][0]["peer_operating_yoy_rank"]=0
    elif change=="missing_source_pin":
        report["securities"][0]["name"]="TAMPER"
    if change!="missing_source_pin":
        report=repin(report)
    path.write_bytes(canonical(report)+b"\n")
    with pytest.raises(ValueError):
        publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    assert not list((project/"output").glob("sector_peer_flow/KR_*"))


def test_untrusted_company_name_is_html_escaped(tmp_path):
    project,path,report=report_file(tmp_path)
    report["securities"][0]["name"]="<script>alert('x')</script>"
    report=repin(report)
    path.write_bytes(canonical(report)+b"\n")
    result=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    html=Path(result["site"]).read_text()
    assert "<script>alert('x')</script>" not in html
    assert "&lt;script&gt;" in html


def test_corrupted_prior_page_refuses_replay(tmp_path):
    project,path,_=report_file(tmp_path)
    first=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    html=Path(first["site"])
    html.write_bytes(html.read_bytes()+b"MUTATION")
    raw=html.read_bytes()
    with pytest.raises(ValueError,match="PUBLICATION_CONFLICT"):
        publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    assert html.read_bytes()==raw


def test_symlink_marketwide_publication_blocked(tmp_path):
    project,path,_=report_file(tmp_path)
    fake=tmp_path/"elsewhere"
    fake.mkdir()
    target=project/"output"/"sector_peer_flow"
    target.symlink_to(fake,target_is_directory=True)
    with pytest.raises(ValueError,match="DESTINATION_LINKED"):
        publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    assert not list(fake.iterdir())


def test_one_company_industry_is_not_qualified_sector_growth(tmp_path):
    project,path,report=report_file(tmp_path)
    report["securities"][2]["industry_code"]="282"
    report["securities"][2]["peer_revenue_yoy_rank"]=None
    report["securities"][2]["peer_revenue_yoy_denominator"]=None
    report["securities"][2]["peer_operating_yoy_rank"]=None
    report["securities"][2]["peer_operating_yoy_denominator"]=None
    for i in (0,1):
        report["securities"][i]["peer_revenue_yoy_denominator"]=2
        report["securities"][i]["peer_operating_yoy_denominator"]=2
    report=repin(report)
    path.write_bytes(canonical(report)+b"\n")
    result=analyze_marketwide_peer_flow(path,clock=NOW)
    assert result["sector_groups_with_at_least_three_observed"]==0
    assert result["relative_revenue_sample_ge3"]==0
    assert not result["partial_sector_medians"]


def test_operations_dashboard_includes_validated_peer_growth_link(tmp_path):
    from eraleader.operations_overview import audit_local_operations,render_operations_overview
    project,path,_=report_file(tmp_path)
    assert audit_local_operations(project,clock=NOW)["kr_peer_flow_research"] is None
    result=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    snapshot=audit_local_operations(project,clock=NOW)
    entry=snapshot["kr_peer_flow_research"]
    assert entry["market_session"]=="2026-10-08"
    assert entry["revenue_peers"]==3 and entry["operating_peers"]==3
    assert entry["raw_flow"]==1 and entry["formal_leaders"]==0
    assert entry["href"].endswith(Path(result["site"]).parent.name+"/index.html")
    page=render_operations_overview(snapshot)
    assert "한국 동종기업 성장·수급 비교 보기" in page
    assert "정식 성장/경쟁력/수급 점수 N/A" in page


def test_operations_rejects_tampered_peer_page_or_bad_injected_link(tmp_path):
    from eraleader.operations_overview import audit_local_operations,render_operations_overview
    project,path,_=report_file(tmp_path)
    published=publish_marketwide_peer_flow(marketwide=path,project=project,clock=NOW)
    snapshot=audit_local_operations(project,clock=NOW)
    snapshot["kr_peer_flow_research"]["href"]="../../../../secret"
    with pytest.raises(ValueError,match="Unsafe sector"):
        render_operations_overview(snapshot)
    target=Path(published["site"])
    target.write_bytes(target.read_bytes()+b"tampered")
    assert audit_local_operations(project,clock=NOW)["kr_peer_flow_research"] is None


def test_operations_cli_opt_in_research_peer_flow(tmp_path):
    import subprocess,sys
    project,path,_=report_file(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    root=path.parent.parent
    cmd=[sys.executable,str(script),"--project",str(project),
         "--marketwide-source-root",str(root),"--marketwide-peer-flow-research"]
    run=subprocess.run(cmd,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    payload=json.loads(run.stdout)
    assert payload["marketwide_peer_flow_status"]=="PUBLISHED"
    assert payload["marketwide_peer_rank_revenue"]==3
    assert payload["marketwide_peer_rank_operating"]==3
    assert payload["marketwide_peer_raw_flow"]==1
    assert payload["marketwide_peer_formal_leaders"]==0
    assert payload["external_api_calls"]==0
    page=(project/"output"/"operations"/"site"/"index.html").read_text()
    assert "한국 동종기업 성장·수급 비교 보기" in page
    repeat=subprocess.run(cmd,capture_output=True,text=True)
    assert repeat.returncode==0,repeat.stderr
    assert json.loads(repeat.stdout)["marketwide_peer_flow_status"]=="ALREADY_PUBLISHED"


def test_operations_peer_flag_requires_source_root(tmp_path):
    import subprocess,sys
    _,project=fixture(tmp_path)
    script=Path(__file__).resolve().parents[1]/"scripts"/"render_local_operations.py"
    run=subprocess.run([sys.executable,str(script),"--project",str(project),
                        "--marketwide-peer-flow-research"],capture_output=True,text=True)
    assert run.returncode!=0
    assert not (project/"output"/"sector_peer_flow").exists()
