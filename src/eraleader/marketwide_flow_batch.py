"""Incremental KR marketwide selected-stock flow batches via SharedBrokerAPI.

No broker account, trading, real mode, or inference of official flow score.
Plan-only default; explicit demo read, bounded one small batch at a time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import tempfile

from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source, prepare_search

SCHEMA="eraleader.kr_marketwide_demo_flow_batch.v1"
FOLDER="marketwide_flow_batches"
MAX_BATCH=5


def _checked_batch(path:Path, *, market:str, source_hash:str, now:datetime) -> dict:
    if (path.is_symlink() or not path.is_dir() or
            path.name.startswith(".") or
            any(p.is_symlink() for p in path.parents)):
        raise ValueError("FLOW_BATCH_UNSAFE_FOLDER")
    summary=path/"manifest.json"
    if (summary.is_symlink() or not summary.is_file()
            or not 100<summary.stat().st_size<1_000_000):
        raise ValueError("FLOW_BATCH_MANIFEST_MISSING_OR_UNSAFE")
    body=summary.read_bytes()
    data=json.loads(body)
    if (type(data) is not dict or body!=canonical(data)+b"\n"):
        raise ValueError("FLOW_BATCH_NONCANONICAL")
    proof=data.get("content_sha256")
    clone=dict(data)
    clone.pop("content_sha256",None)
    if (type(proof) is not str or
            proof!=sha256(canonical(clone)).hexdigest() or
            data.get("schema")!=SCHEMA or
            data.get("market")!="KR" or
            data.get("mode")!="demo" or
            data.get("source_market_session")!=market or
            data.get("source_marketwide_sha256")!=source_hash or
            data.get("orders_enabled") is not False or
            data.get("official_leaders")!=0 or
            data.get("research_only") is not True):
        raise ValueError("FLOW_BATCH_WRONG_OR_FORGED_SOURCE")
    stamp=datetime.fromisoformat(data["finished_at_utc"])
    if (stamp.tzinfo is None or stamp.utcoffset() is None
            or stamp.astimezone(timezone.utc)>now):
        raise ValueError("FLOW_BATCH_FUTURE_OR_UNAWARE")
    codes=data.get("stock_codes")
    records=data.get("items")
    if (type(codes) is not list or type(records) is not list
            or not 1<=len(codes)<=MAX_BATCH or len(codes)!=len(records)
            or len(set(codes))!=len(codes)
            or any(type(code) is not str or
                   re.fullmatch(r"[0-9]{6}",code) is None for code in codes)):
        raise ValueError("FLOW_BATCH_CODE_LIST_INVALID")
    if data.get("reported_20_observations")!=sum(
            bool(r.get("has_20_observations")) for r in records):
        raise ValueError("FLOW_BATCH_OBSERVATION_COUNT_MISMATCH")
    try:
        from shared_broker_api.gateway import compact
    except ImportError:
        compact=canonical
    for code,item in zip(codes,records):
        if (type(item) is not dict or item.get("stock_code")!=code
                or item.get("file")!=code+".json" or
                item.get("response_sha256") is None):
            raise ValueError("FLOW_BATCH_ROW_MISMATCH")
        file=path/(code+".json")
        if file.is_symlink() or not file.is_file() or file.stat().st_size>1_000_000:
            raise ValueError("FLOW_BATCH_MISSING_REPORT")
        content=file.read_bytes()
        report=json.loads(content)
        if content!=canonical(report)+b"\n":
            raise ValueError("FLOW_BATCH_REPORT_NONCANONICAL")
        unsigned=dict(report)
        digest=unsigned.pop("content_sha256",None)
        if (digest!=sha256(compact(unsigned)).hexdigest() or
                item["has_20_observations"] is not (
                    report.get("research_quality")=="UNVERIFIED_20_OBSERVED_SESSIONS") or
                item.get("observed_sessions")!=report.get("observed_sessions") or
                item.get("first_gateway_received_at_utc")!=report.get("first_gateway_received_at_utc") or
                report.get("historical_pit_certified") is not False or
                report.get("whole_market_foreign_flow_equivalent") is not False or
                report.get("trade_signal") is not None or
                report.get("schema")!="sharedbroker.selected_security_flow_research.v1"
                or report.get("stock_code")!=code or
                report.get("market_session")!=market.replace("-","") or
                report.get("mode")!="demo" or
                report.get("orders_enabled") is not False or
                digest!=item["response_sha256"] or
                report.get("units")!="shares" or
                report.get("project")!="eraleader"):
            raise ValueError("FLOW_BATCH_SAVED_FLOW_FORGED")
    return data


def plan_marketwide_flow(*,marketwide:Path,project:Path,
                         limit:int=MAX_BATCH, clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("FLOW_BATCH_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    if type(limit) is not int or not 1<=limit<=MAX_BATCH:
        raise ValueError("FLOW_BATCH_LIMIT_1_TO_5")
    output=_owned_output(project)
    source,_=_source(marketwide)
    from zoneinfo import ZoneInfo
    today=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    manifest,_=prepare_search(source,request_day=today,clock=now)
    if manifest["stale_warning"]:
        return {"status":"STALE_KR_MARKET_HOLD","market_session":source["market_session"],
                "new_codes":[],"already_collected":0,"api_calls":0,"orders_enabled":False}
    root=output/FOLDER
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("FLOW_BATCH_ROOT_UNSAFE")
    covered=set()
    if root.exists():
        for folder in sorted(root.iterdir()):
            if folder.name.startswith("."):continue
            # A different valid source version has its own publication set.
            if not folder.name.startswith("KR_"+source["market_session"].replace("-","")
                                          +"_"+source["content_sha256"][:16]+"_"):
                continue
            data=_checked_batch(folder,market=source["market_session"],
                                source_hash=source["content_sha256"],now=now)
            if any(code in covered for code in data["stock_codes"]):
                raise ValueError("FLOW_BATCH_DUPLICATE_PREVIOUS_CODE")
            covered.update(data["stock_codes"])
    candidates=[]
    for stock in source["securities"]:
        code=stock["security_id"]
        if (type(code) is not str or not re.fullmatch(r"[0-9]{6}",code)
                or stock["market_traded"] is not True):
            continue
        candidates.append(stock)
    # Research priority, NEVER investable/leadership ranking.
    candidates.sort(key=lambda row:(
        row["price_top20_watch_rank"] is None,
        row["price_top20_watch_rank"] or 9999,
        row["two_factor_research_rank"] is None,
        row["two_factor_research_rank"] or 9999,
        -(row["turnover"] or 0), row["security_id"]))
    eligible=[r["security_id"] for r in candidates if r["security_id"] not in covered]
    chosen=eligible[:limit]
    return {"status":("FLOW_BATCH_READY_DEMO_RESEARCH" if chosen else
                      "FLOW_BATCH_ALL_ELIGIBLE_COVERED"),
            "market_session":source["market_session"],
            "source_marketwide_sha256":source["content_sha256"],
            "source_built_at_utc":source["built_at_utc"],
            "new_codes":chosen,"already_collected":len(covered),
            "uncollected_eligible":len(eligible),
            "requested_batch_limit":limit,
            "latest_first_local_receipt_not_historic_pit":True,
            "api_calls":0,"orders_enabled":False,
            "official_leaders":0}


def capture_marketwide_demo_flow(*,marketwide:Path,project:Path,client,
                                 limit:int=MAX_BATCH, clock:datetime|None=None)->dict:
    now=clock or datetime.now(timezone.utc)
    if (client is None or getattr(client,"project",None)!="eraleader"
            or not callable(getattr(client,"status",None))
            or not callable(getattr(client,"selected_flow_research",None))):
        raise ValueError("FLOW_BATCH_SHARED_GATEWAY_CLIENT_REQUIRED")
    plan=plan_marketwide_flow(marketwide=marketwide,project=project,
                              limit=limit,clock=now)
    if plan["status"]!="FLOW_BATCH_READY_DEMO_RESEARCH":
        return plan
    status=client.status()
    if (type(status) is not dict or status.get("orders_enabled") is not False
            or status.get("configured",{}).get("demo") is not True):
        raise ValueError("FLOW_BATCH_READ_ONLY_DEMO_UNAVAILABLE")
    sources=[]
    # All requests first, ZERO artifact written on a partially failed batch.
    for code in plan["new_codes"]:
        payload=client.selected_flow_research(
            stock_code=code,day=plan["market_session"].replace("-",""),
            mode="demo",max_pages=1,recent_sessions=20)
        if (type(payload) is not dict
                or payload.get("schema")!="sharedbroker.selected_security_flow_research.v1"
                or payload.get("project")!="eraleader"
                or payload.get("market_session")!=plan["market_session"].replace("-","")
                or payload.get("stock_code")!=code
                or payload.get("mode")!="demo"
                or payload.get("units")!="shares"
                or payload.get("orders_enabled") is not False
                or payload.get("historical_pit_certified") is not False
                or payload.get("whole_market_foreign_flow_equivalent") is not False):
            raise ValueError("FLOW_BATCH_PROVIDER_RESEARCH_CONTRACT_REJECTED")
        unsigned=dict(payload)
        pin=unsigned.pop("content_sha256",None)
        # Use the original shared gateway's canonical serializer.
        from shared_broker_api.gateway import compact
        if pin!=sha256(compact(unsigned)).hexdigest():
            raise ValueError("FLOW_BATCH_PROVIDER_SHA_INVALID")
        sources.append(payload)
    # In deterministic tests or an explicitly pinned run, the supplied
    # decision clock is the boundary. Real runs stamp after final receipt.
    finished=now if clock is not None else datetime.now(timezone.utc)
    for report in sources:
        receipt=datetime.fromisoformat(report["first_gateway_received_at_utc"])
        decision=datetime.fromisoformat(report["decision_at_utc"])
        if (receipt.tzinfo is None or decision.tzinfo is None or
                receipt>decision or decision>finished):
            raise ValueError("FLOW_BATCH_RECEIPT_NOT_AVAILABLE_AT_DECISION")
    # Fresh public report SHA must still match the selection baseline.
    original,_=_source(marketwide)
    if (original["content_sha256"]!=plan["source_marketwide_sha256"]
            or original["market_session"]!=plan["market_session"]):
        raise ValueError("FLOW_BATCH_SOURCE_CHANGED_DURING_REQUESTS")
    output=_owned_output(project)/FOLDER
    if output.is_symlink():raise ValueError("FLOW_BATCH_OUTPUT_SYMLINK")
    output.mkdir(mode=0o700,exist_ok=True)
    codes=plan["new_codes"]
    batch_pin=sha256(canonical({"day":plan["market_session"],
                                 "source":plan["source_marketwide_sha256"],
                                 "codes":codes})).hexdigest()[:12]
    folder=output/("KR_"+plan["market_session"].replace("-","")+"_"
                   +plan["source_marketwide_sha256"][:16]+"_"+batch_pin)
    if folder.exists() or folder.is_symlink():
        raise ValueError("FLOW_BATCH_RACE_OR_DUPLICATE")
    rows=[]
    for code,record in zip(codes,sources):
        complete=record.get("research_quality")=="UNVERIFIED_20_OBSERVED_SESSIONS"
        rows.append({"stock_code":code,"file":code+".json",
                     "response_sha256":record["content_sha256"],
                     "has_20_observations":complete,
                     "observed_sessions":record.get("observed_sessions"),
                     "first_gateway_received_at_utc":record["first_gateway_received_at_utc"]})
    result={
        "schema":SCHEMA,"market":"KR","mode":"demo",
        "source_market_session":plan["market_session"],
        "source_marketwide_sha256":plan["source_marketwide_sha256"],
        "first_local_run_at_utc":now.astimezone(timezone.utc).isoformat(),
        "finished_at_utc":finished.isoformat(),
        "stock_codes":codes,"items":rows,
        "reported_20_observations":sum(x["has_20_observations"] for x in rows),
        "research_only":True,"historical_pit_certified":False,
        "official_leaders":0,"orders_enabled":False,
    }
    result["content_sha256"]=sha256(canonical(result)).hexdigest()
    stage=Path(tempfile.mkdtemp(prefix=".flow_batch_",dir=output))
    try:
        os.chmod(stage,0o700)
        for name,content in [("manifest.json",canonical(result)+b"\n")]+[
            (code+".json",canonical(record)+b"\n")
            for code,record in zip(codes,sources)]:
            fd=os.open(stage/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(content);out.flush();os.fsync(out.fileno())
        if folder.exists() or folder.is_symlink():
            raise ValueError("FLOW_BATCH_OUTPUT_RACE")
        os.rename(stage,folder)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {"status":"FLOW_BATCH_DEMO_RESEARCH_PUBLISHED",
            "market_session":plan["market_session"],
            "stock_codes":codes,"published_count":len(codes),
            "complete_20_observation_count":result["reported_20_observations"],
            "manifest":str(folder/"manifest.json"),
            "api_calls":len(codes),"orders_enabled":False,
            "official_leaders":0,"historical_pit_certified":False}
