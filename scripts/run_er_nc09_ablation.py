#!/usr/bin/env python3
"""ER-NC-09: one-time pre-outcome freeze, then independently matured evaluation.

Never fetches news/market prices, accesses a broker, or modifies the original
ProspectiveRegistry/frozen holdout. Research outputs only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from eraleader.news_ablation import freeze_news_ablations, evaluate_news_ablations


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description="EraLeader frozen news-ablation research")
    commands = main.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Seal B0–B3 selections; no outcome labels")
    freeze.add_argument("--original-frozen", type=Path, required=True)
    freeze.add_argument("--context-json", type=Path, required=True)
    freeze.add_argument("--expected-context-sha256", required=True)
    freeze.add_argument("--new-output-dir", type=Path, required=True)

    evaluate = commands.add_parser("evaluate", help="Matured labels after an existing seal")
    evaluate.add_argument("--sealed-dir", type=Path, required=True)
    evaluate.add_argument("--outcomes-json", type=Path, required=True)
    evaluate.add_argument("--expected-manifest-sha256", required=True)
    evaluate.add_argument("--evaluated-at", required=True)
    evaluate.add_argument("--new-report", required=True, type=Path)
    return main


def _save_once(path: Path, result: dict) -> None:
    if (not path.is_absolute() or not path.parent.is_dir() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents) or path.exists()):
        raise ValueError("New ordinary report output is required")
    payload = (json.dumps(result, sort_keys=True, ensure_ascii=False,
                          indent=2, allow_nan=False)+"\n").encode()
    new_file = False
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        new_file = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if new_file:
            path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "freeze":
            result = freeze_news_ablations(
                args.original_frozen, args.context_json, args.new_output_dir,
                expected_context_sha256=args.expected_context_sha256,
            )
            public = {key: val for key, val in result.items() if key != "target"}
        else:
            result = evaluate_news_ablations(
                args.sealed_dir, args.outcomes_json,
                expected_manifest_sha256=args.expected_manifest_sha256,
                evaluated_at=args.evaluated_at,
            )
            _save_once(args.new_report, result)
            public = {
                "status": result["status"], "manifest_sha256": result["manifest_sha256"],
                "arm_signal_counts": {arm: result["arms"][arm]["signal_count"]
                                      for arm in ("B0", "B1", "B2", "B3")},
                "real_prospective_accuracy_certified": False,
                "report_saved": True,
            }
        print(json.dumps(public, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        # Never disclose local file paths, raw outcomes, licensed data or keys.
        print("ER_NC09_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
