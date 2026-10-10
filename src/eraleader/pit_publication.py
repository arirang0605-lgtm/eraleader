"""Immutable, recoverable local publication for opt-in KR+US PIT research.

Only a fully written and verified two-market generation is published as
current by one atomic JSON pointer replacement. This is NOT a cross-filesystem
transaction or proof of independently sourced point-in-time stock data.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable
import fcntl
import json
import os
import shutil
import sqlite3
import uuid

SCHEMA = "eraleader.pit_batch_publication.v1"
STATE_FILES = ("state.sqlite", "prospective.sqlite", "state_history.sqlite")
POINTER = "current_pit_batch.json"
RECEIPT = "PUBLISH_RECEIPT.json"


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sync_folder(folder: Path) -> None:
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sqlite_copy(source: Path, destination: Path) -> None:
    """SQLite's online backup API gives a complete read-only WAL-aware copy."""
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Missing or untrusted source SQLite: {source.name}")
    src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(destination)
        try:
            src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()


def _artifacts(directory: Path) -> list[dict]:
    result = []
    for file in sorted(directory.rglob("*")):
        if file.is_symlink():
            raise ValueError("Symlink inside PIT publication is forbidden")
        if file.is_file():
            rel = file.relative_to(directory).as_posix()
            if rel == RECEIPT:
                continue
            result.append({"name": rel, "bytes": file.stat().st_size,
                           "sha256": _hash_file(file)})
    return result


def _rebased(value: object, before: str, after: str) -> object:
    if isinstance(value, dict):
        return {key: _rebased(val, before, after) for key, val in value.items()}
    if isinstance(value, list):
        return [_rebased(item, before, after) for item in value]
    if isinstance(value, str) and (value == before or value.startswith(before + "/")):
        return after + value[len(before):]
    return value


def verify_pit_publication(root: Path) -> dict | None:
    """Only the pointer can identify a current generation; ignore orphans."""
    pointer = Path(root) / POINTER
    if not pointer.exists():
        return None
    if pointer.is_symlink() or not pointer.is_file():
        raise ValueError("Unsafe PIT publication pointer")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA:
        raise ValueError("Invalid PIT publication pointer")
    identifier = data.get("generation_id")
    if not isinstance(identifier, str) or len(identifier) != 32 or any(
            char not in "0123456789abcdef" for char in identifier):
        raise ValueError("Invalid PIT publication generation identifier")
    folder = Path(root) / "pit_generations" / identifier
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Published PIT generation missing or unsafe")
    receipt = folder / RECEIPT
    if receipt.is_symlink() or not receipt.is_file() or _hash_file(receipt) != data.get("receipt_sha256"):
        raise ValueError("PIT publication receipt checksum mismatch")
    content = json.loads(receipt.read_text(encoding="utf-8"))
    if (not isinstance(content, dict) or content.get("schema_version") != SCHEMA or
            content.get("generation_id") != identifier or
            content.get("official_leaders") != 0 or content.get("pit_certified") is not False or
            data.get("official_leaders") != 0 or data.get("pit_certified") is not False):
        raise ValueError("Invalid or falsely certified PIT publication receipt")
    claimed = content.get("artifacts")
    if not isinstance(claimed, list) or claimed != _artifacts(folder):
        raise ValueError("PIT generation artifacts changed or are missing")
    manifest = folder / "batch_manifest.json"
    if not manifest.is_file():
        raise ValueError("Published PIT batch manifest missing")
    published=json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(published, dict) or
            published.get("explicit_offline_pit_research") is not True or
            published.get("official_leaders_confirmed") != 0 or
            published.get("messages_sent") != 0 or
            published.get("external_api_calls") != 0 or
            sorted(x.get("market") for x in published.get("markets", [])) != ["KR","US"] or
            any((x.get("pit_research") or {}).get("pit_certified") is not False
                for x in published["markets"])):
        raise ValueError("Published PIT manifest is incomplete or misleading")
    return {"status": "VERIFIED_LOCAL_RESEARCH_PUBLICATION",
            "generation_id": identifier, "generation": str(folder),
            "manifest": str(manifest), "artifact_count": len(claimed),
            "official_leaders": 0, "pit_certified": False}


