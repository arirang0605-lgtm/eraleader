"""Real-use scheduler replay: same evidence is idempotent, changed evidence blocked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os

import pytest

from eraleader import official_latest_baseline_fallback as fallback
from eraleader.kiwoom_investor_flow import canonical
from test_official_latest_baseline_fallback import choose, archive, NOW
from test_official_kiwoom_daily_bridge import CODES


def _snapshot(folder):
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in folder.iterdir()}


def test_hourly_same_day_retry_is_read_only_even_if_gap_reason_changes(tmp_path):
    first, args = choose(tmp_path)
    previous = _snapshot(args["output"])
    args["clock"] = NOW + timedelta(minutes=55)
    args["reason"] = "WAIT_SAME_DAY_CFS_INDUSTRY_COHORT"
    assert fallback.choose_and_publish(**args) == first
    assert _snapshot(args["output"]) == previous
    assert not list(tmp_path.glob(".fallback_inflight_*"))
    assert first["broker_network_calls"] == first["official_leaders"] == 0


def test_richer_later_verified_source_requires_separate_new_output(tmp_path):
    first, args = choose(tmp_path)
    before = _snapshot(args["output"])
    # A later complete official receipt, not a fake newer filename.
    latest = archive(tmp_path, name="later", received="2026-10-13T08:20:00+00:00",
                     basic_at="2026-10-13T09:25:00+00:00",
                     industry_at="2026-10-13T09:35:00+00:00")
    args["archived_roots"].append(latest)
    with pytest.raises(ValueError, match="SOURCE_CHANGED_NEW_OUTPUT"):
        fallback.choose_and_publish(**args)
    assert _snapshot(args["output"]) == before
    args["output"] = tmp_path / "published_revised"
    new = fallback.choose_and_publish(**args)
    assert new["source_market_session"] == first["source_market_session"]
    assert new["source_candidate_sha256"] != first["source_candidate_sha256"]


@pytest.mark.parametrize("defect", ["html", "json_append", "cohort_value",
                                     "removed", "unexpected", "symlink",
                                     "public_permissions", "future_timestamp"])
def test_broken_or_replaced_output_never_reused(tmp_path, defect):
    _, args = choose(tmp_path)
    root = args["output"]
    original = _snapshot(root)
    page, report = root / "index.html", root / "report.json"
    if defect == "html":
        page.write_bytes(page.read_bytes() + b"altered")
    elif defect == "json_append":
        report.write_bytes(report.read_bytes() + b"\n")
    elif defect == "cohort_value":
        record = json.loads(report.read_bytes())
        record["selected_research_rows"][0]["name"] = "FORGED"
        record.pop("content_sha256")
        record["content_sha256"] = sha256(canonical(record)).hexdigest()
        report.write_bytes(canonical(record) + b"\n")
    elif defect == "removed":
        page.unlink()
    elif defect == "unexpected":
        (root / "extra").write_text("extra")
    elif defect == "symlink":
        original_html = root.parent / "orig.html"
        original_html.write_bytes(page.read_bytes())
        page.unlink()
        page.symlink_to(original_html)
    elif defect == "public_permissions":
        os.chmod(report, 0o644)
    elif defect == "future_timestamp":
        record = json.loads(report.read_bytes())
        record["published_at_utc"] = "2040-01-01T00:00:00+00:00"
        record.pop("content_sha256")
        record["content_sha256"] = sha256(canonical(record)).hexdigest()
        report.write_bytes(canonical(record) + b"\n")
    with pytest.raises((ValueError, OSError)):
        fallback.choose_and_publish(**args)
    assert not list(tmp_path.glob(".fallback_inflight_*"))
    assert root.exists()


def test_changing_requested_code_order_requires_explicit_separate_output(tmp_path):
    _, args = choose(tmp_path)
    old = _snapshot(args["output"])
    args["codes"] = list(reversed(CODES))
    with pytest.raises(ValueError, match="SOURCE_CHANGED_NEW_OUTPUT"):
        fallback.choose_and_publish(**args)
    assert _snapshot(args["output"]) == old


def test_replay_rejects_unregistered_reason_even_if_hash_repaired(tmp_path):
    _, args = choose(tmp_path)
    report = args["output"] / "report.json"
    record = json.loads(report.read_bytes())
    record["reason"] = "TRADING_BUY_APPROVED"
    record.pop("content_sha256")
    record["content_sha256"] = sha256(canonical(record)).hexdigest()
    report.write_bytes(canonical(record) + b"\n")
    with pytest.raises(ValueError, match="UNKNOWN_PREVIOUS_REASON"):
        fallback.choose_and_publish(**args)
