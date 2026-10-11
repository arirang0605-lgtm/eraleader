"""5_3/5_5 native Top-K maturity/unknown-label inventory (NO future labels).

A horizon that has elapsed is NOT a real positive or negative leader outcome.
Only previously sealed, locally recorded native numeric scores may be shown.
Local SHA/OS time still cannot certify the publisher or market PIT universe.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import ceil
from pathlib import Path
import json
import re
import sqlite3

from .ranked_discovery import _frozen, _label_protocol, _now, _time, _canonical, ZONES
from .rank_score_pipeline import audit_computed_rank_provenance

STATUS="LOCAL_RANKED_MATURITY_INVENTORY_NOT_CERTIFIED"
NATIVE_BINDING_SCHEMA="eraleader.native_rank_cohort_binding.v1"
SHA=re.compile(r"[0-9a-f]{64}\Z")


def _validate_binding(frozen:dict) -> dict:
    binding=frozen.get("native_cohort_binding")
    required={
        "schema_version","scope","positive_watch_count",
        "distinct_positive_watch_securities","native_score_first_writes",
        "watch_score_evidence_sha256","score_availability_kind",
        "independent_source_pit_and_timestamp_attested",
    }
    if (not isinstance(binding,dict) or set(binding)!=required or
        binding.get("schema_version")!=NATIVE_BINDING_SCHEMA or
        binding.get("scope")!="ALL_PINNED_MODEL_POSITIVE_WATCH" or
        binding.get("score_availability_kind")!=
            "LOCAL_NATIVE_SCORE_FIRST_WRITE_NOT_FIRST_WATCH" or
        binding.get("independent_source_pit_and_timestamp_attested") is not False):
        raise ValueError("Frozen native cohort binding is missing or invalid")
    size=len(frozen["ranked_candidates"])
    for key in ("positive_watch_count","distinct_positive_watch_securities",
                "native_score_first_writes"):
        if type(binding.get(key)) is not int or binding[key]!=size:
            raise ValueError("Frozen native cohort original WATCH/score count inconsistent")
    if type(binding.get("watch_score_evidence_sha256")) is not str or not SHA.fullmatch(
        binding["watch_score_evidence_sha256"]
    ):
        raise ValueError("Native cohort source witness hash malformed")
    return binding


def _verify_native_original_witnesses(
    frozen:dict, binding:dict, score_db:Path,
) -> None:
    source=Path(score_db)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Missing or linked original native score source")
    db=sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        db.execute("BEGIN")
        try:
            records=db.execute(
                """SELECT security_id,evidence_hash,payload FROM rank_score_events
                   WHERE market=? AND model_version=?""",
                (frozen["market"],frozen["model_version"]),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Native score source ledger missing") from exc
        if len(records)!=len(frozen["ranked_candidates"]):
            raise ValueError("Native first-score source cohort count changed")
        witnesses=[]
        for sec,digest,encoded in records:
            if (not isinstance(sec,str) or type(digest) is not str or
                not SHA.fullmatch(digest)):
                raise ValueError("Invalid saved native first-score hash")
            try:
                evidence=json.loads(encoded)
            except (ValueError,TypeError) as exc:
                raise ValueError("Native first-score original payload unreadable") from exc
            if (not isinstance(evidence,dict) or evidence.get("security_id")!=sec
                    or not isinstance(evidence.get("watch_signal_id"),str)
                    or not isinstance(evidence.get("watch_payload_sha256"),str)):
                raise ValueError("Native score/WATCH witness missing")
            witnesses.append({
                "security_id":sec,
                "score_first_write_sha256":digest,
                "first_watch_signal_id":evidence["watch_signal_id"],
                "first_watch_payload_sha256":evidence["watch_payload_sha256"],
            })
        witnesses.sort(key=lambda row:row["security_id"])
        if {w["security_id"] for w in witnesses}!={
            row["security_id"] for row in frozen["ranked_candidates"]
        }:
            raise ValueError("Original native cohort security coverage changed")
        computed=sha256(_canonical(witnesses)).hexdigest()
        if computed!=binding["watch_score_evidence_sha256"]:
            raise ValueError("Original first-score/WATCH source witness hash changed")
    finally:
        db.close()


def audit_ranked_maturity(
    frozen_file:Path, definition_file:Path, score_db:Path,
    watch_db:Path, feature_dir:Path, *, as_of:str,
    sample_limit:int=100, clock:datetime|None=None,
) -> dict:
    """Read a sealed native cohort and schedule outcome eligibility only.

    There is intentionally NO outcome file input. Even after horizon end,
    outcomes remain UNKNOWN until an independently audited source exists.
    """
    if type(sample_limit) is not int or not 1<=sample_limit<=1000:
        raise ValueError("Ranked maturity sample_limit must be within 1..1000")
    now=_now(clock)
    at=_time(as_of)
    if at>now:
        raise ValueError("Future ranked maturity cutoff beyond OS clock forbidden")
    frozen=_frozen(Path(frozen_file))
    if at<_time(frozen["frozen_at_utc"]):
        raise ValueError("Ranked maturity cannot be audited before actual freeze seal")
    if _time(frozen["frozen_at_utc"])>now:
        raise ValueError("Frozen cohort claims a future seal")
    rule=frozen.get("label_definition_id")
    if (not isinstance(rule,str) or not rule.strip() or
        frozen.get("label_rule_bytes_pinned") is not True or
        frozen.get("outcome_definition_pinned_before_labels") is not True or
        type(frozen.get("label_definition_sha256")) is not str):
        raise ValueError("Predeclared leader label rule/bytes PIN missing")
    pinned=_label_protocol(Path(definition_file),label_id=rule,
                           market=frozen["market"],horizon=frozen["horizon_days"])
    if pinned!=frozen["label_definition_sha256"]:
        raise ValueError("Predeclared leader label rule original SHA changed")
    binding=_validate_binding(frozen)

    native=audit_computed_rank_provenance(
        Path(frozen_file),Path(score_db),Path(feature_dir),
        watch_db=Path(watch_db),sample_limit=min(1000,len(frozen["ranked_candidates"])),
    )
    if (native["blocker_count"] or
        native["locally_computed_score_records_matched"]!=len(frozen["ranked_candidates"]) or
        native["formula_reproduction_locally_consistent"] is not True):
        raise ValueError("Original native formula/WATCH score provenance is not intact: "+
                         ", ".join(native["blockers"][:12]))
    _verify_native_original_witnesses(frozen,binding,Path(score_db))

    zone=ZONES[frozen["market"]]
    snapshot_local=_time(frozen["snapshot_at_utc"]).astimezone(zone)
    deadline_local=snapshot_local+timedelta(days=frozen["horizon_days"])
    deadline=deadline_local.astimezone(timezone.utc)
    elapsed=at>=deadline
    chosen=frozen["ranked_candidates"][:frozen["requested_k"]]
    remaining_secs=max((deadline-at).total_seconds(),0)
    retrospective=frozen["retrospective_freeze"]
    state=("RETROSPECTIVE_SEAL_NOT_A_PREDICTION" if retrospective else
           "HORIZON_ELAPSED_OUTCOME_UNKNOWN" if elapsed else "HORIZON_PENDING")
    candidates=[]
    for row in chosen[:sample_limit]:
        candidates.append({
            "rank":row["rank"],
            "security_id":row["security_id"],
            "first_native_score":row["score"],
            "native_score_first_written_utc":row["recorded_at_utc"],
            "horizon_end_utc":deadline.isoformat(),
            "full_horizon_elapsed":elapsed,
            "hours_until_horizon_end":ceil(remaining_secs/3600),
            "status":state,
            "source_verified_future_leader_outcome":False,
            "leader_outcome_known":False,
        })
    # A second recheck helps catch contemporaneous modifications. A locally
    # controlled machine and its source clocks are NOT independent proof.
    _verify_native_original_witnesses(frozen,binding,Path(score_db))
    final_native=audit_computed_rank_provenance(
        Path(frozen_file),Path(score_db),Path(feature_dir),
        watch_db=Path(watch_db),sample_limit=min(1000,len(frozen["ranked_candidates"])),
    )
    if (final_native["blocker_count"] or
        final_native["locally_computed_score_records_matched"]!=len(frozen["ranked_candidates"]) or
        final_native["formula_reproduction_locally_consistent"] is not True):
        raise ValueError("Native feature/formula source revised during ranked maturity audit")
    if _frozen(Path(frozen_file))!=frozen:
        raise ValueError("Frozen ranked snapshot revised during maturity audit")
    if _label_protocol(Path(definition_file),label_id=rule,
                       market=frozen["market"],horizon=frozen["horizon_days"])!=pinned:
        raise ValueError("Predeclared leader rule modified during maturity audit")
    return {
        "status":STATUS,
        "market":frozen["market"],
        "model_version":frozen["model_version"],
        "label_definition_id":rule,
        "label_definition_sha256":pinned,
        "predeclared_rule_sha256_verified":True,
        "frozen_rank_sha256":frozen["content_sha256"],
        "frozen_at_utc":frozen["frozen_at_utc"],
        "snapshot_at_utc":frozen["snapshot_at_utc"],
        "as_of_utc":at.isoformat(),
        "market_as_of_day":at.astimezone(zone).date().isoformat(),
        "predeclared_horizon_days":frozen["horizon_days"],
        "horizon_end_market_local":deadline_local.isoformat(),
        "next_horizon_end_utc":None if elapsed else deadline.isoformat(),
        "selected_top_k_count":len(chosen),
        "full_horizon_elapsed_count":len(chosen) if elapsed else 0,
        "full_horizon_pending_count":0 if elapsed else len(chosen),
        "awaiting_mature_outcome_evidence_count":len(chosen) if elapsed else 0,
        "frozen_first_score_count":len(frozen["ranked_candidates"]),
        "local_native_provenance_rechecked":True,
        "native_first_watch_score_binding_sha256":binding["watch_score_evidence_sha256"],
        "retrospective_freeze":retrospective,
        "prospective_maturity_eligible":not retrospective,
        "selected_candidate_sample":candidates,
        "sample_truncated":len(chosen)>sample_limit,
        "outcome_labels_read":False,
        "source_document_outcome_corroborated":False,
        "known_positive_leaders":None,
        "known_failures":None,
        "precision_at_k":None,
        "recall_at_k":None,
        "actual_future_leader_skill_certified":False,
        "independently_authenticated_source_pit":False,
        "original_source_retrieval_clock_independently_attested":False,
        "official_leader_promotions":0,
        "warning":(
            "The native rank source and pinned future-leader rule are locally "
            "consistent. An elapsed fixed horizon alone cannot establish "
            "a positive/negative outcome. Real performance, independent "
            "source publication/issuer PIT, and complete exchange universe "
            "remain unaudited. No future labels were read."
        ),
    }
