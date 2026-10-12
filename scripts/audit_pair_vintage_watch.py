#!/usr/bin/env python3
"""Local read-only, independently first-SHA-pinned pair-vintage/WATCH bridge."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare two original pinned local KR/US PIT vintages and genuine prospective WATCH screens (research only)")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--old-pair-root", required=True, type=Path)
    parser.add_argument("--old-first-sha", required=True)
    parser.add_argument("--new-pair-root", required=True, type=Path)
    parser.add_argument("--new-first-sha", required=True)
    parser.add_argument("--old-run", required=True, type=Path)
    parser.add_argument("--new-run", required=True, type=Path)
    parser.add_argument("--prospective-ledger", required=True, type=Path)
    parser.add_argument("--market", choices=("KR", "US"), required=True)
    parser.add_argument("--evaluated-at", required=True,
                        help="Timezone-aware actual evaluation cutoff; no past-replay prediction")
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.provider_pair_vintage_watch import audit_pinned_pair_vintage_watch
    result = audit_pinned_pair_vintage_watch(
        args.old_pair_root, args.old_first_sha,
        args.new_pair_root, args.new_first_sha,
        args.old_run, args.new_run, args.prospective_ledger,
        market=args.market, evaluated_at=args.evaluated_at)
    if (result["historic_pit_certified"] is not False or
            result["official_leader_promotions"] != 0 or
            result["official_leader_replacements"] != 0 or
            result["actual_prediction_accuracy_certified"] is not False or
            result["external_api_calls"] != 0 or result["messages_sent"] != 0):
        raise ValueError("Unsafe provider vintage study claimed official promotion")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, sqlite3.DatabaseError) as exc:
        # Avoid disclosing private original raw data paths, issuer IDs or keys.
        print("EraLeader pinned pair-vintage WATCH research blocked: " +
              type(exc).__name__, file=sys.stderr)
        raise SystemExit(2) from exc
