"""Same-day, no-network-by-default scheduling and crash recovery tests."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import fcntl
import json
import os
import plistlib

import pytest

from eraleader.kiwoom_investor_flow import canonical
from eraleader.kiwoom_daily_runner import run
from scripts import run_shared_kiwoom_daily
from test_kiwoom_shared_daily_batch import Gateway, setup

LATE = datetime(2026, 10, 13, 11, 20, tzinfo=timezone.utc)  # 20:20 KST
EARLY = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)   # 17:00 KST
WEEKEND = datetime(2026, 10, 17, 11, 20, tzinfo=timezone.utc)


class Demo(Gateway):
    def status(self):
        return {"configured": {"demo": True, "real": False}, "orders_enabled": False}


def fresh(tmp_path, date="20261013"):
    one, two, site = setup(tmp_path)
    basic = json.loads(one.read_text())
    basic["market_session"] = date
    basic["content_sha256"] = __import__("hashlib").sha256(canonical({
        k: v for k, v in basic.items() if k != "content_sha256"
    })).hexdigest()
    one.write_bytes(canonical(basic))
    industry = json.loads(two.read_text())
    industry["market_session"] = date
    industry["baseline_candidate_sha256"] = basic["content_sha256"]
    industry["content_sha256"] = __import__("hashlib").sha256(canonical({
        k: v for k, v in industry.items() if k != "content_sha256"
    })).hexdigest()
    two.write_bytes(canonical(industry))
    return one, two, site


def runner(root, *, clock=LATE, apply=False, codes=None, client_factory=None):
    one, two, site = root
    return run(site=site, candidates=one, industries=two,
               stock_codes=["005930", "000660"] if codes is None else codes,
               clock=clock, apply=apply, client_factory=client_factory)


def _must_not_connect():
    raise AssertionError("Network was contacted before safe readiness")


def test_old_baseline_skips_before_any_gateway_or_site_write(tmp_path):
    root = setup(tmp_path)  # baseline 2026-10-08
    before = {p.name: p.read_bytes() for p in root[2].iterdir()}
    result = runner(root, apply=True, client_factory=_must_not_connect)
    assert result["status"] == "SKIPPED_STALE_OR_FUTURE_BASELINE"
    assert {p.name: p.read_bytes() for p in root[2].iterdir()} == before


def test_weekend_and_pre_close_skip_without_auth(tmp_path):
    root = fresh(tmp_path)
    assert runner(root, clock=EARLY, apply=True,
                  client_factory=_must_not_connect)["status"] == "SKIPPED_BEFORE_CUTOFF"
    assert not (root[2] / ".kiwoom_daily_runner.lock").exists()
    weekend_root = tmp_path / "weekend"
    weekend_root.mkdir()
    weekend = fresh(weekend_root, "20261017")
    assert runner(weekend, clock=WEEKEND, apply=True,
                  client_factory=_must_not_connect)["status"] == "SKIPPED_WEEKEND"
    assert not (weekend[2] / ".kiwoom_daily_runner.lock").exists()


def test_check_mode_has_no_network_or_files_and_ready_status(tmp_path):
    root = fresh(tmp_path)
    original = list(root[2].iterdir())
    r = runner(root, apply=False, client_factory=_must_not_connect)
    assert r["status"] == "CHECK_READY_NO_NETWORK"
    assert list(root[2].iterdir()) == original
    assert r["orders_enabled"] is False


def test_apply_once_and_next_hour_reuses_immutable_evidence_no_broker(tmp_path):
    root = fresh(tmp_path)
    fake = Demo()
    outcome = runner(root, apply=True, client_factory=lambda: fake)
    assert outcome["status"] == "PUBLISHED" and outcome["requested_securities"] == 2
    assert len(fake.calls) == 2
    assert runner(root, apply=False)["status"] == "CHECK_ALREADY_PUBLISHED"
    later = datetime(2026, 10, 13, 12, 20, tzinfo=timezone.utc)
    assert runner(root, apply=True, clock=later,
                  client_factory=_must_not_connect)["status"] == "SKIPPED_ALREADY_PUBLISHED"
    assert len(fake.calls) == 2


def test_missing_main_link_repaired_without_reaccessing_provider(tmp_path):
    root = fresh(tmp_path)
    old = (root[2] / "index.html").read_bytes()
    runner(root, apply=True, client_factory=lambda: Demo())
    (root[2] / "index.html").write_bytes(old)
    assert runner(root, apply=False)["status"] == "CHECK_NEEDS_LINK_REPAIR"
    out = runner(root, apply=True, client_factory=_must_not_connect)
    assert out["status"] == "REPAIRED_MISSING_DASHBOARD_LINK"
    assert (root[2] / "index.html").read_bytes().count(b"kiwoom_daily_20261013_") == 1


def test_tampered_immutable_report_blocks_repair_and_new_requests(tmp_path):
    root = fresh(tmp_path)
    runner(root, apply=True, client_factory=lambda: Demo())
    record = next(root[2].glob("kiwoom_daily_20261013_*")) / "005930.json"
    record.write_bytes(record.read_bytes() + b" ")
    with pytest.raises(ValueError):
        runner(root, apply=True, client_factory=_must_not_connect)


def test_provider_failure_retains_no_partial_batch_and_next_try_can_succeed(tmp_path):
    root = fresh(tmp_path)
    old = (root[2] / "index.html").read_bytes()
    with pytest.raises(ValueError):
        runner(root, apply=True, client_factory=lambda: Demo(fail_code="000660"))
    assert not list(root[2].glob("kiwoom_daily_*"))
    assert (root[2] / "index.html").read_bytes() == old
    assert runner(root, apply=True, client_factory=lambda: Demo())["status"] == "PUBLISHED"


def test_orphan_stage_blocks_new_research_without_deleting_old_files(tmp_path):
    root = fresh(tmp_path)
    scratch = root[2] / ".kiwoom_daily_unaudited"
    scratch.mkdir()
    (scratch / "user_data").write_text("keep")
    with pytest.raises(ValueError, match="ORPHAN_DAILY_SCRATCH"):
        runner(root, apply=True, client_factory=_must_not_connect)
    assert (scratch / "user_data").read_text() == "keep"


def test_second_runner_sees_busy_lock_without_network(tmp_path):
    root = fresh(tmp_path)
    lock = root[2] / ".kiwoom_daily_runner.lock"
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runner(root, apply=True, client_factory=_must_not_connect)["status"] == "SKIPPED_CONCURRENT_RUN"
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_bad_owner_unsafe_lock_is_not_reused(tmp_path):
    root = fresh(tmp_path)
    lock = root[2] / ".kiwoom_daily_runner.lock"
    lock.write_text("locked")
    lock.chmod(0o644)
    with pytest.raises(ValueError, match="UNSAFE_RUNNER_LOCK"):
        runner(root, apply=True, client_factory=_must_not_connect)


@pytest.mark.parametrize("codes", [
    [], ["005930", "005930"], ["005930", "ABCDEF"],
    ["005930", "999999"], ["005930"] * 6,
])
def test_bad_cohort_denied_without_broker(tmp_path, codes):
    root = fresh(tmp_path)
    with pytest.raises(ValueError):
        runner(root, codes=codes, apply=True, client_factory=_must_not_connect)


def test_plist_only_generated_owner_private_not_loaded(tmp_path, monkeypatch):
    sandbox = tmp_path / "project"
    output = sandbox / "output"
    output.mkdir(parents=True)
    monkeypatch.setattr(run_shared_kiwoom_daily, "ROOT", sandbox)
    args = SimpleNamespace(
        site=tmp_path / "site",
        candidate_json=tmp_path / "candidates.json",
        industry_json=tmp_path / "industry.json",
        codes="005930,000660",
    )
    file = output / "opt-in.plist"
    result = run_shared_kiwoom_daily._generate_plist(file, args)
    data = plistlib.loads(file.read_bytes())
    assert result["launchd_loaded"] is False and result["file_mode"] == "0600"
    assert data["StartInterval"] == 3600
    assert "--apply" in data["ProgramArguments"]
    assert file.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        run_shared_kiwoom_daily._generate_plist(file, args)


def test_cli_default_check_only_for_stale_baseline(tmp_path, capsys):
    root = setup(tmp_path)
    args = ["--site", str(root[2]), "--candidate-json", str(root[0]),
            "--industry-json", str(root[1]), "--codes", "005930"]
    assert run_shared_kiwoom_daily.main(args) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["status"] == "SKIPPED_STALE_OR_FUTURE_BASELINE"
    assert not (root[2] / ".kiwoom_daily_runner.lock").exists()
