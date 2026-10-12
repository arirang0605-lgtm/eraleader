"""2_2/2_5: sticky, first-write research-only whole-exchange WATCH policy.

This is a LOCAL anti-accidental-downgrade guard. Matching issuer and source
claims, hashes, and a local OS clock cannot independently certify exchange
provenance, true historical PIT, or future alpha.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import re

SCHEMA="eraleader.first_write_exchange_roster_watch_policy.v1"
GUARD_SCHEMA="eraleader.first_write_exchange_roster_policy_guard.v1"
MINIMUM="PINNED_TWO_SUPPLIERS_AND_ISSUER_CLASS_AND_FULL_EXCHANGE_ROSTER"
SHA=re.compile(r"[a-f0-9]{64}\Z")
MAX_BYTES=4096


def _bytes(record:dict) -> bytes:
    return json.dumps(record,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")+b"\n"


def _filenames(root:Path,market:str) -> tuple[Path,Path,Path]:
    if market not in ("KR","US"):
        raise ValueError("Exchange roster policy requires KR or US")
    root=Path(root).absolute()
    if (root.is_symlink() or root.parent.is_symlink() or
            (root.exists() and not root.is_dir())):
        raise ValueError("Unsafe exchange roster policy output directory")
    low=market.lower()
    return (root/("provider_exchange_policy_"+low+".json"),
            root/("provider_exchange_policy_guard_"+low+".json"),
            root/(".provider_exchange_policy_"+low+".lock"))


def _check_path(path:Path) -> None:
    if path.is_symlink() or path.parent.is_symlink() or (
            path.exists() and not path.is_file()):
        raise ValueError("Unsafe exchange roster policy/guard path")


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicated local exchange roster policy field")
        result[key]=value
    return result


def _read(file:Path) -> tuple[dict,bytes]:
    _check_path(file)
    if not file.is_file() or not 0<file.stat().st_size<=MAX_BYTES:
        raise ValueError("Missing/corrupt first-write exchange roster policy file")
    raw=file.read_bytes()
    if not 0<len(raw)<=MAX_BYTES:
        raise ValueError("Oversized exchange roster policy file")
    try:
        obj=json.loads(raw,object_pairs_hook=_unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           ValueError("Nonfinite local exchange policy field")))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Invalid first-write exchange roster policy JSON") from exc
    if type(obj) is not dict or raw!=_bytes(obj):
        raise ValueError("Rewritten/invalid first-write exchange roster policy bytes")
    return obj,raw


def verify_exchange_roster_policy(out:Path,market:str) -> dict|None:
    """Strict read-only validator. Missing BOTH means never sealed, not certified.

    Missing just one is a partial-loss integrity incident and never resets the
    minimum gate. Both files are locally replaceable by a privileged actor.
    """
    primary,guard,_=_filenames(out,market)
    _check_path(primary);_check_path(guard)
    if not primary.exists() and not guard.exists():
        return None
    policy,raw=_read(primary)
    witness,_=_read(guard)
    if (set(policy)!={"schema_version","market","minimum_gate",
                      "first_observed_utc","first_roster_sha256",
                      "nonce","independent_pit_certified","official_leader_promotions"} or
            policy["schema_version"]!=SCHEMA or policy["market"]!=market or
            policy["minimum_gate"]!=MINIMUM or
            type(policy["independent_pit_certified"]) is not bool or
            policy["independent_pit_certified"] is not False or
            type(policy["official_leader_promotions"]) is not int or
            policy["official_leader_promotions"]!=0 or
            type(policy["first_roster_sha256"]) is not str or
            not SHA.fullmatch(policy["first_roster_sha256"]) or
            type(policy["nonce"]) is not str or
            not re.fullmatch(r"[a-f0-9]{32}",policy["nonce"])):
        raise ValueError("Invalid/forged local first-write exchange roster policy claims")
    try:
        when=datetime.fromisoformat(policy["first_observed_utc"])
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid first observation UTC clock") from exc
    if when.tzinfo is None or when.utcoffset() is None or when.utcoffset().total_seconds()!=0:
        raise ValueError("First-write exchange policy clock must be UTC")
    if (set(witness)!={"schema_version","market","policy_sha256",
                       "policy_nonce_sha256","independent_pit_certified"} or
            witness["schema_version"]!=GUARD_SCHEMA or
            witness["market"]!=market or
            witness["independent_pit_certified"] is not False or
            witness["policy_sha256"]!=sha256(raw).hexdigest() or
            witness["policy_nonce_sha256"]!=sha256(policy["nonce"].encode()).hexdigest()):
        raise ValueError("Broken/replaced local first-write exchange roster policy guard")
    return {
        "status":"LOCAL_PINNED_EXCHANGE_WATCH_POLICY_NOT_PIT_CERTIFIED",
        "market":market,"minimum_gate":MINIMUM,
        "first_roster_sha256":policy["first_roster_sha256"],
        "policy_sha256":sha256(raw).hexdigest(),
        "guard_verified":True,"independent_pit_certified":False,
        "official_leader_promotions":0,
    }


def _write_new(path:Path,body:bytes) -> None:
    _check_path(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())


class PolicySession:
    def __init__(self,root:Path,market:str,existing:dict|None):
        self.root=Path(root).absolute()
        self.market=market
        self.existing=existing

    def assert_unchanged(self) -> None:
        """Stop before publishing if protected policy bytes changed mid-run."""
        if self.existing is not None:
            if verify_exchange_roster_policy(self.root,self.market)!=self.existing:
                raise RuntimeError("First-write exchange roster policy revised during WATCH research")

    def require_first_write(self,roster_sha256:str) -> dict:
        """Call AFTER complete strict CLI flags, BEFORE any market/watch write."""
        if type(roster_sha256) is not str or not SHA.fullmatch(roster_sha256):
            raise ValueError("Invalid exchange roster SHA before first policy registration")
        if self.existing is not None:
            return self.existing
        primary,guard,_=_filenames(self.root,self.market)
        payload={
            "schema_version":SCHEMA,"market":self.market,"minimum_gate":MINIMUM,
            "first_observed_utc":datetime.now(timezone.utc).isoformat(),
            "first_roster_sha256":roster_sha256,
            "nonce":os.urandom(16).hex(),
            "independent_pit_certified":False,"official_leader_promotions":0,
        }
        raw=_bytes(payload)
        check={
            "schema_version":GUARD_SCHEMA,"market":self.market,
            "policy_sha256":sha256(raw).hexdigest(),
            "policy_nonce_sha256":sha256(payload["nonce"].encode()).hexdigest(),
            "independent_pit_certified":False,
        }
        # Crash after one first-write leaves a partial seal which is
        # intentionally BLOCKED on every subsequent invocation.
        _write_new(primary,raw)
        _write_new(guard,_bytes(check))
        self.existing=verify_exchange_roster_policy(self.root,self.market)
        assert self.existing is not None
        return self.existing


@contextmanager
def guard_integrated_policy(out:Path,market:str,*,strict_mode:bool):
    """Serialize strict runs; reject later unflagged downgrades BEFORE DB open.

    Legacy outputs without a policy and without opt-in have no new artifacts.
    """
    root=Path(out).absolute()
    primary,guard,lock=_filenames(root,market)
    _check_path(primary);_check_path(guard);_check_path(lock)
    lock_existed=lock.exists()
    if (not strict_mode and not primary.exists() and not guard.exists()
            and not lock_existed):
        yield PolicySession(root,market,None)
        return
    root.mkdir(parents=True,exist_ok=True)
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"rb+") as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Concurrent protected exchange roster WATCH run") from exc
        try:
            existing=verify_exchange_roster_policy(root,market)
            if existing is None and lock_existed:
                raise ValueError("Previously activated exchange roster policy has no sealed receipts; refusing reset")
            if existing is not None and not strict_mode:
                raise ValueError("Pinned exchange roster policy forbids silent downgrade to a weaker WATCH gate")
            yield PolicySession(root,market,existing)
            # Seal may be first-written during validation. Any partial
            # marker loss or alteration before the run returns fails closed.
            if strict_mode:
                final=verify_exchange_roster_policy(root,market)
                if final is None:
                    raise RuntimeError("Strict exchange roster run ended without first-write policy seal")
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
