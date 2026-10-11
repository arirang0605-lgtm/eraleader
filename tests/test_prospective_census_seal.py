"""5_5: indexed census receipts; local tamper checks, not publisher attestation."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest
from test_ranked_outcome_receipts import scenario, NOW, FROZEN, CUTOFF
from eraleader.prospective_census import register_census
from eraleader.prospective_census_seal import (
    indexed_register_census, indexed_audit_censuses, _index_path,
)


def fixture(tmp_path, market="KR"):
    frozen, outcome, receipt = scenario(tmp_path, market=market)
    outcome.unlink()
    receipt.unlink()
    spec = frozen.parent / "census_input.json"
    spec.write_text(json.dumps([{
        "frozen": frozen.name, "definition": "leader_rule.json",
        "outcomes": outcome.name, "receipts": receipt.name,
    }]))
    return spec, frozen


def register(spec, root, name="census_first.json", clock=FROZEN + timedelta(minutes=3)):
    return indexed_register_census(spec, root, name, clock=clock)


def audit(root):
    return indexed_audit_censuses(root, evaluated_at=CUTOFF, clock=NOW)


def test_first_indexed_registration_and_full_denominator(tmp_path):
    spec, freeze = fixture(tmp_path)
    root = tmp_path / "registry"
    before = freeze.read_bytes()
    result = register(spec, root)
    assert result["registered_cohorts"] == 1
    assert result["receipt_index_entries"] == 1
    assert result["receipt_index_verified"] is True
    summary = audit(root)
    assert summary["frozen_selected_denominator"] == 3
    assert summary["unknown_or_censored"] == 3
    assert summary["receipt_index_entries"] == 1
    assert summary["first_write_receipts_verified"] is True
    assert summary["official_leader_promotions"] == 0
    assert summary["real_precision_at_k"] is None
    assert freeze.read_bytes() == before


def test_missing_census_file_detected_despite_original_audit_skipping_it(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    (root / "census_first.json").unlink()
    with pytest.raises(ValueError, match="index|mismatch|missing|receipt"):
        audit(root)


def test_same_valid_json_under_new_filename_not_silently_accepted(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    (root / "census_first.json").rename(root / "census_renamed.json")
    with pytest.raises(ValueError, match="index|mismatch|receipt"):
        audit(root)


def test_original_manifest_modification_detected_before_source_eval(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    p = root / "census_first.json"
    body = json.loads(p.read_text())
    body["registered_at_utc"] = "2026-01-01T00:31:00+00:00"
    from eraleader.prospective_census import _hash
    body["content_sha256"] = _hash({k: v for k, v in body.items() if k != "content_sha256"})
    p.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="index|receipt|SHA|mismatch"):
        audit(root)


def test_missing_receipt_index_cannot_silently_downgrade(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    _index_path(root).unlink()
    with pytest.raises(ValueError, match="index|missing|receipt"):
        audit(root)


def test_legacy_unindexed_registry_is_not_posthoc_certified(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register_census(spec, root, "census_legacy.json", clock=FROZEN)
    with pytest.raises(ValueError, match="index|existing|unindexed"):
        register(spec, root, "census_new.json")
    assert not (root / "census_new.json").exists()


def test_duplicate_registration_keeps_first_receipt_and_original(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    path = _index_path(root)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        register(spec, root)
    assert original == path.read_bytes()
    assert audit(root)["receipt_index_entries"] == 1


def test_second_registration_appends_new_receipt_without_overwriting(tmp_path):
    spec1, _ = fixture(tmp_path / "kr")
    spec2, _ = fixture(tmp_path / "us", market="US")
    root = tmp_path / "registry"
    register(spec1, root, "census_kr.json")
    second = register(spec2, root, "census_us.json", clock=FROZEN + timedelta(minutes=4))
    assert second["receipt_index_entries"] == 2
    summary = audit(root)
    assert summary["registry_manifest_count"] == 2
    assert summary["receipt_index_entries"] == 2
    assert summary["frozen_selected_denominator"] == 6
    assert summary["registered_market_cohort_counts"] == {"KR": 1, "US": 1}


def test_prior_receipt_chain_cannot_backdate_new_entry(tmp_path):
    spec1, _ = fixture(tmp_path / "kr")
    spec2, _ = fixture(tmp_path / "us", market="US")
    root = tmp_path / "registry"
    register(spec1, root, "census_kr.json", clock=FROZEN + timedelta(minutes=9))
    with pytest.raises(ValueError, match="backdate|older|time"):
        register(spec2, root, "census_us.json", clock=FROZEN + timedelta(minutes=5))
    assert not (root / "census_us.json").exists()


def test_sqlite_event_or_head_mutation_detected(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    with sqlite3.connect(_index_path(root)) as db:
        db.execute("UPDATE receipts SET manifest_sha256=? WHERE seq=1", ("a" * 64,))
    with pytest.raises(ValueError, match="receipt|chain|integrity|SHA|mismatch"):
        audit(root)


def test_sqlite_row_deletion_detected_with_meta_count(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    with sqlite3.connect(_index_path(root)) as db:
        db.execute("DELETE FROM receipts")
    with pytest.raises(ValueError, match="receipt|count|index"):
        audit(root)


def test_index_symlink_is_refused(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    root.mkdir()
    outside = tmp_path / "other.sqlite"
    outside.write_text("DO_NOT_CHANGE")
    _index_path(root).symlink_to(outside)
    with pytest.raises(ValueError, match="link|index|unsafe"):
        register(spec, root)
    assert outside.read_text() == "DO_NOT_CHANGE"


def test_missing_first_receipt_after_failed_transaction_blocks_future_claim(tmp_path, monkeypatch):
    import eraleader.prospective_census_seal as module
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    original = module._write_receipt

    def reject(*args, **kwargs):
        raise RuntimeError("simulated_receipt_commit_failure")

    monkeypatch.setattr(module, "_write_receipt", reject)
    with pytest.raises(RuntimeError, match="simulated"):
        register(spec, root)
    assert (root / "census_first.json").exists()  # cross-file transaction interrupted
    monkeypatch.setattr(module, "_write_receipt", original)
    with pytest.raises(ValueError, match="index|receipt|mismatch|unindexed"):
        audit(root)
    with pytest.raises(ValueError, match="index|receipt|mismatch|unindexed"):
        register(spec, root, "census_new.json")


def test_cli_register_and_audit_explicit_index_mode(tmp_path):
    spec, _ = fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_prospective_census.py"
    root = tmp_path / "registries"
    import importlib.util
    module_spec = importlib.util.spec_from_file_location("census_index_cli", script)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    # Patch clock only in the indexed API adapter to avoid synthetic future-seal claims.
    import eraleader.prospective_census_seal as module_seal
    original = module_seal.indexed_register_census
    from unittest.mock import patch
    with patch.object(module_seal, "indexed_register_census", side_effect=lambda *a, **kw: original(*a, clock=FROZEN + timedelta(minutes=3), **kw)):
        module.main(["register", "--spec", str(spec), "--registry-dir", str(root),
                     "--name", "census_first.json", "--receipt-index"])
    derived=tmp_path / "derived"
    assert module.main(["audit", "--registry-dir", str(root), "--evaluated-at", CUTOFF,
                        "--out", str(derived), "--receipt-index"])==0
    published=json.loads((derived / "prospective_census_research.json").read_text())
    assert published["receipt_index_entries"]==1
    assert published["first_write_receipts_verified"] is True
    assert published["real_precision_at_k"] is None



def test_existing_index_cannot_be_silently_bypassed_by_legacy_cli_flag(tmp_path):
    spec, _ = fixture(tmp_path)
    root = tmp_path / "registry"
    register(spec, root)
    import importlib.util
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_prospective_census.py"
    module_spec = importlib.util.spec_from_file_location("census_legacy_bypass", script)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="receipt-index"):
        module.main(["audit", "--registry-dir", str(root), "--evaluated-at", CUTOFF,
                     "--out", str(tmp_path / "unsafe_default")])
    assert not (tmp_path / "unsafe_default" / "prospective_census_research.json").exists()
