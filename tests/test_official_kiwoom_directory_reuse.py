"""Pin an already received official DART issuer directory for a KR session.

Test zero-network default and both explicit reuse and fail-closed paths.
"""
from datetime import timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from scripts import run_official_kiwoom_research as subject
from eraleader import official_dart_corp_directory as provider


def _root(tmp_path):
    root = tmp_path / "first"
    root.mkdir(mode=0o700)
    folder = root / ("dart_directory_" + ("a" * 32))
    folder.mkdir(mode=0o700)
    receipt = folder / "first_receipt.json"
    receipt.write_bytes(b"synthetic-internal-first-receipt")
    return root, folder, sha256(receipt.read_bytes()).hexdigest()


def test_exact_existing_directory_sha_reused_without_network(tmp_path, monkeypatch):
    root, folder, pin = _root(tmp_path)
    seen = []
    def verify(selected, first_sha, *, decision_at):
        seen.append((selected, first_sha, decision_at))
        return {"original_verified": True}
    monkeypatch.setattr(provider, "verify_dart_corp_directory", verify)
    assert subject.reuse_dart_directory(root, pin) == (folder, pin)
    assert len(seen) == 1
    assert seen[0][0] == folder and seen[0][1] == pin
    assert seen[0][2].tzinfo == timezone.utc


@pytest.mark.parametrize("mutate", ["missing", "malformed", "wrong_folder", "symlink"])
def test_refuse_unpinned_or_unsafe_original(tmp_path, monkeypatch, mutate):
    root, folder, pin = _root(tmp_path)
    monkeypatch.setattr(
        provider, "verify_dart_corp_directory",
        lambda *a, **kw: pytest.fail("Original should not reach verifier"))
    if mutate == "missing":
        pin = "f" * 64
    elif mutate == "malformed":
        pin = "a"
    elif mutate == "wrong_folder":
        folder.rename(root / "wrong_directory")
    else:
        (folder / "first_receipt.json").unlink()
        (folder / "first_receipt.json").symlink_to(tmp_path / "missing")
    with pytest.raises((ValueError, FileNotFoundError)):
        subject.reuse_dart_directory(root, pin)


def test_cli_rejects_directory_pin_without_explicit_capture(tmp_path, capsys, monkeypatch):
    def deny(**kwargs):
        pytest.fail("No provider operation is permitted")
    monkeypatch.setattr(subject, "advance", deny)
    args = ["--day", "2026-10-13",
            "--official-out", str(tmp_path / "output"),
            "--cohort-root", str(tmp_path / "cohort"), "--codes", "005930",
            "--dart-directory-first-sha", "a" * 64]
    assert subject.main(args) == 2
    assert "BLOCKED" in capsys.readouterr().err


def test_cli_explicit_capture_passes_reused_receipt_to_official_pipeline(
        tmp_path, monkeypatch, capsys):
    import eraleader.official_api_capture as api
    import eraleader.official_kr_daily_pipeline as pipeline

    root, folder, pin = _root(tmp_path)
    recorded = []
    monkeypatch.setattr(subject, "reuse_dart_directory",
                        lambda directory, first: (folder, pin))
    monkeypatch.setattr(api, "credentials", lambda path: {"mocked": True})
    monkeypatch.setattr(api, "KEYS", ("UNDEFINED_KEY_TEST_SENTINEL",))
    def capture_and_publish_kr_day(**kwargs):
        recorded.append(kwargs)
        return {"status": "OFFICIAL_KR_DAY_RESEARCH_ONLY",
                "market_session": "2026-10-13"}
    monkeypatch.setattr(pipeline, "capture_and_publish_kr_day",
                        capture_and_publish_kr_day)
    def advance(**kwargs):
        result = kwargs["capture_official"]()
        assert result["market_session"] == "2026-10-13"
        return {"status": "PASS_CHECK_ONLY",
                "official_pit_certified": False, "broker_orders": 0}
    monkeypatch.setattr(subject, "advance", advance)
    args = ["--day", "2026-10-13", "--official-out", str(tmp_path / "output"),
            "--cohort-root", str(tmp_path / "cohort"), "--codes", "005930",
            "--capture-root", str(root), "--capture-official",
            "--dart-directory-first-sha", pin,
            "--credentials-file", str(tmp_path / "unread-credentials")]
    assert subject.main(args) == 0
    assert json.loads(capsys.readouterr().out)["broker_orders"] == 0
    assert len(recorded) == 1
    assert recorded[0]["dart_directory"] == (folder, pin)
    assert recorded[0]["research_out"] == tmp_path / "output"
