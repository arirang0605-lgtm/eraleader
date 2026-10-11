"""Strict local issuer/security-class identity evidence for actual WATCH gate.

Never authenticates KRX/SEC, first disclosure time, or real-market PIT.
"""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from eraleader.cli import main
from eraleader.offline_pit import OfflineLedger
from eraleader.provider_candidate_gate import audit_candidate_provider_gate
from eraleader.provider_pit_adapter import import_provider_bundle
from eraleader.local_backup import create_backup, verify_backup, restore_backup
from test_provider_pair_original_pin_gate import (
    case, orig, options, DECISION, AUDIT, NOW,
)
from test_issuer_class_bridge import fixture


def inputs(tmp_path, market="KR"):
    pair = case(tmp_path / "pair", market=market)
    _, lineage = fixture(tmp_path / "lineage", market=market)
    db = OfflineLedger.open_readonly(pair[0][0])
    try:
        members = db.snapshot(DECISION, market=market)["members"]
    finally:
        db.close()
    return pair, lineage, members


def gate(pair, lineage, members, market="KR", *, clock=AUDIT, strict=True):
    return audit_candidate_provider_gate(
        pair[0][0], pair[0][1], pair[1][0], pair[1][1],
        market=market, decision_at=DECISION,
        candidate_members=members,
        require_original_pins=strict,
        original_sources=orig(pair) if strict else None,
        issuer_lineage_file=lineage, clock=clock,
    )


def revise(lineage, edit):
    value = json.loads(lineage.read_text())
    edit(value)
    lineage.write_text(json.dumps(value, sort_keys=True))


@pytest.mark.parametrize("market,prefix", [
    ("KR", "KR:CORP00001234:ISSUE:ISSUE_A"),
    ("US", "US:CIK0000012345:CLASS:CLASS_A"),
])
def test_pinned_two_provider_watch_must_match_separate_claimed_class(
    tmp_path, market, prefix,
):
    pair, lineage, members = inputs(tmp_path, market)
    assert list(members) == [prefix]
    originals = [p for side in pair for p in (side[0], side[2], side[3])]
    originals.append(lineage)
    before = [sha256(p.read_bytes()).hexdigest() for p in originals]
    result = gate(pair, lineage, members, market)
    assert result["research_watch_allowed"] is True
    assert result["issuer_class_bridge_required"] is True
    assert result["issuer_class_matched_candidates"] == 1
    assert result["issuer_class_bridge_status"] == "LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED"
    assert len(result["issuer_class_evidence_sha256"]) == 64
    assert result["require_original_first_ingest_pins"] is True
    assert result["legal_issuer_identity_independently_verified"] is False
    assert result["official_candidate_promotion_allowed"] is False
    assert result["official_leader_promotions"] == 0
    assert prefix not in json.dumps(result)
    assert before == [sha256(p.read_bytes()).hexdigest() for p in originals]
    weak = audit_candidate_provider_gate(
        pair[0][0], pair[0][1], pair[1][0], pair[1][1],
        market=market, decision_at=DECISION,
        candidate_members=members, clock=AUDIT,
        require_original_pins=True, original_sources=orig(pair))
    assert weak["source_pair_digest_sha256"] != result["source_pair_digest_sha256"]


@pytest.mark.parametrize("edit,blocker", [
    (lambda v: v["identities"][0].update(security_id="KR:CORP99999999:ISSUE:ISSUE_A"),
     "ISSUER_CLASS_BRIDGE_TICKER_ONLY_DIFFERENT_SECURITY_CLASS"),
    (lambda v: v["identities"][0].update(ticker="CHANGED"),
     "ISSUER_CLASS_BRIDGE_SECURITY_CLASS_TICKER_CONFLICT"),
    (lambda v: v.update(retrieved_at="2026-10-11T17:00:00+09:00"),
     "ISSUER_CLASS_BRIDGE_ISSUER_LINEAGE_NOT_AVAILABLE_BY_DECISION"),
    (lambda v: v.update(publisher_id_claimed="CLAIMED_PUBLISHER_A"),
     "ISSUER_CLASS_BRIDGE_DUPLICATE_CLAIMED_PUBLISHER"),
])
def test_disagreement_or_retrospective_claim_blocks_watch(tmp_path, edit, blocker):
    pair, lineage, members = inputs(tmp_path)
    revise(lineage, edit)
    result = gate(pair, lineage, members)
    assert result["research_watch_allowed"] is False
    assert result["issuer_class_matched_candidates"] == 0
    assert result["blocker_counts"][blocker] >= 1
    assert result["official_leader_promotions"] == 0


