#!/usr/bin/env python3
"""6_5: explicitly invoked, never-delivered prospective due-evidence warnings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description="Local-only prospective due DRY-RUN")
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--registry-dir",type=Path,required=True)
    parser.add_argument("--native-evidence-config",type=Path)
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    sys.path.insert(0,str(project/"src"))
    from eraleader.prospective_due_alerts import run_prospective_due_alerts
    result=run_prospective_due_alerts(
        project,registry_dir=args.registry_dir,
        native_config=args.native_evidence_config)
    if result.get("status")!="LOCAL_PROSPECTIVE_DUE_DRY_RUN_VERIFIED_BACKUP":
        raise RuntimeError("Prospective due monitor skipped/unverified")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print(f"EraLeader prospective due alert error: {exc}",file=sys.stderr)
        raise SystemExit(2) from exc
