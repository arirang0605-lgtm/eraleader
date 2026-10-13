"""Focused fail-closed tests for ER-NC-07: research only, never real orders."""
import hashlib
import json

import pytest

from eraleader.author_strategy_rules import (
    AuthorRuleRegistry, AuthorStrategyResearch, RuleContractError, assess_all,
)

NOW = "2026-10-13T00:00:00Z"


def rule(strategy="N_ST", **overrides):
    owners = {
        "N_ST": ("남석관", "SHORT"), "N_MT": ("남석관", "MEDIUM"),
        "Y_ST": ("유목민", "SHORT"), "Y_MT": ("유목민", "MEDIUM"),
    }
    author, frame = owners.get(strategy, ("김정수", "SHORT"))
    row = {
        "rule_id": strategy + "_R1", "strategy_id": strategy,
        "author": author, "time_frame": frame,
        "source_title": "Synthetic test evidence only",
        "source_location": "TEST FIXTURE / not author original",
        "observed_publication_date": "2025-01-01",
        "selection_rule": "synthetic coverage statement",
        "entry_rule": "synthetic entry statement",
        "exit_rule": "synthetic exit statement",
        "stop_rule": "synthetic loss statement",
        "market_handling": "synthetic market statement",
        "exact_parameter": {"synthetic": True},
        "evidence_status": "NOT_VERIFIED",
        "ambiguity_note": "No confirmed original primary source",
        "strategy_version": "test-v1",
    }
    row.update(overrides)
    return row


def test_empty_registry_four_separate_author_strategy_ids():
    result = assess_all(None, None, None, None, NOW)
    assert set(result) == {"N_ST", "N_MT", "Y_ST", "Y_MT"}
    for value in result.values():
        assert value["status"] == "NOT_READY"
        assert value["trade_permission"] == "NO_ORDER"
        assert value["executable"] is False
        assert "ORIGINAL_SOURCE_RULES_MISSING" in value["reason_codes"]


def test_author_mismatch_and_excluded_author_are_rejected():
    with pytest.raises(RuleContractError):
        AuthorRuleRegistry([rule("N_ST", author="유목민")])
    with pytest.raises(RuleContractError):
        AuthorRuleRegistry([rule("K_ST")])


def test_unverified_primary_rule_is_non_executable():
    registry = AuthorRuleRegistry([rule("N_ST")])
    assessment = AuthorStrategyResearch("N_ST", registry).evaluate(None, None, None, NOW)
    assert assessment.status == "NOT_READY"
    assert "ORIGINAL_RULE_EVIDENCE_UNVERIFIED" in assessment.reason_codes
    assert assessment.trade_permission == "NO_ORDER"


def test_unreviewed_self_claimed_verified_rule_still_never_signals():
    confirmed = rule(
        evidence_status="PRIMARY_VERIFIED", ambiguity_note="",
        source_sha256="a" * 64, verified_at="2026-01-01T00:00:00Z",
    )
    result = AuthorStrategyResearch("N_ST", AuthorRuleRegistry([confirmed])).evaluate(
        None, None, None, NOW
    )
    assert result.status == "NOT_READY"
    assert "AUTHOR_IMPLEMENTATION_NOT_VALIDATED" in result.reason_codes


def test_future_publication_is_hidden_not_backdated():
    row = rule(observed_publication_date="2027-01-01")
    out = AuthorStrategyResearch("N_ST", AuthorRuleRegistry([row])).evaluate(
        None, None, None, NOW
    )
    assert out.status == "UNKNOWN"
    assert "SOURCE_NOT_PUBLIC_AT_ASOF" in out.reason_codes


def test_later_review_and_later_received_vintage_are_not_pit():
    row = rule(verified_at="2026-10-14T00:00:00Z",
               first_seen_at="2026-10-15T00:00:00Z")
    out = AuthorStrategyResearch("N_ST", AuthorRuleRegistry([row])).evaluate(
        None, None, None, NOW
    )
    assert out.status == "UNKNOWN"
    assert "SOURCE_NOT_OBSERVED_AT_ASOF" in out.reason_codes


def test_later_news_does_not_turn_author_rule_into_signal():
    reg = AuthorRuleRegistry([rule()])
    old = AuthorStrategyResearch("N_ST", reg).evaluate(
        None, None, None, NOW
    )
    new = AuthorStrategyResearch("N_ST", reg).evaluate(
        None, None, {"available_at": "2026-10-14T00:00:00Z"}, NOW
    )
    assert old.status == "NOT_READY"
    assert new.status == "UNKNOWN"
    assert "CATALYST_FUTURE_INPUT_BLOCKED" in new.reason_codes
    assert new.trade_permission == old.trade_permission == "NO_ORDER"


