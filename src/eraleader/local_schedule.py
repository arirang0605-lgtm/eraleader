"""Fail-closed, API-free local scheduled execution for EraLeader research batches.

A scheduled run is not a real-time market signal. Never silently roll forward
a cached market date to today's date.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path
import fcntl
import json
import os
import plistlib
import sys
import uuid

from .data import LEGACY_DEFAULT
from .batch import execute_local_batch
from .local_backup import create_backup, verify_backup

def latest_cached_sessions(root: Path) -> dict[str, date]:
    """Inspect actual cache timestamps, not file modification times."""
    import pandas as pd
    kr_dir = root / "datasets/external_validation/marcap/data"
    years = sorted(kr_dir.glob("marcap-????.parquet"))
    if not years:
        raise FileNotFoundError(f"No KR cache in {kr_dir}")
    kr = pd.read_parquet(years[-1], columns=["Date"])["Date"]
    us_path = root / "datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    us = pd.read_parquet(us_path, columns=["ts"])["ts"]
    if kr.empty or us.empty:
        raise ValueError("Cached market session column is empty")
    return {"KR": pd.to_datetime(kr).max().date(),
            "US": pd.to_datetime(us).max().date()}

def run_scheduled(*, legacy: Path = LEGACY_DEFAULT, out: Path,
                  control: Path, backups: Path, today: date | None = None,
                  max_age_days: int = 10, allow_stale_research: bool = False,
                  sessions: dict[str, date] | None = None) -> dict:
    """Run at most once per cache vintage, retry on failure, verify backup.

    All paths are local. A process lock is held across analysis and backup.
    State is committed only after successful verified backup, allowing retries.
    """
    if max_age_days < 0:
        raise ValueError("max_age_days must be nonnegative")
    now = today or datetime.now().astimezone().date()
    control.mkdir(parents=True, exist_ok=True)
    with (control / "batch.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "SKIPPED_ALREADY_RUNNING"}
        seen = sessions if sessions is not None else latest_cached_sessions(legacy)
        if set(seen) != {"KR", "US"} or not all(isinstance(v, date) for v in seen.values()):
            raise ValueError("Both KR and US observed dates are required")
        dates = {k: v.isoformat() for k, v in seen.items()}
        age = {k: (now-v).days for k, v in seen.items()}
        if any(v < 0 for v in age.values()):
            raise ValueError("Cache contains observations later than local date")
        if any(v > max_age_days for v in age.values()) and not allow_stale_research:
            return {"status": "SKIPPED_STALE_CACHE", "observations": dates,
                    "age_days": age, "max_age_days": max_age_days,
                    "no_live_notifications": True}
        marker = control / "last_verified_batch.json"
        if marker.exists():
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if previous.get("observations") == dates:
                prior_archive = Path(str(previous.get("archive") or ""))
                # A successful analysis without a surviving *verified* backup
                # is not a complete scheduled cycle. Re-run and repair.
                if prior_archive.is_file():
                    try:
                        verify_backup(prior_archive)
                    except (OSError, ValueError):
                        pass
                    else:
                        return {"status": "SKIPPED_UNCHANGED_CACHE", "observations": dates,
                                "last_archive": str(prior_archive)}
        result = execute_local_batch(Namespace(
            kr_as_of=dates["KR"], us_as_of=dates["US"], days=550, top=20,
            legacy=str(legacy), out=str(out)))
        if result.get("market_count") != 2 or result.get("reports_created") != 6:
            raise RuntimeError("Incomplete KR/US batch")
        backups.mkdir(parents=True, exist_ok=True)
        archive = backups / f"eraleader_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}.zip"
        create_backup(out, archive)
        verify_backup(archive)
        record = {
            "status": "RESEARCH_ONLY_VERIFIED_BACKUP",
            "observations": dates, "age_days": age,
            "run_finished_utc": datetime.now(timezone.utc).isoformat(),
            "archive": str(archive), "dry_run_only": True,
            "used_stale_override": allow_stale_research and any(v > max_age_days for v in age.values()),
            "external_api_calls": 0, "messages_sent": 0,
        }
        tmp = control / f".verified_{uuid.uuid4().hex}.tmp"
        try:
            tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, marker)
        finally:
            tmp.unlink(missing_ok=True)
        return record

def write_launch_agent(path: Path, *, python: Path, project: Path,
                       hour: int = 18, minute: int = 10) -> Path:
    """Generate a user-level launchd definition. Does not install/load it."""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid local schedule time")
    script = project / "scripts" / "run_local_scheduled.py"
    if not script.is_file():
        raise FileNotFoundError(script)
    output = project / "output" / "scheduled"
    # launchd starts outside an interactive shell. Keep its initial working
    # directory and log endpoints on the home volume (removable SSD may
    # not be mounted or allowed during login).
    logs = Path.home() / "Library" / "Logs" / "EraLeader"
    logs.mkdir(parents=True, exist_ok=True)
    document = {
        "Label": "org.eraleader.offline-research",
        "ProgramArguments": [str(python), str(script),
                             "--project", str(project)],
        "StartCalendarInterval": [{"Weekday": day, "Hour": hour, "Minute": minute}
                                  for day in range(2, 7)],
        "RunAtLoad": True,
        "WorkingDirectory": str(Path.home()),
        "StandardOutPath": str(logs / "scheduled.log"),
        "StandardErrorPath": str(logs / "scheduled_error.log"),
        "EnvironmentVariables": {"PYTHONPATH": str(project / "src")},
        "ProcessType": "Background",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(document, sort_keys=True))
    return path
