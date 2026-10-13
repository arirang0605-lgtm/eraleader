"""Official DART company.json industry FIRST RECEIPT per current issuer.

Industry codes are current issuer classifications. They do NOT certify historic
share classes, past sector membership, listing status, or future leader alpha.
Existing official DART first receipt and current directory validation reused.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode
import json
import os
import re
import shutil
import stat
import tempfile
import uuid

from .official_api_capture import _http_get, _root, _canonical, _write_new
from .official_api_pit_bridge import _private_file
from .official_dart_corp_directory import verify_dart_corp_directory

SCHEMA="eraleader.dart_company_current_industry_first_received.v1"
INDUSTRY=re.compile(r"[0-9]{3,5}\Z")
STOCK=re.compile(r"[0-9]{6}\Z")
CORP=re.compile(r"[0-9]{8}\Z")
PIN=re.compile(r"[a-f0-9]{64}\Z")
SOURCE="dart-company-profile"


def _unique(items):
    result={}
    for key,value in items:
        if key in result:
            raise ValueError("Duplicate DART company profile JSON key")
        result[key]=value
    return result


def parse_company_profile(raw: bytes, *, stock_code: str, corp_code: str) -> dict:
    if (type(raw) is not bytes or not 0<len(raw)<=64*1024 or
            type(stock_code) is not str or not STOCK.fullmatch(stock_code) or
            type(corp_code) is not str or not CORP.fullmatch(corp_code)):
        raise ValueError("Invalid bounded company profile/original issuer code")
    try:
        body=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=_unique)
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Invalid company profile JSON") from exc
    if (type(body) is not dict or body.get("status")!="000" or
            body.get("corp_code")!=corp_code or
            body.get("stock_code")!=stock_code):
        raise ValueError("DART original company ID/status mismatched directory")
    cls=body.get("corp_cls")
    code=body.get("induty_code")
    if cls not in ("Y","K","N"):
        raise ValueError("Unexpected DART listed-company market classification")
    if code is not None and code!="":
        if type(code) is not str or not INDUSTRY.fullmatch(code):
            raise ValueError("Invalid official DART current industry code")
    else:
        code=None
    return {"stock_code":stock_code, "corp_code":corp_code,
            "current_dart_industry_code":code,
            "current_dart_listed_class":cls,
            "historic_industry_pit_certified":False,
            "historic_share_class_pit_certified":False,
            "official_leader":False}


def capture_company_profile(private_root: Path, *, stock_code: str,
                            directory: tuple[Path,str], creds: dict,
                            fetch=None, clock=None) -> dict:
    root=_root(private_root)
    now=(clock or (lambda:datetime.now(timezone.utc)))()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DART profile source requires timezone-aware first moment")
    lookup=verify_dart_corp_directory(*directory,decision_at=now)
    corp_code=lookup["mapping"].get(stock_code)
    if not corp_code:
        raise ValueError("DART profile ticker not verified in current original directory")
    secret=creds.get("ERALEADER_DART_API_KEY")
    if type(secret) is not str or not re.fullmatch(r"[A-Za-z0-9]{40}",secret):
        raise ValueError("DART key not configured")
    url="https://opendart.fss.or.kr/api/company.json?"+urlencode({
        "crtfc_key":secret,"corp_code":corp_code,
    })
    raw=(fetch or _http_get)(url,{
        "Accept":"application/json","User-Agent":"EraLeader/0.1",
    })
    data=parse_company_profile(raw,stock_code=stock_code,corp_code=corp_code)
    stamp=(clock or (lambda:datetime.now(timezone.utc)))()
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp<now:
        raise ValueError("DART current issuer profile first clock moved backwards")
    metadata={
        "schema":SCHEMA,"source":SOURCE,
        "stock_code":stock_code,"corp_code":corp_code,
        "source_directory_sha256":directory[1],
        "raw_sha256":sha256(raw).hexdigest(),"raw_length":len(raw),
        "first_local_received_at_utc":stamp.astimezone(timezone.utc).isoformat(),
        "current_dart_industry_code":data["current_dart_industry_code"],
        "current_dart_listed_class":data["current_dart_listed_class"],
        "historic_industry_pit_certified":False,
        "historic_share_class_pit_certified":False,
        "official_leaders":0,
    }
    original=_canonical(metadata)
    staged=Path(tempfile.mkdtemp(prefix=".dart_companystage_",dir=root))
    target=root/("dart_company_"+uuid.uuid4().hex)
    try:
        os.chmod(staged,0o700)
        _write_new(staged/"raw_response.json",raw)
        _write_new(staged/"first_receipt.json",original)
        os.replace(staged,target)
    finally:
        if staged.exists():shutil.rmtree(staged)
    return {"status":"CURRENT_DART_COMPANY_INDUSTRY_RESEARCH_ONLY",
            "capture_id":target.name,
            "first_receipt_sha256":sha256(original).hexdigest(),
            "stock_code":stock_code,
            "current_dart_industry_code":data["current_dart_industry_code"],
            "pit_certified":False}


def verify_company_profile(folder: Path, pin: str, *, directory:tuple[Path,str],
                           decision_at: datetime) -> dict:
    p=Path(folder)
    if (not p.is_absolute() or p.is_symlink() or not p.is_dir() or
            p.stat().st_uid!=os.geteuid() or
            stat.S_IMODE(p.stat().st_mode)!=0o700 or
            type(pin) is not str or not PIN.fullmatch(pin) or
            decision_at.tzinfo is None or decision_at.utcoffset() is None):
        raise ValueError("DART profile first receipt private identity and clock required")
    original=_private_file(p/"first_receipt.json",0o600)
    raw=_private_file(p/"raw_response.json",0o600)
    if sha256(original).hexdigest()!=pin:
        raise ValueError("DART company original first SHA changed")
    meta=json.loads(original)
    now=datetime.fromisoformat(meta["first_local_received_at_utc"].replace("Z","+00:00"))
    if (now.tzinfo is None or now.utcoffset() is None or now>decision_at or
            meta.get("schema")!=SCHEMA or meta.get("source")!=SOURCE or
            meta.get("source_directory_sha256")!=directory[1] or
            meta.get("raw_sha256")!=sha256(raw).hexdigest() or
            meta.get("raw_length")!=len(raw) or
            meta.get("official_leaders")!=0 or
            meta.get("historic_industry_pit_certified") is not False or
            meta.get("historic_share_class_pit_certified") is not False):
        raise ValueError("DART company original/PIT provenance conflict")
    directory_data=verify_dart_corp_directory(*directory,decision_at=decision_at)
    if directory_data["mapping"].get(meta["stock_code"])!=meta["corp_code"]:
        raise ValueError("DART current directory issuer mismatch")
    checked=parse_company_profile(raw,stock_code=meta["stock_code"],
                                  corp_code=meta["corp_code"])
    if (checked["current_dart_industry_code"]!=meta["current_dart_industry_code"] or
            checked["current_dart_listed_class"]!=meta["current_dart_listed_class"] or
            {i.name for i in p.iterdir()}!={"first_receipt.json","raw_response.json"}):
        raise ValueError("DART issuer profile actual code differs from pinned original")
    return {**checked,"first_receipt_sha256":pin,
            "first_local_received_at_utc":now.astimezone(timezone.utc).isoformat()}


def collect_industry_profiles(*, private_root: Path, directory:tuple[Path,str],
                              stock_codes:tuple[str,...], creds:dict,
                              existing_only:bool=False, fetch=None,clock=None) -> dict:
    if (type(stock_codes) is not tuple or
            not 1<=len(stock_codes)<=20 or len(set(stock_codes))!=len(stock_codes) or
            any(type(code) is not str or not STOCK.fullmatch(code)
                for code in stock_codes)):
        raise ValueError("Industry batch is restricted to 1..20 distinct six-digit stocks")
    now=(clock or (lambda:datetime.now(timezone.utc)))()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Industry capture decision must be timezone-aware")
    d=verify_dart_corp_directory(*directory,decision_at=now)
    if any(code not in d["mapping"] for code in stock_codes):
        raise ValueError("Cannot collect issuer without independently verified DART directory")
    originals={}
    for file in Path(private_root).glob("dart_company_*/first_receipt.json"):
        if file.is_symlink():
            raise ValueError("Unexpected original symlink")
        meta=json.loads(file.read_bytes())
        code=meta.get("stock_code")
        if code not in stock_codes:continue
        if code in originals:
            raise ValueError("Multiple company-profile first receipts require revision review")
        originals[code]=(file.parent,sha256(file.read_bytes()).hexdigest())
    results=[]
    for code in stock_codes:
        if code in originals:
            folder,pin=originals[code]
            reused=True
        elif existing_only:
            results.append({"stock_code":code,"status":"PROFILE_NOT_CAPTURED",
                            "current_dart_industry_code":None,
                            "first_receipt_sha256":None,
                            "first_local_received_at_utc":None,
                            "pit_certified":False})
            continue
        else:
            rec=capture_company_profile(private_root,stock_code=code,directory=directory,
                                        creds=creds,fetch=fetch,clock=clock)
            folder=Path(private_root)/rec["capture_id"]
            pin=rec["first_receipt_sha256"]
            reused=False
        actual=verify_company_profile(folder,pin,directory=directory,
                          decision_at=(clock or (lambda:datetime.now(timezone.utc)))())
        results.append({
            "stock_code":code,"status":"CURRENT_DART_COMPANY_INDUSTRY_RESEARCH_ONLY",
            "current_dart_industry_code":actual["current_dart_industry_code"],
            "current_dart_listed_class":actual["current_dart_listed_class"],
            "corp_code":actual["corp_code"],
            "first_receipt_sha256":pin,
            "first_local_received_at_utc":actual["first_local_received_at_utc"],
            "existing_original":reused,
            "pit_certified":False,
        })
    return {"schema":"eraleader.dart_industry_profile_cohort.v1",
            "decision_at_utc":(
                (clock or (lambda:datetime.now(timezone.utc)))()
                .astimezone(timezone.utc).isoformat()),
            "source_directory_sha256":directory[1],
            "companies_requested":len(stock_codes),
            "industry_profiles_verified":sum(x["first_receipt_sha256"] is not None
                                               for x in results),
            "companies":results,
            "current_classification_only":True,
            "historic_industry_pit_certified":False,
            "source_data_first_received_not_historical_asof":True,
            "official_leaders":0}
