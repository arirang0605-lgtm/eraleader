"""6_5 explicit cold-package-to-original WATCH replay rehearsal, independent PIN.

Only an enrolled, separately first-pinned AES-GCM custody package is accepted.
A user-supplied owner-only private key is required for actual rehearsal. The
source original ZIP/first PIN are never replaced, and no scheduled key use occurs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
import fcntl
import os
import re
import stat
import uuid

from . import native_cold_integrity as cold
from .native_cold_custody import check_portable_native_custody
from .native_encrypted_vault import (
    SLOT, DIGEST, _private_key, _safe_private_root,
    verify_encrypted_native_original, restore_encrypted_native_original,
)
from .native_sha_witness import validate_witness_destination
from .native_sha_watchdog import ZERO, _bytes, _json, _utc, _new, _atomic

SCHEMA = "eraleader.cold_native_original_replay_drill.v1"
STATUS = "LOCAL_COLD_CUSTODY_ORIGINAL_REPLAY_REHEARSAL_NOT_PIT_CERTIFIED"
DIR = "native_cold_replay_drills"
MAX_EVENTS = 20_000
REASONS = frozenset({"NONE", "INDEPENDENT_PIN_NOT_VERIFIED",
                     "UNSAFE_OR_MISSING_KEY", "COLD_PACKAGE_RECONSTRUCTION_FAILED",
                     "ORIGINAL_WATCH_OR_CENSUS_REPLAY_FAILED",
                     "PRIVATE_TEMPORARY_CLEANUP_FAILED",
                     "INDEPENDENT_PIN_CHANGED_DURING_REHEARSAL"})


def _sha(data):
    return sha256(data).hexdigest()


def _now(clock):
    now = datetime.now(timezone.utc) if clock is None else clock
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Cold recovery rehearsal requires timezone-aware OS time")
    return now.astimezone(timezone.utc)


def _inputs(project, pin_root, scratch, gap, research):
    project, pin_root = cold._configured(
        project, pin_root, gap, research=research)
    scratch = validate_witness_destination(project, Path(scratch))
    scratch = _safe_private_root(scratch, must_exist=True)
    if (pin_root == scratch or pin_root in scratch.parents or
            scratch in pin_root.parents):
        raise ValueError("Temporary plaintext must not overlap independent PIN store")
    if not (project/"output").is_dir() or (project/"output").is_symlink():
        raise ValueError("Native original project needs existing local output root")
    return project, pin_root, scratch


def _ledger_paths(project):
    root = project/"output"/DIR
    site = project/"output"/"site"
    paths = [root, root/"history.jsonl", root/"genesis.json",
             root/"first_event.json", root/"report.json",root/".checks.lock",
             root/"site",root/"site"/"index.html",site/"cold_replay_drill.html",
             site/"index.html"]
    folders = {root,root/"site"}
    for path in paths:
        if path.is_symlink() or (path.exists() and not (
                path.is_dir() if path in folders else path.is_file())):
            raise ValueError("Linked or replaced cold recovery history path")
    return root, site


def _genesis(project, root, scratch, max_gap):
    return {"schema":SCHEMA,
            "project_path_sha256":_sha(str(project).encode()),
            "independent_pin_path_sha256":_sha(str(root).encode()),
            "scratch_path_sha256":_sha(str(scratch).encode()),
            "max_gap_hours":max_gap}


def _pinned(project, root, name, gap, research):
    """Read first PIN/entire ciphertext package with original immutable ledger lock."""
    identity = cold._identifier(name)
    lock, _ = cold._lock(root,create=False)
    with lock:
        _, registered, _, _ = cold._audit(root,project,gap)
        if identity not in registered:
            raise ValueError("Cold package has no independent first SHA PIN")
        state = cold._pin_state(root,project,identity,registered[identity],
                                research=research)
        if state not in ("VERIFIED","RESEARCH_ONLY_VERIFIED"):
            raise ValueError("First PIN/package/witness verification failed")
        pin,_=cold._pin_files(root,identity)
        obj,_=cold._read_json(pin,4096)
        if (obj.get("name")!=name or
                obj.get("colocated_research_only") and not research):
            raise ValueError("Unexpected original independent cold package identity")
        return {"pin_id":identity, "pin_sha256":registered[identity],
                "archive":Path(obj["archive_path"]),
                "package_sha256":obj["package_sha256"],
                "research_only":obj["colocated_research_only"]}


def _event_valid(event,seq,previous,at_prev):
    expected={"seq","at_utc","pin_id","slot_sha256","market","outcome",
              "reason","package_sha256","first_pin_sha256",
              "original_archive_sha256","cipher_sha256",
              "full_cold_zip_verified","aes_gcm_authenticated",
              "first_watch_score_replayed","census_index_replayed",
              "temporary_plaintext_removed","no_live_delivery",
              "previous_sha256","event_sha256"}
    if type(event) is not dict or set(event)!=expected:
        raise ValueError("Cold recovery event missing immutable proof fields")
    now=_utc(event["at_utc"])
    if (type(event["seq"]) is not int or event["seq"]!=seq or
            event["previous_sha256"]!=previous or
            at_prev is not None and now<at_prev):
        raise ValueError("Cold recovery SHA chain revision or clock rollback")
    if (event["market"] not in ("KR","US") or
            event["outcome"] not in ("PASSED","FAILED") or
            event["reason"] not in REASONS or
            event["no_live_delivery"] is not True):
        raise ValueError("Cold custody rehearsal result invalid")
    for key in ("pin_id","slot_sha256","package_sha256",
                "first_pin_sha256","original_archive_sha256","cipher_sha256"):
        if type(event[key]) is not str or DIGEST.fullmatch(event[key]) is None:
            raise ValueError("Cold recovery SHA digest malformed")
    flags=("full_cold_zip_verified","aes_gcm_authenticated",
           "first_watch_score_replayed","census_index_replayed",
           "temporary_plaintext_removed")
    if any(type(event[x]) is not bool for x in flags):
        raise ValueError("Cold recovery witness flags must be Boolean")
    if event["outcome"]=="PASSED":
        if (event["reason"]!="NONE" or
                any(event[x] is not True for x in flags) or
                any(event[k]==ZERO for k in
                    ("package_sha256","first_pin_sha256",
                     "original_archive_sha256","cipher_sha256"))):
            raise ValueError("Replayed original not authenticated as success")
    elif event["reason"]=="NONE":
        raise ValueError("Failed cold replay needs fixed incident code")
    if event["event_sha256"]!=_sha(_bytes(
            {k:v for k,v in event.items() if k!="event_sha256"})):
        raise ValueError("Tampered cold restoration proof chain")
    return now


def _audit(folder,base):
    source,history=folder/"genesis.json",folder/"history.jsonl"
    if any(p.is_symlink() or not p.is_file() for p in (source,history)):
        raise ValueError("Cold recovery history genesis missing")
    first_raw=source.read_bytes()
    first=_json(first_raw)
    if (not 0<len(first_raw)<=2048 or type(first) is not dict or
            set(first)!=set(base)|{"nonce"} or
            any(first.get(k)!=v for k,v in base.items()) or
            type(first.get("nonce")) is not str or
            re.fullmatch("[a-f0-9]{32}",first["nonce"]) is None or
            _bytes(first)!=first_raw):
        raise ValueError("Cold recovery first local integrity genesis replaced")
    if (history.stat().st_size>40_000_000 or history.is_symlink()):
        raise ValueError("Oversized or unsafe recovery SHA history")
    raw=history.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Torn append-only cold replay chain")
    prior,head,last_time=[],ZERO,None
    for line in raw.splitlines():
        if not 0<len(line)<=4096 or len(prior)>=MAX_EVENTS:
            raise ValueError("Cold replay historical event exceeds safety bound")
        event=_json(line)
        last_time=_event_valid(event,len(prior)+1,head,last_time)
        if line+b"\n"!=_bytes(event):
            raise ValueError("Cold replay history noncanonical")
        head=event["event_sha256"]
        prior.append(event)
    first_event=folder/"first_event.json"
    report=folder/"report.json"
    if prior:
        original,body=cold._read_json(first_event,512)
        if original!={"schema":SCHEMA,"genesis_sha256":_sha(first_raw),
                       "first_event_sha256":prior[0]["event_sha256"]}:
            raise ValueError("Cold replay immutable first event receipt replaced")
        latest,body=cold._read_json(report,4096)
        if (latest.get("status")!=STATUS or
                latest.get("check_count")!=len(prior) or
                latest.get("chain_head_sha256")!=head or
                latest.get("latest")!=prior[-1] or
                latest.get("messages_sent")!=0 or
                latest.get("external_api_calls")!=0 or
                latest.get("official_leader_promotions")!=0 or
                latest.get("independent_market_pit_certified") is not False or
                latest.get("actual_future_leader_skill_certified") is not False):
            raise ValueError("Cold recovery local SHA checkpoint lost or rewritten")
    elif first_event.exists() or report.exists() or first_event.is_symlink() or report.is_symlink():
        raise ValueError("Unexpected cold replay checkpoint without historical event")
    return prior


def _html(report):
    item=report["latest"]
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader cold native recovery rehearsal</title>"
            "<h1>6_5 encrypted cold package - original native replay</h1>"
            "<p>Local opt-in rehearsal. No published PIT/leader proof or live delivery. "
            "Temporary plaintext deletion is NOT guaranteed secure erasure.</p>"
            "<p>Checks: "+str(report["check_count"])+"</p>"
            "<table><tr><th>Market</th><th>Outcome</th><th>Code</th><th>Slot digest</th></tr>"
            "<tr><td>"+escape(item["market"])+"</td><td>"+
            escape(item["outcome"])+"</td><td>"+escape(item["reason"])+
            "</td><td>"+escape(item["slot_sha256"][:12])+"</td></tr></table>")


def _publish(folder,site,report):
    (folder/"site").mkdir(mode=0o700,parents=True,exist_ok=True)
    _atomic(folder/"site"/"index.html",_html(report).encode())
    if site.is_dir() and not site.is_symlink():
        _atomic(site/"cold_replay_drill.html",_html(report).encode())
        index=site/"index.html"
        if index.is_file() and not index.is_symlink() and index.stat().st_size<1_000_000:
            raw=index.read_text(encoding="utf-8")
            if "cold_replay_drill.html" not in raw and "</body>" in raw:
                text=("<p><a href='cold_replay_drill.html'>"
                      "Cold custody original replay DRY-RUN</a></p>")
                _atomic(index,raw.replace("</body>",text+"</body>",1).encode())


def verify_cold_replay_history(project,pin_root,scratch,*,max_gap_hours=48,
                               allow_colocated_research=False):
    """Key-free, read-only SHA history check, not a proof of current plaintext."""
    project,pin_root,scratch=_inputs(
        project,pin_root,scratch,max_gap_hours,allow_colocated_research)
    root,_=_ledger_paths(project)
    lock=root/".checks.lock"
    if lock.is_symlink() or not lock.is_file():
        raise ValueError("No independent cold replay writer lock")
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as handler:
        if (stat.S_IMODE(os.fstat(handler.fileno()).st_mode)&0o077 or
                os.fstat(handler.fileno()).st_uid!=os.geteuid()):
            raise ValueError("Cold recovery ledger lock is not private")
        try:
            fcntl.flock(handler.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Cold replay writer running") from exc
        try:
            events=_audit(root,_genesis(project,pin_root,scratch,max_gap_hours))
        finally:
            fcntl.flock(handler.fileno(),fcntl.LOCK_UN)
    return {"status":"LOCAL_COLD_ORIGINAL_REPLAY_CHAIN_VERIFIED",
            "check_count":len(events),"chain_verified":True,
            "latest_event_sha256":events[-1]["event_sha256"] if events else ZERO,
            "private_key_accessed":False,"plaintext_decrypted":False,
            "messages_sent":0,"external_api_calls":0,"official_leader_promotions":0}


def run_cold_replay_drill(project,pin_root,name,slot,key,scratch,*,
                          max_gap_hours=48,allow_colocated_research=False,clock=None):
    """Perform user-requested PIN->cold ZIP->AES-GCM->first WATCH/census replay.

    The original package must first be enrolled using an independently kept
    SHA; source SHA and private key never get emitted to local HTML.
    """
    if type(slot) is not str or SLOT.fullmatch(slot) is None:
        raise ValueError("Specify one original KR/US hashed market/model slot")
    cold._identifier(name)
    now=_now(clock)
    project,pin_root,scratch=_inputs(
        project,pin_root,scratch,max_gap_hours,allow_colocated_research)
    root,site=_ledger_paths(project)
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=root/".checks.lock"
    existed=lock.exists()
    if not existed and any((root/name).exists() for name in (
            "genesis.json","history.jsonl","report.json","first_event.json")):
        raise ValueError("First cold replay lock lost; do not rewrite evidence")
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as handler:
        if (stat.S_IMODE(os.fstat(handler.fileno()).st_mode)&0o077 or
                os.fstat(handler.fileno()).st_uid!=os.geteuid()):
            raise ValueError("Unsafe nonprivate cold recovery writer lock")
        try:
            fcntl.flock(handler.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Cold replay history concurrently locked") from exc
        try:
            genesis,history=root/"genesis.json",root/"history.jsonl"
            if not genesis.exists() and not history.exists():
                if existed:
                    raise ValueError("Original SHA replay history removed: no silent reset")
                _new(genesis,_bytes({**_genesis(project,pin_root,scratch,max_gap_hours),
                                     "nonce":uuid.uuid4().hex}))
                _new(history,b"")
            previous=_audit(root,_genesis(project,pin_root,scratch,max_gap_hours))
            if previous and now<_utc(previous[-1]["at_utc"]):
                raise ValueError("Cold recovery OS clock rolled backward")
            result={"outcome":"FAILED","reason":"INDEPENDENT_PIN_NOT_VERIFIED",
                    "package_sha256":ZERO,"first_pin_sha256":ZERO,
                    "original_archive_sha256":ZERO,"cipher_sha256":ZERO,
                    "full_cold_zip_verified":False,
                    "aes_gcm_authenticated":False,"first_watch_score_replayed":False,
                    "census_index_replayed":False,"temporary_plaintext_removed":False}
            pinned=None
            try:
                pinned=_pinned(project,pin_root,name,max_gap_hours,
                               allow_colocated_research)
                result.update(package_sha256=pinned["package_sha256"],
                              first_pin_sha256=pinned["pin_sha256"],
                              full_cold_zip_verified=True)
            except (ValueError,OSError,RuntimeError,KeyError,TypeError):
                pass
            if pinned is not None:
                try:
                    _private_key(Path(key))
                except (ValueError,OSError,RuntimeError,TypeError):
                    result["reason"]="UNSAFE_OR_MISSING_KEY"
                else:
                    result["reason"]="COLD_PACKAGE_RECONSTRUCTION_FAILED"
                    folder=None
                    try:
                        with TemporaryDirectory(prefix=".cold-original-replay-",dir=scratch) as tmp:
                            folder=Path(tmp)
                            encrypted=folder/"portable_encrypted_original"
                            rebuilt=check_portable_native_custody(
                                pinned["archive"],pinned["package_sha256"],
                                restore_target=encrypted)
                            if (rebuilt.get("status") !=
                                    "PORTABLE_ENCRYPTED_NATIVE_CUSTODY_RESTORED_NOT_DECRYPTED" or
                                    rebuilt.get("ciphertext_and_first_witness_verified") is not True or
                                    rebuilt.get("plaintext_authenticated_or_replayed") is not False or
                                    rebuilt.get("private_key_accessed") is not False or
                                    rebuilt.get("messages_sent")!=0 or
                                    rebuilt.get("external_api_calls")!=0 or
                                    rebuilt.get("official_leader_promotions")!=0):
                                raise RuntimeError("Encrypted-only cold package not reconstructed")
                            vault,witness,cert=(
                                encrypted/"vault",encrypted/"witness",
                                encrypted/"public"/"original_recipient.crt")
                            original=verify_encrypted_native_original(
                                vault,slot,witness,cert)
                            if (original.get("status")!=
                                    "ENCRYPTED_NATIVE_BACKUP_SHA_VERIFIED_NOT_DECRYPTED" or
                                    original.get("ciphertext_verified") is not True or
                                    original.get("messages_sent")!=0 or
                                    original.get("external_api_calls")!=0 or
                                    original.get("official_leader_promotions")!=0):
                                raise RuntimeError("Cold reconstruction original SHA invalid")
                            result.update(original_archive_sha256=original["archive_sha256"],
                                          cipher_sha256=original["encrypted_sha256"])
                            result["reason"]="ORIGINAL_WATCH_OR_CENSUS_REPLAY_FAILED"
                            replay=restore_encrypted_native_original(
                                vault,slot,witness,cert,Path(key),
                                folder/"temporary_original_replay")
                            if (replay.get("status")!=
                                    "ENCRYPTED_NATIVE_FIRST_ORIGINAL_RESTORED_NOT_PIT_CERTIFIED" or
                                    replay.get("archive_sha256")!=result["original_archive_sha256"] or
                                    replay.get("authenticated_plaintext_verified") is not True or
                                    replay.get("first_original_watch_replayed") is not True or
                                    replay.get("registered_index_chain_verified") is not True or
                                    replay.get("messages_sent")!=0 or
                                    replay.get("external_api_calls")!=0 or
                                    replay.get("official_leader_promotions")!=0 or
                                    replay.get("real_future_leader_accuracy_certified") is not False):
                                raise RuntimeError("Original WATCH/census replay not verified")
                            result.update(aes_gcm_authenticated=True,
                                          first_watch_score_replayed=True,
                                          census_index_replayed=True)
                    except (OSError,RuntimeError,ValueError,KeyError,TypeError):
                        pass
                    if folder is not None and folder.exists():
                        result["reason"]="PRIVATE_TEMPORARY_CLEANUP_FAILED"
                    else:
                        result["temporary_plaintext_removed"]=True
                    try:
                        afterward=_pinned(project,pin_root,name,max_gap_hours,
                                          allow_colocated_research)
                        if (afterward["package_sha256"]!=pinned["package_sha256"] or
                                afterward["pin_sha256"]!=pinned["pin_sha256"] or
                                afterward["archive"]!=pinned["archive"]):
                            raise ValueError("PIN or source changed during explicit rehearsal")
                    except (OSError,ValueError,RuntimeError,KeyError,TypeError):
                        result["reason"]="INDEPENDENT_PIN_CHANGED_DURING_REHEARSAL"
                    if (all(result[k] is True for k in (
                            "full_cold_zip_verified","aes_gcm_authenticated",
                            "first_watch_score_replayed","census_index_replayed",
                            "temporary_plaintext_removed")) and
                            result["reason"]=="ORIGINAL_WATCH_OR_CENSUS_REPLAY_FAILED"):
                        # This reason is only cleared when a real original replay succeeded.
                        result["outcome"]="PASSED"
                        result["reason"]="NONE"
            event={"seq":len(previous)+1,"at_utc":now.isoformat(),
                   "pin_id":cold._identifier(name),"slot_sha256":_sha(slot.encode()),
                   "market":slot[:2].upper(),**result,"no_live_delivery":True,
                   "previous_sha256":previous[-1]["event_sha256"] if previous else ZERO}
            event["event_sha256"]=_sha(_bytes(event))
            _event_valid(event,len(previous)+1,event["previous_sha256"],
                         _utc(previous[-1]["at_utc"]) if previous else None)
            with history.open("ab",buffering=0) as output:
                output.write(_bytes(event))
                os.fsync(output.fileno())
            if not previous:
                _new(root/"first_event.json",_bytes({
                    "schema":SCHEMA,"genesis_sha256":_sha(genesis.read_bytes()),
                    "first_event_sha256":event["event_sha256"]}))
            report={"status":STATUS,"check_count":len(previous)+1,
                    "chain_head_sha256":event["event_sha256"],"latest":event,
                    "independent_market_pit_certified":False,
                    "actual_future_leader_skill_certified":False,
                    "official_leader_promotions":0,"messages_sent":0,"external_api_calls":0}
            _atomic(root/"report.json",_bytes(report))
            if len(_audit(root,_genesis(project,pin_root,scratch,max_gap_hours)))!=len(previous)+1:
                raise RuntimeError("Cold replay SHA report not independently consistent")
            _publish(root,site,report)
            return report
        finally:
            fcntl.flock(handler.fileno(),fcntl.LOCK_UN)
