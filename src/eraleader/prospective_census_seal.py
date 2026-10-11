"""5_5: first-write census receipt index; local integrity, no external attestation.

Strictly opt-in to preserve existing registries. Index is a separate SQLite
sidecar and binds first-written census manifests to an append-only SHA chain.
A lost sidecar, deleted manifest, orphan after a crash, or a revised manifest
fails closed. Local files/clock can still be replaced together by an attacker:
this is NOT a trusted timestamp or independent market PIT certification.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .prospective_census import (
    NAME, _root, _read, register_census, audit_all_registered_censuses,
)
from .ranked_discovery import _now, _time

SCHEMA = "eraleader.prospective_census_receipt_index.v1"
ZERO = "0" * 64
MAX_ENTRIES = 1000
FIELDS = ("seq", "registry_name", "manifest_sha256", "registered_at_utc",
          "previous_sha256")


def _index_path(root: Path) -> Path:
    root = Path(root).absolute()
    if (root.is_symlink() or root.parent.is_symlink() or
            (root.exists() and not root.is_dir())):
        raise ValueError("Unsafe or linked census index registry")
    index = root.parent / (root.name + "_receipt_index.sqlite")
    if index.is_symlink() or (index.exists() and not index.is_file()):
        raise ValueError("Unsafe or linked census receipt index")
    return index


def _digest(item: dict) -> str:
    return sha256(json.dumps(item, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _inventory(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    _root(root)
    files = {}
    for p in root.iterdir():
        if (p.is_symlink() or not p.is_file() or
                not p.name.startswith("census_") or not NAME.fullmatch(p.name)):
            raise ValueError("Unindexed or hidden census registry entry")
        files[p.name] = p
    return files


def _open(root: Path, *, create: bool) -> sqlite3.Connection:
    index = _index_path(root)
    exists = index.exists()
    if not exists and not create:
        raise ValueError("Missing original first-write census receipt index")
    if not exists and _inventory(root):
        raise ValueError("Existing unindexed census cannot acquire first-write receipts later")
    index.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(index if exists or create else ":memory:", timeout=10)
    db.row_factory = sqlite3.Row
    try:
        if not exists:
            with db:
                db.execute("""CREATE TABLE meta (
                   name TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)""")
                db.execute("""CREATE TABLE receipts (
                   seq INTEGER PRIMARY KEY NOT NULL,
                   registry_name TEXT NOT NULL UNIQUE,
                   manifest_sha256 TEXT NOT NULL,
                   registered_at_utc TEXT NOT NULL,
                   previous_sha256 TEXT NOT NULL,
                   event_sha256 TEXT NOT NULL)""")
                db.executemany("INSERT INTO meta(name,value) VALUES (?,?)", [
                    ("schema", SCHEMA), ("count", "0"), ("head", ZERO),
                ])
        return db
    except Exception:
        db.close()
        raise


def _verified_index(db: sqlite3.Connection, root: Path) -> dict:
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Corrupt local census receipt index")
        meta = dict(db.execute("SELECT name,value FROM meta").fetchall())
        if (set(meta) != {"schema", "count", "head"} or
                meta["schema"] != SCHEMA or not meta["count"].isdigit() or
                int(meta["count"]) > MAX_ENTRIES):
            raise ValueError("Invalid local census receipt index metadata")
        rows = [dict(row) for row in db.execute(
            "SELECT * FROM receipts ORDER BY seq").fetchall()]
        if len(rows) != int(meta["count"]):
            raise ValueError("Census receipt index count mismatch")
        inventory = _inventory(root)
        if set(inventory) != {r["registry_name"] for r in rows}:
            raise ValueError("Census registry/index receipt mismatch: deleted or unindexed cohort")
        previous = ZERO
        latest: datetime | None = None
        for number, row in enumerate(rows, 1):
            if (set(row) != set(FIELDS) | {"event_sha256"} or
                    type(row["seq"]) is not int or row["seq"] != number or
                    type(row["registry_name"]) is not str or
                    not row["registry_name"].startswith("census_") or
                    not NAME.fullmatch(row["registry_name"]) or
                    type(row["manifest_sha256"]) is not str or
                    len(row["manifest_sha256"]) != 64 or
                    type(row["previous_sha256"]) is not str or
                    row["previous_sha256"] != previous):
                raise ValueError("Malformed census receipt index entry")
            at = _time(row["registered_at_utc"])
            if latest is not None and at < latest:
                raise ValueError("Census receipt index clock backdated")
            latest = at
            path = inventory[row["registry_name"]]
            if sha256(path.read_bytes()).hexdigest() != row["manifest_sha256"]:
                raise ValueError("Census first-write manifest SHA/index mismatch")
            content = _read(path)
            if (not isinstance(content, dict) or
                    content.get("registered_at_utc") != row["registered_at_utc"]):
                raise ValueError("Census first-write receipt timestamp mismatch")
            body = {k: row[k] for k in FIELDS}
            if _digest(body) != row["event_sha256"]:
                raise ValueError("Census receipt SHA chain mismatch")
            previous = row["event_sha256"]
        if previous != meta["head"]:
            raise ValueError("Census receipt head SHA mismatch")
        return {"count": len(rows), "head": previous,
                "last_recorded": latest}
    except (sqlite3.DatabaseError, KeyError, TypeError, IndexError) as exc:
        raise ValueError("Invalid/corrupt census receipt index") from exc


def _write_receipt(db: sqlite3.Connection, *, name: str,
                   digest: str, registered_at: str, prior: dict) -> None:
    if prior["count"] >= MAX_ENTRIES:
        raise ValueError("Census receipt index reached maximum entries")
    instant = _time(registered_at)
    if prior["last_recorded"] is not None and instant < prior["last_recorded"]:
        raise ValueError("Cannot backdate a new census first-write receipt")
    values = {
        "seq": prior["count"] + 1,
        "registry_name": name,
        "manifest_sha256": digest,
        "registered_at_utc": registered_at,
        "previous_sha256": prior["head"],
    }
    hash_value = _digest(values)
    db.execute("""INSERT INTO receipts
        (seq,registry_name,manifest_sha256,registered_at_utc,previous_sha256,event_sha256)
        VALUES (?,?,?,?,?,?)""",
        (*[values[k] for k in FIELDS], hash_value))
    db.execute("UPDATE meta SET value=? WHERE name='count'", (str(values["seq"]),))
    db.execute("UPDATE meta SET value=? WHERE name='head'", (hash_value,))


def indexed_register_census(spec_file: Path, registry_dir: Path, name: str, *,
                            clock: datetime | None = None) -> dict:
    """Serialize first-write registration and its independent-path receipt."""
    root = Path(registry_dir).absolute()
    at = _now(clock)
    with closing(_open(root, create=True)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            prior = _verified_index(db, root)
            if prior["last_recorded"] is not None and at < prior["last_recorded"]:
                raise ValueError("Cannot backdate local first-write census receipt clock")
            # Existing register_census validates prospective seal and O_EXCL.
            result = register_census(spec_file, root, name, clock=at)
            document = root / result["registry_name"]
            raw = document.read_bytes()
            registered_at = _read(document)["registered_at_utc"]
            _write_receipt(db, name=document.name,
                           digest=sha256(raw).hexdigest(),
                           registered_at=registered_at, prior=prior)
            validated = _verified_index(db, root)
            db.commit()
        except Exception:
            db.rollback()
            # Cross-file crash can leave an orphan census manifest; NEVER
            # silently re-register/backdate or erase the original.
            raise
    return {**result, "receipt_index_entries": validated["count"],
            "receipt_index_verified": True,
            "independently_attested_timestamp": False}


def indexed_audit_censuses(registry_dir: Path, *, evaluated_at: str,
                          clock: datetime | None = None) -> dict:
    """Refuse to evaluate if any registered cohort was removed/edited."""
    root = _root(registry_dir)
    now = _now(clock)
    if _time(evaluated_at) > now:
        raise ValueError("Future census evaluation timestamp")
    with closing(_open(root, create=False)) as db:
        before = _verified_index(db, root)
    summary = audit_all_registered_censuses(
        root, evaluated_at=evaluated_at, clock=now)
    with closing(_open(root, create=False)) as db:
        after = _verified_index(db, root)
    if before != after or summary["registry_manifest_count"] != after["count"]:
        raise ValueError("Census receipt index changed during prospective evaluation")
    return {**summary,
            "receipt_index_entries": after["count"],
            "first_write_receipts_verified": True,
            "receipt_index_head_sha256": after["head"],
            "independent_timestamp_attestation": False,
            "independently_verifiable_census_exhaustiveness": False}
