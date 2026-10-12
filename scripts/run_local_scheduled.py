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
    parser.add_argument("--exchange-policy-out", type=Path,
                        help="Opt-in original WATCH output for local strict roster policy SHA watchdog")
    parser.add_argument("--prospective-due-registry", type=Path,
                        help="Opt-in first-write cohort index for local unsent due-evidence warnings")
    parser.add_argument("--prospective-due-native-config", type=Path,
                        help="Required when the original registry has a native WATCH evidence marker")
    parser.add_argument("--native-first-capture-plan", type=Path, action="append",
                        help="Opt-in local first-score Top-K+census; repeat for KR+US plans, never outcomes")
    parser.add_argument("--native-first-private-archive", action="store_true",
                        help="Opt-in private original-source ZIP and separate first SHA receipt after native capture")
    parser.add_argument("--native-first-internal-witness-root", type=Path,
                        help="Opt-in hashed-only original ZIP SHA witness on a different filesystem; no raw market sources copied")
    parser.add_argument("--native-sha-dry-run-plan", type=Path, action="append",
                        help="Opt-in read-only multi-cohort original SHA monitor plan; repeat for each cohort")
    parser.add_argument("--native-sha-dry-run-witness-root", type=Path,
                        help="Separate-volume SHA-only original witness root for unsent dashboard audit")
    parser.add_argument("--native-first-encrypted-vault-root", type=Path,
                        help="Opt-in AES-256-GCM encrypted first native ZIP backup on a different local device")
    parser.add_argument("--native-first-encryption-cert", type=Path,
                        help="Public RSA-OAEP recipient certificate for opt-in encrypted source backup")
    parser.add_argument("--native-encrypted-watch-slot", action="append",
                        help="Opt-in encrypted native first SHA DRY-RUN; repeat for KR/US slots")
    parser.add_argument("--native-encrypted-watch-vault-root", type=Path,
                        help="Original separate-device ciphertext backup directory for local dry-run")
    parser.add_argument("--native-encrypted-watch-witness-root", type=Path,
                        help="Original separate-device SHA-only witness directory for local dry-run")
    parser.add_argument("--native-encrypted-watch-cert", type=Path,
                        help="Original PUBLIC RSA recipient certificate for local dry-run (no private key)")
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
    if args.native_first_private_archive and not args.native_first_capture_plan:
        raise ValueError("Private first-native archive requires --native-first-capture-plan")
    if (args.native_first_internal_witness_root is not None and
            not args.native_first_private_archive):
        raise ValueError("Separate internal SHA witness requires --native-first-private-archive")
    if bool(args.native_sha_dry_run_plan) != (args.native_sha_dry_run_witness_root is not None):
        raise ValueError("Native SHA DRY-RUN needs BOTH --native-sha-dry-run-plan and --native-sha-dry-run-witness-root")
    if bool(args.native_first_encrypted_vault_root) != bool(args.native_first_encryption_cert):
        raise ValueError("Encrypted original vault requires BOTH private destination root and public recipient cert")
    if args.native_first_encrypted_vault_root is not None and (
            args.native_first_capture_plan is None or
            not args.native_first_private_archive or
            args.native_first_internal_witness_root is None):
        raise ValueError("Encrypted first-native vault requires private archive, capture plan and separate SHA witness")
    if any((args.native_encrypted_watch_slot is not None,
            args.native_encrypted_watch_vault_root is not None,
            args.native_encrypted_watch_witness_root is not None,
            args.native_encrypted_watch_cert is not None)) and not all((
            args.native_encrypted_watch_slot is not None,
            args.native_encrypted_watch_vault_root is not None,
            args.native_encrypted_watch_witness_root is not None,
            args.native_encrypted_watch_cert is not None)):
        raise ValueError("Encrypted native DRY-RUN requires --slot, vault, witness and PUBLIC cert")
    if args.generate_plist and (args.local_outbox_dry_run or args.provider_quality_dry_run
                                or args.exchange_policy_out is not None
                                or args.prospective_due_registry is not None
                                or args.native_first_capture_plan is not None
                                or args.native_first_private_archive
                                or args.native_first_internal_witness_root is not None
                                or args.native_sha_dry_run_plan is not None
                                or args.native_sha_dry_run_witness_root is not None
                                or args.native_first_encrypted_vault_root is not None
                                or args.native_first_encryption_cert is not None
                                or args.native_encrypted_watch_slot is not None
                                or args.native_encrypted_watch_vault_root is not None
                                or args.native_encrypted_watch_witness_root is not None
                                or args.native_encrypted_watch_cert is not None):
        raise ValueError("Local observers/first native capture are not supported with --generate-plist")
    if args.native_first_internal_witness_root is not None:
        # Fail BEFORE running market batch or writing any native first scores.
        from eraleader.native_sha_witness import validate_witness_destination
        validate_witness_destination(project,args.native_first_internal_witness_root)
    if args.native_sha_dry_run_witness_root is not None:
        from eraleader.native_sha_witness import validate_witness_destination
        validate_witness_destination(project,args.native_sha_dry_run_witness_root)
    if args.native_first_encrypted_vault_root is not None:
        from eraleader.native_sha_witness import validate_witness_destination
        from eraleader.native_encrypted_vault import _cert
        vault = validate_witness_destination(project,args.native_first_encrypted_vault_root)
        witness = args.native_first_internal_witness_root.absolute()
        if vault==witness or vault in witness.parents or witness in vault.parents:
            raise ValueError("Encrypted vault must not overlap first SHA witness root")
        _cert(args.native_first_encryption_cert)
    if args.native_encrypted_watch_slot is not None:
        # Configuration validation is read-only; missing disk/cert is reported
        # by the audit, not silently installed or reinitialized on T5DATA.
        from eraleader.native_encrypted_watchdog import validate_monitor_inputs
        validate_monitor_inputs(project,args.native_encrypted_watch_slot,
                                args.native_encrypted_watch_vault_root,
                                args.native_encrypted_watch_witness_root,
                                args.native_encrypted_watch_cert)

    def run_and_audit(job):
        # Both dry-run observers are strictly opt-in and never schedule delivery.
        if not (args.local_outbox_dry_run or args.provider_quality_dry_run or
                args.exchange_policy_out is not None or
                args.prospective_due_registry is not None or
                args.native_first_capture_plan is not None or
                args.native_sha_dry_run_plan is not None or
                args.native_encrypted_watch_slot is not None):
            return job()
        from eraleader.local_failure_outbox import run_local_failure_outbox
        from eraleader.provider_quality_watchdog import run_provider_quality_watchdog
        from eraleader.exchange_policy_watchdog import run_exchange_policy_watchdog
        from eraleader.prospective_due_alerts import run_prospective_due_alerts
        from eraleader.native_first_capture import capture_first_native_topk
        from eraleader.scheduled_native_archive import archive_captured_native_plan
        from eraleader.native_sha_witness import record_native_sha_witness
        from eraleader.native_sha_watchdog import run_native_sha_watchdog
        from eraleader.native_encrypted_vault import backup_encrypted_native_original
        from eraleader.native_encrypted_watchdog import run_native_encrypted_watchdog

        def capture():
            seen = set()
            all_results = []
            if args.native_first_private_archive:
                # Reject a renamed same-model Top-K before producing ANY first
                # source ZIP. Default scheduler without opt-in stays untouched.
                from eraleader.native_first_capture import read_capture_plan
                from eraleader.native_evidence_archive import _slot
                slots = [_slot(read_capture_plan(p)[0])
                         for p in args.native_first_capture_plan]
                if len(set(slots))!=len(slots):
                    raise ValueError("Duplicate pinned native model plans cannot produce separate first archives")
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
                if args.native_first_private_archive:
                    first_archive=archive_captured_native_plan(
                        project,original_plan,
                        project/"output"/"native_first_captures",result)
                    expected=("WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN"
                              if result["status"]=="WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE"
                              else None)
                    if (not isinstance(first_archive,dict) or
                            first_archive.get("status") not in (
                                "FIRST_PRIVATE_NATIVE_EVIDENCE_ARCHIVED_NOT_CERTIFIED",
                                "EXISTING_PRIVATE_NATIVE_EVIDENCE_REVERIFIED_NOT_CERTIFIED",
                                "WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN") or
                            (expected is not None and first_archive["status"]!=expected) or
                            (expected is None and first_archive["status"]==
                                "WAITING_NO_PRIVATE_NATIVE_ARCHIVE_WRITTEN") or
                            first_archive.get("original_first_capture_status")!=result["status"] or
                            first_archive.get("official_leader_promotions")!=0 or
                            first_archive.get("external_api_calls")!=0 or
                            first_archive.get("messages_sent")!=0 or
                            first_archive.get("real_future_leader_accuracy_certified") is not False or
                            first_archive.get("external_timestamp_attested") is not False or
                            first_archive.get("independent_market_pit_certified") is not False):
                        raise RuntimeError("Unsafe or skipped private original-source archive first SHA receipt")
                    if (args.native_first_internal_witness_root is not None and
                            expected is None):
                        separate=record_native_sha_witness(
                            project,original_plan,
                            project/"output"/"native_first_captures",
                            first_archive,args.native_first_internal_witness_root)
                        if (not isinstance(separate,dict) or
                                separate.get("status") not in (
                                    "FIRST_SEPARATE_VOLUME_NATIVE_SHA_WITNESSED_NOT_ATTESTED",
                                    "EXISTING_SEPARATE_VOLUME_NATIVE_SHA_REVERIFIED_NOT_ATTESTED") or
                                separate.get("archive_sha256")!=first_archive.get("archive_original_sha256") or
                                separate.get("market")!=first_archive.get("market") or
                                separate.get("source_archive_verified") is not True or
                                separate.get("separate_device_checked") is not True or
                                separate.get("independent_timestamp_attested") is not False or
                                separate.get("real_future_leader_accuracy_certified") is not False or
                                separate.get("official_leader_promotions")!=0 or
                                separate.get("messages_sent")!=0 or
                                separate.get("external_api_calls")!=0):
                            raise RuntimeError("Unsafe or skipped cross-volume first SHA witness")
                        first_archive={**first_archive,"separate_volume_sha_witness":separate}
                    if (args.native_first_encrypted_vault_root is not None and
                            expected is None):
                        sealed=backup_encrypted_native_original(
                            project,original_plan,
                            project/"output"/"native_first_captures",
                            args.native_first_internal_witness_root,
                            args.native_first_encrypted_vault_root,
                            args.native_first_encryption_cert)
                        if (not isinstance(sealed,dict) or
                                sealed.get("status") not in (
                                    "FIRST_ENCRYPTED_NATIVE_BACKUP_CREATED",
                                    "EXISTING_ENCRYPTED_NATIVE_BACKUP_VERIFIED") or
                                sealed.get("archive_sha256")!=first_archive.get("archive_original_sha256") or
                                sealed.get("ciphertext_verified") is not True or
                                sealed.get("authenticated_plaintext_verified") is not False or
                                sealed.get("real_future_leader_accuracy_certified") is not False or
                                sealed.get("messages_sent")!=0 or sealed.get("external_api_calls")!=0 or
                                sealed.get("official_leader_promotions")!=0):
                            raise RuntimeError("Native original encrypted first backup missing or unsafe")
                        first_archive={**first_archive,"encrypted_cross_volume_backup":sealed}
                    result={**result,"private_original_archive":first_archive}
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
            if args.exchange_policy_out is not None:
                result = run_exchange_policy_watchdog(project,args.exchange_policy_out)
                if (not isinstance(result,dict) or
                        result.get("status")!="LOCAL_EXCHANGE_POLICY_DRY_RUN_RECORDED" or
                        result.get("messages_sent")!=0 or
                        result.get("external_api_calls")!=0 or
                        result.get("official_leader_promotions")!=0 or
                        result.get("actual_future_leader_skill_certified") is not False or
                        result.get("local_artifacts_only") is not True):
                    raise RuntimeError("Exchange policy watchdog did not safely record")
                found["exchange_policy_watchdog"]=result
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
            if args.native_sha_dry_run_plan is not None:
                scan = run_native_sha_watchdog(
                    project,args.native_sha_dry_run_plan,args.native_sha_dry_run_witness_root)
                if (not isinstance(scan,dict) or
                        scan.get("status")!="LOCAL_NATIVE_SHA_DRY_RUN_RECORDED" or
                        scan.get("local_artifacts_only") is not True or
                        scan.get("messages_sent")!=0 or scan.get("external_api_calls")!=0 or
                        scan.get("official_leader_promotions")!=0 or
                        scan.get("actual_future_leader_skill_certified") is not False):
                    raise RuntimeError("Native SHA DRY-RUN audit unsafe or incomplete")
                found["native_sha_watchdog"]=scan
            if args.native_encrypted_watch_slot is not None:
                audit=run_native_encrypted_watchdog(
                    project,args.native_encrypted_watch_slot,
                    args.native_encrypted_watch_vault_root,
                    args.native_encrypted_watch_witness_root,
                    args.native_encrypted_watch_cert)
                if (not isinstance(audit,dict) or
                        audit.get("status")!="LOCAL_ENCRYPTED_NATIVE_DRY_RUN_RECORDED" or
                        audit.get("local_artifacts_only") is not True or
                        audit.get("authenticated_plaintext_verified") is not False or
                        audit.get("independent_market_pit_certified") is not False or
                        audit.get("real_future_leader_accuracy_certified") is not False or
                        audit.get("messages_sent")!=0 or
                        audit.get("external_api_calls")!=0 or
                        audit.get("official_leader_promotions")!=0):
                    raise RuntimeError("Unsafe encrypted native dry-run monitor")
                found["native_encrypted_watchdog"]=audit
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
            if args.exchange_policy_out is not None:
                try:
                    run_exchange_policy_watchdog(project,args.exchange_policy_out)
                except Exception as audit_error:
                    primary_error.add_note(f"Exchange roster policy watch also failed: {audit_error}")
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
            if args.native_sha_dry_run_plan is not None:
                try:
                    run_native_sha_watchdog(
                        project,args.native_sha_dry_run_plan,args.native_sha_dry_run_witness_root)
                except Exception as audit_error:
                    primary_error.add_note(f"Native SHA monitor also failed: {audit_error}")
            if args.native_encrypted_watch_slot is not None:
                try:
                    run_native_encrypted_watchdog(
                        project,args.native_encrypted_watch_slot,
                        args.native_encrypted_watch_vault_root,
                        args.native_encrypted_watch_witness_root,
                        args.native_encrypted_watch_cert)
                except Exception as audit_error:
                    # No raw certificate/original source path in exception notes.
                    primary_error.add_note("Encrypted SHA observer incomplete: "+type(audit_error).__name__)
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
