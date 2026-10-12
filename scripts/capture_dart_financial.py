#!/usr/bin/env python3
"""Opt-in verified DART annual/quarterly CFS/OFS capture, no live promotion."""
from pathlib import Path
import argparse,json,os,sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.official_api_capture import credentials,KEYS
from eraleader.official_dart_financials import capture_dart_financial

def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument("--root",required=True,type=Path)
 p.add_argument("--stock-code",required=True)
 p.add_argument("--directory",required=True,type=Path)
 p.add_argument("--directory-sha256",required=True)
 p.add_argument("--year",required=True,type=int)
 p.add_argument("--report",default="11011")
 p.add_argument("--statement",default="CFS",choices=["CFS","OFS"])
 p.add_argument("--credentials-file",type=Path)
 a=p.parse_args(argv)
 saved=(Path.home()/"Library"/"Application Support"/"EraLeader"/"api-credentials"/"official_api.env")
 selected=a.credentials_file
 if selected is None and not any(os.environ.get(k) for k in KEYS) and saved.exists():
  selected=saved
 result=capture_dart_financial(a.root,stock_code=a.stock_code,
            directory=(a.directory,a.directory_sha256),year=a.year,
            report=a.report,statement=a.statement,
            creds=credentials(selected))
 print(json.dumps(result,ensure_ascii=False,sort_keys=True))
 return 0

if __name__=="__main__":
 try:raise SystemExit(main())
 except (OSError,ValueError,KeyError,TypeError):
  print("BLOCKED: DART financial company, source SHA, report or first receipt",file=sys.stderr)
  raise SystemExit(2)
