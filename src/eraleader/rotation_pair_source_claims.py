"""Compare separately claimed future outcome documents to sealed WATCH rotation pairs.

Research only: a digest, claimed publisher and local receipt timestamp DO NOT
authenticate any real data vendor, legal issuer or future leader outcome.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re

from .frozen_holdout import _stamp
from .rotation_holdout import (
    _checked_clock, _read_rotation_freeze, _safe_json,
    audit_rotation_pair_outcomes, LABEL_KEYS,
)

MANIFEST_SCHEMA = "eraleader.rotation_pair_label_receipts.v1"
DOCUMENT_SCHEMA = "eraleader.outcome_label_evidence.v1"
STATUS = "LOCAL_ROTATION_PAIR_SOURCE_CLAIMS_RESEARCH_NOT_CERTIFIED"
MAX_BYTES = 2_000_000
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.json\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
TOP_KEYS = {
    "schema_version", "market", "label_definition_id",
    "rotation_freeze_sha256", "outcomes_sha256", "claims",
}
CLAIM_KEYS = {
    "security_id", "publisher_id_claimed", "source_id", "file",
    "sha256", "published_at", "retrieved_at",
}
AVAILABLE_RESEARCH_STATUSES = {
    "RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED",
    "RESEARCH_PAIR_NOT_CONFIRMED_SOURCE_UNVERIFIED",
}


def _unique(pairs: list[tuple[str,object]]) -> dict:
    item = {}
    for key,value in pairs:
        if key in item:
            raise ValueError("Duplicate source document JSON field")
        item[key] = value
    return item


def _normalize_label_document(raw: bytes, label: dict) -> str | None:
    """Match exact normalized result payload, with aware UTC clock equality.

    Never interpret an arbitrary vendor HTML/PDF/CSV as a verified document.
    """
    try:
        doc = json.loads(raw, object_pairs_hook=_unique)
    except (UnicodeError, ValueError):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    if not isinstance(doc, dict):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    expected = {"schema_version"} | LABEL_KEYS
    if label["is_future_leader"] is True:
        expected.add("leader_start_at")
    if set(doc) != expected or doc.get("schema_version") != DOCUMENT_SCHEMA:
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    if (type(doc.get("is_future_leader")) is not bool or
            any(doc.get(key) != label.get(key) for key in (
                "security_id", "label_definition_id", "is_future_leader"
            ))):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    try:
        clocks = ("mature_at", "outcome_available_at")
        if label["is_future_leader"]:
            clocks += ("leader_start_at",)
        if any(_stamp(doc.get(key)) != _stamp(label.get(key)) for key in clocks):
            return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    except (TypeError, ValueError):
        return "SOURCE_DOCUMENT_LABEL_BINDING_MISMATCH"
    return None


def _text(obj: dict, name: str) -> str:
    value = obj.get(name)
    if not isinstance(value,str) or not value.strip() or len(value)>160:
        raise ValueError("Missing or malformed rotation receipt field: "+name)
    return value


def _read_source_claim(
    folder: Path, claim: dict, label: dict, cutoff: datetime,
) -> list[str]:
    issues = []
    published = _stamp(claim["published_at"])
    retrieved = _stamp(claim["retrieved_at"])
    maturity = _stamp(label["mature_at"])
    label_available = _stamp(label["outcome_available_at"])
    if published < maturity:
        issues.append("SOURCE_PUBLISHED_BEFORE_LABEL_MATURE")
    if published > label_available:
        issues.append("SOURCE_PUBLISHED_AFTER_DECLARED_LABEL_AVAILABILITY")
    if retrieved < published:
        issues.append("SOURCE_RETRIEVED_BEFORE_PUBLICATION")
    if retrieved < label_available:
        issues.append("SOURCE_RETRIEVED_BEFORE_LABEL_AVAILABLE")
    if retrieved > cutoff:
        issues.append("SOURCE_RETRIEVED_AFTER_EVALUATION")

    filename = claim["file"]
    source = folder/filename
    if (source.is_symlink() or not source.is_file() or
            source.resolve().parent != folder):
        issues.append("SOURCE_FILE_MISSING_OR_UNSAFE")
    elif source.stat().st_size == 0 or source.stat().st_size > MAX_BYTES:
        issues.append("SOURCE_FILE_EMPTY_OR_OVERSIZED")
    else:
        raw = source.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != claim["sha256"]:
            issues.append("SOURCE_DOCUMENT_SHA256_MISMATCH")
        else:
            issue = _normalize_label_document(raw, label)
            if issue is not None:
                issues.append(issue)
    return sorted(set(issues))


def audit_rotation_pair_source_claims(
    frozen_file: Path, outcome_file: Path, receipt_manifest: Path, *,
    evaluated_at: str, clock: datetime | None = None,
    sample_limit: int = 100,
) -> dict:
    """Require BOTH normalized, locally timestamped issuer labels per mature pair.

    A locally matching pair only corroborates two *claimed* outcome documents,
    never independently confirms investment-performance or legal leader status.
    """
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Rotation pair source sample_limit must be 1..1000")
    now = _checked_clock(clock)
    cutoff = _stamp(evaluated_at)
    if cutoff > now:
        raise ValueError("Future pair source audit cutoff forbidden")
    sealed = _read_rotation_freeze(Path(frozen_file))
    outcomes, outcomes_sha = _safe_json(Path(outcome_file),required_type=list)
    # Reuse the original as-of maturity/labels parser to prevent receipt
    # claims turning not-yet-known future labels into research confirmations.
    base = audit_rotation_pair_outcomes(
        Path(frozen_file), evaluated_at=evaluated_at,
        outcome_file=Path(outcome_file), clock=now, sample_limit=1000,
    )
    claims, claims_sha = _safe_json(Path(receipt_manifest),required_type=dict)
    if (set(claims) != TOP_KEYS or
            claims.get("schema_version") != MANIFEST_SCHEMA or
            claims.get("market") != sealed["market"] or
            claims.get("label_definition_id") != sealed["label_definition_id"] or
            claims.get("rotation_freeze_sha256") != sealed["content_sha256"] or
            claims.get("outcomes_sha256") != outcomes_sha):
        raise ValueError("Rotation source manifest not bound to sealed pair protocol and label bytes")
    receipt_items = claims.get("claims")
    if not isinstance(receipt_items,list) or len(receipt_items)>2000:
        raise ValueError("Invalid pair source claims inventory")
    declared_labels = {row["security_id"]:row for row in outcomes}
    frozen_ids = set()
    for pair in sealed["pairs"]:
        frozen_ids.update((pair["incumbent_security_id"],pair["contender_security_id"]))
    directory = Path(receipt_manifest).parent
    if directory.is_symlink():
        raise ValueError("Unsafe pair source receipt directory")
    directory = directory.resolve()

    by_security: dict[str,dict] = {}
    for item in receipt_items:
        if not isinstance(item,dict) or set(item) != CLAIM_KEYS:
            raise ValueError("Malformed pair receipt claim fields")
        sec = _text(item,"security_id")
        if sec in by_security:
            raise ValueError("Duplicate source claim for rotation security")
        if sec not in frozen_ids:
            raise ValueError("Source claim references unknown/unmatched frozen issuer")
        _text(item,"source_id")
        _text(item,"publisher_id_claimed")
        filename = _text(item,"file")
        if not SAFE_NAME.fullmatch(filename) or filename.startswith("."):
            raise ValueError("Unsafe pair source document filename")
        digest = _text(item,"sha256")
        if not SHA.fullmatch(digest):
            raise ValueError("Invalid pair source document SHA256")
        _stamp(item["published_at"])
        _stamp(item["retrieved_at"])
        by_security[sec] = item

    sample: list[dict] = []
    blockers: list[str] = []
    supported = confirmed = nonconfirmed = 0
    for pair_row in base["pair_evidence_sample"]:
        sec_old = pair_row["incumbent_security_id"]
        sec_new = pair_row["contender_security_id"]
        status = pair_row["status"]
        issues: list[str] = []
        matched_securities = 0
        label_evaluable = status in AVAILABLE_RESEARCH_STATUSES
        if label_evaluable:
            for sec in (sec_old,sec_new):
                claim = by_security.get(sec)
                label = declared_labels.get(sec)
                if label is None:
                    raise ValueError("Underlying mature pair has a missing outcome label")
                if claim is None:
                    issues.append(sec+":MISSING_PAIR_OUTCOME_SOURCE_RECEIPT")
                    continue
                findings = _read_source_claim(directory, claim, label, cutoff)
                if findings:
                    issues.extend(sec+":"+reason for reason in findings)
                else:
                    matched_securities += 1
            if not issues and matched_securities==2:
                supported += 1
                if status == "RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED":
                    confirmed += 1
                else:
                    nonconfirmed += 1
        blockers.extend(issues)
        local_status = ("PAIR_OUTCOME_NOT_EVALUABLE" if not label_evaluable else
                        "LOCAL_TWO_OUTCOME_DOCUMENT_CLAIMS_MATCH_NOT_AUTHENTICATED"
                        if not issues and matched_securities==2 else
                        "CENSORED_MISSING_OR_CONFLICTING_PAIR_SOURCE")
        if len(sample)<sample_limit:
            sample.append({
                "pair_id":pair_row["pair_id"],
                "industry_id":pair_row["industry_id"],
                "incumbent_security_id":sec_old,
                "contender_security_id":sec_new,
                "underlying_research_outcome_status":status,
                "local_source_claim_status":local_status,
                "local_source_claims_consistent":label_evaluable and not issues,
                "matched_local_normalized_documents":matched_securities,
                "issues":sorted(set(issues)),
                "official_leader_replacement":False,
            })
    if supported > base["internally_evaluable_pair_count"]:
        raise ValueError("Pair source corroboration exceeds mature underlying outcomes")
    return {
        "status": STATUS,
        "market":sealed["market"],
        "model_version":sealed["model_version"],
        "label_definition_id":sealed["label_definition_id"],
        "evaluated_at_utc":cutoff.isoformat(),
        "rotation_freeze_sha256":sealed["content_sha256"],
        "outcomes_sha256":outcomes_sha,
        "source_claim_manifest_sha256":claims_sha,
        "frozen_pair_count":base["frozen_pair_count"],
        "internally_evaluable_pair_count":base["internally_evaluable_pair_count"],
        "unknown_or_censored_pair_count":base["unknown_or_censored_pair_count"],
        "locally_source_corroborated_pairs":supported,
        "eligible_pairs_missing_or_conflicting_source_evidence":
            base["internally_evaluable_pair_count"]-supported,
        "locally_source_corroborated_research_confirmations":confirmed,
        "locally_source_corroborated_research_nonconfirmations":nonconfirmed,
        "research_pair_confirmation_fraction_locally_corroborated":
            round(confirmed/supported,6) if supported else None,
        "blocker_count":len(sorted(set(blockers))),
        "blockers":sorted(set(blockers))[:sample_limit],
        "pair_evidence_sample":sample,
        "publisher_independently_authenticated":False,
        "source_retrieval_time_independently_attested":False,
        "historic_pit_certified":False,
        "actual_leader_replacement_certified":False,
        "official_leader_replacements":0,
        "warning":(
            "Local SHA256, normalized claim equality and timestamps do not "
            "authenticate source publishers, original timestamps, exchange "
            "PIT histories, issuer continuity, or real future leader outcomes."
        ),
    }
