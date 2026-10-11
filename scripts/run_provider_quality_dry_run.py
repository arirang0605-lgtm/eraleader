#!/usr/bin/env python3
"""Standalone local-only 6_5 quality weakening/SHA integrity observer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="Offline DRY-RUN provider quality monitor")
    parser.add_argument("--project",required=True,type=Path)
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.provider_quality_watchdog import run_provider_quality_watchdog
    result=run_provider_quality_watchdog(project)
    if result["status"]!="LOCAL_PROVIDER_QUALITY_DRY_RUN_VERIFIED_BACKUP":
        raise RuntimeError("Quality watchdog skipped/unverified")
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError) as exc:
        print(f"EraLeader quality dry-run error: {exc}",file=sys.stderr)
        raise SystemExit(2) from exc
