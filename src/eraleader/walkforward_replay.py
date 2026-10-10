"""5_5 repeated offline walk-forward replay with non-overlapping test windows.

Strict fold boundaries, embargo and pinned model/label definitions are
mechanical research gates, NOT proof the model was pre-registered or that
source vintages, market membership and outcomes are independently certified.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json

from .walkforward import time, walk_forward_split


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def replay_walk_forward_folds(
    snapshots: list[dict], labels: list[dict], *, windows: list[dict],
    model_version: str, label_definition_id: str, embargo_days: int = 7,
) -> dict:
    """Replay >=2 chronological expanding-origin splits without test labels.

    The next training cutoff may occur only after the previous test ends.
    Previously held-out outcomes may enter later training ONLY when they have
    genuinely become available by that later training cutoff.
    """
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Pinned model_version is required")
    if not isinstance(label_definition_id, str) or not label_definition_id.strip():
        raise ValueError("Pinned label_definition_id is required")
    if type(embargo_days) is not int or not 1 <= embargo_days <= 90:
        raise ValueError("embargo_days must be an integer between 1 and 90")
    if not isinstance(windows, list) or not 2 <= len(windows) <= 40:
        raise ValueError("At least two and at most forty folds are required")
    if not isinstance(snapshots, list) or not isinstance(labels, list):
        raise ValueError("Snapshots and outcome labels must be lists")
    for row in snapshots:
        if not isinstance(row, dict) or row.get("model_version") != model_version:
            raise ValueError("All PIT snapshots must pin the same model version")
        if not isinstance(row.get("feature_hash"), str) or not row["feature_hash"].strip():
            raise ValueError("Snapshot feature fingerprint required")
    for row in labels:
        if not isinstance(row, dict) or row.get("label_definition_id") != label_definition_id:
            raise ValueError("Outcome labels must use the pinned definition")
        if type(row.get("is_future_leader")) is not bool:
            raise ValueError("Boolean outcome label required")

    spec = {"model_version": model_version, "label_definition_id": label_definition_id,
            "embargo_days": embargo_days, "windows": windows}
    prior_end = None
    previous_train = None
    seen_test_signals = set()
    folds = []
    for index, window in enumerate(windows, start=1):
        if not isinstance(window, dict) or set(window) != {"train_ends_at", "test_ends_at"}:
            raise ValueError("Fold must fix train_ends_at and test_ends_at only")
        train_end = time(window["train_ends_at"])
        test_end = time(window["test_ends_at"])
        if train_end + timedelta(days=embargo_days) >= test_end:
            raise ValueError("Test fold must extend beyond the embargo")
        if prior_end is not None and train_end < prior_end:
            raise ValueError("Overlapping holdout windows not permitted")
        if previous_train is not None and train_end <= previous_train:
            raise ValueError("Fold training cutoffs must strictly advance")
        result = walk_forward_split(
            snapshots, labels,
            train_ends_at=window["train_ends_at"],
            test_ends_at=window["test_ends_at"], embargo_days=embargo_days,
        )
        candidates = result["test_candidates"]
        candidate_keys = [(row["security_id"], row["as_of"]) for row in candidates]
        if any(key in seen_test_signals for key in candidate_keys):
            raise ValueError("Holdout candidate reused across folds")
        seen_test_signals.update(candidate_keys)
        folds.append({
            "fold": index, "train_ends_at": train_end.isoformat(),
            "test_begins_at": result["test_begins_at"],
            "test_ends_at": test_end.isoformat(),
            "embargo_days": embargo_days,
            "known_training_samples": result["known_training_samples"],
            "censored_training_samples": result["censored_training_samples"],
            "test_candidate_count": len(candidates),
            "test_candidates": candidates,
            "training_samples_sha256": _digest(result["training"]),
            "test_candidates_sha256": _digest(candidates),
            "test_outcome_labels_revealed": False,
        })
        previous_train, prior_end = train_end, test_end
    return {
        "status": "OFFLINE_REPEATED_WALK_FORWARD_RESEARCH_NOT_CERTIFIED",
        "model_version": model_version,
        "label_definition_id": label_definition_id,
        "protocol_sha256": _digest(spec),
        "fold_count": len(folds),
        "unique_test_candidate_count": len(seen_test_signals),
        "folds": folds,
        "test_outcome_labels_revealed": False,
        "model_was_pre_registered_attested": False,
        "historic_universe_pit_certified": False,
        "outcome_source_independently_verified": False,
        "warning": "Fold replay only. Source PIT, delist proceeds, model lock and live discovery still need independent evidence.",
    }
