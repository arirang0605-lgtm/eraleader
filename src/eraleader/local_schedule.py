"""Fail-closed, API-free local scheduled execution for EraLeader research batches.

A scheduled run is not a real-time market signal. Never silently roll forward
a cached market date to today's date.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import plistlib
import shlex
import sys
import uuid

from .data import LEGACY_DEFAULT
from .batch import execute_local_batch
from .local_backup import create_backup, verify_backup

def active_cache_files(root: Path, *, kr_as_of: date | None = None,
                       lookback_days: int = 550) -> dict[str, Path]:
    """Exact read-only cache paths, including EVERY KR year used by batch."""
    kr_dir = root / "datasets/external_validation/marcap/data"
    years = sorted(kr_dir.glob("marcap-????.parquet"))
    if not years:
        raise FileNotFoundError(f"No KR cache in {kr_dir}")
    us_path = root / "datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
    if kr_as_of is None:
        return {"KR": years[-1], "US": us_path}
    start_year = (kr_as_of - timedelta(days=lookback_days)).year
    result = {"US": us_path}
    for year in range(start_year, kr_as_of.year + 1):
        result[f"KR-{year}"] = kr_dir / f"marcap-{year}.parquet"
    return result

def latest_cache_fingerprints(root: Path, *, kr_as_of: date) -> dict[str, str]:
    """Hash actual source bytes, not mtime, file size or most-recent session.

    Detect corrected/historically restated cached files without exporting raw
    market data. Never follow symlinks or silently accept missing/empty files.
    """
    answer = {}
    for market, path in active_cache_files(root, kr_as_of=kr_as_of).items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"Untrusted/missing {market} source cache file")
        digest = sha256()
        with path.open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk)
        answer[market] = digest.hexdigest()
    return answer

def latest_cached_sessions(root: Path) -> dict[str, date]:
    """Inspect actual cache timestamps, not file modification times."""
    import pandas as pd
    sources = active_cache_files(root)
    kr = pd.read_parquet(sources["KR"], columns=["Date"])["Date"]
    us = pd.read_parquet(sources["US"], columns=["ts"])["ts"]
    if kr.empty or us.empty:
        raise ValueError("Cached market session column is empty")
    return {"KR": pd.to_datetime(kr).max().date(),
            "US": pd.to_datetime(us).max().date()}

def run_scheduled(*, legacy: Path = LEGACY_DEFAULT, out: Path,
                  control: Path, backups: Path, today: date | None = None,
                  max_age_days: int = 10, allow_stale_research: bool = False,
                  sessions: dict[str, date] | None = None,
                  input_fingerprints: dict[str, str] | None = None) -> dict:
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
        live_files = sessions is None
        seen = sessions if sessions is not None else latest_cached_sessions(legacy)
        if set(seen) != {"KR", "US"} or not all(type(v) is date for v in seen.values()):
            raise ValueError("Both KR and US observed dates are required")
        dates = {k: v.isoformat() for k, v in seen.items()}
        age = {k: (now-v).days for k, v in seen.items()}
        if any(v < 0 for v in age.values()):
            raise ValueError("Cache contains observations later than local date")
        if any(v > max_age_days for v in age.values()) and not allow_stale_research:
            return {"status": "SKIPPED_STALE_CACHE", "observations": dates,
                    "age_days": age, "max_age_days": max_age_days,
                    "no_live_notifications": True}
        # A date-only checkpoint is insufficient: a vendor can correct old
        # closes, splits or bars without changing its latest session date.
        fingerprints = (input_fingerprints if input_fingerprints is not None else
                        latest_cache_fingerprints(legacy, kr_as_of=seen["KR"])
                        if live_files else None)
        if fingerprints is not None and (not fingerprints or
                any(not isinstance(k, str) or not k or
                    not (k == "US" or k == "KR" or k.startswith("KR-"))
                    for k in fingerprints) or
                not any(k.startswith("KR") for k in fingerprints) or
                "US" not in fingerprints or
                any(not isinstance(v, str) or len(v) != 64 or
                    any(c not in "0123456789abcdef" for c in v)
                    for v in fingerprints.values())):
            raise ValueError("KR/US immutable SHA256 source fingerprints required")
        marker = control / "last_verified_batch.json"
        if marker.exists():
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if (previous.get("observations") == dates and
                    previous.get("cache_sha256") == fingerprints):
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
        # A file revision DURING a long analysis may mix two cache vintages.
        # Do not create a trusted checkpoint/backup in that case.
        if live_files and (latest_cached_sessions(legacy) != seen or
                           latest_cache_fingerprints(legacy, kr_as_of=seen["KR"]) != fingerprints):
            raise RuntimeError("Input cache was revised during scheduled analysis")
        backups.mkdir(parents=True, exist_ok=True)
        archive = backups / f"eraleader_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}_{uuid.uuid4().hex[:8]}.zip"
        create_backup(out, archive)
        verify_backup(archive)
        # A correction during ZIP creation must not be marked as a stable
        # source vintage either. The archive may remain for investigation,
        # but the successful checkpoint is never advanced.
        if live_files and (latest_cached_sessions(legacy) != seen or
                           latest_cache_fingerprints(legacy, kr_as_of=seen["KR"]) != fingerprints):
            raise RuntimeError("Input cache was revised during scheduled backup")
        record = {
            "status": "RESEARCH_ONLY_VERIFIED_BACKUP",
            "observations": dates, "age_days": age,
            "cache_sha256": fingerprints,
            "source_files_verified_during_run": live_files,
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
                       hour: int = 18, minute: int = 10,
                       bootstrap_path: Path | None = None) -> Path:
    """Generate a user-level launchd definition and SSD-safe home bootstrap.

    Does not install/load the agent. The stable home bootstrap can exit 0
    while a removable SSD is missing, then retry on next launchd interval.
    """
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid local schedule time")
    script = project / "scripts" / "run_local_scheduled.py"
    if not script.is_file():
        raise FileNotFoundError(script)
    # launchd launches this small durable shell script from the home volume.
    # A missing external volume is not a fatal agent configuration error.
    helper = (Path(bootstrap_path) if bootstrap_path is not None else
              Path.home() / "Library" / "Application Support" / "EraLeader" / "offline-launcher.sh")
    if helper.is_symlink() or helper.parent.is_symlink():
        raise ValueError("Symlink launcher paths are not allowed")
    helper.parent.mkdir(parents=True, exist_ok=True)
    unavailable = "SKIPPED_EXTERNAL_SSD_UNAVAILABLE"
    quoted_script = shlex.quote(str(script))
    quoted_project = shlex.quote(str(project))
    quoted_python = shlex.quote(str(python))
    quoted_cache = shlex.quote(str(LEGACY_DEFAULT))
    bootstrap = chr(10).join([
        "#!/bin/sh",
        f"if [ ! -f {quoted_script} ] || [ ! -d {quoted_cache} ]; then",
        f"  echo {unavailable}",
        "  exit 0",
        "fi",
        f"exec {quoted_python} {quoted_script} --project {quoted_project}",
        ""
    ])
    temp = helper.with_name(f".{helper.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(bootstrap, encoding="utf-8")
        temp.chmod(0o700)
        os.replace(temp, helper)
    finally:
        temp.unlink(missing_ok=True)
    logs = Path.home() / "Library" / "Logs" / "EraLeader"
    logs.mkdir(parents=True, exist_ok=True)
    document = {
        "Label": "org.eraleader.offline-research",
        "ProgramArguments": ["/bin/sh", str(helper)],
        "StartInterval": 3600,
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
