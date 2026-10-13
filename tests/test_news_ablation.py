"""ER-NC-09: sealed variant membership before outcomes; compare without leakage."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from test_frozen_holdout import freeze, outcomes_file
from eraleader.frozen_holdout import _read_frozen
from eraleader.news_ablation import freeze_news_ablations, evaluate_news_ablations

SEAL = datetime(2026, 4, 11, 12, tzinfo=timezone.utc)
EVAL = "2026-10-10T17:00:00+09:00"
EVAL_CLOCK = datetime(2026, 10, 11, tzinfo=timezone.utc)


def theme(sec, state="RISING"):
    return {
        "schema": "eraleader.er_nc_theme_lifecycle.v1",
        "theme_id": "THEME.SYNTHETIC", "state": state,
        "episode_id": "SYNTH_EP1",
        "source_sha256": "d"*64,
        "quality_status": "PRICE_RESEARCH_WITH_PARTIAL_ISSUER_CLASS_PROVENANCE",
        "as_of": "2026-04-02T03:00:00Z",
        "available_at": "2026-04-02T04:00:00Z",
        "source_first_received_at": "2026-04-02T05:00:00Z",
        "member_first_known_at": "2026-04-01T03:00:00Z",
        "market_session": "2026-04-02",
        "research_only": True, "official_leaders": 0,
    }


def regime(state="RISING"):
    return {
        "schema": "eraleader.er_nc_market_regime.v1",
        "market": "KR_KOSPI", "state": state,
        "quality_status": "RESEARCH_PIT_INPUTS_PRESENT_NOT_PERFORMANCE_VERIFIED",
        "regime_as_of": "2026-04-02T06:00:00Z",
        "input_cutoff": "2026-04-02T05:00:00Z",
        "source_first_received_at": "2026-04-02T07:00:00Z",
        "market_session": "2026-04-02",
        "research_only": True,
    }


def sample_context():
    return {
        "schema": "eraleader.er_nc09_context.v1",
        "market": "KR",
        "model_version": "era-offline-join-0.1",
        "source_mode": "LIVE_OBSERVED",
        "items": [
            {"security_id": "A", "theme": theme("A"),
             "regime": regime(),
             "news": {
                 "schema": "ernc.news_snapshot.v1",
                 "mode": "LIVE_OBSERVED",
                 "as_of": "2026-04-02T04:00:00Z",
                 "source_first_received_at": "2026-04-02T07:00:00Z",
                 "source_sha256": "a"*64, "quality_status": "OK",
             }},
            {"security_id": "B", "theme": theme("B"),
             "regime": regime("FALLING")},
            {"security_id": "C", "theme": theme("C", "DORMANT")},
        ],
    }


def source(tmp_path, content=None):
    path = tmp_path / "pit_context.json"
    path.write_text(json.dumps(content if content is not None else sample_context(),
                               sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return path, sha256(path.read_bytes()).hexdigest()


def prepare(tmp_path, *, data=None):
    freeze(tmp_path)
    ctx, pin = source(tmp_path, data)
    sealed = tmp_path / "sealed"
    result = freeze_news_ablations(
        tmp_path / "holdout_manifest.json", ctx, sealed,
        expected_context_sha256=pin, clock=SEAL,
    )
    return sealed, result


def test_freeze_cannot_read_labels_and_b1_same_original_candidate_set(tmp_path):
    directory, receipt = prepare(tmp_path)
    assert receipt["status"] == "FROZEN_ABLATION_RESEARCH_ONLY_NOT_CERTIFIED"
    assert receipt["outcome_labels_seen"] is False
    assert receipt["B0_equals_B1"] is True
    assert receipt["candidate_counts"] == {"B0":4, "B1":4, "B2":2, "B3":1}
    assert set(p.name for p in directory.iterdir()) == {
        "ablation_manifest.json", "B0_frozen.json", "B1_frozen.json",
        "B2_frozen.json", "B3_frozen.json",
    }
    ablation = json.loads((directory / "ablation_manifest.json").read_text())
    assert "is_future_leader" not in json.dumps(ablation)
    assert ablation["blocked_strategies"]["B4"].startswith("RULE_REVIEW_REQUIRED")
    assert ablation["real_time_news_witness_attested"] is False
    original = _read_frozen(tmp_path / "holdout_manifest.json")
    assert _read_frozen(directory / "B0_frozen.json")["signals"] == original["signals"]
    assert _read_frozen(directory / "B1_frozen.json")["signals"] == original["signals"]


def test_mature_only_comparison_reuses_original_label_protocol(tmp_path):
    directory, receipt = prepare(tmp_path)
    outcomes = outcomes_file(tmp_path)  # Exists strictly AFTER freeze.
    result = evaluate_news_ablations(
        directory, outcomes, expected_manifest_sha256=receipt["manifest_sha256"],
        evaluated_at=EVAL, clock=EVAL_CLOCK,
    )
    assert result["status"] == "RESEARCH_NOT_CERTIFIED_OUTCOME_EVALUATION"
    assert result["news_sidecar_baseline_identity_verified"]
    assert result["statistical_improvement_claimed"] is False
    assert result["arms"]["B0"]["true_early_discoveries"] == 1
    assert result["arms"]["B0"]["false_discoveries"] == 1
    assert result["arms"]["B0"]["late_or_post_onset"] == 1
    assert result["arms"]["B0"]["censored_outcomes"] == 1
    assert result["arms"]["B1"]["true_early_discoveries"] == 1
    assert result["arms"]["B2"]["signal_count"] == 2
    assert result["arms"]["B3"]["signal_count"] == 1
    assert result["arms"]["B3"]["precision_on_matured_known"] == 1
    assert result["arms"]["B0"]["precision_at_k"] is None
    assert result["arms"]["B0"]["CAGR"] is None
    assert result["B4"]["status"] == result["B5"]["status"] == "NOT_READY"
    assert result["real_prospective_accuracy_certified"] is False


@pytest.mark.parametrize("member,field,value", [
    ("theme", "member_first_known_at", "2026-04-03T00:00:00Z"),
    ("theme", "source_first_received_at", "2026-04-03T00:00:00Z"),
    ("theme", "available_at", "2026-04-03T00:00:00Z"),
    ("theme", "as_of", "2026-04-03T00:00:00Z"),
    ("regime", "source_first_received_at", "2026-04-03T00:00:00Z"),
    ("regime", "regime_as_of", "2026-04-03T00:00:00Z"),
    ("regime", "input_cutoff", "2026-04-03T00:00:00Z"),
    ("news", "source_first_received_at", "2026-04-03T00:00:00Z"),
    ("news", "as_of", "2026-04-03T00:00:00Z"),
])
def test_future_input_and_later_news_cannot_be_backfilled(tmp_path, member, field, value):
    data = sample_context()
    data["items"][0][member][field] = value
    with pytest.raises(ValueError, match="Future or late"):
        prepare(tmp_path, data=data)
    assert not (tmp_path / "sealed").exists()


@pytest.mark.parametrize("item", [
    {"is_future_leader": True}, {"leader_start_at": "2026-05-10"},
    {"outcome_label": "SUCCESS"}, {"security_id": "SECRET_OUTCOME"},
])
def test_labels_or_unknown_source_security_cannot_enter_selection(tmp_path, item):
    data = sample_context()
    if "security_id" in item:
        data["items"][0].update(item)
    else:
        data["items"][0].update(item)
    with pytest.raises(ValueError, match="Unknown|context fields|Context"):
        prepare(tmp_path, data=data)
    assert not (tmp_path / "sealed").exists()


def test_duplicate_or_unknown_candidate_context_is_fail_closed(tmp_path):
    data = sample_context()
    data["items"].append(deepcopy(data["items"][0]))
    with pytest.raises(ValueError, match="Unknown/duplicate"):
        prepare(tmp_path, data=data)


@pytest.mark.parametrize("mode", ["HISTORICAL_PUBLIC_REPLAY", "RETROSPECTIVE_FAKE"])
def test_source_mode_cannot_claim_historic_pit_independent_proof(tmp_path, mode):
    data = sample_context()
    data["source_mode"] = mode
    with pytest.raises(ValueError, match="Historical-public replay"):
        prepare(tmp_path, data=data)


def test_theme_stale_future_market_session_rejected(tmp_path):
    data = sample_context()
    data["items"][0]["theme"]["market_session"] = "2026-10-13"
    with pytest.raises(ValueError, match="Future session"):
        prepare(tmp_path, data=data)


def test_market_quality_not_verified_blocks_new_buy_but_not_original_candidate(tmp_path):
    data = sample_context()
    data["items"][0]["regime"]["quality_status"] = "INSUFFICIENT_PIT_COVERAGE"
    directory, result = prepare(tmp_path, data=data)
    assert result["candidate_counts"] == {"B0":4, "B1":4, "B2":2, "B3":0}
    assert _read_frozen(directory / "B0_frozen.json")["eligible_count"] == 4


def test_original_frozen_holdout_remains_identical(tmp_path):
    # Protect original WATCH registration and existing sealed source bytes.
    freeze(tmp_path)
    original = tmp_path / "holdout_manifest.json"
    digest = sha256(original.read_bytes()).hexdigest()
    ctx, pin = source(tmp_path)
    freeze_news_ablations(original, ctx, tmp_path / "new_dir",
                         expected_context_sha256=pin, clock=SEAL)
    assert sha256(original.read_bytes()).hexdigest() == digest


def test_maturity_censors_early_negative_label_instead_of_improving_precision(tmp_path):
    directory, receipt = prepare(tmp_path)
    labels = outcomes_file(tmp_path)
    data = json.loads(labels.read_text())
    data[1]["mature_at"] = "2026-08-01T17:00:00+09:00"
    labels.write_text(json.dumps(data))
    result = evaluate_news_ablations(
        directory, labels, expected_manifest_sha256=receipt["manifest_sha256"],
        evaluated_at=EVAL, clock=EVAL_CLOCK,
    )
    assert result["arms"]["B0"]["false_discoveries"] == 0
    assert result["arms"]["B0"]["censored_outcomes"] == 2
    assert result["real_prospective_accuracy_certified"] is False


def test_source_sha_pin_tamper_denies_publish(tmp_path):
    freeze(tmp_path)
    ctx, _ = source(tmp_path)
    with pytest.raises(ValueError, match="pin"):
        freeze_news_ablations(
            tmp_path / "holdout_manifest.json", ctx, tmp_path / "sealed",
            expected_context_sha256="f"*64, clock=SEAL,
        )
    assert not (tmp_path / "sealed").exists()


def test_source_symlink_and_duplicate_json_field_blocked(tmp_path):
    freeze(tmp_path)
    original, pin = source(tmp_path)
    linked = tmp_path / "linked.json"
    linked.symlink_to(original)
    with pytest.raises(ValueError, match="non-symlink"):
        freeze_news_ablations(
            tmp_path / "holdout_manifest.json", linked, tmp_path / "sealed",
            expected_context_sha256=pin, clock=SEAL,
        )
    original.write_text('{"schema":"eraleader.er_nc09_context.v1","schema":"duplicate"}')
    digest = sha256(original.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Invalid context JSON"):
        freeze_news_ablations(
            tmp_path / "holdout_manifest.json", original, tmp_path / "sealed",
            expected_context_sha256=digest, clock=SEAL,
        )


def test_seal_after_outcome_maturity_fails_evaluation(tmp_path):
    freeze(tmp_path)
    ctx, pin = source(tmp_path)
    directory = tmp_path / "sealed"
    late = datetime(2026, 10, 5, tzinfo=timezone.utc)
    receipt = freeze_news_ablations(
        tmp_path / "holdout_manifest.json", ctx, directory,
        expected_context_sha256=pin, clock=late,
    )
    with pytest.raises(ValueError, match="mature or known before holdout freeze"):
        evaluate_news_ablations(
            directory, outcomes_file(tmp_path),
            expected_manifest_sha256=receipt["manifest_sha256"],
            evaluated_at=EVAL, clock=EVAL_CLOCK,
        )


def test_pinned_manifest_tampering_and_wrong_external_pin_fail_closed(tmp_path):
    directory, receipt = prepare(tmp_path)
    labels = outcomes_file(tmp_path)
    with pytest.raises(ValueError, match="SHA witness"):
        evaluate_news_ablations(
            directory, labels, expected_manifest_sha256="f"*64,
            evaluated_at=EVAL, clock=EVAL_CLOCK,
        )
    manifest = directory / "ablation_manifest.json"
    content = json.loads(manifest.read_text())
    content["cohorts"]["B3"]["count"] = 4
    manifest.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="SHA witness"):
        evaluate_news_ablations(
            directory, labels,
            expected_manifest_sha256=receipt["manifest_sha256"],
            evaluated_at=EVAL, clock=EVAL_CLOCK,
        )


def test_scenario_blob_tampering_fails_seal_hash(tmp_path):
    directory, receipt = prepare(tmp_path)
    labels = outcomes_file(tmp_path)
    scenario = directory / "B3_frozen.json"
    content = json.loads(scenario.read_text())
    content["signals"] = []
    scenario.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="arm file changed"):
        evaluate_news_ablations(
            directory, labels, expected_manifest_sha256=receipt["manifest_sha256"],
            evaluated_at=EVAL, clock=EVAL_CLOCK,
        )


def test_future_evaluation_before_seal_or_after_clock_refused(tmp_path):
    directory, receipt = prepare(tmp_path)
    labels = outcomes_file(tmp_path)
    with pytest.raises(ValueError, match="after cohort seal"):
        evaluate_news_ablations(
            directory, labels, expected_manifest_sha256=receipt["manifest_sha256"],
            evaluated_at="2026-04-01T00:00:00Z", clock=EVAL_CLOCK,
        )
    with pytest.raises(ValueError, match="Future evaluation cutoff"):
        evaluate_news_ablations(
            directory, labels, expected_manifest_sha256=receipt["manifest_sha256"],
            evaluated_at="2027-10-01T00:00:00Z", clock=EVAL_CLOCK,
        )


def test_existing_directory_no_overwrite_and_metadata_unchanged(tmp_path):
    directory, receipt = prepare(tmp_path)
    before = {f.name:sha256(f.read_bytes()).hexdigest() for f in directory.iterdir()}
    ctx, pin = source(tmp_path)
    with pytest.raises(ValueError, match="new output"):
        freeze_news_ablations(
            tmp_path / "holdout_manifest.json", ctx, directory,
            expected_context_sha256=pin, clock=SEAL,
        )
    assert before == {
        f.name:sha256(f.read_bytes()).hexdigest() for f in directory.iterdir()
    }


def test_no_context_never_creates_hypothetical_gated_signals(tmp_path):
    data = sample_context()
    data["items"] = []
    directory, receipt = prepare(tmp_path, data=data)
    assert receipt["candidate_counts"] == {"B0":4,"B1":4,"B2":0,"B3":0}
    labels = outcomes_file(tmp_path)
    result = evaluate_news_ablations(
        directory, labels, expected_manifest_sha256=receipt["manifest_sha256"],
        evaluated_at=EVAL, clock=EVAL_CLOCK,
    )
    assert result["arms"]["B2"]["precision_on_matured_known"] is None
    assert result["arms"]["B3"]["precision_on_matured_known"] is None
    assert result["arms"]["B0"]["signal_count"] == 4


def test_stale_theme_or_regime_session_fails_instead_of_approving_old_filter(tmp_path):
    data = sample_context()
    data["items"][0]["theme"]["market_session"] = "2026-03-01"
    with pytest.raises(ValueError, match="Stale market"):
        prepare(tmp_path, data=data)


def test_simulated_seal_is_explicitly_marked_and_not_real_prospective_success(tmp_path):
    directory, receipt = prepare(tmp_path)
    assert receipt["simulation_clock_supplied"] is True
    result = evaluate_news_ablations(
        directory, outcomes_file(tmp_path),
        expected_manifest_sha256=receipt["manifest_sha256"],
        evaluated_at=EVAL, clock=EVAL_CLOCK,
    )
    assert result["run_is_simulation"] is True
    assert result["evaluation_clock_injected"] is True
    assert result["real_prospective_accuracy_certified"] is False


def test_theme_price_status_without_original_evidence_sha_cannot_filter(tmp_path):
    data = sample_context()
    data["items"][0]["theme"]["source_sha256"] = ""
    with pytest.raises(ValueError, match="PIT theme research"):
        prepare(tmp_path, data=data)


def test_theme_reactivation_without_original_episode_is_not_reusable(tmp_path):
    data = sample_context()
    data["items"][0]["theme"]["state"] = "REACTIVATING"
    data["items"][0]["theme"]["episode_id"] = None
    with pytest.raises(ValueError, match="PIT theme research"):
        prepare(tmp_path, data=data)
