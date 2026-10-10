"""Generate reproducible *research-only* numeric scores from local feature docs.

Unlike the general rank_score_ledger writer, this entrypoint never accepts
caller-supplied numeric scores: a fixed, versioned heuristic computes them
before the existing WATCH-linked first-write ledger checks. External source
times, historical PIT completeness and future-leader skill stay UNVERIFIED.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
import json
import math
import sqlite3

from .rank_score_ledger import (
    MARKETS, SAFE_NAME, _data, _now, register_rank_scores,
    audit_frozen_rank_scores, _open_watch, _watch_proof,
)
from .ranked_discovery import _time, _frozen
from .prospective import _canonical

# Fixed initial hypothesis, NOT an optimized or official 100-point leader model.
# Missing inputs reject the batch rather than receiving made-up zeroes.
HEURISTIC_VERSION = "eraleader.local_four_factor_rank_heuristic.v1"
TARGETS = {
    "revenue_yoy": 0.50,
    "operating_income_yoy": 0.75,
    "industry_revenue_yoy": 0.30,
    "momentum_6m": 0.60,
}
FORMULA_RULE = "equal_weight_mean_of_four_clipped_factor_ratios_round6"


def formula_provenance() -> dict:
    """Deterministic formula version and SHA pinned inside EACH numeric event."""
    formula = {"version":HEURISTIC_VERSION,"rule":FORMULA_RULE,"targets":TARGETS}
    return {
        "kind":"LOCAL_FIXED_FOUR_FACTOR",
        "formula_version":HEURISTIC_VERSION,
        "formula_sha256":sha256(_canonical(formula).encode("utf-8")).hexdigest(),
    }


def compute_research_score(features: dict) -> float:
    """Four bounded monotone proxies, equal weights, fixed ex ante."""
    if not isinstance(features, dict) or set(features) != set(TARGETS):
        raise ValueError("Exactly four observed rank factors required; no future labels")
    portions = []
    for key, target in TARGETS.items():
        value = features[key]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Invalid, missing or nonfinite observed rank factor")
        portions.append(min(1.0, max(0.0, value / target)))
    return round(100.0 * sum(portions) / len(portions), 6)


def compute_and_register_rank_scores(
    feature_dir: Path,
    watch_db: Path,
    score_db: Path,
    *,
    market: str,
    model_version: str,
    clock: datetime | None = None,
) -> dict:
    """Compute all scores *now* and use the existing atomic first-write ledger.

    The caller cannot provide scores or backdate the CLI clock. A deterministic
    injected clock is accepted only by this Python function for tests.
    All documents are checked before attempting a ledger transaction.
    """
    now = _now(clock)
    directory = Path(feature_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Feature directory missing or linked")
    if market not in MARKETS or not isinstance(model_version, str) or not model_version:
        raise ValueError("Valid market and pinned model_version required")
    paths = sorted(directory.glob("*.json"))
    if not 1 <= len(paths) <= 1000:
        raise ValueError("Require 1..1000 feature evidence documents")
    rows = []
    securities = set()
    for path in paths:
        if not SAFE_NAME.fullmatch(path.name) or path.name.startswith("."):
            raise ValueError("Unsafe feature evidence filename")
        blob = _data(path)
        doc = json.loads(blob)
        if (not isinstance(doc, dict) or
            set(doc) != {"schema", "market", "model_version",
                         "security_id", "available_at", "features"} or
            doc["schema"] != "eraleader.rank_feature_document.v1" or
            doc["market"] != market or doc["model_version"] != model_version):
            raise ValueError("Feature evidence market/model/schema mismatch")
        security_id = doc["security_id"]
        if (not isinstance(security_id, str) or not security_id.strip()
            or security_id in securities):
            raise ValueError("Duplicate or empty permanent security_id")
        securities.add(security_id)
        if _time(doc["available_at"]) > now:
            raise ValueError("Future features are forbidden")
        score = compute_research_score(doc["features"])
        rows.append({
            "security_id": security_id,
            "score": score,
            "feature_file": path.name,
            "feature_sha256": sha256(blob).hexdigest(),
            "features_available_at": doc["available_at"],
        })
    # Deliberately ephemeral: do not retain a misleading externally supplied
    # score-input file. The original feature files and SQLite stay local.
    scratch = None
    try:
        with NamedTemporaryFile(
            mode="w", suffix=".tmp", prefix=".computed_rank_",
            dir=directory, encoding="utf-8", delete=False,
        ) as tmp:
            scratch = Path(tmp.name)
            json.dump(rows, tmp, sort_keys=True, allow_nan=False)
        receipt = register_rank_scores(
            Path(score_db), Path(watch_db), directory, scratch,
            market=market, model_version=model_version, clock=now,
            computation_provenance=formula_provenance(),
        )
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)
    return {
        "status": "LOCAL_COMPUTED_RANK_RESEARCH_ONLY",
        "market": market,
        "model_version": model_version,
        "formula_version": HEURISTIC_VERSION,
        "formula_provenance_sha256": formula_provenance()["formula_sha256"],
        "fixed_factor_targets": TARGETS,
        "locally_computed_this_run": len(rows),
        "new_score_records": receipt["new_score_records"],
        "duplicate_score_records": receipt["duplicate_score_records"],
        "score_first_write_clock_utc": receipt["score_recorded_at_utc"],
        "external_feature_publication_attested": False,
        "independent_score_computation_attested": False,
        "historic_universe_and_actions_pit_certified": False,
        "real_future_leader_skill_certified": False,
        "official_leader_promotions": 0,
    }


def audit_computed_rank_provenance(frozen_file: Path, score_db: Path,
                                   feature_dir: Path, *, watch_db: Path,
                                   sample_limit: int=100) -> dict:
    """Recompute pinned four-factor scores against immutable local score records.

    Fails closed on missing formula claim or mismatched feature bytes/score.
    No local procedure certifies third-party source authenticity or leader skill.
    """
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("Invalid formula audit sample limit")
    frozen=_frozen(Path(frozen_file))
    base=audit_frozen_rank_scores(Path(frozen_file),Path(score_db),Path(feature_dir),
                                   sample_limit=sample_limit)
    database=Path(score_db)
    if database.is_symlink() or not database.is_file():
        raise ValueError("Score registry missing or linked")
    source=Path(feature_dir)
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Feature directory missing or linked")
    connection=sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        rows=connection.execute(
            "SELECT security_id,payload FROM rank_score_events WHERE market=? AND model_version=?",
            (frozen["market"],frozen["model_version"])).fetchall()
    finally:
        connection.close()
    records={sec:json.loads(payload) for sec,payload in rows}
    if len(records)!=len(rows):
        raise ValueError("Duplicated score record security ID")
    expected=formula_provenance()
    watch=_open_watch(Path(watch_db))
    try:
        return _recheck_formula_records(
            frozen,base,records,source,expected,watch,sample_limit)
    finally:
        watch.close()


def _recheck_formula_records(frozen,base,records,source,expected,watch,sample_limit):
    blockers=set(base["blockers"])
    matching=0
    sample=[]
    for candidate in frozen["ranked_candidates"]:
        sid=candidate["security_id"]
        entry=records.get(sid)
        reasons=[]
        if entry is None:
            reasons.append("MISSING_COMPUTED_SCORE")
        else:
            score_recorded=_time(entry["score_recorded_at_utc"])
            watch_registered=_time(entry["watch_registered_at_utc"])
            if _time(candidate["recorded_at_utc"])!=score_recorded:
                reasons.append("RANK_CLAIMED_FIRST_TIME_DIFFERS_FROM_SCORE_FIRST_WRITE")
            computed=_time(candidate["score_computed_at_utc"])
            if computed<watch_registered:
                reasons.append("RANK_CLAIMED_COMPUTED_BEFORE_ORIGINAL_WATCH")
            try:
                truth=_watch_proof(watch,frozen["market"],frozen["model_version"],
                                   sid,score_recorded,3)
                if (entry.get("watch_signal_id")!=truth["watch_signal_id"] or
                    entry.get("watch_payload_sha256")!=truth["watch_payload_sha256"] or
                    watch_registered!=truth["watch_registered_at"]):
                    reasons.append("SCORE_WATCH_SOURCE_LINK_CHANGED")
            except ValueError:
                reasons.append("SCORE_ORIGINAL_WATCH_REGISTRY_INVALID")
            provenance=entry.get("computation_provenance")
            if provenance is None:
                reasons.append("NUMERIC_SCORE_WAS_EXTERNAL_SUBMISSION_NOT_NATIVE_COMPUTATION")
            elif provenance!=expected:
                reasons.append("PINNED_FORMULA_VERSION_OR_DIGEST_MISMATCH")
            name=entry.get("feature_file")
            path=source/name if isinstance(name,str) and SAFE_NAME.fullmatch(name) else None
            if path is None or path.is_symlink() or not path.is_file():
                reasons.append("SOURCE_FEATURE_FILE_UNAVAILABLE")
            else:
                blob=_data(path)
                if sha256(blob).hexdigest()!=entry.get("feature_sha256"):
                    reasons.append("SOURCE_FEATURE_HASH_REVISED")
                else:
                    try:
                        doc=json.loads(blob)
                        features=doc["features"]
                        if (doc.get("market")!=frozen["market"] or
                            doc.get("model_version")!=frozen["model_version"] or
                            doc.get("security_id")!=sid):
                            reasons.append("SOURCE_FEATURE_IDENTITY_MISMATCH")
                        elif compute_research_score(features)!=entry.get("score"):
                            reasons.append("SAVED_SCORE_DIFFERS_FROM_RECOMPUTED_FORMULA")
                    except (ValueError,TypeError,KeyError) as exc:
                        reasons.append("SOURCE_FEATURE_FORMULA_INPUT_INVALID")
            if candidate["score"]!=entry.get("score"):
                reasons.append("FROZEN_RANK_SCORE_CHANGED")
        blockers.update(f"{sid}:{reason}" for reason in reasons)
        if not reasons and not any(x.startswith(sid+":") for x in base["blockers"]):
            matching+=1
        if len(sample)<sample_limit:
            sample.append({
                "security_id":sid,
                "local_formula_claim_matched":not reasons and entry is not None,
                "locally_recomputed_score_matches":not reasons and entry is not None,
                "issues":sorted(reasons),
            })
    issues=sorted(blockers)
    return {
        "status":"LOCAL_FOUR_FACTOR_COMPUTATION_RECHECK_NOT_CERTIFIED",
        "market":frozen["market"],"model_version":frozen["model_version"],
        "frozen_rank_sha256":frozen["content_sha256"],
        "formula_version":HEURISTIC_VERSION,
        "formula_sha256":expected["formula_sha256"],
        "ranked_candidate_count":len(frozen["ranked_candidates"]),
        "locally_computed_score_records_matched":matching,
        "blocker_count":len(issues),"blockers":issues,
        "candidate_sample":sample,
        "formula_reproduction_locally_consistent":not issues,
        "formula_execution_independently_attested":False,
        "feature_source_publication_independently_attested":False,
        "historical_universe_pit_certified":False,
        "real_future_leader_skill_certified":False,
        "official_leader_promotions":0,
        "warning":(
            "The formula's self-declared digest, local source bytes and rank "
            "score can be reproduced, but no independent publication/compute "
            "time attestation or actual era-leader accuracy is established."
        ),
    }
