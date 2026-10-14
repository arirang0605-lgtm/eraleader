#!/usr/bin/env python3
"""Closed-session official KRX update -> existing WATCH/daily/web pipeline."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eraleader.official_market_incremental import update_official_market
from eraleader.data import LEGACY_DEFAULT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--existing-capture-root", type=Path, action="append", default=[])
    parser.add_argument("--through-day", default="today")
    parser.add_argument("--apply-official", action="store_true",
                        help="Allow missing official KRX read-only HTTP requests")
    parser.add_argument("--legacy-root", type=Path, default=LEGACY_DEFAULT)
    parser.add_argument("--dart-cfs-root", type=Path)
    args = parser.parse_args(argv)
    try:
        update = update_official_market(
            project=args.project, source_root=args.source_root,
            capture_root=args.capture_root,
            existing_capture_roots=tuple(args.existing_capture_root),
            through_day=args.through_day, apply_official=args.apply_official,
            legacy_root=args.legacy_root)
        if update["status"] == "KR_INCREMENTAL_ALREADY_RUNNING":
            print(json.dumps(update, sort_keys=True))
            return 0
        command = [sys.executable, str(args.project / "scripts" / "render_local_operations.py"),
                   "--project", str(args.project), "--marketwide-source-root",
                   update["source_root"], "--marketwide-watch-auto"]
        if args.dart_cfs_root is not None:
            command += ["--marketwide-watch-dart-cfs-root", str(args.dart_cfs_root)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if run.returncode:
            raise ValueError("Existing WATCH daily publication failed")
        report = json.loads(run.stdout)
        report["official_market_update"] = update
        report["external_api_calls"] = update["external_api_calls"]
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        # Never print provider URLs, credentials or raw responses on failure.
        print("KR_OFFICIAL_MARKET_DAILY_BLOCKED: source/update/WATCH publication",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
