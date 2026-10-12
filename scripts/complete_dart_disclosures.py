#!/usr/bin/env python3
"""Complete one DART daily listing, preserving existing first receipt SHA."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.official_api_capture import credentials
from eraleader.official_dart_daily import capture_dart_day,verify_dart_day

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--first",type=Path,help="Existing original first-page capture (absolute)")
    p.add_argument("--first-sha256",help="Independently pinned SHA of original first_receipt")
    p.add_argument("--root",required=True,type=Path,help="Existing owner-only 0700 output root")
    p.add_argument("--credentials-file",type=Path)
    p.add_argument("--max-pages",type=int,default=100)
    p.add_argument("--verify",type=Path,help="Existing complete DART folder")
    p.add_argument("--manifest-sha256",help="Independently pinned complete manifest SHA")
    a=p.parse_args(argv)
    if a.verify is not None:
        if not a.manifest_sha256:
            raise ValueError("Missing complete DART SHA pin")
        result=verify_dart_day(a.verify,a.manifest_sha256,
                               first_folder=a.first,first_sha=a.first_sha256)
        result.pop("rows",None)
    else:
        if not a.first or not a.first_sha256:
            raise ValueError("Original DART SHA pin is required")
        saved=Path.home()/"Library"/"Application Support"/"EraLeader"/"api-credentials"/"official_api.env"
        selected=a.credentials_file
        if selected is None and not any(os.environ.get(x) for x in (
                "ERALEADER_KRX_AUTH_KEY","ERALEADER_DART_API_KEY","ERALEADER_SEC_USER_AGENT")) and saved.is_file():
            selected=saved
        result=capture_dart_day(a.first,a.first_sha256,a.root,
                                 creds=credentials(selected),max_pages=a.max_pages)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError):
        print("BLOCKED: DART pagination, receipt SHA or availability contract failed",file=sys.stderr)
        raise SystemExit(2)
