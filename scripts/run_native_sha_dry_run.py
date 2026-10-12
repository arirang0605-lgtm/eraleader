#!/usr/bin/env python3
"""Explicit offline multi-cohort original ZIP SHA DRY-RUN viewer; never sends."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="EraLeader cross-volume cohort SHA monitor")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--plan", type=Path, action="append", required=True,
                        help="Original first native plan; repeat for KR+US or multiple models")
    parser.add_argument("--witness-root", type=Path, required=True,
                        help="Separate-device SHA-only first witness directory")
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.native_sha_watchdog import run_native_sha_watchdog
    result = run_native_sha_watchdog(project, args.plan, args.witness_root)
    if (result.get("status") != "LOCAL_NATIVE_SHA_DRY_RUN_RECORDED" or
            result.get("local_artifacts_only") is not True or
            result.get("messages_sent") != 0 or result.get("external_api_calls") != 0 or
            result.get("official_leader_promotions") != 0 or
            result.get("actual_future_leader_skill_certified") is not False):
        raise RuntimeError("Unsafe native SHA watchdog summary")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("EraLeader native SHA DRY-RUN error: " + str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
