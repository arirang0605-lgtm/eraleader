"""Official DART financial CFS, mock JSON from pinned current directory only."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from urllib.parse import parse_qs,urlsplit
import json,pytest

from eraleader.official_dart_corp_directory import capture_dart_corp_directory
from eraleader.official_dart_financials import (
  capture_dart_financial,verify_dart_financial,annual_growth_diagnostic,
  parse_dart_financial,
)

NOW=datetime(2026,10,12,12,0,tzinfo=timezone.utc)
CREDS={"ERALEADER_DART_API_KEY":"A"*40}

def zipped():
 b=BytesIO()
 with ZipFile(b,"w") as z:
  z.writestr("CORPCODE.xml","<result><list><corp_code>00126380</corp_code>"
             "<stock_code>005930</stock_code><modify_date>20261011</modify_date>"
             "</list></result>")
 return b.getvalue()


@pytest.fixture
def setup(tmp_path):
 root=tmp_path/"private";root.mkdir(mode=0o700);root.chmod(0o700)
 d=capture_dart_corp_directory(root,creds=CREDS,fetch=lambda *_:zipped(),clock=lambda:NOW)
 return root,(root/d["capture_id"],d["first_receipt_sha256"])

def statement(year=2025,amount="12,000"):
 return {"status":"000","list":[{
  "corp_code":"00126380","bsns_year":str(year),"reprt_code":"11011",
  "rcept_no":f"{year+1}0109000001","account_id":"ifrs-full_Revenue",
  "account_detail":"-","sj_div":"IS","currency":"KRW",
  "thstrm_amount":amount,
 },{
  "corp_code":"00126380","bsns_year":str(year),"reprt_code":"11011",
  "rcept_no":f"{year+1}0109000001","account_id":"dart_OperatingIncomeLoss",
  "account_detail":"-","sj_div":"IS","currency":"KRW",
  "thstrm_amount":"1,300",
 }]}
# Filing numbers exactly 14 digits


def test_dart_two_year_revenue_first_receipt_yoy(setup):
 root,directory=setup
 def fetch(url,_headers):
  y=int(parse_qs(urlsplit(url).query)["bsns_year"][0])
  return json.dumps(statement(y,"10,000" if y==2024 else "12,000")).encode()
 past=capture_dart_financial(root,stock_code="005930",directory=directory,
                year=2024,report="11011",creds=CREDS,fetch=fetch,
                clock=lambda:NOW+timedelta(seconds=2))
 current=capture_dart_financial(root,stock_code="005930",directory=directory,
                year=2025,report="11011",creds=CREDS,fetch=fetch,
                clock=lambda:NOW+timedelta(seconds=3))
 a=verify_dart_financial(root/past["capture_id"],past["first_receipt_sha256"],
                         decision_at=NOW+timedelta(seconds=4),directory=directory)
 b=verify_dart_financial(root/current["capture_id"],current["first_receipt_sha256"],
                         decision_at=NOW+timedelta(seconds=4),directory=directory)
 report=annual_growth_diagnostic(a,b)
 assert report["research_metrics"]["revenue_yoy"]==pytest.approx(.2)
 assert report["prospective_backtest_eligible"] is False
 assert b["metrics"]["revenue"]["unit"]=="KRW"
 with pytest.raises(ValueError,match="not locally available"):
  verify_dart_financial(root/current["capture_id"],current["first_receipt_sha256"],
                         decision_at=NOW, directory=directory)


def test_unknown_company_blocks_before_http(setup):
 root,directory=setup
 with pytest.raises(ValueError,match="missing or ambiguous"):
  capture_dart_financial(root,stock_code="999999",directory=directory,year=2025,
    report="11011",creds=CREDS,fetch=lambda *_:pytest.fail("fetched"),clock=lambda:NOW)


@pytest.mark.parametrize("change,expected",[
 ({"bsns_year":"2024"},"report or receipt"),
 ({"corp_code":"00000000"},"report or receipt"),
 ({"thstrm_amount":"not-money"},"amount"),
 ({"rcept_no":"wrong"},"report or receipt"),
])
def test_invalid_financial_fails_closed(setup,change,expected):
 root,directory=setup
 bad=statement()
 bad["list"][0].update(change)
 with pytest.raises(ValueError,match=expected):
  capture_dart_financial(root,stock_code="005930",directory=directory,
   year=2025,report="11011",creds=CREDS,fetch=lambda *_:json.dumps(bad).encode(),
   clock=lambda:NOW)
 assert not list(root.glob("dart_fin_*"))


def test_duplicate_json_and_wrong_report_rejected():
 payload=b'{"status":"000","status":"000","list":[]}'
 with pytest.raises(ValueError,match="JSON invalid"):
  parse_dart_financial(payload,corp_code="00126380",year=2025,report="11011")
 with pytest.raises(ValueError,match="annual growth"):
  annual_growth_diagnostic({"stock_code":"A","corp_code":"1","year":2022,
                             "report_code":"11012"},{
   "stock_code":"A","corp_code":"1","year":2025,"report_code":"11011"})
