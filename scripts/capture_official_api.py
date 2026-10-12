#!/usr/bin/env python3
"""Opt-in official API first-receipt capture. No API keys on command line."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture official KRX/DART/SEC raw API evidence privately; no PIT promotion")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source", required=True, choices=(
        "krx-kospi", "krx-kosdaq", "dart-disclosures",
        "sec-submissions", "sec-companyfacts"))
    parser.add_argument("--market-day", help="YYYY-MM-DD for KRX/DART")
    parser.add_argument("--cik", help="SEC issuer CIK, exact numbers only")
    parser.add_argument("--out", type=Path, help="Existing 0700 private folder (default project/output/official_api_capture)")
    parser.add_argument("--credentials-file", type=Path,
                        help="Optional local owner-only 0600 key=value file, never committed")
    parser.add_argument("--check-config", action="store_true",
                        help="Check only configuration presence; makes zero API requests")
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.official_api_capture import SOURCES, credentials, _settings, capture_official_api
    if args.source not in SOURCES:
        raise ValueError("Unknown source")
    values = credentials(args.credentials_file)
    if args.check_config:
        try:
            _settings(args.source, day=args.market_day, cik=args.cik, creds=values)
            ready, reason = True, "READY_TO_REQUEST_NOT_TESTED"
        except ValueError:
            ready, reason = False, "CREDENTIAL_OR_REQUEST_ARGUMENTS_INCOMPLETE"
        print(json.dumps({"source":args.source, "status":reason,
                          "credentials_and_request_preflight_ready":ready,
                          "external_api_calls":0,
                          "first_received_data_available":False,
                          "historical_pit_certified":False},sort_keys=True))
        return 0 if ready else 2
    # Fail on missing credentials/invalid request BEFORE creating any path.
    _settings(args.source, day=args.market_day, cik=args.cik, creds=values)
    parent = args.out if args.out else project/"output"/"official_api_capture"
    parent = parent.absolute()
    if not parent.exists():
        # Create the project-owned ignored private evidence root only.
        if parent != project/"output"/"official_api_capture":
            raise ValueError("Custom capture directory must already exist")
        parent.parent.mkdir(parents=True, exist_ok=True)
        parent.mkdir(mode=0o700)
    result = capture_official_api(
        args.source, parent, day=args.market_day, cik=args.cik, creds=values)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, ValueError, KeyError, RuntimeError):
        # Never print a URL with the DART secret query parameter, key, or raw body.
        print("Official EraLeader API capture blocked; inspect configuration and source status",
              file=sys.stderr)
        raise SystemExit(2)
