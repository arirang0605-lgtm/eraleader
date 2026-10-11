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
    parser.add_argument("--ranked-maturity-config", type=Path,
                        help="Opt-in KR/US first-written native Top-K cohort paths (no outcome labels)")
    parser.add_argument("--maturity-only", action="store_true",
                        help="Run only sealed Top-K maturity daily/weekly/monthly research briefs")
    parser.add_argument("--maturity-sample-limit", type=int, default=100,
                        help="Rows displayed, not the frozen Top-K denominator")
    parser.add_argument("--local-outbox-dry-run", action="store_true",
                        help="Opt-in after-run local evidence incidents; NEVER transmit or install")
    parser.add_argument("--generate-plist", type=Path,
                        help="Generate but do not install/load macOS launchd agent")
    parser.add_argument("--hour", type=int, default=18)
    parser.add_argument("--minute", type=int, default=10)
    args = parser.parse_args(argv)
    project = args.project.resolve(strict=True)
    sys.path.insert(0, str(project / "src"))
    from eraleader.local_schedule import (
        run_scheduled, run_scheduled_watch_only, run_scheduled_maturity_only,
        write_launch_agent,
    )
    if args.watch_only and args.watch_research_config is None:
        raise ValueError("WATCH-only mode requires explicit --watch-research-config")
    if args.maturity_only and args.watch_only:
        raise ValueError("WATCH-only and maturity-only schedule modes cannot be mixed")
    if (args.maturity_only and args.ranked_maturity_config is None):
        raise ValueError("Maturity-only requires explicit --ranked-maturity-config")
    if (args.ranked_maturity_config is not None and not args.maturity_only):
        raise ValueError("Maturity sources require explicit --maturity-only mode")
    if args.maturity_only and args.watch_research_config is not None:
        raise ValueError("Maturity-only must not silently use unrelated WATCH-only config")
    if args.maturity_only and args.allow_stale_research:
        raise ValueError("Maturity-only never enables stale price-cache overrides")
    if args.generate_plist and args.local_outbox_dry_run:
        raise ValueError("Local outbox dry-run is not supported with --generate-plist")

    def run_and_audit(job):
        # Existing scheduler behavior is untouched unless explicitly opted in.
        if not args.local_outbox_dry_run:
            return job()
        from eraleader.local_failure_outbox import run_local_failure_outbox
        try:
            scheduled = job()
        except Exception as primary_error:
            # Read existing checkpoints even after a schedule exception, but
            # never turn an unverified outbox result into scheduler success.
            try:
                run_local_failure_outbox(project)
            except Exception as audit_error:
                primary_error.add_note(f"Local outbox audit also failed: {audit_error}")
            raise
        if (not isinstance(scheduled, dict)
                or scheduled.get("status") == "SKIPPED_ALREADY_RUNNING"
                or scheduled.get("messages_sent", 0) != 0
                or scheduled.get("external_api_calls", 0) != 0):
            raise RuntimeError("Unsafe or concurrent scheduler result for local dry-run audit")
        audit = run_local_failure_outbox(project)
        if (not isinstance(audit, dict)
                or audit.get("status") != "LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
                or audit.get("messages_sent") != 0
                or audit.get("external_api_calls") != 0
                or audit.get("official_leaders_confirmed") != 0
                or audit.get("actual_future_leader_skill_certified") is not False
                or audit.get("local_artifacts_only") is not True):
            raise RuntimeError("Local dry-run outbox verification unsafe or skipped")
        return {"schedule": scheduled, "local_failure_outbox": audit,
                "messages_sent": 0, "external_api_calls": 0,
                "official_leaders_confirmed": 0,
                "actual_future_leader_skill_certified": False}

    if args.generate_plist:
        path = write_launch_agent(args.generate_plist, python=Path(sys.executable),
                                  project=project, hour=args.hour, minute=args.minute,
                                  watch_research_config=args.watch_research_config,
                                  watch_max_age_days=args.watch_max_age_days,
                                  watch_only=args.watch_only,
                                  maturity_only=args.maturity_only,
                                  ranked_maturity_config=args.ranked_maturity_config)
        result = {"status": "PLIST_GENERATED_NOT_INSTALLED", "path": str(path)}
    elif args.maturity_only:
        result = run_and_audit(lambda: run_scheduled_maturity_only(
            out=project / "output" / "scheduled_maturity",
            control=project / "output" / "scheduler_maturity_control",
            backups=project / "output" / "scheduler_maturity_backups",
            ranked_maturity_config=args.ranked_maturity_config,
            sample_limit=args.maturity_sample_limit,
        ))
    elif args.watch_only:
        result = run_and_audit(lambda: run_scheduled_watch_only(
            out=project / "output" / "scheduled_watch",
            control=project / "output" / "scheduler_watch_control",
            backups=project / "output" / "scheduler_watch_backups",
            watch_research_config=args.watch_research_config,
            watch_max_age_days=args.watch_max_age_days,
        ))
    else:
        result = run_and_audit(lambda: run_scheduled(
                               legacy=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"),
                               out=project / "output" / "scheduled",
                               control=project / "output" / "scheduler_control",
                               backups=project / "output" / "scheduler_backups",
                               max_age_days=args.max_age_days,
                               allow_stale_research=args.allow_stale_research,
                               watch_research_config=args.watch_research_config,
                               watch_max_age_days=args.watch_max_age_days))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"EraLeader schedule error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
