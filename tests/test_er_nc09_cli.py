"""ER-NC-09 CLI uses only pinned files, sealed pre-outcome membership."""
import json
import os
from pathlib import Path
import subprocess
import sys

from test_news_ablation import (
    EVAL, EVAL_CLOCK, prepare, source,
)
from test_frozen_holdout import freeze, outcomes_file

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/run_er_nc09_ablation.py"


def call(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )


def test_actual_cli_freeze_seals_once_and_never_opens_outcome_file(tmp_path):
    freeze(tmp_path)
    context, digest = source(tmp_path)
    target = tmp_path / "fresh_scenarios"
    cmd = ("freeze", "--original-frozen", tmp_path/"holdout_manifest.json",
           "--context-json", context, "--expected-context-sha256", digest,
           "--new-output-dir", target)
    first = call(*cmd)
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["B0_equals_B1"] is True
    assert report["outcome_labels_seen"] is False
    assert report["B4_B5"] == "NOT_READY"
    assert not (target / "future_outcomes.json").exists()
    assert (target / "ablation_manifest.json").exists()
    second = call(*cmd)
    assert second.returncode == 2
    assert "ER_NC09_BLOCKED" in second.stderr


def test_cli_evaluate_writes_single_dry_run_research_report(tmp_path):
    directory, receipt = prepare(tmp_path)
    outcomes = outcomes_file(tmp_path)
    report = tmp_path / "evaluation.json"
    cmd = ("evaluate", "--sealed-dir", directory,
           "--outcomes-json", outcomes,
           "--expected-manifest-sha256", receipt["manifest_sha256"],
           "--evaluated-at", EVAL, "--new-report", report)
    first = call(*cmd)
    assert first.returncode == 0, first.stderr
    output = json.loads(first.stdout)
    assert output["report_saved"] is True
    assert output["arm_signal_counts"] == {"B0":4, "B1":4, "B2":2, "B3":1}
    assert output["real_prospective_accuracy_certified"] is False
    saved = json.loads(report.read_text())
    assert saved["B4"]["status"] == "NOT_READY"
    assert saved["statistical_improvement_claimed"] is False
    assert oct(report.stat().st_mode & 0o777) == "0o600"
    second = call(*cmd)
    assert second.returncode == 2
    assert json.loads(report.read_text()) == saved


def test_evaluate_cli_wrong_manifest_sha_does_not_create_report(tmp_path):
    directory, _ = prepare(tmp_path)
    label = outcomes_file(tmp_path)
    target = tmp_path / "not_written.json"
    result = call(
        "evaluate", "--sealed-dir", directory, "--outcomes-json", label,
        "--expected-manifest-sha256", "f"*64, "--evaluated-at", EVAL,
        "--new-report", target,
    )
    assert result.returncode == 2
    assert not target.exists()
    assert str(label) not in result.stderr and str(directory) not in result.stderr


def test_freeze_cli_bad_sha_does_not_make_artifacts(tmp_path):
    freeze(tmp_path)
    context, pin = source(tmp_path)
    target = tmp_path / "should_not_exist"
    result = call(
        "freeze", "--original-frozen", tmp_path/"holdout_manifest.json",
        "--context-json", context,
        "--expected-context-sha256", "f"*64, "--new-output-dir", target,
    )
    assert result.returncode == 2
    assert not target.exists()
    assert result.stdout == ""
