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
    parser.add_argument("--provider-quality-dry-run", action="store_true",
                        help="Opt-in SHA/quality weakening watchdog; local preview only, never sent")
    parser.add_argument("--prospective-due-registry", type=Path,
                        help="Opt-in first-write cohort index for local unsent due-evidence warnings")
    parser.add_argument("--prospective-due-native-config", type=Path,
                        help="Required when the original registry has a native WATCH evidence marker")
    parser.add_argument("--native-first-capture-plan", type=Path, action="append",
                        help="Opt-in local first-score Top-K+census; repeat for KR+US plans, never outcomes")
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
    if args.prospective_due_native_config is not None and args.prospective_due_registry is None:
        raise ValueError("Native due evidence needs an explicit prospective registry")
    if args.generate_plist and (args.local_outbox_dry_run or args.provider_quality_dry_run
                                or args.prospective_due_registry is not None
                                or args.native_first_capture_plan is not None):
        raise ValueError("Local observers/first native capture are not supported with --generate-plist")

    def run_and_audit(job):
        # Both dry-run observers are strictly opt-in and never schedule delivery.
        if not (args.local_outbox_dry_run or args.provider_quality_dry_run or
                args.prospective_due_registry is not None or
                args.native_first_capture_plan is not None):
            return job()
        from eraleader.local_failure_outbox import run_local_failure_outbox
        from eraleader.provider_quality_watchdog import run_provider_quality_watchdog
        from eraleader.prospective_due_alerts import run_prospective_due_alerts
        from eraleader.native_first_capture import capture_first_native_topk

        def capture():
            seen = set()
            all_results = []
            for original_plan in args.native_first_capture_plan:
                # Do not credit the same input plan twice in one job. The
                # underlying native capture also deduplicates market+model.
                identity = str(original_plan.absolute())
                if identity in seen:
                    raise ValueError("Duplicate first-native capture plan supplied to scheduler")
                seen.add(identity)
                result=capture_first_native_topk(
                    original_plan,project/"output"/"native_first_captures")
                if (not isinstance(result,dict) or
                        result.get("status") not in (
                            "FIRST_NATIVE_TOPK_CAPTURED_AND_CENSUS_REGISTERED_NOT_CERTIFIED",
                            "ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY",
                            "WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE") or
                        result.get("messages_sent") != 0 or
                        result.get("external_api_calls") != 0 or
                        result.get("real_future_leader_accuracy_certified") is not False or
                        result.get("official_leader_promotions") != 0):
                    raise RuntimeError("Unsafe or skipped first-native capture result")
                all_results.append(result)
            if len(all_results)==1:
                return all_results[0]
            return {
                "status":"LOCAL_MULTI_NATIVE_CAPTURE_NOT_CERTIFIED",
                "plan_count":len(all_results),
                "cohorts":all_results,
                "real_future_leader_accuracy_certified":False,
                "official_leader_promotions":0,"messages_sent":0,
                "external_api_calls":0,
            }

        def observers():
            found = {}
            if args.local_outbox_dry_run:
                result = run_local_failure_outbox(project)
                if (not isinstance(result, dict)
                        or result.get("status") != "LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP"
                        or result.get("messages_sent") != 0
                        or result.get("external_api_calls") != 0
                        or result.get("official_leaders_confirmed") != 0
                        or result.get("actual_future_leader_skill_certified") is not False
                        or result.get("local_artifacts_only") is not True):
                    raise RuntimeError("Local dry-run outbox verification unsafe or skipped")
                found["local_failure_outbox"] = result
            if args.provider_quality_dry_run:
                result = run_provider_quality_watchdog(project)
                if (not isinstance(result, dict)
                        or result.get("status") != "LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP"
                        or result.get("messages_sent") != 0
                        or result.get("external_api_calls") != 0
                        or result.get("official_leaders_confirmed") != 0
                        or result.get("actual_future_leader_skill_certified") is not False
                        or result.get("local_artifacts_only") is not True):
                    raise RuntimeError("Local quality dry-run verification unsafe or skipped")
                found["provider_quality_watchdog"] = result
            if args.prospective_due_registry is not None:
                result = run_prospective_due_alerts(
                    project,registry_dir=args.prospective_due_registry,
                    native_config=args.prospective_due_native_config)
                if (not isinstance(result,dict)
                        or result.get("status") != "LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP"
                        or result.get("messages_sent") != 0
                        or result.get("external_api_calls") != 0
                        or result.get("official_leaders_confirmed") != 0
                        or result.get("actual_future_leader_skill_certified") is not False
                        or result.get("local_artifacts_only") is not True):
                    raise RuntimeError("Prospective due dry-run verification unsafe or skipped")
                found["prospective_due_alerts"] = result
            if args.native_first_capture_plan is not None:
                found["native_first_capture"] = capture()
            return found

        try:
            scheduled = job()
        except Exception as primary_error:
            # Even if the main research schedule is blocked by stale caches,
            # record local quality anomalies without masking that failure.
            if args.local_outbox_dry_run:
                try:
                    run_local_failure_outbox(project)
                except Exception as audit_error:
                    primary_error.add_note(f"Local outbox audit also failed: {audit_error}")
            if args.provider_quality_dry_run:
                try:
                    run_provider_quality_watchdog(project)
                except Exception as audit_error:
                    primary_error.add_note(f"Quality watchdog audit also failed: {audit_error}")
            if args.prospective_due_registry is not None:
                try:
                    run_prospective_due_alerts(
                        project,registry_dir=args.prospective_due_registry,
                        native_config=args.prospective_due_native_config)
                except Exception as audit_error:
                    primary_error.add_note(f"Prospective due audit also failed: {audit_error}")
            if args.native_first_capture_plan is not None:
                try:
                    capture()
                except Exception as audit_error:
                    primary_error.add_note(f"Native first capture also failed: {audit_error}")
            raise
        if (not isinstance(scheduled, dict)
                or scheduled.get("status") == "SKIPPED_ALREADY_RUNNING"
                or scheduled.get("messages_sent", 0) != 0
                or scheduled.get("external_api_calls", 0) != 0):
            raise RuntimeError("Unsafe or concurrent scheduler result for local dry-run audit")
        results = observers()
        return {"schedule": scheduled, **results,
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
