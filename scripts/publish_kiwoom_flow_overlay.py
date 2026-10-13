#!/usr/bin/env python3
"""Attach a verified read-only institutional/foreign overlay to existing KR research.

No provider credentials needed to show honest N/A; never reorder earlier ranks.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from eraleader.kiwoom_investor_flow import canonical
from eraleader.official_kiwoom_flow_overlay import build_overlay, render_overlay


def read(path: Path) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("Original source file must be a regular absolute file")
    value = json.loads(path.read_bytes())
    if type(value) is not dict:
        raise ValueError("Expected evidence object")
    return value


def _new(path: Path, blob: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(blob);file.flush();os.fsync(file.fileno())


def _swap(path: Path, old: bytes, new: bytes) -> None:
    if path.read_bytes() != old:
        raise ValueError("Previous research page changed")
    fd, name = tempfile.mkstemp(prefix=".kiwoom_link_", dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "wb") as file:
            fd = -1
            file.write(new);file.flush();os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if fd != -1:os.close(fd)
        if os.path.exists(name):os.unlink(name)


def read_flows(manifest_path: Path | None) -> dict[str, dict]:
    if manifest_path is None:return {}
    meta = read(manifest_path)
    pin = meta.pop("content_sha256", None)
    if (pin != sha256(canonical(meta)).hexdigest()
            or meta.get("schema") != "eraleader.kiwoom_selected_flow_capture_manifest.v1"
            or meta.get("historic_market_pit_certified") is not False
            or meta.get("trading_enabled") is not False
            or meta.get("unit") != "shares"
            or meta.get("companies") != len(meta.get("files", []))):
        raise ValueError("Invalid original Kiwoom capture manifest")
    flows = {}
    for item in meta["files"]:
        code = item.get("security_id")
        name = item.get("filename")
        if (type(code) is not str or not re.fullmatch("[0-9]{6}", code) or
                name != code + ".json" or code in flows):
            raise ValueError("Unsafe Kiwoom receipt identity")
        path = manifest_path.parent / name
        if path.is_symlink() or sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            raise ValueError("Kiwoom original report SHA mismatch")
        flow = read(path)
        if flow.get("content_sha256") is None or flow["security_id"] != code:
            raise ValueError("Capture identity or evidence missing")
        flows[code] = flow
    return flows


def publish(*, candidates: Path, industries: Path, site: Path,
            flow_manifest: Path | None = None, clock: datetime | None = None) -> dict:
    site = Path(site)
    if (not site.is_absolute() or not site.is_dir() or site.is_symlink()
            or any(p.is_symlink() for p in site.parents)):
        raise ValueError("Must publish into existing nonlinked local research site")
    basic, industry = read(candidates), read(industries)
    flows = read_flows(flow_manifest)
    report = build_overlay(basic, industry, flows=flows, decision_at=clock)
    html = render_overlay(report).encode("utf-8")
    result = (canonical(report) + b"\n")
    new_page, new_json = site / "investor_flow_kr.html", site.parent / "investor_flow_kr.json"
    if any(p.exists() or p.is_symlink() for p in (new_page, new_json)):
        raise FileExistsError("Flow evidence already exists; do not overwrite")
    backlinks = {
        "index.html": (b"</body>", "<p><a href='investor_flow_kr.html'>기관·외국인 수급 분석</a> · <a href='http://127.0.0.1:8782/'>키움 API 모의/실전 설정</a></p>"),
        "basic_candidates_kr.html": (
            b"</main>", "<p><a href='investor_flow_kr.html'>기관·외국인 수급 검증</a> · <a href='http://127.0.0.1:8782/'>키움 API 설정</a></p>"),
        "industry_peers_kr.html": (
            b"</main>", "<p><a href='investor_flow_kr.html'>수급 검증 결과</a> · <a href='http://127.0.0.1:8782/'>키움 API 설정</a></p>"),
    }
    old = {}
    updated = {}
    for name, (target, anchor) in backlinks.items():
        path = site / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Existing site page missing or linked")
        raw = path.read_bytes()
        if (raw.count(target) != 1 or b"investor_flow_kr.html" in raw or
                not raw.startswith(b"<!doctype html>")):
            raise ValueError("Flow UI link cannot be inserted safely")
        old[path] = raw
        updated[path] = raw.replace(target, anchor.encode("utf-8")+target, 1)
    created, changed = [], []
    try:
        for path, data in ((new_page, html), (new_json, result)):
            _new(path, data); created.append(path)
        for path, data in updated.items():
            _swap(path, old[path], data);changed.append(path)
    except BaseException:
        for path in reversed(changed):
            if path.read_bytes() == updated[path]:
                _swap(path, updated[path], old[path])
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {
        "status": "KIWOOM_FLOW_RESEARCH_PANEL_PUBLISHED",
        "selected_companies": report["selected_companies"],
        "kiwoom_received": report["kiwoom_flow_received_companies"],
        "flow_20_observations_usable": report["usable_20_observation_flow_companies"],
        "official_leaders": 0, "orders": 0,
        "page": new_page.name, "report_sha256": report["content_sha256"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json", type=Path, required=True)
    parser.add_argument("--industry-json", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--kiwoom-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        result = publish(candidates=args.candidate_json, industries=args.industry_json,
                         site=args.site, flow_manifest=args.kiwoom_manifest)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("KIWOOM_FLOW_OVERLAY_BLOCKED: "+type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
