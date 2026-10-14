#!/usr/bin/env python3
"""Generate a read-only LOCAL operations status page. No live APIs or alerts."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys


def main(argv=None):
    parser=ArgumentParser(description="Offline EraLeader research operations health")
    parser.add_argument("--project",type=Path,required=True,
                        help="Existing EraLeader root (report writes only under output/operations)")
    parser.add_argument("--include-local-outbox",action="store_true",
                        help="Opt-in read-only joined operations/outbox page, no delivery")
    parser.add_argument("--marketwide-source-root",type=Path,default=None,
                        help="Opt-in refresh of latest already-verified KR marketwide research under a source output folder")
    parser.add_argument("--marketwide-publish-outbox",action="store_true",
                        help="Opt-in project-neutral PRICE WATCH20 JSON only; no recipient or orders")
    parser.add_argument("--marketwide-record-watch-history",action="store_true",
                        help="Opt-in price-only WATCH StateHistory in own SQLite; no formal leader transitions")
    parser.add_argument("--marketwide-derive-partial-factors",action="store_true",
                        help="Opt-in source-backed price+earnings partial Stage4 WATCH; no invented other scores")
    parser.add_argument("--marketwide-peer-flow-research",action="store_true",
                        help="Opt-in sector peer growth ranks and raw same-session flow research (not formal scores)")
    parser.add_argument("--marketwide-flow-coverage",action="store_true",
                        help="Show SHA-verified cumulative selected-stock Kiwoom demo flow, read only")
    parser.add_argument("--marketwide-flow-diagnostics",action="store_true",
                        help="Opt-in observed 5/20-share flows / KRX market-cap implied shares proxy, no trades")
    parser.add_argument("--marketwide-volume-alignment",action="store_true",
                        help="Opt-in read-only marcap volume cache date coverage for selected Kiwoom flow")
    args=parser.parse_args(argv)
    if args.marketwide_volume_alignment and args.marketwide_source_root is None:
        raise ValueError("Volume alignment requires --marketwide-source-root")
    if args.marketwide_flow_diagnostics and args.marketwide_source_root is None:
        raise ValueError("Flow diagnostics require --marketwide-source-root")
    if args.marketwide_flow_coverage and args.marketwide_source_root is None:
        raise ValueError("Flow coverage requires --marketwide-source-root")
    if args.marketwide_peer_flow_research and args.marketwide_source_root is None:
        raise ValueError("Peer-flow research requires --marketwide-source-root")
    if args.marketwide_record_watch_history and not args.marketwide_publish_outbox:
        raise ValueError("State history requires explicit --marketwide-publish-outbox")
    if args.marketwide_derive_partial_factors and args.marketwide_source_root is None:
        raise ValueError("Partial factors require explicit --marketwide-source-root")
    if args.marketwide_publish_outbox and args.marketwide_source_root is None:
        raise ValueError("Research outbox requires --marketwide-source-root")
    root=args.project.resolve(strict=True)
    sys.path.insert(0,str(root/"src"))
    refresh=None
    if args.marketwide_source_root is not None:
        if args.marketwide_publish_outbox:
            from eraleader.marketwide_handoff_bridge import publish_latest_marketwide_handoff
            handoff=publish_latest_marketwide_handoff(
                source_root=args.marketwide_source_root,project=root,request_day="today",
                record_watch_history=args.marketwide_record_watch_history)
            refresh={
                "status":handoff.get("search_status",handoff["status"]),
                "source_market_session":handoff.get("source_market_session"),
            }
        else:
            from eraleader.marketwide_auto_refresh import refresh_latest_marketwide
            refresh=refresh_latest_marketwide(source_root=args.marketwide_source_root,
                                             project=root,request_day="today")
    partial_stage=None
    partial_input=None
    if args.marketwide_derive_partial_factors:
        source_file=(handoff.get("source_report_file") if args.marketwide_publish_outbox
                     else refresh.get("source_report_file"))
        if source_file is not None:
            from eraleader.official_partial_factor_bridge import derive_partial_factor_input
            from eraleader.factor_selection_pipeline import run_factor_selection
            partial_input=derive_partial_factor_input(
                marketwide=Path(source_file),project=root)
            partial_stage=run_factor_selection(
                marketwide=Path(source_file),project=root,
                assessment_file=Path(partial_input["input_file"])
                if partial_input.get("input_file") else None)
    peer_flow=None
    if args.marketwide_peer_flow_research:
        source_file=(handoff.get("source_report_file") if args.marketwide_publish_outbox
                     else refresh.get("source_report_file"))
        if source_file is not None:
            from eraleader.sector_peer_flow_research import publish_marketwide_peer_flow
            peer_flow=publish_marketwide_peer_flow(marketwide=Path(source_file),project=root)
    flow_coverage=None
    if args.marketwide_flow_coverage:
        source_file=(handoff.get("source_report_file") if args.marketwide_publish_outbox
                     else refresh.get("source_report_file"))
        if source_file is not None:
            from eraleader.marketwide_flow_coverage import publish_flow_coverage
            flow_coverage=publish_flow_coverage(marketwide=Path(source_file),project=root)
    flow_diagnostics=None
    if args.marketwide_flow_diagnostics:
        source_file=(handoff.get("source_report_file") if args.marketwide_publish_outbox
                     else refresh.get("source_report_file"))
        if source_file is not None:
            from eraleader.marketwide_flow_diagnostics import publish_flow_share_proxy
            flow_diagnostics=publish_flow_share_proxy(
                marketwide=Path(source_file),project=root)
    volume_alignment=None
    if args.marketwide_volume_alignment:
        source_file=(handoff.get("source_report_file") if args.marketwide_publish_outbox
                     else refresh.get("source_report_file"))
        if source_file is not None:
            from eraleader.marketwide_volume_alignment import publish_volume_alignment
            volume_alignment=publish_volume_alignment(
                marketwide=Path(source_file),project=root)
    if args.include_local_outbox:
        from eraleader.operations_alert_bridge import publish_operations_alert_dashboard
        report=publish_operations_alert_dashboard(root)
    else:
        from eraleader.operations_overview import publish_operations_overview
        report=publish_operations_overview(root)
    if args.marketwide_publish_outbox:
        report["marketwide_handoff_status"]=handoff["status"]
        report["marketwide_handoff_watchlist_count"]=handoff["watchlist_count"]
        report["marketwide_handoff_selected_count"]=0
        report["marketwide_handoff_orders"]=0
        report["marketwide_watch_state_status"]=handoff.get("watch_history_status","NOT_REQUESTED")
        report["marketwide_watch_state_rows"]=handoff.get("watch_history_rows",0)
        report["marketwide_verified_leader_events"]=0
    if args.marketwide_volume_alignment:
        report["marketwide_volume_alignment_status"]=(
            volume_alignment["status"] if volume_alignment else "NO_VERIFIED_KR_MARKETWIDE_SOURCE")
        report["marketwide_volume_alignment_stocks"]=(
            volume_alignment["flow_stocks"] if volume_alignment else 0)
        report["marketwide_volume_alignment_matching_session"]=(
            volume_alignment["price_cache_matched"] if volume_alignment else 0)
        report["marketwide_volume_alignment_5_20_ready"]=0
        report["marketwide_volume_alignment_orders"]=0
    if args.marketwide_flow_diagnostics:
        report["marketwide_flow_diagnostics_status"]=(
            flow_diagnostics["status"] if flow_diagnostics else "NO_VERIFIED_KR_MARKETWIDE_SOURCE")
        report["marketwide_flow_diagnostics_stocks"]=(
            flow_diagnostics["observed_stocks"] if flow_diagnostics else 0)
        report["marketwide_flow_diagnostics_proxy_denominators"]=(
            flow_diagnostics["stocks_with_usable_denominator"] if flow_diagnostics else 0)
        report["marketwide_flow_diagnostics_orders"]=0
    if args.marketwide_flow_coverage:
        report["marketwide_flow_coverage_status"]=(
            flow_coverage["status"] if flow_coverage else "NO_VERIFIED_KR_MARKETWIDE_SOURCE")
        report["marketwide_flow_coverage_stocks"]=(
            flow_coverage["collected_stocks"] if flow_coverage else 0)
        report["marketwide_flow_coverage_orders"]=0
    if args.marketwide_peer_flow_research:
        report["marketwide_peer_flow_status"]=(peer_flow["status"] if peer_flow else "N/A")
        report["marketwide_peer_flow_site"]=(peer_flow["site"] if peer_flow else None)
        report["marketwide_peer_rank_revenue"]=(peer_flow["revenue_peer_ranked"] if peer_flow else 0)
        report["marketwide_peer_rank_operating"]=(peer_flow["operating_peer_ranked"] if peer_flow else 0)
        report["marketwide_peer_raw_flow"]=(peer_flow["flow_raw_observed"] if peer_flow else 0)
        report["marketwide_peer_formal_leaders"]=0
    if args.marketwide_derive_partial_factors:
        report["marketwide_partial_factor_status"]=(
            partial_input["status"] if partial_input else "NO_VERIFIED_KR_MARKETWIDE_SOURCE")
        report["marketwide_partial_factor_rows"]=(
            partial_input.get("research_candidates",0) if partial_input else 0)
        report["marketwide_partial_factor_selected"]=(
            partial_stage["research_selected"] if partial_stage else 0)
        report["marketwide_partial_factor_orders"]=0
    if refresh is not None:
        report["marketwide_refresh_status"]=refresh["status"]
        report["marketwide_observation_session"]=refresh.get("source_market_session")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print("EraLeader local operations research error: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
