"""5_5: exact pooled lead-days & censored false-discovery bounds; synthetic only."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import json

import pytest

from eraleader.prospective_census import register_census, audit_all_registered_censuses
from eraleader.ranked_outcome_receipts import audit_ranked_outcome_receipts
from test_ranked_outcome_receipts import (
    scenario, label, rewrite_doc, FROZEN, CUTOFF, NOW,
)


def cohort(folder: Path, *, market: str = "KR", labels=None):
    frozen, outcome, receipts = scenario(folder, market=market, labels=labels)
    future = {outcome: outcome.read_bytes(), receipts: receipts.read_bytes()}
    outcome.unlink()
    receipts.unlink()
    spec = frozen.parent / "census_input.json"
    spec.write_text(json.dumps([{
        "frozen": frozen.name, "definition": "leader_rule.json",
        "outcomes": outcome.name, "receipts": receipts.name,
    }]))
    return spec, (frozen, outcome, receipts), future


def populate(staged: dict[Path, bytes]):
    for file, value in staged.items():
        file.write_bytes(value)


def register(spec, directory, name):
    return register_census(spec, directory, name, clock=FROZEN + timedelta(minutes=5))


def audit(directory):
    return audit_all_registered_censuses(directory, evaluated_at=CUTOFF, clock=NOW)


def test_single_source_corroborated_lead_histogram_is_full_k_not_sample_limited(tmp_path):
    first, files, future = cohort(tmp_path, labels=[
        label("SYN-A", True, onset="2026-01-03T00:00:00+00:00"),
        label("SYN-B", True, onset="2026-01-05T00:00:00+00:00"),
    ])
    populate(future)
    result = audit_ranked_outcome_receipts(*files, evaluated_at=CUTOFF, clock=NOW,
        label_definition_file=files[0].parent/"leader_rule.json", sample_limit=1)
    assert result["source_document_matched_early_hits"] == 2
    assert result["top_k_selected_count"] == 3
    assert result["sample_truncated"] is True
    assert result["documented_early_lead_day_histogram"] == {"2": 1, "4": 1}
    assert result["median_locally_documented_lead_days"] == 3
    assert result["locally_documented_false_discovery_rate_on_known"] == 0.0


def test_exact_global_median_not_mean_of_two_cohort_medians(tmp_path):
    kr_spec, _, kr_future = cohort(tmp_path/"kr", labels=[
        label("SYN-A", True, onset="2026-01-03T00:00:00+00:00"),
        label("SYN-B", True, onset="2026-01-05T00:00:00+00:00"),
    ])
    us_spec, _, us_future = cohort(tmp_path/"us", market="US", labels=[
        label("SYN-A", True, onset="2026-01-25T00:00:00+00:00"),
        label("SYN-B", False, mature="2026-01-31T00:00:00+00:00",
              published="2026-02-01T00:00:00+00:00"),
    ])
    root = tmp_path/"registered"
    register(kr_spec, root, "census_KR.json")
    register(us_spec, root, "census_US.json")
    populate(kr_future)
    populate(us_future)
    result = audit(root)
    assert result["frozen_selected_denominator"] == 6
    assert result["locally_documented_early_hits"] == 3
    assert result["locally_documented_known_failures"] == 1
    assert result["unknown_or_censored"] == 2
    assert result["documented_early_lead_day_histogram"] == {"2": 1, "4": 1, "24": 1}
    # The overall median of [2,4,24] is 4; not (median[2,4]+median[24])/2=13.5.
    assert result["median_locally_documented_lead_days"] == 4
    assert result["false_discovery_rate_on_documented_known"] == .25
    assert result["full_frozen_k_false_discovery_floor"] == round(1/6, 6)
    assert result["full_frozen_k_false_discovery_ceiling"] == round(3/6, 6)
    assert result["real_precision_at_k"] is None
    assert result["publisher_independently_authenticated"] is False
    assert result["official_leader_promotions"] == 0


def test_no_mature_source_keeps_false_discovery_unknown_and_lead_median_null(tmp_path):
    spec, _, _ = cohort(tmp_path)
    root=tmp_path/"registry"
    register(spec, root, "census_one.json")
    report=audit(root)
    assert report["frozen_selected_denominator"] == 3
    assert report["documented_early_lead_day_histogram"] == {}
    assert report["median_locally_documented_lead_days"] is None
    assert report["false_discovery_rate_on_documented_known"] is None
    assert report["full_frozen_k_false_discovery_floor"] == 0
    assert report["full_frozen_k_false_discovery_ceiling"] == 1
    assert report["real_precision_at_k"] is None


def test_rehashed_incorrect_source_document_censors_hit_not_false_discovery(tmp_path):
    spec, files, future = cohort(tmp_path)
    root=tmp_path/"registry"
    register(spec, root, "census_a.json")
    populate(future)
    rewrite_doc(files, "SYN-A", lambda doc: doc.update(is_future_leader=False))
    report=audit(root)
    assert report["locally_documented_early_hits"] == 0
    assert report["locally_documented_known_failures"] == 1
    assert report["unknown_or_censored"] == 2
    assert report["documented_early_lead_day_histogram"] == {}
    assert report["median_locally_documented_lead_days"] is None
    assert report["false_discovery_rate_on_documented_known"] == 1.0
    assert report["full_frozen_k_false_discovery_floor"] == round(1/3, 6)
    assert report["full_frozen_k_false_discovery_ceiling"] == 1.0


def test_late_leader_onset_is_known_failed_selection_not_early_lead(tmp_path):
    spec, _, future = cohort(tmp_path, labels=[
        label("SYN-A", True, onset="2026-02-01T00:00:00+00:00"),
    ])
    root = tmp_path/"registry"
    register(spec, root, "census_one.json")
    populate(future)
    report=audit(root)
    assert report["locally_documented_early_hits"] == 0
    assert report["locally_documented_known_failures"] == 1
    assert report["unknown_or_censored"] == 2
    assert report["documented_early_lead_day_histogram"] == {}
    assert report["median_locally_documented_lead_days"] is None


@pytest.mark.parametrize("bad", [
    {"2": 2}, {"0": 1}, {"31": 1}, {"02": 1}, {"-1": 1},
    {"10": True}, {"10": -1}, {"10": 1.5},
])
def test_injected_false_source_lead_histogram_cannot_rewrite_global_results(tmp_path, monkeypatch, bad):
    from eraleader import prospective_census
    spec, _, future = cohort(tmp_path)
    root=tmp_path/"registry"
    register(spec, root, "census_one.json")
    populate(future)
    original=prospective_census.audit_ranked_outcome_receipts
    def altered(*args,**kwargs):
        result=original(*args,**kwargs)
        result["documented_early_lead_day_histogram"]=bad
        return result
    monkeypatch.setattr(prospective_census, "audit_ranked_outcome_receipts", altered)
    with pytest.raises(ValueError,match="lead|histogram|count"):
        audit(root)
