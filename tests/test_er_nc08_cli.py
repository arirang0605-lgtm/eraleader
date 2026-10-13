"""Pinned ER-NC-08 local operator CLI: opt-in only, zero external effects."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from test_news_theme_delivery import fixture

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/run_er_nc08_delivery.py"


def run_cli(*arguments):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, str(CLI), *map(str, arguments)],
                          cwd=ROOT, env=env, capture_output=True, text=True)


def source(tmp_path, payload=None):
    path = tmp_path / "derived_research.json"
    path.write_text(json.dumps(payload if payload is not None else fixture(),
                               ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path, sha256(path.read_bytes()).hexdigest()


def invoke(src, digest, dest):
    return run_cli("--news-enabled", "--derived-research-json", src,
                   "--expected-sha256", digest, "--new-output-root", dest)


def test_off_is_noop_without_any_source_or_output(tmp_path):
    destination = tmp_path / "never_created"
    result = run_cli("--new-output-root", destination)
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "NEWS_OFF_NO_WRITE"
    assert not destination.exists()


def test_cli_pinned_input_creates_static_bundle_and_is_idempotent(tmp_path):
    src, sha = source(tmp_path)
    root = tmp_path / "output_bundle"
    first = invoke(src, sha, root)
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["status"] == "RESEARCH_ONLY_WRITTEN"
    assert report["files_present"] == 5
    assert report["messages_sent"] == report["trades_executed"] == 0
    assert len(list(root.glob("**/*.*"))) == 5
    second = invoke(src, sha, root)
    assert second.returncode == 0
    assert json.loads(second.stdout) == report


def test_wrong_pin_fails_without_creating_files(tmp_path):
    src, sha = source(tmp_path)
    root = tmp_path / "no_output"
    result = invoke(src, "f" * 64, root)
    assert result.returncode == 2
    assert "ER_NC08_BLOCKED" in result.stderr
    assert str(src) not in result.stderr
    assert result.stdout == ""
    assert not root.exists()


def test_symlinked_source_is_rejected_without_following(tmp_path):
    src, digest = source(tmp_path)
    alias = tmp_path / "linked.json"
    alias.symlink_to(src)
    root = tmp_path / "no_output"
    result = invoke(alias, digest, root)
    assert result.returncode == 2
    assert not root.exists()


def test_json_duplicate_keys_are_rejected(tmp_path):
    path = tmp_path / "dupe.json"
    path.write_text('{"schema":"a","schema":"b"}')
    digest = sha256(path.read_bytes()).hexdigest()
    root = tmp_path / "no_output"
    result = invoke(path, digest, root)
    assert result.returncode == 2
    assert not root.exists()


def test_not_ready_author_strategy_cannot_be_forged_executable(tmp_path):
    data = fixture()
    data["author_strategies"][0]["executable"] = True
    src, digest = source(tmp_path, data)
    root = tmp_path / "no_output"
    result = invoke(src, digest, root)
    assert result.returncode == 2
    assert not root.exists()
