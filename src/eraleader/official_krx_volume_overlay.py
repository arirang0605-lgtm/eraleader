"""Verified official KRX daily volume supplement from local first receipts.

Reads previously received two-exchange original KRX responses only; never
replaces historical marcap or requests new KRX API dates. No inferred volume.
"""
from __future__ import annotations

from datetime import date,datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import tempfile

from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source
from .marketwide_dated_flow import read_dated_flow, plan_dated_capture
from .official_api_pit_bridge import verified_capture,_krx_frame
from .official_company_explorer import canonical

SCHEMA="eraleader.kr_official_krx_dated_volume_v1"
SUBDIR="official_krx_volume_overlay"
SOURCES=("krx-kospi","krx-kosdaq")
MAX_RECEIPTS=800


def _clock(value):
    now=value or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("KRX_VOLUME_AWARE_CLOCK_REQUIRED")
    return now.astimezone(timezone.utc)


def _receipt_index(root:Path,now:datetime):
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or any(p.is_symlink() for p in root.parents)
            or root.stat().st_uid!=os.geteuid()):
        raise ValueError("KRX_VOLUME_CAPTURE_ROOT_UNSAFE")
    folders=list(root.iterdir())
    if len(folders)>MAX_RECEIPTS:
        raise ValueError("KRX_VOLUME_TOO_MANY_CAPTURE_FOLDERS")
    found={}
    for directory in folders:
        if directory.is_symlink() or not directory.is_dir():
            continue
        receipt=directory/"first_receipt.json"
        if not receipt.is_file():
            continue
        if receipt.is_symlink() or receipt.stat().st_size>30_000:
            raise ValueError("KRX_VOLUME_RECEIPT_FILE_UNSAFE")
        try:
            raw=receipt.read_bytes()
            header=json.loads(raw)
        except (OSError,ValueError,UnicodeError):
            continue
        source=header.get("source")
        if source not in SOURCES:
            continue
        day=header.get("request_value")
        if (type(day) is not str
                or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",day) is None
                or date.fromisoformat(day)>now.date()):
            continue
        stamp=datetime.fromisoformat(header["first_local_received_at_utc"])
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc)>now:
            continue
        key=(day,source)
        candidate=(stamp.astimezone(timezone.utc),directory,sha256(raw).hexdigest())
        old=found.get(key)
        if old is None or candidate[0]<old[0]:
            found[key]=candidate
    return found


def construct_volume_overlay(*,marketwide:Path,project:Path,
                             capture_root:Path,stock_code:str,
                             clock:datetime|None=None)->dict:
    now=_clock(clock)
    base=_owned_output(project)
    source,_=_source(marketwide)
    if type(stock_code) is not str or not re.fullmatch(r"[0-9]{6}",stock_code):
        raise ValueError("KRX_VOLUME_STOCK_CODE_INVALID")
    saved=plan_dated_capture(
        marketwide=marketwide,project=project,stock_code=stock_code,clock=now)
    if saved["status"]!="DATED_FLOW_ALREADY_CAPTURED":
        return {"status":"KRX_VOLUME_WAIT_DATED_KIWOOM",
                "stock_code":stock_code,"new_dates":0,"api_calls":0,"orders":0}
    receipt=read_dated_flow(Path(saved["file"]),expected_code=stock_code,
                            expected_source=source["content_sha256"],clock=now)
    desired={entry["session"] for entry in receipt["rows"]}
    original=_receipt_index(capture_root,now)
    points=[]
    for day in sorted(desired):
        if day>source["market_session"]:
            raise ValueError("KRX_VOLUME_FUTURE_MARKET_DATE")
        pair={}
        for name in SOURCES:
            candidate=original.get((day,name))
            if candidate is None:
                pair={}
                break
            _observed,folder,pin=candidate
            meta,raw=verified_capture(folder,name,pin,now)
            if meta["request_value"]!=day or meta["source"]!=name:
                raise ValueError("KRX_VOLUME_WRONG_DAY_OR_SOURCE")
            pair[name]=(meta,_krx_frame(name,meta,raw),pin)
        if len(pair)!=2:
            continue
        all_codes=set()
        current_snapshot={r["security_id"]:r for r in source["securities"]}
        for name,(_meta,frame,_pin) in pair.items():
            codes=set(frame["security_id"])
            if codes & all_codes:
                raise ValueError("KRX_VOLUME_OVERLAPPING_EXCHANGE_CODES")
            all_codes.update(codes)
            if day==source["market_session"]:
                for row in frame.itertuples(index=False):
                    current=current_snapshot.get(row.security_id)
                    if (current is None or current["name"]!=row.name
                            or current["venue"]!=row.venue
                            or current["close"]!=float(row.close)
                            or current["market_cap"]!=float(row.market_cap)
                            or current["turnover"]!=float(row.turnover)):
                        raise ValueError("KRX_VOLUME_LATEST_ORIGINAL_MISMATCH")
        if day==source["market_session"] and len(all_codes)!=len(current_snapshot):
            raise ValueError("KRX_VOLUME_LATEST_UNIVERSE_INCOMPLETE")
        observed=[]
        for name,(meta,frame,pin) in pair.items():
            row=frame.loc[frame["security_id"]==stock_code]
            if not row.empty:
                r=row.iloc[0]
                observed.append({
                    "session":day,"stock_code":stock_code,
                    "volume":int(r["volume"]),
                    "close":float(r["close"]),
                    "market_cap":float(r["market_cap"]),
                    "market":name,
                    "first_receipt_sha256":pin,
                    "first_locally_received_at_utc":meta["first_local_received_at_utc"],
                })
        if len(observed)>1:
            raise ValueError("KRX_VOLUME_MULTIPLE_LISTING")
        if observed:
            points.append(observed[0])
    data={
        "schema":SCHEMA,"market":"KR",
        "source_market_session":source["market_session"],
        "source_marketwide_sha256":source["content_sha256"],
        "stock_code":stock_code,
        "dated_kiwoom_sha256":receipt["content_sha256"],
        "capture_root":str(capture_root),
        "source_first_receipts_verified":True,
        "capture_dates":[r["session"] for r in points],
        "rows":points,
        "source_volume_is_official_observation":True,
        "historical_pit_independently_certified":False,
        "corporate_actions_verified":False,
        "normalised_flow_score_10":None,
        "orders_enabled":False,"formal_leaders":0,
    }
    data["content_sha256"]=sha256(canonical(data)).hexdigest()
    return data


