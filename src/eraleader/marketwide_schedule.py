"""6_5: Safe, opt-in launchd definition for the existing KR research refresh.

Generate-only: never installs, loads or starts a job. The generated command
uses the existing operations publisher; official updates are explicit opt-in.
"""
from __future__ import annotations

import os
import plistlib
from pathlib import Path
import stat
import sys

from .marketwide_auto_refresh import _safe_directory

LABEL = "org.eraleader.marketwide-search-research.v1"
DEFAULT_HOUR = 18
DEFAULT_MINUTE = 40


def generate_marketwide_plist(*, project: Path, source_root: Path,
                              destination: Path, hour: int = DEFAULT_HOUR,
                              minute: int = DEFAULT_MINUTE,
                              python: Path | None = None,
                              auto_watch: bool = False,
                              dart_cfs_root: Path | None = None,
                              update_official: bool = False,
                              capture_root: Path | None = None,
                              existing_capture_roots: tuple[Path, ...] = (),
                              legacy_root: Path | None = None) -> dict:
    """Write one new mode-0600 launchd plist under project/output only."""
    _safe_directory(project)
    _safe_directory(source_root)
    output = project / "output"
    _safe_directory(output)
    if type(update_official) is not bool:
        raise ValueError("KR_SCHEDULE_INVALID_OFFICIAL_UPDATE")
    if update_official:
        if not auto_watch or capture_root is None:
            raise ValueError("KR_SCHEDULE_OFFICIAL_REQUIRES_WATCH_AND_CAPTURE")
        _safe_directory(capture_root)
        for root in existing_capture_roots:
            _safe_directory(root)
        if legacy_root is not None:
            _safe_directory(legacy_root)
        if hour < 19:
            raise ValueError("KR_SCHEDULE_OFFICIAL_AFTER_19_REQUIRED")
    elif capture_root is not None or existing_capture_roots or legacy_root is not None:
        raise ValueError("KR_SCHEDULE_CAPTURE_REQUIRES_OFFICIAL_UPDATE")
    script = project / "scripts" / (
        "run_marketwide_daily.py" if update_official else "render_local_operations.py")
    if not script.is_file() or script.is_symlink():
        raise ValueError("KR_SCHEDULE_MISSING_LOCAL_RUNNER")
    if type(auto_watch) is not bool:
        raise ValueError("KR_SCHEDULE_INVALID_AUTO_WATCH")
    if dart_cfs_root is not None:
        if not auto_watch or not isinstance(dart_cfs_root, Path):
            raise ValueError("KR_SCHEDULE_DART_REQUIRES_AUTO_WATCH")
        _safe_directory(dart_cfs_root)
    if (type(hour) is not int or type(minute) is not int
            or not 0 <= hour <= 23 or not 0 <= minute <= 59):
        raise ValueError("KR_SCHEDULE_INVALID_LOCAL_TIME")
    if (not isinstance(destination, Path) or not destination.is_absolute()
            or destination.is_symlink() or destination.exists()
            or destination.parent != output or destination.suffix != ".plist"):
        raise ValueError("KR_SCHEDULE_NEW_OUTPUT_PLIST_REQUIRED")
    interpreter = python if python is not None else Path(sys.executable)
    if not isinstance(interpreter, Path) or not interpreter.is_absolute():
        raise ValueError("KR_SCHEDULE_INTERPRETER_INVALID")
    log_root = output / "verification_logs"
    if log_root.is_symlink() or (log_root.exists() and not log_root.is_dir()):
        raise ValueError("KR_SCHEDULE_LOG_ROOT_UNSAFE")
    if not log_root.exists():
        log_root.mkdir(mode=0o700)

    program_args = [
        str(interpreter), str(script), "--project", str(project),
        "--marketwide-source-root", str(source_root),
    ]
    if update_official:
        program_args = [str(interpreter), str(script), "--project", str(project),
                        "--source-root", str(source_root),
                        "--capture-root", str(capture_root), "--apply-official"]
        for root in existing_capture_roots:
            program_args.extend(["--existing-capture-root", str(root)])
        if legacy_root is not None:
            program_args.extend(["--legacy-root", str(legacy_root)])
        if dart_cfs_root is not None:
            program_args.extend(["--dart-cfs-root", str(dart_cfs_root)])
    else:
        if auto_watch:
            program_args.append("--marketwide-watch-auto")
        if dart_cfs_root is not None:
            program_args.extend(["--marketwide-watch-dart-cfs-root", str(dart_cfs_root)])
    payload = {
        "Label": LABEL,
        "ProgramArguments": program_args,
        "StartCalendarInterval": [
            {"Weekday": weekday, "Hour": hour, "Minute": minute}
            for weekday in range(1, 6)  # launchd: Mon=1 ... Fri=5
        ],
        "RunAtLoad": False,
        "ProcessType": "Background",
        "WorkingDirectory": str(project),
        "StandardOutPath": str(log_root / "kr_search_daily.log"),
        "StandardErrorPath": str(log_root / "kr_search_daily_error.log"),
    }
    body = plistlib.dumps(payload, sort_keys=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(destination, 0o600)
        # T5DATA may expose owner-only 0700 even after chmod(0600).
        # Reject any group/other access, not harmless owner execute bits.
        actual_mode=stat.S_IMODE(destination.stat().st_mode)
        if actual_mode & 0o077 or not actual_mode & 0o400:
            raise ValueError("KR_SCHEDULE_OWNER_ONLY_MODE_REQUIRED")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {
        "status": "KR_MARKETWIDE_SCHEDULE_PREPARED_NOT_INSTALLED",
        "plist_file": str(destination),
        "local_time": f"{hour:02d}:{minute:02d}",
        "weekdays": "Monday-Friday",
        "launchd_loaded": False,
        "file_mode": format(actual_mode, "04o"),
        "owner_only_access": True,
        "auto_job_installed": False,
        "orders_enabled": False,
        "market_api_calls": 0,
        "source_date_will_be_shown": True,
        "watch_daily_pipeline_enabled": auto_watch,
        "annual_cfs_source_enabled": dart_cfs_root is not None,
        "official_incremental_update_enabled": update_official,
        "market_api_calls_when_executed": "missing closed KRX sessions only" if update_official else 0,
    }
