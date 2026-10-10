"""5_4 / 5_5 sealed *research* holdout of actually registered candidate signals.

Freeze contains no future labels; evaluation can only attach outcomes after
their maturity and availability. Neither local clock nor source provenance is
independently certified; results are NEVER real investment-performance claims.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
from statistics import median
import sqlite3

TIMEZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
SCHEMA = "eraleader.holdout.v1"
STATUS = "OFFLINE_SEALED_HOLDOUT_RESEARCH_ONLY_NOT_CERTIFIED"

def _stamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected timezone-aware timestamp")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid ISO timestamp") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return t.astimezone(timezone.utc)

def _canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)

def _digest(data: dict) -> str:
    return sha256(_canonical(data).encode("utf-8")).hexdigest()

def _read_frozen(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA:
        raise ValueError("Invalid frozen-holdout schema")
    digest = data.pop("content_sha256", None)
    if digest != _digest(data):
        raise ValueError("Frozen holdout hash mismatch")
    if data.get("historic_pit_certified") is not False:
        raise ValueError("Holdout may not certify historical PIT")
    data["content_sha256"] = digest
    return data

def _publish_once(path: Path, data: dict) -> None:
    """Exclusive create, with fsync; never overwrite an existing sealed freeze.

    External T5DATA may be exFAT (no hard-links). A crash during the write
    leaves an invalid checksum and fails closed rather than rewriting history.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2)
    created = False
    try:
        with path.open("x", encoding="utf-8") as fp:
            created = True
            fp.write(payload)
            fp.flush()
            os.fsync(fp.fileno())
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise

