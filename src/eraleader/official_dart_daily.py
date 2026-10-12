"""Official DART daily disclosure pagination with first-received and SHA lineage.

Research evidence only: receipt dates do not prove intraday public availability,
complete company membership, or any financial metric's reporting history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib import parse
import json
import math
import os
import re
import shutil
import stat
import tempfile
import uuid

from .official_api_capture import (
    _canonical, _decoded, _http_get, _root, _settings, _write_new,
    credentials,
)
from .official_api_pit_bridge import _private_file, verified_capture

SCHEMA = "eraleader.official_dart_complete_day_first_received.v1"
MAX_PAGES = 100


def _page(raw: bytes, *, day: str, number: int,
          total: int | None = None, page_count: int = 100) -> tuple[dict, int]:
    count, quality = _decoded(raw, "dart-disclosures", day=day, cik=None)
    data = json.loads(raw)
    if quality == "NO_DISCLOSURES_FOR_DAY":
        if number != 1 or total not in (None, 0):
            raise ValueError("DART no-data page incompatible with claimed count")
        return data, 0
    reported = data.get("total_count")
    if type(reported) not in (str, int) or not str(reported).isdigit():
        raise ValueError("DART total_count is not a decimal")
    reported = int(reported)
    if reported < 1 or (total is not None and reported != total):
        raise ValueError("DART total_count changed during pagination")
    for field, expected in (("page_no", number), ("page_count", page_count)):
        observed = data.get(field)
        if type(observed) not in (str, int) or str(observed) != str(expected):
            raise ValueError("DART pagination metadata mismatch")
    pages = math.ceil(reported / page_count)
    if str(data.get("total_page")) != str(pages) or pages > MAX_PAGES:
        raise ValueError("DART total pages invalid or over safe limit")
    expected_rows = page_count if number < pages else reported - page_count * (pages - 1)
    if number > pages or count != expected_rows:
        raise ValueError("DART missing or duplicated page position")
    seen = set()
    for r in data["list"]:
        no = r["rcept_no"]
        if no in seen:
            raise ValueError("DART duplicate receipt inside page")
        seen.add(no)
    return data, reported


def capture_dart_day(first_folder: Path, first_sha: str, output_root: Path,
                     *, creds: dict, fetch=None, clock=None,
                     max_pages: int = MAX_PAGES) -> dict:
    """Complete *one* prior captured DART day, atomic on success only.

    The existing original first page is NEVER rewritten. Pages >1 are fetched
    from the pinned DART HTTPS origin in sequence. No silent partial publish.
    """
    output_root = _root(output_root)
    now = clock or (lambda: datetime.now(timezone.utc))
    first, original = verified_capture(
        first_folder, "dart-disclosures", first_sha, now())
    day = first["request_value"]
    if type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("Invalid explicit safe page limit")
    first_raw = _private_file(Path(first_folder) / "raw_response.json", 0o600)
    first_body, total = _page(first_raw, day=day, number=1)
    pages = max(1, math.ceil(total/100))
    if pages > max_pages:
        raise ValueError("DART day needs more pages than requested safe cap")
    url, headers = _settings("dart-disclosures", day=day, cik=None, creds=creds)
    parsed = parse.urlsplit(url)
    query = parse.parse_qs(parsed.query)
    fetch = fetch or _http_get
    target = output_root / ("dart_full_" + uuid.uuid4().hex)
    seen = set()
    entries = []
    stage = Path(tempfile.mkdtemp(prefix=".dart_inflight_", dir=output_root))
    try:
        os.chmod(stage, 0o700)
        last_stamp = None
        for idx in range(1, pages+1):
            if idx == 1:
                raw = first_raw
                body = first_body
                receipt_time = first["first_local_received_at_utc"]
            else:
                query["page_no"] = [str(idx)]
                page_url = parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                            parse.urlencode(query, doseq=True), ""))
                raw = fetch(page_url, headers)
                body, checked_total = _page(raw, day=day, number=idx, total=total)
                if checked_total != total:
                    raise ValueError("DART pagination total changed")
                stamp = now()
                if stamp.tzinfo is None:
                    raise ValueError("DART first receipt clock must have timezone")
                receipt_time = stamp.astimezone(timezone.utc).isoformat()
            if idx == 1 and total > 0:
                body, _ = _page(raw, day=day, number=1, total=total)
            stamp = datetime.fromisoformat(receipt_time.replace("Z","+00:00"))
            if stamp.tzinfo is None or (last_stamp and stamp < last_stamp):
                raise ValueError("DART local receipt times must be monotonic")
            last_stamp = stamp
            rows = body.get("list",[])
            for row in rows:
                rid = row["rcept_no"]
                if rid in seen:
                    raise ValueError("DART duplicate disclosure across pages")
                seen.add(rid)
            filename = f"page_{idx:03d}.json"
            _write_new(stage/filename,raw)
            entries.append({"page_no":idx, "filename":filename,
                            "sha256":sha256(raw).hexdigest(), "count":len(rows),
                            "first_local_received_at_utc":receipt_time})
        if len(seen) != total:
            raise ValueError("Incomplete DART total rows, cannot publish")
        manifest = {
            "schema":SCHEMA,"source":"dart-disclosures","market_day":day,
            "original_first_capture_id":Path(first_folder).name,
            "original_first_receipt_sha256":first_sha,
            "original_first_raw_sha256":first["raw_sha256"],
            "total_count":total, "total_pages":pages,
            "pages":entries,"all_rows_unique":True,
            "company_issuer_class_pit_certified":False,
            "intraday_publication_time_independently_verified":False,
            "financial_metrics_pit_joined":False,"official_leaders":0,
        }
        raw_manifest = _canonical(manifest)
        _write_new(stage/"manifest.json",raw_manifest)
        os.replace(stage, target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"status":"DART_COMPLETE_RETRIEVED_DAY_RESEARCH_ONLY",
            "market_day":day,"total_rows":total,"pages":pages,
            "captured_new_pages":pages-1,"manifest_sha256":sha256(raw_manifest).hexdigest(),
            "capture_id":target.name,"pit_certified":False}


def verify_dart_day(folder: Path, manifest_sha256: str,
                    *, first_folder: Path | None = None,
                    first_sha: str | None = None,
                    decision_at: datetime | None = None) -> dict:
    """Read-only as-of gate on every original page byte, identity and receipt."""
    folder = Path(folder)
    if (not folder.is_absolute() or folder.is_symlink() or
            not folder.is_dir() or stat.S_IMODE(folder.stat().st_mode) != 0o700 or
            folder.stat().st_uid != os.geteuid() or
            not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256)):
        raise ValueError("DART private folder and immutable manifest SHA required")
    data = _private_file(folder/"manifest.json", 0o600)
    if sha256(data).hexdigest() != manifest_sha256:
        raise ValueError("DART first manifest SHA pin mismatch")
    manifest = json.loads(data)
    if (manifest.get("schema") != SCHEMA or
            manifest.get("source") != "dart-disclosures" or
            manifest.get("all_rows_unique") is not True or
            manifest.get("official_leaders") != 0 or
            manifest.get("company_issuer_class_pit_certified") is not False):
        raise ValueError("DART manifest contract corrupted")
    pages = manifest["pages"]
    total = manifest["total_count"]
    if (type(total) is not int or type(pages) is not list or
            not 1 <= len(pages) <= MAX_PAGES or
            manifest.get("total_pages") != len(pages)):
        raise ValueError("DART manifest counts invalid")
    if (first_folder is None) != (first_sha is None):
        raise ValueError("DART original first source and SHA must be paired")
    if first_folder is not None:
        if first_sha != manifest["original_first_receipt_sha256"]:
            raise ValueError("DART original first SHA mismatch")
        original, _ = verified_capture(first_folder,"dart-disclosures",first_sha,
                                         decision_at or datetime.now(timezone.utc))
        if (original["raw_sha256"] != manifest["original_first_raw_sha256"] or
                Path(first_folder).name != manifest["original_first_capture_id"]):
            raise ValueError("DART original first raw receipt mismatch")
    if decision_at is not None and (decision_at.tzinfo is None or
                                    decision_at.utcoffset() is None):
        raise ValueError("DART decision timestamp must be aware")
    all_rows = []
    seen = set()
    previous = None
    for index, entry in enumerate(pages, 1):
        name = f"page_{index:03d}.json"
        if entry.get("page_no") != index or entry.get("filename") != name:
            raise ValueError("DART page sequence tampered")
        raw = _private_file(folder/name, 0o600)
        if sha256(raw).hexdigest() != entry.get("sha256"):
            raise ValueError("DART page SHA changed")
        body, checked = _page(raw, day=manifest["market_day"],
                              number=index, total=total)
        if checked != total or len(body.get("list",[])) != entry["count"]:
            raise ValueError("DART page count tampered")
        observed = datetime.fromisoformat(entry["first_local_received_at_utc"].replace("Z","+00:00"))
        if (observed.tzinfo is None or previous is not None and observed < previous or
                decision_at is not None and observed > decision_at):
            raise ValueError("DART page not received by decision time")
        previous=observed
        if index == 1 and sha256(raw).hexdigest()!=manifest["original_first_raw_sha256"]:
            raise ValueError("DART original page unpinned")
        for row in body.get("list",[]):
            rid=row["rcept_no"]
            if rid in seen:
                raise ValueError("Duplicate DART rcept_no across pages")
            seen.add(rid)
            all_rows.append(row)
    if len(all_rows) != total or len(pages) != max(1, math.ceil(total/100)):
        raise ValueError("DART full daily coverage mismatch")
    expected_names={e["filename"] for e in pages}|{"manifest.json"}
    if {p.name for p in folder.iterdir()} != expected_names:
        raise ValueError("DART unaccounted first-capture files")
    return {"market_day":manifest["market_day"],"total_rows":total,
            "total_pages":len(pages),"manifest_sha256":manifest_sha256,
            "last_received_at_utc":pages[-1]["first_local_received_at_utc"],
            "financial_pit_verified":False,"issuer_class_pit_verified":False,
            "rows":all_rows}


def observed_dart_unique_corp_map(rows: list[dict], krx_ids: set[str]) -> dict[str,str]:
    """Observed *same-day* code-to-corp overlap. Never certified share-class PIT."""
    unique = {}
    ambiguous = set()
    for row in rows:
        code, corp = row.get("stock_code"), row.get("corp_code")
        if (code not in krx_ids or type(code) is not str or
                not re.fullmatch(r"[A-Za-z0-9]{6}", code) or
                type(corp) is not str or not re.fullmatch(r"[0-9]{8}", corp)):
            continue
        if code in unique and unique[code] != corp:
            ambiguous.add(code)
        else:
            unique[code] = corp
    return {code:corp for code,corp in unique.items() if code not in ambiguous}


def observed_dart_stock_links(rows: list[dict], krx_ids: set[str]) -> dict:
    """Only same-day code overlap, never asserts unique legal class ownership."""
    code_corp = {}
    rejected=0
    for row in rows:
        code=row.get("stock_code")
        corp=row.get("corp_code")
        if code not in krx_ids:
            continue
        if (type(code) is not str or not re.fullmatch(r"[0-9A-Za-z]{6}",code) or
                type(corp) is not str or not re.fullmatch(r"[0-9]{8}",corp)):
            rejected+=1
            continue
        code_corp.setdefault(code,set()).add(corp)
    ambiguous={code for code,ids in code_corp.items() if len(ids)!=1}
    return {"observed_matching_security_count":len(code_corp)-len(ambiguous),
            "ambiguous_security_count":len(ambiguous),
            "unusable_rows":rejected,
            "issuer_class_pit_certified":False,
            "current_observation_only":True}
