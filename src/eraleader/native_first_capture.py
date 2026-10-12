"""5_3/5_5: opt-in first-native-WATCH Top-K freeze AND census registration.

This orchestrates existing trustworthy *local* validators, without replaying
old scores as an ex-ante prediction, importing later outcomes, or generating
random score/label data. Local OS first-write, issuer/PIT and time are NOT
externally attested. A cross-file partial write is an incident, not a signal.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import fcntl
import json
import os
import re
import sqlite3

from .native_topk_freeze import freeze_native_topk, _readonly_cohort
from .native_census_gate import (
    SCHEMA as NATIVE_SCHEMA, register_native_census, audit_native_census,
)
from .prospective_census import _read
from .ranked_discovery import _frozen, _now, _time, _label_protocol
from .prospective_census_seal import _index_path, _inventory

PLAN_SCHEMA="eraleader.native_first_capture_plan.v1"
CAPTURE_SCHEMA="eraleader.native_first_capture_verified.v1"
CAPTURE_NAME="capture_receipt.json"
FROZEN_NAME="first_ranked_native_topk.json"
RULE_NAME="predeclared_leader_rule.json"
SPEC_NAME="census_input.json"
SOURCE_NAME="native_source_proofs.json"
OUTCOME_NAME="future_outcomes.json"
RECEIPT_NAME="future_source_receipts.json"
PLAN_KEYS={
    "schema_version","cohort_id","market","model_version",
    "score_ledger","watch_ledger","features_dir",
    "label_definition_file","label_definition_sha256",
    "label_definition_id","horizon_days","top_k","max_age_hours",
}
NAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,58}\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
MAX_WATCH=1000


def _sha(file:Path) -> str:
    return sha256(file.read_bytes()).hexdigest()


def _create(path:Path,payload:bytes):
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Linked native first-capture evidence forbidden")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())


def _canonical(obj:object)->bytes:
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,
                       indent=2,allow_nan=False)+"\n").encode("utf-8")


def _safe_source(value:object,kind:str)->Path:
    if type(value) is not str or not 0<len(value)<4096:
        raise ValueError("Missing native first-capture "+kind+" source path")
    file=Path(value)
    if (not file.is_absolute() or ".." in file.parts or
            file.is_symlink() or file.parent.is_symlink()):
        raise ValueError("Unsafe/linked native first-capture "+kind+" source")
    if kind=="features_dir":
        if not file.is_dir():
            raise ValueError("Missing native first-capture feature directory")
    elif kind!="score_ledger" and kind!="watch_ledger":
        if not file.is_file():
            raise ValueError("Missing predeclared label rule file")
    elif file.exists() and not file.is_file():
        raise ValueError("Untrusted native first-capture ledger")
    return file


def read_capture_plan(path:Path)->tuple[dict,str,dict[str,Path]]:
    """Exact-predeclared source/rule inputs; never create a plan during capture."""
    doc=_read(path)
    if (type(doc) is not dict or set(doc)!=PLAN_KEYS or
            doc["schema_version"]!=PLAN_SCHEMA or
            doc["market"] not in ("KR","US") or
            type(doc["cohort_id"]) is not str or
            not NAME.fullmatch(doc["cohort_id"]) or
            type(doc["model_version"]) is not str or
            not 0<len(doc["model_version"])<=120 or
            any(ord(c)<32 for c in doc["model_version"]) or
            type(doc["label_definition_id"]) is not str or
            not 0<len(doc["label_definition_id"])<=160 or
            type(doc["horizon_days"]) is not int or
            not 1<=doc["horizon_days"]<=1095 or
            type(doc["top_k"]) is not int or not 1<=doc["top_k"]<=MAX_WATCH or
            type(doc["max_age_hours"]) is not int or
            not 1<=doc["max_age_hours"]<=168 or
            type(doc["label_definition_sha256"]) is not str or
            not SHA.fullmatch(doc["label_definition_sha256"])):
        raise ValueError("Incomplete/invalid predeclared first-native cohort plan")
    paths={kind:_safe_source(doc[kind],kind) for kind in (
        "score_ledger","watch_ledger","features_dir","label_definition_file")}
    pinned=_label_protocol(
        paths["label_definition_file"],label_id=doc["label_definition_id"],
        market=doc["market"],horizon=doc["horizon_days"])
    if pinned!=doc["label_definition_sha256"]:
        raise ValueError("Changed predeclared leader rule before capture")
    return doc,_sha(Path(path)),paths


def _counts(watch:Path,score:Path,market:str,model:str)->tuple[int,int]|None:
    if not watch.exists():
        if score.exists():
            raise ValueError("Native score ledger exists without original WATCH registry")
        return None
    with closing(sqlite3.connect(watch.as_uri()+"?mode=ro",uri=True)) as conn:
        try:
            count=conn.execute(
                "SELECT count(*) FROM prospective_signals WHERE market=? AND model_version=?",
                (market,model)).fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise ValueError("Missing/corrupt positive native WATCH source") from exc
    if count>MAX_WATCH:
        raise ValueError("Oversized first-native positive WATCH set")
    if not score.exists():
        return count,0
    with closing(sqlite3.connect(score.as_uri()+"?mode=ro",uri=True)) as conn:
        try:
            scored=conn.execute(
                "SELECT count(*) FROM rank_score_events WHERE market=? AND model_version=?",
                (market,model)).fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise ValueError("Missing/corrupt native first-score receipts") from exc
    if scored>MAX_WATCH or scored>count:
        raise ValueError("Native numeric score rows exceed the complete positive WATCH cohort")
    return count,scored


def _pending(condition:str,count:int=0,scored:int=0) ->dict:
    return {
        "status":"WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE",
        "waiting_reason":condition,
        "positive_watch_count_observed":count,
        "native_score_count_observed":scored,
        "first_write_registry_created":False,
        "censored_or_unknown_selected":None,
        "real_future_leader_accuracy_certified":False,
        "publisher_independently_authenticated":False,
        "official_leader_promotions":0,"external_api_calls":0,
        "messages_sent":0,
    }


def _inspect_complete(cohort:Path,plan:dict,plan_sha:str,
                      sources:dict[str,Path],now:datetime) ->dict:
    receipt=_read(cohort/CAPTURE_NAME)
    required={
        "schema_version","plan_sha256","market","model_version",
        "frozen_file_sha256","label_file_sha256","native_source_proofs_sha256",
        "census_manifest_sha256","census_index_head_sha256",
        "census_index_bytes_sha256",
        "original_positive_watch_count","original_selected_top_k",
        "captured_at_utc","original_outcome_unknown",
        "first_write_pit_independently_verified","real_future_leader_accuracy_certified",
        "official_leader_promotions",
    }
    if (type(receipt) is not dict or set(receipt)!=required or
            receipt["schema_version"]!=CAPTURE_SCHEMA or
            receipt["plan_sha256"]!=plan_sha or
            receipt["market"]!=plan["market"] or
            receipt["model_version"]!=plan["model_version"] or
            receipt["label_file_sha256"]!=plan["label_definition_sha256"] or
            receipt["original_selected_top_k"]!=plan["top_k"] or
            receipt["original_outcome_unknown"]!=plan["top_k"] or
            receipt["first_write_pit_independently_verified"] is not False or
            receipt["real_future_leader_accuracy_certified"] is not False or
            receipt["official_leader_promotions"]!=0):
        raise ValueError("Missing/forged original first-native capture receipt")
    when=_time(receipt["captured_at_utc"])
    if when>now:
        raise ValueError("First-native capture claims future registration")
    evidence=cohort/"evidence"
    rule=evidence/RULE_NAME
    frozen=evidence/FROZEN_NAME
    source=evidence/SOURCE_NAME
    spec=evidence/SPEC_NAME
    reg=cohort/"registered"
    name="census_"+plan["cohort_id"]+".json"
    for path in (rule,frozen,source,spec,reg/name):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Lost/unsafe original native cohort proof")
    if (_sha(rule)!=receipt["label_file_sha256"] or
            _sha(frozen)!=receipt["frozen_file_sha256"] or
            _sha(source)!=receipt["native_source_proofs_sha256"] or
            _sha(reg/name)!=receipt["census_manifest_sha256"] or
            _sha(_index_path(reg))!=receipt["census_index_bytes_sha256"]):
        # SQLite quick_check/receipt-chain verification alone cannot detect
        # ignored trailing bytes or self-consistent mutation of the DB file.
        # This independent-path digest binds exact first-registered index bytes.
        raise ValueError("Revised original prospective native cohort bytes")
    src=_read(source)
    if (type(src) is not dict or src.get("schema_version")!=NATIVE_SCHEMA or
            type(src.get("cohorts")) is not list or len(src["cohorts"])!=1 or
            src["cohorts"][0]!={
                "frozen_sha256":receipt["frozen_file_sha256"],
                "score_ledger":str(sources["score_ledger"]),
                "watch_ledger":str(sources["watch_ledger"]),
                "features_dir":str(sources["features_dir"]),
            }):
        raise ValueError("Local original first-WATCH score proof paths replaced")
    freeze=_frozen(frozen)
    if (_time(freeze["frozen_at_utc"])!=when or
            _time(freeze["snapshot_at_utc"])!=when):
        raise ValueError("First native capture clock differs from the actual frozen snapshot")
    if (freeze["market"]!=plan["market"] or
            freeze["model_version"]!=plan["model_version"] or
            freeze["label_definition_sha256"]!=plan["label_definition_sha256"] or
            freeze["requested_k"]!=plan["top_k"] or
            freeze["horizon_days"]!=plan["horizon_days"] or
            freeze["retrospective_freeze"] is not False or
            len(freeze["ranked_candidates"])!=receipt["original_positive_watch_count"]):
        raise ValueError("Captured original positive WATCH ranked denominator revised")
    specs=_read(spec)
    if specs!=[{
        "frozen":FROZEN_NAME,"definition":RULE_NAME,
        "outcomes":OUTCOME_NAME,"receipts":RECEIPT_NAME,
    }]:
        raise ValueError("Native first-capture future label filenames revised")
    registry=audit_native_census(reg,native_config=source,
                                 evaluated_at=now.isoformat(),clock=now)
    if (registry["registry_manifest_count"]!=1 or
            registry["registered_cohort_count"]!=1 or
            registry["first_write_receipts_verified"] is not True or
            registry["local_native_score_provenance_complete"] is not True or
            registry["receipt_index_head_sha256"]!=receipt["census_index_head_sha256"] or
            registry["frozen_selected_denominator"]!=plan["top_k"]):
        raise ValueError("Registered native first-write census receipt/index revised")
    if _sha(sources["label_definition_file"])!=plan["label_definition_sha256"]:
        raise ValueError("Predeclared external label rule revised after capture")
    return {
        "status":"ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY",
        "market":plan["market"],"cohort_id":plan["cohort_id"],
        "model_version":plan["model_version"],
        "original_complete_positive_watch":receipt["original_positive_watch_count"],
        "first_frozen_top_k":plan["top_k"],
        "frozen_rank_sha256":receipt["frozen_file_sha256"],
        "original_first_write_index_head_sha256":receipt["census_index_head_sha256"],
        "native_watch_score_provenance_rechecked":True,
        "original_label_rule_sha256_pinned":True,
        "unknown_or_censored_now":registry["unknown_or_censored"],
        "locally_documented_hits_not_official":registry["locally_documented_early_hits"],
        "independent_market_pit_certified":False,
        "real_future_leader_accuracy_certified":False,
        "official_leader_promotions":0,"messages_sent":0,"external_api_calls":0,
    }


def capture_first_native_topk(plan_file:Path,capture_root:Path,*,
                              clock:datetime|None=None) ->dict:
    """Create one complete, predeclared, then-current model cohort once.

    A partial crash is NEVER automatically healed or backdated. Outcomes are
    not created/read until a later separate source receipt audit.
    """
    now=_now(clock)
    plan,plan_sha,sources=read_capture_plan(Path(plan_file))
    capture_root=Path(capture_root).absolute()
    if (capture_root.is_symlink() or capture_root.parent.is_symlink() or
            (capture_root.exists() and not capture_root.is_dir())):
        raise ValueError("Unsafe native first-capture output root")
    # The permanent storage identity is MARKET + PINNED MODEL, never the
    # user-supplied cohort label. Otherwise identical WATCH first-scores
    # could be re-frozen with a different name/K after seeing a result.
    slot=plan["market"].lower()+"_"+sha256(plan["model_version"].encode()).hexdigest()[:24]
    cohort=capture_root/("native_"+slot)
    lock_path=capture_root/(".capture_"+slot+".lock")
    if cohort.is_symlink() or lock_path.is_symlink():
        raise ValueError("Unsafe first-native capture path or lock")
    if cohort.exists() and not lock_path.exists():
        raise ValueError("Missing original native capture first-write lock; refusing reset")
    if lock_path.exists() and not cohort.exists():
        # A different process may be between taking the lock and making
        # its first O_EXCL evidence; an unlocked surviving sentinel is
        # instead evidence of a failed/deleted first-write attempt.
        fd=os.open(lock_path,os.O_RDWR|getattr(os,"O_NOFOLLOW",0))
        with os.fdopen(fd,"r+b") as guard:
            try:
                fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                return {"status":"SKIPPED_CONCURRENT_NATIVE_CAPTURE",
                        "messages_sent":0,"external_api_calls":0,
                        "official_leader_promotions":0}
        raise ValueError("Original prospective capture missing after first-write attempt")
    # An already completed cohort takes precedence over score-readiness; its
    # historical original MUST be audited, not silently recreated from a new
    # model/freshly modified score source.
    if not cohort.exists():
        ready=_counts(sources["watch_ledger"],sources["score_ledger"],
                      plan["market"],plan["model_version"])
        if ready is None or ready[0]==0:
            return _pending("WAITING_FOR_POSITIVE_FIRST_WATCH")
        if ready[1]<ready[0]:
            return _pending("WAITING_FOR_ALL_NATIVE_SCORES",*ready)
        # Fail closed on matching row counts but different identities /
        # fabricated numeric score/feature provenance, BEFORE first write.
        records,_=_readonly_cohort(
            sources["score_ledger"],sources["watch_ledger"],
            market=plan["market"],model_version=plan["model_version"],
            as_of=now,max_age_hours=plan["max_age_hours"])
        if plan["top_k"]>len(records):
            raise ValueError("Predeclared Top-K exceeds available positive WATCH cohort")
        # Entire native formula, first-WATCH and original-score preflight
        # must finish before creating ANY permanent capture output. The
        # generated freeze is stamped now, and its bytes move O_EXCL later.
        with TemporaryDirectory(prefix="eraleader-native-first-preflight-") as tmp:
            trial=Path(tmp)/FROZEN_NAME
            first=freeze_native_topk(
                sources["score_ledger"],sources["watch_ledger"],sources["features_dir"],
                sources["label_definition_file"],trial,
                market=plan["market"],model_version=plan["model_version"],
                label_definition_id=plan["label_definition_id"],
                horizon_days=plan["horizon_days"],k=plan["top_k"],
                max_age_hours=plan["max_age_hours"],clock=now)
            frozen_bytes=trial.read_bytes()
    capture_root.mkdir(parents=True,exist_ok=True)
    if lock_path.exists() and not cohort.exists():
        raise ValueError("Original prospective capture is missing after first-write attempt")
    fd=os.open(lock_path,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"r+b") as guard:
        try:
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status":"SKIPPED_CONCURRENT_NATIVE_CAPTURE","messages_sent":0,
                    "external_api_calls":0,"official_leader_promotions":0}
        if cohort.exists():
            if not (cohort/CAPTURE_NAME).exists():
                raise ValueError("Partial prospective native capture; never backfill or reset")
            return _inspect_complete(cohort,plan,plan_sha,sources,now)
        # New first-write root is created only once all WATCH/score evidence
        # existed BEFORE the freeze attempt; all subsequent steps are O_EXCL.
        cohort.mkdir(mode=0o700)
        evidence=cohort/"evidence"
        evidence.mkdir(mode=0o700)
        rule=sources["label_definition_file"]
        raw=rule.read_bytes()
        if sha256(raw).hexdigest()!=plan["label_definition_sha256"]:
            raise ValueError("Predeclared leader criterion revised before freeze")
        _create(evidence/RULE_NAME,raw)
        frozen=evidence/FROZEN_NAME
        _create(frozen,frozen_bytes)
        spec=[{"frozen":FROZEN_NAME,"definition":RULE_NAME,
               "outcomes":OUTCOME_NAME,"receipts":RECEIPT_NAME}]
        _create(evidence/SPEC_NAME,_canonical(spec))
        frozen_sha=_sha(frozen)
        native={"schema_version":NATIVE_SCHEMA,"cohorts":[{
            "frozen_sha256":frozen_sha,
            "score_ledger":str(sources["score_ledger"]),
            "watch_ledger":str(sources["watch_ledger"]),
            "features_dir":str(sources["features_dir"]),
        }]}
        _create(evidence/SOURCE_NAME,_canonical(native))
        census_name="census_"+plan["cohort_id"]+".json"
        registered=register_native_census(
            evidence/SPEC_NAME,cohort/"registered",census_name,
            native_config=evidence/SOURCE_NAME,clock=now)
        audit=audit_native_census(
            cohort/"registered",native_config=evidence/SOURCE_NAME,
            evaluated_at=now.isoformat(),clock=now)
        if (registered["selected_denominator"]!=plan["top_k"] or
                audit["frozen_selected_denominator"]!=plan["top_k"] or
                audit["unknown_or_censored"]!=plan["top_k"] or
                registered["receipt_index_entries"]!=1 or
                registered["fully_native_bound_cohorts"]!=1):
            raise ValueError("First-written prospective native cohort not completely registered")
        if _sha(Path(plan_file))!=plan_sha or _sha(rule)!=plan["label_definition_sha256"]:
            raise ValueError("Predeclared capture plan or original rule changed during first-write")
        receipt={
            "schema_version":CAPTURE_SCHEMA,
            "plan_sha256":plan_sha,
            "market":plan["market"],"model_version":plan["model_version"],
            "frozen_file_sha256":frozen_sha,
            "label_file_sha256":plan["label_definition_sha256"],
            "native_source_proofs_sha256":_sha(evidence/SOURCE_NAME),
            "census_manifest_sha256":_sha(cohort/"registered"/census_name),
            "census_index_head_sha256":audit["receipt_index_head_sha256"],
            "census_index_bytes_sha256":_sha(_index_path(cohort/"registered")),
            "original_positive_watch_count":first["positive_watch_count"],
            "original_selected_top_k":plan["top_k"],
            "captured_at_utc":now.isoformat(),
            "original_outcome_unknown":plan["top_k"],
            "first_write_pit_independently_verified":False,
            "real_future_leader_accuracy_certified":False,
            "official_leader_promotions":0,
        }
        _create(cohort/CAPTURE_NAME,_canonical(receipt))
        result=_inspect_complete(cohort,plan,plan_sha,sources,now)
        return {**result,"status":"FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED"}
