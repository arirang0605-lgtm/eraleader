#!/usr/bin/env python3
"""Conservative KRX+DART research capture and same-session demo flow handoff.

Default is CHECK-ONLY. --capture-official performs explicitly authorized live
official requests into a new private directory; --apply-demo-flow requires a
distinct, already-complete same-day company+industry cohort.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from eraleader.official_kiwoom_daily_bridge import advance, reject_empty_live_krx


def reuse_dart_directory(private_root: Path, first_sha: str) -> tuple[Path, str]:
    """Verify the exact EXISTING current directory receipt; no live API calls."""
    from eraleader.official_dart_multi_company import _all_pinned
    from eraleader.official_dart_corp_directory import verify_dart_corp_directory
    if (type(first_sha) is not str
            or re.fullmatch(r"[a-f0-9]{64}\Z", first_sha) is None
            or not private_root.is_absolute() or private_root.is_symlink()):
        raise ValueError("EXPLICIT_VALID_CURRENT_DART_DIRECTORY_PIN_REQUIRED")
    selected = _all_pinned(private_root).get(first_sha)
    if selected is None or not selected.name.startswith("dart_directory_"):
        raise ValueError("DART_CURRENT_DIRECTORY_FIRST_PIN_MISSING")
    original = selected / "first_receipt.json"
    if (original.is_symlink() or
            sha256(original.read_bytes()).hexdigest() != first_sha):
        raise ValueError("DART_CURRENT_DIRECTORY_FIRST_PIN_CHANGED")
    verify_dart_corp_directory(selected, first_sha,
                               decision_at=datetime.now(timezone.utc))
    if sha256(original.read_bytes()).hexdigest() != first_sha:
        raise ValueError("DART_CURRENT_DIRECTORY_CHANGED_DURING_VERIFY")
    return selected, first_sha


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--day", required=True,
                   help="ISO YYYY-MM-DD or today (automatically resolves the Mac KST date)")
    p.add_argument("--official-out", type=Path, required=True)
    p.add_argument("--cohort-root", type=Path, required=True)
    p.add_argument("--codes", required=True)
    p.add_argument("--capture-official", action="store_true")
    p.add_argument("--apply-demo-flow", action="store_true")
    p.add_argument("--capture-root", type=Path,
                   help="Existing owner-only official first-receipt root; required with --capture-official")
    p.add_argument("--dart-directory-first-sha",
                   help="Reuse exact current DART issuer directory original first SHA, no extra HTTP")
    p.add_argument("--legacy-root", type=Path,
                   default=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"))
    p.add_argument("--credentials-file", type=Path)
    p.add_argument("--fallback-source", type=Path, action="append", default=[],
                   help="Explicit, previously completed price+CFS+industry research folders")
    p.add_argument("--fallback-history-dir", type=Path,
                   help="Auto-discover completed research folders in this local archive directory")
    p.add_argument("--fallback-out", type=Path,
                   help="New immutable research-only HTML+JSON directory on unavailable today")
    args = p.parse_args(argv)
    try:
        if args.day == "today":
            args.day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        def dated(path):
            # Stable daily scheduler argv may include a {date} token; a new
            # result folder is still mandatory and never overwritten.
            return (None if path is None else
                    Path(str(path).replace("{date}", args.day.replace("-", ""))))
        args.official_out = dated(args.official_out)
        args.cohort_root = dated(args.cohort_root)
        args.fallback_out = dated(args.fallback_out)
        fallback_enabled = bool(args.fallback_source or args.fallback_history_dir)
        if fallback_enabled != bool(args.fallback_out):
            raise ValueError("EXPLICIT_FALLBACK_SOURCE_AND_NEW_OUTPUT_REQUIRED")
        archives = list(args.fallback_source)
        if args.fallback_history_dir:
            from eraleader.official_latest_baseline_fallback import discover_archived_cohorts
            archives.extend(discover_archived_cohorts(args.fallback_history_dir))
        archives = list(dict.fromkeys(archives))
        capture = None
        if args.dart_directory_first_sha and not args.capture_official:
            raise ValueError("DART_DIRECTORY_PIN_REQUIRES_EXPLICIT_CAPTURE")
        if args.capture_official:
            if args.capture_root is None:
                raise ValueError("EXPLICIT_EXISTING_PRIVATE_CAPTURE_ROOT_REQUIRED")
            from eraleader.official_api_capture import credentials, KEYS, _http_get
            from eraleader.official_kr_daily_pipeline import capture_and_publish_kr_day
            directory = (reuse_dart_directory(
                args.capture_root, args.dart_directory_first_sha)
                if args.dart_directory_first_sha else None)
            file = args.credentials_file
            saved = (Path.home() / "Library/Application Support/EraLeader" /
                     "api-credentials/official_api.env")
            if file is None and not any(os.environ.get(key) for key in KEYS) and saved.is_file():
                file = saved
            def capture():
                return capture_and_publish_kr_day(
                    trading_day=args.day,
                    capture_root=args.capture_root,
                    research_out=args.official_out,
                    creds=credentials(file),
                    legacy_root=args.legacy_root,
                    dart_directory=directory,
                    fetch=lambda url, headers: reject_empty_live_krx(
                        url, headers, day=args.day, fetch=_http_get),
                )
        factory = None
        if args.apply_demo_flow:
            sys.path.insert(0, "/Volumes/T5DATA/SharedBrokerAPI/src")
            from shared_broker_api.client import ReadOnlyClient
            factory = lambda: ReadOnlyClient("eraleader")
        opts = dict(
            market_day=args.day, official_out=args.official_out,
            cohort_root=args.cohort_root, codes=args.codes.split(","),
            capture_official=capture, apply_capture=args.capture_official,
            apply_kiwoom=args.apply_demo_flow, client_factory=factory,
        )
        if fallback_enabled:
            from eraleader.official_latest_baseline_fallback import advance_with_fallback
            result = advance_with_fallback(
                **opts, archived_roots=archives,
                fallback_out=args.fallback_out)
        else:
            result = advance(**opts)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError):
        # No provider error bodies, credentials or raw data in command output.
        print("OFFICIAL_KIWOOM_DAILY_RESEARCH_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
