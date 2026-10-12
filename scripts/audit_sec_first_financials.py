#!/usr/bin/env python3
"""Pin-backed SEC filings+companyfacts research diagnostics, without US promotion."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.official_sec_pit_features import audit_sec_financial_asof,save_sec_research

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for kind in ("submissions","companyfacts"):
        p.add_argument("--"+kind,required=True,type=Path)
        p.add_argument("--"+kind+"-sha256",required=True)
    p.add_argument("--decision-at",default=datetime.now(timezone.utc).isoformat())
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args(argv)
    report=audit_sec_financial_asof(
        (a.submissions,a.submissions_sha256),
        (a.companyfacts,a.companyfacts_sha256),
        decision_at=a.decision_at)
    print(json.dumps(save_sec_research(report,a.out),ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError):
        print("BLOCKED: SEC CIK first receipt, filing cross-check or PIT quality",file=sys.stderr)
        raise SystemExit(2)
