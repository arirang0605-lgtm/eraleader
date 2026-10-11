#!/usr/bin/env python3
"""Offline KR/US legal issuer / security-class declared-source audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="Offline issuer and share-class PIT consistency; NEVER official certification")
    parser.add_argument("--staged-manifest",type=Path,required=True)
    parser.add_argument("--issuer-lineage",type=Path,required=True)
    parser.add_argument("--decision-at",required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.issuer_class_bridge import audit_staged_issuer_class
    from eraleader.watch_operating_reports import _atomic_text

    result=audit_staged_issuer_class(args.staged_manifest,args.issuer_lineage,
                                     decision_at=args.decision_at)
    if args.out.is_symlink() or args.out.parent.is_symlink():
        raise ValueError("Unsafe linked derived issuer class report directory")
    dest=args.out/"issuer_class_corroboration_research.json"
    _atomic_text(dest,json.dumps(result,sort_keys=True,ensure_ascii=False,
                                 indent=2,allow_nan=False)+"\n")
    print(json.dumps({
        "status":result["status"],
        "market":result["market"],
        "matched_security_class_count":result["matched_security_class_count"],
        "matched_legal_entity_count":result["matched_legal_entity_count"],
        "blocker_counts":result["blocker_counts"],
        "historical_universe_pit_certified":False,
        "official_leader_promotions":0,
    },sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,TypeError,KeyError) as exc:
        print("EraLeader issuer class evidence ERROR: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
