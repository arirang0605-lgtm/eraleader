#!/usr/bin/env python3
"""Capture official current DART corporation crosswalk first ZIP receipt."""
from pathlib import Path
import argparse,json,os,sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.official_api_capture import credentials,KEYS
from eraleader.official_dart_corp_directory import capture_dart_corp_directory,verify_dart_corp_directory

def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument("--root",type=Path,required=True)
 p.add_argument("--credentials-file",type=Path)
 p.add_argument("--verify",type=Path)
 p.add_argument("--first-sha256")
 a=p.parse_args(argv)
 if a.verify:
  from datetime import datetime,timezone
  if not a.first_sha256:raise ValueError("SHA pin required")
  d=verify_dart_corp_directory(a.verify,a.first_sha256,decision_at=datetime.now(timezone.utc))
  result={"status":"DART_DIRECTORY_SHA_VERIFIED","matched_codes":len(d["mapping"]),
          "total_corporations":d["total_corporations"],"pit_certified":False}
 else:
  saved=(Path.home()/"Library"/"Application Support"/"EraLeader"/"api-credentials"/"official_api.env")
  selected=a.credentials_file
  if selected is None and not any(os.environ.get(k) for k in KEYS) and saved.exists():
   selected=saved
  result=capture_dart_corp_directory(a.root,creds=credentials(selected))
 print(json.dumps(result,ensure_ascii=False,sort_keys=True))
 return 0

if __name__=="__main__":
 try:raise SystemExit(main())
 except (OSError,ValueError,KeyError,TypeError):
  print("BLOCKED: official DART current directory ZIP or SHA validation",file=sys.stderr)
  raise SystemExit(2)
