"""5_5 multiple walk-forward folds, synthetic only, strict PIT embargo."""
import copy

import pytest

from eraleader.walkforward_replay import replay_walk_forward_folds


WINDOWS = [
    {"train_ends_at": "2024-03-01T17:00:00+09:00",
     "test_ends_at": "2024-05-01T17:00:00+09:00"},
    {"train_ends_at": "2024-05-01T17:00:00+09:00",
     "test_ends_at": "2024-07-01T17:00:00+09:00"},
]
MODEL = "locked-experiment-1"
LABEL_ID = "fixed-leader-definition-1"


def sample(decision, sid, available=None):
    return {"security_id": sid, "as_of": decision,
            "features_available_at": available or decision,
            "feature_hash": sid + "-feature-snapshot",
            "model_version": MODEL}


def outcome(signal, known, truth):
    return {"security_id": signal["security_id"],
            "as_of": signal["as_of"],
            "label_available_at": known,
            "label_definition_id": LABEL_ID,
            "is_future_leader": truth}


def dataset():
    stamps = [
        "2024-01-05T17:00:00+09:00",
        "2024-03-08T17:00:00+09:00",
        "2024-04-30T17:00:00+09:00",
        "2024-05-08T17:00:00+09:00",
    ]
    s = [sample(when, sec) for when, sec in zip(stamps, "ABCD")]
    labels = [
        outcome(s[0], "2024-02-10T17:00:00+09:00", True),
        outcome(s[1], "2024-04-10T17:00:00+09:00", True),
        outcome(s[2], "2024-06-10T17:00:00+09:00", False),
        outcome(s[3], "2024-08-20T17:00:00+09:00", False),
    ]
    return s, labels


def replay(snapshots=None, labels=None, windows=None, **overrides):
    s, lab = dataset()
    return replay_walk_forward_folds(
        s if snapshots is None else snapshots,
        lab if labels is None else labels,
        windows=WINDOWS if windows is None else windows,
        model_version=overrides.pop("model_version", MODEL),
        label_definition_id=overrides.pop("label_definition_id", LABEL_ID),
        **overrides,
    )


def test_repeated_fold_training_only_after_label_available_and_test_never_labeled():
    result = replay()
    assert result["fold_count"] == 2
    assert result["unique_test_candidate_count"] == 3
    first, second = result["folds"]
    assert first["known_training_samples"] == 1  # A, known by Mar1
    assert second["known_training_samples"] == 2  # A+B, B matured Apr10
    assert first["test_candidate_count"] == 2
    assert [x["security_id"] for x in first["test_candidates"]] == ["B", "C"]
    assert [x["security_id"] for x in second["test_candidates"]] == ["D"]
    assert all("target" not in row for fold in result["folds"]
               for row in fold["test_candidates"])
    assert result["test_outcome_labels_revealed"] is False
    assert result["model_was_pre_registered_attested"] is False
    assert result["historic_universe_pit_certified"] is False


def test_replay_is_reproducible_and_protocol_pins_all_folds():
    x = replay()
    y = replay()
    assert x == y
    assert len(x["protocol_sha256"]) == 64
    assert x["folds"][0]["test_candidates_sha256"] != x["folds"][1]["test_candidates_sha256"]
    assert replay(embargo_days=8)["protocol_sha256"] != x["protocol_sha256"]


@pytest.mark.parametrize("windows", [
    WINDOWS[:1],
    [],
    [WINDOWS[0], WINDOWS[0]],
    [WINDOWS[1], WINDOWS[0]],
    [WINDOWS[0], {"train_ends_at": "2024-04-20T17:00:00+09:00",
                   "test_ends_at": "2024-08-01T17:00:00+09:00"}],
    [WINDOWS[0], {"train_ends_at": "2024-05-01T17:00:00+09:00",
                   "test_ends_at": "2024-05-08T17:00:00+09:00"}],
])
def test_invalid_or_overlapping_fold_windows_are_rejected(windows):
    with pytest.raises(ValueError):
        replay(windows=windows)


def test_leaking_future_features_fails_closed():
    s, labels = dataset()
    s[1]["features_available_at"] = "2024-03-09T17:00:00+09:00"
    with pytest.raises(ValueError, match="Future feature"):
        replay(snapshots=s, labels=labels)


def test_post_cutoff_label_is_censored_not_trainable():
    s, labels = dataset()
    labels[1]["label_available_at"] = "2024-05-02T17:00:00+09:00"
    result = replay(snapshots=s, labels=labels)
    assert result["folds"][1]["known_training_samples"] == 1
    assert result["folds"][1]["censored_training_samples"] >= 1


@pytest.mark.parametrize("change,match", [
    (lambda s, l: s[0].update(model_version="revised-after-holdout"), "model version"),
    (lambda s, l: s[0].update(feature_hash=""), "fingerprint"),
    (lambda s, l: l[0].update(label_definition_id="changed"), "pinned definition"),
    (lambda s, l: l[0].update(is_future_leader=1), "Boolean"),
    (lambda s, l: l[1].update(label_available_at=s[1]["as_of"]), "availability"),
])
def test_unlocked_model_wrong_label_or_lookahead_fails_closed(change, match):
    s, labels = dataset()
    change(s, labels)
    with pytest.raises(ValueError, match=match):
        replay(snapshots=s, labels=labels)


@pytest.mark.parametrize("invalid", [True, 0, 91, 1.5])
def test_noninteger_or_unsafe_embargo_fails(invalid):
    with pytest.raises(ValueError, match="embargo_days"):
        replay(embargo_days=invalid)
