"""6_5 opt-in SHA witness on a filesystem separate from the T5DATA source.

Stores ONLY digests: no WATCH, issuer, symbols, files, model names or paths.
Same Mac administrator can still change both volumes; timestamps are NOT
independently attested. No external API, cloud upload or scheduled installation.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from contextlib import closing
import fcntl
import os
import re
import stat

from .native_evidence_archive import _slot,_bytes,_parse
from .native_first_capture import read_capture_plan
from .scheduled_native_archive import (
    _safe_output,_source_identity,_verify_seal,READY,
)

SCHEMA="eraleader.native_original_cross_volume_sha_witness.v1"
GUARD_SCHEMA="eraleader.native_cross_volume_sha_witness_guard.v1"
SHA=re.compile(r"[a-f0-9]{64}\Z")
NONCE=re.compile(r"[a-f0-9]{32}\Z")


def _digest(blob:bytes)->str:
    return sha256(blob).hexdigest()


def _now(clock:datetime|None)->datetime:
    current=clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(current,datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Separate-volume witness requires aware local clock")
    return current.astimezone(timezone.utc)


def _separate_device(project:Path,nearest_existing:Path)->bool:
    """Actual macOS stat.st_dev check, not string/path-prefix comparison."""
    return project.stat().st_dev != nearest_existing.stat().st_dev


def validate_witness_destination(project:Path,witness_root:Path)->Path:
    """Read-only preflight; do NOT create directories or touch original ZIP."""
    project=Path(project).absolute()
    candidate=Path(witness_root)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Absolute safe separate-filesystem witness root required")
    root=candidate.absolute()
    if root==project or project in root.parents or root in project.parents or len(root.parts)<3:
        raise ValueError("Unsafe separate-volume witness root overlaps original project")
    if not project.is_dir() or project.is_symlink():
        raise ValueError("Missing native original research project")
    for p in (root,*root.parents):
        if p.is_symlink():
            raise ValueError("Linked cross-volume SHA witness root or ancestor")
    if root.exists() and not root.is_dir():
        raise ValueError("SHA witness root is not a directory")
    ancestor=root
    while not ancestor.exists():
        if ancestor==ancestor.parent:
            raise ValueError("Cannot identify separate witness filesystem")
        ancestor=ancestor.parent
    if not _separate_device(project,ancestor):
        raise ValueError("Witness must reside on a different filesystem/device than T5DATA SSD")
    if root.exists() and stat.S_IMODE(root.stat().st_mode)&0o077:
        raise ValueError("Private SHA witness directory must not be accessible by group/others")
    return root


def _new(file:Path,data:bytes)->None:
    if file.is_symlink() or file.parent.is_symlink() or file.exists():
        raise ValueError("Existing/unsafe first SHA witness destination")
    fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _read(file:Path,limit:int)->tuple[dict,bytes]:
    if (file.is_symlink() or file.parent.is_symlink() or
            not file.is_file() or not 0<file.stat().st_size<=limit):
        raise ValueError("Missing/linked/oversized separate-volume first SHA witness receipt")
    raw=file.read_bytes()
    value=_parse(raw)
    if type(value) is not dict or raw!=_bytes(value):
        raise ValueError("Rewritten/noncanonical separate-volume first SHA witness")
    return value,raw


def _witness_paths(root:Path,slot:str)->tuple[Path,Path,Path]:
    first=root/("native_"+slot+"_first.json")
    guard=root/("native_"+slot+"_guard.json")
    lock=root/(".native_"+slot+".lock")
    for file in (first,guard,lock):
        if file.is_symlink() or (file.exists() and not file.is_file()):
            raise ValueError("Linked or invalid separate-volume SHA witness path")
    return first,guard,lock


def _read_local_source(project:Path,plan_file:Path,capture_root:Path,
                       now:datetime)->dict:
    capture,archives,receipts=_safe_output(project,capture_root)
    plan,plan_sha,_=read_capture_plan(Path(plan_file))
    slot=_slot(plan)
    archive=archives/("native_"+slot+".zip")
    first=receipts/("native_"+slot+"_receipt.json")
    guard=receipts/("native_"+slot+"_guard.json")
    lock=receipts/(".native_"+slot+".lock")
    if any(p.is_symlink() for p in (archive,first,guard,lock)) or not all(
            p.is_file() for p in (archive,first,guard,lock)):
        raise ValueError("Missing/unsafe original native archive and first SHA receipt")
    capture_sha=_source_identity(capture,plan)
    sealed=_verify_seal(first,guard,archive,plan,plan_sha,capture,capture_sha,now)
    return {
        "market":plan["market"],"slot":slot,
        "model_sha256":_digest(plan["model_version"].encode()),
        "project_sha256":_digest(str(Path(project).absolute()).encode()),
        "capture_root_sha256":_digest(str(capture).encode()),
        "plan_sha256":plan_sha,"capture_receipt_sha256":capture_sha,
        "local_receipt_sha256":_digest(first.read_bytes()),
        "local_guard_sha256":_digest(guard.read_bytes()),
        "archive_sha256":sealed["archive_sha256"],
        "archived_at_utc":sealed["archived_at_utc"],
    }


def _checked_witness(first:Path,guard:Path,source:dict,now:datetime)->dict:
    stamp,raw=_read(first,4096)
    witness,_=_read(guard,2048)
    required={
        "schema_version","market","slot","model_sha256",
        "project_root_sha256","capture_root_sha256","plan_sha256",
        "capture_receipt_sha256","local_receipt_sha256","local_guard_sha256",
        "archive_sha256","archived_at_utc","first_witnessed_utc",
        "nonce","independent_timestamp_attested",
        "independent_market_pit_certified","official_leader_promotions",
    }
    fields={
        "market":"market","slot":"slot","model_sha256":"model_sha256",
        "project_root_sha256":"project_sha256",
        "capture_root_sha256":"capture_root_sha256",
        "plan_sha256":"plan_sha256",
        "capture_receipt_sha256":"capture_receipt_sha256",
        "local_receipt_sha256":"local_receipt_sha256",
        "local_guard_sha256":"local_guard_sha256",
        "archive_sha256":"archive_sha256",
        "archived_at_utc":"archived_at_utc",
    }
    if (set(stamp)!=required or stamp["schema_version"]!=SCHEMA or
            any(stamp[key]!=source[source_key] for key,source_key in fields.items()) or
            type(stamp["nonce"]) is not str or not NONCE.fullmatch(stamp["nonce"]) or
            stamp["independent_timestamp_attested"] is not False or
            stamp["independent_market_pit_certified"] is not False or
            type(stamp["official_leader_promotions"]) is not int or
            stamp["official_leader_promotions"]!=0):
        raise ValueError("Separate-volume original SHA witness contradicts first SSD receipt")
    try:
        observed=datetime.fromisoformat(stamp["first_witnessed_utc"])
        original=datetime.fromisoformat(stamp["archived_at_utc"])
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid cross-volume first-write local clock") from exc
    if (observed.tzinfo is None or observed.utcoffset() is None or
            observed.utcoffset().total_seconds()!=0 or observed>now or
            original.tzinfo is None or original.utcoffset() is None or
            original.utcoffset().total_seconds()!=0 or original>observed):
        raise ValueError("Cross-volume SHA witness clock must be UTC and not backdated")
    if (set(witness)!={"schema_version","slot","first_witness_sha256",
                       "nonce_sha256","independent_timestamp_attested"} or
            witness["schema_version"]!=GUARD_SCHEMA or
            witness["slot"]!=source["slot"] or
            witness["first_witness_sha256"]!=_digest(raw) or
            witness["nonce_sha256"]!=_digest(stamp["nonce"].encode()) or
            witness["independent_timestamp_attested"] is not False):
        raise ValueError("Separate-volume first SHA witness/guard integrity mismatch")
    return {
        "market":source["market"],"slot":source["slot"],
        "archive_sha256":source["archive_sha256"],
        "witness_sha256":_digest(raw),
    }


def _summary(source:dict,verified:dict,*,is_new:bool)->dict:
    return {
        "status":("FIRST_SEPARATE_VOLUME_NATIVE_SHA_WITNESSED_NOT_ATTESTED"
                  if is_new else
                  "EXISTING_SEPARATE_VOLUME_NATIVE_SHA_REVERIFIED_NOT_ATTESTED"),
        "market":source["market"],
        "archive_sha256":source["archive_sha256"],
        "witness_sha256":verified["witness_sha256"],
        "source_archive_verified":True,
        "separate_device_checked":True,
        "witness_created":is_new,
        "independent_timestamp_attested":False,
        "independent_market_pit_certified":False,
        "real_future_leader_accuracy_certified":False,
        "official_leader_promotions":0,
        "messages_sent":0,"external_api_calls":0,
    }


def record_native_sha_witness(
    project:Path,plan_file:Path,capture_root:Path,archive_result:dict,
    witness_root:Path,*,clock:datetime|None=None,
)->dict:
    """First-anchor a proven ZIP hash on a separate local filesystem.

    Call only after a verified scheduled private ZIP receipt. Original bytes
    are NEVER copied off the SSD; same-admin replacement is still possible.
    """
    if (type(archive_result) is not dict or
            archive_result.get("status") not in {
                "FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED",
                "EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED",
            } or
            archive_result.get("separate_local_first_sha_receipt_verified") is not True or
            archive_result.get("real_future_leader_accuracy_certified") is not False or
            archive_result.get("official_leader_promotions")!=0 or
            archive_result.get("messages_sent")!=0 or
            archive_result.get("external_api_calls")!=0 or
            archive_result.get("external_timestamp_attested") is not False):
        raise ValueError("Completed verified private archive receipt required before witness")
    now=_now(clock)
    root=validate_witness_destination(project,witness_root)
    source=_read_local_source(Path(project),Path(plan_file),Path(capture_root),now)
    if (archive_result.get("archive_original_sha256")!=source["archive_sha256"] or
            archive_result.get("market")!=source["market"]):
        raise ValueError("Private archive and requested witness original SHA disagree")
    first,guard,lock=_witness_paths(root,source["slot"])
    presence=[p.exists() for p in (first,guard,lock)]
    if any(presence) and not all(presence):
        raise ValueError("Partial separate-volume original SHA witness cannot self-reset")
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    root=validate_witness_destination(project,root)
    lock_existed=lock.exists()
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent separate-volume first SHA witness writer") from exc
        try:
            current=_read_local_source(Path(project),Path(plan_file),
                                       Path(capture_root),now)
            if current!=source:
                raise ValueError("Original native archive changed during SHA witness")
            if first.exists() != guard.exists():
                raise ValueError("Incomplete separate-volume original SHA witness seal")
            if first.exists():
                verified=_checked_witness(first,guard,source,now)
                return _summary(source,verified,is_new=False)
            if lock_existed:
                raise ValueError("Original separate-volume SHA witness lost first receipt; no reset")
            stamp={
                "schema_version":SCHEMA,"market":source["market"],
                "slot":source["slot"],
                "model_sha256":source["model_sha256"],
                "project_root_sha256":source["project_sha256"],
                "capture_root_sha256":source["capture_root_sha256"],
                "plan_sha256":source["plan_sha256"],
                "capture_receipt_sha256":source["capture_receipt_sha256"],
                "local_receipt_sha256":source["local_receipt_sha256"],
                "local_guard_sha256":source["local_guard_sha256"],
                "archive_sha256":source["archive_sha256"],
                "archived_at_utc":source["archived_at_utc"],
                "first_witnessed_utc":now.isoformat(),
                "nonce":os.urandom(16).hex(),
                "independent_timestamp_attested":False,
                "independent_market_pit_certified":False,
                "official_leader_promotions":0,
            }
            raw=_bytes(stamp)
            anchor={
                "schema_version":GUARD_SCHEMA,"slot":source["slot"],
                "first_witness_sha256":_digest(raw),
                "nonce_sha256":_digest(stamp["nonce"].encode()),
                "independent_timestamp_attested":False,
            }
            _new(first,raw)
            _new(guard,_bytes(anchor))
            verified=_checked_witness(first,guard,source,now)
            if _read_local_source(Path(project),Path(plan_file),
                                  Path(capture_root),now)!=source:
                raise ValueError("Original source was revised after cross-volume SHA seal")
            return _summary(source,verified,is_new=True)
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def verify_native_sha_witness(
    project:Path,plan_file:Path,capture_root:Path,witness_root:Path,
    *,clock:datetime|None=None,
)->dict:
    """Read-only audit of SSD ZIP and anchored different-filesystem digest."""
    now=_now(clock)
    root=validate_witness_destination(project,witness_root)
    source=_read_local_source(Path(project),Path(plan_file),Path(capture_root),now)
    first,guard,lock=_witness_paths(root,source["slot"])
    if not lock.is_file():
        raise ValueError("Missing original separate-volume first SHA witness lock")
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Separate-volume witness writer is active; read-only check incomplete") from exc
        try:
            evidence=_checked_witness(first,guard,source,now)
            if _read_local_source(Path(project),Path(plan_file),
                                  Path(capture_root),now)!=source:
                raise ValueError("Original native ZIP revised during cross-volume witness check")
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    report=_summary(source,evidence,is_new=False)
    return {**report,"status":"SEPARATE_VOLUME_NATIVE_SHA_VERIFIED_NOT_ATTESTED"}
