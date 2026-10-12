"""6_5: opt-in independent local DRY-RUN integrity check for sticky roster policies.

The earliest locally valid policy SHA is chained to an independent first-write
observer. No API, message, market PIT or trusted external timestamp is claimed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import json
import os
import re
import uuid

from .exchange_roster_policy import verify_exchange_roster_policy

SCHEMA="eraleader.exchange_roster_policy_watchdog.v1"
DIR="exchange_policy_alerts"
ZERO="0"*64
MARKETS=("KR","US")
STATES={"HEALTHY","ANOMALY","NOT_ACTIVATED"}
ISSUES={"NONE","POLICY_DISAPPEARED","INCOMPLETE_POLICY",
        "UNSAFE_OR_CORRUPT_POLICY","PINNED_POLICY_REPLACED"}


def _bytes(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,
                       separators=(",",":"),allow_nan=False)+"\n").encode()


def _sha(blob):
    return sha256(blob).hexdigest()


def _now(clock):
    dt=clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(dt,datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Exchange policy watchdog requires aware UTC clock")
    return dt.astimezone(timezone.utc)


def _paths(project,policy_out):
    project=Path(project).absolute()
    root=project/"output"
    source=Path(policy_out).absolute()
    if project.is_symlink() or not project.is_dir() or root.is_symlink() or not root.is_dir():
        raise ValueError("Exchange policy watchdog requires real project/output")
    folder=root/DIR
    if folder==source or folder in source.parents:
        raise ValueError("Exchange policy watchdog source root overlaps audit")
    for p in (folder,folder/"genesis.json",folder/"history.jsonl",
              folder/"first_event.json",folder/".checks.lock",folder/"report.json",folder/"site",
              folder/"site"/"index.html"):
        if p.is_symlink():
            raise ValueError("Unsafe linked exchange policy watchdog artifact")
    return folder,source


def _utc(raw):
    if type(raw) is not str:
        raise ValueError("Invalid exchange policy watchdog clock")
    try:
        dt=datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Invalid exchange policy watchdog clock") from exc
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset().total_seconds()!=0:
        raise ValueError("Invalid exchange policy watchdog UTC clock")
    return dt


def _new(file,content):
    fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(content)
        out.flush()
        os.fsync(out.fileno())


def _unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:
            raise ValueError("Duplicate exchange policy watchdog JSON key")
        d[k]=v
    return d


def _json(raw):
    try:
        result=json.loads(raw,object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Corrupt exchange policy watchdog JSON") from exc
    return result


def _chain(folder,source):
    marker=folder/"genesis.json"
    history_file=folder/"history.jsonl"
    if not marker.is_file() or not history_file.is_file():
        raise ValueError("Missing exchange policy watchdog original receipt files")
    raw=marker.read_bytes()
    if not 0<len(raw)<=1024:
        raise ValueError("Oversized exchange policy watchdog genesis")
    stamp=_json(raw)
    if (type(stamp) is not dict or set(stamp)!={"schema","source_hash","nonce"} or
            stamp["schema"]!=SCHEMA or
            stamp["source_hash"]!=_sha(str(source).encode()) or
            type(stamp["nonce"]) is not str or
            not re.fullmatch(r"[0-9a-f]{32}",stamp["nonce"]) or
            raw!=_bytes(stamp)):
        raise ValueError("Exchange policy watchdog source root/genesis mismatch")
    data=history_file.read_bytes()
    if len(data)>50_000_000 or (data and not data.endswith(b"\n")):
        raise ValueError("Broken exchange policy watchdog log tail")
    prior=ZERO
    previous_at=None
    rows=[]
    trusted={m:ZERO for m in MARKETS}
    for no,line in enumerate(data.splitlines(),1):
        if len(line)>4096 or len(line)==0 or no>50000:
            raise ValueError("Oversized exchange policy watchdog event")
        event=_json(line)
        if type(event) is not dict or set(event)!={
                "seq","recorded_at_utc","states","issues","sha256",
                "new_alerts","previous_sha256","event_sha256"}:
            raise ValueError("Forged exchange policy watchdog event keys")
        at=_utc(event["recorded_at_utc"])
        if (type(event["seq"]) is not int or event["seq"]!=no or
                event["previous_sha256"]!=prior or
                (previous_at is not None and at<previous_at)):
            raise ValueError("Broken exchange policy watchdog chain/clock")
        previous_at=at
        if (type(event["states"]) is not dict or
                type(event["issues"]) is not dict or
                type(event["sha256"]) is not dict or
                any(set(event[k])!=set(MARKETS) for k in ("states","issues","sha256"))):
            raise ValueError("Incomplete exchange policy watchdog market evidence")
        for m in MARKETS:
            state,issue,digest=(event["states"][m],event["issues"][m],event["sha256"][m])
            if (state not in STATES or issue not in ISSUES or
                    type(digest) is not str or not re.fullmatch(r"[a-f0-9]{64}",digest) or
                    (state=="HEALTHY" and (issue!="NONE" or digest==ZERO)) or
                    (state=="NOT_ACTIVATED" and (issue!="NONE" or digest!=ZERO)) or
                    (state=="ANOMALY" and (issue=="NONE" or digest!=ZERO))):
                raise ValueError("Forged exchange policy watchdog health")
            if state=="HEALTHY":
                if trusted[m]!=ZERO and trusted[m]!=digest:
                    raise ValueError("Exchange policy watchdog first trusted SHA revised")
                trusted[m]=digest
        alerts=event["new_alerts"]
        legal={m+":"+s for m in MARKETS for s in ISSUES-{"NONE"}}
        legal|={m+":POLICY_RESTORED" for m in MARKETS}
        if (type(alerts) is not list or len(alerts)!=len(set(alerts)) or
                not set(alerts).issubset(legal)):
            raise ValueError("Forged exchange policy watchdog alert")
        unsigned={k:v for k,v in event.items() if k!="event_sha256"}
        if (event["event_sha256"]!=_sha(_bytes(unsigned)) or
                line+b"\n"!=_bytes(event)):
            raise ValueError("Broken exchange policy watchdog hash/bytes")
        prior=event["event_sha256"]
        rows.append(event)
    first=folder/"first_event.json"
    if first.is_symlink() or (first.exists() and not first.is_file()):
        raise ValueError("Unsafe exchange policy watchdog first-event receipt")
    if not rows:
        if first.exists():
            raise ValueError("Exchange policy watchdog first event deleted after receipt")
    else:
        if not first.is_file() or not 0<first.stat().st_size<=1024:
            raise ValueError("Missing exchange policy watchdog original first receipt")
        body=first.read_bytes()
        witness=_json(body)
        if (type(witness) is not dict or
                set(witness)!={"schema","event_sha256","genesis_sha256"} or
                witness["schema"]!=SCHEMA or
                witness["event_sha256"]!=rows[0]["event_sha256"] or
                witness["genesis_sha256"]!=_sha(raw) or
                body!=_bytes(witness)):
            raise ValueError("Broken exchange policy watchdog original first receipt")
    return rows,trusted


def _checkpoint(folder,rows):
    """Detect a whole-event log rollback against the last published local report."""
    file=folder/"report.json"
    if file.is_symlink() or (file.exists() and not file.is_file()):
        raise ValueError("Unsafe exchange policy watchdog report checkpoint")
    if not file.exists():
        if rows:
            raise ValueError("Missing exchange policy watchdog published chain checkpoint")
        return
    raw=file.read_bytes()
    if not 0<len(raw)<=4096:
        raise ValueError("Corrupt exchange policy watchdog report checkpoint")
    obj=_json(raw)
    last=rows[-1] if rows else {}
    if (type(obj) is not dict or raw!=_bytes(obj) or
            type(obj.get("check_count")) is not int or
            obj["check_count"]!=len(rows) or not rows or
            obj.get("chain_head_sha256")!=last["event_sha256"] or
            obj.get("market_states")!=last["states"] or
            obj.get("issue_codes")!=last["issues"] or
            obj.get("new_alerts")!=last["new_alerts"] or
            obj.get("status")!="LOCAL_EXCHANGE_POLICY_DRY_RUN_RECORDED" or
            obj.get("local_artifacts_only") is not True or
            obj.get("independent_pit_certified") is not False or
            obj.get("actual_future_leader_skill_certified") is not False or
            type(obj.get("official_leader_promotions")) is not int or
            obj["official_leader_promotions"]!=0 or
            type(obj.get("messages_sent")) is not int or
            obj["messages_sent"]!=0 or
            type(obj.get("external_api_calls")) is not int or
            obj["external_api_calls"]!=0):
        raise ValueError("Exchange policy watchdog published checkpoint mismatch / history rolled back")


def _snapshot(root,market,original):
    if root.is_symlink() or root.parent.is_symlink() or (root.exists() and not root.is_dir()):
        return "ANOMALY","UNSAFE_OR_CORRUPT_POLICY",ZERO
    primary=root/("provider_exchange_policy_"+market.lower()+".json")
    witness=root/("provider_exchange_policy_guard_"+market.lower()+".json")
    lock=root/(".provider_exchange_policy_"+market.lower()+".lock")
    if any(f.is_symlink() for f in (primary,witness,lock)):
        return "ANOMALY","UNSAFE_OR_CORRUPT_POLICY",ZERO
    presence=[f.exists() for f in (primary,witness,lock)]
    if not any(presence):
        if original!=ZERO:
            return "ANOMALY","POLICY_DISAPPEARED",ZERO
        return "NOT_ACTIVATED","NONE",ZERO
    if not all(presence) or not all(f.is_file() for f in (primary,witness,lock)):
        return "ANOMALY","INCOMPLETE_POLICY",ZERO
    try:
        fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(fd,"rb") as stream:
            fcntl.flock(stream.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)
            try:
                info=verify_exchange_roster_policy(root,market)
            finally:
                fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    except BlockingIOError as exc:
        raise RuntimeError("Concurrent roster writer; watchdog did not finish") from exc
    except (OSError,ValueError,KeyError,TypeError):
        return "ANOMALY","UNSAFE_OR_CORRUPT_POLICY",ZERO
    if not info or not info.get("guard_verified"):
        return "ANOMALY","UNSAFE_OR_CORRUPT_POLICY",ZERO
    digest=info["policy_sha256"]
    if original!=ZERO and original!=digest:
        return "ANOMALY","PINNED_POLICY_REPLACED",ZERO
    return "HEALTHY","NONE",digest


def verify_exchange_policy_watchdog(project,policy_out=None):
    """Read-only verification of all previously recorded local SHA events."""
    project=Path(project).absolute()
    source=(project/"output"/"strict_watch" if policy_out is None
            else Path(policy_out))
    folder,root=_paths(project,source)
    lock=folder/".checks.lock"
    if lock.is_symlink() or not lock.is_file():
        raise ValueError("Missing exchange policy watchdog audit lock")
    fd=os.open(lock,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_SH|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Exchange policy watchdog audit currently being updated") from exc
        try:
            rows,trusted=_chain(folder,root)
            _checkpoint(folder,rows)
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    return {
        "check_count":len(rows),
        "trusted_policy_sha256":trusted,
        "last_states":rows[-1]["states"] if rows else {},
        "chain_verified":True,
    }


def _atomic(file,body):
    temp=file.parent/("."+file.name+"."+uuid.uuid4().hex+".tmp")
    try:
        _new(temp,body)
        os.replace(temp,file)
    finally:
        temp.unlink(missing_ok=True)


def run_exchange_policy_watchdog(project,policy_out,*,clock=None):
    """Report local policy integrity without editing original WATCH or policy."""
    now=_now(clock)
    folder,source=_paths(project,policy_out)
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    (folder/"site").mkdir(mode=0o700,exist_ok=True)
    lock=folder/".checks.lock"
    lock_existed=lock.exists()
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent exchange policy watchdog") from exc
        try:
            first=folder/"genesis.json"
            log=folder/"history.jsonl"
            if not first.exists() and not log.exists():
                if lock_existed:
                    raise ValueError("Exchange policy watchdog first-write history deleted")
                stamp={"schema":SCHEMA,"source_hash":_sha(str(source).encode()),
                       "nonce":uuid.uuid4().hex}
                _new(first,_bytes(stamp))
                _new(log,b"")
            rows,trusted=_chain(folder,source)
            _checkpoint(folder,rows)
            if rows and now<_utc(rows[-1]["recorded_at_utc"]):
                raise ValueError("Exchange policy watchdog clock rollback")
            snap={m:_snapshot(source,m,trusted[m]) for m in MARKETS}
            states={m:snap[m][0] for m in MARKETS}
            issues={m:snap[m][1] for m in MARKETS}
            sha={m:snap[m][2] for m in MARKETS}
            previous=rows[-1] if rows else {}
            alerts=[]
            for m in MARKETS:
                old_status=previous.get("states",{}).get(m)
                old_issue=previous.get("issues",{}).get(m)
                if states[m]=="ANOMALY" and (
                        old_status!="ANOMALY" or old_issue!=issues[m]):
                    alerts.append(m+":"+issues[m])
                elif states[m]=="HEALTHY" and old_status=="ANOMALY":
                    alerts.append(m+":POLICY_RESTORED")
            event={
                "seq":len(rows)+1,"recorded_at_utc":now.isoformat(),
                "states":states,"issues":issues,"sha256":sha,
                "new_alerts":alerts,
                "previous_sha256":rows[-1]["event_sha256"] if rows else ZERO,
            }
            event["event_sha256"]=_sha(_bytes(event))
            with open(log,"ab",buffering=0) as sink:
                sink.write(_bytes(event))
                os.fsync(sink.fileno())
            if not rows:
                witness={"schema":SCHEMA,"event_sha256":event["event_sha256"],
                         "genesis_sha256":_sha(first.read_bytes())}
                _new(folder/"first_event.json",_bytes(witness))
            verified,trusted=_chain(folder,source)
            if len(verified)!=event["seq"]:
                raise RuntimeError("Exchange policy watchdog chain append not verified")
            result={
                "status":"LOCAL_EXCHANGE_POLICY_DRY_RUN_RECORDED",
                "check_count":len(verified),
                "chain_head_sha256":verified[-1]["event_sha256"],
                "market_states":states,
                "issue_codes":issues,"trusted_policy_sha256":trusted,
                "new_alerts":alerts,"local_artifacts_only":True,
                "independent_pit_certified":False,
                "actual_future_leader_skill_certified":False,
                "official_leader_promotions":0,
                "messages_sent":0,"external_api_calls":0,
            }
            _atomic(folder/"report.json",_bytes(result))
            _checkpoint(folder,verified)
            html=("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                  "<title>EraLeader local policy monitor</title>"
                  "<h1>Exchange roster WATCH policy — local DRY-RUN</h1>"
                  "<p>Checks: "+str(len(verified))+" | New warnings: "+
                  str(len(alerts))+"</p><table>"
                  "<tr><th>Market</th><th>Status</th><th>Issue</th></tr>"+
                  "".join("<tr><td>"+escape(m)+"</td><td>"+escape(states[m])+
                          "</td><td>"+escape(issues[m])+"</td></tr>" for m in MARKETS)+
                  "</table><p>Not PIT certified. No API, live alerts or official leader.</p>"
                  "</html>")
            _atomic(folder/"site"/"index.html",html.encode("utf-8"))
            return result
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
