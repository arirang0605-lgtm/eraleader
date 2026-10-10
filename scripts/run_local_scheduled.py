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
    parser.add_argument("--generate-plist", type=Path,
                        help="Generate but do not install/load macOS launchd agent")
    parser.add_argument("--hour", type=int, default=18)
    parser.add_argument("--minute", type=int, default=10)
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.local_schedule import run_scheduled, write_launch_agent
    if args.generate_plist:
        path = write_launch_agent(args.generate_plist, python=Path(sys.executable),
                                  project=project, hour=args.hour, minute=args.minute)
        result = {"status": "PLIST_GENERATED_NOT_INSTALLED", "path": str(path)}
    else:
        result = run_scheduled(legacy=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"),
                               out=project / "output" / "scheduled",
                               control=project / "output" / "scheduler_control",
                               backups=project / "output" / "scheduler_backups",
                               max_age_days=args.max_age_days,
                               allow_stale_research=args.allow_stale_research)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"EraLeader schedule error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
