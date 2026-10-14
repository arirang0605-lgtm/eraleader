#!/usr/bin/env python3
"""Read-only KR cached volume overlap report for previously captured flow."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.marketwide_volume_alignment import publish_volume_alignment
from eraleader.data import LEGACY_DEFAULT


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    p.add_argument("--marketwide-report",required=True,type=Path)
    p.add_argument("--legacy-root",default=LEGACY_DEFAULT,type=Path)
    args=p.parse_args(argv)
    try:
        summary=publish_volume_alignment(
            marketwide=args.marketwide_report,project=args.project,
            legacy_root=args.legacy_root)
    except (OSError,ValueError,TypeError,KeyError,OverflowError):
        print("KR_VOLUME_ALIGNMENT_BLOCKED",file=sys.stderr)
        return 2
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
