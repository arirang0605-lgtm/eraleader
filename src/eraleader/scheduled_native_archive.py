"""5_5/6_5 opt-in private archive immediately after first-native capture.

Separate LOCAL first-write ZIP SHA receipt (not external attestation). Missing,
partial or rewritten archive/receipt/guard never silently resets. Existing
Top-K, WATCH, native scoring, scheduler and public Git paths are preserved.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import fcntl
import json
import os
import re

from .native_first_capture import (
    read_capture_plan, CAPTURE_NAME, _sha as source_sha,
)
from .native_evidence_archive import (
    _slot, _parse, _bytes, MANIFEST,
    create_native_evidence_archive, verify_native_evidence_archive,
)

SCHEMA="eraleader.scheduled_private_native_archive_receipt.v1"
GUARD_SCHEMA="eraleader.scheduled_native_archive_sha_guard.v1"
READY={
    "FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED",
    "ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY",
}
WAITING="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
SHA=re.compile(r"[a-f0-9]{64}\Z")


def _now(clock:datetime|None)->datetime:
    value=datetime.now(timezone.utc) if clock is None else clock
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Private original archive observation requires aware time")
    return value.astimezone(timezone.utc)


def _safe_output(project:Path,capture_root:Path):
    project=Path(project).absolute()
    output=project/"output"
    capture=Path(capture_root).absolute()
    if (project.is_symlink() or not project.is_dir() or
            output.is_symlink() or not output.is_dir() or
            capture.is_symlink() or capture.parent.is_symlink() or
            not capture.is_relative_to(output)):
        raise ValueError("Private first-native archive requires original local output")
    archives=output/"native_first_private_archives"
    receipts=output/"native_first_archive_receipts"
    for folder in (archives,receipts):
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ValueError("Unsafe linked first-native archive or SHA receipt root")
    return capture,archives,receipts


def _safe_path(path:Path):
    if path.is_symlink() or path.parent.is_symlink() or (
            path.exists() and not path.is_file()):
        raise ValueError("Unsafe linked first-native archive/SHA receipt")


def _new(path:Path,raw:bytes)->None:
    _safe_path(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as writer:
        writer.write(raw)
        writer.flush()
        os.fsync(writer.fileno())


def _read_exact(file:Path,max_bytes:int)->tuple[dict,bytes]:
    _safe_path(file)
    if not file.is_file() or not 0<file.stat().st_size<=max_bytes:
        raise ValueError("Missing or oversized private native original SHA receipt")
    raw=file.read_bytes()
    obj=_parse(raw)
    if type(obj) is not dict or raw!=_bytes(obj):
        raise ValueError("Rewritten/noncanonical private native original SHA receipt")
    return obj,raw


def _source_identity(capture_root:Path,plan:dict)->str:
    slot=_slot(plan)
    path=capture_root/("native_"+slot)/CAPTURE_NAME
    _safe_path(path)
    if not path.is_file():
        raise ValueError("Missing original first-native capture evidence")
    return source_sha(path)


def _read_archive_manifest(archive:Path)->dict:
    # Archive verifier has already bounded path count / member SHA / ZIP sizes.
    with ZipFile(archive,"r") as reader:
        return _parse(reader.read(MANIFEST))


def _verify_archive_source(
    archive:Path,digest:str,plan:dict,plan_sha:str,
    capture_root:Path,capture_sha:str,
)->dict:
    report=verify_native_evidence_archive(archive,expected_sha256=digest)
    details=_read_archive_manifest(archive)
    if (report.get("status")!="PRIVATE_NATIVE_EVIDENCE_ARCHIVE_VERIFIED" or
            report.get("real_future_leader_accuracy_certified") is not False or
            report.get("official_leader_promotions")!=0 or
            details.get("market")!=plan["market"] or
            details.get("model_version_sha256")!=sha256(
                plan["model_version"].encode()).hexdigest() or
            details.get("original_capture_root")!=str(capture_root) or
            details.get("plan_sha256")!=plan_sha or
            details.get("capture_receipt_sha256")!=capture_sha):
        raise ValueError("Original private native archive model/cohort/source identity revised")
    return report


def _verify_seal(
    first:Path,guard:Path,archive:Path,
    plan:dict,plan_sha:str,capture_root:Path,capture_sha:str,now:datetime,
)->dict:
    seal,raw=_read_exact(first,4096)
    witness,_=_read_exact(guard,2048)
    slot=_slot(plan)
    if (set(seal)!={"schema_version","market","model_version_sha256",
                    "slot","plan_sha256","capture_receipt_sha256",
                    "capture_root_sha256","archive_name","archive_sha256",
                    "archived_at_utc","nonce","external_timestamp_attested",
                    "independent_market_pit_certified","official_leader_promotions"} or
            seal["schema_version"]!=SCHEMA or seal["market"]!=plan["market"] or
            seal["slot"]!=slot or
            seal["model_version_sha256"]!=sha256(
                plan["model_version"].encode()).hexdigest() or
            seal["plan_sha256"]!=plan_sha or
            seal["capture_receipt_sha256"]!=capture_sha or
            seal["capture_root_sha256"]!=sha256(str(capture_root).encode()).hexdigest() or
            seal["archive_name"]!=archive.name or
            type(seal["archive_sha256"]) is not str or
            not SHA.fullmatch(seal["archive_sha256"]) or
            type(seal["nonce"]) is not str or
            not re.fullmatch(r"[a-f0-9]{32}",seal["nonce"]) or
            seal["external_timestamp_attested"] is not False or
            seal["independent_market_pit_certified"] is not False or
            type(seal["official_leader_promotions"]) is not int or
            seal["official_leader_promotions"]!=0):
        raise ValueError("Revised original private native first SHA receipt claims")
    try:
        at=datetime.fromisoformat(seal["archived_at_utc"])
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid private original archive receipt clock") from exc
    if at.tzinfo is None or at.utcoffset() is None or at.utcoffset().total_seconds()!=0:
        raise ValueError("Invalid private first archive UTC receipt")
    if at>now:
        raise ValueError("Private original archive receipt claims a future clock")
    if (set(witness)!={"schema_version","slot","receipt_sha256",
                        "nonce_sha256","independent_timestamp_attested"} or
            witness["schema_version"]!=GUARD_SCHEMA or
            witness["slot"]!=slot or
            witness["receipt_sha256"]!=sha256(raw).hexdigest() or
            witness["nonce_sha256"]!=sha256(seal["nonce"].encode()).hexdigest() or
            witness["independent_timestamp_attested"] is not False):
        raise ValueError("Original private native archive SHA receipt guard was replaced")
    _verify_archive_source(archive,seal["archive_sha256"],plan,plan_sha,
                           capture_root,capture_sha)
    return seal


def archive_captured_native_plan(
    project:Path,plan_file:Path,capture_root:Path,capture_result:dict,
    *,clock:datetime|None=None,
)->dict:
    """Use only AFTER a successful original first-native capture/registered census.

    WAITING never creates archive artifacts. On completion first ZIP+receipt+
    guard are O_EXCL immutable; partial states require review, not auto healing.
    """
    if (type(capture_result) is not dict or
            capture_result.get("status") not in READY|{WAITING} or
            capture_result.get("messages_sent")!=0 or
            capture_result.get("external_api_calls")!=0 or
            capture_result.get("official_leader_promotions")!=0 or
            capture_result.get("real_future_leader_accuracy_certified") is not False):
        raise ValueError("Unsafe/unverified native first capture cannot create private original archive")
    if capture_result["status"]==WAITING:
        return {
            "status":"WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN",
            "original_first_capture_status":WAITING,
            "archive_created":False,
            "archive_original_sha256":None,
            "separate_local_first_sha_receipt_verified":False,
            "external_timestamp_attested":False,
            "independent_market_pit_certified":False,
            "real_future_leader_accuracy_certified":False,
            "official_leader_promotions":0,"messages_sent":0,"external_api_calls":0,
        }
    now=_now(clock)
    capture_root,archive_root,receipt_root=_safe_output(project,capture_root)
    plan,plan_sha,sources=read_capture_plan(Path(plan_file))
    slot=_slot(plan)
    archive=archive_root/("native_"+slot+".zip")
    first=receipt_root/("native_"+slot+"_receipt.json")
    guard=receipt_root/("native_"+slot+"_guard.json")
    lock=receipt_root/(".native_"+slot+".lock")
    for path in (archive,first,guard,lock):
        _safe_path(path)
    capture_sha=_source_identity(capture_root,plan)
    originally_present=[p.exists() for p in (archive,first,guard,lock)]
    if any(originally_present) and not all(originally_present):
        raise ValueError("Partial/missing original native private archive and separate first SHA receipt")
    # Keep first-native source root distinct from the private ZIP/receipts root.
    if (capture_root in archive_root.parents or
            capture_root in receipt_root.parents or
            capture_root in (archive_root,receipt_root)):
        raise ValueError("Private native source archive overlaps original cohort root")
    archive_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    receipt_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock_existed=lock.exists()
    fd=os.open(lock,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as handle:
        try:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent private original native archive handoff") from exc
        try:
            flags=[p.exists() for p in (archive,first,guard)]
            if any(flags) and not all(flags):
                raise ValueError("Partial original native archive/first SHA receipt cannot be re-anchored")
            if all(flags):
                seal=_verify_seal(first,guard,archive,plan,plan_sha,
                                  capture_root,capture_sha,now)
                is_new=False
            else:
                if lock_existed:
                    raise ValueError("Previously activated first native archive lost original ZIP/receipt; refusing reset")
                if any(flags):
                    raise ValueError("Unsealed original native archive cannot become a late first SHA claim")
                original=create_native_evidence_archive(
                    Path(plan_file),capture_root,archive,
                    project=Path(project),clock=now,
                )
                if (original.get("status")!="PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_PIT_CERTIFIED" or
                        original.get("source_bytes_unchanged") is not True or
                        original.get("official_leader_promotions")!=0 or
                        original.get("messages_sent")!=0 or
                        original.get("external_api_calls")!=0 or
                        original.get("real_future_leader_accuracy_certified") is not False):
                    raise RuntimeError("Unsafe private native source archive result; original SHA not sealed")
                first_sha=original["archive_sha256"]
                if type(first_sha) is not str or not SHA.fullmatch(first_sha):
                    raise ValueError("First private native archive did not supply a SHA-256")
                _verify_archive_source(archive,first_sha,plan,plan_sha,
                                       capture_root,capture_sha)
                payload={
                    "schema_version":SCHEMA,"market":plan["market"],"slot":slot,
                    "model_version_sha256":sha256(plan["model_version"].encode()).hexdigest(),
                    "plan_sha256":plan_sha,
                    "capture_receipt_sha256":capture_sha,
                    "capture_root_sha256":sha256(str(capture_root).encode()).hexdigest(),
                    "archive_name":archive.name,"archive_sha256":first_sha,
                    "archived_at_utc":now.isoformat(),
                    "nonce":os.urandom(16).hex(),
                    "external_timestamp_attested":False,
                    "independent_market_pit_certified":False,
                    "official_leader_promotions":0,
                }
                body=_bytes(payload)
                witness={
                    "schema_version":GUARD_SCHEMA,"slot":slot,
                    "receipt_sha256":sha256(body).hexdigest(),
                    "nonce_sha256":sha256(payload["nonce"].encode()).hexdigest(),
                    "independent_timestamp_attested":False,
                }
                # Crash between ZIP and both receipts is an integrity incident:
                # never infer a new 'original SHA' from an unsealed existing ZIP.
                _new(first,body)
                _new(guard,_bytes(witness))
                seal=_verify_seal(first,guard,archive,plan,plan_sha,
                                  capture_root,capture_sha,now)
                is_new=True
            return {
                "status":("FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED"
                          if is_new else
                          "EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED"),
                "market":plan["market"],
                "original_first_capture_status":capture_result["status"],
                "archive_original_sha256":seal["archive_sha256"],
                "archive_created":is_new,
                "separate_local_first_sha_receipt_verified":True,
                "external_timestamp_attested":False,
                "independent_market_pit_certified":False,
                "real_future_leader_accuracy_certified":False,
                "official_leader_promotions":0,"messages_sent":0,
                "external_api_calls":0,
            }
        finally:
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
