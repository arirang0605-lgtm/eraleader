"""Track prospectively observed research WATCH persistence, weakness and re-entry.

Research-only. A security missing from a run is NOT weakening; only an
explicitly recorded false growth screen can establish an observation change.
Local timestamps and input sources are NOT independently PIT attested.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sqlite3

MARKET_ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
STATUS = "LOCAL_WATCH_TRANSITIONS_RESEARCH_ONLY_NOT_CERTIFIED"
PROVENANCE = "PROSPECTIVE_RESEARCH_ONLY_PIT_NOT_CERTIFIED"


def _stamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timezone-aware research observation timestamp required")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid research observation timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Timezone-aware research observation timestamp required")
    return moment.astimezone(timezone.utc)


def audit_watch_progression(
    ledger: Path, *, market: str, model_version: str,
    max_registration_lag_days: int = 3, sample_limit: int = 100,
) -> dict:
    if market not in MARKET_ZONES:
        raise ValueError("market must be KR/US")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("A pinned model_version is required")
    if (type(max_registration_lag_days) is not int or
            not 0 <= max_registration_lag_days <= 14):
        raise ValueError("Invalid registration lag limit")
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("Invalid audit sample_limit")
    if not Path(ledger).is_file():
        raise FileNotFoundError(f"Missing prospective research ledger: {ledger}")

    connection=sqlite3.connect(Path(ledger).resolve().as_uri()+"?mode=ro",uri=True)
    try:
        try:
            rows=connection.execute("""SELECT security_id,observed_as_of,
                recorded_at_utc,source_run_id,screen_hit,payload_hash,payload
                FROM research_screen_observations
                WHERE market=? AND model_version=?
                ORDER BY security_id,observed_as_of""",(market,model_version)).fetchall()
        except sqlite3.OperationalError as exc:
            raise ValueError("No complete-screen observations; replay cannot certify history") from exc
    finally:
        connection.close()
    transitions=[]
    backfills=0
    previous_by_security={}
    ever_hit=set()
    counted={"INITIAL_WATCH":0,"WATCH_PERSISTED":0,"SCREEN_WEAKENED":0,
             "SCREEN_STILL_WEAK":0,"SCREEN_REENTERED":0,"PRE_WATCH":0}
    prospective=0
    last_observed={}
    last_recorded={}
    for sec,seen,recorded,run_id,hit,digest,payload in rows:
        if not isinstance(sec,str) or not sec or type(hit) is not int or hit not in (0,1):
            raise ValueError("Malformed research screen row identity or hit")
        if not isinstance(payload,str) or sha256(payload.encode()).hexdigest()!=digest:
            raise ValueError("Research screen payload hash mismatch")
        try:
            basis=json.loads(payload)
        except (ValueError,TypeError) as exc:
            raise ValueError("Invalid research screen JSON") from exc
        encoded=json.dumps(basis,sort_keys=True,ensure_ascii=False,
                           separators=(",",":"),allow_nan=False)
        if not isinstance(basis,dict) or encoded!=payload:
            raise ValueError("Noncanonical research screen payload")
        company=basis.get("company")
        if (not isinstance(company,dict) or basis.get("market")!=market or
                basis.get("model_version")!=model_version or
                basis.get("source_run_id")!=run_id or
                basis.get("as_of")!=seen or company.get("security_id")!=sec or
                company.get("as_of")!=seen or company.get("market")!=market or
                company.get("research_growth_screen_hit") is not bool(hit) or
                company.get("research_screen_evaluated", True) is not True or
                company.get("state")!="WATCH" or company.get("full_score") is not None or
                company.get("verified_future_leader_candidate") is not False):
            raise ValueError("Research screen payload identity or status mismatch")
        observed=_stamp(seen)
        registration=_stamp(recorded)
        if observed>registration:
            raise ValueError("Future observation registered earlier than available")
        # Replaying an old historical source today cannot masquerade as a
        # genuinely prospective observation. Keep visible excluded count.
        local_observed=observed.astimezone(MARKET_ZONES[market]).date()
        local_registration=registration.astimezone(MARKET_ZONES[market]).date()
        lag=(local_registration-local_observed).days
        if lag<0 or lag>max_registration_lag_days:
            backfills+=1
            continue
        if sec in last_observed and observed <= last_observed[sec]:
            raise ValueError("Unordered prospective research decision dates")
        if sec in last_recorded and registration < last_recorded[sec]:
            raise ValueError("Prospective registration clock moved backwards")
        last_observed[sec]=observed
        last_recorded[sec]=registration
        was=previous_by_security.get(sec)
        if hit:
            tag=("INITIAL_WATCH" if sec not in ever_hit else
                 "WATCH_PERSISTED" if was else "SCREEN_REENTERED")
            ever_hit.add(sec)
        else:
            tag=("PRE_WATCH" if sec not in ever_hit else
                 "SCREEN_WEAKENED" if was else "SCREEN_STILL_WEAK")
        previous_by_security[sec]=bool(hit)
        counted[tag]+=1
        prospective+=1
        if len(transitions)<sample_limit:
            transitions.append({
                "security_id":sec, "observed_at":observed.isoformat(),
                "registered_at":registration.isoformat(),
                "transition":tag, "screen_hit":bool(hit),
                "registration_lag_days":lag,
            })
    return {
        "status": STATUS,
        "market":market,"model_version":model_version,
        "source_ledger_observations":len(rows),
        "eligible_prospective_observations":prospective,
        "excluded_retrospective_observations":backfills,
        "securities_with_eligible_observations":len(previous_by_security),
        "transition_counts":counted,
        "transition_event_sample":transitions,
        "sample_limit":sample_limit,
        "official_state_promotions":0,
        "pit_certified":False,
        "leader_prediction_accuracy_certified":False,
        "warning":("A missing security is not a negative research observation. "
                   "Explicit screening of both hits and nonhits is required. "
                   "Registration uses an unauthenticated local clock; no "
                   "exchange PIT, legal source, independent label or live alpha certification."),
    }