@pytest.mark.parametrize("mutation,blocker", [
    (lambda m: m.update({"KR:CORP99999999:ISSUE:FAKE": {
        **next(iter(m.values())),
        "security_id": "KR:CORP99999999:ISSUE:FAKE",
    }}), "ISSUER_CLASS_CANDIDATE_CLASS_NOT_IN_PINNED_SOURCE"),
    (lambda m: next(iter(m.values())).update(ticker="CHANGED"),
     "ISSUER_CLASS_CANDIDATE_CLASS_MEMBERSHIP_MISMATCH"),
])
def test_class_key_and_ticker_not_joined_by_similar_names(tmp_path, mutation, blocker):
    pair, lineage, members = inputs(tmp_path)
    mutation(members)
    result = gate(pair, lineage, members)
    assert not result["research_watch_allowed"]
    assert blocker in result["blocker_counts"]


def test_without_raw_first_ingest_pin_cannot_request_lineage_gate(tmp_path):
    pair, lineage, members = inputs(tmp_path)
    with pytest.raises(ValueError, match="first-ingest PINs"):
        gate(pair, lineage, members, strict=False)


@pytest.mark.parametrize("extra", [
    ["--require-provider-issuer-class-lineage"],
    ["--provider-issuer-lineage", "MISSING.json"],
    ["--require-provider-issuer-class-lineage", "--provider-issuer-lineage", "MISSING.json"],
])
def test_cli_missing_lineage_mode_or_source_or_original_pins_fails_before_write(
    tmp_path, capsys, extra,
):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(SystemExit) as result:
        main(["offline-integrated", "--market", "KR", "--as-of", DECISION,
              "--out", str(out), *extra])
    assert result.value.code == 2
    assert "Issuer-class lineage option" in capsys.readouterr().err
    assert not (out / "offline.sqlite").exists()
    assert not (out / "runs").exists()
    assert not (out / "prospective.sqlite").exists()


def test_strict_cli_research_watch_and_backup_recovery_without_raw_data(
    tmp_path, capsys,
):
    pair, lineage, members = inputs(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    import_provider_bundle(pair[0][3], out / "offline.sqlite", clock=NOW)
    original = (out / "offline.sqlite").read_bytes()
    flags = ["--require-provider-issuer-class-lineage",
             "--provider-issuer-lineage", str(lineage)]
    main(["offline-integrated", "--market", "KR", "--as-of", DECISION,
          "--out", str(out), *options(pair), *flags])
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "OFFLINE_INTEGRATION_RESEARCH_ONLY"
    assert response["new_prospective_research_signals"] == 1
    assert response["official_leaders"] == 0
    stored = json.loads((out / "provider_candidate_gate_research.json").read_text())
    assert stored["research_watch_allowed"]
    assert stored["issuer_class_bridge_required"]
    assert stored["official_candidate_promotion_allowed"] is False
    with sqlite3.connect(out / "prospective.sqlite") as db:
        assert db.execute("SELECT count(*) FROM prospective_signals").fetchone()[0] == 1
    assert (out / "offline.sqlite").read_bytes() == original
    derived = tmp_path / "derived"
    derived.mkdir()
    filename = "provider_candidate_gate_research.json"
    (derived / filename).write_bytes((out / filename).read_bytes())
    archive = tmp_path / "verified.zip"
    create_backup(derived, archive)
    assert verify_backup(archive)["status"] == "LOCAL_BACKUP_VERIFIED"
    restore_backup(archive, tmp_path / "restored")
    assert (tmp_path / "restored" / filename).read_bytes() == (out / filename).read_bytes()
    assert str(lineage) not in (out / filename).read_text()


def test_strict_cli_bad_lineage_emits_no_candidate_watch_or_run(tmp_path, capsys):
    pair, lineage, _ = inputs(tmp_path)
    revise(lineage, lambda v: v["identities"][0].update(ticker="FAKE"))
    out = tmp_path / "out"
    out.mkdir()
    import_provider_bundle(pair[0][3], out / "offline.sqlite", clock=NOW)
    before = sha256((out / "offline.sqlite").read_bytes()).hexdigest()
    main(["offline-integrated", "--market", "KR", "--as-of", DECISION,
          "--out", str(out), *options(pair),
          "--require-provider-issuer-class-lineage",
          "--provider-issuer-lineage", str(lineage)])
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH"
    assert result["new_prospective_research_signals"] == 0
    assert not (out / "prospective.sqlite").exists()
    assert not (out / "runs").exists()
    assert not (out / "site").exists()
    assert sha256((out / "offline.sqlite").read_bytes()).hexdigest() == before


def test_lineage_revised_after_first_gate_pass_never_accepted(tmp_path, monkeypatch):
    from eraleader import provider_candidate_gate as mod
    pair, lineage, members = inputs(tmp_path)
    genuine = mod.audit_candidate_issuer_class
    calls = [0]

    def mutate_once(*args, **kwargs):
        response = genuine(*args, **kwargs)
        calls[0] += 1
        if calls[0] == 1:
            revise(lineage, lambda v: v["identities"][0].update(ticker="REVISION"))
        return response

    monkeypatch.setattr(mod, "audit_candidate_issuer_class", mutate_once)
    with pytest.raises(RuntimeError, match="revised before WATCH"):
        gate(pair, lineage, members)
    assert calls[0] == 2
