"""5_3/5_5 native first-write Top-K freeze; 100% synthetic input only."""
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3

import pytest

from eraleader.native_topk_freeze import freeze_native_topk
from eraleader.ranked_discovery import _frozen
from eraleader.rank_score_pipeline import audit_computed_rank_provenance
from eraleader.prospective import ProspectiveRegistry
from eraleader.cli import main
from test_rank_score_pipeline import bundle, score
from test_rank_score_ledger import WRITE, STAMP, MODEL
from test_ranked_registry import run

NOW = WRITE + timedelta(minutes=5)
LABEL = "SYN-LEADER-PREDECLARED-V1"


def protocol(path, market="KR"):
    obj = {
        "schema_version": "eraleader.future_leader_label_definition.v1",
        "label_definition_id": LABEL, "market": market, "horizon_days": 180,
        "positive_criterion": "Prospectively classify a documented leader within 180 days.",
        "measurement_method": "Use future independent leader start date, not source features.",
        "universe_scope": "All original positive WATCH records for the pinned model.",
        "delisted_handling": "Censor without source-verified delisting and cash proceeds.",
    }
    path.write_text(json.dumps(obj, sort_keys=True))
    return path


def fixture(tmp_path, market="KR", scored=True):
    b = bundle(tmp_path, market=market)
    definition = protocol(tmp_path / "definition.json", market)
    if scored:
        score(b, market=market)
    return b, definition, tmp_path / "frozen.json"


def freeze(b, rule, target, market="KR", clock=NOW, **kwargs):
    return freeze_native_topk(
        b[4], b[1], b[2], rule, target,
        market=market, model_version=MODEL, label_definition_id=LABEL,
        horizon_days=180, k=1, clock=clock, **kwargs,
    )


@pytest.mark.parametrize("market", ["KR", "US"])
def test_native_score_first_write_freeze_keeps_real_time_not_watch_time(tmp_path, market):
    b, rule, out = fixture(tmp_path, market=market)
    watch_before = sha256(b[1].read_bytes()).hexdigest()
    scores_before = sha256(b[4].read_bytes()).hexdigest()
    report = freeze(b, rule, out, market=market)
    obj = _frozen(out)
    assert report["status"] == "LOCAL_NATIVE_TOPK_FROZEN_RESEARCH_ONLY"
    assert report["positive_watch_count"] == 2
    assert report["native_scores_matched"] == 2
    assert [row["security_id"] for row in obj["ranked_candidates"]] == ["A", "B"]
    assert [row["score"] for row in obj["ranked_candidates"]] == [100, 50]
    assert all(row["recorded_at_utc"] == WRITE.isoformat() for row in obj["ranked_candidates"])
    assert all(row["score_computed_at_utc"] == WRITE.isoformat() for row in obj["ranked_candidates"])
    assert all(row["recorded_at_utc"] != STAMP.isoformat() for row in obj["ranked_candidates"])
    assert obj["retrospective_freeze"] is False
    assert obj["label_definition_sha256"] == sha256(rule.read_bytes()).hexdigest()
    assert obj["native_cohort_binding"]["scope"] == "ALL_PINNED_MODEL_POSITIVE_WATCH"
    assert obj["source_pit_independently_authenticated"] is False
    assert obj["timestamp_independently_attested"] is False
    assert report["official_leader_promotions"] == 0
    check = audit_computed_rank_provenance(out, b[4], b[2], watch_db=b[1])
    assert check["formula_reproduction_locally_consistent"] is True
    assert sha256(b[1].read_bytes()).hexdigest() == watch_before
    assert sha256(b[4].read_bytes()).hexdigest() == scores_before


def test_missing_score_cannot_publish_partial_cohort(tmp_path):
    b, rule, out = fixture(tmp_path, scored=False)
    with pytest.raises(ValueError, match="score|WATCH"):
        freeze(b, rule, out)
    assert not out.exists()