def test_missing_context_availability_returns_unknown():
    result = AuthorStrategyResearch("Y_ST").evaluate(
        {"score": 70}, None, None, NOW
    )
    assert result.status == "UNKNOWN"
    assert "PIT_AVAILABILITY_UNVERIFIED" in result.reason_codes


def test_later_market_input_blocked_not_treated_as_bullish():
    result = AuthorStrategyResearch("N_MT").evaluate(
        None, {"available_at": "2026-10-15T00:00:00Z"}, None, NOW
    )
    assert result.status == "UNKNOWN"
    assert result.executable is False


def test_identical_duplicate_is_idempotent_but_content_conflict_fails():
    row = rule()
    registry = AuthorRuleRegistry([row, dict(row)])
    assert len(registry.for_strategy("N_ST")) == 1
    with pytest.raises(RuleContractError, match="conflicting"):
        AuthorRuleRegistry([row, {**row, "entry_rule": "changed"}])


def test_rule_version_collision_does_not_hide_other_author():
    with pytest.raises(RuleContractError):
        AuthorRuleRegistry([rule("N_ST"), rule("Y_ST", rule_id="N_ST_R1")])


@pytest.mark.parametrize("field", [
    "entry_rule", "exit_rule", "stop_rule", "market_handling", "source_location",
])
def test_missing_original_decision_part_stays_not_ready(field):
    row = rule(**{field: ""})
    out = AuthorStrategyResearch("N_ST", AuthorRuleRegistry([row])).evaluate(
        None, None, None, NOW
    )
    assert "ORIGINAL_RULE_AMBIGUOUS" in out.reason_codes


def test_rule_string_is_never_executed_as_python(tmp_path):
    marker = tmp_path / "should-not-exist"
    payload = "__import__('pathlib').Path(" + repr(str(marker)) + ").touch()"
    row = rule(entry_rule=payload)
    out = AuthorStrategyResearch("N_ST", AuthorRuleRegistry([row])).evaluate(
        None, None, None, NOW
    )
    assert out.status == "NOT_READY"
    assert not marker.exists()


def test_json_registry_is_readonly_and_repeatable(tmp_path):
    path = tmp_path / "source.json"
    path.write_text(json.dumps({
        "schema_version": "author_rule_registry_v1", "rules": [rule("Y_MT")]
    }), encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    registry = AuthorRuleRegistry.from_file(path)
    a = AuthorStrategyResearch("Y_MT", registry).evaluate(None, None, None, NOW)
    b = AuthorStrategyResearch("Y_MT", registry).evaluate(None, None, None, NOW)
    assert a == b and a.trade_permission == "NO_ORDER"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_symlink_to_registry_is_rejected(tmp_path):
    target = tmp_path / "registry.json"
    target.write_text('{"schema_version":"author_rule_registry_v1","rules":[]}')
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(RuleContractError, match="symlink"):
        AuthorRuleRegistry.from_file(link)


def test_duplicate_json_keys_are_rejected(tmp_path):
    source = tmp_path / "duplicate.json"
    source.write_text('{"schema_version":"author_rule_registry_v1",'
                      '"rules":[],"rules":[]}')
    with pytest.raises(RuleContractError, match="duplicate"):
        AuthorRuleRegistry.from_file(source)


def test_unknown_registry_version_is_rejected(tmp_path):
    source = tmp_path / "unknown.json"
    source.write_text('{"schema_version":"future_v2","rules":[]}')
    with pytest.raises(RuleContractError, match="schema"):
        AuthorRuleRegistry.from_file(source)


def test_oversized_registry_is_rejected(tmp_path):
    source = tmp_path / "huge.json"
    source.write_bytes(b"x" * 2_000_001)
    with pytest.raises(RuleContractError, match="oversized"):
        AuthorRuleRegistry.from_file(source)


def test_naive_decision_clock_is_rejected():
    with pytest.raises(RuleContractError, match="timezone"):
        AuthorStrategyResearch("Y_MT").evaluate(None, None, None, "2026-10-13T00:00:00")


def test_source_review_timestamp_requires_timezone():
    with pytest.raises(RuleContractError, match="timezone"):
        AuthorRuleRegistry([rule(verified_at="2026-01-01T00:00:00")])


def test_news_off_on_affects_only_context_research_not_author_rule():
    records = AuthorRuleRegistry([rule("N_ST")])
    strat = AuthorStrategyResearch("N_ST", records)
    off = strat.evaluate(None, None, None, NOW)
    on = strat.evaluate(
        None, None, {"available_at": "2026-10-12T00:00:00Z"}, NOW
    )
    assert (off.status, off.trade_permission) == (on.status, on.trade_permission)
    assert off.reason_codes == on.reason_codes
