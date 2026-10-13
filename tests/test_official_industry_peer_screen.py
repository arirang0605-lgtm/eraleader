"""DART first-original two-digit division peers never become buy rankings."""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from test_official_basic_candidates import observed_two_companies
from eraleader.official_basic_candidates import build_basic_candidate_research
from eraleader import official_industry_peer_screen as industry

NOW=datetime(2026,10,13,11,tzinfo=timezone.utc)
PIN="d"*64
SECTOR={"005930":("264","00126380"),"000660":("2612","00164779")}


def base():
    return build_basic_candidate_research(observed_two_companies())


def cohort():
    return {
        "schema":industry.COHORT,
        "decision_at_utc":"2026-10-13T10:30:00Z",
        "source_directory_sha256":PIN,
        "companies_requested":2,
        "current_classification_only":True,
        "historic_industry_pit_certified":False,
        "official_leaders":0,
        "companies":[{
            "stock_code":stock,
            "pit_certified":False,
            "status":"CURRENT_DART_COMPANY_INDUSTRY_RESEARCH_ONLY",
            "current_dart_industry_code":SECTOR[stock][0],
            "corp_code":SECTOR[stock][1],
            "first_local_received_at_utc":"2026-10-13T10:10:00+00:00",
            "first_receipt_sha256":char*64
        } for stock,char in (("005930","a"),("000660","b"))],
    }


@pytest.fixture
def real_source_witness(monkeypatch,tmp_path):
    def verified(_folder, pin, *, decision_at, directory):
        stock="005930" if pin=="a"*64 else "000660"
        assert decision_at>=NOW
        assert directory[1]==PIN
        return {
            "stock_code":stock,
            "corp_code":SECTOR[stock][1],
            "current_dart_industry_code":SECTOR[stock][0],
            "current_dart_listed_class":"Y",
            "first_local_received_at_utc":"2026-10-13T10:10:00+00:00",
            "historic_industry_pit_certified":False,
        }
    monkeypatch.setattr(industry,"verify_company_profile",verified)
    return {"a"*64:tmp_path/"src_a","b"*64:tmp_path/"src_b"}


def run(real_source_witness, basic=None, metadata=None, when=NOW):
    return industry.build_industry_peers(
        basic if basic is not None else base(),
        metadata if metadata is not None else cohort(),
        originals=real_source_witness,
        directory=(Path("/validated/issuer-directory"),PIN),decision_at=when)


def test_current_sector_subcodes_grouped_by_two_digit_division_with_actual_two_companies(real_source_witness):
    result=run(real_source_witness)
    assert result["selected_companies"]==2
    assert result["verified_current_industries"]==2
    assert result["verified_industry_divisions"]==1
    assert result["selected_multi_company_peer_groups"]==1
    assert result["companies_with_real_peer"]==2
    assert result["current_industry_groups"][0]["industry_division_code"]=="26"
    by_code={row["stock_code"]:row for row in result["companies"]}
    assert by_code["005930"]["revenue_yoy_peer_position"]==1
    assert by_code["000660"]["revenue_yoy_peer_position"]==2
    assert by_code["005930"]["return_3m_peer_position"]==1
    assert all(row["official_leader"] is False and row["total_score_100"] is None
               for row in result["companies"])
    assert result["full_investment_priority_ranking_ready"] is False
    assert result["official_industry_full_market_growth_ready"] is False


def test_html_labels_two_digit_comparison_is_not_full_market_leader(real_source_witness):
    result=run(real_source_witness)
    html=industry.render_industry_peers(result)
    assert "산업 대분류" in html
    assert "대분류가 같아도 직접 경쟁사가 아닐 수 있습니다" in html
    assert "000660" in html and "005930" in html
    assert "전체 순위" not in html or "업종 전체 순위는 아닙니다" in html
    assert "투자 우선순위 N/A" in html


def test_industry_missing_is_na_no_ranks(real_source_witness):
    metadata=cohort()
    metadata["companies"][0]={
        "stock_code":"005930","status":"PROFILE_NOT_CAPTURED",
        "pit_certified":False,
        "first_receipt_sha256":None,
        "current_dart_industry_code":None
    }
    report=run(real_source_witness,metadata=metadata)
    rows={row["stock_code"]:row for row in report["companies"]}
    assert rows["005930"]["industry_division_code"] is None
    assert rows["005930"]["revenue_yoy_peer_position"] is None
    assert rows["000660"]["revenue_yoy_peer_position"] is None
    assert rows["000660"]["peer_cohort_size"]==1
    assert report["companies_with_real_peer"]==0
    assert "N/A" in industry.render_industry_peers(report)


def test_exact_source_SHA_and_realtime_availability_required(real_source_witness):
    manifest=cohort()
    manifest["companies"][0]["first_receipt_sha256"]="e"*64
    with pytest.raises(ValueError,match="first DART company receipt"):
        run(real_source_witness,metadata=manifest)
    with pytest.raises(ValueError,match="not yet observed"):
        run(real_source_witness,when=datetime(2026,10,13,9,tzinfo=timezone.utc))


