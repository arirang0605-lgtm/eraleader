"""Actual contract E2E for a separately dated Kiwoom demo observation panel."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest

from test_kiwoom_investor_flow import fixtures
from eraleader.kiwoom_investor_flow import fetch_ka10059,canonical
from eraleader.kiwoom_live_research_panel import make_panel,render_panel,clean_session
from scripts.capture_kiwoom_investor_flow import capture
from scripts.publish_kiwoom_live_panel import publish

CLOCK=datetime(2026,10,13,11,tzinfo=timezone.utc)

def sample_flow():
    records=[]
    for i in range(25):
        date=(datetime(2026,10,13)-timedelta(days=i)).strftime("%Y%m%d")
        records.append({"dt":date,"frgnr_invsr":"+200","orgn":"-20"})
    def feed(_path,_body,_headers):
        return {"return_code":0,"stk_invsr_orgn":records},{"cont-yn":"Y","next-key":"older"}
    return fetch_ka10059(code="005930",as_of="20261013",token="FAKE",
                         post=feed,received_at=datetime(2026,10,13,7,tzinfo=timezone.utc),
                         max_pages=1,environment_mode="demo",recent_window_only=True)

def seeded_root(tmp_path):
    candidate,industry=fixtures()
    site=tmp_path/"site";site.mkdir()
    (site/"index.html").write_text("<!doctype html><body>BASELINE_CONTENT</body>")
    (tmp_path/"candidate.json").write_bytes(canonical(candidate)+b"\n")
    (tmp_path/"industry.json").write_bytes(canonical(industry)+b"\n")
    flow=sample_flow()
    manifest=tmp_path/"demo_manifest"
    capture(codes=["005930"],market_day="20261013",out=manifest,
            token="FIXTURE",environment_mode="demo",
            fetch=lambda **kw:flow,post=lambda *args: ({},{}))
    return (tmp_path/"candidate.json",tmp_path/"industry.json",
            manifest/"manifest.json",site,flow)

def test_live_panel_displays_actual_flow_but_baseline_day_never_joins():
    a,b=fixtures()
    report=make_panel(a,b,flows={"005930":sample_flow()},decision_at=CLOCK)
    row=report["observations"][0]
    assert row["observed_flow_session"]=="20261013"
    assert row["baseline_market_session"]=="20261008"
    assert row["baseline_session_equal"] is False
    assert row["flow_status"]=="DEMO_FLOW_DIFFERENT_SESSION_NOT_JOINED"
    assert row["foreign_net_5_shares"]==1000
    assert row["institution_net_20_shares"]==-400
    assert row["score_eligible"] is False
    assert row["trade_signal"] is None
    assert report["official_future_leaders"]==0
    assert report["investment_ranking_available"] is False
    assert report["orders_enabled"] is False
    html=render_panel(report)
    assert "20261013" in html and "20261008" in html
    assert "모의투자" in html and "금지" in html

def test_publish_atomic_new_sidecar_and_one_existing_index_link(tmp_path):
    candidate,industry,manifest,site,_=seeded_root(tmp_path)
    original=(site/"index.html").read_bytes()
    result=publish(candidates=candidate,industries=industry,
                   flow_manifest=manifest,site=site,clock=CLOCK)
    assert result["status"]=="DEMO_INVESTOR_FLOW_RESEARCH_PUBLISHED"
    assert result["sessions_aligned"] is False
    assert result["scores_changed"] is False and result["orders"]==0
    path=site/result["path"]
    assert path.is_file()
    assert "DEMO_FLOW_DIFFERENT_SESSION_NOT_JOINED" in path.read_text()
    assert (site/"kiwoom_demo_20261013"/"report.json").is_file()
    current=(site/"index.html").read_bytes()
    assert b"BASELINE_CONTENT" in current
    assert current.count(b"kiwoom_demo_20261013")==1
    assert original not in (b"",current)
    with pytest.raises(FileExistsError):
        publish(candidates=candidate,industries=industry,
                flow_manifest=manifest,site=site,clock=CLOCK)

def test_tampered_original_provider_sha_blocks_before_any_publication(tmp_path):
    candidate,industry,manifest,site,_=seeded_root(tmp_path)
    report=manifest.parent/"005930.json"
    report.write_bytes(report.read_bytes()+b" ")
    with pytest.raises(ValueError):
        publish(candidates=candidate,industries=industry,
                flow_manifest=manifest,site=site,clock=CLOCK)
    assert not any(p.name.startswith("kiwoom_demo") for p in site.iterdir())
    assert "kiwoom_demo" not in (site/"index.html").read_text()

def test_future_first_received_time_denied():
    candidate,industry=fixtures()
    future=sample_flow()
    future["source_first_locally_received_at_utc"]=(CLOCK+timedelta(hours=1)).isoformat()
    future.pop("content_sha256")
    future["content_sha256"]=sha256(canonical(future)).hexdigest()
    with pytest.raises(ValueError):
        make_panel(candidate,industry,flows={"005930":future},decision_at=CLOCK)

def test_demo_live_never_accepts_real_profile_or_other_security():
    a,b=fixtures()
    report=sample_flow()
    report["environment_mode"]="real"
    report.pop("content_sha256")
    report["content_sha256"]=sha256(canonical(report)).hexdigest()
    with pytest.raises(ValueError):
        make_panel(a,b,flows={"005930":report},decision_at=CLOCK)
    with pytest.raises(ValueError):
        make_panel(a,b,flows={"000660":sample_flow()},decision_at=CLOCK)

@pytest.mark.parametrize("value,want", [
    ("2026-10-08","20261008"),("20261013","20261013"),
])
def test_normalize_krx_and_kiwoom_sessions(value,want):
    assert clean_session(value)==want

@pytest.mark.parametrize("bad", ["2026/10/13","20261344","2026-02-30",None])
def test_invalid_session_rejected(bad):
    with pytest.raises(ValueError):
        clean_session(bad)


def test_future_market_session_does_not_enter_current_panel():
    basic,industry=fixtures()
    future=sample_flow()
    future["requested_day"]="20261014"
    future.pop("content_sha256")
    future["content_sha256"]=sha256(canonical(future)).hexdigest()
    with pytest.raises(ValueError,match="Future live market session"):
        make_panel(basic,industry,flows={"005930":future},decision_at=CLOCK)


def test_noncurrent_observed_day_never_fake_zero_or_full_window():
    basic,industry=fixtures()
    stale=sample_flow()
    stale["latest_observed_day"]="20261012"
    stale.pop("content_sha256")
    stale["content_sha256"]=sha256(canonical(stale)).hexdigest()
    panel=make_panel(basic,industry,flows={"005930":stale},decision_at=CLOCK)
    row=panel["observations"][0]
    assert row["foreign_net_5_shares"] is None
    assert row["institution_net_20_shares"] is None
    assert row["score_eligible"] is False
