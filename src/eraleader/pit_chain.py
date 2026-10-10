"""Research-only provenance chain: signal-time source audits -> frozen candidates -> dated outcomes.

Existing independent modules are reconciled without reinterpreting file
hashes or provider-declared clocks as authentic historical PIT attestation.
A locally complete chain NEVER promotes or certifies actual era leaders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from .evidence_gate import evaluate_local_evidence, _iso_time
from .frozen_holdout import _read_frozen, _stamp
from .holdout_outcome_reconcile import reconcile_holdout_outcomes
from .outcome_source_claims import audit_outcome_source_claims

STATUS_BLOCKED="BLOCKED_PIT_TO_OUTCOME_CHAIN_RESEARCH_ONLY"
STATUS_LOCAL="LOCAL_PIT_TO_OUTCOME_CHAIN_COHERENT_NOT_CERTIFIED"


def audit_pit_to_outcome_chain(
    *, market: str, decision_at: str, evaluated_at: str,
    report_dir: Path, frozen_file: Path,
    outcome_file: Path | None = None,
    receipt_manifest: Path | None = None,
    clock: datetime | None = None,
) -> dict:
    """Reconcile 5 market-domain audits, sealed model protocol and label receipts.

    The market source decision must be no later than the earliest actual
    candidate registration. All clock claims remain independently UNVERIFIED.
    """
    if market not in ("KR", "US"):
        raise ValueError("PIT chain market must be KR/US")
    if (outcome_file is None) != (receipt_manifest is None):
        raise ValueError("Outcome labels and source receipt manifest must be supplied together")
    now=clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Audit clock requires timezone")
    cutoff=_iso_time(decision_at)
    evaluation=_stamp(evaluated_at)
    if evaluation > now.astimezone(timezone.utc):
        raise ValueError("Future outcome evaluation is forbidden")
    if cutoff > evaluation:
        raise ValueError("Market source cutoff is after outcome evaluation")
    freeze=Path(frozen_file)
    if freeze.is_symlink() or not freeze.is_file():
        raise ValueError("Missing or symlinked sealed candidate manifest")
    frozen=_read_frozen(freeze)
    if frozen.get("market")!=market:
        raise ValueError("Sealed candidate market differs from PIT market")
    if cutoff > _stamp(frozen["frozen_at_utc"]):
        raise ValueError("Source decision cutoff postdates sealed freeze")

    evidence=evaluate_local_evidence(Path(report_dir),market=market,
                                     decision_at=decision_at)
    reconciliation=reconcile_holdout_outcomes(
        freeze,evaluated_at=evaluated_at,outcome_file=outcome_file,clock=now,
        sample_limit=1000)
    if (reconciliation.get("market")!=market or
            reconciliation.get("frozen_manifest_sha256")!=frozen["content_sha256"] or
            reconciliation.get("model_version")!=frozen["model_version"] or
            reconciliation.get("label_definition_id")!=frozen["label_definition_id"]):
        raise ValueError("Sealed holdout and outcome research contract mismatch")

    blockers=[f"source:{b}" for b in evidence["blockers"]]
    registrations=[_stamp(x["recorded_at_utc"]) for x in frozen["signals"]]
    if registrations and cutoff>min(registrations):
        blockers.append("cross_stage:SOURCE_CUTOFF_AFTER_CANDIDATE_REGISTRATION")
    source_claims=None
    if outcome_file is None:
        blockers.append("outcomes:SOURCE_LABEL_RECEIPTS_NOT_PROVIDED")
    else:
        source_claims=audit_outcome_source_claims(
            freeze,Path(outcome_file),Path(receipt_manifest),
            evaluated_at=evaluated_at,clock=now,sample_limit=1000)
        if (source_claims.get("market")!=market or
                source_claims.get("frozen_manifest_sha256")!=frozen["content_sha256"] or
                source_claims.get("label_definition_id")!=frozen["label_definition_id"] or
                source_claims.get("outcomes_sha256")!=reconciliation["outcomes_sha256"]):
            raise ValueError("Result source receipts do not match the sealed cohort")
        blockers.extend(f"outcomes:{b}" for b in source_claims["blockers"])
        if source_claims["eligible_outcomes_missing_or_inconsistent_sources"]>0:
            blockers.append("outcomes:MISSING_OR_INCONSISTENT_EVALUABLE_SOURCE_EVIDENCE")
        if source_claims["local_source_claims_consistent"]!=reconciliation["internally_evaluable_outcome_count"]:
            blockers.append("outcomes:NOT_ALL_EVALUABLE_CLAIMS_HAVE_LOCAL_SOURCE_EVIDENCE")
    if reconciliation["unknown_or_censored_count"]>0:
        blockers.append("outcomes:UNRESOLVED_OR_UNMATURED_HOLDOUT_CANDIDATES")
    blockers=sorted(set(blockers))
    locally_coherent=not blockers
    return {
        "status":STATUS_LOCAL if locally_coherent else STATUS_BLOCKED,
        "market":market,
        "source_decision_at_utc":cutoff.isoformat(),
        "evaluated_at_utc":evaluation.isoformat(),
        "model_version":frozen["model_version"],
        "label_definition_id":frozen["label_definition_id"],
        "predeclared_horizon_days":frozen["horizon_days"],
        "frozen_manifest_sha256":frozen["content_sha256"],
        "source_domain_audit_hashes":{
            e["domain"]:e["sha256"] for e in evidence["evidence"]},
        "outcomes_sha256":reconciliation["outcomes_sha256"],
        "source_claim_manifest_sha256":(
            source_claims["source_claim_manifest_sha256"] if source_claims else None),
        "source_report_domains_present":evidence["present_domains"],
        "source_report_domains_required":evidence["required_domains"],
        "local_market_domain_diagnostics_complete":evidence["research_diagnostics_complete"],
        "frozen_candidate_count":reconciliation["frozen_candidates"],
        "horizon_elapsed_count":reconciliation["horizon_elapsed_count"],
        "internally_evaluable_research_labels":reconciliation["internally_evaluable_outcome_count"],
        "local_consistent_outcome_source_claims":(
            source_claims["local_source_claims_consistent"] if source_claims else 0),
        "unresolved_candidate_count":reconciliation["unknown_or_censored_count"],
        "blocker_count":len(blockers),
        "blockers":blockers,
        "research_chain_locally_coherent":locally_coherent,
        "publisher_independently_authenticated":False,
        "source_availability_independently_attested":False,
        "historic_universe_pit_certified":False,
        "independent_outcome_labels_certified":False,
        "leader_prediction_accuracy_certified":False,
        "official_leader_promotions":0,
        "warning":(
            "This chain only reconciles local, partly self-declared audit summaries "
            "and outcome file hashes. Even coherent reports are not official PIT "
            "provenance, complete historical listed/delisted universes, independent "
            "outcome evidence, or real future leader prediction accuracy."
        ),
    }
