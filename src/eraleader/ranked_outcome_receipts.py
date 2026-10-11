"""5_5: predeclared top-K outcome rule + local normalized document receipts.

The optional source receipts do NOT authenticate publishers or make a real
leader prediction. Both missing and conflicting source documents censor the
top-K numerator; historical late-sealed ranks never earn prospective credit.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from statistics import median
import json

from .ranked_discovery import (
    _frozen,_time,_now,_label_protocol,evaluate_ranked_precision_at_k,
)
from .outcome_source_claims import (
    SOURCE_LABEL_SCHEMA,BASENAME,SHA,MAX_FILE_BYTES,_document_binding_issue,
)

SCHEMA="eraleader.ranked_outcome_receipts.v1"
STATUS_RESEARCH="LOCAL_PREDECLARED_TOPK_SOURCE_DOCUMENT_AUDIT_NOT_CERTIFIED"
STATUS_RETROSPECTIVE="CENSORED_RETROSPECTIVE_RANK_SEAL_NOT_PREDICTION"
FIELDS={"schema_version","market","model_version","label_definition_id",
        "ranked_snapshot_sha256","outcomes_sha256","claims"}
CLAIM_FIELDS={"security_id","publisher_id_claimed","source_id",
              "file","sha256","published_at","retrieved_at"}
DOC_FIELDS={"schema_version","security_id","label_definition_id",
            "is_future_leader","mature_at","outcome_available_at"}
MAX_RANK_LABEL_BYTES=1_000_000
MAX_CLAIMS=1000


def _no_duplicate_keys(pairs:list[tuple[str,object]]) -> dict:
    found={}
    for key,value in pairs:
        if key in found:
            raise ValueError("Duplicate ranked outcome evidence JSON key")
        found[key]=value
    return found


def _read_bytes(path:Path,*,size:int=MAX_FILE_BYTES) -> bytes:
    p=Path(path)
    if (p.is_symlink() or p.parent.is_symlink() or not p.is_file()
            or not 0<p.stat().st_size<=size):
        raise ValueError("Missing, linked, blank or oversized ranked outcome evidence file")
    return p.read_bytes()


def _parse(raw:bytes,*,desc:str):
    try:
        value=json.loads(raw,object_pairs_hook=_no_duplicate_keys,
                         parse_constant=lambda _:(_ for _ in ()).throw(
                             ValueError("Nonfinite source JSON number")))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Invalid or duplicate "+desc+" JSON") from exc
    return value


def _claim_text(claim:dict,key:str) -> str:
    text=claim.get(key)
    if type(text) is not str or not text.strip() or len(text)>160:
        raise ValueError("Invalid ranked receipt "+key)
    return text


def audit_ranked_outcome_receipts(
    frozen_file:Path,outcome_file:Path,receipt_manifest:Path, *,
    evaluated_at:str,label_definition_file:Path|None=None,
    clock:datetime|None=None,sample_limit:int=100,
) -> dict:
    """Apply the original frozen denominator and exact local source receipt checks."""
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Invalid source audit sample_limit")
    when=_time(evaluated_at)
    now=_now(clock)
    if when>now:
        raise ValueError("Future ranked source audit evaluated_at is forbidden")
    freeze=_frozen(Path(frozen_file))
    definition=freeze.get("label_definition_id")
    if (not isinstance(definition,str) or not definition.strip()
            or freeze.get("outcome_definition_pinned_before_labels") is not True):
        raise ValueError("Strict source audit requires predeclared pinned label definition")
    original_rule_digest=freeze.get("label_definition_sha256")
    if (label_definition_file is None or
            freeze.get("label_rule_bytes_pinned") is not True or
            not isinstance(original_rule_digest,str)):
        raise ValueError("Strict source audit requires predeclared pinned label rule file SHA")
    rule_digest=_label_protocol(Path(label_definition_file),
                                label_id=definition,market=freeze["market"],
                                horizon=freeze["horizon_days"])
    if rule_digest!=original_rule_digest:
        raise ValueError("Predeclared label rule content SHA mismatch")
    if freeze["frozen_at_utc"]>now.isoformat():
        raise ValueError("Sealed ranked cohort timestamp is in the future")
    # Original ranked evaluator owns horizon boundary, market-local DST,
    # positive lead / late-hits, negative maturity, and censored label rules.
    base=evaluate_ranked_precision_at_k(
        frozen_file,outcome_file,evaluated_at=evaluated_at,clock=now)
    if base["label_definition_predeclared"] is not True:
        raise ValueError("Evaluator lost frozen predeclared label definition")

    original_labels=_read_bytes(Path(outcome_file),size=MAX_RANK_LABEL_BYTES)
    labels=_parse(original_labels,desc="outcome labels")
    if not isinstance(labels,list):
        raise ValueError("Ranked outcomes must be an array")
    label_map={}
    for label in labels:
        if not isinstance(label,dict):
            raise ValueError("Ranked outcome label must be an object")
        sid=label.get("security_id")
        if not isinstance(sid,str) or not sid or sid in label_map:
            raise ValueError("Duplicate ranked outcome label security_id")
        label_map[sid]=label
    ranked_ids={row["security_id"] for row in freeze["ranked_candidates"]}
    if set(label_map)-ranked_ids:
        raise ValueError("Outcome labels contain an unknown frozen security ID")

    raw_manifest=_read_bytes(Path(receipt_manifest),size=MAX_RANK_LABEL_BYTES)
    manifest=_parse(raw_manifest,desc="ranked source manifest")
    if not isinstance(manifest,dict) or set(manifest)!=FIELDS:
        raise ValueError("Invalid ranked source receipt schema fields")
    if manifest.get("schema_version")!=SCHEMA:
        raise ValueError("Invalid ranked source receipt schema")
    if (manifest.get("market")!=freeze["market"] or
        manifest.get("model_version")!=freeze["model_version"] or
        manifest.get("label_definition_id")!=definition):
        raise ValueError("Ranked source manifest label_definition/market/model protocol mismatch")
    if manifest.get("ranked_snapshot_sha256")!=freeze["content_sha256"]:
        raise ValueError("Ranked source manifest references different frozen SHA")
    if manifest.get("outcomes_sha256")!=sha256(original_labels).hexdigest():
        raise ValueError("Ranked source manifest outcome bytes SHA mismatch")
    claims=manifest.get("claims")
    if not isinstance(claims,list) or len(claims)>MAX_CLAIMS:
        raise ValueError("Invalid ranked source claim list length")
    by_id={}
    for claim in claims:
        if not isinstance(claim,dict) or set(claim)!=CLAIM_FIELDS:
            raise ValueError("Invalid ranked source receipt claim fields")
        sid=_claim_text(claim,"security_id")
        if sid in by_id:
            raise ValueError("Duplicate ranked outcome source receipt identity")
        if sid not in ranked_ids:
            raise ValueError("Ranked receipt references unknown frozen security")
        by_id[sid]=claim

    retrospective=bool(
        freeze.get("retrospective_freeze") or
        base["evaluation_as_of_precedes_actual_seal"]
    )
    cutoff=when
    source_folder=Path(receipt_manifest).resolve().parent
    problems=Counter()
    samples=[]
    verified_hit=verified_failure=0
    lead_values=[]
    for ranking in base["ranked_results"]:
        sec=ranking["security_id"]
        source_state=ranking["status"]
        issues=[]
        if retrospective:
            issues=["RETROSPECTIVE_RANK_SEAL_NOT_PROSPECTIVE"]
        elif source_state=="censored":
            issues=["OUTCOME_NOT_MATURE_OR_AVAILABLE"]
        else:
            claimed=by_id.get(sec)
            label=label_map.get(sec)
            if claimed is None:
                issues=["MISSING_LOCAL_SOURCE_RECEIPT"]
            elif label is None:
                issues=["OUTCOME_NOT_MATURE_OR_AVAILABLE"]
            else:
                filename=_claim_text(claimed,"file")
                if not BASENAME.fullmatch(filename) or filename.startswith("."):
                    raise ValueError("Unsafe ranked source file basename/path")
                for name in ("publisher_id_claimed","source_id"):
                    _claim_text(claimed,name)
                expected=_claim_text(claimed,"sha256")
                if not SHA.fullmatch(expected):
                    raise ValueError("Invalid ranked source claimed SHA256")
                mature=_time(label["mature_at"])
                available=_time(label["outcome_available_at"])
                published=_time(claimed["published_at"])
                retrieved=_time(claimed["retrieved_at"])
                if published<mature:
                    issues.append("SOURCE_PUBLISHED_BEFORE_MATURITY")
                if published>available:
                    issues.append("SOURCE_PUBLISHED_AFTER_LABEL_AVAILABILITY")
                if retrieved<available:
                    issues.append("SOURCE_RETRIEVED_BEFORE_AVAILABILITY")
                if retrieved>cutoff:
                    issues.append("SOURCE_RETRIEVED_AFTER_EVALUATION")
                document=source_folder/filename
                if (document.is_symlink() or not document.is_file() or
                        document.resolve().parent!=source_folder or
                        not 0<document.stat().st_size<=MAX_FILE_BYTES):
                    issues.append("MISSING_OR_UNSAFE_LOCAL_SOURCE_FILE")
                else:
                    raw=document.read_bytes()
                    if sha256(raw).hexdigest()!=expected:
                        issues.append("SOURCE_BYTES_SHA256_MISMATCH")
                    else:
                        try:
                            obj=_parse(raw,desc="ranked source label document")
                        except ValueError:
                            issues.append("SOURCE_DOCUMENT_LABEL_BINDING_REQUIRED")
                        else:
                            required=set(DOC_FIELDS)
                            if label.get("is_future_leader") is True:
                                required.add("leader_start_at")
                            if (not isinstance(obj,dict) or set(obj)!=required or
                                    obj.get("schema_version")!=SOURCE_LABEL_SCHEMA):
                                issues.append("SOURCE_DOCUMENT_LABEL_BINDING_REQUIRED")
                            else:
                                error=_document_binding_issue(raw,label)
                                if error:
                                    issues.append(error)
        if not issues:
            if source_state=="early_hit":
                verified_hit+=1
                lead_values.append(ranking["early_lead_days"])
            elif source_state=="known_failure":
                verified_failure+=1
            else:
                raise ValueError("Unexpected ranked source evaluator outcome")
        for problem in set(issues):
            problems[problem]+=1
        if len(samples)<sample_limit:
            samples.append({
                "rank":ranking["rank"],"security_id":sec,
                "original_research_label_status":source_state,
                "local_source_corroborated":not issues,
                "local_source_corroboration_status":(
                    source_state if not issues else "censored"),
                "issues":sorted(set(issues)),
            })

    n=base["selected_count"]
    known=verified_hit+verified_failure
    unknown=n-known
    if verified_hit+verified_failure+unknown!=n:
        raise ValueError("Ranked source counts violate frozen K")
    # Preserve the FULL distribution of locally documented early lead-days.
    # A per-cohort median cannot be averaged to get the global median; no
    # security IDs or unverifiable/late lead values enter this histogram.
    lead_day_histogram={str(day):count for day,count in
                        sorted(Counter(lead_values).items())}
    if (sum(lead_day_histogram.values())!=verified_hit or
            any(type(day) is not int or not 0<day<=freeze["horizon_days"]
                for day in lead_values)):
        raise ValueError("Invalid locally documented early lead-day evidence")
    result={
        "status":STATUS_RETROSPECTIVE if retrospective else STATUS_RESEARCH,
        "market":freeze["market"],"model_version":freeze["model_version"],
        "label_definition_id":definition,
        "label_definition_sha256":original_rule_digest,
        "label_rule_bytes_verified_against_frozen_sha":True,
        "ranked_snapshot_sha256":freeze["content_sha256"],
        "outcomes_sha256":sha256(original_labels).hexdigest(),
        "source_receipt_manifest_sha256":sha256(raw_manifest).hexdigest(),
        "predeclared_horizon_days":freeze["horizon_days"],
        "frozen_at_utc":freeze["frozen_at_utc"],
        "evaluated_at_utc":cutoff.isoformat(),
        "retrospective_freeze":retrospective,
        "ranked_snapshot_original_research":{
            "early_hits":base["early_hits"],
            "known_failures":base["known_failures"],
            "censored":base["censored"],
            "precision_on_known_unverified":base["precision_at_k_on_known"],
        },
        "top_k_selected_count":n,
        "source_document_matched_early_hits":verified_hit,
        "source_document_matched_known_failures":verified_failure,
        "locally_documented_known_count":known,
        "unknown_or_source_censored_count":unknown,
        "precision_on_locally_documented_known":(
            round(verified_hit/known,6) if known else None),
        "locally_documented_precision_full_k_floor":(
            None if retrospective else round(verified_hit/n,6)),
        "locally_documented_precision_full_k_ceiling":(
            None if retrospective else round((verified_hit+unknown)/n,6)),
        "median_locally_documented_lead_days":(
            median(lead_values) if lead_values else None),
        "documented_early_lead_day_histogram":lead_day_histogram,
        "locally_documented_false_discovery_rate_on_known":(
            round(verified_failure/known,6) if known else None),
        "blocker_counts":dict(sorted(problems.items())),
        "blocker_count":sum(problems.values()),
        "top_k_evidence_sample":samples,
        "sample_truncated":n>sample_limit,
        "recall_at_k":None,
        "real_future_leader_precision":None,
        "actual_future_leader_accuracy_certified":False,
        "independently_authenticated_publisher":False,
        "original_source_retrieval_clock_independently_attested":False,
        "market_pit_source_universe_completeness_certified":False,
        "official_leader_promotions":0,
        "external_api_calls":0,
        "warning":(
            "Local source document hash+claimed timing and leader outcome "
            "agreement do NOT authenticate publisher, document origin or "
            "true contemporaneous historical availability. The local bounded "
            "research precision is not actual market leader prediction skill."
        ),
    }
    return result
