#!/usr/bin/env python3
"""One-shot offline three-provider same-session availability audit publication."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"src"))

from scripts.publish_kiwoom_flow_overlay import read_flows,_swap
from eraleader.official_three_provider_session_gate import verify_live_captures,render,normalized_day
from eraleader.kiwoom_investor_flow import canonical

def publish(*,kospi:tuple[Path,str],kosdaq:tuple[Path,str],
            dart:tuple[Path,str],manifest:Path,day:str,code:str,
            site:Path,decision:datetime|None=None,
            dart_complete:tuple[Path,str]|None=None)->dict:
    site=Path(site)
    if (not site.is_absolute() or not site.is_dir() or site.is_symlink() or
            any(parent.is_symlink() for parent in site.parents)):
        raise ValueError("Private original local site directory required")
    flows=read_flows(Path(manifest).absolute())
    if code not in flows:
        raise ValueError("No original captured Kiwoom issue in manifest")
    verdict=verify_live_captures(
        krx_kospi=(Path(kospi[0]).absolute(),kospi[1]),
        krx_kosdaq=(Path(kosdaq[0]).absolute(),kosdaq[1]),
        dart_disclosures=(Path(dart[0]).absolute(),dart[1]),
        market_day=day,security_id=code,flow=flows[code],
        dart_complete=((Path(dart_complete[0]).absolute(),dart_complete[1])
                       if dart_complete is not None else None),
        decision_at=decision or datetime.now(timezone.utc))
    slug="provider_session_"+normalized_day(day)+(
        "_dart_full" if dart_complete is not None else "")
    target=site/slug
    if target.exists() or target.is_symlink():
        raise FileExistsError("Existing same-day audit is immutable")
    index=site/"index.html"
    if index.is_symlink() or not index.is_file():
        raise ValueError("Existing EraLeader index required")
    old=index.read_bytes()
    if not old.startswith(b"<!doctype html>") or old.count(b"</body>")!=1 or slug.encode() in old:
        raise ValueError("Index link not safely insertable")
    link=("<p><a href='"+slug+"/index.html'>KRX·DART·키움 "
          +normalized_day(day)+" 시점검증</a></p>").encode()
    updated=old.replace(b"</body>",link+b"</body>",1)
    temp=Path(tempfile.mkdtemp(prefix=".provider_session_",dir=site))
    os.chmod(temp,0o700)
    published=False
    try:
        for filename,data in (
            ("index.html",render(verdict).encode("utf-8")),
            ("report.json",canonical(verdict)+b"\n"),
        ):
            flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
            if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
            fd=os.open(temp/filename,flags,0o600)
            with os.fdopen(fd,"wb") as out:
                out.write(data);out.flush();os.fsync(out.fileno())
        os.rename(temp,target)
        published=True
        _swap(index,old,updated)
    except BaseException:
        if index.exists() and index.read_bytes()==updated:
            _swap(index,updated,old)
        if published:shutil.rmtree(target)
        elif temp.exists():shutil.rmtree(temp)
        raise
    return {
        "status":verdict["readiness"],
        "session":verdict["session"],
        "blockers":verdict["blockers"],
        "can_compare_same_session_research":verdict["can_compare_same_session_research"],
        "official_leaders":0,"orders":0,
        "report_sha256":verdict["content_sha256"],
        "dashboard":slug+"/index.html",
    }

def main() ->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--krx-kospi-folder",type=Path,required=True)
    parser.add_argument("--krx-kospi-sha",required=True)
    parser.add_argument("--krx-kosdaq-folder",type=Path,required=True)
    parser.add_argument("--krx-kosdaq-sha",required=True)
    parser.add_argument("--dart-folder",type=Path,required=True)
    parser.add_argument("--dart-sha",required=True)
    parser.add_argument("--dart-full-folder",type=Path)
    parser.add_argument("--dart-full-sha")
    parser.add_argument("--kiwoom-manifest",type=Path,required=True)
    parser.add_argument("--day",required=True)
    parser.add_argument("--code",required=True)
    parser.add_argument("--site",type=Path,required=True)
    args=parser.parse_args()
    try:
        if (args.dart_full_folder is None)!=(args.dart_full_sha is None):
            raise ValueError("DART full folder and independently pinned SHA required together")
        result=publish(
            kospi=(args.krx_kospi_folder,args.krx_kospi_sha),
            kosdaq=(args.krx_kosdaq_folder,args.krx_kosdaq_sha),
            dart=(args.dart_folder,args.dart_sha),
            manifest=args.kiwoom_manifest,day=args.day,
            code=args.code,site=args.site,
            dart_complete=((args.dart_full_folder,args.dart_full_sha)
                           if args.dart_full_folder is not None else None))
        print(json.dumps(result,sort_keys=True,ensure_ascii=False))
        return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print("PROVIDER_SESSION_GATE_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
