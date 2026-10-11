#!/usr/bin/env python3
"""Local research scheduler entrypoint; no network and no live alerts."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

def main(argv=None):
    parser = argparse.ArgumentParser(description="EraLeader offline scheduled research")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=10)
    parser.add_argument("--allow-stale-research", action="store_true",
                        help="Research only: explicitly process aged existing caches")
    parser.add_argument("--watch-research-config", type=Path,
                        help="Opt-in local KR+US WATCH ledger/model pins (no APIs or live alerts)")
    parser.add_argument("--watch-max-age-days", type=int, default=7,
                        help="Strict maximum age of locally registered WATCH evidence")
    parser.add_argument("--watch-only", action="store_true",
                        help="Run only KR/US local WATCH briefs, independently of stale price caches")
    parser.add_argument("--generate-plist", type=Path,
                        help="Generate but do not install/load macOS launchd agent")
    parser.add_argument("--hour", type=int, default=18)
    parser.add_argument("--minute", type=int, default=10)
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.local_schedule import (
        run_scheduled, run_scheduled_watch_only, write_launch_agent,
    )
    if args.watch_only and args.watch_research_config is None:
        raise ValueError("WATCH-only mode requires explicit --watch-research-config")
    if args.generate_plist:
        path = write_launch_agent(args.generate_plist, python=Path(sys.executable),
                                  project=project, hour=args.hour, minute=args.minute,
                                  watch_research_config=args.watch_research_config,
                                  watch_max_age_days=args.watch_max_age_days,
                                  watch_only=args.watch_only)
        result = {"status": "PLIST_GENERATED_NOT_INSTALLED", "path": str(path)}
    elif args.watch_only:
        result = run_scheduled_watch_only(
            out=project / "output" / "scheduled_watch",
            control=project / "output" / "scheduler_watch_control",
            backups=project / "output" / "scheduler_watch_backups",
            watch_research_config=args.watch_research_config,
            watch_max_age_days=args.watch_max_age_days,
        )
    else:
        result = run_scheduled(legacy=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"),
                               out=project / "output" / "scheduled",
                               control=project / "output" / "scheduler_control",
                               backups=project / "output" / "scheduler_backups",
                               max_age_days=args.max_age_days,
                               allow_stale_research=args.allow_stale_research,
                               watch_research_config=args.watch_research_config,
                               watch_max_age_days=args.watch_max_age_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"EraLeader schedule error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
