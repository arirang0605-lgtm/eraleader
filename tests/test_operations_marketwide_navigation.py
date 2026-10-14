"""6_2: Only owner-local versioned research search pages appear in operations nav."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from eraleader.official_company_explorer import canonical
from eraleader.operations_overview import audit_local_operations, render_operations_overview

NOW=datetime(2026,10,14,2,tzinfo=timezone.utc)


def publish_fixture(root:Path, date_tag="20261014", session="2026-10-08"):
    site=root/"output"/("marketwide_kr_search_"+date_tag)
    site.mkdir(parents=True)
    manifest={
        "schema":"eraleader.marketwide_local_search.v1",
        "market":"KR", "research_only":True,
        "official_leaders":0,"official_100_point_rank_available":False,
        "formal_selection":None,"observed_stocks":3,
        "research_50_scored":1,"source_market_session":session,
        "requested_day":date_tag[:4]+"-"+date_tag[4:6]+"-"+date_tag[6:],
        "published_at_utc":"2026-10-14T01:00:00+00:00",
        "stale_warning":True,
    }
    manifest["content_sha256"]=sha256(canonical(manifest)).hexdigest()
    (site/"manifest.json").write_bytes(canonical(manifest)+b"\n")
    page=('<html><script id="stock-meta" type="application/json">'
          +json.dumps(manifest,ensure_ascii=False)
          +'</script><script id="stock-data" type="application/json">'
          +'[{"security_id":"005930"}]</script></html>')
    (site/"index.html").write_text(page+"\n"+(" " * 1100),encoding="utf-8")
    return site


def test_search_menu_shows_market_session_and_research_warning(tmp_path):
    site=publish_fixture(tmp_path)
    snap=audit_local_operations(tmp_path,clock=NOW)
    entry=snap["kr_marketwide_search"]
    assert entry["href"]=="../../marketwide_kr_search_20261014/index.html"
    assert entry["market_session"]=="2026-10-08"
    assert entry["source_pit_certified"] is False
    page=render_operations_overview(snap)
    assert "한국시장 전체 종목 검색 열기" in page
    assert "자료 지연 / 오늘 시세 아님" in page
    assert "공인 대장주 확정이 아닙니다" in page
    assert site.joinpath("index.html").exists()


def test_no_search_page_keeps_operations_working(tmp_path):
    snap=audit_local_operations(tmp_path,clock=NOW)
    assert snap["kr_marketwide_search"] is None
    assert "N/A" in render_operations_overview(snap)


def test_modified_manifest_or_html_is_never_linked(tmp_path):
    site=publish_fixture(tmp_path)
    manifest=site/"manifest.json"
    orig=manifest.read_bytes()
    manifest.write_bytes(orig.replace(b'"observed_stocks":3',b'"observed_stocks":4'))
    assert audit_local_operations(tmp_path,clock=NOW)["kr_marketwide_search"] is None
    manifest.write_bytes(orig)
    html=site/"index.html"
    html.write_text(html.read_text().replace('"observed_stocks": 3','"observed_stocks": 4'))
    assert audit_local_operations(tmp_path,clock=NOW)["kr_marketwide_search"] is None


def test_symlink_output_is_not_linked(tmp_path):
    real=publish_fixture(tmp_path)
    target=tmp_path/"output"/"marketwide_kr_search_20261014"
    alias=tmp_path/"output"/"marketwide_kr_search_20261013"
    alias.symlink_to(real,target_is_directory=True)
    assert audit_local_operations(tmp_path,clock=NOW)["kr_marketwide_search"]["requested_day"]=="2026-10-14"
    target.rename(tmp_path/"outside")
    assert audit_local_operations(tmp_path,clock=NOW)["kr_marketwide_search"] is None


def test_unsafe_injected_navigation_link_rejected(tmp_path):
    snap=audit_local_operations(tmp_path,clock=NOW)
    snap["kr_marketwide_search"]={
        "href":"../../../../evil/index.html","market_session":"2026-10-08",
        "requested_day":"2026-10-14","observed_stocks":3,
        "partial_research_scored":1,"stale_warning":True,
        "source_pit_certified":False,
    }
    import pytest
    with pytest.raises(ValueError,match="Unsafe marketwide"):
        render_operations_overview(snap)
