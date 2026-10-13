#!/usr/bin/env python3
"""Publish an evidence-scored EraLeader development status without altering ranks.

No API calls, no market DB writes, no historical signal or score changes.
Only one new dated page/JSON and a minimal link in existing local HTML.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import stat
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from eraleader.development_progress import (
    acceptance_progress, render_html, render_markdown, AS_OF,
)


def _regular(path: Path) -> bytes:
    if (not path.is_file() or path.is_symlink() or
            any(p.is_symlink() for p in path.parents)):
        raise ValueError("Readiness site must contain unlinked ordinary HTML")
    data=path.read_bytes()
    if not 30<=len(data)<=2500000:
        raise ValueError("Invalid existing dashboard page")
    return data


def _exclusive(path: Path, data: bytes):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _replace_link(path: Path, original: bytes, new: bytes):
    """Atomic swap with current bytes checked; avoids touching market data."""
    if path.read_bytes()!=original:
        raise ValueError("Generated dashboard changed while publishing progress")
    fd,tmp=tempfile.mkstemp(prefix=".progress_link_",dir=str(path.parent))
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as dest:
            fd=-1
            dest.write(new)
            dest.flush()
            os.fsync(dest.fileno())
        os.replace(tmp,path)
    finally:
        if fd>=0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)


def publish(site: Path, document: Path) -> dict:
    site=Path(site)
    document=Path(document)
    if (not site.is_absolute() or not site.is_dir() or site.is_symlink() or
            any(parent.is_symlink() for parent in site.parents) or
            not document.is_absolute() or not document.parent.is_dir() or
            document.is_symlink() or document.exists()):
        raise ValueError("Require fresh absolute progress MD path and existing ordinary site")
    if document.parent.is_symlink() or any(p.is_symlink() for p in document.parents):
        raise ValueError("Progress document parent cannot be a symlink")
    report=acceptance_progress()
    if report["exact_percent"]!=37.5 or report["earned"]!=45:
        raise ValueError("Latest acceptance points changed without a reviewed new baseline")
    status_file=site/f"development_progress_{AS_OF.replace('-','')}.html"
    json_file=site.parent/f"development_progress_{AS_OF.replace('-','')}.json"
    if any(p.exists() or p.is_symlink() for p in (status_file,json_file)):
        raise FileExistsError("Never overwrite an earlier acceptance audit")
    old={}
    links={
        "index.html":"<p><a href='"+status_file.name+"'>전체 개발 인수 진행률 ("+
                     str(report["display_percent"])+"%, 30개 ID 증거 기준)</a></p>",
        "kr.html":"<p><a href='"+status_file.name+
                  "'>EraLeader 전체 개발 진척률 · 데이터 연결/실전 검증 기준</a></p>",
    }
    for file,link in links.items():
        path=site/file
        body=_regular(path)
        if body.count(b"</body>")!=1 or not body.startswith(b"<!doctype html>"):
            raise ValueError("Local dashboard template mismatch; no in-place update")
        if status_file.name.encode() in body:
            raise FileExistsError("Progress page already linked in local dashboard")
        old[path]=body
    created=[]
    updated=[]
    try:
        for path,payload in (
            (status_file,render_html(report).encode("utf-8")),
            (json_file,(json.dumps(report,sort_keys=True,ensure_ascii=False,
                                   indent=2,allow_nan=False)+"\n").encode("utf-8")),
            (document,render_markdown(report).encode("utf-8"))):
            _exclusive(path,payload)
            created.append(path)
        for path,body in old.items():
            link=links[path.name].encode("utf-8")
            revised=body.replace(b"</body>",link+b"</body>")
            _replace_link(path,body,revised)
            updated.append(path)
    except BaseException:
        for path in reversed(updated):
            latest=path.read_bytes()
            if status_file.name.encode() in latest:
                _replace_link(path,latest,old[path])
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {
        "status":"PROGRESS_HUMAN_REVIEWED_ACCEPTANCE_38_PERCENT_NOT_CERTIFIED",
        "earned":report["earned"],"possible":report["possible"],
        "exact_percent":report["exact_percent"],
        "display_percent":report["display_percent"],
        "all_thirty_ids_checked":True,
        "market_data_rewritten":False,"live_orders_sent":0,
        "status_page":str(status_file),
        "evidence_json":str(json_file),
        "markdown":str(document),
        "progress_sha256":report["evidence_sha256"],
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site",type=Path,required=True)
    p.add_argument("--document",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        result=publish(a.site,a.document)
    except (ValueError,FileExistsError,OSError,TypeError,KeyError) as exc:
        print("ER_ACCEPTANCE_PROGRESS_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
