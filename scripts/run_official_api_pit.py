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
    p.add_argument("--dart-financial", action="append",nargs=2,
                   metavar=("PRIVATE_FIRST_REPORT","FIRST_RECEIPT_SHA256"),
                   default=[],help="Optional paired receipt-pinned annual CFS report")
    p.add_argument("--dart-directory", type=Path,
                   help="Read-only current official DART corpCode first ZIP folder")
    p.add_argument("--dart-directory-sha256",
                   help="First SHA of DART directory receipt")
    p.add_argument("--dart-complete", type=Path,
                   help="Optional verified complete DART daily evidence folder")
    p.add_argument("--dart-manifest-sha256",
                   help="Separate SHA PIN of DART full daily manifest")
    p.add_argument("--dart-original-first", type=Path,
                   help="Original DART first page folder")
    p.add_argument("--dart-original-first-sha256",
                   help="Original DART first-receipt SHA pin")
    p.add_argument("--pit-ledger", type=Path,
                   help="Optional existing read-only offline.sqlite; research only")
    p.add_argument("--vintage-ledger", type=Path,
                   help="Optional existing read-only local DART CFS first-seen SQLite research registry")
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        pins=(a.dart_complete,a.dart_manifest_sha256,
              a.dart_original_first,a.dart_original_first_sha256)
        if any(item is not None for item in pins) and not all(item is not None for item in pins):
            raise ValueError("All four full DART evidence and original PIN inputs required")
        if (a.dart_directory is None)!=(a.dart_directory_sha256 is None):
            raise ValueError("DART current directory requires both capture and first SHA")
        snap = build_official_price_snapshot(
            kospi=(a.kospi, a.kospi_sha256),
            kosdaq=(a.kosdaq, a.kosdaq_sha256),
            decision_at=a.decision_at, as_of=a.as_of,
            legacy_root=a.legacy_root, days=a.days, top=a.top,
            auxiliary=tuple((src, Path(folder), pin) for src, folder, pin in a.aux),
            dart_complete=tuple(pins) if all(x is not None for x in pins) else None,
            dart_directory=(a.dart_directory,a.dart_directory_sha256)
                if a.dart_directory is not None else None,
            dart_financial_receipts=tuple((Path(folder),pin) for folder,pin in a.dart_financial))
        result = run_official_research(snap, a.out, pit_ledger=a.pit_ledger,
                                       vintage_ledger=a.vintage_ledger)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # No untrusted raw JSON or URL in terminal output.
        print("BLOCKED: official first receipt, price schema or PIT gate failed ("+
              type(exc).__name__ + ")", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
