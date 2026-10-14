"""Immutable original-date Kiwoom DEMO flow witness for saved marketwide stocks.

It fetches at most ONE already-researched code per explicit invocation.
Never modifies SharedBrokerAPI or previously saved aggregate research files.
No independently certified historic availability or brokerage authorization.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re

from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search
from .marketwide_flow_coverage import summarize_flow_coverage
from .official_company_explorer import canonical
from .kiwoom_investor_flow import shares

SCHEMA="eraleader.kr_kiwoom_dated_selected_flow.v1"
FOLDER="marketwide_dated_flow"
MAX_ROWS=20
CODE=re.compile(r"[0-9]{6}\Z")


def _instant(value):
    if type(value) is not str:
        raise ValueError("DATED_FLOW_RECEIPT_TIME_INVALID")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("DATED_FLOW_RECEIPT_TIME_INVALID") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("DATED_FLOW_RECEIPT_TIME_UNAWARE")
    return dt.astimezone(timezone.utc)


def _input(*,marketwide:Path,project:Path,clock:datetime):
    report,_=_source(marketwide)
    day=clock.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    view,_=prepare_search(report,request_day=day,clock=clock)
    coverage=summarize_flow_coverage(marketwide=marketwide,project=project,clock=clock)
    if (coverage["source_marketwide_sha256"]!=report["content_sha256"] or
            coverage["source_market_session"]!=report["market_session"] or
            coverage["orders_enabled"] is not False or
            coverage["mode"]!="demo"):
        raise ValueError("DATED_FLOW_COVERAGE_MISMATCH")
    return report,view,coverage


def _destination(project:Path, report:dict, code:str)->Path:
    return (_owned_output(project)/FOLDER/
            ("KR_"+report["market_session"].replace("-","")+"_"
             +report["content_sha256"][:16]+"_"+code+".json"))


def read_dated_flow(path:Path,*,expected_code:str|None=None,
                    expected_source:str|None=None,
                    clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DATED_FLOW_CLOCK_UNAWARE")
    if (not path.is_absolute() or path.is_symlink() or
            any(part.is_symlink() for part in path.parents) or
            not path.is_file() or path.stat().st_uid!=os.geteuid()
            or not 400<path.stat().st_size<20_000):
        raise ValueError("DATED_FLOW_FILE_UNSAFE")
    raw=path.read_bytes()
    obj=json.loads(raw)
    if type(obj) is not dict or raw!=canonical(obj)+b"\n":
        raise ValueError("DATED_FLOW_NOT_CANONICAL")
    unsigned=dict(obj)
    digest=unsigned.pop("content_sha256",None)
    if (type(digest) is not str or digest!=sha256(canonical(unsigned)).hexdigest()
            or obj.get("schema")!=SCHEMA or obj.get("market")!="KR"
            or obj.get("mode")!="demo" or obj.get("orders_enabled") is not False
            or obj.get("historical_pit_certified") is not False
            or obj.get("formal_leaders")!=0
            or obj.get("flow_score_10") is not None
            or type(obj.get("stock_code")) is not str
            or not CODE.fullmatch(obj["stock_code"])
            or expected_code not in (None,obj["stock_code"])
            or expected_source not in (None,obj.get("source_marketwide_sha256"))):
        raise ValueError("DATED_FLOW_CONTRACT_INVALID")
    received=_instant(obj.get("first_gateway_received_at_utc"))
    accepted=_instant(obj.get("recorded_at_utc"))
    if received>accepted or accepted>now.astimezone(timezone.utc):
        raise ValueError("DATED_FLOW_RECEIPT_FUTURE")
    sessions=obj.get("rows")
    if type(sessions) is not list or len(sessions)!=MAX_ROWS:
        raise ValueError("DATED_FLOW_ROWS_INCOMPLETE")
    previous=None
    for row in sessions:
        if (type(row) is not dict or set(row)!={
                "session","foreign_net_shares","institution_net_shares"}):
            raise ValueError("DATED_FLOW_ROW_SCHEMA")
        dt=date.fromisoformat(row["session"])
        if (dt>date.fromisoformat(obj["source_market_session"]) or
                previous is not None and dt>=previous or
                any(v is not None and type(v) is not int
                    for v in (row["foreign_net_shares"],row["institution_net_shares"]))):
            raise ValueError("DATED_FLOW_ORDER_OR_QUANTITY")
        previous=dt
    return obj


def plan_dated_capture(*,marketwide:Path,project:Path,
                       stock_code:str,clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DATED_FLOW_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    if type(stock_code) is not str or not CODE.fullmatch(stock_code):
        raise ValueError("DATED_FLOW_SELECTED_CODE_REQUIRED")
    report,view,coverage=_input(marketwide=marketwide,project=project,clock=now)
    known={r["security_id"]:r for r in coverage["rows"]}
    if stock_code not in known or known[stock_code]["has_20_observed_sessions"] is not True:
        raise ValueError("DATED_FLOW_NO_PREVIOUS_20_ROW_RECEIPT")
    if view["stale_warning"]:
        return {"status":"DATED_FLOW_SOURCE_STALE_HOLD","stock_code":stock_code,
                "api_calls":0,"orders_enabled":False}
    target=_destination(project,report,stock_code)
    if target.is_symlink():
        raise ValueError("DATED_FLOW_DESTINATION_SYMLINK")
    if target.exists():
        saved=read_dated_flow(target,expected_code=stock_code,
                              expected_source=report["content_sha256"],clock=now)
        if saved["prior_research_sha256"]!=known[stock_code]["original_research_sha256"]:
            raise ValueError("DATED_FLOW_PREVIOUS_RECEIPT_MISMATCH")
        status="DATED_FLOW_ALREADY_CAPTURED"
    else:
        status="DATED_FLOW_READY_DEMO_ONE_CODE"
    return {
        "status":status,"stock_code":stock_code,
        "market_session":report["market_session"],
        "source_marketwide_sha256":report["content_sha256"],
        "previous_research_sha256":known[stock_code]["original_research_sha256"],
        "file":str(target),
        "api_calls":0,"orders_enabled":False,
    }


def capture_dated_flow(*,marketwide:Path,project:Path,
                       stock_code:str,client,
                       clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DATED_FLOW_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    previous=plan_dated_capture(marketwide=marketwide,project=project,
                                stock_code=stock_code,clock=now)
    if previous["status"]!="DATED_FLOW_READY_DEMO_ONE_CODE":
        return previous
    if (getattr(client,"project",None)!="eraleader"
            or not callable(getattr(client,"investor_flow_page",None))
            or not callable(getattr(client,"status",None))):
        raise ValueError("DATED_FLOW_GATEWAY_CLIENT_REQUIRED")
    status=client.status()
    if (type(status) is not dict or status.get("orders_enabled") is not False or
            status.get("configured",{}).get("demo") is not True):
        raise ValueError("DATED_FLOW_NO_READONLY_DEMO")
    market_day=previous["market_session"].replace("-","")
    page=client.investor_flow_page(stock_code=stock_code,day=market_day,
                                   mode="demo",cursor=None)
    from shared_broker_api.gateway import compact
    if (type(page) is not dict or page.get("source")!="KIWOOM_KA10059"
            or page.get("mode")!="demo" or page.get("stock_code")!=stock_code
            or page.get("requested_day")!=market_day
            or page.get("orders_enabled") is not False
            or type(page.get("response")) is not dict
            or page["response"].get("return_code")!=0
            or sha256(compact(page["response"])).hexdigest()!=page.get("response_sha256")
            or type(page.get("headers")) is not dict
            or page["headers"].get("cont-yn") not in ("Y","N")):
        raise ValueError("DATED_FLOW_PROVIDER_SHA_OR_IDENTITY_INVALID")
    receipt=_instant(page.get("first_gateway_received_utc"))
    accepted=now if clock is not None else datetime.now(timezone.utc)
    if receipt>accepted:
        raise ValueError("DATED_FLOW_RECEIPT_AFTER_DECISION")
    raw_rows=page["response"].get("stk_invsr_orgn")
    if type(raw_rows) is not list or len(raw_rows)<MAX_ROWS:
        raise ValueError("DATED_FLOW_FEWER_THAN_20_ROWS")
    selected=[]
    previous_day=None
    for raw in raw_rows[:MAX_ROWS]:
        if type(raw) is not dict or type(raw.get("dt")) is not str or not re.fullmatch(r"[0-9]{8}",raw["dt"]):
            raise ValueError("DATED_FLOW_ROW_INVALID")
        session=date.fromisoformat(raw["dt"][:4]+"-"+raw["dt"][4:6]+"-"+raw["dt"][6:])
        if (session>date.fromisoformat(previous["market_session"]) or
                previous_day is not None and session>=previous_day):
            raise ValueError("DATED_FLOW_NEWEST_FIRST_REQUIRED")
        previous_day=session
        selected.append({
            "session":session.isoformat(),
            "foreign_net_shares":shares(raw.get("frgnr_invsr")),
            "institution_net_shares":shares(raw.get("orgn")),
        })
    if selected[0]["session"]!=previous["market_session"]:
        raise ValueError("DATED_FLOW_MARKET_DAY_NOT_RETURNED")
    report,_,coverage=_input(marketwide=marketwide,project=project,clock=accepted)
    matched=next(r for r in coverage["rows"] if r["security_id"]==stock_code)
    for actor,source_key in (("foreign","foreign"),("institution","institution")):
        vals=[r[actor+"_net_shares"] for r in selected]
        for n in (5,20):
            if any(v is None for v in vals[:n]) or sum(vals[:n])!=matched[
                    source_key+"_net_"+str(n)+"_shares"]:
                raise ValueError("DATED_FLOW_CANNOT_MATCH_ORIGINAL_AGGREGATE")
    if report["content_sha256"]!=previous["source_marketwide_sha256"]:
        raise ValueError("DATED_FLOW_KRX_SOURCE_REVISED")
    result={
        "schema":SCHEMA,"market":"KR","mode":"demo",
        "source_market_session":previous["market_session"],
        "source_marketwide_sha256":previous["source_marketwide_sha256"],
        "stock_code":stock_code,
        "prior_research_sha256":previous["previous_research_sha256"],
        "page_response_sha256":page["response_sha256"],
        "first_gateway_received_at_utc":receipt.isoformat(),
        "recorded_at_utc":accepted.isoformat(),
        "original_page_had_more_rows":len(raw_rows)>MAX_ROWS,
        "rows":selected,
        "historical_pit_certified":False,
        "formal_leaders":0,"flow_score_10":None,
        "orders_enabled":False,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    dest=Path(previous["file"])
    dest.parent.mkdir(mode=0o700,exist_ok=True)
    if dest.exists() or dest.is_symlink():
        raise ValueError("DATED_FLOW_PUBLICATION_RACE")
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as file:
        file.write(canonical(result)+b"\n")
        file.flush()
        os.fsync(file.fileno())
    return {"status":"DATED_FLOW_CAPTURED_DEMO_RESEARCH",
            "stock_code":stock_code,"row_count":len(selected),
            "file":str(dest),"api_calls":1,
            "orders_enabled":False,"historical_pit_certified":False}
