"""Offline KRX/DART and SEC/exchange staged-export normalizers (NO live APIs).

The two profiles are declared intermediate export contracts, NOT the
official KRX, DART or SEC response schemas. A company identifier (corp_code
or CIK) alone must never stand in for an individual listed security/class.
Output is the existing provider_pit_adapter's validated JSONL bundle.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile
import shutil

from .offline_pit import KINDS, natural_key, normalize
from .provider_pit_adapter import (
    BUNDLE_SCHEMA, SHA, BASENAME, MAX_ROWS_PER_STREAM,
    MAX_MANIFEST_BYTES, MAX_STREAM_BYTES, _json, _now,
    inspect_provider_bundle,
)
from .frozen_holdout import _stamp

STAGE_SCHEMA="eraleader.provider_staged_export.v1"
EXPORT_STATUS="LOCAL_PROVIDER_EXPORT_NORMALIZED_RESEARCH_NOT_AUTHENTICATED"
PROFILES={"KR":"KRX_DART_STAGED_V1","US":"SEC_EXCHANGE_STAGED_V1"}
TOP={"schema_version","profile","market","source_id",
     "publisher_id_claimed","vintage_id","retrieved_at_claimed","streams"}
STREAM={"kind","file","sha256","record_count"}
COMMON={"revision","published_at","source_document_id"}
DATA_KEYS={
    "membership": {"listed_on","delisted_on"},
    "actions": {"event_uid","action_type","effective_on"},
    "fundamentals": {"metric","period_end","value","unit"},
    "industry": {"metric","period_end","value","unit"},
}
FIELDS={
    "KR":{
        "identity":{"corp_code","issue_uid"},
        "ticker":"stock_code",
        "sector":"industry_code",
    },
    "US":{
        "identity":{"cik","share_class_uid"},
        "ticker":"ticker",
        "sector":"sic",
    },
}
ASCII_ID=re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,40}\Z")
DOCUMENT_ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}\Z")
KR_SECTOR=re.compile(r"[A-Z0-9][A-Z0-9_-]{1,20}\Z")
US_TICKER=re.compile(r"[A-Z][A-Z0-9.-]{0,18}\Z")
KR_STOCK=re.compile(r"[0-9]{6}\Z")
KR_CORP=re.compile(r"[0-9]{8}\Z")
US_CIK=re.compile(r"[0-9]{1,10}\Z")
US_SIC=re.compile(r"[0-9]{4}\Z")


def _text(obj:dict,key:str) -> str:
    val=obj.get(key)
    if (type(val) is not str or not val.strip() or
            len(val)>150 or "|" in val or any(ord(c)<32 for c in val)):
        raise ValueError("Invalid staged export identity/document field: "+key)
    return val


def _stamp_iso(value:object) -> str:
    return _stamp(value).isoformat()


def _company_id(row:dict,market:str) -> str:
    if market=="KR":
        corp=_text(row,"corp_code")
        issue=_text(row,"issue_uid")
        if not KR_CORP.fullmatch(corp):
            raise ValueError("Invalid KR corp_code; need exact 8-digit declared issuer")
        if not ASCII_ID.fullmatch(issue):
            raise ValueError("Invalid KR issue_uid; cannot infer security from stock_code")
        return "KR:CORP"+corp+":ISSUE:"+issue
    cik=_text(row,"cik")
    share=_text(row,"share_class_uid")
    if not US_CIK.fullmatch(cik):
        raise ValueError("Invalid US SEC CIK; need numeric declared registrant")
    if not ASCII_ID.fullmatch(share):
        raise ValueError("Invalid US share_class_uid; SEC CIK alone is not security identity")
    return "US:CIK"+cik.zfill(10)+":CLASS:"+share


def _sector(row:dict,market:str) -> str:
    key=FIELDS[market]["sector"]
    val=_text(row,key)
    if market=="KR" and not KR_SECTOR.fullmatch(val):
        raise ValueError("Invalid KR industry_code")
    if market=="US" and not US_SIC.fullmatch(val):
        raise ValueError("Invalid US SIC sector")
    return ("KR:INDUSTRY:" if market=="KR" else "US:SIC:")+val


def _keys(kind:str,market:str) -> tuple[set[str],set[str]]:
    expected=set(COMMON)|set(DATA_KEYS[kind])
    if kind=="industry":
        expected.add(FIELDS[market]["sector"])
    else:
        expected.update(FIELDS[market]["identity"])
        if kind=="membership":
            expected.add(FIELDS[market]["ticker"])
            expected.add(FIELDS[market]["sector"])
    allowed=expected|({"ratio","cash_amount"} if kind=="actions" else set())
    return expected,allowed


def _convert(kind:str,market:str,entry:dict,source:str,retrieved:datetime) -> dict:
    required,allowed=_keys(kind,market)
    if (not isinstance(entry,dict) or not required.issubset(entry)
            or not set(entry).issubset(allowed)):
        raise ValueError("Unsupported/missing staged "+kind+" fields")
    doc=_text(entry,"source_document_id")
    if not DOCUMENT_ID.fullmatch(doc):
        raise ValueError("Invalid source_document_id")
    timestamp=_stamp(entry["published_at"])
    if timestamp>retrieved:
        raise ValueError("Staged publication after claimed retrieval")
    base={"source_id":source,"revision":entry["revision"]}
    if kind=="membership":
        ticker=_text(entry,FIELDS[market]["ticker"])
        pattern=KR_STOCK if market=="KR" else US_TICKER
        if not pattern.fullmatch(ticker):
            raise ValueError("Invalid staged ticker/stock_code")
        data={
            **base,
            "security_id":_company_id(entry,market),
            "market":market,"ticker":ticker,
            "industry_id":_sector(entry,market),
            "valid_from":entry["listed_on"],
            "valid_to":entry["delisted_on"],
            "known_at":timestamp.isoformat(),
        }
    elif kind=="actions":
        kind_of_action=_text(entry,"action_type")
        required_extras=(
            {"ratio"} if kind_of_action=="split" else
            {"cash_amount"} if kind_of_action=="dividend" else set()
        )
        if set(entry)-required!=required_extras:
            raise ValueError("Invalid action optional fields")
        data={
            **base,"security_id":_company_id(entry,market),
            "action_id":_text(entry,"event_uid"),
            "action_type":kind_of_action,
            "effective_on":entry["effective_on"],
            "known_at":timestamp.isoformat(),
        }
        if kind_of_action=="split":data["ratio"]=entry["ratio"]
        if kind_of_action=="dividend":data["cash_amount"]=entry["cash_amount"]
    else:
        data={
            **base,"metric":_text(entry,"metric"),
            "period_end":entry["period_end"],
            "available_at":timestamp.isoformat(),
            "value":entry["value"],"unit":entry["unit"],
        }
        if kind=="fundamentals":
            data["security_id"]=_company_id(entry,market)
        else:
            data["industry_id"]=_sector(entry,market)
    return normalize(kind,data)


def _preflight(manifest_file:Path,clock:datetime) -> tuple[dict,dict[str,list],list,dict]:
    src=Path(manifest_file)
    if (src.is_symlink() or src.parent.is_symlink()
            or not src.is_file() or
            not 0<src.stat().st_size<=MAX_MANIFEST_BYTES):
        raise ValueError("Missing/oversized/symlink staged manifest")
    raw=src.read_bytes()
    manifest=_json(raw)
    if (not isinstance(manifest,dict) or set(manifest)!=TOP or
            manifest.get("schema_version")!=STAGE_SCHEMA):
        raise ValueError("Invalid staged export schema/fields")
    market=manifest.get("market")
    if market not in PROFILES or manifest.get("profile")!=PROFILES[market]:
        raise ValueError("Staged provider profile/market mismatch")
    for f in ("source_id","vintage_id","publisher_id_claimed"):
        _text(manifest,f)
    retrieved=_stamp(manifest["retrieved_at_claimed"])
    if retrieved>clock:
        raise ValueError("Staged retrieval future of actual local OS clock")
    specifications=manifest["streams"]
    if not isinstance(specifications,list) or not 1<=len(specifications)<=4:
        raise ValueError("Staged export requires 1..4 streams")
    sources={}
    mapped={}
    evidence=[]
    source_sha={}
    root=src.parent.resolve()
    for s in specifications:
        if not isinstance(s,dict) or set(s)!=STREAM:
            raise ValueError("Invalid staged stream schema/fields")
        kind=s.get("kind")
        if kind not in KINDS or kind in mapped:
            raise ValueError("Duplicate or unsupported staged kind")
        filename=_text(s,"file")
        if not BASENAME.fullmatch(filename) or filename.startswith("."):
            raise ValueError("Unsafe staged source filename")
        expected=s.get("sha256")
        if not isinstance(expected,str) or not SHA.fullmatch(expected):
            raise ValueError("Invalid staged source SHA256 digest")
        count=s.get("record_count")
        if type(count) is not int or not 1<=count<=MAX_ROWS_PER_STREAM:
            raise ValueError("Invalid staged row_count")
        file=root/filename
        if (file.is_symlink() or not file.is_file() or file.resolve().parent!=root
                or not 0<file.stat().st_size<=MAX_STREAM_BYTES):
            raise ValueError("Missing or symlink staged source data")
        blob=file.read_bytes()
        checksum=sha256(blob).hexdigest()
        if checksum!=expected:
            raise ValueError("Staged source SHA256 mismatch")
        lines=blob.splitlines(keepends=True)
        if len(lines)!=count:
            raise ValueError("Staged JSONL row_count mismatch")
        converted=[]
        ids=set()
        for n,line in enumerate(lines,1):
            if not line.strip() or len(line)>2_000_000:
                raise ValueError("Blank/oversized staged JSONL row")
            record=_json(line)
            result=_convert(kind,market,record,manifest["source_id"],retrieved)
            key=natural_key(kind,result)
            if key in ids:
                raise ValueError("Duplicate normalized staged identity/revision")
            ids.add(key)
            text=json.dumps(result,sort_keys=True,ensure_ascii=False,
                            separators=(",",":"),allow_nan=False)
            evidence.append({
                "kind":kind,"natural_key":key,
                "source_document_id_claimed":record["source_document_id"],
                "source_line_sha256":sha256(line).hexdigest(),
                "normalized_sha256":sha256(text.encode()).hexdigest(),
            })
            converted.append(result)
        mapped[kind]=converted
        source_sha[kind]=checksum
        sources[kind]=len(converted)
    if "membership" not in mapped:
        raise ValueError("Staged normalization requires membership identities")
    return manifest,mapped,evidence,{
        "source_raw_manifest_sha256":sha256(raw).hexdigest(),
        "source_file_sha256":source_sha,
        "rows_by_kind":sources,
        "stage_first_normalized_utc":clock.isoformat(),
    }


def _write_immutable(path:Path,data:bytes) -> None:
    with path.open("xb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def normalize_provider_export(
    manifest_file:Path,stage_dir:Path,*,clock:datetime|None=None,
) -> dict:
    """Preflight source bytes, write NEW staged directory, validate downstream bundle.

    Never edits raw source or existing staged output, never touches the PIT
    SQLite. The CLI clock is always OS time; injected clock is test-only.
    """
    now=_now(clock)
    manifest,records,evidence,meta=_preflight(Path(manifest_file),now)
    target=Path(stage_dir)
    if (target.is_symlink() or target.exists() or
            target.parent.is_symlink() or not target.name or
            target.name in (".","..")):
        raise ValueError("Staged target exists/unsafe: no overwrite permitted")
    target.parent.mkdir(parents=True,exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix=".eraleader_stage_",dir=target.parent))
    try:
        streams=[]
        for kind in KINDS:
            if kind not in records:
                continue
            raw=b"".join(
                (json.dumps(item,sort_keys=True,ensure_ascii=False,
                            separators=(",",":"),allow_nan=False)+"\n").encode()
                for item in records[kind]
            )
            filename=kind+".jsonl"
            _write_immutable(scratch/filename,raw)
            streams.append({
                "kind":kind,"file":filename,
                "sha256":sha256(raw).hexdigest(),
                "record_count":len(records[kind]),
            })
        normalized_manifest={
            "schema_version":BUNDLE_SCHEMA,
            "market":manifest["market"],
            "source_id":manifest["source_id"],
            "publisher_id_claimed":manifest["publisher_id_claimed"],
            "vintage_id":manifest["vintage_id"],
            "retrieved_at_claimed":manifest["retrieved_at_claimed"],
            "streams":streams,
        }
        encoded=(json.dumps(normalized_manifest,sort_keys=True,
                            ensure_ascii=False,indent=2)+"\n").encode()
        _write_immutable(scratch/"manifest.json",encoded)
        witness=b"".join(
            (json.dumps(record,sort_keys=True,ensure_ascii=False,
                        separators=(",",":"),allow_nan=False)+"\n").encode()
            for record in evidence
        )
        _write_immutable(scratch/"normalization_witnesses.jsonl",witness)
        # Reuse the only accepted normalized-input reader as the final gate.
        checked=inspect_provider_bundle(scratch/"manifest.json",clock=now)
        if checked["rows_received"]!=len(evidence):
            raise ValueError("Normalized staged source row count inconsistent")
        if target.exists() or target.is_symlink():
            raise ValueError("Staged target exists: overwrite refused")
        os.rename(scratch,target)
    except Exception:
        shutil.rmtree(scratch)
        raise
    return {
        "status":EXPORT_STATUS,
        "market":manifest["market"],
        "profile":manifest["profile"],
        "source_id":manifest["source_id"],
        "publisher_id_claimed":manifest["publisher_id_claimed"],
        "vintage_id":manifest["vintage_id"],
        "source_raw_manifest_sha256":meta["source_raw_manifest_sha256"],
        "source_file_sha256":meta["source_file_sha256"],
        "normalized_bundle_manifest_sha256":sha256(encoded).hexdigest(),
        "normalization_witnesses_sha256":sha256(witness).hexdigest(),
        "normalized_manifest":str(target/"manifest.json"),
        "normalized_row_count":len(evidence),
        "normalized_row_count_by_kind":meta["rows_by_kind"],
        "stage_first_normalized_utc":meta["stage_first_normalized_utc"],
        "source_publisher_independently_authenticated":False,
        "publisher_independently_authenticated":False,
        "source_retrieval_time_independently_attested":False,
        "issuer_and_share_class_independently_verified":False,
        "original_document_id_independently_verified":False,
        "licensed_raw_api_schema_verified":False,
        "historic_pit_certified":False,
        "official_leader_promotions":0,
        "external_api_calls":0,
        "warning":(
            "These are declared intermediate export profiles, NOT direct "
            "KRX, DART or SEC API shapes. Claimed company/issue/class IDs, "
            "publication times and publisher identities are unverified. "
            "The normalized rows become eligible only after separately "
            "recorded first local ingestion through import-provider-pit."
        ),
    }