@pytest.mark.parametrize("alter",[
    "duplicate_profile","stale_candidate_sha","future_rank_claim","issuer_receipt_time",
    "different_directory","future_company_count",
])
def test_mismatched_industry_or_rank_claim_blocks_publication(real_source_witness,alter):
    manifest=cohort()
    baseline=base()
    if alter=="duplicate_profile":
        manifest["companies"][1]["stock_code"]="005930"
    elif alter=="stale_candidate_sha":
        baseline["comparisons"][0]["revenue_yoy"]=99999
    elif alter=="future_rank_claim":
        baseline["comparisons"][0]["total_score_100"]=80
        former=baseline.pop("content_sha256")
        baseline["content_sha256"]=sha256(industry._canonical(
            {key:val for key,val in baseline.items() if key!="content_sha256"})).hexdigest()
    elif alter=="issuer_receipt_time":
        manifest["companies"][0]["first_local_received_at_utc"]="2026-10-14T10:00:00Z"
    elif alter=="different_directory":
        manifest["source_directory_sha256"]="c"*64
    elif alter=="future_company_count":
        manifest["companies_requested"]=4
    with pytest.raises(ValueError):
        run(real_source_witness,basic=baseline,metadata=manifest)


def test_sha_protected_report_rejects_html_modification(real_source_witness):
    report=run(real_source_witness)
    altered=deepcopy(report)
    altered["companies"][0]["revenue_yoy"]=20
    with pytest.raises(ValueError,match="SHA"):
        industry.render_industry_peers(altered)


def test_unsafe_company_name_escaped_even_with_valid_original_sha(real_source_witness):
    baseline=base()
    baseline["comparisons"][0]["name"]="<script>bad()</script>"
    without={key:val for key,val in baseline.items() if key!="content_sha256"}
    baseline["content_sha256"]=sha256(industry._canonical(without)).hexdigest()
    doc=industry.render_industry_peers(run(real_source_witness,basic=baseline))
    assert "<script>" not in doc
    assert "&lt;script&gt;" in doc



@pytest.fixture
def site_sources(real_source_witness,tmp_path,monkeypatch):
    from scripts import publish_dart_industry_peers as deliver
    def save(name,obj):
        path=tmp_path/name
        path.write_text(json.dumps(obj,ensure_ascii=False))
        return path
    basic_file=save("candidates.json",base())
    profiles_file=save("industry.json",cohort())
    official_file=save("official.json",{
        "schema":"eraleader.official_api_pit_research_bridge.v1",
        "official_leaders":0,"historic_universe_pit_verified":False,
        "dart_current_directory":{"first_receipt_sha256":PIN},
    })
    raw=tmp_path/"private";raw.mkdir(mode=0o700)
    site=tmp_path/"result"/"site";site.mkdir(parents=True)
    for file in ("index.html","kr.html","basic_candidates_kr.html"):
        (site/file).write_text(
            "<!doctype html><html lang='ko'><body><main><h1>Original price"
            "</h1></main></body></html>")
    monkeypatch.setattr(deliver,"_all_pinned",
        lambda *_:{PIN:tmp_path/"company_original",**real_source_witness})
    original_builder=deliver.build_industry_peers
    monkeypatch.setattr(deliver,"build_industry_peers",
        lambda *a,**kw:original_builder(*a,**kw,decision_at=NOW))
    return {
        "candidate_file":basic_file,
        "industry_manifest":profiles_file,
        "official_evidence":official_file,
        "private_root":raw,
        "existing_site":site,
    }


def test_peer_panel_attaches_real_standalone_page_without_modifying_WATCH_data(site_sources):
    from scripts.publish_dart_industry_peers import publish
    result=publish(**site_sources)
    assert result["companies"]==2
    assert result["multi_company_divisions"]==1
    assert result["companies_with_division_peer"]==2
    assert result["real_investment_leader_ranking"] is False
    site=site_sources["existing_site"]
    assert "000660" in (site/"industry_peers_kr.html").read_text()
    assert json.loads((site.parent/"industry_peers_kr.json").read_text())[
        "selected_multi_company_peer_groups"]==1
    for name in ("index.html","kr.html","basic_candidates_kr.html"):
        page=(site/name).read_text()
        assert "Original price" in page
        assert "industry_peers_kr.html" in page
    old={(site/name):(site/name).read_bytes() for name in (
        "index.html","kr.html","basic_candidates_kr.html")}
    with pytest.raises(FileExistsError):
        publish(**site_sources)
    assert all(path.read_bytes()==value for path,value in old.items())


def test_peer_publication_wrong_official_directory_pin_fails_without_pages(site_sources):
    from scripts.publish_dart_industry_peers import publish
    info=json.loads(site_sources["official_evidence"].read_text())
    info["dart_current_directory"]["first_receipt_sha256"]="e"*64
    site_sources["official_evidence"].write_text(json.dumps(info))
    with pytest.raises(ValueError,match="directory original SHA"):
        publish(**site_sources)
    site=site_sources["existing_site"]
    assert not (site/"industry_peers_kr.html").exists()
    assert not (site.parent/"industry_peers_kr.json").exists()


def test_bad_existing_price_page_rejected_before_publication(site_sources):
    from scripts.publish_dart_industry_peers import publish
    site=site_sources["existing_site"]
    (site/"kr.html").write_text("<html>No body close</html>")
    with pytest.raises(ValueError,match="Existing research page"):
        publish(**site_sources)
    assert not (site/"industry_peers_kr.html").exists()
    assert "industry_peers_kr.html" not in (site/"index.html").read_text()
