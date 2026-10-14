#!/usr/bin/env python3
"""Append signed KRX PRICE WATCH observations to research-only Stage4 history.

No PIT-certified leader promotion, no artificial delisting on leaving TOP20.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_watch_state_bridge import record_official_watch_history
from eraleader.official_company_explorer import canonical


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--marketwide-report",type=Path,required=True)
    p.add_argument("--ledger",type=Path,required=True,
                   help="Existing or new owner-only output/official_price_watch_state_history.sqlite")
    p.add_argument("--out",type=Path,required=True,
                   help="New private immutable research result JSON")
    args=p.parse_args(argv)
    try:
        output_root=ROOT/"output"
        if (not args.ledger.is_absolute() or
                not args.ledger.is_relative_to(output_root) or
                not args.out.is_absolute() or
                not args.out.is_relative_to(output_root) or
                args.out.exists() or args.out.is_symlink() or
                not args.out.parent.is_dir() or
                any(x.is_symlink() for x in args.out.parents) or
                stat.S_IMODE(args.out.parent.stat().st_mode) & 0o022):
            raise ValueError("Only existing owner-private EraLeader output paths allowed")
        result=record_official_watch_history(args.marketwide_report,args.ledger)
        fd=os.open(args.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(canonical(result)+b"\n")
            f.flush()
            os.fsync(f.fileno())
        print(json.dumps({
            "status":"PRICE_WATCH_STATE_HISTORY_RECORDED_RESEARCH_ONLY",
            "market_session":result["market_session"],
            "watch":result["recorded_watch_count"],
            "selected":0,
            "orders_enabled":False,
        },sort_keys=True))
        return 0
    except (OSError,TypeError,KeyError,ValueError) as err:
        print("OFFICIAL_PRICE_WATCH_HISTORY_BLOCKED: "+type(err).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