def test_extra_watch_cannot_be_silently_excluded_from_topk_denominator(tmp_path):
    b, rule, out = fixture(tmp_path)
    reg = ProspectiveRegistry(b[1])
    try:
        instant = STAMP + timedelta(minutes=1)
        reg.record_integrated(run(["C"], model=MODEL, observed=instant.isoformat()),
                              clock=instant)
    finally:
        reg.close()
    with pytest.raises(ValueError, match="coverage|WATCH"):
        freeze(b, rule, out)
    assert not out.exists()


def test_orphan_positive_signal_no_matching_observation_rejected(tmp_path):
    b, rule, out = fixture(tmp_path)
    with sqlite3.connect(b[1]) as db:
        db.execute("DELETE FROM research_screen_observations WHERE security_id='A'")
    with pytest.raises(ValueError, match="observation|WATCH"):
        freeze(b, rule, out)
    assert not out.exists()


def test_missing_positive_signal_no_matching_observation_rejected(tmp_path):
    b, rule, out = fixture(tmp_path)
    with sqlite3.connect(b[1]) as db:
        db.execute("DELETE FROM prospective_signals WHERE security_id='A'")
    with pytest.raises(ValueError, match="observation|WATCH|coverage"):
        freeze(b, rule, out)
    assert not out.exists()


def test_mutated_feature_bytes_before_freeze_fail_closed(tmp_path):
    b, rule, out = fixture(tmp_path)
    (b[2] / "A.json").write_text('{"corrupted":true}')
    with pytest.raises(ValueError, match="Native|SOURCE_FEATURE|score"):
        freeze(b, rule, out)
    assert not out.exists()


def test_score_rehashed_to_forged_higher_value_cannot_pass_formula(tmp_path):
    b, rule, out = fixture(tmp_path)
    with sqlite3.connect(b[4]) as db:
        original = json.loads(db.execute(
            "SELECT payload FROM rank_score_events WHERE security_id='B'").fetchone()[0])
        original["score"] = 99.0
        from eraleader.prospective import _canonical
        from eraleader.rank_score_ledger import _hash
        db.execute("UPDATE rank_score_events SET payload=?,evidence_hash=? WHERE security_id='B'",
                   (_canonical(original), _hash(original)))
    with pytest.raises(ValueError, match="Native|FORMULA|FROZEN|score"):
        freeze(b, rule, out)
    assert not out.exists()


def test_rule_must_exist_and_match_before_any_freeze(tmp_path):
    b, rule, out = fixture(tmp_path)
    item = json.loads(rule.read_text())
    item["horizon_days"] = 100
    rule.write_text(json.dumps(item))
    with pytest.raises(ValueError, match="protocol"):
        freeze(b, rule, out)
    assert not out.exists()


def test_native_topk_requires_nonempty_preregistered_definition(tmp_path):
    b, rule, out = fixture(tmp_path)
    with pytest.raises(ValueError):
        freeze_native_topk(b[4], b[1], b[2], rule, out, market="KR",
                           model_version=MODEL, label_definition_id="",
                           horizon_days=180, k=1, clock=NOW)
    assert not out.exists()


def test_first_write_not_backdated_or_stale(tmp_path):
    b, rule, out = fixture(tmp_path)
    with pytest.raises(ValueError, match="future|clock|time"):
        freeze(b, rule, out, clock=STAMP)
    with pytest.raises(ValueError, match="(?i)stale|age"):
        freeze(b, rule, out, clock=NOW + timedelta(days=2))
    assert not out.exists()


def test_oversized_topk_rejected_and_existing_output_immutable(tmp_path):
    b, rule, out = fixture(tmp_path)
    with pytest.raises(ValueError, match="K|k|candidate"):
        freeze_native_topk(b[4], b[1], b[2], rule, out, market="KR",
                           model_version=MODEL, label_definition_id=LABEL,
                           horizon_days=180, k=3, clock=NOW)
    assert not out.exists()
    freeze(b, rule, out)
    original = out.read_bytes()
    with pytest.raises(FileExistsError):
        freeze(b, rule, out)
    assert out.read_bytes() == original


