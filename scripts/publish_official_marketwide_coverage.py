#!/usr/bin/env python3
"""Publish observed whole-KRX coverage using already-pinned KRX/DART receipts."""
from __future__ import annotations
from pathlib import Path
import argparse
from datetime import datetime
import json
import os
import stat
from zoneinfo import ZoneInfo
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_marketwide_coverage import (
    build_marketwide_coverage, publish_marketwide_coverage,
    refresh_saved_marketwide_flow,extend_saved_marketwide_factors,
)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument("--cohort",type=Path)
    source.add_argument("--reuse-marketwide-report",type=Path,
                        help="Republish an already SHA-verified marketwide report into fresh EraLeader output")
    source.add_argument("--extend-marketwide-report",type=Path,
                        help="Read-only fast append of original-verified financial/industry cohorts")
    source.add_argument("--verified-marketwide-report",type=Path,
                        help="Reuse existing SHA-verified KR marketwide report to join new Kiwoom flow")
    p.add_argument("--capture-root",type=Path)
    p.add_argument("--official-evidence",type=Path,
                   help="Official same-session KRX+DART first receipt summary for fast expansion")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--p2-readiness-out",type=Path,
                   help="New EraLeader research-only P2 5-factor coverage report JSON+HTML directory")
    p.add_argument("--watch-state-ledger",type=Path,
                   help="Optional research-only Stage4 PRICE WATCH SQLite inside EraLeader output")
    p.add_argument("--strategy-outbox-dir",type=Path,
                   help="Optional existing EraLeader output-only immutable research handoff outbox")
    p.add_argument("--extra-cfs-manifest",type=Path,action="append",default=[],
                   help="Additional verified existing bounded CFS batch (FY consecutive)")
    p.add_argument("--extra-industry-manifest",type=Path,action="append",default=[],
                   help="Additional verified DART industry first-receipt batch")
    p.add_argument("--full-price-lookback",action="store_true",
                   help="Opt in to existing uncertified local marcap price-history percentiles")
    p.add_argument("--previous-price-watch",type=Path,
                   help="Older pinned official KR price WATCH for observed changes")
    p.add_argument("--kiwoom-flow-folder",type=Path,
                   help="Existing read-only Kiwoom selected-flow capture; exact KRX session only")
    a=p.parse_args(argv)
    if a.strategy_outbox_dir is not None:
        outbox=a.strategy_outbox_dir
        owned_output=ROOT/"output"
        if (not outbox.is_absolute() or not outbox.is_relative_to(owned_output) or
                not outbox.is_dir() or outbox.is_symlink() or
                any(parent.is_symlink() for parent in outbox.parents) or
                outbox.stat().st_uid!=os.geteuid() or
                stat.S_IMODE(outbox.stat().st_mode)!=0o700):
            p.error("Strategy research outbox must be an existing private EraLeader output subdirectory")
    if a.reuse_marketwide_report is not None:
        if (a.kiwoom_flow_folder is not None or a.capture_root is not None or
                a.official_evidence is not None or a.extra_cfs_manifest or
                a.extra_industry_manifest or a.full_price_lookback or
                a.previous_price_watch is not None):
            p.error("Reuse mode accepts an existing verified marketwide report and output options only")
        from eraleader.official_p2_readiness import _load
        result=_load(a.reuse_marketwide_report)
    elif a.verified_marketwide_report is not None:
        if (a.kiwoom_flow_folder is None or a.capture_root is not None or
                a.extra_cfs_manifest or a.extra_industry_manifest or
                a.full_price_lookback or a.previous_price_watch is not None or
                a.official_evidence is not None):
            p.error("Saved report mode only accepts --kiwoom-flow-folder and --out")
        result=refresh_saved_marketwide_flow(
            a.verified_marketwide_report,a.kiwoom_flow_folder)
    elif a.extend_marketwide_report is not None:
        if (a.capture_root is None or a.official_evidence is None or
                not a.extra_cfs_manifest or a.full_price_lookback or
                a.previous_price_watch is not None or
                a.kiwoom_flow_folder is not None):
            p.error("Fast marketwide extension requires --capture-root, --official-evidence, and extra CFS manifests")
        result=extend_saved_marketwide_factors(
            a.extend_marketwide_report,a.official_evidence,a.capture_root,
            financial_manifests=tuple(a.extra_cfs_manifest),
            industry_manifests=tuple(a.extra_industry_manifest))
    else:
        if a.capture_root is None:
            p.error("Official KRX/DART capture-root is required")
        result=build_marketwide_coverage(a.cohort,a.capture_root,
                                          extra_cfs_manifests=tuple(a.extra_cfs_manifest),
                                          extra_industry_manifests=tuple(a.extra_industry_manifest),
                                          full_price_lookback=a.full_price_lookback,
                                          kiwoom_flow_folder=a.kiwoom_flow_folder,
                                          previous_watch_file=a.previous_price_watch)
    paths=publish_marketwide_coverage(result,a.out)
    watch_state=None
    if a.watch_state_ledger is not None:
        from eraleader.official_watch_state_bridge import (
            LEDGER_NAME,record_official_watch_history,
        )
        path=a.watch_state_ledger
        if (not path.is_absolute() or not path.is_relative_to(ROOT/"output") or
                path.name!=LEDGER_NAME):
            p.error("Only research-only EraLeader WATCH SQLite supported")
        watch_state=record_official_watch_history(paths[0],path)
    p2=None
    if a.p2_readiness_out is not None:
        from eraleader.official_p2_readiness import (
            build_p2_readiness,publish_p2_readiness,
        )
        destination=a.p2_readiness_out
        if (not destination.is_absolute() or
                not destination.is_relative_to(ROOT/"output") or
                destination.exists() or
                not destination.parent.is_dir() or destination.parent.is_symlink()):
            p.error("New EraLeader-owned P2 readiness output directory required")
        p2_report=build_p2_readiness(paths[0],state_history=a.watch_state_ledger)
        p2_files=publish_p2_readiness(p2_report,destination)
        p2={"research_two_factor":p2_report["two_factor_research_evaluable"],
            "five_factor_counts":p2_report["observed_factor_counts"],
            "official_selected":0,"files":[str(f) for f in p2_files]}
    handoff=None
    if a.strategy_outbox_dir is not None:
        from eraleader.strategy_handoff import (
            marketwide_research_handoff,publish_versioned_handoff,
        )
        research=marketwide_research_handoff(
            paths[0],request_day=datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
        handoff=publish_versioned_handoff(research,a.strategy_outbox_dir)
    print(json.dumps({"status":"RESEARCH_COVERAGE_PUBLISHED",
          "watch_state":None if watch_state is None else {
              "watch":watch_state["recorded_watch_count"],
              "selected":watch_state["leader_selection_count"],
              "orders_enabled":watch_state["orders_enabled"]},
          "handoff":handoff,
          "p2_readiness":p2,
          "observed":result["official_krx_observed"],
          "finance":result["financial_factors_observed"],
          "industry":result["industry_factors_observed"],
          "formal_leaders":0,"files":[str(x) for x in paths]},
          ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
