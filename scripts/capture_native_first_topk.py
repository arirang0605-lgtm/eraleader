#!/usr/bin/env python3
"""Predeclared first native WATCH+computed Top-K+strict census in one local run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="First-write native prospective Top-K; research only, no future labels")
    parser.add_argument("--plan",type=Path,required=True,
                        help="Predeclared plan with KR/US/model/K/rule SHA and WATCH+score source paths")
    parser.add_argument("--capture-root",type=Path,required=True,
                        help="Local new first-write evidence root; never retroactively register")
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
    from eraleader.native_first_capture import capture_first_native_topk
    result=capture_first_native_topk(args.plan,args.capture_root)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
        print("EraLeader native first capture: "+str(exc),file=sys.stderr)
        raise SystemExit(2) from exc
