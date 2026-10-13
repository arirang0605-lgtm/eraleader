"""Selected-stock flow publication remains read-only and does not re-rank."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from test_kiwoom_investor_flow import fixtures, flow
from eraleader.kiwoom_investor_flow import canonical
from scripts.publish_kiwoom_flow_overlay import publish, read_flows
from scripts.capture_kiwoom_investor_flow import capture


def as_file(path, obj):
    path.write_bytes(canonical(obj)+b"\n")
    return path


def sample_pages(root):
    site=root/"site";site.mkdir()
    for name in ("index.html","basic_candidates_kr.html","industry_peers_kr.html"):
        as_file(site/name, {}) if False else (site/name).write_text(
            "<!doctype html><html><body><main>ORIGINAL_MARKET_ANALYSIS"
            "</main></body></html>")
    a,b=fixtures()
    candidate=as_file(root/"candidate.json",a)
    peer=as_file(root/"industry.json",b)
    return candidate,peer,site


def test_publish_zero_flow_as_honest_NA_and_preserve_existing_prices(tmp_path):
    candidate,industry,site=sample_pages(tmp_path)
    original={name:(site/name).read_bytes() for name in
              ("index.html","basic_candidates_kr.html","industry_peers_kr.html")}
    result=publish(candidates=candidate,industries=industry,site=site,
                   clock=datetime(2026,10,13,9,tzinfo=timezone.utc))
    assert result["selected_companies"]==2
    assert result["kiwoom_received"]==0
    assert result["official_leaders"]==0
    assert result["orders"]==0
    html=(site/"investor_flow_kr.html").read_text()
    assert "N/A" in html
    assert "http://127.0.0.1:8782/" in html
    assert "실전 주문 0" in html
    for name,old in original.items():
        after=(site/name).read_bytes()
        assert after.count(b"ORIGINAL_MARKET_ANALYSIS")==1
        assert b"investor_flow_kr.html" in after
        assert b"http://127.0.0.1:8782/" in after
        assert after.replace(after[after.find(b"<p><a href="):after.find(b"</p>")+4],b"") == old
    with pytest.raises(FileExistsError):
        publish(candidates=candidate,industries=industry,site=site,
                clock=datetime(2026,10,13,9,tzinfo=timezone.utc))


def test_capture_mock_is_private_and_manifest_receipts_verify(tmp_path):
    calls=[]
    report=flow()
    report["source_first_locally_received_at_utc"]=datetime.now(timezone.utc).isoformat()
    report.pop("content_sha256")
    report["content_sha256"]=sha256(canonical(report)).hexdigest()
    def fake_fetch(*,code,as_of,token,environment_mode,post):
        calls.append((code,as_of,environment_mode))
        assert environment_mode=="demo"
        assert token=="ONLY_TEST_FAKE"
        return report
    path=tmp_path/"protected"/"capture"
    path.parent.mkdir(mode=0o700)
    result=capture(codes=["005930"],market_day="20261008",out=path,
                   token="ONLY_TEST_FAKE",environment_mode="demo",fetch=fake_fetch)
    assert result["companies"]==1 and result["official_investment_ranking"] is False
    records=read_flows(path/"manifest.json")
    assert records["005930"]["content_sha256"]==report["content_sha256"]
    assert calls==[("005930","20261008","demo")]
    assert not any("ONLY_TEST_FAKE" in x.read_text()
                   for x in path.glob("*.json"))
    with pytest.raises(ValueError):
        capture(codes=["005930"],market_day="20261008",out=path,
                token="ONLY_TEST_FAKE",environment_mode="demo",fetch=fake_fetch)
    as_bytes=(path/"005930.json").read_bytes()
    (path/"005930.json").write_bytes(as_bytes+b" ")
    with pytest.raises(ValueError):
        read_flows(path/"manifest.json")


def test_capture_cannot_override_mode_or_partial_publish(tmp_path):
    def failing(**kwargs):raise ValueError("synthetic broker error")
    path=tmp_path/"private"/"capture";path.parent.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        capture(codes=["005930","000660"],market_day="20261008",out=path,
                token="NO_LIVE",environment_mode="real",fetch=failing)
    assert not path.exists()
    assert list(path.parent.iterdir())==[]
    with pytest.raises(ValueError):
        capture(codes=["005930"],market_day="20261008",out=path,
                token="NO_LIVE",environment_mode="other",fetch=failing)