def freeze_registered_candidates(
    registry_path: Path, target: Path, *,
    market: str, model_version: str, label_definition_id: str,
    horizon_days: int = 180, max_observation_lag_days: int = 3,
    clock: datetime | None = None
) -> dict:
    """Lock first *on-time* registration per ID. No outcome labels are read."""
    if market not in TIMEZONES:
        raise ValueError("Only KR/US market allowed")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Model version must be pinned")
    if not isinstance(label_definition_id, str) or not label_definition_id.strip():
        raise ValueError("Holdout label definition ID must be predeclared")
    if isinstance(horizon_days, bool) or not isinstance(horizon_days, int) or not 1 <= horizon_days <= 1095:
        raise ValueError("Holdout horizon_days must be fixed at freeze")
    if isinstance(max_observation_lag_days, bool) or not isinstance(max_observation_lag_days, int) or not 0 <= max_observation_lag_days <= 14:
        raise ValueError("Invalid observation lag")
    stamp = clock if clock is not None else datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Freeze clock requires timezone")
    frozen_at = stamp.astimezone(timezone.utc)
    registry_path = Path(registry_path)
    if not registry_path.is_file():
        raise FileNotFoundError(f"Missing prospective source ledger: {registry_path}")
    db = sqlite3.connect(registry_path.resolve().as_uri()+"?mode=ro", uri=True)
    try:
        rows = db.execute("""SELECT signal_id,security_id,kind,observed_as_of,
                                    recorded_at_utc,source_run_id,payload_hash,payload,
                                    status,model_version
                             FROM prospective_signals WHERE market=? AND model_version=?
                             ORDER BY recorded_at_utc,signal_id""",
                          (market, model_version)).fetchall()
    finally:
        db.close()
    accepted = {}
    late = future = 0
    for signal_id, sec, kind, seen, recorded, run_id, fingerprint, payload, status, version in rows:
        if status != "PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED" or version != model_version:
            raise ValueError("Unexpected registry status or model version")
        # The prospective registry is local and writable. Verify every frozen
        # record against its original canonical screen payload before locking
        # the earliest signal; a stale or rewritten SQLite cell must fail closed.
        if (kind != "UNVERIFIED_GROWTH_SCREEN" or
                signal_id != sha256(f"{market}|{sec}|{kind}|{seen}|{version}".encode()).hexdigest()):
            raise ValueError("Prospective signal identity mismatch")
        if not isinstance(payload, str) or sha256(payload.encode("utf-8")).hexdigest() != fingerprint:
            raise ValueError("Prospective registry payload hash mismatch")
        try:
            basis = json.loads(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("Prospective registry payload invalid") from exc
        if not isinstance(basis, dict) or _canonical(basis) != payload:
            raise ValueError("Prospective registry payload is not canonical")
        company = basis.get("company")
        if (not isinstance(company, dict) or basis.get("market") != market or
                basis.get("source_run_id") != run_id or basis.get("model_version") != version or
                company.get("security_id") != sec or company.get("market") != market or
                company.get("state") != "WATCH" or company.get("full_score") is not None or
                company.get("verified_future_leader_candidate") is not False or
                company.get("research_growth_screen_hit") is not True):
            raise ValueError("Prospective registry payload identity or research status mismatch")
        actual_time = _stamp(recorded)
        observation_time = _stamp(seen)
        if _stamp(basis.get("as_of")) != observation_time or _stamp(company.get("as_of")) != observation_time:
            raise ValueError("Prospective registry observation timestamp mismatch")
        if observation_time > actual_time or actual_time > frozen_at:
            future += 1
            continue
        local_day = actual_time.astimezone(TIMEZONES[market]).date()
        observed_day = observation_time.astimezone(TIMEZONES[market]).date()
        lag = (local_day-observed_day).days
        if lag < 0 or lag > max_observation_lag_days:
            late += 1
            continue
        if sec not in accepted:
            accepted[sec] = {
                "security_id": sec, "observed_as_of": seen,
                "recorded_at_utc": recorded, "source_run_id": run_id,
                "model_version": version, "payload_sha256": fingerprint,
                "registration_lag_days": lag,
            }
    if future:
        raise ValueError("Prospective registry contains future timestamps")
    payload = {
        "schema_version": SCHEMA, "market": market,
        "model_version": model_version,
        "label_definition_id": label_definition_id,
        "horizon_days": horizon_days,
        "frozen_at_utc": frozen_at.isoformat(),
        "max_observation_lag_days": max_observation_lag_days,
        "eligible_count": len(accepted),
        "excluded_historical_backfills": late,
        "signals": sorted(accepted.values(), key=lambda x:x["security_id"]),
        "historic_pit_certified": False, "outcome_labels_included": False,
        "status": STATUS,
        "warning": "Local clock and retrospective source completeness are NOT independently attested.",
    }
    payload["content_sha256"] = _digest(payload)
    _publish_once(Path(target), payload)
    return {"status": STATUS, "path": str(target),
            "eligible_candidates":len(accepted),
            "label_definition_id":label_definition_id,
            "horizon_days":horizon_days,
            "excluded_historical_backfills":late,
            "outcome_labels_included":False, "historic_pit_certified":False}

def evaluate_frozen_candidates(
    frozen_file: Path, outcome_file: Path, *,
    evaluated_at: str, horizon_days: int | None = None, clock: datetime | None = None
) -> dict:
    """Post-freeze assessment without inserting future labels into signal data."""
    frozen = _read_frozen(frozen_file)
    frozen_horizon = frozen.get("horizon_days")
    if type(frozen_horizon) is not int or not 1 <= frozen_horizon <= 1095:
        raise ValueError("Frozen horizon configuration invalid")
    if not isinstance(frozen.get("label_definition_id"), str) or not frozen["label_definition_id"].strip():
        raise ValueError("Frozen label definition is missing")
    if horizon_days is None:
        horizon_days = frozen_horizon
    if type(horizon_days) is not int or horizon_days != frozen_horizon:
        raise ValueError("Evaluation horizon cannot differ from frozen protocol")
    cutoff = _stamp(evaluated_at)
    real_now = clock if clock is not None else datetime.now(timezone.utc)
    if real_now.tzinfo is None or real_now.utcoffset() is None:
        raise ValueError("Evaluation clock requires timezone")
    if cutoff > real_now.astimezone(timezone.utc):
        raise ValueError("Future evaluation cutoff cannot be used")
    if cutoff <= _stamp(frozen["frozen_at_utc"]):
        raise ValueError("Evaluation must take place after freeze")
    market = frozen.get("market")
    if market not in TIMEZONES or frozen.get("outcome_labels_included") is not False:
        raise ValueError("Invalid frozen holdout market or label leakage")
    if len(frozen["signals"]) != frozen["eligible_count"]:
        raise ValueError("Frozen holdout candidate count mismatch")
    outcomes = json.loads(Path(outcome_file).read_text(encoding="utf-8"))
    if not isinstance(outcomes, list):
        raise ValueError("Evaluation labels must be an array")
    lookup = {}
    freeze_cutoff = _stamp(frozen["frozen_at_utc"])
    for label in outcomes:
        if not isinstance(label, dict):
            raise ValueError("Invalid outcome record")
        sec = label.get("security_id")
        if not isinstance(sec, str) or not sec or sec in lookup:
            raise ValueError("Duplicate or invalid outcome identity")
        if type(label.get("is_future_leader")) is not bool:
            raise ValueError("Boolean future-leader label required")
        if label.get("label_definition_id") != frozen["label_definition_id"]:
            raise ValueError("Outcome label definition does not match frozen protocol")
        mature = _stamp(label["mature_at"])
        known = _stamp(label["outcome_available_at"])
        if known < mature:
            raise ValueError("Outcome known before maturity")
        if mature <= freeze_cutoff or known <= freeze_cutoff:
            raise ValueError("Outcome was already mature or known before holdout freeze")
        if label["is_future_leader"]:
            onset = _stamp(label["leader_start_at"])
            if onset > mature:
                raise ValueError("Leader onset after maturity")
        lookup[sec] = label
    seen_ids=set()
    tp=fp=late=censored=0
    premature_negative=0
    lead_days=[]
    for signal in frozen["signals"]:
        sec = signal["security_id"]
        if sec in seen_ids or signal.get("model_version") != frozen["model_version"]:
            raise ValueError("Duplicate or mismatched candidate in freeze")
        seen_ids.add(sec)
        recorded = _stamp(signal["recorded_at_utc"])
        if recorded > _stamp(frozen["frozen_at_utc"]):
            raise ValueError("Signal registered after holdout was frozen")
        observation = _stamp(signal["observed_as_of"])
        if (recorded.astimezone(TIMEZONES[market]).date() -
                observation.astimezone(TIMEZONES[market]).date()).days > frozen["max_observation_lag_days"]:
            raise ValueError("Backfilled signal inserted into frozen holdout")
        label=lookup.get(sec)
        if label is None:
            censored+=1
            continue
        matured = _stamp(label["mature_at"])
        known = _stamp(label["outcome_available_at"])
        if known > cutoff or matured > cutoff:
            censored+=1
            continue
        if not label["is_future_leader"]:
            # A negative conclusion is only mature after the FULL frozen
            # forecast window. Early negative labels cannot be final FPs.
            # Preserve the recorded local clock, not only the date: a label
            # matured one minute before the pinned horizon is still censored.
            # Convert back to UTC to compare absolute instants across US DST.
            required_end = (recorded.astimezone(TIMEZONES[market])
                            + timedelta(days=frozen_horizon)).astimezone(timezone.utc)
            if matured < required_end:
                censored += 1
                premature_negative += 1
                continue
            fp+=1
            continue
        onset=_stamp(label["leader_start_at"])
        delta=(onset.astimezone(TIMEZONES[market]).date() -
               recorded.astimezone(TIMEZONES[market]).date()).days
        # Calendar-day difference alone counts an onset a minute AFTER
        # horizon expiry as an early hit. Enforce the frozen local clock too.
        positive_deadline = (recorded.astimezone(TIMEZONES[market])
                             + timedelta(days=frozen_horizon)).astimezone(timezone.utc)
        if 0 < delta <= horizon_days and recorded < onset <= positive_deadline:
            tp+=1
            lead_days.append(delta)
        else:
            late+=1
    known_count=tp+fp+late
    return {
        "status": STATUS,
        "frozen_manifest_sha256":frozen["content_sha256"],
        "frozen_at_utc":frozen["frozen_at_utc"],"evaluated_at_utc":cutoff.isoformat(),
        "market":market,"model_version":frozen["model_version"],
        "label_definition_id":frozen["label_definition_id"],
        "horizon_days":frozen_horizon,
        "eligible_candidates":len(seen_ids),
        "excluded_historical_backfills":frozen["excluded_historical_backfills"],
        "known_outcomes":known_count, "censored_outcomes":censored,
        "premature_negative_labels_censored":premature_negative,
        "coverage_fraction":round(known_count/len(seen_ids),6) if seen_ids else None,
        "true_early_discoveries":tp,"false_discoveries":fp,"late_or_post_onset":late,
        "precision_known_including_late":round(tp/known_count,6) if known_count else None,
        "conservative_precision_floor":round(tp/len(seen_ids),6) if seen_ids else None,
        "median_early_lead_days":median(lead_days) if lead_days else None,
        "recall_complete_universe":None,"financial_returns_certified":False,
        "historic_pit_certified":False,"independent_clock_attested":False,
        "warning":"Negative outcomes require maturity over the full frozen horizon. Data and labels require independent vendor and prospective PIT certification. No certified investing accuracy.",
    }
