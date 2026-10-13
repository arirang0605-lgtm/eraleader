#!/usr/bin/env python3
"""Publish Kiwoom demo observations as a separate same-day research site.

Does not alter existing price, earnings, sector or leader scores. A small
link in the existing index is the only original-page change, opt-in.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import stat
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"src"))
from eraleader.kiwoom_investor_flow import canonical
from eraleader.kiwoom_live_research_panel import (
    make_panel,render_panel,clean_session
)
from scripts.publish_kiwoom_flow_overlay import read, read_flows, _swap

def _write_new(path:Path, data:bytes) -> None:
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def publish(*,candidates:Path,industries:Path,flow_manifest:Path,
            site:Path,clock:datetime|None=None,link_index:bool=True)->dict:
    site=Path(site)
    if (not site.is_absolute() or not site.is_dir() or
            site.is_symlink() or any(path.is_symlink() for path in site.parents)):
        raise ValueError("Existing nonlinked site required")
    raw_manifest=read(flow_manifest)
    digest=raw_manifest.pop("content_sha256",None)
    if (digest!=sha256(canonical(raw_manifest)).hexdigest() or
            raw_manifest.get("schema")!="eraleader.kiwoom_selected_flow_capture_manifest.v1"
            or raw_manifest.get("environment_mode")!="demo"
            or raw_manifest.get("unit")!="shares"
            or raw_manifest.get("trading_enabled") is not False
            or raw_manifest.get("historic_market_pit_certified") is not False):
        raise ValueError("Untrusted demo capture manifest")
    captured_session=clean_session(raw_manifest.get("requested_day"))
    flows=read_flows(flow_manifest)
    if not flows or any(
            f.get("requested_day")!=captured_session or
            f.get("environment_mode")!="demo" or
            f.get("security_id")!=code
            for code,f in flows.items()):
        raise ValueError("Flow captures disagree with pinned session/mode")
    panel=make_panel(read(candidates),read(industries),
                     flows=flows,decision_at=clock)
    period={row["observed_flow_session"] for row in panel["observations"]}
    if period!={captured_session}:
        raise ValueError("Different market-day flows cannot share one snapshot")
    folder="kiwoom_demo_"+captured_session
    final=site/folder
    if final.exists() or final.is_symlink():
        raise FileExistsError("Immutable live research panel already published")
    index=site/"index.html"
    old=None
    updated=None
    if link_index:
        if index.is_symlink() or not index.is_file():
            raise ValueError("Existing main index required")
        old=index.read_bytes()
        marker=b"</body>"
        if (old.count(marker)!=1 or
                folder.encode() in old or
                not old.startswith(b"<!doctype html>")):
            raise ValueError("Main index cannot be safely linked")
        anchor=(
            "<p><a href='"+folder+"/index.html'>"
            "키움 모의 수급 "+captured_session+" (별도 날짜 연구)</a></p>"
        ).encode("utf-8")
        updated=old.replace(marker,anchor+marker,1)
    stage=Path(tempfile.mkdtemp(prefix=".kiwoom_live_",dir=site))
    os.chmod(stage,0o700)
    created=False
    linked=False
    try:
        _write_new(stage/"index.html",render_panel(panel).encode("utf-8"))
        _write_new(stage/"report.json",canonical(panel)+b"\n")
        os.rename(stage,final)
        created=True
        if link_index:
            _swap(index,old,updated)
            linked=True
    except BaseException:
        if linked and index.read_bytes()==updated:
            _swap(index,updated,old)
        if created and final.is_dir():
            shutil.rmtree(final)
        elif stage.is_dir():
            shutil.rmtree(stage)
        raise
    return {
        "status":"DEMO_INVESTOR_FLOW_RESEARCH_PUBLISHED",
        "market_day":captured_session,
        "baseline_day":panel["baseline_market_session"],
        "sessions_aligned":panel["all_flow_same_session_as_baseline"],
        "observed":panel["live_observed_security_count"],
        "path":folder+"/index.html",
        "content_sha256":panel["content_sha256"],
        "scores_changed":False,"official_leaders":0,"orders":0,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-json",type=Path,required=True)
    p.add_argument("--industry-json",type=Path,required=True)
    p.add_argument("--kiwoom-manifest",type=Path,required=True)
    p.add_argument("--site",type=Path,required=True)
    p.add_argument("--no-index-link",action="store_true")
    options=p.parse_args(argv)
    try:
        outcome=publish(
            candidates=options.candidate_json,
            industries=options.industry_json,
            flow_manifest=options.kiwoom_manifest,
            site=options.site,link_index=not options.no_index_link)
        print(json.dumps(outcome,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print("DEMO_FLOW_PANEL_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
