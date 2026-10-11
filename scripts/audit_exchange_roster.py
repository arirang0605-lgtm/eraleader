#!/usr/bin/env python3
"""Research-only, third declared source exchange-class roster reconciliation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Offline whole exchange class coverage check")
    parser.add_argument("--staged-manifest",type=Path,required=True)
    parser.add_argument("--issuer-lineage",type=Path,required=True)
    parser.add_argument("--exchange-roster",type=Path,required=True)
    parser.add_argument("--decision-at",required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.exchange_roster_crosscheck import audit_declared_exchange_roster
    from eraleader.watch_operating_reports import _atomic_text
    result=audit_declared_exchange_roster(
        args.staged_manifest,args.issuer_lineage,args.exchange_roster,
        decision_at=args.decision_at)
    out=args.out.absolute()
    if out.is_symlink() or out.parent.is_symlink():
        raise ValueError("Unsafe exchange-roster report destination")
    _atomic_text(out/"exchange_roster_coverage_research.json",
                 json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as exc:
        print(f"EraLeader exchange-roster audit error: {exc}",file=sys.stderr)
        raise SystemExit(2) from exc
