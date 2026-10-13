"""Atomic same-session cohort assembly; zero credentials/HTTP/trading."""
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from eraleader import official_same_session_cohort as subject
from eraleader.kiwoom_investor_flow import canonical
from test_official_kiwoom_daily_bridge import official

NOW = datetime(2026, 10, 13, 11, 20, tzinfo=timezone.utc)
DAY = "2026-10-13"


def setup(tmp_path, monkeypatch):
    source = tmp_path / "official"
    original = official(source)
    financial = tmp_path / "cfs.json"
    financial.write_bytes(canonical({
        "schema": subject.CFS_SCHEMA,
        "research_only": True,
        "official_market": {"market_session": DAY},
    }))
    industry = tmp_path / "industry.json"
    industry.write_bytes(canonical({
        "schema": subject.INDUSTRY_SCHEMA,
        "current_classification_only": True,
        "historic_industry_pit_certified": False,
    }))
    private = tmp_path / "capture"
    private.mkdir()
    out = tmp_path / "result"
    operations = []

    def basic(**kw):
        assert kw["official_source"] == source / "official_api_pit_research.json"
        assert kw["private_root"] == private
        operations.append("basic")
        target = kw["new_output"]
        target.mkdir()
        (target / "site").mkdir()
        (target / "basic_candidates_kr.json").write_bytes(canonical({
            "content_sha256": "a" * 64,
        }))
        return {"market_session": DAY, "annual_cfs_research_companies": 2}

    def peers(**kw):
        operations.append("peers")
        kw["existing_site"].joinpath("industry_peers_kr.html").write_text("research")
        kw["existing_site"].parent.joinpath("industry_peers_kr.json").write_bytes(canonical({
            "content_sha256": "b" * 64,
        }))
        return {"market_session": DAY, "companies": 2}

    def audit(root, day, now, ev, codes):
        operations.append("audit")
        assert root == out or root.name == "cohort"
        assert day == DAY
        assert ev["source_pins"]["krx-kospi"] == "a" * 64
        assert codes == ["005930", "000660"]
        assert (root / "industry_peers_kr.json").exists()
        return (root / "basic_candidates_kr.json",
                root / "industry_peers_kr.json", root / "site")

    monkeypatch.setattr(subject, "publish_basic_company_screen", basic)
    monkeypatch.setattr(subject, "publish_industry", peers)
    monkeypatch.setattr(subject, "_inspect_cohort", audit)
    opts = {
        "official_out": source, "financial_manifest": financial,
        "industry_manifest": industry, "private_root": private,
        "new_output": out, "codes": ["005930", "000660"],
        "clock": NOW,
    }
    return opts, operations, original


def test_compose_atomic_and_leave_official_original_unchanged(tmp_path, monkeypatch):
    opts, operations, _ = setup(tmp_path, monkeypatch)
    src = opts["official_out"] / "official_api_pit_research.json"
    before = src.read_bytes()
    result = subject.publish(**opts)
    assert result["status"] == "SAME_SESSION_KR_CFS_INDUSTRY_RESEARCH_PUBLISHED"
    assert result["broker_network_calls"] == 0
    assert result["investment_ranking_available"] is False
    assert result["orders_enabled"] is False
    assert operations == ["basic", "peers", "audit"]
    assert src.read_bytes() == before
    assert (opts["new_output"] / "site" / "industry_peers_kr.html").exists()
    assert not list(tmp_path.glob(".cohort_inflight_*"))


def test_second_publication_does_not_overwrite(tmp_path, monkeypatch):
    opts, operations, _ = setup(tmp_path, monkeypatch)
    subject.publish(**opts)
    with pytest.raises(ValueError, match="DESTINATION"):
        subject.publish(**opts)
    assert operations == ["basic", "peers", "audit"]


def test_late_stage_failure_cleans_only_private_scratch(tmp_path, monkeypatch):
    opts, operations, _ = setup(tmp_path, monkeypatch)
    src = opts["official_out"] / "official_api_pit_research.json"
    before = src.read_bytes()
    def failed(**kw):
        raise ValueError("INJECTED_INDUSTRY_FAILURE")
    monkeypatch.setattr(subject, "publish_industry", failed)
    with pytest.raises(ValueError, match="INJECTED"):
        subject.publish(**opts)
    assert operations == ["basic"]
    assert not opts["new_output"].exists()
    assert src.read_bytes() == before
    assert not list(tmp_path.glob(".cohort_inflight_*"))


def test_original_sha_mutation_is_rejected_before_publish(tmp_path, monkeypatch):
    opts, operations, _ = setup(tmp_path, monkeypatch)
    original_builder = subject.publish_basic_company_screen
    def mutate(**kw):
        result = original_builder(**kw)
        payload = json.loads(opts["financial_manifest"].read_text())
        payload["new_field"] = "changed"
        opts["financial_manifest"].write_bytes(canonical(payload))
        return result
    monkeypatch.setattr(subject, "publish_basic_company_screen", mutate)
    with pytest.raises(ValueError, match="ORIGINAL_EVIDENCE_CHANGED"):
        subject.publish(**opts)
    assert not opts["new_output"].exists()
    assert not list(tmp_path.glob(".cohort_inflight_*"))


@pytest.mark.parametrize("change", ["wrong_day", "invalid_code", "existing_out",
                                    "nested_output", "unsafe_symlink", "future_time"])
def test_gate_rejects_incomplete_or_unsafe_without_writes(tmp_path, monkeypatch, change):
    opts, operations, _ = setup(tmp_path, monkeypatch)
    if change == "wrong_day":
        manifest = json.loads(opts["financial_manifest"].read_text())
        manifest["official_market"]["market_session"] = "2026-10-12"
        opts["financial_manifest"].write_bytes(canonical(manifest))
    elif change == "invalid_code":
        opts["codes"] = ["005930", "ABCDEF"]
    elif change == "existing_out":
        opts["new_output"].mkdir()
    elif change == "nested_output":
        opts["new_output"] = opts["official_out"] / "new"
    elif change == "unsafe_symlink":
        link = tmp_path / "linked.json"
        link.symlink_to(opts["financial_manifest"])
        opts["financial_manifest"] = link
    elif change == "future_time":
        opts["clock"] = datetime(2026, 10, 13, 7, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        subject.publish(**opts)
    assert not operations


def test_cli_default_is_offline_and_errors_sanitized(tmp_path, monkeypatch, capsys):
    from scripts import publish_official_same_session_cohort as cli
    calls = []
    def fake(**kw):
        calls.append(kw)
        return {"status": "DONE", "orders_enabled": False}
    monkeypatch.setattr(cli, "publish", fake)
    args = ["--official-out", str(tmp_path / "official"),
            "--financial-manifest", str(tmp_path / "cfs"),
            "--industry-manifest", str(tmp_path / "industry"),
            "--private-root", str(tmp_path / "private"),
            "--out", str(tmp_path / "out"), "--codes", "005930,000660"]
    assert cli.main(args) == 0
    assert calls[0]["codes"] == ["005930", "000660"]
    assert json.loads(capsys.readouterr().out)["orders_enabled"] is False
    def deny(**kw):
        raise ValueError("PRIVATE_SECRET_SHOULD_NOT_LEAK")
    monkeypatch.setattr(cli, "publish", deny)
    assert cli.main(args) == 2
    assert "PRIVATE_SECRET" not in capsys.readouterr().err