def read_volume_overlay(file:Path,*,expected_code:str,expected_source:str,
                        clock:datetime|None=None)->dict:
    now=_clock(clock)
    if (not file.is_absolute() or file.is_symlink() or not file.is_file()
            or any(p.is_symlink() for p in file.parents)
            or file.stat().st_size>120_000):
        raise ValueError("KRX_VOLUME_OVERLAY_FILE_UNSAFE")
    b=file.read_bytes()
    try:
        obj=json.loads(b)
        if type(obj) is not dict:
            raise ValueError("KRX_VOLUME_OVERLAY_PIN_INVALID")
    except (ValueError,UnicodeError):
        raise ValueError("KRX_VOLUME_OVERLAY_PIN_INVALID") from None
    unsigned=dict(obj);pin=unsigned.pop("content_sha256",None)
    if (b!=canonical(obj)+b"\n" or
            pin!=sha256(canonical(unsigned)).hexdigest() or
            obj.get("schema")!=SCHEMA or obj.get("market")!="KR"
            or obj.get("stock_code")!=expected_code
            or obj.get("source_marketwide_sha256")!=expected_source
            or obj.get("source_first_receipts_verified") is not True
            or obj.get("orders_enabled") is not False
            or obj.get("normalised_flow_score_10") is not None):
        raise ValueError("KRX_VOLUME_OVERLAY_PIN_INVALID")
    rows=obj.get("rows")
    if type(rows) is not list or len(rows)>20:
        raise ValueError("KRX_VOLUME_OVERLAY_ROW_COUNT")
    seen=set()
    for row in rows:
        day=row["session"]
        received=datetime.fromisoformat(row["first_locally_received_at_utc"])
        if (day in seen or date.fromisoformat(day)>date.fromisoformat(obj["source_market_session"])
                or received.tzinfo is None
                or row["stock_code"]!=expected_code
                or type(row["volume"]) is not int or row["volume"]<0
                or not re.fullmatch(r"[0-9a-f]{64}",row["first_receipt_sha256"])
                or received.astimezone(timezone.utc)>now):
            raise ValueError("KRX_VOLUME_OVERLAY_ROW_INVALID")
        seen.add(day)
    if sorted(seen)!=obj["capture_dates"]:
        raise ValueError("KRX_VOLUME_OVERLAY_DATES_INVALID")
    return obj


def publish_volume_overlay(*,marketwide:Path,project:Path,capture_root:Path,
                           stock_code:str,clock:datetime|None=None)->dict:
    doc=construct_volume_overlay(marketwide=marketwide,project=project,
                                 capture_root=capture_root,stock_code=stock_code,
                                 clock=clock)
    if doc.get("status")=="KRX_VOLUME_WAIT_DATED_KIWOOM":
        return doc
    parent=_owned_output(project)/SUBDIR
    if parent.is_symlink():
        raise ValueError("KRX_VOLUME_OVERLAY_ROOT_SYMLINK")
    parent.mkdir(mode=0o700,exist_ok=True)
    version=sha256(canonical({
        "market":doc["source_marketwide_sha256"],
        "flow":doc["dated_kiwoom_sha256"],
        "rows":doc["rows"],
    })).hexdigest()[:12]
    folder=parent/("KR_"+doc["source_market_session"].replace("-","")+"_"
                   +stock_code+"_"+version)
    out=folder/"manifest.json"
    content=canonical(doc)+b"\n"
    if folder.is_symlink():raise ValueError("KRX_VOLUME_OVERLAY_TARGET_SYMLINK")
    if folder.exists():
        if (not folder.is_dir() or out.is_symlink() or
                out.read_bytes()!=content):
            raise ValueError("KRX_VOLUME_OVERLAY_EXISTING_CONFLICT")
        status="ALREADY_PUBLISHED"
    else:
        stage=Path(tempfile.mkdtemp(prefix=".krxvol_",dir=parent))
        try:
            fd=os.open(stage/"manifest.json",os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as file:
                file.write(content);file.flush();os.fsync(file.fileno())
            if folder.exists() or folder.is_symlink():
                raise ValueError("KRX_VOLUME_OVERLAY_RACE")
            os.rename(stage,folder)
        finally:
            if stage.exists():shutil.rmtree(stage)
        status="PUBLISHED"
    return {
        "status":status,"stock_code":stock_code,"source_market_session":doc["source_market_session"],
        "official_volume_days":len(doc["rows"]),
        "observed_dates":doc["capture_dates"],
        "manifest":str(out),"source_sha256":doc["source_marketwide_sha256"],
        "api_calls":0,"orders":0,
    }
