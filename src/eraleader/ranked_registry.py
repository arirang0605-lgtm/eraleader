"""Read-only linkage between frozen ranked top-K and real WATCH registration.

Links permanent security IDs and exact first registered timestamps to the
original append-only, local prospective.sqlite event payload. It NEVER proves
a score existed at registration: the WATCH payload explicitly has full_score
None; rank inputs are separately claimed and unauthenticated.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .ranked_discovery import _frozen, _time, ZONES
from .prospective import _SIGNAL_KIND, _STATUS, _canonical

STATUS = "RANKED_WATCH_LEDGER_RESEARCH_LINK_NOT_CERTIFIED"


def audit_ranked_watch_registry(
    frozen_file: Path, registry_file: Path, *, max_registration_lag_days: int = 3,
    sample_limit: int = 100,
) -> dict:
    """Fail closed on original WATCH record tampering, count unlinked ranks.

    For the same security/model, the earliest actually registered positive
    signal is authoritative. Matching rank timestamp is necessary, but not
    sufficient evidence that the supplied numerical score then existed.
    """
    if type(max_registration_lag_days) is not int or not 0 <= max_registration_lag_days <= 14:
        raise ValueError("Invalid max registration lag")
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("Invalid rank audit sample limit")
    frozen=_frozen(Path(frozen_file))
    file=Path(registry_file)
    if file.is_symlink() or not file.is_file():
        raise ValueError("Missing or symlinked prospective WATCH registry")
    market=frozen["market"]
    model=frozen["model_version"]
    snapshot=_time(frozen["snapshot_at_utc"])
    zone=ZONES[market]
    connection=sqlite3.connect(file.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        try:
            rows=connection.execute(
                """SELECT signal_id,security_id,kind,observed_as_of,
                          recorded_at_utc,source_run_id,model_version,
                          payload_hash,payload,status
                   FROM prospective_signals
                   WHERE market=? AND model_version=?
                   ORDER BY recorded_at_utc,signal_id""",
                (market,model)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("WATCH registry is absent or not readable") from exc
    finally:
        connection.close()

    earliest={}
    total_seen=0
    historical_backfills=0
    for signal_id,sec,kind,observed,registered,run_id,version,digest,payload,status in rows:
        if (not isinstance(sec,str) or not sec or not isinstance(run_id,str)
                or not run_id or kind!=_SIGNAL_KIND or status!=_STATUS or version!=model):
            raise ValueError("Unexpected original WATCH signal identity/status")
        observed_dt=_time(observed)
        registered_dt=_time(registered)
        expected_signal=sha256(f"{market}|{sec}|{kind}|{observed}|{version}".encode()).hexdigest()
        if signal_id!=expected_signal or not isinstance(payload,str):
            raise ValueError("Original WATCH event ID or payload invalid")
        if sha256(payload.encode("utf-8")).hexdigest()!=digest:
            raise ValueError("Original WATCH payload checksum mismatch")
        try:
            basis=json.loads(payload)
        except (ValueError,TypeError) as exc:
            raise ValueError("Original WATCH JSON invalid") from exc
        if not isinstance(basis,dict) or _canonical(basis)!=payload:
            raise ValueError("Original WATCH payload noncanonical")
        company=basis.get("company")
        if (not isinstance(company,dict)
            or basis.get("market")!=market or basis.get("model_version")!=version
            or basis.get("source_run_id")!=run_id
            or _time(basis.get("as_of"))!=observed_dt
            or company.get("security_id")!=sec or company.get("market")!=market
            or _time(company.get("as_of"))!=observed_dt
            or company.get("research_growth_screen_hit") is not True
            or company.get("research_screen_evaluated",True) is not True
            or company.get("state")!="WATCH" or company.get("full_score") is not None
            or company.get("verified_future_leader_candidate") is not False):
            raise ValueError("Original WATCH registry company/source identity mismatch")
        if observed_dt>registered_dt:
            raise ValueError("Original WATCH observation registered in its future")
        lag=(registered_dt.astimezone(zone).date()-observed_dt.astimezone(zone).date()).days
        total_seen+=1
        if lag>max_registration_lag_days:
            historical_backfills+=1
            continue
        if registered_dt>snapshot:
            continue
        current=earliest.get(sec)
        if current is None or registered_dt<current["registered"]:
            earliest[sec]={"registered":registered_dt,"signal_id":signal_id,
                           "observed":observed_dt,"payload_sha256":digest,"lag":lag,
                           "source_run_id":run_id}

    count=0
    issues=[]
    sample=[]
    top_ids={r["security_id"] for r in frozen["ranked_candidates"][:frozen["requested_k"]]}
    for entry in frozen["ranked_candidates"]:
        sec=entry["security_id"]
        rank=entry["rank"]
        found=earliest.get(sec)
        errors=[]
        if found is None:
            errors.append("NO_ELIGIBLE_REGISTERED_WATCH_FOR_PINNED_MODEL")
        elif _time(entry["recorded_at_utc"])!=found["registered"]:
            errors.append("RANK_TIMESTAMP_DIFFERS_FROM_FIRST_WATCH_REGISTRATION")
        if found is not None and _time(entry["features_available_at_utc"])>found["registered"]:
            errors.append("RANK_FEATURE_AVAILABLE_AFTER_WATCH_REGISTRATION")
        if found is not None and _time(entry["score_computed_at_utc"])>found["registered"]:
            errors.append("RANK_SCORE_COMPUTED_AFTER_WATCH_REGISTRATION")
        if errors:
            issues.extend(f"{sec}:{message}" for message in errors)
        else:
            count+=1
        if len(sample)<sample_limit:
            sample.append({
                "security_id":sec,"rank":rank,
                "top_k_selected":sec in top_ids,
                "watch_registration_locally_matched":not errors,
                "first_watch_signal_id":found["signal_id"] if found else None,
                "first_watch_payload_sha256":found["payload_sha256"] if found else None,
                "original_watch_contains_numeric_rank_score":False,
                "issues":errors,
            })
    errors=sorted(set(issues))
    # A retrospective seal or unauthenticated rank score can NEVER represent
    # verified historical first detection, even with a zero-error ID join.
    return {
        "status":STATUS,
        "market":market,"model_version":model,
        "frozen_rank_sha256":frozen["content_sha256"],
        "requested_k":frozen["requested_k"],
        "registered_watch_records_scanned":total_seen,
        "historical_backfill_records_excluded":historical_backfills,
        "ranked_candidate_count":len(frozen["ranked_candidates"]),
        "top_k_candidate_count":len(top_ids),
        "ranked_ids_and_first_timestamps_matched":count,
        "unmatched_or_mismatched_ranked_candidates":len(frozen["ranked_candidates"])-count,
        "retrospective_freeze":frozen["retrospective_freeze"],
        "blocker_count":len(errors),"blockers":errors,
        "candidate_sample":sample,
        "rank_ids_and_registration_dates_locally_consistent":not errors,
        "original_watch_has_independently_recorded_numeric_score":False,
        "rank_score_availability_independently_attested":False,
        "issuer_universe_pit_certified":False,
        "prospective_discovery_skill_certified":False,
        "official_leader_promotions":0,
        "warning":(
            "WATCH ledger records positive research-screen IDs, not a numeric "
            "rank score. Matching original signal IDs and actual local recorded "
            "timestamps is a necessary local link but cannot prove a score "
            "was computed then or that source clocks are independently authentic."
        ),
    }
