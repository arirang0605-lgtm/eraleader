"""Research-only peer WATCH rotation hypotheses from prospectively recorded screens.

This does NOT designate a verified sector leader or successor. Explicit
two-screen weakening + a new peer's two-screen persistence is an early
watchlist *hypothesis*. Missing coverage never becomes a negative signal.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from .prospective import _canonical
from .watch_progression import _stamp, MARKET_ZONES

STATUS = "RESEARCH_PEER_WATCH_ROTATION_NOT_CERTIFIED"
HYPOTHESIS = "RESEARCH_PEER_WATCH_REPLACEMENT_HYPOTHESIS"
MAX_ROWS = 50000
WINDOW_DAYS = 30
MAX_LAG_DAYS = 3
MAX_PAIR_CHECKS = 100000


def _market_day_gap(start: datetime, end: datetime, zone) -> int:
    return (end.astimezone(zone).date() - start.astimezone(zone).date()).days


def _clock(value: datetime | None) -> datetime:
    moment = value if value is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("Rotation audit clock must be timezone-aware")
    return moment.astimezone(timezone.utc)


def audit_watch_rotation(
    ledger: Path, *, market: str, model_version: str,
    evaluated_at: str, clock: datetime | None = None, sample_limit: int = 100,
) -> dict:
    """Read-only as-of cohort audit; NEVER read retrospective outcome labels.

    Strictly require an incumbent's 2 explicit positive screens followed by
    2 explicit negatives, and a *new* same-industry peer with 2 positives
    first registered after the incumbent's initial weakness.
    """
    if market not in MARKET_ZONES:
        raise ValueError("Market must be KR or US")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned research model version is required")
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("sample_limit must be 1..1000")
    cutoff = _stamp(evaluated_at)
    if cutoff > _clock(clock):
        raise ValueError("Rotation evaluation cannot use future cutoff")
    source = Path(ledger)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Missing or symlinked prospective rotation ledger")
    uri = source.resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        try:
            rows = db.execute(
                """SELECT security_id, observed_as_of, recorded_at_utc,
                          source_run_id, screen_hit, payload_hash, payload
                   FROM research_screen_observations
                   WHERE market=? AND model_version=?
                   ORDER BY security_id, observed_as_of""",
                (market, model_version),
            ).fetchmany(MAX_ROWS + 1)
        except sqlite3.DatabaseError as exc:
            raise ValueError("Missing or corrupt prospective research observations") from exc
    finally:
        db.close()
    if len(rows) > MAX_ROWS:
        raise ValueError("Oversized prospective rotation sample")

    by_security: dict[str, list[dict]] = defaultdict(list)
    invalid_industry: set[str] = set()
    unassigned_industry: set[str] = set()
    excluded_future = excluded_backfill = 0
    total_eligible = 0
    market_zone = MARKET_ZONES[market]
    for sec, observed_at, registered_at, source_run, hit, digest, payload in rows:
        if (not isinstance(sec, str) or not sec.strip() or
                type(hit) is not int or hit not in (0, 1) or
                not isinstance(payload, str) or
                sha256(payload.encode("utf-8")).hexdigest() != digest):
            raise ValueError("Prospective observation payload hash or hit mismatch")
        try:
            obj = json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise ValueError("Malformed prospective rotation payload") from exc
        if not isinstance(obj, dict) or _canonical(obj) != payload:
            raise ValueError("Noncanonical prospective rotation payload")
        company = obj.get("company")
        if (not isinstance(company, dict) or
                obj.get("market") != market or
                obj.get("model_version") != model_version or
                obj.get("source_run_id") != source_run or
                obj.get("as_of") != observed_at or
                company.get("market") != market or
                company.get("security_id") != sec or
                company.get("as_of") != observed_at or
                company.get("state") != "WATCH" or
                company.get("full_score") is not None or
                company.get("verified_future_leader_candidate") is not False or
                company.get("research_screen_evaluated", True) is not True or
                company.get("research_growth_screen_hit") is not bool(hit)):
            raise ValueError("Prospective rotation company identity/status mismatch")
        observed = _stamp(observed_at)
        registered = _stamp(registered_at)
        if registered < observed:
            raise ValueError("Prospective observation registered before observation")
        if registered > cutoff:
            excluded_future += 1
            continue
        lag = (registered.astimezone(market_zone).date() -
               observed.astimezone(market_zone).date()).days
        if lag < 0 or lag > MAX_LAG_DAYS:
            excluded_backfill += 1
            continue
        industry = company.get("industry_id")
        if not isinstance(industry, str) or not industry.strip():
            unassigned_industry.add(sec)
            continue
        by_security[sec].append({
            "observed": observed, "registered": registered,
            "hit": bool(hit), "industry_id": industry,
        })
        total_eligible += 1

    # Industry membership is self-declared. If a candidate changes industry
    # during this audit horizon, there is no PIT sector-reclassification proof:
    # exclude rather than retrospectively assigning either sector.
    industry_groups: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for sec, history in by_security.items():
        if sec in unassigned_industry:
            continue
        history.sort(key=lambda event: (event["observed"], event["registered"]))
        if len({event["industry_id"] for event in history}) != 1:
            invalid_industry.add(sec)
            continue
        if any(later["observed"] <= earlier["observed"] or
               later["registered"] < earlier["registered"]
               for earlier, later in zip(history, history[1:])):
            raise ValueError("Prospective screen observation chronology reversed")
        industry_groups[history[-1]["industry_id"]][sec] = history

    hypotheses = []
    for industry, securities in industry_groups.items():
        weakenings = []
        newcomers = []
        for sec, observations in securities.items():
            hits = [event["hit"] for event in observations]
            if not hits:
                continue
            if len(observations) >= 4 and hits[-1] is False and hits[-2] is False:
                start = len(hits) - 1
                while start > 0 and hits[start-1] is False:
                    start -= 1
                if (len(hits) - start >= 2 and start >= 2 and
                        hits[start-1] is True and hits[start-2] is True and
                        observations[start-2]["registered"] <
                        observations[start-1]["registered"] <
                        observations[start]["registered"] <
                        observations[start+1]["registered"] and
                        _market_day_gap(observations[start-2]["registered"],
                                        observations[start-1]["registered"],market_zone)<=WINDOW_DAYS and
                        _market_day_gap(observations[start-1]["registered"],
                                        observations[start]["registered"],market_zone)<=WINDOW_DAYS):
                    weakenings.append((sec, observations[start]["registered"],
                                       observations[start+1]["registered"]))
            first_hit = next((index for index, hit in enumerate(hits) if hit), None)
            if (first_hit is not None and len(observations) >= first_hit + 2 and
                    observations[first_hit]["hit"] is True and
                    observations[first_hit+1]["hit"] is True and
                    observations[first_hit]["registered"] <
                    observations[first_hit+1]["registered"] and
                    all(hits[first_hit:]) and
                    hits[-1] is True and hits[-2] is True):
                newcomers.append((sec, observations[first_hit]["registered"],
                                  observations[first_hit+1]["registered"],
                                  observations[-1]["registered"]))

        if len(weakenings)*len(newcomers)>MAX_PAIR_CHECKS:
            raise ValueError("Rotation pair search exceeds safe comparison budget")
        for previous_sec, weakened_at, confirmed_at in weakenings:
            for candidate_sec, first_at, second_at, last_at in newcomers:
                if (previous_sec == candidate_sec or first_at <= weakened_at or
                        second_at < confirmed_at or
                        _market_day_gap(weakened_at,last_at,market_zone)>WINDOW_DAYS or
                        _market_day_gap(last_at,cutoff,market_zone)>WINDOW_DAYS):
                    continue
                hypotheses.append({
                    "kind": HYPOTHESIS, "industry_id": industry,
                    "incumbent_security_id": previous_sec,
                    "contender_security_id": candidate_sec,
                    "first_explicit_weakening_at_utc": weakened_at.isoformat(),
                    "second_explicit_weakening_at_utc": confirmed_at.isoformat(),
                    "contender_first_watch_at_utc": first_at.isoformat(),
                    "contender_second_watch_at_utc": second_at.isoformat(),
                    "incumbent_is_certified_leader": False,
                    "contender_is_certified_leader": False,
                })

    hypotheses.sort(key=lambda x: (
        x["first_explicit_weakening_at_utc"], x["industry_id"],
        x["incumbent_security_id"], x["contender_security_id"],
    ))
    return {
        "status": STATUS, "market": market, "model_version": model_version,
        "evaluated_at_utc": cutoff.isoformat(),
        "source_observation_count": len(rows),
        "eligible_observation_count": total_eligible,
        "excluded_future_registered_count": excluded_future,
        "excluded_hindsight_or_backfill_count": excluded_backfill,
        "excluded_unassigned_industry_securities": len(unassigned_industry),
        "excluded_industry_reclassified_securities": len(invalid_industry),
        "rotation_hypothesis_count": len(hypotheses),
        "hypothesis_sample": hypotheses[:sample_limit],
        "rotation_window_calendar_days": WINDOW_DAYS,
        "official_leader_replacements": 0,
        "historic_pit_certified": False,
        "peer_universe_coverage_certified": False,
        "industry_membership_pit_certified": False,
        "actual_prediction_accuracy_certified": False,
        "warning": (
            "WATCH-screen transitions are research hypotheses only. Neither "
            "the candidate nor the prior WATCH is an authenticated era leader. "
            "Absence of a security does not imply weakness. Local clock, "
            "industry identity, issuer PIT and future outcome labels are unverified."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local prospective peer rotation hypotheses")
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--market", required=True, choices=("KR", "US"))
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_watch_rotation(
            args.ledger, market=args.market, model_version=args.model_version,
            evaluated_at=args.evaluated_at,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(args.out, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        parser.exit(2, f"EraLeader watch rotation error: {exc}\n")
    print(json.dumps({
        "status": report["status"], "rotation_hypothesis_count": report["rotation_hypothesis_count"],
        "official_leader_replacements": 0, "path": str(args.out),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
