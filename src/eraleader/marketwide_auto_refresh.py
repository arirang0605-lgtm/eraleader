"""6_2 local refresh from the latest already-published KR research evidence.

Reads only completed marketwide reports; never calls an API or places orders.
All previous immutable search pages remain available. A new market session
supersedes old data while missing/invalid candidates retain the last page.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re

from .marketwide_live_search import (_source, prepare_search, publish_search,
                                     render_html)
from .official_company_explorer import canonical

MAX_REPORT_FOLDERS = 400
MAX_MANIFEST_BYTES = 12000


def _safe_directory(path: Path) -> None:
    if (not isinstance(path, Path) or not path.is_absolute()
            or not path.is_dir() or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or path.stat().st_uid != os.geteuid()):
        raise ValueError("KR_SEARCH_REFRESH_UNSAFE_DIRECTORY")


def _owned_output(project: Path) -> Path:
    _safe_directory(project)
    root = project / "output"
    _safe_directory(root)
    return root


def _verified_existing(folder: Path, *, expected: dict, rows: list[dict],
                       now: datetime) -> bool:
    """Existing artifacts must exactly match the selected, verified source."""
    if folder.is_symlink() or not folder.is_dir():
        return False
    manifest_path, index = folder / "manifest.json", folder / "index.html"
    if (manifest_path.is_symlink() or index.is_symlink()
            or not manifest_path.is_file() or not index.is_file()
            or not 100 < manifest_path.stat().st_size <= MAX_MANIFEST_BYTES
            or not 1000 < index.stat().st_size <= 8_000_000):
        return False
    try:
        def unique(pairs):
            output = {}
            for key, value in pairs:
                if key in output:
                    raise ValueError("Duplicate manifest field")
                output[key] = value
            return output
        persisted = json.loads(manifest_path.read_bytes(), object_pairs_hook=unique)
        unsigned = dict(persisted)
        digest = unsigned.pop("content_sha256", None)
        if not isinstance(digest, str) or digest != sha256(canonical(unsigned)).hexdigest():
            return False
        published = datetime.fromisoformat(persisted["published_at_utc"])
        if (published.tzinfo is None or published.utcoffset() is None
                or published.astimezone(timezone.utc) > now):
            return False
        # generated-at time is the only allowed distinction between runs.
        fields = dict(expected)
        fields.pop("published_at_utc")
        fields.pop("content_sha256")
        compare = dict(unsigned)
        compare.pop("published_at_utc", None)
        if compare != fields:
            return False
        # The published HTML uses the producer dict insertion order; stored
        # manifest JSON is canonical/key-sorted, so reconstruct producer order.
        original_order = dict(expected)
        original_order["published_at_utc"] = persisted["published_at_utc"]
        original_order["content_sha256"] = digest
        return index.read_bytes() == render_html(original_order, rows)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return False


def refresh_latest_marketwide(*, source_root: Path, project: Path,
                              request_day: str,
                              clock: datetime | None = None) -> dict:
    """Auto-select the newest *market session*, then best complete partial data.

    The output naming is source-hash versioned. Same-day reruns are idempotent;
    newer evidence never overwrites earlier, reviewable local research pages.
    """
    _safe_directory(source_root)
    output_root = _owned_output(project)
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("KR_SEARCH_REFRESH_CLOCK_UNZONED")
    now = now.astimezone(timezone.utc)
    if request_day == "today":
        request_day = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    if not isinstance(request_day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", request_day):
        raise ValueError("KR_SEARCH_REFRESH_REQUEST_DAY_INVALID")

    directories = sorted(source_root.iterdir())
    if len(directories) > MAX_REPORT_FOLDERS:
        raise ValueError("KR_SEARCH_REFRESH_TOO_MANY_SOURCE_FOLDERS")
    valid = []
    rejected = 0
    for folder in directories:
        if folder.is_symlink() or not folder.is_dir():
            continue
        path = folder / "marketwide_kr.json"
        if not path.is_file() and not path.is_symlink():
            continue
        try:
            source, _ = _source(path)
            expected, rows = prepare_search(source, request_day=request_day, clock=now)
            priority = (expected["source_market_session"],
                        expected["research_50_scored"],
                        expected["financial_available"],
                        expected["industry_available"],
                        expected["flow_matched_session_companies"],
                        expected["source_built_at_utc"],
                        expected["source_marketwide_sha256"])
            valid.append((priority, path, expected, rows))
        except (ValueError, OSError, TypeError, KeyError, OverflowError):
            rejected += 1
    if not valid:
        return {
            "status": "NO_VERIFIED_KR_MARKETWIDE_SOURCE",
            "verified_candidates": 0,
            "rejected_candidates": rejected,
            "existing_pages_untouched": True,
            "official_leaders": 0,
            "orders": 0,
        }

    _, chosen, manifest, rows = max(valid, key=lambda item: item[0])
    digest = sha256(("kr-local-search-v1|"+request_day+"|"
                     +manifest["source_marketwide_sha256"]).encode()).hexdigest()[:12]
    target = output_root / ("marketwide_kr_search_"
                            + request_day.replace("-", "") + "_r" + digest)
    if target.exists() or target.is_symlink():
        if not _verified_existing(target, expected=manifest, rows=rows, now=now):
            raise ValueError("KR_SEARCH_REFRESH_EXISTING_OUTPUT_MISMATCH")
        status = "KR_MARKETWIDE_SEARCH_ALREADY_CURRENT"
    else:
        publish_search(input_report=chosen, output=target,
                       request_day=request_day, clock=now)
        status = "KR_MARKETWIDE_SEARCH_REFRESHED"
    return {
        "status": status,
        "site": str(target / "index.html"),
        "manifest": str(target / "manifest.json"),
        "source_market_session": manifest["source_market_session"],
        "requested_day": request_day,
        "observed_stocks": manifest["observed_stocks"],
        "financial_available": manifest["financial_available"],
        "research_50_scored": manifest["research_50_scored"],
        "stale_warning": manifest["stale_warning"],
        "verified_candidates": len(valid),
        "rejected_candidates": rejected,
        "existing_pages_untouched": True,
        "official_leaders": 0,
        "orders": 0,
    }
