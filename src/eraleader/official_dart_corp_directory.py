"""First-observed DART corporation-code directory ZIP: nonhistorical crosswalk.

The complete *current* DART directory is a company crosswalk, not a source of
historic listed membership, daily venue, permanent share-class or PIT issuer
corporate actions. No issuer identity is backdated before first local receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from xml.etree import ElementTree
from zipfile import ZipFile, BadZipFile
import os
import re
import shutil
import stat
import tempfile
import uuid

from .official_api_capture import _http_get, _root, _canonical, _write_new
from .official_api_pit_bridge import _private_file

SCHEMA="eraleader.dart_corp_directory_first_received.v1"
ZIP_MAX=24*1024*1024
XML_MAX=128*1024*1024
ROWS_MAX=300_000


def parse_directory_zip(raw: bytes) -> tuple[dict[str,set[str]], int]:
    """Parse bounded ZIP without permitting entities/DTD, nested ZIP or traversal."""
    if type(raw) is not bytes or not 0<len(raw)<=ZIP_MAX:
        raise ValueError("Invalid DART company directory ZIP bytes")
    try:
        with ZipFile(BytesIO(raw)) as z:
            all_files=z.infolist()
            if (len(all_files)!=1 or all_files[0].filename.upper()!="CORPCODE.XML" or
                    all_files[0].file_size>XML_MAX or all_files[0].is_dir() or
                    all_files[0].flag_bits & 0x1):
                raise ValueError("Unexpected DART ZIP members or decompression limit")
            xml=z.read(all_files[0],pwd=None)
    except (BadZipFile,RuntimeError,MemoryError) as exc:
        raise ValueError("DART company directory ZIP corrupt") from exc
    if (len(xml)>XML_MAX or b"<!DOCTYPE" in xml.upper() or
            b"<!ENTITY" in xml.upper()):
        raise ValueError("DART XML entity/DTD disallowed")
    try:
        root=ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError("DART company directory XML invalid") from exc
    if root.tag!="result":
        raise ValueError("DART corporate directory XML root invalid")
    seen_corp=set()
    by_code={}
    count=0
    for item in root.findall("list"):
        count+=1
        if count>ROWS_MAX:
            raise ValueError("DART corporate code directory row cap")
        corp=item.findtext("corp_code")
        code=item.findtext("stock_code")
        when=item.findtext("modify_date")
        if (type(corp) is not str or not re.fullmatch(r"[0-9]{8}",corp) or
                corp in seen_corp or type(when) is not str or
                not re.fullmatch(r"[0-9]{8}",when)):
            raise ValueError("DART duplicate/invalid corporation identity")
        seen_corp.add(corp)
        if not code or not code.strip():
            continue
        if not re.fullmatch(r"[0-9A-Za-z]{6}",code):
            raise ValueError("DART invalid listed stock code in directory")
        by_code.setdefault(code,set()).add(corp)
    if count == 0:
        raise ValueError("DART empty corporation directory")
    return by_code,count


def capture_dart_corp_directory(private_root: Path, *,
                                creds: dict, fetch=None, clock=None) -> dict:
    private_root=_root(private_root)
    key=creds.get("ERALEADER_DART_API_KEY")
    if type(key) is not str or not re.fullmatch(r"[A-Za-z0-9]{40}",key):
        raise ValueError("Official DART key unavailable")
    url="https://opendart.fss.or.kr/api/corpCode.xml?"+urlencode({"crtfc_key":key})
    raw=(fetch or _http_get)(url,{"Accept":"application/zip","User-Agent":"EraLeader/0.1"})
    mapping,count=parse_directory_zip(raw)
    stamp=(clock or (lambda:datetime.now(timezone.utc)))()
    if stamp.tzinfo is None:
        raise ValueError("DART directory first receipt clock requires offset")
    observed=stamp.astimezone(timezone.utc).isoformat()
    metadata={
        "schema":SCHEMA,"source":"dart-corp-directory",
        "first_local_received_at_utc":observed,
        "raw_sha256":sha256(raw).hexdigest(),"raw_length":len(raw),
        "total_corporations":count,"listed_security_code_count":len(mapping),
        "ambiguous_security_code_count":sum(len(v)>1 for v in mapping.values()),
        "current_directory_only":True,
        "historic_membership_pit_certified":False,
        "issuer_share_class_pit_certified":False,"official_leaders":0,
    }
    signed=_canonical(metadata)
    stage=Path(tempfile.mkdtemp(prefix=".dart_directory_inflight_",dir=private_root))
    target=private_root/("dart_directory_"+uuid.uuid4().hex)
    try:
        os.chmod(stage,0o700)
        _write_new(stage/"raw_directory.zip",raw)
        _write_new(stage/"first_receipt.json",signed)
        os.replace(stage,target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {"status":"DART_CURRENT_DIRECTORY_RESEARCH_ONLY",
            "capture_id":target.name,"first_receipt_sha256":sha256(signed).hexdigest(),
            "total_corporations":count,
            "listed_codes":len(mapping),
            "ambiguous_codes":metadata["ambiguous_security_code_count"],
            "pit_certified":False}


def verify_dart_corp_directory(folder: Path, sha: str,
                                *, decision_at: datetime) -> dict:
    folder=Path(folder)
    if (not folder.is_absolute() or folder.is_symlink() or
            not folder.is_dir() or
            stat.S_IMODE(folder.stat().st_mode)!=0o700 or
            folder.stat().st_uid!=os.geteuid() or
            not re.fullmatch(r"[0-9a-f]{64}",sha)):
        raise ValueError("DART private first-directory SHA and folder required")
    receipt=_private_file(folder/"first_receipt.json",0o600)
    raw=_private_file(folder/"raw_directory.zip",0o600)
    if sha256(receipt).hexdigest()!=sha:
        raise ValueError("DART first directory receipt SHA altered")
    import json
    metadata=json.loads(receipt)
    if (metadata.get("schema")!=SCHEMA or
            metadata.get("raw_sha256")!=sha256(raw).hexdigest() or
            metadata.get("raw_length")!=len(raw) or
            metadata.get("current_directory_only") is not True or
            metadata.get("official_leaders")!=0 or
            metadata.get("historic_membership_pit_certified") is not False):
        raise ValueError("DART original directory receipt differs from raw")
    when=datetime.fromisoformat(metadata["first_local_received_at_utc"].replace("Z","+00:00"))
    if (when.tzinfo is None or decision_at.tzinfo is None or
            when>decision_at):
        raise ValueError("DART directory was not first received by decision")
    mapping,count=parse_directory_zip(raw)
    if (count!=metadata["total_corporations"] or len(mapping)!=metadata["listed_security_code_count"] or
            sum(len(v)>1 for v in mapping.values())!=metadata["ambiguous_security_code_count"]):
        raise ValueError("DART directory first count changed")
    if {p.name for p in folder.iterdir()}!={"raw_directory.zip","first_receipt.json"}:
        raise ValueError("DART directory extra unaccounted original")
    return {"mapping":{k:next(iter(v)) for k,v in mapping.items() if len(v)==1},
            "ambiguous_stock_codes":{k for k,v in mapping.items() if len(v)>1},
            "total_corporations":count,
            "listed_security_code_count":len(mapping),
            "first_local_received_at_utc":when.isoformat(),
            "first_receipt_sha256":sha,
            "historic_pit_certified":False}


def match_krx_codes(directory: dict, codes: set[str]) -> dict:
    matched=codes & set(directory["mapping"])
    conflicting=codes & directory["ambiguous_stock_codes"]
    return {"krx_total_observed":len(codes),
            "matched_unique_dart_corporation":len(matched),
            "ambiguous_codes_excluded":len(conflicting),
            "unmatched_or_nonunique":len(codes)-len(matched),
            "historical_pit_certified":False}
