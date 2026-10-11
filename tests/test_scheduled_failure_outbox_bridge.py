"""Opt-in scheduled failure evidence bridge: never enable delivery or install agents."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from eraleader import local_schedule, local_failure_outbox


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_local_scheduled.py"


def load_script():
    spec = importlib.util.spec_from_file_location("era_scheduled_outbox_bridge", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mocked(tmp_path, monkeypatch):
    project = tmp_path / "era-project"
    project.mkdir()
    calls = []
    result = {"status": "SKIPPED_STALE_CACHE", "messages_sent": 0, "external_api_calls": 0}

    def schedule(**kwargs):
        calls.append(("schedule", kwargs))
        return dict(result)

    def outbox(root):
        calls.append(("outbox", root))
        return {
            "status": "LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP",
            "new_events": 1,
            "total_events": 1,
            "active_local_faults": 1,
            "messages_sent": 0,
            "external_api_calls": 0,
            "official_leaders_confirmed": 0,
            "actual_future_leader_skill_certified": False,
            "local_artifacts_only": True,
        }

    monkeypatch.setattr(local_schedule, "run_scheduled", schedule)
    monkeypatch.setattr(local_schedule, "run_scheduled_watch_only", schedule)
    monkeypatch.setattr(local_schedule, "run_scheduled_maturity_only", schedule)
    monkeypatch.setattr(local_failure_outbox, "run_local_failure_outbox", outbox)
    return project, calls, schedule, outbox


def test_unflagged_scheduler_has_no_new_side_effect_or_output(mocked, capsys):
    project, calls, _, _ = mocked
    assert load_script().main(["--project", str(project)]) == 0
    assert [c[0] for c in calls] == ["schedule"]
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "SKIPPED_STALE_CACHE"
    assert "local_failure_outbox" not in data


@pytest.mark.parametrize("mode,extra", [
    ("price", []),
    ("watch", ["--watch-only", "--watch-research-config", "watch.json"]),
    ("maturity", ["--maturity-only", "--ranked-maturity-config", "ranked.json"]),
])
def test_explicit_dry_run_runs_after_selected_mode(mocked, capsys, mode, extra):
    project, calls, _, _ = mocked
    assert load_script().main([
        "--project", str(project), *extra, "--local-outbox-dry-run"
    ]) == 0
    assert [c[0] for c in calls] == ["schedule", "outbox"]
    assert calls[-1][1] == project
    data = json.loads(capsys.readouterr().out)
    assert data["schedule"]["status"] == "SKIPPED_STALE_CACHE"
    assert data["local_failure_outbox"]["status"] == "LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
    assert data["messages_sent"] == 0 and data["external_api_calls"] == 0
    assert data["official_leaders_confirmed"] == 0
    assert data["actual_future_leader_skill_certified"] is False


def test_opt_in_does_not_generate_persisted_launch_agent(mocked, tmp_path):
    project, calls, _, _ = mocked
    with pytest.raises(ValueError, match="not supported with.*generate-plist"):
        load_script().main([
            "--project", str(project), "--local-outbox-dry-run",
            "--generate-plist", str(tmp_path / "agent.plist"),
        ])
    assert calls == []
    assert not (tmp_path / "agent.plist").exists()


def test_sched_error_preserved_even_when_local_outbox_runs(mocked, monkeypatch):
    project, calls, _, _ = mocked

    def fails(**kwargs):
        calls.append(("schedule-failed", None))
        raise ValueError("scheduler-source-error")

    monkeypatch.setattr(local_schedule, "run_scheduled", fails)
    with pytest.raises(ValueError, match="scheduler-source-error"):
        load_script().main(["--project", str(project), "--local-outbox-dry-run"])
    assert [c[0] for c in calls] == ["schedule-failed", "outbox"]


def test_outbox_error_during_schedule_failure_cannot_mask_original(mocked, monkeypatch):
    project, calls, _, _ = mocked

    def fails(**kwargs):
        raise ValueError("original-source-error")

    def outbox_fails(*args):
        raise RuntimeError("outbox-damaged")

    monkeypatch.setattr(local_schedule, "run_scheduled", fails)
    monkeypatch.setattr(local_failure_outbox, "run_local_failure_outbox", outbox_fails)
    with pytest.raises(ValueError, match="original-source-error") as exc:
        load_script().main(["--project", str(project), "--local-outbox-dry-run"])
    assert "outbox-damaged" in " ".join(getattr(exc.value, "__notes__", []))


def test_outbox_error_after_scheduler_refuses_to_announce_success(mocked, monkeypatch, capsys):
    project, _, _, _ = mocked
    monkeypatch.setattr(
        local_failure_outbox, "run_local_failure_outbox",
        lambda _: (_ for _ in ()).throw(RuntimeError("backup-not-verified")),
    )
    with pytest.raises(RuntimeError, match="backup-not-verified"):
        load_script().main(["--project", str(project), "--local-outbox-dry-run"])
    assert not capsys.readouterr().out


@pytest.mark.parametrize("invalid", [
    {"status": "SKIPPED_ALREADY_RUNNING", "messages_sent": 0, "external_api_calls": 0},
    {"status": "SENT", "messages_sent": 1, "external_api_calls": 1},
    {"status": "LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP", "messages_sent": 0,
     "external_api_calls": 0, "official_leaders_confirmed": 1,
     "actual_future_leader_skill_certified": False},
])
def test_unverified_or_fake_sent_outbox_never_passes_gate(mocked, monkeypatch, invalid):
    project, _, _, _ = mocked
    monkeypatch.setattr(local_failure_outbox, "run_local_failure_outbox", lambda _: invalid)
    with pytest.raises(RuntimeError, match="dry-run.*verification|unsafe"):
        load_script().main(["--project", str(project), "--local-outbox-dry-run"])


def test_unflagged_failure_does_not_run_outbox(mocked, monkeypatch):
    project, calls, _, _ = mocked

    def fails(**kwargs):
        raise ValueError("stale data")

    monkeypatch.setattr(local_schedule, "run_scheduled", fails)
    with pytest.raises(ValueError, match="stale data"):
        load_script().main(["--project", str(project)])
    assert calls == []
