"""Integrated first-watch research with synthetic HTTP responses, never live."""
from __future__ import annotations
from datetime import datetime, timezone
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from hashlib import sha256
import json
import pandas as pd
import pytest

from eraleader import official_kr_daily_pipeline as workflow
from eraleader import official_api_pit_bridge as bridge

NOW=datetime(2026,10,12,11,15,tzinfo=timezone.utc)
DAY="2026-10-08"
CREDS={"ERALEADER_KRX_AUTH_KEY":"A"*40,
       "ERALEADER_DART_API_KEY":"B"*40}

@pytest.fixture
def folders(tmp_path):
    root=tmp_path/"private"
    root.mkdir(mode=0o700);root.chmod(0o700)
    return root,tmp_path/"new_research"

@pytest.fixture
def price_cache(monkeypatch):
    dates=pd.bdate_range(end="2026-10-02",periods=270)
    records=[]
    for code in ("005930","A23456"):
        for i,dt in enumerate(dates):
            close=9000+i*3
            records.append(dict(security_id=code,name=code,venue="OLD_UNVERIFIED",
                session=dt,open=close,high=close+200,low=close-200,
                close=close,volume=100,turnover=close*100,market_cap=10000000))
    df=pd.DataFrame(records)
    monkeypatch.setattr(bridge,"read_market_bars",lambda *args,**kwargs:
                        (df.copy(),{"source":"fake old readonly historical price"}))

def fetch(url,headers,*,mutate=False):
    split=urlsplit(url);query=parse_qs(split.query)
    if "stk_bydd" in split.path or "ksq_bydd" in split.path:
        code="005930" if "stk_bydd" in split.path else "A23456"
        return json.dumps({"OutBlock_1":[{
            "BAS_DD":"20261008","ISU_CD":code,"ISU_NM":code,
            "TDD_OPNPRC":"11,000","TDD_HGPRC":"12,000",
            "TDD_LWPRC":"10,000","TDD_CLSPRC":"11,500",
            "ACC_TRDVOL":"1,000","ACC_TRDVAL":"11,500,000",
            "MKTCAP":"500,000,000"}]}).encode()
    assert split.path.endswith("/list.json")
    pg=int(query.get("page_no",["1"])[0])
    low=(pg-1)*100+1
    rows=[{"rcept_no":f"{x:014d}","rcept_dt":"20261008",
           "corp_code":"00126380", "stock_code":"005930"}
          for x in range(low,min(pg*100,201)+1)]
    if mutate and pg==3:rows[0]["rcept_no"]=f"{1:014d}"
    return json.dumps({"status":"000","total_count":"201",
          "page_no":str(pg),"page_count":"100","total_page":"3",
          "list":rows}).encode()

def test_full_one_shot_integrates_sources_and_runs_reports(folders,price_cache):
    cap,out=folders
    result=workflow.capture_and_publish_kr_day(
        trading_day=DAY,capture_root=cap,research_out=out,
        creds=CREDS,fetch=fetch,clock=lambda:NOW,top=2)
    assert result["api_observation_rows"]==2
    assert result["dart_disclosure_rows"]==201
    assert result["dart_pages"]==3 and result["captured_sources"]==5
    assert result["watch_rows"]==2 and result["reports"]==3
    assert result["official_leaders"]==0 and result["pit_certified"] is False
    assert result["live_messages"]==0
    assert Path(result["market_dashboard"]).is_file()
    assert Path(result["audit_dashboard"]).is_file()
    assert Path(result["market_dashboard"]).is_relative_to(out)
    assert Path(result["audit_dashboard"]).is_relative_to(out)
    assert not list(out.parent.glob(".official_kr_research_*"))
    assert len(list((out/"reports").glob("*.md")))==3
    assert len(list(cap.glob("first_*")))==3
    assert len(list(cap.glob("dart_full_*")))==1
    receipt=json.loads((out/"official_api_pit_research.json").read_text())
    assert receipt["dart_full_day"]["row_count"]==201
    assert receipt["dart_full_day"]["issuer_links"]["issuer_class_pit_certified"] is False
    assert sha256((out/"site"/"official_api.html").read_bytes()).hexdigest()
    assert "201" in (out/"site"/"official_api.html").read_text()
    assert len(json.loads((out/"alerts_preview.json").read_text()))==2
    with pytest.raises(ValueError,match="new absolute"):
        workflow.capture_and_publish_kr_day(
            trading_day=DAY,capture_root=cap,research_out=out,
            creds=CREDS,fetch=lambda *_:pytest.fail("network on existing output"),
            clock=lambda:NOW,top=2)


