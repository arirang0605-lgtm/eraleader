#!/usr/bin/env python3
"""Publish an independently verified CURRENT OpenDART division peer panel.

Only a new peer evidence page + JSON and links. Original KRX/DART financial
first receipts, PRICE WATCH rankings, order logic and reports stay untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import stat
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from eraleader.official_dart_multi_company import _all_pinned
from eraleader.official_industry_peer_screen import (
    build_industry_peers, render_industry_peers,
)


def _first(filepath:Path) -> dict:
    if not filepath.is_absolute() or filepath.is_symlink() or not filepath.is_file():
        raise ValueError("Industry research requires original regular evidence file")
    value=json.loads(filepath.read_bytes())
    if type(value) is not dict:
        raise ValueError("Industry source original must be a JSON object")
    return value


def _new(filepath:Path, data:bytes) -> None:
    fd=os.open(filepath,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as output:
        output.write(data);output.flush();os.fsync(output.fileno())


def _change_link(path:Path, before:bytes, after:bytes) -> None:
    if path.read_bytes()!=before:
        raise ValueError("Old official research HTML changed during industry sidecar write")
    fd,temp=tempfile.mkstemp(prefix=".industry_link_",dir=path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as f:
            fd=-1
            f.write(after);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if fd>=0:os.close(fd)
        if os.path.exists(temp):os.unlink(temp)


def publish(*, candidate_file:Path, industry_manifest:Path,
            official_evidence:Path, private_root:Path,
            existing_site:Path) -> dict:
    basic=_first(candidate_file)
    cohort=_first(industry_manifest)
    original=_first(official_evidence)
    if (original.get("schema")!="eraleader.official_api_pit_research_bridge.v1"
            or original.get("historic_universe_pit_verified") is not False
            or original.get("official_leaders")!=0):
        raise ValueError("Industry peers require actual official unpromoted receipt evidence")
    root=Path(private_root)
    if not root.is_dir() or root.is_symlink() or not root.is_absolute():
        raise ValueError("Source first receipt originals are not in a private absolute root")
    first=_all_pinned(root)
    pin=original["dart_current_directory"]["first_receipt_sha256"]
    if pin not in first:
        raise ValueError("DART current issuer directory original SHA missing")
    site=Path(existing_site)
    if (not site.is_dir() or not site.is_absolute() or site.is_symlink() or
            any(parent.is_symlink() for parent in site.parents)):
        raise ValueError("Existing local research page root must not be linked")
    report=build_industry_peers(basic,cohort,originals=first,
                                directory=(first[pin],pin))
    page=site/"industry_peers_kr.html"
    data=site.parent/"industry_peers_kr.json"
    if page.exists() or data.exists() or page.is_symlink() or data.is_symlink():
        raise FileExistsError("Industry peer panel already published; never overwrite")
    links={
        "index.html":("<p><a href='industry_peers_kr.html'>DART 업종별 동종기업 실적 비교</a></p>",b"</body>"),
        "kr.html":("<p><a href='industry_peers_kr.html'>DART 산업 대분류 실적·주가 비교</a></p>",b"</main>"),
        "basic_candidates_kr.html":(
            "<p><a href='industry_peers_kr.html'>KSIC 업종별 동종기업 비교 결과</a></p>",b"</main>"),
    }
    original_pages={}
    replacements={}
    for name,(anchor,target) in links.items():
        path=site/name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Cannot modify a linked/nonexistent earlier research page")
        before=path.read_bytes()
        if (before.count(target)!=1 or
                b"industry_peers_kr.html" in before or
                not before.startswith(b"<!doctype html>")):
            raise ValueError("Existing research page not available for industry link")
        original_pages[path]=before
        replacements[path]=before.replace(target,anchor.encode("utf-8")+target,1)
    created=[]
    changed=[]
    try:
        for path,payload in (
            (page,render_industry_peers(report).encode("utf-8")),
            (data,(json.dumps(report,ensure_ascii=False,sort_keys=True,
                              indent=2,allow_nan=False)+"\n").encode("utf-8")),
        ):
            _new(path,payload)
            created.append(path)
        for path,new in replacements.items():
            _change_link(path,original_pages[path],new)
            changed.append(path)
    except BaseException:
        for path in reversed(changed):
            current=path.read_bytes()
            if b"industry_peers_kr.html" in current:
                _change_link(path,current,original_pages[path])
        for path in created:path.unlink(missing_ok=True)
        raise
    return {
        "status":"KR_BASIC_INDUSTRY_DIVISION_PEER_RESEARCH_PUBLISHED",
        "companies":report["selected_companies"],
        "exact_industry_codes":report["verified_current_industries"],
        "industry_divisions":report["verified_industry_divisions"],
        "multi_company_divisions":report["selected_multi_company_peer_groups"],
        "companies_with_division_peer":report["companies_with_real_peer"],
        "market_session":report["market_session"],
        "historic_industry_pit_certified":False,
        "real_investment_leader_ranking":False,
        "real_messages_sent":0,
        "output_page":page.name,
        "provenance_sha256":report["content_sha256"],
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json",required=True,type=Path)
    parser.add_argument("--industry-manifest",required=True,type=Path)
    parser.add_argument("--official-evidence",required=True,type=Path)
    parser.add_argument("--private-root",required=True,type=Path)
    parser.add_argument("--site",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        result=publish(candidate_file=args.candidate_json,
                       industry_manifest=args.industry_manifest,
                       official_evidence=args.official_evidence,
                       private_root=args.private_root,
                       existing_site=args.site)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print("DART_INDUSTRY_PEERS_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
