"""5_3 ranking snapshot integrity and censored precision@K research."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from eraleader.ranked_discovery import (
    _canonical, evaluate_ranked_precision_at_k, freeze_ranked_snapshot, main,
)

UTC = timezone.utc
NOW = datetime(2026, 4, 1, tzinfo=UTC)
SNAP = "2026-01-01T00:00:00+00:00"


def record(sid="A", score=90, available="2025-12-31T22:00:00+00:00",
           calculated="2025-12-31T22:10:00+00:00",
           registered="2025-12-31T22:15:00+00:00"):
    return {"security_id": sid, "score": score,
            "features_available_at": available, "score_computed_at": calculated,
            "recorded_at": registered}


def label(sid, winner, mature="2026-02-02T00:00:00+00:00",
          published="2026-02-03T00:00:00+00:00",
          onset="2026-01-11T00:00:00+00:00"):
    data = {"security_id": sid, "is_future_leader": winner, "mature_at": mature,
            "outcome_available_at": published}
    if winner:
        data["leader_start_at"] = onset
    return data


def sealed(tmp_path, candidates=None, *, k=3, market="KR", snap=SNAP, now=NOW):
    if candidates is None:
        candidates = [record("B", 80), record("A", 90), record("C", 80), record("D", 30)]
    data = tmp_path/"candidate_inputs.json"
    data.write_text(json.dumps(candidates), encoding="utf-8")
    output = tmp_path/"sealed_ranked_snapshot.json"
    result = freeze_ranked_snapshot(
        data, output, market=market, snapshot_at=snap,
        model_version="research-v1", horizon_days=30, k=k, clock=now)
    return output, result


def measured(tmp_path, freeze, outcomes, cutoff="2026-03-01T00:00:00Z", *, now=NOW):
    src = tmp_path/"future_outcomes.json"
    src.write_text(json.dumps(outcomes), encoding="utf-8")
    return evaluate_ranked_precision_at_k(freeze, src, evaluated_at=cutoff, clock=now)


def test_freeze_seals_deterministic_order_and_pinned_k(tmp_path):
    output, result = sealed(tmp_path)
    assert [r["security_id"] for r in result["ranked_candidates"]] == ["A", "B", "C", "D"]
    assert [r["rank"] for r in result["ranked_candidates"]] == [1, 2, 3, 4]
    assert result["requested_k"] == 3 and result["retrospective_freeze"] is True
    assert len(result["content_sha256"]) == 64
    assert result["source_pit_independently_authenticated"] is False
    with pytest.raises(FileExistsError):
        freeze_ranked_snapshot(tmp_path/"candidate_inputs.json", output,
                               market="KR", snapshot_at=SNAP, model_version="m",
                               horizon_days=30, k=2, clock=NOW)


def test_precision_at_k_freezes_denominator_and_censors_unknown(tmp_path):
    output, _ = sealed(tmp_path)
    result = measured(tmp_path, output, [label("A", True), label("B", False),
                                        label("D", True), label("UNKNOWN", True)])
    assert result["selected_count"] == 3
    assert result["early_hits"] == 1 and result["known_failures"] == 1
    assert result["censored"] == 1 and result["unmatched_label_ids"] == 1
    assert result["precision_at_k_on_known"] == 0.5
    assert result["conservative_precision_at_k_floor"] == round(1/3, 6)
    assert result["median_early_lead_days"] == 10
    assert result["recall_at_k"] is None
    assert result["official_leader_promotions"] == 0
    assert result["real_leader_prediction_certified"] is False


def test_only_unknown_labels_give_no_precision_not_zero(tmp_path):
    output, _ = sealed(tmp_path)
    result = evaluate_ranked_precision_at_k(output, None, evaluated_at="2026-03-01T00:00:00Z", clock=NOW)
    assert result["censored"] == 3
    assert result["precision_at_k_on_known"] is None
    assert result["conservative_precision_at_k_floor"] == 0


def test_negative_before_full_horizon_stays_censored(tmp_path):
    output, _ = sealed(tmp_path, k=1)
    result = measured(tmp_path, output, [label("A", False,
                            mature="2026-01-21T00:00:00Z", published="2026-01-22T00:00:00Z")])
    assert result["censored"] == 1
    assert result["premature_negative_censored"] == 1
    assert result["known_failures"] == 0


def test_negative_mature_at_exact_horizon_is_failure(tmp_path):
    output, _ = sealed(tmp_path, k=1)
    result = measured(tmp_path, output, [label("A", False,
                            mature="2026-01-31T00:00:00Z", published="2026-02-01T00:00:00Z")])
    assert result["known_failures"] == 1 and result["censored"] == 0


@pytest.mark.parametrize("onset", [
    "2026-01-01T01:00:00Z",  # KR same day, no early lead
    "2025-12-31T00:00:00Z",  # Already a leader
    "2026-02-11T00:00:00Z",  # After declared 30 day window
])
def test_late_or_same_day_positive_not_early(tmp_path, onset):
    output, _ = sealed(tmp_path, k=1)
    result = measured(tmp_path, output, [label("A", True, onset=onset,
                            mature="2026-02-20T00:00:00Z", published="2026-02-21T00:00:00Z")])
    assert result["early_hits"] == 0 and result["known_failures"] == 1


def test_future_label_publication_censored(tmp_path):
    output, _ = sealed(tmp_path, k=1)
    result = measured(tmp_path, output, [label("A", True,
                            mature="2026-02-02T00:00:00Z", published="2026-04-02T00:00:00Z")])
    assert result["censored"] == 1 and result["precision_at_k_on_known"] is None


def test_outcome_maturity_in_future_censored(tmp_path):
    output, _ = sealed(tmp_path, k=1)
    result = measured(tmp_path, output, [label("A", True,
                            mature="2026-03-21T00:00:00Z", published="2026-03-22T00:00:00Z")],
                      cutoff="2026-03-01T00:00:00Z")
    assert result["censored"] == 1


def test_snapshot_digest_tamper_refused(tmp_path):
    output, _ = sealed(tmp_path)
    obj = json.loads(output.read_text())
    obj["ranked_candidates"][0]["score"] = 0
    output.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="SHA256"):
        evaluate_ranked_precision_at_k(output, None, evaluated_at="2026-03-01T00:00:00Z", clock=NOW)


def test_rehash_does_not_allow_resorting_frozen_candidates(tmp_path):
    output, _ = sealed(tmp_path)
    obj = json.loads(output.read_text())
    obj["ranked_candidates"][0], obj["ranked_candidates"][1] = obj["ranked_candidates"][1], obj["ranked_candidates"][0]
    obj["content_sha256"] = hashlib.sha256(_canonical({k:v for k,v in obj.items() if k != "content_sha256"})).hexdigest()
    output.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="rank"):
        evaluate_ranked_precision_at_k(output, None, evaluated_at="2026-03-01T00:00:00Z", clock=NOW)


@pytest.mark.parametrize("change", [
    {"score": float("nan")},
    {"score": float("inf")},
    {"score": True},
    {"score": -1},
    {"score": 101},
    {"features_available_at": "2026-01-02T00:00:00Z"},
    {"score_computed_at": "2026-01-02T00:00:00Z"},
    {"recorded_at": "2026-01-02T00:00:00Z"},
    {"recorded_at": "2025-12-30T00:00:00Z"},
    {"features_available_at": "2025-12-31T22:00:00"},
    {"leader_start_at": "2026-03-15"},
])
def test_bad_or_future_candidate_inputs_rejected(tmp_path, change):
    row = {**record(), **change}
    with pytest.raises(ValueError):
        sealed(tmp_path, [row], k=1)


def test_duplicate_security_id_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicated"):
        sealed(tmp_path, [record("A"), record("A")], k=1)


@pytest.mark.parametrize("args", [{"k": 0}, {"k": True}, {"k": 1001},
                                 {"market": "FR"}, {"snap": "2026-08-01T00:00:00Z"},
                                 {"snap": "2026-01-01"}])
def test_invalid_protocol_parameters_rejected(tmp_path, args):
    with pytest.raises(ValueError):
        sealed(tmp_path, **args)


def test_invalid_eval_cutoffs_refused(tmp_path):
    output, _ = sealed(tmp_path)
    with pytest.raises(ValueError, match="cutoff"):
        evaluate_ranked_precision_at_k(output, None, evaluated_at="2025-12-31T00:00:00Z", clock=NOW)
    with pytest.raises(ValueError, match="cutoff"):
        evaluate_ranked_precision_at_k(output, None, evaluated_at="2026-05-01T00:00:00Z", clock=NOW)


@pytest.mark.parametrize("bad", [
    [label("A", True), label("A", False)],
    [label("A", "true")],
    [label("A", True, mature="2026-02-02T00:00:00Z", published="2026-01-31T00:00:00Z")],
    [label("A", True, mature="2026-01-05T00:00:00Z", published="2026-01-10T00:00:00Z")],
])
def test_invalid_outcome_schema_rejected(tmp_path, bad):
    output, _ = sealed(tmp_path)
    with pytest.raises(ValueError):
        measured(tmp_path, output, bad)


def test_us_exchange_local_dst_lead_day(tmp_path):
    snap = "2026-03-07T23:45:00-05:00"  # 2026-03-07 US, 2026-03-08 UTC
    candidate = record("US-X", 91,
                       available="2026-03-07T20:00:00Z",
                       calculated="2026-03-07T21:00:00Z",
                       registered="2026-03-07T22:00:00Z")
    output, _ = sealed(tmp_path, [candidate], k=1, market="US", snap=snap)
    result = measured(tmp_path, output, [label("US-X", True,
                            mature="2026-03-20T14:00:00Z", published="2026-03-21T14:00:00Z",
                            onset="2026-03-09T10:00:00-04:00")],
                      cutoff="2026-03-25T14:00:00Z")
    assert result["early_hits"] == 1 and result["median_early_lead_days"] == 2


def test_symlinked_labels_are_rejected(tmp_path):
    output, _ = sealed(tmp_path)
    labels = tmp_path/"source.json"
    labels.write_text("[]")
    symlink = tmp_path/"future_outcomes.json"
    symlink.symlink_to(labels)
    with pytest.raises(ValueError, match="linked"):
        evaluate_ranked_precision_at_k(output, symlink, evaluated_at="2026-03-01T00:00:00Z", clock=NOW)


def test_cli_freeze_and_evaluate_research_only(tmp_path, capsys):
    rows = tmp_path/"inputs.json"
    rows.write_text(json.dumps([record("A")]))
    frozen = tmp_path/"frozen.json"
    report = tmp_path/"ranked_precision_at_k_research.json"
    assert main(["freeze","--input",str(rows),"--out",str(frozen),
                 "--market","KR","--snapshot-at",SNAP,"--model-version","frozen-01",
                 "--horizon-days","30","--k","1"]) == 0
    assert frozen.is_file()
    assert main(["evaluate","--freeze",str(frozen),
                 "--evaluated-at","2026-03-01T00:00:00+00:00","--out",str(report)]) == 0
    out = json.loads(report.read_text())
    assert out["censored"] == 1 and out["precision_at_k_on_known"] is None
    assert out["official_leader_promotions"] == 0
