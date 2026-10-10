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

from .rank_score_ledger import (
    MARKETS, SAFE_NAME, _data, _now, register_rank_scores,
)
from .ranked_discovery import _time

# Fixed initial hypothesis, NOT an optimized or official 100-point leader model.
# Missing inputs reject the batch rather than receiving made-up zeroes.
HEURISTIC_VERSION = "eraleader.local_four_factor_rank_heuristic.v1"
TARGETS = {
    "revenue_yoy": 0.50,
    "operating_income_yoy": 0.75,
    "industry_revenue_yoy": 0.30,
    "momentum_6m": 0.60,
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
        )
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)
    return {
        "status": "LOCAL_COMPUTED_RANK_RESEARCH_ONLY",
        "market": market,
        "model_version": model_version,
        "formula_version": HEURISTIC_VERSION,
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
