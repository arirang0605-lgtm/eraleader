"""Local byte-and-clock audit for separately claimed holdout outcome sources.

Checks that cited document *bytes* exist and are chronologically consistent
with a sealed research cohort's outcome labels. Supplier identity, acquisition
timestamps, legal issuer/actions coverage and leader outcomes are NEVER
independently authenticated by a self-declared local manifest.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import json
import re

from .frozen_holdout import _read_frozen, _stamp
from .holdout_outcome_reconcile import reconcile_holdout_outcomes

SCHEMA = "eraleader.outcome_evidence_claims.v1"
STATUS = "LOCAL_OUTCOME_EVIDENCE_CLAIMS_AUDITED_NOT_CERTIFIED"
SHA = re.compile(r"[0-9a-f]{64}\Z")
BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.json\Z")
MAX_FILE_BYTES = 5_000_000
SOURCE_LABEL_SCHEMA = "eraleader.outcome_label_evidence.v1"


def _document_binding_issue(raw: bytes, label: dict) -> str | None:
    """Check an opt-in normalized evidence record against exact supplied label.

    A matching document is still self-declared local data, never an
    independent source signature or a true future-leader certification.
    """
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return "SOURCE_DOCUMENT_LABEL_BINDING_REQUIRED"
    if not isinstance(doc, dict) or doc.get("schema_version") != SOURCE_LABEL_SCHEMA:
        return "SOURCE_DOCUMENT_LABEL_BINDING_REQUIRED"
    if (type(doc.get("is_future_leader")) is not bool or
            any(doc.get(k) != label.get(k) for k in
                ("security_id", "label_definition_id", "is_future_leader"))):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    try:
        for key in ("mature_at", "outcome_available_at"):
            if _stamp(doc.get(key)) != _stamp(label.get(key)):
                return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
        if label["is_future_leader"]:
            if _stamp(doc.get("leader_start_at")) != _stamp(label.get("leader_start_at")):
                return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
        elif "leader_start_at" in doc:
            return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    except (ValueError, TypeError):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    return None



def _safe_file(path: Path, *, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked outcome evidence file")
    if path.stat().st_size > limit:
        raise ValueError("Oversized outcome evidence file")
    return path.read_bytes()


def _valid_text(spec: dict, key: str) -> str:
    val=spec.get(key)
    if not isinstance(val,str) or not val.strip() or len(val)>160:
        raise ValueError(f"Missing/invalid evidence field: {key}")
    return val


def audit_outcome_source_claims(
    frozen_file: Path, outcome_file: Path, receipt_manifest: Path, *,
    evaluated_at: str, clock: datetime | None = None,
    sample_limit: int = 100,
    require_document_label_binding: bool = False,
) -> dict:
    if type(require_document_label_binding) is not bool:
        raise ValueError("Invalid strict source-binding flag")
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Invalid evidence audit sample_limit")
    now = clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Evidence audit clock requires timezone")
    cutoff=_stamp(evaluated_at)
    if cutoff>now.astimezone(timezone.utc):
        raise ValueError("Future evidence audit cutoff forbidden")
    freeze=Path(frozen_file)
    if freeze.is_symlink() or not freeze.is_file():
        raise ValueError("Missing or symlinked frozen holdout")
    sealed=_read_frozen(freeze)

    outcomes=Path(outcome_file)
    outcome_bytes=_safe_file(outcomes,limit=MAX_FILE_BYTES)
    label_rows=json.loads(outcome_bytes)
    if not isinstance(label_rows,list):
        raise ValueError("Outcome labels must be an array")
    known={}
    for item in label_rows:
        if not isinstance(item,dict):
            raise ValueError("Outcome label must be an object")
        sec=item.get("security_id")
        if not isinstance(sec,str) or not sec or sec in known:
            raise ValueError("Duplicate or missing outcome identity")
        known[sec]=item

    # Use existing strong frozen horizon and availability rules. A source
    # receipt cannot turn immature/premature-negative labels into winners.
    reconciliation=reconcile_holdout_outcomes(
        freeze,evaluated_at=evaluated_at,outcome_file=outcomes,
        clock=now,sample_limit=1000)
    reconciled_status={row["security_id"]:row["status"]
                       for row in reconciliation["candidate_evidence_sample"]}

    receipt_path=Path(receipt_manifest)
    raw=_safe_file(receipt_path,limit=MAX_FILE_BYTES)
    receipts=json.loads(raw)
    if not isinstance(receipts,dict) or receipts.get("schema_version")!=SCHEMA:
        raise ValueError("Invalid local outcome evidence receipt schema")
    if (receipts.get("market")!=sealed["market"] or
        receipts.get("label_definition_id")!=sealed["label_definition_id"] or
        receipts.get("frozen_manifest_sha256")!=sealed["content_sha256"] or
        receipts.get("outcomes_sha256")!=sha256(outcome_bytes).hexdigest()):
        raise ValueError("Outcome receipt points to a different frozen protocol/label bytes")
    claims=receipts.get("claims")
    if not isinstance(claims,list) or not 1<=len(claims)<=1000:
        raise ValueError("Outcome claims require 1..1000 document receipts")
    folder=receipt_path.resolve().parent
    if receipt_path.parent.is_symlink():
        raise ValueError("Unsafe receipt directory")

    by_sec={}
    for entry in claims:
        if not isinstance(entry,dict):
            raise ValueError("Source evidence claim must be an object")
        sec=_valid_text(entry,"security_id")
        if sec in by_sec:
            raise ValueError("Duplicate source claim for one security")
        if sec not in known:
            raise ValueError("Source claim references an unknown outcome identity")
        by_sec[sec]=entry

    eligible_status="RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED"
    frozen_ids={r["security_id"] for r in sealed["signals"]}
    from .frozen_holdout import TIMEZONES
    zone=TIMEZONES[sealed["market"]]
    horizon=sealed["horizon_days"]
    blockers=[]
    details=[]
    passed=0
    bound_count=0
    for sec in sorted(frozen_ids):
        record=next(r for r in sealed["signals"] if r["security_id"]==sec)
        label=known.get(sec)
        if label is None:
            status="NO_OUTCOME_LABEL"
        else:
            matured=_stamp(label["mature_at"])
            available=_stamp(label["outcome_available_at"])
            # An independent receipt must never upgrade a negative outcome
            # before the complete frozen exchange-local calendar-day horizon.
            # Preserve the registration's clock time across New York DST.
            end=(_stamp(record["recorded_at_utc"]).astimezone(zone)
                 +timedelta(days=horizon)).astimezone(timezone.utc)
            if matured>cutoff or available>cutoff:
                status="LABEL_NOT_YET_AVAILABLE"
            elif label["is_future_leader"] is False and matured<end:
                status="PREMATURE_NEGATIVE_LABEL"
            else:
                status=eligible_status
        authoritative_local_status=reconciled_status.get(sec)
        if authoritative_local_status is not None:
            if label is None:
                matching=authoritative_local_status in {
                    "HORIZON_PENDING_NO_LABEL", "HORIZON_ELAPSED_NO_LABEL"}
            else:
                matching=(authoritative_local_status==status)
            if not matching:
                raise ValueError("Outcome source audit and frozen evaluator disagree")
        if status!=eligible_status:
            # Not-yet-mature labels cannot be made eligible by a receipt.
            details.append({"security_id":sec,"maturity_status":status,
                            "local_source_bytes_checked":False,
                            "source_claim_chronology_ok":False,
                            "issues":["OUTCOME_NOT_YET_EVALUABLE"]})
            continue
        problems=[]
        bound=False
        claim=by_sec.get(sec)
        doc_hash=None
        if claim is None:
            problems.append("MISSING_OUTCOME_SOURCE_RECEIPT")
        else:
            publisher=_valid_text(claim,"publisher_id_claimed")
            source=_valid_text(claim,"source_id")
            if len(publisher)>160 or len(source)>160:
                raise ValueError("Untrusted source metadata")
            filename=_valid_text(claim,"file")
            if not BASENAME.fullmatch(filename) or filename.startswith("."):
                raise ValueError("Unsafe local evidence filename")
            announced=_stamp(claim.get("published_at"))
            retrieved=_stamp(claim.get("retrieved_at"))
            matured=_stamp(known[sec]["mature_at"])
            label_available=_stamp(known[sec]["outcome_available_at"])
            if announced<matured:
                problems.append("SOURCE_PUBLISHED_BEFORE_LABEL_MATURITY")
            if label_available<announced:
                problems.append("LABEL_AVAILABLE_BEFORE_CLAIMED_PUBLICATION")
            if retrieved<announced:
                problems.append("SOURCE_RETRIEVED_BEFORE_PUBLICATION")
            if retrieved>cutoff:
                problems.append("SOURCE_RETRIEVED_AFTER_EVALUATION")
            expected=_valid_text(claim,"sha256")
            if not SHA.fullmatch(expected):
                raise ValueError("Invalid local source SHA256")
            document=folder/filename
            if document.is_symlink() or not document.is_file() or document.resolve().parent != folder:
                problems.append("MISSING_OR_UNSAFE_SOURCE_FILE")
            elif document.stat().st_size==0 or document.stat().st_size>MAX_FILE_BYTES:
                problems.append("EMPTY_OR_OVERSIZED_SOURCE_FILE")
            else:
                document_bytes=document.read_bytes()
                doc_hash=sha256(document_bytes).hexdigest()
                if doc_hash!=expected:
                    problems.append("SOURCE_BYTES_SHA256_MISMATCH")
                elif require_document_label_binding:
                    issue=_document_binding_issue(document_bytes,known[sec])
                    if issue:
                        problems.append(issue)
                    else:
                        bound=True
        if not problems:
            passed+=1
            if bound:
                bound_count+=1
        for reason in problems:
            blockers.append(f"{sec}:{reason}")
        details.append({
            "security_id":sec,"maturity_status":status,
            "local_source_bytes_checked":doc_hash is not None,
            "source_document_label_binding_checked":bound,
            "source_claim_chronology_ok":not problems,
            "issues":sorted(set(problems)),
        })
    # Claims cannot make more results evaluable than the sealed evaluator.
    if passed>reconciliation["internally_evaluable_outcome_count"]:
        raise ValueError("Source claims exceed sealed internally evaluable outcomes")
    # A self-reported file hash is not a signature; even all clean entries
    # remain unauthenticated external outcome claims.
    return {
        "status":STATUS,
        "market":sealed["market"],
        "model_version":sealed["model_version"],
        "label_definition_id":sealed["label_definition_id"],
        "frozen_manifest_sha256":sealed["content_sha256"],
        "outcomes_sha256":sha256(outcome_bytes).hexdigest(),
        "source_claim_manifest_sha256":sha256(raw).hexdigest(),
        "evaluated_at_utc":cutoff.isoformat(),
        "frozen_candidates":len(frozen_ids),
        "internally_evaluable_outcomes":reconciliation["internally_evaluable_outcome_count"],
        "local_source_claims_consistent":passed,
        "local_source_labels_bound":bound_count,
        "require_document_label_binding":require_document_label_binding,
        "eligible_outcomes_missing_or_inconsistent_sources":
            reconciliation["internally_evaluable_outcome_count"]-passed,
        "blocker_count":len(blockers),
        "blockers":sorted(blockers)[:sample_limit],
        "candidate_evidence_sample":details[:sample_limit],
        "declared_receipts_for_unmatched_candidates":len(set(by_sec)-frozen_ids),
        "independently_source_authenticated":False,
        "historical_universe_pit_certified":False,
        "actual_leader_prediction_certified":False,
        "official_leader_promotions":0,
        "warning":("Checking hashes and self-declared dates does not prove independent "
                   "publisher identity, original creation/retrieval clocks, historical "
                   "universe completeness, corporate-action/delist settlement, "
                   "or an actual future era-leader outcome.")
    }
