"""Atomic Kiwoom daily batch, no-rank and no-orders regression."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from eraleader.kiwoom_investor_flow import canonical
from eraleader.kiwoom_shared_daily_batch import daily_batch
from test_kiwoom_investor_flow import fixtures
from test_kiwoom_shared_research_sidecar import source

CLOCK = datetime(2026, 10, 13, 11, tzinfo=timezone.utc)


def demo_source(code, day="20261008", *, missing=False):
    item = source(day)
    item["stock_code"] = code
    if missing:
        item["foreign_net_20_sessions"] = None
        item["institution_net_20_sessions"] = None
    item["content_sha256"] = sha256(canonical({
        k: v for k, v in item.items() if k != "content_sha256"
    })).hexdigest()
    return item


class Gateway:
    project = "eraleader"
    def __init__(self, *, fail_code=None, missing_code=None):
        self.fail_code = fail_code
        self.missing_code = missing_code
        self.calls = []

    def selected_flow_research(self, **kwargs):
        code = kwargs["stock_code"]
        self.calls.append(kwargs)
        if code == self.fail_code:
            raise ValueError("PROVIDER_UNAVAILABLE")
        return demo_source(code, kwargs["day"], missing=code == self.missing_code)


def setup(tmp_path):
    basic, industry = fixtures()
    one, two = tmp_path / "candidate.json", tmp_path / "industry.json"
    one.write_bytes(canonical(basic))
    two.write_bytes(canonical(industry))
    site = tmp_path / "site"
    site.mkdir(mode=0o700)
    (site / "index.html").write_text(
        "<!doctype html><html><body>UNCHANGED_RANKING</body></html>"
    )
    return one, two, site


def run(client, root, *, codes=None, day="20261008", now=CLOCK):
    one, two, site = root
    return daily_batch(
        client=client, stock_codes=["005930", "000660"] if codes is None else codes,
        market_day=day, candidates=one, industries=two, site=site, now=now,
    )


def test_two_realistic_mock_pages_publish_once_with_each_shares_observation(tmp_path):
    root = setup(tmp_path)
    client = Gateway()
    original_index = root[2].joinpath("index.html").read_bytes()
    result = run(client, root)
    assert result["status"] == "SHARED_KIWOOM_DAILY_RESEARCH_PUBLISHED"
    assert result["companies"] == result["usable_20_observation_companies"] == 2
    assert result["orders"] == 0 and result["score_changed"] is False
    assert [c["stock_code"] for c in client.calls] == ["005930", "000660"]
    assert all(c["mode"] == "demo" and c["recent_sessions"] == 20
               and c["max_pages"] == 1 for c in client.calls)
    ledger = root[2] / result["page"]
    manifest = json.loads((ledger.parent / "report.json").read_text())
    pin = manifest.pop("content_sha256")
    assert sha256(canonical(manifest)).hexdigest() == pin
    assert manifest["investment_ranking_available"] is False
    assert manifest["historical_pit_certified"] is False
    assert manifest["orders_enabled"] is False
    assert manifest["selected_stock_count"] == 2
    assert len(list(ledger.parent.glob("*.json"))) == 3
    assert len(list(ledger.parent.glob("*.html"))) == 3
    assert "UNCHANGED_RANKING" in (root[2] / "index.html").read_text()
    assert original_index != (root[2] / "index.html").read_bytes()
    for code in ("005930", "000660"):
        row = json.loads((ledger.parent / (code + ".json")).read_text())
        assert row["orders_enabled"] is False and row["score_changed"] is False
        assert row["stock_code"] == code
    with pytest.raises(FileExistsError, match="ALREADY_PUBLISHED"):
        run(client, root)
    assert len(client.calls) == 2  # no second HTTP read on same day


def test_one_provider_failure_does_not_publish_partial_day(tmp_path):
    root = setup(tmp_path)
    original = (root[2] / "index.html").read_bytes()
    client = Gateway(fail_code="000660")
    with pytest.raises(ValueError, match="PROVIDER_UNAVAILABLE"):
        run(client, root)
    assert client.calls and len(client.calls) == 2
    assert list(root[2].glob("kiwoom_daily_*")) == []
    assert (root[2] / "index.html").read_bytes() == original


def test_one_missing_20_observations_keeps_na_and_no_trade(tmp_path):
    root = setup(tmp_path)
    result = run(Gateway(missing_code="000660"), root)
    assert result["usable_20_observation_companies"] == 1
    report = json.loads((root[2] / result["page"]).parent.joinpath("000660.json").read_text())
    assert report["foreign_net_20_shares"] is None
    assert report["institution_net_20_shares"] is None
    assert report["orders_enabled"] is False


@pytest.mark.parametrize("codes", [
    [], ["005930", "005930"], ["005930", "ABC123"],
    ["005930", "000660", "123456"], ["005930"] * 6,
])
def test_bad_or_unapproved_cohort_never_requests_broker(tmp_path, codes):
    root = setup(tmp_path)
    client = Gateway()
    with pytest.raises(ValueError):
        run(client, root, codes=codes if codes else [])
    assert not client.calls
    assert list(root[2].glob("kiwoom_daily_*")) == []


def test_future_day_rejected_before_broker_calls(tmp_path):
    root = setup(tmp_path)
    client = Gateway()
    with pytest.raises(ValueError, match="FUTURE_COHORT_DATE"):
        run(client, root, day="20261014")
    assert client.calls == []


def test_symlinked_site_and_wrong_project_rejected(tmp_path):
    root = setup(tmp_path)
    site = tmp_path / "shortcut"
    site.symlink_to(root[2], target_is_directory=True)
    client = Gateway()
    with pytest.raises(ValueError):
        run(client, (root[0], root[1], site))
    assert client.calls == []
    client.project = "coreastock"
    with pytest.raises(ValueError):
        run(client, root)
    assert client.calls == []


def test_cli_direct_script_imports_without_broker_or_secret_access():
    cmd = [sys.executable, "scripts/publish_shared_kiwoom_daily.py", "--help"]
    process = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert process.returncode == 0
    assert "--codes" in process.stdout and "--day" in process.stdout
    assert "--site" in process.stdout and not process.stderr


def test_live_receipt_is_anchored_after_all_network_responses(tmp_path):
    root = setup(tmp_path)
    class LiveGateway(Gateway):
        def selected_flow_research(self, **options):
            item = super().selected_flow_research(**options)
            stamp = datetime.now(timezone.utc).isoformat()
            item["first_gateway_received_at_utc"] = stamp
            item["decision_at_utc"] = stamp
            item["page_sha256_witnesses"][0]["gateway_first_received_at_utc"] = stamp
            item["content_sha256"] = sha256(canonical({
                k: v for k, v in item.items() if k != "content_sha256"
            })).hexdigest()
            return item
    result = run(LiveGateway(), root, now=None, codes=["005930"])
    assert result["companies"] == 1 and result["orders"] == 0
    evidence = json.loads((root[2] / result["page"]).parent.joinpath("report.json").read_text())
    selected = json.loads((root[2] / result["page"]).parent.joinpath("005930.json").read_text())
    assert selected["source_decision_at_utc"] <= evidence["run_at_utc"]


def test_atomic_rollback_on_index_link_failure(tmp_path, monkeypatch):
    root = setup(tmp_path)
    previous = (root[2] / "index.html").read_bytes()
    from eraleader import kiwoom_shared_daily_batch
    def injected(*_args):
        raise OSError("simulated local index permission failure")
    monkeypatch.setattr(kiwoom_shared_daily_batch, "_swap", injected)
    with pytest.raises(OSError):
        run(Gateway(), root)
    assert (root[2] / "index.html").read_bytes() == previous
    assert list(root[2].glob("kiwoom_daily_*")) == []
