"""Regression guards for off-line registered signal integrity at holdout freeze.

All timestamps, company IDs and payloads here are synthetic. Checksums
catch accidental or partial local tampering, not adversaries controlling DB
and clock or independent historical source/PIT provenance.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.frozen_holdout import freeze_registered_candidates
from eraleader.prospective import ProspectiveRegistry

RUN_DATE = "2026-04-02T11:00:00+09:00"
STAMP = datetime(2026, 4, 2, 8, tzinfo=timezone.utc)
FROZEN_AT = datetime(2026, 4, 10, tzinfo=timezone.utc)
MODEL = "synthetic-model-v1"


def _ledger(tmp_path: Path) -> Path:
    path = tmp_path / "prospective.sqlite"
    registry = ProspectiveRegistry(path)
    try:
        registry.record_integrated({
            "market": "KR", "as_of": RUN_DATE, "version": MODEL,
            "run_id": "synthetic-run", "pit_certified": False,
            "offline_provenance": ["synthetic_fixture"],
            "company_rows": [{
                "market": "KR", "security_id": "EXAMPLE-A", "as_of": RUN_DATE,
                "state": "WATCH", "full_score": None,
                "verified_future_leader_candidate": False,
                "research_growth_screen_hit": True,
            }],
        }, clock=STAMP)
    finally:
        registry.close()
    return path


def _freeze(ledger: Path, tmp_path: Path):
    return freeze_registered_candidates(
        ledger, tmp_path / "holdout_manifest.json", market="KR",
        model_version=MODEL, label_definition_id="fixed-synthetic-label-v1",
        clock=FROZEN_AT,
    )


def _tamper_basis(ledger: Path, change):
    with sqlite3.connect(ledger) as db:
        row = db.execute("SELECT payload FROM prospective_signals").fetchone()
        basis = json.loads(row[0])
        change(basis)
        updated = json.dumps(
            basis, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
        db.execute(
            "UPDATE prospective_signals SET payload=?, payload_hash=?",
            (updated, sha256(updated.encode()).hexdigest()),
        )


def test_untampered_synthetic_ledger_still_freezes(tmp_path):
    result = _freeze(_ledger(tmp_path), tmp_path)
    assert result["eligible_candidates"] == 1
    assert result["historic_pit_certified"] is False


def test_registry_payload_changed_without_rehash_rejected(tmp_path):
    ledger = _ledger(tmp_path)
    with sqlite3.connect(ledger) as db:
        db.execute("UPDATE prospective_signals SET payload='{}'")
    with pytest.raises(ValueError, match="payload hash mismatch"):
        _freeze(ledger, tmp_path)
    assert not (tmp_path / "holdout_manifest.json").exists()


@pytest.mark.parametrize("modify", [
    lambda b: b["company"].update(security_id="FAKE-ID"),
    lambda b: b.update(source_run_id="another-run"),
    lambda b: b["company"].update(state="CONFIRMED"),
    lambda b: b["company"].update(verified_future_leader_candidate=True),
    lambda b: b.update(as_of="2026-04-03T11:00:00+09:00"),
    lambda b: b["company"].update(as_of="2026-04-03T11:00:00+09:00"),
])
def test_payload_rehashed_but_identity_or_timestamp_forged_rejected(tmp_path, modify):
    ledger = _ledger(tmp_path)
    _tamper_basis(ledger, modify)
    with pytest.raises(ValueError, match="payload identity|observation timestamp"):
        _freeze(ledger, tmp_path)
    assert not (tmp_path / "holdout_manifest.json").exists()


@pytest.mark.parametrize("field,value", [
    ("signal_id", "f" * 64),
    ("kind", "PROMOTED_LEADER"),
    ("security_id", "FAKE-ID"),
])
def test_registry_outer_identity_mutation_rejected(tmp_path, field, value):
    ledger = _ledger(tmp_path)
    with sqlite3.connect(ledger) as db:
        db.execute(f"UPDATE prospective_signals SET {field}=?", (value,))
    with pytest.raises(ValueError, match="signal identity mismatch"):
        _freeze(ledger, tmp_path)
    assert not (tmp_path / "holdout_manifest.json").exists()


def test_noncanonical_payload_rehashed_still_rejected(tmp_path):
    ledger = _ledger(tmp_path)
    with sqlite3.connect(ledger) as db:
        row = db.execute("SELECT payload FROM prospective_signals").fetchone()
        altered = json.dumps(json.loads(row[0]), indent=2)
        db.execute(
            "UPDATE prospective_signals SET payload=?, payload_hash=?",
            (altered, sha256(altered.encode()).hexdigest()),
        )
    with pytest.raises(ValueError, match="not canonical"):
        _freeze(ledger, tmp_path)
