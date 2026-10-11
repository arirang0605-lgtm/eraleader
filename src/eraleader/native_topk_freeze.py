"""5_3/5_5: freeze a complete *locally observed* native-score WATCH cohort.

The score recorded_at clock is the actual first WRITE of the numeric score,
NOT the earlier first WATCH clock. Local self-hashes do not certify data source
PIT, clock attestation, market-wide completeness or future leader skill.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import math
import sqlite3

from .prospective import _canonical
from .rank_score_ledger import _hash, _open_watch, _watch_proof
from .rank_score_pipeline import audit_computed_rank_provenance
from .ranked_discovery import (
    _digest, _frozen, _now, _save_new, _time, freeze_ranked_snapshot,
)

STATUS = "LOCAL_NATIVE_TOPK_FROZEN_RESEARCH_ONLY"
BINDING_SCHEMA = "eraleader.native_rank_cohort_binding.v1"


def _readonly_cohort(
    score_db: Path, watch_db: Path, *, market: str,
    model_version: str, as_of: datetime, max_age_hours: int,
) -> tuple[list[dict], dict]:
    """Read all positive WATCH identities and all local numeric score receipts.

    A unique model_version must be used per prospective cohort. Refuse to
    select only the already-scored winners and silently drop missing WATCHs.
    """
    watch = _open_watch(watch_db)
    try:
        try:
            signals = watch.execute(
                """SELECT security_id,observed_as_of,recorded_at_utc,
                          source_run_id,payload_hash,payload
                   FROM prospective_signals
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
            observations = watch.execute(
                """SELECT security_id,observed_as_of,recorded_at_utc,
                          source_run_id,payload_hash,payload,screen_hit
                   FROM research_screen_observations
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("WATCH source tables not available") from exc
        if not 1 <= len(signals) <= 1000:
            raise ValueError("Complete pinned-model positive WATCH cohort must have 1..1000 events")
        positive_observations = {
            tuple(row[:6]) for row in observations if row[6] == 1
        }
        positive_signals = {tuple(row) for row in signals}
        if len(positive_observations) != sum(row[6] == 1 for row in observations) or (
            len(positive_signals) != len(signals) or
            positive_signals != positive_observations
        ):
            raise ValueError("Positive WATCH signals and original screen observations disagree")
        watch_ids = {row[0] for row in signals}
        for row in signals:
            if _time(row[2]) > as_of:
                raise ValueError("Future WATCH registration after current clock")
        proofs = {
            sec: _watch_proof(watch, market, model_version, sec, as_of, 3)
            for sec in sorted(watch_ids)
        }
    finally:
        watch.close()

    file = Path(score_db)
    if file.is_symlink() or not file.is_file():
        raise ValueError("Missing or linked original numeric score ledger")
    db = sqlite3.connect(file.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        try:
            rows = db.execute(
                """SELECT security_id,evidence_hash,payload
                   FROM rank_score_events
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Numeric score source table not available") from exc
    finally:
        db.close()

    score_ids = {row[0] for row in rows}
    if len(score_ids) != len(rows) or score_ids != watch_ids:
        raise ValueError("Incomplete positive WATCH-to-native-score cohort coverage")
    candidates = []
    bindings = []
    for sec, evidence_hash, raw in rows:
        try:
            item = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid original score JSON") from exc
        if (not isinstance(item, dict) or item.get("security_id") != sec or
            item.get("market") != market or
            item.get("model_version") != model_version or
            _canonical(item) != raw or _hash(item) != evidence_hash):
            raise ValueError("Original score first-write hash/identity inconsistent")
        computed_at = _time(item["score_recorded_at_utc"])
        available_at = _time(item["feature_available_at_utc"])
        first_watch = proofs[sec]
        first_watch_at = first_watch["watch_registered_at"]
        if computed_at > as_of or available_at > computed_at:
            raise ValueError("Future score or feature before snapshot clock")
        if first_watch_at > computed_at or computed_at - first_watch_at > timedelta(minutes=60):
            raise ValueError("Score first write outside original WATCH registration window")
        if as_of - computed_at > timedelta(hours=max_age_hours):
            raise ValueError("Stale first-written score cannot become a new prospective ranking")
        if (item.get("watch_signal_id") != first_watch["watch_signal_id"] or
            item.get("watch_payload_sha256") != first_watch["watch_payload_sha256"] or
            _time(item["watch_registered_at_utc"]) != first_watch_at):
            raise ValueError("Original WATCH-to-score evidence linkage changed")
        if (type(item.get("score")) not in (int, float) or
            not math.isfinite(item["score"]) or not 0 <= item["score"] <= 100):
            raise ValueError("Invalid first-written bounded score")
        # First WRITE is a conservative local computation time claim; never
        # substitute earlier WATCH registration for numeric score availability.
        candidates.append({
            "security_id": sec,
            "score": float(item["score"]),
            "features_available_at": available_at.isoformat(),
            "score_computed_at": computed_at.isoformat(),
            "recorded_at": computed_at.isoformat(),
        })
        bindings.append({
            "security_id": sec,
            "score_first_write_sha256": evidence_hash,
            "first_watch_signal_id": first_watch["watch_signal_id"],
            "first_watch_payload_sha256": first_watch["watch_payload_sha256"],
        })
    candidates.sort(key=lambda row: row["security_id"])
    bindings.sort(key=lambda row: row["security_id"])
    return candidates, {
        "schema_version": BINDING_SCHEMA,
        "scope": "ALL_PINNED_MODEL_POSITIVE_WATCH",
        "positive_watch_count": len(signals),
        "distinct_positive_watch_securities": len(watch_ids),
        "native_score_first_writes": len(rows),
        "watch_score_evidence_sha256": sha256(
            _canonical(bindings).encode("utf-8")
        ).hexdigest(),
        "score_availability_kind": "LOCAL_NATIVE_SCORE_FIRST_WRITE_NOT_FIRST_WATCH",
        "independent_source_pit_and_timestamp_attested": False,
    }


def freeze_native_topk(
    score_db: Path, watch_db: Path, feature_dir: Path,
    label_definition_file: Path, out_file: Path, *,
    market: str, model_version: str, label_definition_id: str,
    horizon_days: int, k: int, max_age_hours: int = 24,
    clock: datetime | None = None,
) -> dict:
    """Preflight native scores + complete WATCH cohort, then O_EXCL-seal once.

    The injected clock is solely for offline deterministic tests. The public
    CLI uses the current OS clock and cannot backdate the cohort.
    """
    if market not in ("KR", "US") or not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned KR/US market and nonempty model_version required")
    if not isinstance(label_definition_id, str) or not label_definition_id.strip():
        raise ValueError("Original predeclared leader label definition ID required")
    if type(max_age_hours) is not int or not 1 <= max_age_hours <= 168:
        raise ValueError("Invalid max_age_hours")
    if type(k) is not int or k < 1:
        raise ValueError("Invalid K")
    now = _now(clock)
    out_file = Path(out_file)
    if out_file.is_symlink() or out_file.parent.is_symlink():
        raise ValueError("Unsafe linked freeze destination")
    if out_file.exists():
        raise FileExistsError(out_file)

    first, binding = _readonly_cohort(
        Path(score_db), Path(watch_db), market=market,
        model_version=model_version, as_of=now,
        max_age_hours=max_age_hours,
    )
    if k > len(first):
        raise ValueError("Requested K exceeds prospectively scored positive WATCH candidates")

    with TemporaryDirectory(prefix="eraleader-native-topk-") as dirname:
        directory = Path(dirname)
        input_file = directory / "source_scores.json"
        input_file.write_text(json.dumps(first, ensure_ascii=False, sort_keys=True))
        preview = directory / "preflight_frozen.json"
        sealed = freeze_ranked_snapshot(
            input_file, preview,
            market=market, snapshot_at=now.isoformat(),
            model_version=model_version, horizon_days=horizon_days, k=k,
            label_definition_id=label_definition_id,
            label_definition_file=Path(label_definition_file), clock=now,
        )
        audit = audit_computed_rank_provenance(
            preview, Path(score_db), Path(feature_dir),
            watch_db=Path(watch_db),
            sample_limit=min(1000, len(first)),
        )
        if (audit["blocker_count"] or
            audit["locally_computed_score_records_matched"] != len(first) or
            not audit["formula_reproduction_locally_consistent"]):
            raise ValueError(
                "Native computation / original WATCH preflight failed: " +
                ", ".join(audit["blockers"][:10])
            )
        # Read source witnesses a second time immediately before publication.
        # If source rows change during the audit, publish no frozen result.
        second, witness = _readonly_cohort(
            Path(score_db), Path(watch_db), market=market,
            model_version=model_version, as_of=now,
            max_age_hours=max_age_hours,
        )
        if first != second or binding != witness:
            raise ValueError("WATCH/score first-write witnesses revised during freeze")
        # The score and WATCH witness rows may be stable while the referenced
        # original feature document is rewritten during a lengthy preflight.
        # Recompute the source hashes/formula immediately before publication.
        final_audit = audit_computed_rank_provenance(
            preview, Path(score_db), Path(feature_dir),
            watch_db=Path(watch_db), sample_limit=min(1000, len(first)),
        )
        if (final_audit["blocker_count"] or
            final_audit["locally_computed_score_records_matched"] != len(first) or
            not final_audit["formula_reproduction_locally_consistent"]):
            raise ValueError("Native source features revised during freeze: " +
                             ", ".join(final_audit["blockers"][:10]))
        from .ranked_discovery import _label_protocol
        if _label_protocol(Path(label_definition_file), label_id=label_definition_id,
                           market=market, horizon=horizon_days) != sealed["label_definition_sha256"]:
            raise ValueError("Predeclared leader rule bytes revised during freeze")
        sealed["native_cohort_binding"] = binding
        sealed["content_sha256"] = _digest({
            key: val for key, val in sealed.items()
            if key != "content_sha256"
        })
        _save_new(out_file, sealed)
        _frozen(out_file)

    return {
        "status": STATUS,
        "path": str(out_file),
        "market": market,
        "model_version": model_version,
        "frozen_rank_sha256": sealed["content_sha256"],
        "label_definition_sha256": sealed["label_definition_sha256"],
        "positive_watch_count": binding["distinct_positive_watch_securities"],
        "native_scores_matched": len(first),
        "requested_k": k,
        "snapshot_at_utc": now.isoformat(),
        "retrospective_freeze": False,
        "source_pit_independently_authenticated": False,
        "timestamp_independently_attested": False,
        "real_leader_prediction_certified": False,
        "official_leader_promotions": 0,
    }
