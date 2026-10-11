"""Offline CLI: data -> quality -> screen -> event ledger -> web/report."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from . import __version__
from .data import LEGACY_DEFAULT, read_market_bars
from .discovery import score_price_observations, detect_watch_changes,run_id_for
from .pit import LocalStore
from .delivery import write_dashboard,make_report,write_integrated_dashboard,write_prospective_dashboard,write_evidence_gate_dashboard,write_watch_progression_dashboard
from .backtest import delayed_momentum_baseline
from .offline_pit import OfflineLedger
from .pit_provider_readiness import audit_pit_provider_readiness
from .provider_pit_adapter import import_provider_bundle, audit_registered_provider_asof
from .provider_export_normalizer import normalize_provider_export
from .provider_staged_lineage import audit_staged_source_lineage
from .provider_dual_source_audit import audit_provider_source_pair
from .provider_candidate_gate import audit_candidate_provider_gate
from .offline_features import financial_snapshot
from .peer_normalization import normalize_peer_file
from .rank_feature_bridge import build_rank_feature_inputs
from .research import integrated_snapshot
from .discovery_metrics import evaluate_early_discovery
from .walkforward import walk_forward_split
from .walkforward_replay import replay_walk_forward_folds
from .state_history import StateHistory
from .corporate_returns import reconstruct_total_return
from .adjusted_crosscheck import compare_total_return_indexes
from .session_close_gate import audit_declared_session_close
from .session_calendar_crosscheck import corroborate_declared_closes
from .frozen_holdout import freeze_registered_candidates, evaluate_frozen_candidates
from .holdout_maturity import audit_holdout_maturity
from .holdout_outcome_reconcile import reconcile_holdout_outcomes
from .outcome_source_claims import audit_outcome_source_claims
from .ranked_outcome_receipts import audit_ranked_outcome_receipts
from .pit_chain import audit_pit_to_outcome_chain
from .ranked_registry import audit_ranked_watch_registry
from .rank_score_ledger import register_rank_scores, audit_frozen_rank_scores
from .rank_score_pipeline import compute_and_register_rank_scores, audit_computed_rank_provenance
from .native_topk_freeze import freeze_native_topk
from .source_vintage import audit_source_vintages
from .universe_audit import audit_observed_universe
from .continuity_audit import audit_observation_continuity
from .calendar_audit import audit_exchange_calendar
from .delist_cash import reconstruct_cash_delisting
from .cash_exit_lineage import audit_dual_vintage_cash_exit
from .issuer_lineage import audit_issuer_lineage
from .evidence_gate import evaluate_local_evidence
from .pit_coverage import reconcile_membership_to_prices
from .prospective import ProspectiveRegistry
from .watch_progression import audit_watch_progression
from .watch_operating_reports import compile_watch_operating_report, write_watch_operating_reports
from .watch_rotation import audit_watch_rotation
from .peer_score_series import record_peer_score_series, audit_peer_score_advantage
from .rotation_holdout import freeze_rotation_pairs, audit_rotation_pair_outcomes
from .rotation_pair_source_claims import audit_rotation_pair_source_claims
from .delivery import write_watch_rotation_dashboard, write_peer_score_rotation_dashboard
from .pit_publication import verify_pit_publication
from .local_backup import create_backup, verify_backup, restore_backup

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"output"
def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")

def execute_run(args) -> dict:
    prepared=getattr(args,"prepared_snapshot",None)
    if prepared is None:
        asof=date.fromisoformat(args.as_of)
        data,quality=read_market_bars(args.market,asof,days=args.days,
                          legacy_root=Path(args.legacy),tickers=args.tickers)
        snap=score_price_observations(data,args.market,args.as_of,args.top)
        snap["data_source"]=quality["source"]
        snap["quality_flags"]=quality
        rid=run_id_for(args.market,args.as_of,snap["rows"])
        snap["run_id"]=rid
    else:
        # Only the in-process explicit batch preflight supplies this snapshot.
        # Default CLI and scheduled runs still read and score their own data.
        if not isinstance(prepared,dict) or (
                prepared.get("source_market")!=args.market or
                prepared.get("as_of_requested")!=args.as_of):
            raise ValueError("Preflight price snapshot market/day mismatch")
        snap=deepcopy(prepared)
        quality=snap["quality_flags"]
        rid=run_id_for(args.market,args.as_of,snap["rows"])
        if snap.get("run_id") != rid:
            raise ValueError("Preflight price snapshot content changed")
    store=LocalStore(Path(args.out)/"state.sqlite")
    try:
        before=store.recent(args.market)
        events=detect_watch_changes(before,snap,rid)
        store.save_snapshot(rid,args.market,snap["market_last_observation"],snap,events)
    finally:
        store.close()
    dest=Path(args.out)/"runs"/f"{rid}.json"
    write_json(dest,snap)
    write_json(Path(args.out)/f"{args.market.lower()}_latest.json",snap)
    page=write_dashboard(snap,Path(args.out)/"site")
    return {"status":"PRICE_ONLY_RESEARCH","run_id":rid,
            "source":quality["source"],"market":args.market,
            "as_of":snap["market_last_observation"],"rows":snap["shown"],
            "events_attempted":len(events),"snapshot":str(dest),"dashboard":str(page),
            "limitation":"Fundamentals, historic membership, corporate actions/PIT not certified"}

def execute_baseline(args):
    bars,q=read_market_bars(args.market,date.fromisoformat(args.as_of),
                    days=args.days,legacy_root=Path(args.legacy),tickers=args.tickers)
    results=delayed_momentum_baseline(bars,lookback=args.lookback,
                                      top_n=args.top,rebalance=args.rebalance,
                                      weekly=(args.market=="US"))
    results["market"]=args.market;results["data_source"]=q["source"]
    results["as_of_requested"]=args.as_of
    dest=Path(args.out)/"baseline_research.json"
    write_json(dest,results)
    return {"path":str(dest),**results}

def execute_report(args) -> dict:
    db=LocalStore(Path(args.out)/"state.sqlite")
    try:snap=db.recent(args.market)
    finally:db.close()
    if not snap:
        raise RuntimeError(f"No saved market snapshot for {args.market}; run command first")
    path=Path(args.out)/"reports"/f"{args.market.lower()}_{args.period}_{snap['market_last_observation']}.md"
    make_report(snap,args.period,path)
    return {"status":"LOCAL_MARKDOWN_CREATED","path":str(path),
            "data_as_of":snap["market_last_observation"]}

def execute_alerts(args):
    db=LocalStore(Path(args.out)/"state.sqlite")
    try:
        events=db.events(pending_only=True)
        # Real delivery not connected; only write an offline preview.
        target=Path(args.out)/"alerts_preview.json"
        write_json(target,events)
        for ev in events:db.mark_dry_run(ev["event_id"])
        return {"status":"DRY_RUN_ONLY_NO_MESSAGE_SENT","count":len(events),"path":str(target)}
    finally:db.close()

def execute_offline_import(args) -> dict:
    ledger=OfflineLedger(Path(args.out)/"offline.sqlite")
    try:
        summary=ledger.import_file(Path(args.file),kind=args.kind,provenance=args.provenance)
        return {"status":"OFFLINE_IMPORT_DONE_NOT_CERTIFIED","summary":summary,
                "database":str(ledger.path),"disclaimer":"No evidence of complete point-in-time universe"}
    finally:ledger.close()

def execute_offline_features(args) -> dict:
    ledger=OfflineLedger(Path(args.out)/"offline.sqlite")
    try:
        snap=ledger.snapshot(args.as_of,market=args.market)
        scored=financial_snapshot(snap)
        # Freeze every research run. Never erase older vintages of early
        # signals; otherwise prospective detection cannot be audited.
        import hashlib
        encoded=json.dumps(scored,ensure_ascii=False,sort_keys=True)
        signature=hashlib.sha256(encoded.encode()).hexdigest()[:16]
        stamp=snap["as_of"][:16].replace("-","").replace(":","").replace("T","_")
        audit_path=Path(args.out)/"runs"/f"offline_{args.market.lower()}_{stamp}_{signature}.json"
        write_json(audit_path,scored)
        destination=Path(args.out)/f"offline_{args.market.lower()}_features.json"
        write_json(destination,scored)
        return {"status":"RESEARCH_ONLY_PIT_SOURCE_NOT_CERTIFIED",
                "path":str(destination),"immutable_run":str(audit_path),
                "companies":scored["company_count"],
                "heuristic_screen_hits":scored["research_screen_count"],
                "deferred_research_screens":scored["research_screens_deferred"],
                "quality":scored["quality"]}
    finally:ledger.close()

def execute_peer_normalization(args) -> dict:
    return normalize_peer_file(Path(args.input), Path(args.out), min_peers=args.min_peers)

def execute_rank_feature_inputs(args) -> dict:
    return build_rank_feature_inputs(Path(args.offline), Path(args.price),
                                     Path(args.features_dir),
                                     model_version=args.model_version,
                                     min_peers=args.min_peers,
                                     offline_ledger=(Path(args.offline_ledger)
                                                     if args.offline_ledger else None),
                                     price_cache_root=(Path(args.price_cache_root)
                                                       if args.price_cache_root else None),
                                     price_cache_days=args.cache_days)

def execute_integrated(args) -> dict:
    # An explicitly selected two-provider PIT check must be complete. Never
    # fall back to the old ungated integration because one flag was omitted.
    fields=("provider_ledger_a","provider_bundle_a","provider_ledger_b",
            "provider_bundle_b")
    supplied=[getattr(args,field,None) for field in fields]
    if any(supplied) and not all(supplied):
        raise ValueError("All four provider PIT flags are required together")
    pair=supplied if all(supplied) else None
    offline_path=Path(args.out)/"offline.sqlite"
    source=(OfflineLedger.open_readonly(offline_path) if pair
            else OfflineLedger(offline_path))
    gate=None
    try:
        offline=source.snapshot(args.as_of,market=args.market)
        price=json.loads(Path(args.price_json).read_text(encoding="utf-8")) if args.price_json else None
        result=integrated_snapshot(offline,price,args.as_of)
        if pair:
            gate=audit_candidate_provider_gate(
                Path(pair[0]),pair[1],Path(pair[2]),pair[3],
                market=args.market,decision_at=args.as_of,
                candidate_members=offline["members"],
                candidate_facts=offline["fundamentals"],
                candidate_industry=offline["industry"],
                candidate_actions=(offline["actions"]+
                                   offline["announced_future_actions"]))
    finally:
        source.close()
    if gate is not None:
        gate_file=Path(args.out)/"provider_candidate_gate_research.json"
        # The gate is evaluated on actual source receipts and source rows, not
        # just a separately supplied self-declared summary report.
        write_json(gate_file,gate)
        if not gate["research_watch_allowed"]:
            return {"status":"BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH",
                    "gate_path":str(gate_file),
                    "blocker_counts":gate["blocker_counts"],
                    "new_prospective_research_signals":0,
                    "official_leaders":0,"pit_certified":False,
                    "provider_research_watch_allowed":False}
        # Existing rank/WATCH source_run_id must remain immutable when the
        # provenance pair changes even if offline candidate numbers do not.
        result["provider_pair_gate"]=gate
        stamp=json.dumps({
            "original_run_id":result["run_id"],
            "local_pair_digest":gate["source_pair_digest_sha256"]
        },ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
        result["run_id"]=sha256(stamp.encode()).hexdigest()[:20]
    target=Path(args.out)/"runs"/f"joined_{args.market.lower()}_{result['run_id']}.json"
    if target.exists():
        existing=json.loads(target.read_text(encoding="utf-8"))
        if existing!=result:
            raise ValueError("Existing immutable run differs from candidate")
    else:
        write_json(target,result)
    page=write_integrated_dashboard(result,Path(args.out)/'site')
    ledger=StateHistory(Path(args.out)/'state_history.sqlite')
    try:
        observations=[{"security_id":row["security_id"],"components":{},
                       "evidence":{"financial_pit":False,
                                   "historic_universe_pit":False,
                                   "corporate_actions_pit":False},
                       "input_run_id":result["run_id"]}
                      for row in result["company_rows"]]
        tracked=ledger.record(args.market,args.as_of,observations)
    finally:
        ledger.close()
    registry=ProspectiveRegistry(Path(args.out)/"prospective.sqlite")
    try:
        registration=registry.record_integrated(result)
        prospective_report=registry.first_signals(args.market)
    finally:
        registry.close()
    prospective_page=write_prospective_dashboard(prospective_report,Path(args.out)/"site")
    return {"status":"OFFLINE_INTEGRATION_RESEARCH_ONLY",
            "prospective_dashboard":str(prospective_page),
            "state_events":len(tracked["new_state_events"]),"dashboard":str(page),
            "new_prospective_research_signals":registration["new_records"],
            "path":str(target),"company_count":result["company_count"],
            "growth_screen_hits":result["research_growth_screen_count"],
            "deferred_research_screens":result["research_screen_deferred_count"],
            "official_leaders":0,"pit_certified":False,
            "provider_research_watch_allowed": bool(gate and gate["research_watch_allowed"])}

def execute_validation(args) -> dict:
    signals=json.loads(Path(args.signals).read_text(encoding="utf-8"))
    outcomes=json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    if not isinstance(signals,list) or not isinstance(outcomes,list):
        raise ValueError("Evaluation requires two JSON arrays")
    result=evaluate_early_discovery(signals,outcomes,evaluated_at=args.evaluated_at,
                                    horizon_days=args.horizon_days)
    target=Path(args.out)/"validation_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "true_early_discoveries":result["true_early_discoveries"],
            "false_discoveries":result["false_discoveries"],
            "censored":result["censored"],"note":"Synthetic/partial outcomes not performance certification"}

def execute_walkforward(args) -> dict:
    samples=json.loads(Path(args.snapshots).read_text(encoding="utf-8"))
    outcomes=json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    if not isinstance(samples,list) or not isinstance(outcomes,list):
        raise ValueError("Walkforward input must be lists")
    result=walk_forward_split(samples,outcomes,train_ends_at=args.train_ends_at,
                               test_ends_at=args.test_ends_at,embargo_days=args.embargo_days)
    target=Path(args.out)/"walkforward_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "train_samples":len(result["training"]),
            "test_candidates":len(result["test_candidates"]),
            "historic_universe_certified":False}

def execute_repeated_walkforward(args) -> dict:
    snapshots=json.loads(Path(args.snapshots).read_text(encoding="utf-8"))
    outcomes=json.loads(Path(args.outcomes).read_text(encoding="utf-8"))
    windows=json.loads(Path(args.windows).read_text(encoding="utf-8"))
    result=replay_walk_forward_folds(
        snapshots,outcomes,windows=windows,
        model_version=args.model_version,
        label_definition_id=args.label_definition_id,
        embargo_days=args.embargo_days)
    target=Path(args.out)/"repeated_walkforward_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "fold_count":result["fold_count"],
            "unique_test_candidate_count":result["unique_test_candidate_count"],
            "test_outcome_labels_revealed":False,
            "historic_universe_pit_certified":False}

def execute_corporate_research(args) -> dict:
    bundle=json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(bundle,dict) or not isinstance(bundle.get("bars"),list) or not isinstance(bundle.get("actions"),list):
        raise ValueError("Corporate-action evaluation expects JSON with bars/actions lists")
    if bundle.get("schema_version")!="corporate_return_research_v1" or bundle.get("price_basis")!=args.price_basis:
        raise ValueError("Corporate return input schema/price basis mismatch")
    if bundle.get("provenance") not in ("synthetic_fixture","external_public_file","user_supplied"):
        raise ValueError("Corporate return input provenance must be explicit")
    for flag in ("corporate_actions_complete","price_sessions_complete"):
        if flag in bundle and not isinstance(bundle[flag],bool):
            raise ValueError("Quality attestations must be booleans")
    result=reconstruct_total_return(
        bundle["bars"],bundle["actions"],
        decision_at=args.decision_at,evaluated_at=args.evaluated_at,
        security_id=args.security_id,market=args.market,
        price_basis=args.price_basis,
        corporate_actions_complete=bool(bundle.get("corporate_actions_complete",False)),
        price_sessions_complete=bool(bundle.get("price_sessions_complete",False)))
    target=Path(args.out)/"corporate_returns_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "total_return_research":result["total_return"],
            "actions_applied":result["actions_applied"],
            "pit_certified":False}

def execute_universe_audit(args) -> dict:
    bars,source_quality=read_market_bars("KR",date.fromisoformat(args.as_of),
                             days=args.days,legacy_root=Path(args.legacy))
    audit=audit_observed_universe(bars,date.fromisoformat(args.as_of))
    audit["source"]=source_quality["source"]
    audit["cached_price_quality"]=source_quality
    target=Path(args.out)/"universe_observation_audit.json"
    write_json(target,audit)
    return {"status":audit["status"],"path":str(target),
            "last_observation":audit["last_observation"],
            "observed_symbols_current":audit["observed_symbols_current"],
            "appeared_count":audit["appeared_count"],
            "disappeared_count":audit["disappeared_count"],
            "halted_count":audit["halted_count"],
            "historic_membership_certified":False}

def execute_return_crosscheck(args) -> dict:
    bundle=json.loads(Path(args.file).read_text(encoding="utf-8"))
    if bundle.get("schema_version")!="total_return_crosscheck_v1":
        raise ValueError("Unsupported total-return crosscheck schema")
    if bundle.get("provenance") not in ("synthetic_fixture","external_public_file","user_supplied"):
        raise ValueError("Explicit offline provenance required")
    if bundle.get("price_basis")!="raw_unadjusted":
        raise ValueError("Raw unadjusted price basis required")
    clock_audit=None
    calendar_audit=None
    if args.exchange_calendar and not args.session_clock:
        raise ValueError("--exchange-calendar requires --session-clock")
    if args.session_clock:
        clock_path=Path(args.session_clock)
        if clock_path.stat().st_size>2_000_000:
            raise ValueError("Oversized local session-clock manifest")
        clock=json.loads(clock_path.read_text(encoding="utf-8"))
        clock_audit=audit_declared_session_close(
            bundle["bars"],bundle["reference"]["bars"],clock,
            market=args.market,raw_source_id=bundle["raw_source_id"],
            reference_source_id=bundle["reference"]["source_id"],
            decision_at=args.decision_at,evaluated_at=args.evaluated_at)
    if args.exchange_calendar:
        calendar_path=Path(args.exchange_calendar)
        if calendar_path.stat().st_size>2_000_000:
            raise ValueError("Oversized exchange calendar")
        calendar=json.loads(calendar_path.read_text(encoding="utf-8"))
        calendar_audit=corroborate_declared_closes(
            clock,calendar,market=args.market,decision_at=args.decision_at,
            raw_source_id=bundle["raw_source_id"],
            reference_source_id=bundle["reference"]["source_id"])
    result=compare_total_return_indexes(
        bundle["bars"],bundle["actions"],bundle["reference"],
        decision_at=args.decision_at,evaluated_at=args.evaluated_at,
        security_id=args.security_id,market=args.market,
        raw_source_id=bundle["raw_source_id"],
        tolerance_bps=args.tolerance_bps)
    if clock_audit is not None:
        result["declared_session_close_audit"]=clock_audit
    if calendar_audit is not None:
        result["declared_calendar_corroboration_audit"]=calendar_audit
    target=Path(args.out)/"total_return_crosscheck_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "intervals_outside_tolerance":result["intervals_outside_tolerance"],
            "historic_price_actions_pit_certified":False}

def execute_ranked_outcome_receipts(args) -> dict:
    outcome=audit_ranked_outcome_receipts(
        Path(args.freeze),Path(args.outcomes),Path(args.receipt_manifest),
        evaluated_at=args.evaluated_at,sample_limit=args.sample_limit,
        label_definition_file=Path(args.definition_file),
    )
    artifact=Path(args.out)/"ranked_outcome_receipts_research.json"
    write_json(artifact,outcome)
    return {
        "status":outcome["status"],"path":str(artifact),
        "top_k_selected_count":outcome["top_k_selected_count"],
        "locally_documented_known_count":outcome["locally_documented_known_count"],
        "source_document_matched_early_hits":outcome["source_document_matched_early_hits"],
        "actual_future_leader_accuracy_certified":False,
        "official_leader_promotions":0,
    }


def execute_staged_source_lineage(args) -> dict:
    result=audit_staged_source_lineage(
        Path(args.staged_manifest),Path(args.normalized_manifest),
        ledger_file=(Path(args.ledger) if args.ledger else None),
        decision_at=args.decision_at,
    )
    dest=Path(args.out)/"provider_staged_lineage_research.json"
    write_json(dest,result)
    return {"status":result["status"],"path":str(dest),
            "source_and_normalized_bytes_matched":result["source_and_normalized_bytes_matched"],
            "usable_as_local_research_source_at_decision":
                result["usable_as_local_research_source_at_decision"],
            "normalized_record_count":result["normalized_record_count"],
            "official_leader_promotions":0,"external_pit_certified":False}


def execute_provider_source_pair(args) -> dict:
    result=audit_provider_source_pair(
        Path(args.ledger_a),args.bundle_a,Path(args.ledger_b),args.bundle_b,
        decision_at=args.decision_at,sample_limit=args.sample_limit)
    path=Path(args.out)/"provider_source_pair_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "blocker_counts":result["blocker_counts"],
            "matched_active_issuer_count":result["matched_active_issuer_count"],
            "problem_count":result["problem_count"],
            "historic_pit_certified":False,"official_leader_promotions":0}


def execute_normalize_provider_export(args) -> dict:
    report=normalize_provider_export(Path(args.manifest),Path(args.stage_dir))
    dest=Path(args.out)/"provider_stage_normalization_research.json"
    write_json(dest,report)
    return {"status":report["status"],"path":str(dest),
            "normalized_manifest":report["normalized_manifest"],
            "normalized_row_count":report["normalized_row_count"],
            "historic_pit_certified":False,"official_leader_promotions":0}


def execute_provider_pit_import(args) -> dict:
    audit=import_provider_bundle(Path(args.manifest),Path(args.ledger))
    path=Path(args.out)/"provider_pit_import_research.json"
    write_json(path,audit)
    return {"status":audit["status"],"path":str(path),
            "bundle_sha256":audit["bundle_sha256"],
            "rows_received":audit["rows_received"],
            "rows_inserted":audit["rows_inserted"],
            "historic_pit_certified":False,
            "official_leader_promotions":0}


def execute_provider_pit_asof(args) -> dict:
    audit=audit_registered_provider_asof(
        Path(args.ledger),args.bundle_sha256,decision_at=args.decision_at)
    path=Path(args.out)/"provider_pit_asof_research.json"
    write_json(path,audit)
    return {"status":audit["status"],"path":str(path),
            "bundle_sha256":audit["bundle_sha256"],
            "eligible_for_contemporaneous_research":
                audit["eligible_for_contemporaneous_research"],
            "official_leader_promotions":0}


def execute_pit_provider_readiness(args) -> dict:
    result=audit_pit_provider_readiness(
        Path(args.cache_root),evaluated_at=args.evaluated_at,
        kr_ledger=Path(args.kr_ledger) if args.kr_ledger else None,
        us_ledger=Path(args.us_ledger) if args.us_ledger else None,
        max_price_age_days=args.max_price_age_days,
    )
    path=Path(args.out)/"pit_provider_readiness_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "blocker_count":result["blocker_count"],
            "official_leader_promotions":0,
            "independent_pit_verified":False}


def execute_source_vintage(args) -> dict:
    audit=audit_source_vintages(Path(args.manifest),decision_at=args.decision_at)
    path=Path(args.out)/"source_vintage_audit_research.json"
    write_json(path,audit)
    return {"status":audit["status"],"path":str(path),
            "source_count":audit["source_count"],
            "retrospective_source_count":audit["retrospective_source_count"],
            "historical_pit_certified":False}

def execute_freeze_rotation_pairs(args) -> dict:
    return freeze_rotation_pairs(
        Path(args.watch_ledger), Path(args.score_history),
        Path(args.feature_root), Path(args.freeze_file),
        market=args.market, model_version=args.model_version,
        label_definition_id=args.label_definition_id,
        horizon_days=args.horizon_days,
    )

def execute_rotation_pair_outcomes(args) -> dict:
    report = audit_rotation_pair_outcomes(
        Path(args.freeze_file), evaluated_at=args.evaluated_at,
        outcome_file=Path(args.outcomes) if args.outcomes else None,
        sample_limit=args.sample_limit,
    )
    output = Path(args.out)/"rotation_pair_outcomes_research.json"
    write_json(output,report)
    return {"status":report["status"],"path":str(output),
            "frozen_pair_count":report["frozen_pair_count"],
            "internally_evaluable_pair_count":report["internally_evaluable_pair_count"],
            "research_pair_confirmed_count":report["research_pair_confirmed_count"],
            "official_leader_replacements":0,
            "independent_future_label_source_certified":False}

def execute_rotation_pair_sources(args) -> dict:
    result = audit_rotation_pair_source_claims(
        Path(args.freeze_file),Path(args.outcomes),Path(args.receipt_manifest),
        evaluated_at=args.evaluated_at,sample_limit=args.sample_limit,
    )
    destination = Path(args.out)/"rotation_pair_source_claims_research.json"
    write_json(destination,result)
    return {"status":result["status"],"path":str(destination),
            "frozen_pair_count":result["frozen_pair_count"],
            "internally_evaluable_pair_count":result["internally_evaluable_pair_count"],
            "locally_source_corroborated_pairs":result["locally_source_corroborated_pairs"],
            "official_leader_replacements":0,
            "publisher_independently_authenticated":False}

def execute_freeze_holdout(args) -> dict:
    return freeze_registered_candidates(Path(args.ledger), Path(args.freeze_file),
                                        market=args.market, model_version=args.model_version,
                                        label_definition_id=args.label_definition_id,
                                        horizon_days=args.horizon_days,
                                        max_observation_lag_days=args.max_lag_days)

def execute_evaluate_holdout(args) -> dict:
    result=evaluate_frozen_candidates(Path(args.freeze_file),Path(args.outcomes),
                                      evaluated_at=args.evaluated_at,
                                      horizon_days=args.horizon_days)
    target=Path(args.out)/"holdout_evaluation_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "known_outcomes":result["known_outcomes"],
            "censored_outcomes":result["censored_outcomes"],
            "true_early_discoveries":result["true_early_discoveries"],
            "historic_pit_certified":False}

def execute_prospective_export(args) -> dict:
    registry_path=Path(args.out)/"prospective.sqlite"
    if not registry_path.is_file():
        raise FileNotFoundError(f"Missing prospective signal ledger: {registry_path}")
    registry=ProspectiveRegistry(registry_path)
    try:
        report=registry.first_signals(args.market)
    finally:
        registry.close()
    target=Path(args.out)/f"prospective_{args.market.lower()}_research.json"
    write_json(target,report)
    page=write_prospective_dashboard(report,Path(args.out)/"site")
    return {"status":report["status"],"path":str(target),"dashboard":str(page),
            "first_registration_signals":report["distinct_companies"],
            "historic_pit_certified":False}

def execute_coverage(args) -> dict:
    ledger_path=Path(args.ledger)
    if not ledger_path.is_file():
        raise FileNotFoundError(f"Missing offline PIT ledger: {ledger_path}")
    ledger=OfflineLedger(ledger_path)
    try:
        snap=ledger.snapshot(args.as_of,market=args.market)
    finally:
        ledger.close()
    bars, quality=read_market_bars(args.market,date.fromisoformat(snap["trading_day"]),
                                  days=args.days,legacy_root=Path(args.legacy))
    audit=reconcile_membership_to_prices(snap,bars,as_of=date.fromisoformat(snap["trading_day"]))
    audit["price_feed_source"]=quality["source"]
    path=Path(args.out)/f"pit_coverage_{args.market.lower()}.json"
    write_json(path,audit)
    return {"status":audit["status"],"path":str(path),
            "pit_member_count":audit["pit_member_count"],
            "observed_price_security_count":audit["observed_price_security_count"],
            "matching_count":audit["matching_count"],
            "historic_membership_pit_certified":False}

def execute_continuity(args) -> dict:
    bars, quality = read_market_bars(args.market, date.fromisoformat(args.as_of),
                                     days=args.days, legacy_root=Path(args.legacy))
    report = audit_observation_continuity(
        bars, market=args.market, as_of=date.fromisoformat(args.as_of),
        sample_limit=args.sample_limit)
    report["cached_price_quality"] = quality
    destination=Path(args.out)/f"continuity_{args.market.lower()}_research.json"
    write_json(destination,report)
    return {"status":report["status"],"path":str(destination),
            "observed_security_count":report["observed_security_count"],
            "internal_gap_event_count":report["internal_gap_event_count"],
            "right_boundary_last_observations":report["right_boundary_last_observations"],
            "historic_universe_pit_certified":False}

def execute_calendar_audit(args) -> dict:
    asof=date.fromisoformat(args.as_of)
    bars, quality=read_market_bars(args.market,asof,days=args.days,
                                  legacy_root=Path(args.legacy))
    report=audit_exchange_calendar(Path(args.file),bars,market=args.market,
                                   as_of=asof,sample_limit=args.sample_limit)
    report["cached_price_quality"]=quality
    target=Path(args.out)/f"calendar_{args.market.lower()}_research.json"
    write_json(target,report)
    return {"status":report["status"],"path":str(target),
            "reference_only_missing_market_periods":report["reference_only_missing_market_periods"],
            "feed_only_unexpected_periods":report["feed_only_unexpected_periods"],
            "calendar_pit_certified":False}

def execute_cash_delist(args) -> dict:
    bundle=json.loads(Path(args.file).read_text(encoding="utf-8"))
    if not isinstance(bundle,dict) or bundle.get("schema_version")!="cash_delist_research_v1":
        raise ValueError("Unsupported cash-delisting research schema")
    if bundle.get("price_basis")!="raw_unadjusted":
        raise ValueError("Raw unadjusted price basis required")
    if bool(args.decision_lineage) != bool(args.evaluation_lineage):
        raise ValueError("Two dated issuer lineage vintages must be provided together")
    if args.require_lineage_amount_claims and not args.decision_lineage:
        raise ValueError("Strict lineage amounts require two issuer vintages")
    if (args.settlement_receipt or args.require_settlement_receipt) and not args.decision_lineage:
        raise ValueError("Payment evidence receipt requires both issuer vintages")
    if args.decision_lineage:
        result=audit_dual_vintage_cash_exit(
            Path(args.file),Path(args.decision_lineage),Path(args.evaluation_lineage),
            security_id=args.security_id,market=args.market,
            decision_at=args.decision_at,evaluated_at=args.evaluated_at,
            require_lineage_amount_claims=args.require_lineage_amount_claims,
            settlement_receipt_file=args.settlement_receipt,
            require_settlement_receipt=args.require_settlement_receipt)
    else:
        result=reconstruct_cash_delisting(
            bundle["bars"],bundle["actions"],bundle.get("settlement"),
            security_id=args.security_id,market=args.market,
            decision_at=args.decision_at,evaluated_at=args.evaluated_at,
            price_basis=bundle["price_basis"])
    target=Path(args.out)/"cash_delisting_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "cash_exit_total_return":result["cash_exit_total_return"],
            "pit_certified":False}

def execute_issuer_lineage(args) -> dict:
    result=audit_issuer_lineage(Path(args.file),decision_at=args.decision_at,
                                sample_limit=args.sample_limit)
    target=Path(args.out)/f"issuer_lineage_{result['market'].lower()}_research.json"
    write_json(target,result)
    return {"status":result["status"],"path":str(target),
            "active_ticker_conflict_count":result["active_ticker_conflict_count"],
            "observed_tickers_unmatched_count":result["observed_tickers_unmatched_count"],
            "historic_membership_pit_certified":False}

def execute_evidence_gate(args) -> dict:
    report=evaluate_local_evidence(Path(args.input_root),market=args.market,
                                   decision_at=args.decision_at)
    target=Path(args.out)/f"evidence_gate_{args.market.lower()}_research.json"
    write_json(target,report)
    page=write_evidence_gate_dashboard(report,Path(args.out)/"site")
    return {"status":report["status"],"path":str(target),
            "dashboard":str(page),
            "present_domains":report["present_domains"],
            "blocker_count":report["blocker_count"],
            "official_promotion_allowed":False}

def execute_watch_operating_reports(args) -> dict:
    brief=compile_watch_operating_report(
        Path(args.watch_ledger),market=args.market,
        model_version=args.model_version,evaluated_at=args.evaluated_at,
        max_age_days=args.max_age_days,sample_limit=args.sample_limit,
        score_ledger=Path(args.score_history) if args.score_history else None,
        feature_root=Path(args.feature_root) if args.feature_root else None,
    )
    return write_watch_operating_reports(brief,Path(args.out))

def execute_watch_progression(args) -> dict:
    result=audit_watch_progression(Path(args.ledger),market=args.market,
                                   model_version=args.model_version,
                                   max_registration_lag_days=args.max_lag_days)
    dest=Path(args.out)/f"watch_progression_{args.market.lower()}_research.json"
    write_json(dest,result)
    page=write_watch_progression_dashboard(result,Path(args.out)/"site")
    return {"status":result["status"],"path":str(dest),
            "dashboard":str(page),
            "prospective_observations":result["eligible_prospective_observations"],
            "historical_backfills":result["excluded_retrospective_observations"],
            "official_state_promotions":0}

def execute_watch_rotation(args) -> dict:
    result=audit_watch_rotation(Path(args.ledger),market=args.market,
                                model_version=args.model_version,
                                evaluated_at=args.evaluated_at,
                                sample_limit=args.sample_limit)
    dest=Path(args.out)/f"watch_rotation_{args.market.lower()}_research.json"
    write_json(dest,result)
    dashboard=write_watch_rotation_dashboard(result,Path(args.out)/"site")
    return {"status":result["status"],"path":str(dest),
            "dashboard":str(dashboard),
            "rotation_hypothesis_count":result["rotation_hypothesis_count"],
            "official_leader_replacements":0,
            "historic_pit_certified":False}

def execute_record_peer_scores(args) -> dict:
    return record_peer_score_series(
        Path(args.score_history),Path(args.watch_ledger),Path(args.feature_root),
        market=args.market,model_version=args.model_version)

def execute_audit_peer_score_rotation(args) -> dict:
    result=audit_peer_score_advantage(
        Path(args.watch_ledger),Path(args.score_history),Path(args.feature_root),
        market=args.market,model_version=args.model_version,
        evaluated_at=args.evaluated_at,sample_limit=args.sample_limit)
    dest=Path(args.out)/f"peer_score_rotation_{args.market.lower()}_research.json"
    write_json(dest,result)
    dashboard=write_peer_score_rotation_dashboard(result,Path(args.out)/"site")
    return {"status":result["status"],"path":str(dest),
            "dashboard":str(dashboard),
            "rotation_hypotheses":result["rotation_hypothesis_count"],
            "locally_two_session_score_correlated":result["locally_two_session_score_correlated"],
            "official_leader_replacements":0,
            "rank_scores_independently_authenticated":False}

def execute_register_rank_scores(args) -> dict:
    return register_rank_scores(Path(args.score_ledger),Path(args.watch_ledger),
                                Path(args.features_dir),Path(args.scores),
                                market=args.market,model_version=args.model_version)

def execute_compute_rank_scores(args) -> dict:
    return compute_and_register_rank_scores(
        Path(args.features_dir),Path(args.watch_ledger),Path(args.score_ledger),
        market=args.market,model_version=args.model_version)

def execute_freeze_native_topk(args) -> dict:
    return freeze_native_topk(
        Path(args.score_ledger), Path(args.watch_ledger), Path(args.features_dir),
        Path(args.label_definition_file), Path(args.out_file),
        market=args.market, model_version=args.model_version,
        label_definition_id=args.label_definition_id,
        horizon_days=args.horizon_days, k=args.k,
        max_age_hours=args.max_age_hours,
    )


def execute_audit_native_scores(args) -> dict:
    result=audit_computed_rank_provenance(
        Path(args.frozen_rank),Path(args.score_ledger),Path(args.features_dir),
        watch_db=Path(args.watch_ledger))
    output=Path(args.out)/f"native_score_{result['market'].lower()}_research.json"
    write_json(output,result)
    return {"status":result["status"],"path":str(output),
            "locally_computed_score_records_matched":result["locally_computed_score_records_matched"],
            "blocker_count":result["blocker_count"],
            "real_future_leader_skill_certified":False,
            "official_leader_promotions":0}

def execute_audit_rank_scores(args) -> dict:
    result=audit_frozen_rank_scores(Path(args.frozen_rank),
                                    Path(args.score_ledger),Path(args.features_dir))
    path=Path(args.out)/f"rank_score_{result['market'].lower()}_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "matched":result["local_numeric_score_records_matched"],
            "blocker_count":result["blocker_count"],
            "score_computation_independently_verified":False,
            "real_leader_prediction_certified":False}

def execute_ranked_registry(args) -> dict:
    result=audit_ranked_watch_registry(
        Path(args.frozen_rank),Path(args.ledger),
        max_registration_lag_days=args.max_lag_days)
    path=Path(args.out)/f"ranked_registry_{result['market'].lower()}_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "ranked_candidate_count":result["ranked_candidate_count"],
            "matched":result["ranked_ids_and_first_timestamps_matched"],
            "blocker_count":result["blocker_count"],
            "prospective_discovery_skill_certified":False,
            "official_leader_promotions":0}

def execute_pit_chain(args) -> dict:
    result=audit_pit_to_outcome_chain(
        market=args.market,decision_at=args.decision_at,
        evaluated_at=args.evaluated_at,report_dir=Path(args.report_dir),
        frozen_file=Path(args.freeze_file),
        outcome_file=Path(args.outcomes) if args.outcomes else None,
        receipt_manifest=Path(args.receipt_manifest) if args.receipt_manifest else None)
    path=Path(args.out)/f"pit_chain_{args.market.lower()}_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "blocker_count":result["blocker_count"],
            "frozen_candidate_count":result["frozen_candidate_count"],
            "internally_evaluable_research_labels":
                result["internally_evaluable_research_labels"],
            "official_leader_promotions":0,
            "leader_prediction_accuracy_certified":False}

def execute_outcome_source_claims(args) -> dict:
    result=audit_outcome_source_claims(
        Path(args.freeze_file),Path(args.outcomes),Path(args.receipt_manifest),
        evaluated_at=args.evaluated_at,sample_limit=args.sample_limit,
        require_document_label_binding=args.require_document_label_binding)
    path=Path(args.out)/"outcome_source_claims_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "internally_evaluable_outcomes":result["internally_evaluable_outcomes"],
            "local_source_claims_consistent":result["local_source_claims_consistent"],
            "blocker_count":result["blocker_count"],
            "independently_source_authenticated":False,
            "actual_leader_prediction_certified":False}

def execute_holdout_reconciliation(args) -> dict:
    result=reconcile_holdout_outcomes(
        Path(args.freeze_file), evaluated_at=args.evaluated_at,
        outcome_file=Path(args.outcomes) if args.outcomes else None,
        sample_limit=args.sample_limit)
    path=Path(args.out)/"holdout_outcome_reconciliation_research.json"
    write_json(path,result)
    return {"status":result["status"],"path":str(path),
            "frozen_candidates":result["frozen_candidates"],
            "horizon_elapsed_count":result["horizon_elapsed_count"],
            "internally_evaluable_outcome_count":
                result["internally_evaluable_outcome_count"],
            "unknown_or_censored_count":result["unknown_or_censored_count"],
            "official_leader_promotions":0,
            "leader_accuracy_certified":False}

def execute_holdout_maturity(args) -> dict:
    result = audit_holdout_maturity(
        Path(args.freeze_file), as_of=args.as_of, sample_limit=args.sample_limit)
    path = Path(args.out) / "holdout_maturity_research.json"
    write_json(path, result)
    return {"status":result["status"],"path":str(path),
            "eligible_frozen_candidates":result["eligible_frozen_candidates"],
            "horizon_elapsed_count":result["horizon_elapsed_count"],
            "horizon_pending_count":result["horizon_pending_count"],
            "actual_known_outcomes":0,"official_leader_promotions":0}

def execute_publication_verify(args) -> dict:
    verified=verify_pit_publication(Path(args.out))
    if verified is None:
        return {"status":"NO_PUBLISHED_PIT_RESEARCH_GENERATION",
                "official_leaders":0,"pit_certified":False}
    return verified

def execute_backup(args) -> dict:
    if args.command=="backup-local":
        return create_backup(Path(args.out),Path(args.archive))
    if args.command=="verify-backup":
        return verify_backup(Path(args.archive))
    return restore_backup(Path(args.archive),Path(args.target))

def main(argv=None):
    parser=argparse.ArgumentParser(prog="eraleader",description="Offline EraLeader prototype (APIs disabled)")
    parser.add_argument("--version",action="version",version=__version__)
    sub=parser.add_subparsers(dest="command",required=True)
    def common(name):
        p=sub.add_parser(name)
        p.add_argument("--market",choices=["KR","US"],default="KR")
        p.add_argument("--as-of",default="2026-10-02" if name!="baseline" else "2025-12-30")
        p.add_argument("--legacy",default=str(LEGACY_DEFAULT))
        p.add_argument("--out",default=str(OUT))
        p.add_argument("--days",type=int,default=550)
        p.add_argument("--tickers",nargs="*")
        return p
    run=common("run")
    run.add_argument("--top",type=int,default=20)
    baseline=common("baseline")
    baseline.add_argument("--top",type=int,default=3)
    baseline.add_argument("--lookback",type=int,default=26)
    baseline.add_argument("--rebalance",type=int,default=4)
    rep=sub.add_parser("report")
    rep.add_argument("period",choices=["daily","weekly","monthly"])
    rep.add_argument("--market",choices=["KR","US"],default="KR")
    rep.add_argument("--out",default=str(OUT))
    al=sub.add_parser("alerts-preview")
    al.add_argument("--out",default=str(OUT))
    srv=sub.add_parser("serve")
    srv.add_argument("--out",default=str(OUT))
    srv.add_argument("--port",type=int,default=8765)
    importer=sub.add_parser("offline-import",help="Import locally available CSV/JSON without API calls")
    importer.add_argument("--file",required=True)
    importer.add_argument("--kind",choices=["membership","actions","fundamentals","industry"])
    importer.add_argument("--provenance",choices=["synthetic_fixture","external_public_file","user_supplied"])
    importer.add_argument("--out",default=str(OUT))
    features=sub.add_parser("offline-features",help="Research-only PIT-aware growth diagnostics")
    features.add_argument("--market",choices=["KR","US"],default="KR")
    features.add_argument("--as-of",required=True,help="Timezone-aware ISO timestamp")
    features.add_argument("--out",default=str(OUT))
    peer=sub.add_parser("audit-peer-normalization",help="Research-only same-industry as-of percentiles")
    peer.add_argument("--input",required=True,help="Existing offline-features JSON")
    peer.add_argument("--out",required=True,help="New derived JSON; never overwrite")
    peer.add_argument("--min-peers",type=int,default=3)
    bridge=sub.add_parser("prepare-rank-features",
            help="Make present-written four-factor input JSON from as-of offline+price research")
    bridge.add_argument("--offline",required=True,help="Existing offline-features JSON")
    bridge.add_argument("--price",required=True,help="Existing same-day price run JSON")
    bridge.add_argument("--features-dir",required=True,help="New output directory (no overwrite)")
    bridge.add_argument("--model-version",required=True)
    bridge.add_argument("--min-peers",type=int,default=3)
    bridge.add_argument("--offline-ledger",help="Optional original offline.sqlite read-only PIT recomputation gate")
    bridge.add_argument("--price-cache-root",help="Optional existing read-only KR/US price cache to recheck displayed raw returns")
    bridge.add_argument("--cache-days",type=int,default=550)
    join=sub.add_parser('offline-integrated',help='PIT-aligned research join')
    join.add_argument('--market',choices=['KR','US'],default='KR')
    join.add_argument('--as-of',required=True)
    join.add_argument('--price-json')
    join.add_argument('--out',default=str(OUT))
    join.add_argument('--provider-ledger-a',help='Optional first local PIT source ledger; all four flags required')
    join.add_argument('--provider-bundle-a',help='First previously registered provider bundle SHA256')
    join.add_argument('--provider-ledger-b',help='Optional second independent claimed PIT source ledger')
    join.add_argument('--provider-bundle-b',help='Second previously registered provider bundle SHA256')
    evaluate=sub.add_parser("validate-discovery",help="Post hoc early detection quality, research only")
    evaluate.add_argument("--signals",required=True)
    evaluate.add_argument("--outcomes",required=True)
    evaluate.add_argument("--evaluated-at",required=True)
    evaluate.add_argument("--horizon-days",type=int,default=180)
    evaluate.add_argument("--out",default=str(OUT))
    wf=sub.add_parser("walkforward",help="Horizon/embargo PIT split; research only")
    wf.add_argument("--snapshots",required=True)
    wf.add_argument("--outcomes",required=True)
    wf.add_argument("--train-ends-at",required=True)
    wf.add_argument("--test-ends-at",required=True)
    wf.add_argument("--embargo-days",type=int,default=7)
    wf.add_argument("--out",default=str(OUT))
    rw=sub.add_parser("replay-walkforward",help="Repeated embargoed folds with pinned model/label; offline research only")
    rw.add_argument("--snapshots",required=True)
    rw.add_argument("--outcomes",required=True)
    rw.add_argument("--windows",required=True,help="Local JSON list of fixed fold time windows")
    rw.add_argument("--model-version",required=True)
    rw.add_argument("--label-definition-id",required=True)
    rw.add_argument("--embargo-days",type=int,default=7)
    rw.add_argument("--out",default=str(OUT))
    batch=sub.add_parser("batch",help="Explicit-date offline KR+US reporting batch")
    batch.add_argument("--kr-as-of",required=True)
    batch.add_argument("--us-as-of",required=True)
    batch.add_argument("--out",default=str(OUT))
    batch.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    batch.add_argument("--days",type=int,default=550)
    batch.add_argument("--top",type=int,default=20)
    batch.add_argument("--integrate-pit-research",action="store_true",
                       help="Explicit opt-in: join offline PIT research ledger with price reports; never certify leaders")
    batch.add_argument("--kr-decision-at",help="Timezone-aware local KR research decision timestamp")
    batch.add_argument("--us-decision-at",help="Timezone-aware local US research decision timestamp")
    cr=sub.add_parser("corporate-return",help="Offline raw split/dividend total return, research only")
    cr.add_argument("--file",required=True,help="Raw bars and announced actions JSON")
    cr.add_argument("--security-id",required=True)
    cr.add_argument("--market",choices=["KR","US"],required=True)
    cr.add_argument("--decision-at",required=True,help="Timezone-aware signal time")
    cr.add_argument("--evaluated-at",required=True,help="Timezone-aware evaluation cutoff")
    cr.add_argument("--price-basis",choices=["raw_unadjusted"],required=True)
    cr.add_argument("--out",default=str(OUT))
    ua=sub.add_parser("audit-universe",help="Historical observed listed symbols; not certified")
    ua.add_argument("--as-of",required=True)
    ua.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    ua.add_argument("--days",type=int,default=30)
    ua.add_argument("--out",default=str(OUT))
    check=sub.add_parser("audit-total-return",help="Compare raw corporate-action return and separate local total-return index")
    check.add_argument("--file",required=True,help="Offline total_return_crosscheck_v1 JSON bundle")
    check.add_argument("--security-id",required=True)
    check.add_argument("--market",choices=["KR","US"],required=True)
    check.add_argument("--decision-at",required=True)
    check.add_argument("--evaluated-at",required=True)
    check.add_argument("--tolerance-bps",type=float,default=5.0)
    check.add_argument("--session-clock",help="Optional local pre-decision declared close-time manifest")
    check.add_argument("--exchange-calendar",help="Optional separate claimed calendar with per-session closes")
    check.add_argument("--out",default=str(OUT))
    dp=sub.add_parser("audit-provider-source-pair",
                      help="Compare two separately registered local PIT bundle receipts, no official PIT certification")
    dp.add_argument("--ledger-a",required=True)
    dp.add_argument("--bundle-a",required=True)
    dp.add_argument("--ledger-b",required=True)
    dp.add_argument("--bundle-b",required=True)
    dp.add_argument("--decision-at",required=True)
    dp.add_argument("--sample-limit",type=int,default=40)
    dp.add_argument("--out",default=str(OUT))
    lineage=sub.add_parser("audit-provider-staged-lineage",
                          help="Recheck original staged source lines/doc IDs -> normalized bytes -> optional first PIT ingest")
    lineage.add_argument("--staged-manifest",required=True)
    lineage.add_argument("--normalized-manifest",required=True)
    lineage.add_argument("--ledger",help="Optional local first-ingest SQLite receipt; missing means no timely PIT claim")
    lineage.add_argument("--decision-at",required=True)
    lineage.add_argument("--out",default=str(OUT))
    pe=sub.add_parser("normalize-provider-export",
                      help="Offline staged KRX/DART or SEC/exchange declared exports into provider-neutral JSONL")
    pe.add_argument("--manifest",required=True,help="Raw staged export SHA/record-count manifest")
    pe.add_argument("--stage-dir",required=True,help="NEW empty path for generated normalized bundle")
    pe.add_argument("--out",default=str(OUT),help="Derived summary only; original/staged JSONL stay local")
    pi=sub.add_parser("import-provider-pit",
                      help="Opt-in atomic, first-clock receipt import for normalized offline source JSONL")
    pi.add_argument("--manifest",required=True,
                    help="Existing JSON manifest with SHA of local normalized source JSONL")
    pi.add_argument("--ledger",required=True,help="Local PIT SQLite target; raw sources not copied")
    pi.add_argument("--out",default=str(OUT))
    pa=sub.add_parser("audit-provider-pit-asof",
                      help="Reject post-decision ingestion as historical PIT evidence")
    pa.add_argument("--ledger",required=True)
    pa.add_argument("--bundle-sha256",required=True)
    pa.add_argument("--decision-at",required=True)
    pa.add_argument("--out",default=str(OUT))
    readiness=sub.add_parser("audit-pit-provider-readiness",
                       help="Read real local KR/US price cache and offline PIT coverage without promoting leaders")
    readiness.add_argument("--cache-root",default=str(LEGACY_DEFAULT))
    readiness.add_argument("--kr-ledger",help="Optional existing KR PIT SQLite")
    readiness.add_argument("--us-ledger",help="Optional existing US PIT SQLite")
    readiness.add_argument("--evaluated-at",required=True)
    readiness.add_argument("--max-price-age-days",type=int,default=7)
    readiness.add_argument("--out",default=str(OUT))
    provenance=sub.add_parser("audit-source-vintage",help="Hash and as-of audit local source vintages without PIT certification")
    provenance.add_argument("--manifest",required=True,help="Local source_vintage_manifest_v1 JSON")
    provenance.add_argument("--decision-at",required=True,help="Timezone-aware as-of cutoff")
    provenance.add_argument("--out",default=str(OUT))
    rs=sub.add_parser("record-rank-scores",
                      help="Write immutable local numeric scores with real OS recording time; never certify score calculation")
    rs.add_argument("--market",choices=["KR","US"],required=True)
    rs.add_argument("--model-version",required=True)
    rs.add_argument("--scores",required=True)
    rs.add_argument("--features-dir",required=True)
    rs.add_argument("--watch-ledger",required=True)
    rs.add_argument("--score-ledger",required=True)
    auto_rs=sub.add_parser("compute-rank-scores",
                           help="Compute fixed four-factor research scores and timestamp-link to first WATCH")
    auto_rs.add_argument("--market",choices=["KR","US"],required=True)
    auto_rs.add_argument("--model-version",required=True)
    auto_rs.add_argument("--features-dir",required=True)
    auto_rs.add_argument("--watch-ledger",required=True)
    auto_rs.add_argument("--score-ledger",required=True)
    seal=sub.add_parser("freeze-native-topk",
                        help="Safely seal all first-WRITTEN four-factor scores for one prospective WATCH cohort")
    seal.add_argument("--market", choices=["KR", "US"], required=True)
    seal.add_argument("--model-version", required=True)
    seal.add_argument("--score-ledger", required=True)
    seal.add_argument("--watch-ledger", required=True)
    seal.add_argument("--features-dir", required=True)
    seal.add_argument("--label-definition-file", required=True)
    seal.add_argument("--label-definition-id", required=True)
    seal.add_argument("--horizon-days", type=int, required=True)
    seal.add_argument("--k", type=int, required=True)
    seal.add_argument("--max-age-hours", type=int, default=24)
    seal.add_argument("--out-file", required=True, help="Exclusive new local frozen-cohort JSON path")
    native=sub.add_parser("audit-native-rank-scores",
                          help="Verify sealed rank against persisted formula digest and recomputed four-factor source")
    native.add_argument("--frozen-rank",required=True)
    native.add_argument("--score-ledger",required=True)
    native.add_argument("--features-dir",required=True)
    native.add_argument("--watch-ledger",required=True)
    native.add_argument("--out",default=str(OUT))
    ra=sub.add_parser("audit-rank-scores",
                      help="Match pinned frozen top-K numeric scores to original local score-entry time and feature hashes")
    ra.add_argument("--frozen-rank",required=True)
    ra.add_argument("--score-ledger",required=True)
    ra.add_argument("--features-dir",required=True)
    ra.add_argument("--out",default=str(OUT))
    rr=sub.add_parser("audit-ranked-registry",
                      help="Audit frozen top-K ranks against actually registered WATCH ledger IDs and timestamps")
    rr.add_argument("--frozen-rank",required=True)
    rr.add_argument("--ledger",required=True)
    rr.add_argument("--max-lag-days",type=int,default=3)
    rr.add_argument("--out",default=str(OUT))
    chain=sub.add_parser("audit-pit-chain",
                         help="Reconcile market-local PIT audits and sealed research outcome receipts; never certify leader skill")
    chain.add_argument("--market",choices=["KR","US"],required=True)
    chain.add_argument("--decision-at",required=True)
    chain.add_argument("--evaluated-at",required=True)
    chain.add_argument("--report-dir",required=True)
    chain.add_argument("--freeze-file",required=True)
    chain.add_argument("--outcomes",help="Optional separate outcome label JSON")
    chain.add_argument("--receipt-manifest",help="Required together with --outcomes")
    chain.add_argument("--out",default=str(OUT))
    rank_docs=sub.add_parser("audit-ranked-outcome-receipts",
                      help="Compare predeclared top-K ranked labels to dated local document receipts; NOT certified accuracy")
    rank_docs.add_argument("--freeze",required=True)
    rank_docs.add_argument("--outcomes",required=True)
    rank_docs.add_argument("--receipt-manifest",required=True)
    rank_docs.add_argument("--definition-file",required=True,
                           help="Original predeclared leader rule JSON bytes, SHA pinned in freeze")
    rank_docs.add_argument("--evaluated-at",required=True)
    rank_docs.add_argument("--sample-limit",type=int,default=100)
    rank_docs.add_argument("--out",default=str(OUT))
    source_claims=sub.add_parser("audit-outcome-source-claims",
                       help="Audit label source document SHA/chronology; never certify issuer PIT or outcome accuracy")
    source_claims.add_argument("--freeze-file",required=True)
    source_claims.add_argument("--outcomes",required=True)
    source_claims.add_argument("--receipt-manifest",required=True)
    source_claims.add_argument("--evaluated-at",required=True)
    source_claims.add_argument("--sample-limit",type=int,default=100)
    source_claims.add_argument("--require-document-label-binding",action="store_true",
        help="Require normalized local evidence JSON to match each exact supplied outcome label")
    source_claims.add_argument("--out",default=str(OUT))
    reconcile=sub.add_parser("reconcile-holdout-outcomes",
                       help="Match matured sealed cohort and separate research labels; never claim verified accuracy")
    reconcile.add_argument("--freeze-file",required=True)
    reconcile.add_argument("--outcomes",help="Optional local unverified outcome label array")
    reconcile.add_argument("--evaluated-at",required=True)
    reconcile.add_argument("--sample-limit",type=int,default=100)
    reconcile.add_argument("--out",default=str(OUT))
    maturity=sub.add_parser("audit-holdout-maturity",
                      help="Calendar-only full-horizon readiness; does NOT generate leader outcomes")
    maturity.add_argument("--freeze-file",required=True)
    maturity.add_argument("--as-of",required=True,help="Timezone-aware audit timestamp not in future")
    maturity.add_argument("--sample-limit",type=int,default=20)
    maturity.add_argument("--out",default=str(OUT))
    rp=sub.add_parser("freeze-rotation-pairs",
                      help="Seal two-score WATCH rotation pair cohort before any future labels")
    rp.add_argument("--watch-ledger",required=True)
    rp.add_argument("--score-history",required=True)
    rp.add_argument("--feature-root",required=True)
    rp.add_argument("--market",choices=["KR","US"],required=True)
    rp.add_argument("--model-version",required=True)
    rp.add_argument("--label-definition-id",required=True)
    rp.add_argument("--horizon-days",type=int,default=180)
    rp.add_argument("--freeze-file",required=True,
                    help="New exclusive frozen pair JSON; prior cohort cannot be overwritten")
    ra=sub.add_parser("audit-rotation-pair-outcomes",
                      help="Reconcile only separately dated mature pair labels; never actual alpha proof")
    ra.add_argument("--freeze-file",required=True)
    ra.add_argument("--evaluated-at",required=True)
    ra.add_argument("--outcomes",help="Separate later local self-declared issuer labels")
    ra.add_argument("--sample-limit",type=int,default=100)
    ra.add_argument("--out",default=str(OUT))
    rs=sub.add_parser("audit-rotation-pair-sources",
                      help="Match two mature pair issuer label documents; no external publisher proof")
    rs.add_argument("--freeze-file",required=True)
    rs.add_argument("--outcomes",required=True,help="Later separate declared future-label JSON")
    rs.add_argument("--receipt-manifest",required=True,help="Local normalized source receipt manifest")
    rs.add_argument("--evaluated-at",required=True)
    rs.add_argument("--sample-limit",type=int,default=100)
    rs.add_argument("--out",default=str(OUT))
    hf=sub.add_parser("freeze-holdout",help="Seal an actual-registration research holdout before future labels")
    hf.add_argument("--ledger",required=True,help="Existing prospective.sqlite")
    hf.add_argument("--market",choices=["KR","US"],required=True)
    hf.add_argument("--model-version",required=True)
    hf.add_argument("--label-definition-id",required=True,help="Predeclared label rule version; no post-hoc changes")
    hf.add_argument("--horizon-days",type=int,default=180)
    hf.add_argument("--max-lag-days",type=int,default=3)
    hf.add_argument("--freeze-file",required=True,help="New output JSON path; existing path never overwritten")
    he=sub.add_parser("evaluate-holdout",help="Post-freeze mature-outcome evaluation (research only)")
    he.add_argument("--freeze-file",required=True)
    he.add_argument("--outcomes",required=True,help="Separate published/mature outcomes JSON")
    he.add_argument("--evaluated-at",required=True)
    he.add_argument("--horizon-days",type=int,help="Optional consistency check against frozen horizon; cannot override")
    he.add_argument("--out",default=str(OUT))
    prospect=sub.add_parser("prospective-signals",help="Export first actually registered research WATCH signals")
    prospect.add_argument("--market",choices=["KR","US"],required=True)
    prospect.add_argument("--out",default=str(OUT))
    cv=sub.add_parser("audit-pit-coverage",help="Compare observed prices to an offline PIT listing ledger; not certified")
    cv.add_argument("--market",choices=["KR","US"],required=True)
    cv.add_argument("--as-of",required=True,help="Timezone-aware decision timestamp")
    cv.add_argument("--ledger",required=True,help="Existing imported offline PIT SQLite")
    cv.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    cv.add_argument("--days",type=int,default=35)
    cv.add_argument("--out",default=str(OUT))
    co=sub.add_parser("audit-continuity",help="Historical observed-symbol gaps, not official delisting")
    co.add_argument("--market",choices=["KR","US"],required=True)
    co.add_argument("--as-of",required=True)
    co.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    co.add_argument("--days",type=int,default=120)
    co.add_argument("--sample-limit",type=int,default=20)
    co.add_argument("--out",default=str(OUT))
    ca=sub.add_parser("audit-calendar",help="Compare offline claimed exchange sessions to cached price bars")
    ca.add_argument("--file",required=True,help="Local exchange calendar JSON, not independently certified")
    ca.add_argument("--market",choices=["KR","US"],required=True)
    ca.add_argument("--as-of",required=True)
    ca.add_argument("--legacy",default=str(LEGACY_DEFAULT))
    ca.add_argument("--days",type=int,default=120)
    ca.add_argument("--sample-limit",type=int,default=20)
    ca.add_argument("--out",default=str(OUT))
    cd=sub.add_parser("audit-cash-delist",help="Explicit cash delist payout without invented proceeds")
    cd.add_argument("--file",required=True,help="Local cash_delist_research_v1 JSON")
    cd.add_argument("--security-id",required=True)
    cd.add_argument("--market",choices=["KR","US"],required=True)
    cd.add_argument("--decision-at",required=True)
    cd.add_argument("--evaluated-at",required=True)
    cd.add_argument("--decision-lineage",help="As-of-decision issuer JSON (research-only)")
    cd.add_argument("--evaluation-lineage",help="Later issuer/corporate event JSON (research-only)")
    cd.add_argument("--require-lineage-amount-claims",action="store_true",
                    help="Block missing local split/dividend/cash amount claims (not independent PIT proof)")
    cd.add_argument("--settlement-receipt",
                    help="Local cash-payment document receipt manifest (not authenticated)")
    cd.add_argument("--require-settlement-receipt",action="store_true",
                    help="Censor a missing cash settlement receipt")
    cd.add_argument("--out",default=str(OUT))
    ii=sub.add_parser("audit-issuer-lineage",help="Offline permanent issuer/ticker/event identity conflicts")
    ii.add_argument("--file",required=True,help="Local eraleader.issuer_lineage_research.v1 input")
    ii.add_argument("--decision-at",required=True,help="Timezone-aware decision timestamp")
    ii.add_argument("--sample-limit",type=int,default=20)
    ii.add_argument("--out",default=str(OUT))
    eg=sub.add_parser("audit-evidence-gate",help="Combine local PIT audit blockers without certification")
    eg.add_argument("--market",choices=["KR","US"],required=True)
    eg.add_argument("--decision-at",required=True)
    eg.add_argument("--input-root",required=True,help="Existing local derived audit JSON directory")
    eg.add_argument("--out",default=str(OUT))
    wo=sub.add_parser("report-watch-operations",
                      help="As-of daily/weekly/monthly research WATCH operating briefs; never official leaders")
    wo.add_argument("--watch-ledger",required=True)
    wo.add_argument("--market",choices=["KR","US"],required=True)
    wo.add_argument("--model-version",required=True)
    wo.add_argument("--evaluated-at",required=True,help="Timezone-aware as-of cutoff, not future")
    wo.add_argument("--max-age-days",type=int,default=7)
    wo.add_argument("--sample-limit",type=int,default=50)
    wo.add_argument("--score-history",help="Optional existing peer-score SQLite; also requires --feature-root")
    wo.add_argument("--feature-root",help="Optional local historical feature directory, never uploaded")
    wo.add_argument("--out",default=str(OUT))
    wp=sub.add_parser("audit-watch-progression",help="Explicit research WATCH hits, weakness and re-entry, never official leaders")
    wp.add_argument("--ledger",required=True)
    wp.add_argument("--market",choices=["KR","US"],required=True)
    wp.add_argument("--model-version",required=True)
    wp.add_argument("--max-lag-days",type=int,default=3)
    wp.add_argument("--out",default=str(OUT))
    wr=sub.add_parser("audit-watch-rotation",
                      help="Read-only peer WATCH weakening/replacement hypotheses, never certified leaders")
    wr.add_argument("--ledger",required=True)
    wr.add_argument("--market",choices=["KR","US"],required=True)
    wr.add_argument("--model-version",required=True)
    wr.add_argument("--evaluated-at",required=True,help="Timezone-aware as-of cutoff")
    wr.add_argument("--sample-limit",type=int,default=100)
    wr.add_argument("--out",default=str(OUT))
    ps=sub.add_parser("record-peer-scores",
                      help="Append fixed-formula daily peer scores to separate prospective SQLite history")
    ps.add_argument("--watch-ledger",required=True)
    ps.add_argument("--score-history",required=True)
    ps.add_argument("--feature-root",required=True)
    ps.add_argument("--market",choices=["KR","US"],required=True)
    ps.add_argument("--model-version",required=True)
    asr=sub.add_parser("audit-peer-score-rotation",
                       help="Read-only two-session peer score corroboration, never official leaders")
    asr.add_argument("--watch-ledger",required=True)
    asr.add_argument("--score-history",required=True)
    asr.add_argument("--feature-root",required=True)
    asr.add_argument("--market",choices=["KR","US"],required=True)
    asr.add_argument("--model-version",required=True)
    asr.add_argument("--evaluated-at",required=True)
    asr.add_argument("--sample-limit",type=int,default=100)
    asr.add_argument("--out",default=str(OUT))
    pv=sub.add_parser("verify-pit-publication",
                      help="Verify current immutable KR+US PIT research generation, never official leader data")
    pv.add_argument("--out",required=True)
    bkp=sub.add_parser("backup-local",help="Consistent SQLite + safe local output archive")
    bkp.add_argument("--out",default=str(OUT))
    bkp.add_argument("--archive",required=True)
    vb=sub.add_parser("verify-backup",help="Check archive hashes and approved paths")
    vb.add_argument("--archive",required=True)
    rb=sub.add_parser("restore-backup",help="Restore only to a new empty path")
    rb.add_argument("--archive",required=True)
    rb.add_argument("--target",required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=="run":result=execute_run(args)
        elif args.command=="baseline":result=execute_baseline(args)
        elif args.command=="report":result=execute_report(args)
        elif args.command=="alerts-preview":result=execute_alerts(args)
        elif args.command=="offline-import":result=execute_offline_import(args)
        elif args.command=="offline-features":result=execute_offline_features(args)
        elif args.command=="audit-peer-normalization":result=execute_peer_normalization(args)
        elif args.command=="prepare-rank-features":result=execute_rank_feature_inputs(args)
        elif args.command=="offline-integrated":result=execute_integrated(args)
        elif args.command=="validate-discovery":result=execute_validation(args)
        elif args.command=="walkforward":result=execute_walkforward(args)
        elif args.command=="replay-walkforward":result=execute_repeated_walkforward(args)
        elif args.command=="corporate-return":result=execute_corporate_research(args)
        elif args.command=="audit-universe":result=execute_universe_audit(args)
        elif args.command=="audit-continuity":result=execute_continuity(args)
        elif args.command=="audit-calendar":result=execute_calendar_audit(args)
        elif args.command=="audit-cash-delist":result=execute_cash_delist(args)
        elif args.command=="audit-issuer-lineage":result=execute_issuer_lineage(args)
        elif args.command=="audit-evidence-gate":result=execute_evidence_gate(args)
        elif args.command=="report-watch-operations":result=execute_watch_operating_reports(args)
        elif args.command=="audit-watch-progression":result=execute_watch_progression(args)
        elif args.command=="audit-watch-rotation":result=execute_watch_rotation(args)
        elif args.command=="record-peer-scores":result=execute_record_peer_scores(args)
        elif args.command=="audit-peer-score-rotation":result=execute_audit_peer_score_rotation(args)
        elif args.command=="verify-pit-publication":result=execute_publication_verify(args)
        elif args.command=="audit-holdout-maturity":result=execute_holdout_maturity(args)
        elif args.command=="reconcile-holdout-outcomes":result=execute_holdout_reconciliation(args)
        elif args.command=="audit-ranked-outcome-receipts":result=execute_ranked_outcome_receipts(args)
        elif args.command=="audit-outcome-source-claims":result=execute_outcome_source_claims(args)
        elif args.command=="audit-pit-chain":result=execute_pit_chain(args)
        elif args.command=="audit-ranked-registry":result=execute_ranked_registry(args)
        elif args.command=="record-rank-scores":result=execute_register_rank_scores(args)
        elif args.command=="compute-rank-scores":result=execute_compute_rank_scores(args)
        elif args.command=="freeze-native-topk":result=execute_freeze_native_topk(args)
        elif args.command=="audit-native-rank-scores":result=execute_audit_native_scores(args)
        elif args.command=="audit-rank-scores":result=execute_audit_rank_scores(args)
        elif args.command=="audit-pit-coverage":result=execute_coverage(args)
        elif args.command=="prospective-signals":result=execute_prospective_export(args)
        elif args.command=="audit-total-return":result=execute_return_crosscheck(args)
        elif args.command=="freeze-rotation-pairs":result=execute_freeze_rotation_pairs(args)
        elif args.command=="audit-rotation-pair-outcomes":result=execute_rotation_pair_outcomes(args)
        elif args.command=="audit-rotation-pair-sources":result=execute_rotation_pair_sources(args)
        elif args.command=="freeze-holdout":result=execute_freeze_holdout(args)
        elif args.command=="evaluate-holdout":result=execute_evaluate_holdout(args)
        elif args.command=="audit-provider-source-pair":result=execute_provider_source_pair(args)
        elif args.command=="normalize-provider-export":result=execute_normalize_provider_export(args)
        elif args.command=="audit-provider-staged-lineage":result=execute_staged_source_lineage(args)
        elif args.command=="import-provider-pit":result=execute_provider_pit_import(args)
        elif args.command=="audit-provider-pit-asof":result=execute_provider_pit_asof(args)
        elif args.command=="audit-pit-provider-readiness":result=execute_pit_provider_readiness(args)
        elif args.command=="audit-source-vintage":result=execute_source_vintage(args)
        elif args.command in ("backup-local","verify-backup","restore-backup"):
            result=execute_backup(args)
        elif args.command=="batch":
            from .batch import execute_local_batch
            result=execute_local_batch(args)
        else:
            site=Path(args.out)/"site"
            site.mkdir(parents=True,exist_ok=True)
            handler=partial(SimpleHTTPRequestHandler,directory=str(site))
            with ThreadingHTTPServer(("127.0.0.1",args.port),handler) as httpd:
                print(f"EraLeader local: http://127.0.0.1:{args.port}/",flush=True)
                httpd.serve_forever()
            return
    except (ValueError,OSError,RuntimeError) as exc:
        parser.exit(2,f"EraLeader ERROR: {exc}\n")
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