def _ensure_complete(stage: Path, result: dict) -> None:
    if result.get("market_count") != 2 or result.get("reports_created") != 6:
        raise ValueError("Incomplete two-market PIT research batch")
    manifest = stage / "batch_manifest.json"
    if not manifest.is_file():
        raise ValueError("PIT research manifest missing")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if (record.get("explicit_offline_pit_research") is not True or
            record.get("official_leaders_confirmed") != 0 or
            record.get("messages_sent") != 0 or
            record.get("external_api_calls") != 0 or
            sorted(x.get("market") for x in record.get("markets", [])) != ["KR", "US"]):
        raise ValueError("PIT publication must contain two non-certified markets")
    for info in record["markets"]:
        p = info.get("pit_research") or {}
        if p.get("pit_certified") is not False or p.get("official_leaders") != 0:
            raise ValueError("Uncertified PIT output attempted official promotion")
        for path in [p.get("research_dashboard"), info.get("dashboard"), *info.get("reports", [])]:
            if not isinstance(path, str) or not Path(path).is_file():
                raise ValueError("Incomplete PIT report or dashboard")
    for name in STATE_FILES:
        if not (stage / name).is_file():
            raise ValueError("Missing published PIT state ledger")


def execute_published_pit_batch(args: Namespace, execute: Callable[[Namespace], dict]) -> dict:
    """Stage all state; on failure leave previous published pointer untouched.

    Atomicity is limited to a generation-pointer switch on the same filesystem.
    Readers must use verify_pit_publication instead of scanning stale outputs.
    """
    requested=Path(args.out)
    if requested.is_symlink():
        raise ValueError("Unsafe PIT output directory")
    root = requested.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".pit_publication.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another PIT research publication is running") from exc
        previous = verify_pit_publication(root)
        source = root / "offline.sqlite"
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError("Existing trusted local offline.sqlite required")
        staging_base = root / ".pit_staging"
        versions = root / "pit_generations"
        if staging_base.is_symlink() or versions.is_symlink():
            raise ValueError("Symlinked PIT publication directories forbidden")
        staging_base.mkdir(exist_ok=True)
        versions.mkdir(exist_ok=True)
        identifier = uuid.uuid4().hex
        stage = staging_base / identifier
        dest = versions / identifier
        stage.mkdir()
        moved = False
        try:
            _sqlite_copy(source, stage / "offline.sqlite")
            old = Path(previous["generation"]) if previous else root
            for name in STATE_FILES:
                item = old / name
                if item.exists():
                    _sqlite_copy(item, stage / name)
            staged_args = Namespace(**{**vars(args), "out": str(stage)})
            result = execute(staged_args)
            _ensure_complete(stage, result)
            # Consumers of the versioned output must never see obsolete
            # temporary paths after the generation is atomically renamed.
            path = stage / "batch_manifest.json"
            content = json.loads(path.read_text(encoding="utf-8"))
            content = _rebased(content, str(stage), str(dest))
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True),
                            encoding="utf-8")
            _ensure_complete_rebased(stage, dest, content)
            receipts = {"schema_version": SCHEMA, "generation_id": identifier,
                        "artifacts": _artifacts(stage),
                        "official_leaders": 0, "pit_certified": False}
            receipt = stage / RECEIPT
            receipt.write_text(json.dumps(receipts, sort_keys=True, indent=2), encoding="utf-8")
            for file in stage.rglob("*"):
                if file.is_file():
                    with file.open("rb") as handle:
                        os.fsync(handle.fileno())
            for folder in sorted((p for p in stage.rglob("*") if p.is_dir()), reverse=True):
                _sync_folder(folder)
            _sync_folder(stage)
            os.replace(stage, dest)
            moved = True
            _sync_folder(versions)
            # This single atomic replace is the commit point.
            pointer = {"schema_version": SCHEMA, "generation_id": identifier,
                       "receipt_sha256": _hash_file(dest / RECEIPT),
                       "published_at_utc": datetime.now(timezone.utc).isoformat(),
                       "official_leaders": 0, "pit_certified": False}
            temp = root / f".pit_pointer_{identifier}.tmp"
            try:
                temp.write_text(json.dumps(pointer, sort_keys=True, indent=2), encoding="utf-8")
                with temp.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temp, root / POINTER)
                _sync_folder(root)
            finally:
                temp.unlink(missing_ok=True)
            verified = verify_pit_publication(root)
            return {**result, "status": "PUBLISHED_OFFLINE_PIT_RESEARCH_ONLY",
                    "manifest": verified["manifest"],
                    "publication_pointer": str(root / POINTER),
                    "generation": verified["generation"],
                    "official_leaders": 0, "pit_certified": False}
        finally:
            if not moved and stage.exists():
                shutil.rmtree(stage)


def _ensure_complete_rebased(stage: Path, destination: Path, record: dict) -> None:
    """Check destination paths map onto existing staged artifacts."""
    for info in record.get("markets", []):
        items = [info.get("dashboard"), *(info.get("reports") or []),
                 (info.get("pit_research") or {}).get("research_dashboard")]
        for item in items:
            if not isinstance(item, str) or not item.startswith(str(destination) + "/"):
                raise ValueError("Invalid PIT publication artifact pointer")
            equivalent = stage / item[len(str(destination)) + 1:]
            if not equivalent.is_file():
                raise ValueError("Missing PIT artifact for publication pointer")
