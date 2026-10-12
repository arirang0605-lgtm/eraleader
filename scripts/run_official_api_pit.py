#!/usr/bin/env python3
"""KRX/DART/SEC already-received official evidence into research WATCH/reports.

Does not call API endpoints or read credentials; SHA pins must be supplied.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eraleader.official_api_pit_bridge import build_official_price_snapshot, run_official_research


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kospi", required=True, type=Path)
    p.add_argument("--kospi-sha256", required=True)
    p.add_argument("--kosdaq", required=True, type=Path)
    p.add_argument("--kosdaq-sha256", required=True)
    p.add_argument("--aux", action="append", nargs=3,
                   metavar=("SOURCE", "PRIVATE_CAPTURE_DIR", "FIRST_RECEIPT_SHA256"),
                   default=[])
    p.add_argument("--decision-at", required=True,
                   help="Real timezone-aware decision time after first local receipt")
    p.add_argument("--as-of", required=True, help="Decision date, not backdated market signal")
    p.add_argument("--legacy-root", type=Path,
                   default=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"))
    p.add_argument("--days", type=int, default=550)
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--pit-ledger", type=Path,
                   help="Optional existing read-only offline.sqlite; research only")
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        snap = build_official_price_snapshot(
            kospi=(a.kospi, a.kospi_sha256),
            kosdaq=(a.kosdaq, a.kosdaq_sha256),
            decision_at=a.decision_at, as_of=a.as_of,
            legacy_root=a.legacy_root, days=a.days, top=a.top,
            auxiliary=tuple((src, Path(folder), pin) for src, folder, pin in a.aux))
        result = run_official_research(snap, a.out, pit_ledger=a.pit_ledger)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # No untrusted raw JSON or URL in terminal output.
        print("BLOCKED: official first receipt, price schema or PIT gate failed ("+
              type(exc).__name__ + ")", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