def test_cli_seals_at_actual_os_time_no_backdate_option(tmp_path, capsys):
    from datetime import datetime, timezone
    from test_rank_score_pipeline import FACTORS_A
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=5)
    model = "cli-native-" + tmp_path.name
    watch = tmp_path / "live_watch.sqlite"
    reg = ProspectiveRegistry(watch)
    try:
        reg.record_integrated(run(["CLIA"], model=model, observed=past.isoformat()),
                              clock=past)
    finally:
        reg.close()
    folder = tmp_path / "features"
    folder.mkdir()
    (folder / "a.json").write_text(json.dumps({
        "schema": "eraleader.rank_feature_document.v1",
        "market": "KR", "model_version": model, "security_id": "CLIA",
        "available_at": (past - timedelta(seconds=1)).isoformat(),
        "features": FACTORS_A}))
    db = tmp_path / "score.sqlite"
    from eraleader.rank_score_pipeline import compute_and_register_rank_scores
    compute_and_register_rank_scores(folder, watch, db, market="KR", model_version=model)
    rule = protocol(tmp_path / "rule.json")
    out = tmp_path / "native_frozen.json"
    main(["freeze-native-topk", "--market", "KR", "--model-version", model,
          "--score-ledger", str(db), "--watch-ledger", str(watch),
          "--features-dir", str(folder), "--label-definition-id", LABEL,
          "--label-definition-file", str(rule), "--horizon-days", "180", "--k", "1",
          "--out-file", str(out)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["positive_watch_count"] == 1
    assert now <= datetime.fromisoformat(_frozen(out)["frozen_at_utc"]) <= datetime.now(timezone.utc)
    assert payload["real_leader_prediction_certified"] is False
    assert payload["official_leader_promotions"] == 0


def test_feature_revised_while_preflight_is_running_must_not_seal(tmp_path, monkeypatch):
    import eraleader.native_topk_freeze as module
    b, rule, out = fixture(tmp_path)
    actual = module.audit_computed_rank_provenance

    def change_source_after_good_audit(*args, **kwargs):
        report = actual(*args, **kwargs)
        (b[2] / "A.json").write_text('{"post_preflight_revision":true}')
        return report

    monkeypatch.setattr(module, "audit_computed_rank_provenance", change_source_after_good_audit)
    with pytest.raises(ValueError, match="Native|feature|SOURCE_FEATURE|revised"):
        freeze(b, rule, out)
    assert not out.exists()


def test_positive_observation_modified_during_preflight_blocks_publication(tmp_path, monkeypatch):
    import eraleader.native_topk_freeze as module
    b, rule, out = fixture(tmp_path)
    actual = module.audit_computed_rank_provenance

    def drop_source_observation_after_good_audit(*args, **kwargs):
        report = actual(*args, **kwargs)
        with sqlite3.connect(b[1]) as db:
            db.execute("DELETE FROM research_screen_observations WHERE security_id='A'")
        return report

    monkeypatch.setattr(module, "audit_computed_rank_provenance", drop_source_observation_after_good_audit)
    with pytest.raises(ValueError, match="WATCH|observation|revised"):
        freeze(b, rule, out)
    assert not out.exists()


def test_native_first_write_cohort_never_accepts_unproven_external_score(tmp_path):
    from test_rank_score_ledger import setup, record
    b = setup(tmp_path)
    record(b)
    rule = protocol(tmp_path / "rule.json")
    out = tmp_path / "frozen_native.json"
    with pytest.raises(ValueError, match="Native|COMPUTATION|EXTERNAL|provenance"):
        freeze(b, rule, out)
    assert not out.exists()


def test_no_future_label_or_return_fields_in_frozen_native_rank(tmp_path):
    b, rule, out = fixture(tmp_path)
    freeze(b, rule, out)
    candidates = _frozen(out)["ranked_candidates"]
    assert all(set(row) == {"security_id", "score", "rank",
                            "features_available_at_utc", "score_computed_at_utc",
                            "recorded_at_utc"} for row in candidates)
    assert all("is_future_leader" not in row and "future_return" not in row
               for row in candidates)
