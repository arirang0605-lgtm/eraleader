"""Prospectively freeze score-supported WATCH *pairs* for later label review.

Never infer an outcome from a missing label. Self-declared local scores,
industry membership, clocks and subsequent labels have no independent PIT
authenticity; all official leader certifications remain false.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from .frozen_holdout import _stamp, _canonical, _digest, _publish_once, TIMEZONES
from .peer_score_series import audit_peer_score_advantage, MIN_SCORE_ADVANTAGE

FROZEN_SCHEMA = "eraleader.rotation_pair_holdout.v1"
FREEZE_STATUS = "LOCAL_SEALED_PEER_ROTATION_PAIRS_NOT_PIT_CERTIFIED"
AUDIT_STATUS = "LOCAL_ROTATION_PAIR_MATURITY_OUTCOMES_RESEARCH_NOT_CERTIFIED"
MAX_BYTES = 2_000_000
MAX_FREEZE_LAG_HOURS = 72
FREEZE_KEYS = {
    "schema_version", "status", "market", "model_version",
    "label_definition_id", "horizon_days", "frozen_at_utc",
    "score_audit_sha256_claimed", "source_rotation_hypotheses",
    "score_correlated_hypotheses", "excluded_stale_pair_hypotheses",
    "excluded_ambiguous_peer_hypotheses", "eligible_pair_count",
    "pairs", "outcome_labels_included", "historic_pit_certified",
    "real_leader_replacement_certified", "official_leader_replacements",
    "content_sha256",
}
PAIR_KEYS = {
    "pair_id", "industry_id", "incumbent_security_id",
    "contender_security_id", "last_two_paired_market_days",
    "last_two_paired_scores", "last_two_paired_score_event_hashes",
    "last_two_paired_score_registered_at",
}
LABEL_KEYS = {
    "security_id", "label_definition_id", "is_future_leader",
    "mature_at", "outcome_available_at",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _deduplicated(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate sealed rotation or outcome JSON field")
        obj[key] = value
    return obj


def _safe_json(path: Path, *, required_type) -> tuple[object, str]:
    file = Path(path)
    if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= MAX_BYTES:
        raise ValueError("Missing, symlinked, empty or oversized research evidence file")
    raw = file.read_bytes()
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Empty or oversized research evidence bytes")
    try:
        obj = json.loads(raw, object_pairs_hook=_deduplicated)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Malformed research evidence JSON") from exc
    if not isinstance(obj, required_type):
        raise ValueError("Research evidence JSON has wrong object/list type")
    return obj, sha256(raw).hexdigest()


def _checked_clock(clock: datetime | None) -> datetime:
    now = clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Prospective research freeze/evaluation clock requires timezone")
    return now.astimezone(timezone.utc)


def _pair_id(market: str, model: str, frozen_at: str, row: dict) -> str:
    identity = {
        "market": market, "model_version": model, "frozen_at_utc": frozen_at,
        **{key: row[key] for key in PAIR_KEYS if key != "pair_id"},
    }
    return _digest(identity)


def _checked_pair(row: dict, *, market: str, model: str, frozen_at: datetime) -> datetime:
    if not isinstance(row, dict) or set(row) != PAIR_KEYS:
        raise ValueError("Malformed sealed rotation pair identity evidence")
    if any(not isinstance(row.get(key), str) or not row[key].strip() for key in (
            "industry_id", "incumbent_security_id", "contender_security_id")):
        raise ValueError("Missing rotation pair industry/permanent security ID")
    if row["incumbent_security_id"] == row["contender_security_id"]:
        raise ValueError("Cannot replace a WATCH with itself")
    if not isinstance(row["pair_id"], str) or not SHA.fullmatch(row["pair_id"]):
        raise ValueError("Invalid rotation pair ID")
    if row["pair_id"] != _pair_id(market, model, frozen_at.isoformat(), row):
        raise ValueError("Rotation pair id/identity mismatch")
    days = row["last_two_paired_market_days"]
    scores = row["last_two_paired_scores"]
    hashes = row["last_two_paired_score_event_hashes"]
    stamps = row["last_two_paired_score_registered_at"]
    if (not all(isinstance(x, list) and len(x) == 2 for x in
                (days, scores, hashes, stamps))):
        raise ValueError("Rotation pair needs two complete score sessions")
    try:
        decoded_days = [date.fromisoformat(day) for day in days]
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid market-local rotation score days") from exc
    if (any(not isinstance(day, str) or len(day) != 10 for day in days)
            or decoded_days != sorted(set(decoded_days))):
        raise ValueError("Rotation score market days unordered or duplicated")
    newest = None
    for day, pair, evidence, clock in zip(days, scores, hashes, stamps):
        if (not isinstance(pair, dict) or set(pair) != {
                "market_day", "incumbent_score", "contender_score"}
                or pair["market_day"] != day):
            raise ValueError("Sealed score/market-day identity mismatch")
        old, new = pair["incumbent_score"], pair["contender_score"]
        if (type(old) not in (int, float) or type(new) not in (int, float)
                or not math.isfinite(old) or not math.isfinite(new)
                or not 0 <= old <= 100 or not 0 <= new <= 100
                or round(new - old, 6) < MIN_SCORE_ADVANTAGE):
            raise ValueError("Sealed rotation score difference below fixed hypothesis")
        if (not isinstance(evidence, dict) or set(evidence) != {
                "incumbent_event_sha256", "contender_event_sha256"}
                or any(not isinstance(value, str) or not SHA.fullmatch(value)
                       for value in evidence.values())):
            raise ValueError("Malformed original rotation score-event SHA")
        if not isinstance(clock, dict) or set(clock) != {
                "incumbent_score_recorded_at_utc", "contender_score_recorded_at_utc"}:
            raise ValueError("Missing original score registration clocks")
        for registered in clock.values():
            at = _stamp(registered)
            if (at > frozen_at or
                    at.astimezone(TIMEZONES[market]).date().isoformat() != day):
                raise ValueError("Historical score registered after freeze or wrong market session")
            newest = at if newest is None or at > newest else newest
    return newest


def freeze_rotation_pairs(
    watch_db: Path, score_db: Path, feature_root: Path, target: Path, *,
    market: str, model_version: str, label_definition_id: str,
    horizon_days: int = 180, clock: datetime | None = None,
) -> dict:
    """One exclusive pre-outcome freeze; CLI cannot backdate OS time."""
    if market not in TIMEZONES:
        raise ValueError("Rotation frozen holdout supports KR/US only")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned model version required")
    if not isinstance(label_definition_id, str) or not label_definition_id.strip():
        raise ValueError("A predeclared rotation label definition is required")
    if type(horizon_days) is not int or not 1 <= horizon_days <= 1095:
        raise ValueError("Rotation forecast horizon must be 1..1095 days")
    now = _checked_clock(clock)
    audit = audit_peer_score_advantage(
        Path(watch_db), Path(score_db), Path(feature_root),
        market=market, model_version=model_version, evaluated_at=now.isoformat(),
        clock=now, sample_limit=1000,
    )
    pairs = audit["hypothesis_sample"]
    if len(pairs) != audit["rotation_hypothesis_count"]:
        raise ValueError("Truncated score rotation list cannot become a frozen cohort")
    scored = [row for row in pairs if row["locally_score_correlated"] is True]
    if len(scored) != audit["locally_two_session_score_correlated"]:
        raise ValueError("Partial local score audit cannot be frozen")
    contender_counts = Counter(row["contender_security_id"] for row in scored)
    accepted = []
    stale = multi_incumbents = 0
    for original in scored:
        if contender_counts[original["contender_security_id"]] != 1:
            multi_incumbents += 1
            continue
        row = {key: original[key] for key in PAIR_KEYS if key != "pair_id"}
        row["pair_id"] = _pair_id(market, model_version, now.isoformat(), row)
        last_written = _checked_pair(row,market=market,model=model_version,frozen_at=now)
        if (now - last_written).total_seconds() > MAX_FREEZE_LAG_HOURS*3600:
            stale += 1
            continue
        accepted.append(row)
    if not accepted:
        raise ValueError("No eligible contemporaneous score-corroborated rotation pairs for freeze")
    accepted.sort(key=lambda x: x["pair_id"])
    payload = {
        "schema_version": FROZEN_SCHEMA, "status": FREEZE_STATUS,
        "market": market, "model_version": model_version,
        "label_definition_id": label_definition_id,
        "horizon_days": horizon_days,
        "frozen_at_utc": now.isoformat(),
        "score_audit_sha256_claimed": _digest(audit),
        "source_rotation_hypotheses":audit["rotation_hypothesis_count"],
        "score_correlated_hypotheses":audit["locally_two_session_score_correlated"],
        "excluded_stale_pair_hypotheses":stale,
        "excluded_ambiguous_peer_hypotheses":multi_incumbents,
        "eligible_pair_count":len(accepted), "pairs":accepted,
        "outcome_labels_included":False, "historic_pit_certified":False,
        "real_leader_replacement_certified":False,
        "official_leader_replacements":0,
    }
    payload["content_sha256"] = _digest(payload)
    _publish_once(Path(target),payload)
    return {
        "status": FREEZE_STATUS, "path": str(target),
        "frozen_sha256": payload["content_sha256"],
        "eligible_pairs":len(accepted),
        "excluded_stale_pair_hypotheses":stale,
        "excluded_ambiguous_peer_hypotheses":multi_incumbents,
        "outcome_labels_included":False,
        "historic_pit_certified":False,
        "official_leader_replacements":0,
    }


def _read_rotation_freeze(path: Path) -> dict:
    obj, _ = _safe_json(Path(path), required_type=dict)
    checksum = obj.get("content_sha256")
    if (not isinstance(checksum,str) or not SHA.fullmatch(checksum)
            or _digest({k:v for k,v in obj.items() if k!="content_sha256"}) != checksum):
        raise ValueError("Frozen rotation holdout content hash mismatch")
    if (set(obj) != FREEZE_KEYS or
            obj.get("schema_version") != FROZEN_SCHEMA or obj.get("status") != FREEZE_STATUS
            or obj.get("market") not in TIMEZONES
            or not isinstance(obj.get("model_version"),str)
            or not obj["model_version"].strip()
            or not isinstance(obj.get("label_definition_id"),str)
            or not obj["label_definition_id"].strip()
            or type(obj.get("horizon_days")) is not int
            or not 1 <= obj["horizon_days"] <= 1095
            or obj.get("outcome_labels_included") is not False
            or obj.get("historic_pit_certified") is not False
            or obj.get("real_leader_replacement_certified") is not False
            or obj.get("official_leader_replacements") != 0):
        raise ValueError("Invalid sealed research-only rotation protocol")
    if (type(obj.get("eligible_pair_count")) is not int or
            not isinstance(obj.get("score_audit_sha256_claimed"),str) or
            not SHA.fullmatch(obj["score_audit_sha256_claimed"]) or
            any(type(obj.get(key)) is not int or obj[key]<0 for key in (
                "source_rotation_hypotheses", "score_correlated_hypotheses",
                "excluded_stale_pair_hypotheses",
                "excluded_ambiguous_peer_hypotheses")) or
            obj["score_correlated_hypotheses"]>obj["source_rotation_hypotheses"] or
            obj["eligible_pair_count"] + obj["excluded_stale_pair_hypotheses"]
            + obj["excluded_ambiguous_peer_hypotheses"] !=
                obj["score_correlated_hypotheses"]):
        raise ValueError("Inconsistent frozen research score inventory")
    frozen_at = _stamp(obj["frozen_at_utc"])
    if (not isinstance(obj.get("pairs"),list)
            or type(obj.get("eligible_pair_count")) is not int
            or len(obj["pairs"]) != obj["eligible_pair_count"]
            or len(obj["pairs"]) < 1 or len(obj["pairs"]) > 1000):
        raise ValueError("Inconsistent sealed rotation pair inventory")
    ids = set()
    contenders = set()
    for row in obj["pairs"]:
        newest = _checked_pair(row,market=obj["market"],
                               model=obj["model_version"],frozen_at=frozen_at)
        if (frozen_at-newest).total_seconds() > MAX_FREEZE_LAG_HOURS*3600:
            raise ValueError("Stale retrospectively frozen rotation pair")
        if row["pair_id"] in ids or row["contender_security_id"] in contenders:
            raise ValueError("Duplicated rotation pair identity or contender")
        ids.add(row["pair_id"])
        contenders.add(row["contender_security_id"])
    return obj


def audit_rotation_pair_outcomes(
    frozen_file: Path, *, evaluated_at: str,
    outcome_file: Path | None = None, sample_limit: int = 100,
    clock: datetime | None = None,
) -> dict:
    """Reconcile *later* self-declared results to immutable pairs.

    A pair is only internally evaluable AFTER its full predeclared
    market-local horizon and BOTH separate company labels have matured and
    become available. No missing labels are ever counted as failures.
    """
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("Rotation outcome sample_limit must be 1..1000")
    now = _checked_clock(clock)
    cutoff = _stamp(evaluated_at)
    if cutoff > now:
        raise ValueError("Future rotation evaluation cutoff is not permitted")
    frozen = _read_rotation_freeze(Path(frozen_file))
    frozen_at = _stamp(frozen["frozen_at_utc"])
    if cutoff <= frozen_at:
        raise ValueError("Rotation outcome evaluation cannot precede freeze")
    market = frozen["market"]
    zone = TIMEZONES[market]
    days = frozen["horizon_days"]
    labels: dict[str,dict] = {}
    labels_sha = None
    if outcome_file is not None:
        records, labels_sha = _safe_json(Path(outcome_file),required_type=list)
        if len(records) > 5000:
            raise ValueError("Oversized local rotation labels")
        for row in records:
            if not isinstance(row,dict):
                raise ValueError("Malformed rotation outcome record")
            sec = row.get("security_id")
            if not isinstance(sec,str) or not sec.strip() or sec in labels:
                raise ValueError("Duplicate or missing rotation outcome company ID")
            expected_keys = LABEL_KEYS | ({"leader_start_at"}
                                          if row.get("is_future_leader") is True else set())
            if set(row) != expected_keys or type(row.get("is_future_leader")) is not bool:
                raise ValueError("Invalid immutable rotation label definition/fields")
            if row.get("label_definition_id") != frozen["label_definition_id"]:
                raise ValueError("Outcome label definition differs from frozen protocol")
            mature = _stamp(row["mature_at"])
            available = _stamp(row["outcome_available_at"])
            if mature <= frozen_at or available <= frozen_at or available < mature:
                raise ValueError("Outcome maturity/availability predates freeze or maturity")
            if row["is_future_leader"]:
                onset = _stamp(row["leader_start_at"])
                if onset > mature:
                    raise ValueError("Positive leader onset cannot occur after reported maturity")
            labels[sec] = row
    examined = set()
    sample = []
    complete = pending = ready = unconfirmed = confirmed = 0
    for event in frozen["pairs"]:
        incumbent = event["incumbent_security_id"]
        contender = event["contender_security_id"]
        examined.update((incumbent,contender))
        due = (frozen_at.astimezone(zone) + timedelta(days=days)
               ).astimezone(timezone.utc)
        elapsed = cutoff >= due
        if elapsed:
            complete += 1
        else:
            pending += 1
        label_inc = labels.get(incumbent)
        label_new = labels.get(contender)
        status = "HORIZON_PENDING"
        if elapsed:
            if label_inc is None or label_new is None:
                status = "HORIZON_ELAPSED_NO_COMPLETE_LABELS"
            else:
                available_inc = _stamp(label_inc["outcome_available_at"])
                available_new = _stamp(label_new["outcome_available_at"])
                mature_inc = _stamp(label_inc["mature_at"])
                mature_new = _stamp(label_new["mature_at"])
                if (mature_inc > cutoff or mature_new > cutoff or
                        available_inc > cutoff or available_new > cutoff):
                    status = "LABEL_NOT_YET_AVAILABLE"
                elif ((not label_inc["is_future_leader"] and mature_inc < due) or
                      (not label_new["is_future_leader"] and mature_new < due)):
                    status = "PREMATURE_NEGATIVE_LABEL"
                elif ((label_inc["is_future_leader"] and
                       _stamp(label_inc["leader_start_at"]) <= frozen_at) or
                      (label_new["is_future_leader"] and
                       _stamp(label_new["leader_start_at"]) <= frozen_at)):
                    status = "PREEXISTING_OR_UNRELIABLE_POSITIVE_ONSET"
                elif (label_new["is_future_leader"] and
                      not label_inc["is_future_leader"] and
                      _stamp(label_new["leader_start_at"]) <= due):
                    status = "RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED"
                    confirmed += 1
                else:
                    status = "RESEARCH_PAIR_NOT_CONFIRMED_SOURCE_UNVERIFIED"
                    unconfirmed += 1
        if len(sample) < sample_limit:
            sample.append({
                "pair_id": event["pair_id"],
                "industry_id": event["industry_id"],
                "incumbent_security_id": incumbent,
                "contender_security_id": contender,
                "horizon_end_utc": due.isoformat(),
                "full_horizon_elapsed": elapsed,
                "both_local_outcome_labels_present": (
                    label_inc is not None and label_new is not None
                ),
                "status": status,
                "publisher_independently_attested": False,
                "official_leader_replacement": False,
            })
    known = confirmed + unconfirmed
    if known + (len(frozen["pairs"])-known) != len(frozen["pairs"]):
        raise ValueError("Rotation outcome count inconsistency")
    return {
        "status": AUDIT_STATUS,
        "frozen_sha256": frozen["content_sha256"],
        "market":market, "model_version":frozen["model_version"],
        "label_definition_id":frozen["label_definition_id"],
        "predeclared_horizon_days":days,
        "frozen_at_utc":frozen_at.isoformat(),
        "evaluated_at_utc":cutoff.isoformat(),
        "local_outcome_labels_supplied":outcome_file is not None,
        "self_declared_outcomes_sha256":labels_sha,
        "frozen_pair_count":len(frozen["pairs"]),
        "full_horizon_elapsed_pair_count":complete,
        "horizon_pending_pair_count":pending,
        "internally_evaluable_pair_count":known,
        "unknown_or_censored_pair_count":len(frozen["pairs"])-known,
        "research_pair_confirmed_count":confirmed,
        "research_pair_nonconfirmation_count":unconfirmed,
        "unmatched_outcome_label_count":len(set(labels)-examined),
        "research_known_pair_confirmation_fraction": (
            round(confirmed/known,6) if known else None
        ),
        "research_pair_confirmation_floor":(
            round(confirmed/len(frozen["pairs"]),6) if known else None
        ),
        "pair_evidence_sample":sample,
        "independent_future_label_source_certified":False,
        "historic_pit_certified":False,
        "real_leader_replacement_certified":False,
        "official_leader_replacements":0,
        "warning": (
            "Pair outcomes are separately provided SELF-DECLARED research "
            "labels, not authenticated exchange or prospective prediction "
            "results. Missing or immature outcome labels remain censored, "
            "not trading failures. Independent issuer/PIT/outcome proof absent."
        ),
    }
