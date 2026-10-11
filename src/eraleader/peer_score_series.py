"""Append-only prospective peer score events linked to explicit WATCH screens.

Local OS timestamps, local feature bytes and declared issuer/industry groups are
not independently PIT authenticated. Never uses realized labels or trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .prospective import _canonical
from .rank_score_ledger import _data, SAFE_NAME, _now
from .rank_score_pipeline import compute_research_score, formula_provenance
from .watch_progression import _stamp, MARKET_ZONES
from .watch_rotation import audit_watch_rotation

STATUS = "LOCAL_PROSPECTIVE_PEER_SCORES_RESEARCH_ONLY"
AUDIT_STATUS = "LOCAL_PEER_SCORE_ADVANTAGE_HYPOTHESES_NOT_CERTIFIED"
DOC_SCHEMA = "eraleader.rank_feature_document.v1"
CREATE = """CREATE TABLE IF NOT EXISTS peer_score_observations (
    market TEXT NOT NULL, model_version TEXT NOT NULL,
    security_id TEXT NOT NULL, observed_at_utc TEXT NOT NULL,
    evidence_hash TEXT NOT NULL, payload TEXT NOT NULL,
    PRIMARY KEY (market, model_version, security_id, observed_at_utc)
)"""
SCORE_LIMIT = 1000
REGISTRATION_DELAY_SECONDS = 3600
MIN_SCORE_ADVANTAGE = 5.0


def _unique_json_keys(pairs: list[tuple[str,object]]) -> dict:
    doc = {}
    for name, value in pairs:
        if name in doc:
            raise ValueError("Duplicate source feature JSON field")
        doc[name] = value
    return doc


def _score_evidence(path: Path, *, market: str, model_version: str, now: datetime) -> dict:
    """Check exact pinned and complete four-factor local evidence bytes."""
    raw = _data(path)
    try:
        document = json.loads(raw, object_pairs_hook=_unique_json_keys)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Invalid prospective feature JSON") from exc
    if (not isinstance(document, dict) or
            set(document) != {"schema", "market", "model_version", "security_id",
                              "available_at", "features"} or
            document.get("schema") != DOC_SCHEMA or
            document.get("market") != market or
            document.get("model_version") != model_version or
            not isinstance(document.get("security_id"), str) or
            not document["security_id"].strip()):
        raise ValueError("Prospective feature schema, issuer, model or market mismatch")
    available = _stamp(document["available_at"])
    if available > now:
        raise ValueError("Future feature availability cannot enter peer score")
    return {
        "security_id": document["security_id"],
        "score": compute_research_score(document["features"]),
        "feature_file": path.name,
        "feature_sha256": sha256(raw).hexdigest(),
        "feature_available_at_utc": available.isoformat(),
    }


def _open_readonly(path: Path, *, purpose: str) -> sqlite3.Connection:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked " + purpose)
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def _screen_source(connection: sqlite3.Connection, *, market: str,
                   model_version: str, security_id: str,
                   now: datetime) -> dict:
    try:
        rows = connection.execute(
            """SELECT observed_as_of, recorded_at_utc, screen_hit, source_run_id,
                      payload_hash, payload
               FROM research_screen_observations
               WHERE market=? AND model_version=? AND security_id=?""",
            (market, model_version, security_id),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Missing original WATCH observations") from exc
    relevant = []
    zone = MARKET_ZONES[market]
    for observed, registered, screen_hit, run, digest, text in rows:
        observation = _stamp(observed)
        recorded = _stamp(registered)
        if recorded > now or observation > now:
            continue
        if observation.astimezone(zone).date() != now.astimezone(zone).date():
            continue
        if (recorded > now or recorded < observation or
                (now-recorded).total_seconds() > REGISTRATION_DELAY_SECONDS):
            continue
        relevant.append((observation, recorded, screen_hit, run, digest, text, observed))
    if len(relevant) != 1:
        raise ValueError("Exactly one current locally recorded WATCH observation required")
    observed, registered, hit, run, digest, text, raw_observed = relevant[0]
    if (type(hit) is not int or hit not in (0, 1) or
            not isinstance(text, str) or
            sha256(text.encode("utf-8")).hexdigest() != digest):
        raise ValueError("WATCH screen status or payload SHA corrupted")
    try:
        body = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError("Malformed original WATCH score screen") from exc
    if not isinstance(body, dict) or _canonical(body) != text:
        raise ValueError("Noncanonical original WATCH score screen")
    company = body.get("company")
    if (not isinstance(company, dict) or
            body.get("market") != market or body.get("model_version") != model_version or
            body.get("source_run_id") != run or body.get("as_of") != raw_observed or
            company.get("security_id") != security_id or company.get("market") != market or
            company.get("as_of") != raw_observed or company.get("state") != "WATCH" or
            company.get("full_score") is not None or
            company.get("verified_future_leader_candidate") is not False or
            company.get("research_screen_evaluated", True) is not True or
            company.get("research_growth_screen_hit") is not bool(hit)):
        raise ValueError("Original WATCH score screen identity/status mismatch")
    industry = company.get("industry_id")
    if not isinstance(industry, str) or not industry.strip():
        raise ValueError("Unknown peer industry cannot establish score history")
    return {
        "screen_observed_at_utc": observed.isoformat(),
        "screen_recorded_at_utc": registered.isoformat(),
        "screen_payload_sha256": digest,
        "screen_hit": bool(hit),
        "industry_id": industry,
    }


def record_peer_score_series(
    series_db: Path, watch_db: Path, feature_dir: Path, *,
    market: str, model_version: str, clock: datetime | None = None,
) -> dict:
    """Compute from current files and register once per screen observation.

    Production callers have no clock argument in CLI; injected times are for
    deterministic unit tests. First-write timestamps may never be restated.
    """
    if market not in MARKET_ZONES or not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned market and model_version required")
    now = _now(clock)
    feature_root = Path(feature_dir)
    if feature_root.is_symlink() or not feature_root.is_dir():
        raise ValueError("Missing or unsafe peer-score feature root")
    local_session = now.astimezone(MARKET_ZONES[market]).date().isoformat()
    folder = feature_root / local_session
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Missing or symlinked current market-day feature batch")
    paths = sorted(folder.glob("*.json"))
    if not 1 <= len(paths) <= SCORE_LIMIT:
        raise ValueError("Require 1..1000 current prospective feature documents")
    seen = set()
    batch = []
    watch = _open_readonly(Path(watch_db), purpose="WATCH ledger")
    try:
        for file in paths:
            if file.is_symlink() or not SAFE_NAME.fullmatch(file.name):
                raise ValueError("Unsafe peer score document name")
            row = _score_evidence(file, market=market, model_version=model_version, now=now)
            row["feature_file"] = local_session + "/" + file.name
            sec = row["security_id"]
            if sec in seen:
                raise ValueError("Duplicate security in peer-score registration batch")
            seen.add(sec)
            proof = _screen_source(watch, market=market, model_version=model_version,
                                   security_id=sec, now=now)
            # A feature released after the observation is not credited to
            # that observation: its score is only known when written NOW.
            event = {
                "market": market, "model_version": model_version,
                "security_id": sec, "score": row["score"],
                "feature_file": row["feature_file"],
                "feature_sha256": row["feature_sha256"],
                "feature_available_at_utc": row["feature_available_at_utc"],
                "score_recorded_at_utc": now.isoformat(),
                **proof,
                "computation_provenance": formula_provenance(),
            }
            batch.append(event)
    finally:
        watch.close()
    path = Path(series_db)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Unsafe peer score history ledger path")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    inserted = repeated = 0
    try:
        connection.execute(CREATE)
        connection.commit()
        with connection:
            for event in batch:
                identity = (market, model_version, event["security_id"],
                            event["screen_observed_at_utc"])
                existing = connection.execute(
                    """SELECT evidence_hash, payload FROM peer_score_observations
                       WHERE market=? AND model_version=? AND security_id=?
                         AND observed_at_utc=?""", identity,
                ).fetchone()
                if existing:
                    old_hash, encoded = existing
                    old = json.loads(encoded)
                    if _canonical(old) != encoded or sha256(encoded.encode()).hexdigest() != old_hash:
                        raise ValueError("Immutable peer score event checksum corrupted")
                    candidate = {k: v for k, v in event.items() if k != "score_recorded_at_utc"}
                    before = {k: v for k, v in old.items() if k != "score_recorded_at_utc"}
                    if candidate != before:
                        raise ValueError("Existing peer score screen cannot be rewritten")
                    repeated += 1
                    continue
                encoded = _canonical(event)
                connection.execute(
                    """INSERT INTO peer_score_observations(
                         market,model_version,security_id,observed_at_utc,
                         evidence_hash,payload) VALUES (?,?,?,?,?,?)""",
                    (*identity, sha256(encoded.encode()).hexdigest(), encoded),
                )
                inserted += 1
    finally:
        connection.close()
    return {
        "status": STATUS, "market": market, "model_version": model_version,
        "new_score_events": inserted, "unchanged_score_events": repeated,
        "score_registered_at_utc": now.isoformat(),
        "scoring_formula_sha256": formula_provenance()["formula_sha256"],
        "issuer_and_industry_pit_certified": False,
        "real_leader_prediction_certified": False,
        "official_leader_replacements": 0,
    }


def audit_peer_score_advantage(
    watch_db: Path, series_db: Path, feature_dir: Path, *,
    market: str, model_version: str, evaluated_at: str,
    clock: datetime | None = None, sample_limit: int = 100,
) -> dict:
    """Read-only reconfirm two peer score advantages behind a WATCH rotation.

    Score differences can only corroborate a prospective research hypothesis;
    they cannot promote either security to official leader status.
    """
    if type(sample_limit) is not int or not 1 <= sample_limit <= 1000:
        raise ValueError("Invalid peer score audit sample limit")
    now = _now(clock)
    cutoff = _stamp(evaluated_at)
    if cutoff > now:
        raise ValueError("Future peer-score evaluation is forbidden")
    base = Path(feature_dir)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Missing or symlinked archived peer feature root")
    rotation = audit_watch_rotation(
        Path(watch_db), market=market, model_version=model_version,
        evaluated_at=evaluated_at, clock=now, sample_limit=1000,
    )
    if rotation["rotation_hypothesis_count"] != len(rotation["hypothesis_sample"]):
        raise ValueError("Cannot silently truncate peer rotation hypotheses")
    watch = _open_readonly(Path(watch_db), purpose="WATCH ledger")
    series = _open_readonly(Path(series_db), purpose="peer score history")
    try:
        try:
            screen_rows = watch.execute(
                """SELECT security_id, observed_as_of, recorded_at_utc,
                          screen_hit, payload_hash, payload
                   FROM research_screen_observations
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
            score_rows = series.execute(
                """SELECT security_id, observed_at_utc, evidence_hash, payload
                   FROM peer_score_observations
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Broken WATCH or peer-score schema") from exc
    finally:
        watch.close()
        series.close()
    if len(screen_rows) > 50000 or len(score_rows) > 50000:
        raise ValueError("Oversized peer score audit evidence")
    screen_index = {}
    for sec, observed, recorded, hit, digest, encoded in screen_rows:
        key = (sec, _stamp(observed).isoformat())
        if key in screen_index:
            raise ValueError("Duplicate original WATCH observation key")
        # watch_rotation already verified every canonical signal, but the
        # score witness must also match the *actual* screen's source hash.
        screen_index[key] = (_stamp(recorded).isoformat(), bool(hit), digest,
                             json.loads(encoded)["company"].get("industry_id"))
    zone = MARKET_ZONES[market]
    score_days: dict[str, dict[str, list[dict]]] = {}
    visible_events=0
    for sec, observed, digest, encoded in score_rows:
        try:
            item = json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid serialized peer score event") from exc
        if (not isinstance(item, dict) or _canonical(item) != encoded or
                sha256(encoded.encode()).hexdigest() != digest or
                item.get("market") != market or
                item.get("model_version") != model_version or
                item.get("security_id") != sec or
                item.get("screen_observed_at_utc") != observed or
                item.get("computation_provenance") != formula_provenance()):
            raise ValueError("Peer score event canonical/identity/formula mismatch")
        written = _stamp(item["score_recorded_at_utc"])
        # An as-of audit must not import scores that were written only later.
        # Their canonical SQLite row can exist without rewriting the past.
        if written > cutoff:
            continue
        witness = screen_index.get((sec, observed))
        if (witness is None or item.get("screen_recorded_at_utc") != witness[0] or
                item.get("screen_hit") is not witness[1] or
                item.get("screen_payload_sha256") != witness[2] or
                item.get("industry_id") != witness[3]):
            raise ValueError("Peer score event does not match original WATCH source")
        written = _stamp(item["score_recorded_at_utc"])
        screen_recorded = _stamp(witness[0])
        available = _stamp(item["feature_available_at_utc"])
        if (not screen_recorded <= written <= cutoff or available > written or
                (written-screen_recorded).total_seconds() > REGISTRATION_DELAY_SECONDS):
            raise ValueError("Peer score chronology contradicts screen registration")
        parts = item.get("feature_file")
        if not isinstance(parts, str) or len(parts.split("/")) != 2:
            raise ValueError("Unsafe archived peer feature path")
        session_folder, filename = parts.split("/")
        if (session_folder != written.astimezone(zone).date().isoformat() or
                not SAFE_NAME.fullmatch(filename) or filename.startswith(".")):
            raise ValueError("Peer feature file changed its market-local session")
        dirpath = base / session_folder
        file = dirpath / filename
        if dirpath.is_symlink() or file.is_symlink() or not file.is_file():
            raise ValueError("Missing or symlinked archived peer feature")
        fresh = _score_evidence(file, market=market, model_version=model_version,
                                now=written)
        if (fresh["security_id"] != sec or fresh["score"] != item["score"] or
                fresh["feature_sha256"] != item["feature_sha256"] or
                fresh["feature_available_at_utc"] != item["feature_available_at_utc"]):
            raise ValueError("Archived peer score features or formula were revised")
        local_day = _stamp(observed).astimezone(zone).date().isoformat()
        score_days.setdefault(sec, {}).setdefault(local_day, []).append(item)
        visible_events += 1

    samples = []
    aligned = 0
    for proposed in rotation["hypothesis_sample"]:
        previous = proposed["incumbent_security_id"]
        contender = proposed["contender_security_id"]
        weakness = _stamp(proposed["first_explicit_weakening_at_utc"])
        a = score_days.get(previous, {})
        b = score_days.get(contender, {})
        candidate_days = sorted(set(a) & set(b))
        good_days = []
        differences = []
        paired_event_hashes = []
        issues = []
        for day in candidate_days:
            if len(a[day]) != 1 or len(b[day]) != 1:
                issues.append("MULTIPLE_PEER_SCORE_EVENTS_ONE_MARKET_DAY")
                continue
            old, new = a[day][0], b[day][0]
            if (old["industry_id"] != proposed["industry_id"] or
                    new["industry_id"] != proposed["industry_id"]):
                issues.append("SCORED_PEER_INDUSTRY_CHANGED")
                continue
            if (_stamp(old["screen_recorded_at_utc"]) < weakness or
                    _stamp(new["screen_recorded_at_utc"]) <= weakness):
                continue
            if old["screen_hit"] is not False or new["screen_hit"] is not True:
                issues.append("SCORE_SCREENS_DO_NOT_CONFIRM_WEAKNESS_VS_WATCH")
                continue
            good_days.append(day)
            differences.append(round(new["score"] - old["score"], 6))
            paired_event_hashes.append({
                "incumbent_event_sha256":sha256(_canonical(old).encode()).hexdigest(),
                "contender_event_sha256":sha256(_canonical(new).encode()).hexdigest(),
            })
        # Both most recent matched sessions must show a clear advantage;
        # do not cherry-pick any two older successes if the latest reversed.
        if len(good_days) < 2:
            issues.append("MISSING_TWO_PAIRED_PROSPECTIVE_SCORE_SESSIONS")
        elif (differences[-1] < MIN_SCORE_ADVANTAGE or
              differences[-2] < MIN_SCORE_ADVANTAGE):
            issues.append("RECENT_TWO_PEER_SCORE_ADVANTAGES_INSUFFICIENT")
        if not issues:
            aligned += 1
        samples.append({
            "industry_id": proposed["industry_id"],
            "incumbent_security_id": previous,
            "contender_security_id": contender,
            "paired_market_day_count": len(good_days),
            "last_two_paired_market_days": good_days[-2:],
            "last_two_contender_minus_incumbent_scores": differences[-2:],
            "last_two_paired_score_event_hashes": paired_event_hashes[-2:],
            "score_advantage_min_points_hypothesis": MIN_SCORE_ADVANTAGE,
            "locally_score_correlated": not issues,
            "issues": sorted(set(issues)),
        })
    return {
        "status": AUDIT_STATUS,
        "market": market, "model_version": model_version,
        "evaluated_at_utc": cutoff.isoformat(),
        "rotation_hypothesis_count": rotation["rotation_hypothesis_count"],
        "locally_two_session_score_correlated": aligned,
        "uncorroborated_rotation_hypotheses":
            rotation["rotation_hypothesis_count"] - aligned,
        "score_history_event_count": len(score_rows),
        "score_history_events_available_by_cutoff": visible_events,
        "source_watch_rotation_status": rotation["status"],
        "hypothesis_sample": samples[:sample_limit],
        "minimum_score_difference_hypothesis": MIN_SCORE_ADVANTAGE,
        "issuer_industry_pit_certified": False,
        "rank_scores_independently_authenticated": False,
        "real_leader_replacement_certified": False,
        "official_leader_replacements": 0,
        "warning": ("Research-only fixed four-factor score and WATCH event evidence. "
                    "Not independently time-attested, and no genuine era-leader "
                    "replacement or investment signal is certified."),
    }
