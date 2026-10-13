#!/usr/bin/env python3
"""Opt-in Kiwoom demo daily schedule. Check-only default; never install a job."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from eraleader.kiwoom_daily_runner import run


def _generate_plist(path: Path, args) -> dict:
    # User must explicitly install/load this generated file in a separate act.
    output = (ROOT / "output").resolve()
    if (not path.is_absolute() or path.is_symlink() or path.exists()
            or path.parent.resolve() != output
            or not all(p.is_absolute() and not p.is_symlink() for p in
                       (args.site, args.candidate_json, args.industry_json))):
        raise ValueError("NEW_OUTPUT_PLIST_PATH_REQUIRED")
    command = [
        sys.executable, str(Path(__file__).resolve()), "--apply",
        "--site", str(args.site), "--candidate-json", str(args.candidate_json),
        "--industry-json", str(args.industry_json), "--codes", args.codes,
    ]
    payload = {
        "Label": "local.eraleader.kiwoom-demo-research-v1",
        "ProgramArguments": command,
        "StartInterval": 3600,
        "RunAtLoad": True,
        "ProcessType": "Background",
    }
    content = plistlib.dumps(payload, sort_keys=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o600)
    bits = stat.S_IMODE(path.stat().st_mode)
    if bits & 0o077:
        raise ValueError("PLIST_OWNER_ONLY_MODE_REQUIRED")
    return {"status": "PLIST_GENERATED_NOT_INSTALLED",
            "file_mode": format(bits, "04o"), "launchd_loaded": False,
            "interval_seconds": 3600, "orders_enabled": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--candidate-json", required=True, type=Path)
    parser.add_argument("--industry-json", required=True, type=Path)
    parser.add_argument("--codes", required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Explicitly enable demo research publication for fresh baselines")
    parser.add_argument("--generate-plist", type=Path,
                        help="Write an opt-in hourly launchd file under output; never install/load")
    args = parser.parse_args(argv)
    try:
        if args.generate_plist:
            if args.apply:
                raise ValueError("PLIST_GENERATION_AND_APPLY_CONFLICT")
            state = _generate_plist(args.generate_plist, args)
        else:
            if args.apply:
                from shared_broker_api.client import ReadOnlyClient
                factory = lambda: ReadOnlyClient("eraleader")
            else:
                factory = None
            state = run(
                site=args.site, candidates=args.candidate_json,
                industries=args.industry_json, stock_codes=args.codes.split(","),
                client_factory=factory, apply=args.apply,
            )
        print(json.dumps(state, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ImportError,
            json.JSONDecodeError):
        # Never serialize underlying provider messages or credential contents.
        print("KIWOOM_SCHEDULE_RESEARCH_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