def test_late_report_error_never_publishes_partial_watch(folders,price_cache,monkeypatch):
    cap,out=folders
    def fail_during_report(_snapshot,staged):
        (staged/"incomplete.html").write_text("NOT FOR PUBLICATION")
        raise RuntimeError("research report failed after partial writes")
    monkeypatch.setattr(workflow,"run_official_research",fail_during_report)
    with pytest.raises(RuntimeError,match="report failed"):
        workflow.capture_and_publish_kr_day(
            trading_day=DAY,capture_root=cap,research_out=out,
            creds=CREDS,fetch=fetch,clock=lambda:NOW,top=2)
    assert not out.exists()
    assert not list(out.parent.glob(".official_kr_research_*"))
    assert len(list(cap.glob("first_*")))==3
    assert len(list(cap.glob("dart_full_*")))==1


def test_destination_race_preserves_existing_user_files(folders,price_cache,monkeypatch):
    cap,out=folders
    def raced(_snapshot,staged):
        (staged/"site").mkdir()
        (staged/"site"/"kr.html").write_text("temporary")
        (staged/"site"/"official_api.html").write_text("temporary")
        out.mkdir()
        (out/"keep.txt").write_text("user content")
        return {"market_dashboard":str(staged/"site"/"kr.html"),
                "dashboard":str(staged/"site"/"official_api.html")}
    monkeypatch.setattr(workflow,"run_official_research",raced)
    with pytest.raises(ValueError,match="destination appeared"):
        workflow.capture_and_publish_kr_day(
            trading_day=DAY,capture_root=cap,research_out=out,
            creds=CREDS,fetch=fetch,clock=lambda:NOW,top=2)
    assert (out/"keep.txt").read_text()=="user content"
    assert not list(out.parent.glob(".official_kr_research_*"))


def test_page_duplicate_blocks_publication_but_preserves_private_originals(folders,price_cache):
    cap,out=folders
    with pytest.raises(ValueError,match="duplicate disclosure"):
        workflow.capture_and_publish_kr_day(
            trading_day=DAY,capture_root=cap,research_out=out,
            creds=CREDS,fetch=lambda u,h:fetch(u,h,mutate=True),clock=lambda:NOW)
    assert not out.exists()
    assert len(list(cap.glob("first_*")))==3
    assert not list(cap.glob("dart_full_*"))


@pytest.mark.parametrize("bad_day", ["2026-10-13","2026-09-01"])
def test_expired_future_day_rejected_without_fetch(folders,bad_day):
    cap,out=folders
    with pytest.raises(ValueError,match="freshness"):
        workflow.capture_and_publish_kr_day(
            trading_day=bad_day,capture_root=cap,research_out=out,
            creds=CREDS,fetch=lambda *_:pytest.fail("fetched"),clock=lambda:NOW)
    assert not list(cap.iterdir())


def test_missing_credentials_blocks_no_partial_capture(folders):
    cap,out=folders
    with pytest.raises(ValueError,match="not configured"):
        workflow.capture_and_publish_kr_day(trading_day=DAY,capture_root=cap,
                         research_out=out,creds={},fetch=lambda *_:pytest.fail("network"),
                         clock=lambda:NOW)
    assert not list(cap.iterdir()) and not out.exists()


def test_current_day_before_19_kst_blocks(folders):
    cap,out=folders
    early=datetime(2026,10,12,1,0,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match="not yet closed"):
        workflow.capture_and_publish_kr_day(
            trading_day="2026-10-12",capture_root=cap,research_out=out,
            creds=CREDS,fetch=lambda *_:pytest.fail("fetched"),clock=lambda:early)
    assert not out.exists()


def test_existing_root_rejects_group_read(folders):
    cap,out=folders
    cap.chmod(0o755)
    with pytest.raises(ValueError,match="owner-only"):
        workflow.capture_and_publish_kr_day(
            trading_day=DAY,capture_root=cap,research_out=out,
            creds=CREDS,fetch=lambda *_:pytest.fail("fetched"),clock=lambda:NOW)
