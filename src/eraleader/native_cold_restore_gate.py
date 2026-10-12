"""6_5 cold-custody restoration readiness: PIN + ciphertext + real replay + due.

Read-only audits the independently first-pinned AES-GCM custody archive and
the original authenticated WATCH/census replay history. Only an explicit opt-in
records a private, SHA-linked local observation. No key/decryption/network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zipfile import ZipFile
import fcntl
import os
import re
import stat
import uuid

from . import native_cold_integrity as cold
from . import native_cold_replay_drill as replay
from . import native_cold_custody as storage
from .native_sha_watchdog import _bytes, _json, _new, _atomic, _utc, ZERO

SCHEMA="eraleader.native_cold_restore_readiness.v1"
DIR="native_cold_restore_readiness"
STATUS="LOCAL_ENCRYPTED_COLD_RESTORE_READINESS_DRY_RUN"
STATES=frozenset({
    "READY_FRESH", "RESEARCH_ONLY_FRESH", "DUE_SOON", "OVERDUE",
    "NEVER_REPLAYED", "LAST_REPLAY_FAILED", "UNTRUSTED_COLD_SHA",
    "REPLAY_EVIDENCE_INVALID", "PIN_HISTORY_INVALID", "REPLAY_HISTORY_ROLLBACK",
    "PIN_HISTORY_ROLLBACK", "MISSING_REGISTERED_PIN",
})
OK=frozenset({"READY_FRESH","RESEARCH_ONLY_FRESH"})
HASH=re.compile("[a-f0-9]{64}\\Z")
MAX_EVENTS=10000
MAX_SLOTS=128


def _sha(data):
    return sha256(data).hexdigest()


def _now(value):
    dt=datetime.now(timezone.utc) if value is None else value
    if not isinstance(dt,datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Cold restore readiness requires timezone-aware local time")
    return dt.astimezone(timezone.utc)


def _config(project,pin_root,scratch,due_days,warn_days,max_gap_hours,research):
    if (type(due_days) is not int or not 1<=due_days<=365 or
            type(warn_days) is not int or not 0<=warn_days<due_days):
        raise ValueError("Restore readiness policy requires due 1..365 and warning < due")
    p,root,s=replay._inputs(project,pin_root,scratch,max_gap_hours,research)
    return p,root,s


def _base(p,root,s,due,warn,gap,research):
    return {"schema":SCHEMA,"project_path_sha256":_sha(str(p).encode()),
            "pin_root_path_sha256":_sha(str(root).encode()),
            "scratch_root_path_sha256":_sha(str(s).encode()),
            "due_days":due,"warn_days":warn,"max_gap_hours":gap,
            "research_only":research}


def _paths(p):
    root=p/"output"/DIR
    site=p/"output"/"site"
    dirs={root,root/"site"}
    for x in (root,root/"genesis.json",root/"history.jsonl",
              root/"first_event.json",root/"report.json",root/".checks.lock",
              root/"site",root/"site"/"index.html",
              site/"cold_restore_readiness.html",site/"index.html"):
        if x.is_symlink() or (x.exists() and not (
                x.is_dir() if x in dirs else x.is_file())):
            raise ValueError("Unsafe local restore readiness observer path")
    return root,site


def _head(events):
    return {"count":len(events),"sha256":events[-1]["event_sha256"] if events else ZERO}


def _source(root, audit, genesis, *, lock_file):
    """Validate one original immutable ledger under its original private lock."""
    lock=root/lock_file
    evidence_present=any((root/name).exists() or (root/name).is_symlink()
                         for name in ("genesis.json","history.jsonl",
                                      "first_event.json","checkpoint.json",
                                      "report.json",".checks.lock"))
    if not evidence_present:
        return [],True
    if (lock.is_symlink() or not lock.is_file() or
            lock.stat().st_uid!=os.geteuid() or
            stat.S_IMODE(lock.stat().st_mode)&0o077):
        return [],False
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as handle:
        try:
            fcntl.flock(handle.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Native source SHA ledger currently being written") from exc
        try:
            try:
                return audit(root,genesis),True
            except (ValueError,OSError,TypeError,KeyError):
                return [],False
        finally:
            fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def _recorded_source(previous,events,verified):
    """Anchor previously observed head: fully self-consistent rollback != healthy."""
    previous=previous or {"count":0,"sha256":ZERO}
    if not verified:
        return previous,False
    n=previous["count"]
    if (len(events)<n or
            (n and events[n-1]["event_sha256"]!=previous["sha256"])):
        return previous,False
    return _head(events),True


def _row(market,first,state,at=None,due=None):
    return {"market":market,"first_pin_sha256":first,"state":state,
            "last_replay_at_utc":at,"next_due_at_utc":due}


def _roster(archive,expected_sha):
    """Trusted SHA must bind the FULL multi-model census, not one sampled slot."""
    if storage._file_sha(archive,storage.MAX_PACKAGE)[0]!=expected_sha:
        raise ValueError("Cold package changed after original SHA inspection")
    with ZipFile(archive,"r") as zipped:
        item=zipped.getinfo(storage.MANIFEST)
        if item.file_size>65536:
            raise ValueError("Oversized frozen cold package roster")
        raw=zipped.read(item)
    meta=storage._parse(raw)
    slots,_,_=storage._validate_manifest(meta)
    if storage._file_sha(archive,storage.MAX_PACKAGE)[0]!=expected_sha:
        raise ValueError("Cold package changed while reading model roster")
    return slots


def _select_state(key,first,available,package_digests,rosters,replays,
                  now,due_days,warn_days,research):
    source_state=available.get(key,"UNTRUSTED_COLD_SHA")
    if source_state not in ("VERIFIED","RESEARCH_ONLY_VERIFIED"):
        return _row("UNKNOWN",first,"UNTRUSTED_COLD_SHA")
    slots=rosters.get(key,())
    if not slots:
        return _row("UNKNOWN",first,"UNTRUSTED_COLD_SHA")
    markets={slot[:2].upper() for slot in slots}
    market=next(iter(markets)) if len(markets)==1 else "MIXED"
    verified_dates=[]
    for slot in slots:
        model_sha=_sha(slot.encode())
        matching=[event for event in replays if
                  event["pin_id"]==key and event["slot_sha256"]==model_sha]
        if not matching:
            return _row(market,first,"NEVER_REPLAYED")
        last=matching[-1]
        if (last["first_pin_sha256"]!=first or
                last["outcome"]!="PASSED" or
                last["market"]!=slot[:2].upper() or
                last["package_sha256"]!=package_digests.get(key)):
            return _row(market,first,"LAST_REPLAY_FAILED")
        at=_utc(last["at_utc"])
        if at>now:
            return _row(market,first,"REPLAY_EVIDENCE_INVALID")
        verified_dates.append(at)
    # The oldest successful replay determines the next due date.
    oldest=min(verified_dates)
    following=oldest+timedelta(days=due_days)
    if now>=following:
        state="OVERDUE"
    elif now>=following-timedelta(days=warn_days):
        state="DUE_SOON"
    elif research or source_state=="RESEARCH_ONLY_VERIFIED":
        state="RESEARCH_ONLY_FRESH"
    else:
        state="READY_FRESH"
    return _row(market,first,state,oldest.isoformat(),following.isoformat())


def _alerts(old,new):
    changed=[]
    for key,row in sorted(new.items()):
        prior=old.get(key)
        if prior is None:
            if row["state"] not in OK:
                changed.append(key+":"+row["state"])
        elif row["state"]!=prior["state"]:
            changed.append(key+":"+(
                "RESTORED_FRESH_REPLAY" if row["state"] in OK else row["state"]))
    return changed


def _validate_row(key,row,prior=None):
    if type(key) is not str or HASH.fullmatch(key) is None:
        raise ValueError("Malformed restore-readiness hashed alias")
    if (type(row) is not dict or set(row)!={
            "market","first_pin_sha256","state",
            "last_replay_at_utc","next_due_at_utc"} or
            row["market"] not in ("KR","US","MIXED","UNKNOWN") or
            row["state"] not in STATES or
            type(row["first_pin_sha256"]) is not str or
            HASH.fullmatch(row["first_pin_sha256"]) is None):
        raise ValueError("Invalid originally pinned cold readiness row")
    for field in ("last_replay_at_utc","next_due_at_utc"):
        if row[field] is not None:
            _utc(row[field])
    if (row["state"] in (OK|{"DUE_SOON","OVERDUE"}) and
            (row["last_replay_at_utc"] is None or
             row["next_due_at_utc"] is None)):
        raise ValueError("False fresh or due status with no replay")
    if prior and prior["first_pin_sha256"]!=row["first_pin_sha256"]:
        raise ValueError("Cold restore first PIN substitution")


def _audit_observer(root,base):
    genesis,first_raw=cold._read_json(root/"genesis.json",2048)
    if (type(genesis) is not dict or set(genesis)!=set(base)|{"nonce"} or
            any(genesis.get(k)!=v for k,v in base.items()) or
            type(genesis.get("nonce")) is not str or
            re.fullmatch("[a-f0-9]{32}",genesis["nonce"]) is None):
        raise ValueError("Cold readiness first policy SHA changed")
    history=root/"history.jsonl"
    if history.is_symlink() or not history.is_file() or history.stat().st_size>80_000_000:
        raise ValueError("Original cold readiness SHA history missing")
    raw=history.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("Torn cold readiness event append")
    events=[]
    previous_head=ZERO
    previous_at=None
    previous_rows={}
    previous_pin={"count":0,"sha256":ZERO}
    previous_replay={"count":0,"sha256":ZERO}
    for line in raw.splitlines():
        if not 0<len(line)<=60_000 or len(events)>=MAX_EVENTS:
            raise ValueError("Oversized cold readiness SHA event")
        event=_json(line)
        if (type(event) is not dict or set(event)!={
                "seq","at_utc","rows","alerts","pin_source","replay_source",
                "previous_sha256","event_sha256"} or
                type(event["seq"]) is not int or event["seq"]!=len(events)+1 or
                event["previous_sha256"]!=previous_head or
                _bytes(event)!=line+b"\n"):
            raise ValueError("Cold readiness SHA event replaced or truncated")
        at=_utc(event["at_utc"])
        if previous_at is not None and at<previous_at:
            raise ValueError("Cold readiness historical OS clock rollback")
        previous_at=at
        rows=event["rows"]
        if (type(rows) is not dict or len(rows)>MAX_SLOTS or
                not set(previous_rows).issubset(rows) or
                event["alerts"]!=_alerts(previous_rows,rows)):
            raise ValueError("Cold readiness previous cohort vanished or warnings edited")
        for key,row in rows.items():
            _validate_row(key,row,previous_rows.get(key))
        for field,prior in (("pin_source",previous_pin),
                            ("replay_source",previous_replay)):
            current=event[field]
            if (type(current) is not dict or set(current)!={"count","sha256"} or
                    type(current["count"]) is not int or
                    not 0<=current["count"]<=30000 or
                    type(current["sha256"]) is not str or
                    HASH.fullmatch(current["sha256"]) is None or
                    (current["count"]==0)!=(current["sha256"]==ZERO) or
                    current["count"]<prior["count"] or
                    (current["count"]==prior["count"] and
                     current["sha256"]!=prior["sha256"])):
                raise ValueError("Cold readiness source chain head revised")
        digest=event["event_sha256"]
        if digest!=_sha(_bytes({k:v for k,v in event.items()
                               if k!="event_sha256"})):
            raise ValueError("Cold readiness independent SHA chain mismatch")
        previous_head=digest
        previous_rows=rows
        previous_pin=event["pin_source"]
        previous_replay=event["replay_source"]
        events.append(event)
    first=root/"first_event.json"
    report=root/"report.json"
    if events:
        receipt,_=cold._read_json(first,512)
        if receipt!={"schema":SCHEMA,"genesis_sha256":_sha(first_raw),
                     "first_event_sha256":events[0]["event_sha256"]}:
            raise ValueError("Cold readiness immutable first event missing")
        current,_=cold._read_json(report,100_000)
        last=events[-1]
        if (current.get("status")!=STATUS or current.get("checks")!=len(events) or
                current.get("chain_head_sha256")!=last["event_sha256"] or
                current.get("rows")!=last["rows"] or
                current.get("new_alerts")!=last["alerts"] or
                current.get("pin_source")!=last["pin_source"] or
                current.get("replay_source")!=last["replay_source"] or
                current.get("messages_sent")!=0 or
                current.get("external_api_calls")!=0 or
                current.get("official_leader_promotions")!=0 or
                current.get("official_market_pit_certified") is not False):
            raise ValueError("Cold readiness report SHA checkpoint altered")
    elif first.exists() or report.exists() or first.is_symlink() or report.is_symlink():
        raise ValueError("Cold readiness checkpoint exists without history")
    return events


def _html(report):
    rows="".join(
        "<tr><td>"+escape(key[:12])+"</td><td>"+
        escape(row["market"])+"</td><td>"+
        escape(row["state"])+"</td><td>"+
        escape(row["next_due_at_utc"] or "N/A")+"</td></tr>"
        for key,row in sorted(report["rows"].items()))
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            "<title>EraLeader cold recovery readiness</title>"
            "<h1>6_5 Cold ZIP + independent PIN + native replay readiness</h1>"
            "<p>Local read-only sources; NO private key/decryption, "
            "live delivery or official PIT/leader certification.</p>"
            "<p>Operational offsite is NOT attested by these SHA checks.</p>"
            "<p>Checks: "+str(report["checks"])+" | incidents: "+
            str(report["warning_count"])+"</p>"
            "<table><tr><th>Anonymous PIN</th><th>Market</th><th>Status</th>"
            "<th>Next rehearsal UTC</th></tr>"+rows+"</table>")


def _publish(p,folder,site,report):
    (folder/"site").mkdir(mode=0o700,parents=True,exist_ok=True)
    html=_html(report).encode()
    _atomic(folder/"site"/"index.html",html)
    if site.is_dir() and not site.is_symlink():
        _atomic(site/"cold_restore_readiness.html",html)
        index=site/"index.html"
        if index.is_file() and not index.is_symlink() and index.stat().st_size<=1_000_000:
            source=index.read_text(encoding="utf-8")
            if "cold_restore_readiness.html" not in source and "</body>" in source:
                anchor=("<p><a href='cold_restore_readiness.html'>"
                        "Cold native replay readiness DRY-RUN</a></p>")
                _atomic(index,source.replace("</body>",anchor+"</body>",1).encode())


def _observer_lock(folder,*,create):
    lock=folder/".checks.lock"
    previous=lock.exists()
    if lock.is_symlink() or (previous and not lock.is_file()):
        raise ValueError("Cold readiness lock linked or replaced")
    if not previous and any((folder/k).exists() or (folder/k).is_symlink()
                            for k in ("genesis.json","history.jsonl",
                                      "first_event.json","report.json")):
        raise ValueError("Cold readiness previous lock removed; no silent reset")
    if not previous and not create:
        raise ValueError("No first cold readiness SHA observation")
    flags=os.O_RDWR|getattr(os,"O_NOFOLLOW",0)
    if not previous:
        flags|=os.O_CREAT|os.O_EXCL
    fd=os.open(lock,flags,0o600)
    handle=os.fdopen(fd,"rb+")
    meta=os.fstat(handle.fileno())
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.geteuid() or
            stat.S_IMODE(meta.st_mode)&0o077):
        handle.close()
        raise ValueError("Unsafe cold readiness ledger writer lock")
    try:
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError("Concurrent cold readiness writer") from exc
    return handle,previous


def verify_restore_gate_history(project,pin_root,scratch,*,due_days=30,
                                warn_days=7,max_gap_hours=48,
                                allow_colocated_research=False):
    p,pr,s=_config(project,pin_root,scratch,due_days,warn_days,
                   max_gap_hours,allow_colocated_research)
    root,_=_paths(p)
    handle,_=_observer_lock(root,create=False)
    with handle:
        records=_audit_observer(root,_base(
            p,pr,s,due_days,warn_days,max_gap_hours,allow_colocated_research))
    return {"status":"COLD_RESTORE_READINESS_LOCAL_SHA_CHAIN_VERIFIED",
            "checks":len(records),
            "chain_head_sha256":records[-1]["event_sha256"] if records else ZERO,
            "private_key_accessed":False,"plaintext_decrypted":False,
            "external_api_calls":0,"messages_sent":0,
            "official_leader_promotions":0}


def run_cold_restore_gate(project,pin_root,scratch,*,due_days=30,
                          warn_days=7,max_gap_hours=48,
                          allow_colocated_research=False,clock=None):
    """Opt-in key-free quality gate: NEVER performs a decrypt or SHA re-pin."""
    now=_now(clock)
    p,pr,s=_config(project,pin_root,scratch,due_days,warn_days,
                   max_gap_hours,allow_colocated_research)
    folder,site=_paths(p)
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    handle,prior_lock=_observer_lock(folder,create=True)
    with handle:
        genesis,history=folder/"genesis.json",folder/"history.jsonl"
        base=_base(p,pr,s,due_days,warn_days,max_gap_hours,allow_colocated_research)
        if not genesis.exists() and not history.exists():
            if prior_lock:
                raise ValueError("Cold readiness original SHA chain was deleted")
            _new(genesis,_bytes({**base,"nonce":uuid.uuid4().hex}))
            _new(history,b"")
        prior=_audit_observer(folder,base)
        if prior and now<_utc(prior[-1]["at_utc"]):
            raise ValueError("Cold readiness local wall clock moved backwards")
        previous_rows=prior[-1]["rows"] if prior else {}
        prior_pins=prior[-1]["pin_source"] if prior else None
        prior_replay=prior[-1]["replay_source"] if prior else None

        pin_events, pin_valid=_source(pr,lambda r,_: cold._audit(r,p,max_gap_hours)[0],
                                     None,lock_file=".checks.lock")
        if pin_events and _utc(pin_events[-1]["at_utc"])>now:
            pin_valid=False  # A future local source timestamp is not a present proof.
        # The first-PIN ledger must itself be complete; _audit also returns
        # current unique hashed PINs to preserve the full denominator.
        pin_registered={}
        if pin_valid and pin_events:
            try:
                lock,_=cold._lock(pr,create=False)
                with lock:
                    checked, pin_registered, _,_ =cold._audit(pr,p,max_gap_hours)
                    if checked!=pin_events:
                        pin_valid=False
            except (ValueError,OSError,RuntimeError,KeyError):
                pin_valid=False
        current_pin_head,pin_continuity=_recorded_source(
            prior_pins,pin_events,pin_valid)
        if not pin_registered and not previous_rows:
            raise ValueError("No verified independent first-native cold SHA PIN inventory")
        original_root=p/"output"/replay.DIR
        replay_events,replay_valid=_source(
            original_root,replay._audit,
            replay._genesis(p,pr,s,max_gap_hours),lock_file=".checks.lock")
        if replay_events and _utc(replay_events[-1]["at_utc"])>now:
            replay_valid=False  # Never bless a future-dated authenticated replay.
        current_replay_head,replay_continuity=_recorded_source(
            prior_replay,replay_events,replay_valid)

        statuses={}
        package_digests={}
        rosters={}
        if pin_valid and pin_continuity:
            for key,first_sha in pin_registered.items():
                statuses[key]=cold._pin_state(pr,p,key,first_sha,
                                               research=allow_colocated_research)
                if statuses[key] in ("VERIFIED","RESEARCH_ONLY_VERIFIED"):
                    first_file,_=cold._pin_files(pr,key)
                    pin_meta,_=cold._read_json(first_file,4096)
                    package_digests[key]=pin_meta["package_sha256"]
                    try:
                        rosters[key]=_roster(Path(pin_meta["archive_path"]),
                                              package_digests[key])
                    except (ValueError,OSError,RuntimeError,KeyError,TypeError):
                        statuses[key]="PACKAGE_INVALID"
        old={key:row["first_pin_sha256"] for key,row in previous_rows.items()}
        all_ids=set(old)|set(pin_registered)
        if len(all_ids)>MAX_SLOTS:
            raise ValueError("Cold readiness PIN inventory exceeds 128")
        rows={}
        for key in sorted(all_ids):
            first=old.get(key,pin_registered.get(key))
            if (not pin_valid):
                state="PIN_HISTORY_INVALID"
            elif not pin_continuity:
                state="PIN_HISTORY_ROLLBACK"
            elif key not in pin_registered:
                state="MISSING_REGISTERED_PIN"
            elif first!=pin_registered[key]:
                # Never accept a newly minted first receipt under same alias.
                state="PIN_HISTORY_ROLLBACK"
            elif not replay_valid:
                state="REPLAY_EVIDENCE_INVALID"
            elif not replay_continuity:
                state="REPLAY_HISTORY_ROLLBACK"
            else:
                rows[key]=_select_state(
                    key,first,statuses,package_digests,rosters,replay_events,
                    now,due_days,warn_days,allow_colocated_research)
                continue
            rows[key]=_row("UNKNOWN",first,state)

        alerts=_alerts(previous_rows,rows)
        event={"seq":len(prior)+1,"at_utc":now.isoformat(),
               "rows":rows,"alerts":alerts,
               "pin_source":current_pin_head,
               "replay_source":current_replay_head,
               "previous_sha256":prior[-1]["event_sha256"] if prior else ZERO}
        event["event_sha256"]=_sha(_bytes(event))
        with history.open("ab",buffering=0) as out:
            out.write(_bytes(event))
            os.fsync(out.fileno())
        if not prior:
            _new(folder/"first_event.json",_bytes({
                "schema":SCHEMA,"genesis_sha256":_sha(genesis.read_bytes()),
                "first_event_sha256":event["event_sha256"]}))
        report={"status":STATUS,"checks":len(prior)+1,
                "chain_head_sha256":event["event_sha256"],"rows":rows,
                "new_alerts":alerts,"pin_source":current_pin_head,
                "replay_source":current_replay_head,
                "verified_replay_count":sum(x["state"]=="READY_FRESH" for x in rows.values()),
                "research_only_fresh_count":sum(x["state"]=="RESEARCH_ONLY_FRESH"
                                                for x in rows.values()),
                "warning_count":sum(x["state"] not in OK for x in rows.values()),
                "operational_offsite_attested":False,
                "private_key_accessed":False,"plaintext_decrypted":False,
                "local_artifacts_only":True,
                "official_market_pit_certified":False,
                "actual_future_leader_skill_certified":False,
                "messages_sent":0,"external_api_calls":0,
                "official_leader_promotions":0}
        _atomic(folder/"report.json",_bytes(report))
        if len(_audit_observer(folder,base))!=event["seq"]:
            raise RuntimeError("Cold restore readiness SHA checkpoint mismatch")
        _publish(p,folder,site,report)
        return report
