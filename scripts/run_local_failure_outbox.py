#!/usr/bin/env python3
"""Record locally observable scheduler data failures. NO live alert channels."""
from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys


def main(argv=None) -> int:
    parser=ArgumentParser(description="EraLeader local-only data failure dry-run outbox")
    parser.add_argument("--project",type=Path,required=True,
                        help="Authorized EraLeader project (write output/ only)")
    args=parser.parse_args(argv)
    project=args.project.resolve(strict=True)
    # The executable's verified installation supplies code; project supplies
    # only its local research checkpoints. Never execute code from the project.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.local_failure_outbox import run_local_failure_outbox
    summary=run_local_failure_outbox(project)
    print(json.dumps(summary,sort_keys=True,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,KeyError) as exc:
        print(f"EraLeader local dry-run alert error: {exc}",file=sys.stderr)
        raise SystemExit(2) from exc
