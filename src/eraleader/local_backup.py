"""Atomic, verified local backup of research outputs (never original price vault).

SQLite databases are backed up using SQLite online backup rather than copying a
potentially inconsistent live DB file. Only allowlisted artifacts are stored.
The archive is a local-only operational backup, not a Git upload.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import os
import shutil
import sqlite3
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

DB_NAMES={"state.sqlite","offline.sqlite","state_history.sqlite","prospective.sqlite",
          "peer_scores.sqlite","dry_run_alerts.sqlite",
          "provider_quality_history.sqlite","provider_quality_watchdog.sqlite"}
JSON_NAMES={"kr_latest.json","us_latest.json","batch_manifest.json",
            "baseline_research.json","alerts_preview.json","dry_run_alerts_research.json",
            "validation_research.json","walkforward_research.json",
            "prospective_kr_research.json","prospective_us_research.json",
            "total_return_crosscheck_research.json",
            "holdout_manifest.json","holdout_evaluation_research.json",
            "holdout_maturity_research.json",
            "holdout_outcome_reconciliation_research.json",
            "outcome_source_claims_research.json",
            "pit_chain_kr_research.json","pit_chain_us_research.json",
            "ranked_registry_kr_research.json","ranked_registry_us_research.json",
            "rank_score_kr_research.json","rank_score_us_research.json",
            "native_score_kr_research.json","native_score_us_research.json",
            "continuity_kr_research.json","continuity_us_research.json",
            "calendar_kr_research.json","calendar_us_research.json",
            "cash_delisting_research.json",
            "issuer_lineage_kr_research.json","issuer_lineage_us_research.json",
            "repeated_walkforward_research.json",
            "evidence_gate_kr_research.json","evidence_gate_us_research.json",
            "watch_progression_kr_research.json","watch_progression_us_research.json",
            "watch_rotation_kr_research.json","watch_rotation_us_research.json",
            "peer_score_rotation_kr_research.json","peer_score_rotation_us_research.json",
            "rotation_pair_outcomes_research.json",
            "rotation_pair_source_claims_research.json",
            "watch_operating_kr_research.json","watch_operating_us_research.json",
            "pit_provider_readiness_research.json",
            "provider_pit_import_research.json","provider_pit_asof_research.json",
            "provider_stage_normalization_research.json",
            "provider_staged_lineage_research.json",
            "provider_source_pair_research.json",
            "provider_candidate_gate_research.json",
            "ranked_outcome_receipts_research.json",
            "ranked_maturity_kr_research.json","ranked_maturity_us_research.json",
            "prospective_census_research.json",
            "issuer_class_corroboration_research.json",
            "provider_quality_history_genesis.json",
            "provider_quality_history_kr_research.json",
            "provider_quality_history_us_research.json",
            "provider_quality_watchdog_genesis.json",
            "provider_quality_alerts_research.json"}
FOLDERS={"site":{".html"},"reports":{".md"},"runs":{".json"}}
MAX_FILES=400
MAX_FILE_BYTES=40*1024*1024
MAX_ARCHIVE_INPUT=180*1024*1024
MANIFEST="MANIFEST.json"

def _valid_relative(name: str) -> bool:
    path=PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or ".." in path.parts:
        return False
    if len(path.parts)==1:
        return name in DB_NAMES | JSON_NAMES
    if len(path.parts)==2:
        return path.parts[0] in FOLDERS and path.suffix in FOLDERS[path.parts[0]]
    return False

def _selected(root: Path) -> list[Path]:
    files=[root/name for name in sorted(DB_NAMES | JSON_NAMES) if (root/name).exists()]
    for folder,suffixes in FOLDERS.items():
        sub=root/folder
        if sub.exists():
            if sub.is_symlink() or not sub.is_dir():
                raise ValueError(f"Unexpected output directory: {sub}")
            files.extend(sorted(p for p in sub.iterdir() if p.suffix in suffixes))
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Unsafe source path: {path}")
        rel=path.relative_to(root).as_posix()
        if not _valid_relative(rel):
            raise ValueError(f"Unapproved backup path: {rel}")
        if path.stat().st_size>MAX_FILE_BYTES:
            raise ValueError(f"Oversized artifact in backup: {rel}")
    if not files:
        raise ValueError("No verified output artifacts to back up")
    if len(files)>MAX_FILES:
        raise ValueError("Too many backup files")
    return files

def _database_blob(path: Path, staging: Path) -> bytes:
    temp=staging/(path.name+".consistent")
    # SQLite's backup API takes a read-consistent snapshot of the live DB.
    source=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
    destination=sqlite3.connect(temp)
    try:
        source.backup(destination, pages=128, sleep=0.05)
        check=destination.execute("PRAGMA quick_check").fetchone()[0]
        if check!="ok":
            raise ValueError(f"SQLite backup integrity failed: {path.name}")
    finally:
        destination.close()
        source.close()
    data=temp.read_bytes()
    temp.unlink()
    return data

def create_backup(output_dir: Path, archive: Path) -> dict:
    root=Path(output_dir).resolve(strict=True)
    archive=Path(archive)
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.exists():
        raise FileExistsError("Backup archive already exists; no overwriting history")
    files=_selected(root)
    with tempfile.TemporaryDirectory(prefix="eraleader-snapshot-",dir=archive.parent) as tmp:
        tmpdir=Path(tmp)
        partial=tmpdir/"backup.zip"
        metadata=[]
        total=0
        with ZipFile(partial,"w",ZIP_DEFLATED,compresslevel=6) as writer:
            for file in files:
                rel=file.relative_to(root).as_posix()
                payload=(_database_blob(file,tmpdir) if file.name in DB_NAMES
                         else file.read_bytes())
                total+=len(payload)
                if len(payload)>MAX_FILE_BYTES or total>MAX_ARCHIVE_INPUT:
                    raise ValueError("Backup size limit reached")
                digest=sha256(payload).hexdigest()
                writer.writestr(rel,payload)
                metadata.append({"path":rel,"bytes":len(payload),"sha256":digest})
            manifest={"schema_version":"eraleader.localbackup.v1",
                      "created_at":datetime.now(timezone.utc).isoformat(),
                      "files":metadata,"file_count":len(metadata),
                      "total_input_bytes":total,
                      "quality":"LOCAL_RESEARCH_SNAPSHOT_NOT_PIT_CERTIFIED"}
            writer.writestr(MANIFEST,json.dumps(manifest,ensure_ascii=False,sort_keys=True))
        verify_backup(partial)
        # Atomic publication after content and archive integrity checks.
        os.replace(partial,archive)
    return {"status":"LOCAL_BACKUP_CREATED","archive":str(archive),
            "file_count":len(metadata),"input_bytes":total}

def verify_backup(archive: Path) -> dict:
    archive=Path(archive)
    with ZipFile(archive,"r") as reader:
        names=reader.namelist()
        if names.count(MANIFEST)!=1 or len(names)!=len(set(names)):
            raise ValueError("Missing manifest or duplicate archive paths")
        extra=[name for name in names if name!=MANIFEST and not _valid_relative(name)]
        if extra:
            raise ValueError(f"Unsafe archive members: {extra[:3]}")
        manifest=json.loads(reader.read(MANIFEST))
        if manifest.get("schema_version")!="eraleader.localbackup.v1":
            raise ValueError("Unsupported backup version")
        files=manifest.get("files")
        if not isinstance(files,list) or not 0<len(files)<=MAX_FILES:
            raise ValueError("Invalid backup inventory")
        expected=[x["path"] for x in files]
        if sorted(expected)!=sorted(n for n in names if n!=MANIFEST):
            raise ValueError("Backup manifest/files mismatch")
        total=0
        for item in files:
            name=item["path"]
            if not _valid_relative(name):
                raise ValueError(f"Unsafe manifest path: {name}")
            payload=reader.read(name)
            total+=len(payload)
            if len(payload)>MAX_FILE_BYTES or total>MAX_ARCHIVE_INPUT:
                raise ValueError("Oversized decompressed backup contents")
            if len(payload)!=item["bytes"] or sha256(payload).hexdigest()!=item["sha256"]:
                raise ValueError(f"Backup hash mismatch: {name}")
        if total!=manifest["total_input_bytes"] or len(files)!=manifest["file_count"]:
            raise ValueError("Backup totals mismatch")
    return {"status":"LOCAL_BACKUP_VERIFIED","archive":str(archive),
            "file_count":len(files),"input_bytes":total}

def restore_backup(archive: Path, target: Path) -> dict:
    """Restore to a BRAND-NEW directory only. Never overwrite active outputs."""
    result=verify_backup(archive)
    target=Path(target)
    if target.exists():
        raise FileExistsError("Restore target already exists; refusing to overwrite")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".eraleader-restore-",dir=target.parent) as temp:
        staged=Path(temp)/"restored"
        staged.mkdir()
        with ZipFile(archive,"r") as reader:
            manifest=json.loads(reader.read(MANIFEST))
            for item in manifest["files"]:
                destination=staged/item["path"]
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(reader.read(item["path"]))
        # Same-parent atomic replace of a fully staged, verified tree.
        os.replace(staged,target)
    return {"status":"LOCAL_BACKUP_RESTORED","target":str(target),
            "file_count":result["file_count"]}
