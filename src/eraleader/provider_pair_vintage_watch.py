"""Read-only bridge: two independently pinned atomic PIT vintages -> observed WATCH
weakening and *existing* prospective peer-rotation hypotheses.

Missing/removed source records, revised earlier published facts, or changing
industry classifications never silently become a negative screen. This
remains local, claimed-provider research; no official issuer/PIT certification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3

from .frozen_holdout import _stamp
from .provider_pair_asof_seal import _receipt
from .provider_pair_candidate_bridge import (
    resolve_atomic_candidate_pair, assert_atomic_candidate_pair_unchanged,
)
from .provider_dual_source_audit import (
    _full_receipt_source, _membership_asof, _latest, _events, ZONES,
)
from .prospective import _canonical
from .watch_rotation import audit_watch_rotation

STATUS = "LOCAL_PINNED_PAIR_VINTAGE_WATCH_EVIDENCE_RESEARCH_ONLY"
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE = 8_000_000
MAX_SECURITIES = 50_000
MAX_ROTATION_SAMPLE = 1000


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate research run JSON key")
        obj[key] = value
    return obj


def _run(file: Path, *, market: str, pinned_sha: str):
    file = Path(file)
    if (file.is_symlink() or file.parent.is_symlink() or
            not file.is_file() or not 0 < file.stat().st_size <= MAX_FILE):
        raise ValueError("Missing, linked or oversized pinned research run")
    doc = json.loads(file.read_bytes(), object_pairs_hook=_unique)
    if not isinstance(doc, dict) or doc.get("market") != market:
        raise ValueError("Pinned research run market mismatch")
    gate = doc.get("provider_pair_gate")
    if (not isinstance(gate, dict) or
            gate.get("atomic_first_pair_receipt_sha256") != pinned_sha or
            gate.get("atomic_first_pair_research_only") is not True or
            gate.get("research_watch_allowed") is not True or
            gate.get("official_candidate_promotion_allowed") is not False or
            gate.get("original_first_ingest_pins_locally_consistent") is not True or
            doc.get("pit_certified") is not False or
            doc.get("confirmed_leaders") != 0 or
            doc.get("potential_leaders") != 0 or
            not isinstance(gate.get("source_pair_digest_sha256"), str) or
            HEX.fullmatch(gate["source_pair_digest_sha256"]) is None):
        raise ValueError("Research run lacks accepted immutable atomic-pair WATCH gate")
    if (not isinstance(doc.get("run_id"), str) or
            not isinstance(doc.get("version"), str) or not doc["version"] or
            not isinstance(doc.get("company_rows"), list) or
            len(doc["company_rows"]) > MAX_SECURITIES or
            not isinstance(doc.get("offline_provenance"), list)):
        raise ValueError("Malformed pinned research run")
    cutoff = _stamp(doc.get("as_of"))
    # Recompute the existing offline-integrated run-id AND its independently
    # first-pinned pair binding; no new historical score or run is generated.
    basis = {field: doc[field] for field in (
        "version", "as_of", "market", "company_rows",
        "price_run_id", "offline_provenance")}
    original = sha256(json.dumps(
        basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    stamped = _canonical({
        "original_run_id": original,
        "local_pair_digest": gate["source_pair_digest_sha256"],
        "atomic_first_pair_receipt_sha256": pinned_sha,
    })
    expected = sha256(stamped.encode()).hexdigest()[:20]
    if doc["run_id"] != expected:
        raise ValueError("Immutable pinned WATCH run-id/content mismatch")
    companies = {}
    for row in doc["company_rows"]:
        if (not isinstance(row, dict) or
                not isinstance(row.get("security_id"), str) or
                not row["security_id"] or
                row["security_id"] in companies or
                row.get("market") != market or row.get("as_of") != doc["as_of"] or
                row.get("state") != "WATCH" or
                row.get("full_score") is not None or
                row.get("verified_future_leader_candidate") is not False or
                type(row.get("research_growth_screen_hit")) is not bool or
                type(row.get("research_screen_evaluated")) is not bool):
            raise ValueError("Unverified or duplicated WATCH research company")
        companies[row["security_id"]] = row
    return doc, cutoff, companies


def _observations(db: sqlite3.Connection, doc: dict, rows: dict, *, cutoff: datetime):
    try:
        entries = db.execute(
            """SELECT security_id, observed_as_of, recorded_at_utc,
                      source_run_id, screen_hit, payload_hash, payload
               FROM research_screen_observations
               WHERE market=? AND model_version=? AND source_run_id=?""",
            (doc["market"], doc["version"], doc["run_id"])
        ).fetchmany(MAX_SECURITIES + 1)
    except sqlite3.DatabaseError as exc:
        raise ValueError("Missing prospective observation table") from exc
    if len(entries) > MAX_SECURITIES:
        raise ValueError("Oversized prospective WATCH observations")
    expected = {sec for sec, row in rows.items()
                if row["research_screen_evaluated"]}
    if len(entries) != len(expected):
        raise ValueError("Missing/extra immutable prospective screen observations")
    verified = {}
    lagged = 0
    zone = ZONES[doc["market"]]
    for sec, asof, recorded, rid, hit, digest, payload in entries:
        if (sec not in expected or sec in verified or
                rid != doc["run_id"] or
                type(hit) is not int or hit not in (0, 1) or
                not isinstance(digest, str) or
                not isinstance(payload, str) or
                sha256(payload.encode()).hexdigest() != digest):
            raise ValueError("Prospective WATCH row missing or mutated")
        recorded_dt = _stamp(recorded)
        if (_stamp(asof) != _stamp(doc["as_of"]) or
                recorded_dt < _stamp(asof) or recorded_dt > cutoff or
                bool(hit) is not rows[sec]["research_growth_screen_hit"]):
            raise ValueError("Future/backdated or inconsistent paired WATCH row")
        expected_payload = _canonical({
            "source_run_id": doc["run_id"], "market": doc["market"],
            "as_of": doc["as_of"], "model_version": doc["version"],
            "company": rows[sec],
            "provenances": doc["offline_provenance"],
        })
        if payload != expected_payload:
            raise ValueError("Registered WATCH was not generated by pinned research run")
        days = (recorded_dt.astimezone(zone).date() -
                _stamp(asof).astimezone(zone).date()).days
        if days < 0 or days > 3:
            lagged += 1
        else:
            verified[sec] = recorded_dt
    return verified, lagged


def _facts(source: dict, kind: str):
    identity = {
        "fundamentals": ("security_id", "metric", "period_end"),
        "industry": ("industry_id", "metric", "period_end"),
    }[kind]
    return {
        key: (row["value"], row["unit"])
        for key, row in _latest(source[kind], identity).items()
    }


def _membership_active(source: dict, day: str):
    members = _membership_asof(source["membership"], day)
    actions = _latest(source["actions"], ("security_id", "action_id"))
    terminal = {row["security_id"] for row in actions.values()
                if row["action_type"] in ("delist", "merger")
                and row["effective_on"] <= day}
    active = {
        sec: row for sec, row in members.items()
        if (row["valid_to"] is None or row["valid_to"] > day)
        and sec not in terminal
    }
    return members, active, terminal


def _changed_domain(previous: dict, later: dict, *, old_day: str, new_day: str):
    summary = {}
    for kind in ("fundamentals", "industry"):
        old = _facts(previous, kind)
        new = _facts(later, kind)
        summary[kind] = {
            "newly_available_keys": len(new.keys() - old.keys()),
            "prior_known_keys_absent_in_new_vintage": len(old.keys() - new.keys()),
            "revised_prior_period_keys": sum(old[k] != new[k] for k in old.keys() & new.keys()),
        }
    def reject_ambiguous(*_):
        raise ValueError("Ambiguous corporate-action semantic key in source vintage")
    old_actions = {
        key: (row.get("ratio"), row.get("cash_amount"))
        for key, row in _events(previous["actions"], reject_ambiguous).items()
    }
    new_actions = {
        key: (row.get("ratio"), row.get("cash_amount"))
        for key, row in _events(later["actions"], reject_ambiguous).items()
    }
    summary["actions"] = {
        "new_events": len(new_actions.keys() - old_actions.keys()),
        "previous_events_absent": len(old_actions.keys() - new_actions.keys()),
        "revised_existing_event_terms": sum(
            old_actions[k] != new_actions[k]
            for k in old_actions.keys() & new_actions.keys()),
    }
    old_members = _membership_asof(previous["membership"], old_day)
    new_members = _membership_asof(later["membership"], new_day)
    summary["membership"] = {
        "new_claimed_security_ids": len(new_members.keys() - old_members.keys()),
        "previous_security_ids_absent": len(old_members.keys() - new_members.keys()),
        "changed_claimed_fields_or_membership_interval": sum(
            any(old_members[k].get(field) != new_members[k].get(field)
                for field in ("ticker", "industry_id", "valid_from", "valid_to"))
            for k in old_members.keys() & new_members.keys()),
    }
    return summary


def audit_pinned_pair_vintage_watch(
    old_root: Path, old_sha: str, new_root: Path, new_sha: str,
    old_run_file: Path, new_run_file: Path, prospective_ledger: Path, *,
    market: str, evaluated_at: str, clock: datetime | None = None,
) -> dict:
    """Correlate *first-recorded* PIT vintages and actual recorded screens.

    A revision in source data does not change the previous run or create an
    inferred negative WATCH. Existing rotation requires independently observed
    two positives, then two explicit negatives and a contender's two hits.
    """
    now = clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware actual analysis clock is required")
    now = now.astimezone(timezone.utc)
    cutoff = _stamp(evaluated_at)
    if market not in ZONES or cutoff > now:
        raise ValueError("Market invalid or future evaluation forbidden")
    old = resolve_atomic_candidate_pair(
        old_root, old_sha, market=market, decision_at=_run(
            old_run_file, market=market, pinned_sha=old_sha)[0]["as_of"], clock=now)
    new = resolve_atomic_candidate_pair(
        new_root, new_sha, market=market, decision_at=_run(
            new_run_file, market=market, pinned_sha=new_sha)[0]["as_of"], clock=now)
    old_doc, old_at, old_rows = _run(old_run_file, market=market, pinned_sha=old_sha)
    new_doc, new_at, new_rows = _run(new_run_file, market=market, pinned_sha=new_sha)
    if (Path(old_root).resolve() == Path(new_root).resolve() or
            old_sha == new_sha or old_at >= new_at or new_at > cutoff or
            old_doc["version"] != new_doc["version"] or
            old_doc["run_id"] == new_doc["run_id"] or
            Path(old_run_file).resolve() == Path(new_run_file).resolve()):
        raise ValueError("Pinned provider vintages must be distinct and chronological")
    _, _, old_registered, _ = _receipt(old_root, old_sha)
    _, _, new_registered, _ = _receipt(new_root, new_sha)
    if not (old_registered < new_registered and
            old_registered <= old_at and new_registered <= new_at):
        raise ValueError("New claimed provider pair is not prospectively first-ingested")
    old_sources = _full_receipt_source(old.pair[0], old.pair[1], old_at)
    new_sources = _full_receipt_source(new.pair[0], new.pair[1], new_at)
    old_day = old_at.astimezone(ZONES[market]).date().isoformat()
    new_day = new_at.astimezone(ZONES[market]).date().isoformat()
    _, old_active, _ = _membership_active(old_sources, old_day)
    new_members, new_active, new_terminal = _membership_active(new_sources, new_day)
    missing = set(old_active) - set(new_members)
    explicit_exits = {sec for sec in old_active
                      if sec in new_members and sec not in new_active and
                      (sec in new_terminal or
                       (new_members[sec]["valid_to"] is not None and
                        new_members[sec]["valid_to"] <= new_day))}
    reclassified = {sec for sec in set(old_active) & set(new_active)
                    if old_active[sec]["industry_id"] != new_active[sec]["industry_id"]}
    ledger = Path(prospective_ledger)
    if ledger.is_symlink() or not ledger.is_file():
        raise ValueError("Missing original read-only prospective WATCH ledger")
    db = sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        old_observed, old_lag = _observations(db, old_doc, old_rows, cutoff=cutoff)
        new_observed, new_lag = _observations(db, new_doc, new_rows, cutoff=cutoff)
    finally:
        db.close()
    weakening, emerging = {}, {}
    persistence = unhit = 0
    deferred = excluded = retrospective = 0
    for sec in sorted(set(old_rows) | set(new_rows)):
        if sec not in old_observed or sec not in new_observed:
            deferred += 1
            continue
        # An old-date screen reprocessed AFTER the new source was ingested is
        # hindsight, even if its old PIT bundle itself is internally sound.
        # The new observation must also truly follow new first-ingest.
        if (old_observed[sec] >= new_registered or
                new_observed[sec] < new_registered):
            retrospective += 1
            continue
        if (sec not in old_active or sec not in new_active or
                sec in reclassified or
                old_rows[sec].get("industry_id") != old_active[sec]["industry_id"] or
                new_rows[sec].get("industry_id") != new_active[sec]["industry_id"] or
                new_observed[sec] <= old_observed[sec]):
            excluded += 1
            continue
        was = old_rows[sec]["research_growth_screen_hit"]
        current = new_rows[sec]["research_growth_screen_hit"]
        if was and not current:
            weakening[sec] = new_observed[sec]
        elif not was and current:
            emerging[sec] = new_observed[sec]
        elif was and current:
            persistence += 1
        else:
            unhit += 1
    rotation = audit_watch_rotation(
        ledger, market=market, model_version=old_doc["version"],
        evaluated_at=cutoff.isoformat(), clock=now,
        sample_limit=MAX_ROTATION_SAMPLE)
    truncated = (rotation["rotation_hypothesis_count"] >
                 len(rotation["hypothesis_sample"]))
    linked = None if truncated else sum(
        event["incumbent_security_id"] in weakening and
        event["contender_security_id"] in emerging and
        event["second_explicit_weakening_at_utc"] ==
            weakening.get(event["incumbent_security_id"], now).isoformat() and
        event["contender_second_watch_at_utc"] ==
            emerging.get(event["contender_security_id"], now).isoformat() and
        old_active[event["incumbent_security_id"]]["industry_id"] ==
            new_active[event["contender_security_id"]]["industry_id"]
        for event in rotation["hypothesis_sample"]
    )
    assert_atomic_candidate_pair_unchanged(
        old, old_root, decision_at=old_doc["as_of"], clock=now)
    assert_atomic_candidate_pair_unchanged(
        new, new_root, decision_at=new_doc["as_of"], clock=now)
    return {
        "status": STATUS, "market": market, "model_version": old_doc["version"],
        "evaluated_at_utc": cutoff.isoformat(),
        "old_first_pair_sha256": old_sha,
        "new_first_pair_sha256": new_sha,
        "old_first_registered_at_utc": old_registered.isoformat(),
        "new_first_registered_at_utc": new_registered.isoformat(),
        "old_decision_at_utc": old_at.isoformat(),
        "new_decision_at_utc": new_at.isoformat(),
        "old_active_declared_issuer_count": len(old_active),
        "new_active_declared_issuer_count": len(new_active),
        "new_declared_active_members": len(set(new_active) - set(old_active)),
        "old_active_missing_from_new_vintage_not_a_weakness": len(missing),
        "old_active_with_explicit_new_vintage_exit_not_a_screen": len(explicit_exits),
        "reclassified_industry_excluded": len(reclassified),
        "source_delta_counts": _changed_domain(
            old_sources, new_sources, old_day=old_day, new_day=new_day),
        "paired_observations_late_or_backfilled": old_lag + new_lag,
        "paired_screens_not_comparable_or_deferred": deferred,
        "paired_old_screens_registered_after_new_vintage_censored": retrospective,
        "paired_screens_without_safe_identity_or_chronology": excluded,
        "explicit_one_screen_weakening_only": len(weakening),
        "explicit_one_screen_emerging_only": len(emerging),
        "explicit_screen_persistence": persistence,
        "explicit_screen_nonhits": unhit,
        "existing_rotation_research_hypothesis_count":
            rotation["rotation_hypothesis_count"],
        "pair_linked_existing_rotation_hypotheses": linked,
        "rotation_sample_truncated": truncated,
        "official_leader_replacements": 0,
        "official_leader_promotions": 0,
        "historic_pit_certified": False,
        "first_publication_independently_attested": False,
        "actual_prediction_accuracy_certified": False,
        "external_api_calls": 0,
        "messages_sent": 0,
        "note": (
            "Only explicitly observed, timely registered WATCH screens are compared. "
            "Missing issuer/period is not a weakening; a revision is not a negative screen. "
            "The existing 2+2 peer rotation evidence remains a hypothesis. "
            "Local first SHA and clock do not independently authenticate publishers "
            "or historical PIT; no official leader or performance certification."
        ),
    }
