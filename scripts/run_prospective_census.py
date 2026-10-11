#!/usr/bin/env python3
"""EraLeader 5_5 first-write Top-K cohort census (offline, no future outcome import)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Local prospective Top-K cohort census")
    subs=parser.add_subparsers(dest="command",required=True)
    reg=subs.add_parser("register",help="First-write a prospective, pre-result census")
    reg.add_argument("--spec",type=Path,required=True)
    reg.add_argument("--registry-dir",type=Path,required=True)
    reg.add_argument("--name",required=True,help="Unique census_*.json O_EXCL basename")
    reg.add_argument("--receipt-index",action="store_true",
                     help="Strict local SHA-chain first-write receipts (opt-in)")
    reg.add_argument("--native-evidence-config",type=Path,
                     help="Require original native WATCH+score+formula provenance before first census write")
    audit=subs.add_parser("audit",help="Audit ALL on-disk census registries, no subsets")
    audit.add_argument("--registry-dir",type=Path,required=True)
    audit.add_argument("--evaluated-at",required=True)
    audit.add_argument("--receipt-index",action="store_true",
                       help="Require complete indexed first-write receipts")
    audit.add_argument("--native-evidence-config",type=Path,
                       help="Recheck every original WATCH score and feature formula of indexed cohorts")
    audit.add_argument("--out",type=Path,required=True,
                       help="Derived directory for sanitized prospective_census_research.json")
    audit.add_argument("--due-followups",action="store_true",
                       help="Opt-in all-cohort maturity/missing-outcome due queue; strict indexed receipt required")
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.prospective_census import register_census, audit_all_registered_censuses
    from eraleader.prospective_census_seal import _index_path
    index = _index_path(args.registry_dir)
    if not args.receipt_index and (index.exists() or index.is_symlink()):
        raise ValueError("An indexed census requires --receipt-index; refusing unsafe downgrade")
    from eraleader.native_census_gate import native_gate_marker
    native_required = native_gate_marker(args.registry_dir)
    if (native_required.exists() or native_required.is_symlink()) and args.native_evidence_config is None:
        raise ValueError("This prospective census requires --native-evidence-config; unsafe downgrade")
    if args.native_evidence_config is not None and not args.receipt_index:
        raise ValueError("Native provenance requires the first-write --receipt-index")
    if getattr(args,"due_followups",False) and not args.receipt_index:
        raise ValueError("Prospective due follow-ups require --receipt-index")
    if args.receipt_index:
        from eraleader.prospective_census_seal import indexed_register_census, indexed_audit_censuses
    if args.native_evidence_config is not None:
        from eraleader.native_census_gate import register_native_census, audit_native_census
    if args.command=="register":
        result=(register_native_census(args.spec,args.registry_dir,args.name,
                                      native_config=args.native_evidence_config)
                if args.native_evidence_config is not None else
                indexed_register_census(args.spec,args.registry_dir,args.name)
                if args.receipt_index else
                register_census(args.spec,args.registry_dir,args.name))
    else:
        result=(audit_native_census(args.registry_dir,
                                   native_config=args.native_evidence_config,
                                   evaluated_at=args.evaluated_at)
                if args.native_evidence_config is not None else
                indexed_audit_censuses(args.registry_dir,evaluated_at=args.evaluated_at)
                if args.receipt_index else
                audit_all_registered_censuses(args.registry_dir,evaluated_at=args.evaluated_at))
        due=None
        if args.due_followups:
            from eraleader.prospective_due_followups import audit_prospective_due_followups
            due=audit_prospective_due_followups(
                args.registry_dir,evaluated_at=args.evaluated_at,
                native_config=args.native_evidence_config)
        dest=args.out/"prospective_census_research.json"
        from eraleader.watch_operating_reports import _atomic_text
        if args.out.is_symlink() or args.out.parent.is_symlink():
            raise ValueError("Unsafe prospective census derived output directory")
        if due is not None:
            from eraleader.prospective_due_followups import publish_due_followups
            # Validate page and destination before altering the existing
            # complete-cohort summary or emitting any locally "healthy" claim.
            from eraleader.prospective_due_followups import render_due_followups
            render_due_followups(due)
        _atomic_text(dest,json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
        if due is not None:
            publish_due_followups(due,args.out)
            result={"census_audit":result,"due_followups":due}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
        print("EraLeader prospective census error: "+str(error),file=sys.stderr)
        raise SystemExit(2) from error
