"""ER-NC-06 read-only CLI: pinned input, PIT result, local-only query."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from eraleader.news_catalyst_adapter import record_sha256

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_er_nc06_research.py"


def event():
    row = {
        "schema_version": "1.0.0",
        "export_id": "er_nc06_e2e",
        "event_id": "fact.synthetic.1",
        "event_version": 1,
        "event_type": "NEW_CONTRACT",
        "published_at": "2026-10-12T08:00:00Z",
        "first_seen_at": "2026-10-12T08:10:00Z",
        "available_at": "2026-10-12T08:15:00Z",
        "verification_status": "VERIFIED",
        "novelty": "NEW",
        "catalyst_state": "CONFIRMED",
        "evidence_ids": ["witness.1"],
        "source_refs": [{"url": "https://example.org/synthetic", "source_id": "newsfeed"}],
        "related_issuer_ids": ["ISSUER.A"],
        "beneficiary_candidates": [],
        "theme_hints": ["THEME.A"],
        "model_version": "synthetic",
        "extractor_version": "synthetic",
        "data_cutoff": "2026-10-12T08:15:00Z",
        "license_profile": {
            "research_allowed": True,
            "derived_storage_allowed": True,
            "redistribution_allowed": False,
        },
        "quality_flags": [],
    }
    row["record_sha256"] = record_sha256(row)
    return row


def run(tmp_path, *, pin=None, as_of="2026-10-12T09:00:00Z", symlink=False):
    sample = tmp_path / "synthetic.jsonl"
    sample.write_text(json.dumps(event(), ensure_ascii=False) + "\n")
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    if symlink:
        alias = tmp_path / "alias.jsonl"
        alias.symlink_to(sample)
        sample = alias
    command = [
        sys.executable, str(SCRIPT), "--news-export", str(sample),
        "--expected-source-sha256", pin or digest, "--as-of", as_of,
        "--market-session", "2026-10-12",
        "--market-data-available-at", "2026-10-12T08:30:00Z",
        "--issuer-mapping-available-at", "2026-10-12T07:00:00Z",
        "--issuer-id", "ISSUER.A", "--security-id", "SHARE.A",
        "--excess-return-pct", "6.5", "--turnover-multiple", "2.8",
        "--anomaly-type", "TURNOVER_SPIKE",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)


def test_cli_pinned_synthetic_end_to_end_read_only(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "eraleader.er_nc06_local_research.v1"
    assert payload["market_diagnostic"]["diagnosis"] == "positive_news_positive_price"
    assert payload["market_diagnostic"]["event_evidence_ids"] == ["fact.synthetic.1"]
    assert payload["anomaly_local_query"]["read_only"] is True
    assert payload["anomaly_local_query"]["remote_search_permitted"] is False
    assert payload["query_cache_receipt"]["queued_unique_count"] == 1
    assert payload["network_calls"] == 0 and payload["trading_enabled"] is False
    assert "https://example.org/synthetic" not in result.stdout


def test_cli_wrong_independent_sha_fails_before_analysis(tmp_path):
    result = run(tmp_path, pin="f" * 64)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "synthetic" not in result.stderr.lower()


def test_cli_future_event_unavailable_and_never_backfilled(tmp_path):
    result = run(tmp_path, as_of="2026-10-12T08:05:00Z")
    assert result.returncode == 2  # future price vs decision as-of


def test_cli_symlinked_input_is_rejected(tmp_path):
    result = run(tmp_path, symlink=True)
    assert result.returncode == 2
    assert result.stdout == ""
