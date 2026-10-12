#!/usr/bin/env python3
"""Opt-in full KRX two-market + DART daily retrieval and WATCH research."""
from pathlib import Path
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_api_capture import KEYS,credentials
from eraleader.official_kr_daily_pipeline import capture_and_publish_kr_day

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--day",required=True,help="Exchange day YYYY-MM-DD")
    p.add_argument("--captures",type=Path,default=ROOT/"output"/"official_api_capture")
    p.add_argument("--out",type=Path,required=True,
                   help="NEW private research output directory, not existing")
    p.add_argument("--legacy-root",type=Path,
                   default=Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine"))
    p.add_argument("--credentials-file",type=Path)
    p.add_argument("--dart-directory",type=Path)
    p.add_argument("--dart-directory-sha256")
    p.add_argument("--top",type=int,default=20)
    p.add_argument("--days",type=int,default=550)
    a=p.parse_args(argv)
    saved=(Path.home()/"Library"/"Application Support"/"EraLeader"/
           "api-credentials"/"official_api.env")
    selected=a.credentials_file
    if selected is None and not any(os.environ.get(key) for key in KEYS) and saved.is_file():
        selected=saved
    if (a.dart_directory is None)!=(a.dart_directory_sha256 is None):
        raise ValueError("DART current directory must include first SHA pin")
    result=capture_and_publish_kr_day(
        trading_day=a.day,capture_root=a.captures.absolute(),
        research_out=a.out.absolute(),creds=credentials(selected),
        top=a.top,days=a.days,legacy_root=a.legacy_root,
        dart_directory=(a.dart_directory,a.dart_directory_sha256)
            if a.dart_directory is not None else None)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError,RuntimeError):
        print("BLOCKED: official KR daily source, private SHA or PIT research preflight",
              file=sys.stderr)
        raise SystemExit(2)
