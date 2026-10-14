"""Attach verified cash observations to an existing WATCH edition, then brief.

The original queue order and observation dates are preserved. No new ranking,
source API, current-market claim or replacement cashflow report is introduced.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import math
import os
import re
import shutil
import tempfile

from .dart_cashflow_watch import CASH_FIELDS, METHOD, read_cashflow
from .official_company_explorer import canonical
from .marketwide_auto_refresh import _owned_output
from .marketwide_live_search import _source

SHA = re.compile(r"[a-f0-9]{64}\Z")


def validate_cashflow_watch_fields(doc: dict, now: datetime) -> None:
    """Validate added evidence without changing the existing WATCH contract."""
    if doc.get("dart_cashflow_method") is None:
        return
    stamp = datetime.fromisoformat(doc["watch_published_at_utc"])
    original = datetime.fromisoformat(doc["original_watch_published_at_utc"])
    report_time = datetime.fromisoformat(doc["source_cashflow_published_at_utc"])
    if (doc["dart_cashflow_method"] != METHOD
            or doc.get("archived_watch_annotation_only") is not True
            or original.tzinfo is None or report_time.tzinfo is None
            or stamp.tzinfo is None or original > stamp or report_time > stamp or stamp > now
            or not SHA.fullmatch(doc.get("source_original_watch_sha256", ""))
            or not SHA.fullmatch(doc.get("source_cashflow_sha256", ""))):
        raise ValueError("WATCH_CASHFLOW_ANNOTATION_TIME_OR_SOURCE_INVALID")
    cfo_count = after_count = 0
    for row in doc["review_queue"]:
        if any(key not in row for key in CASH_FIELDS):
            raise ValueError("WATCH_CASHFLOW_ROW_FIELDS_MISSING")
        for key in CASH_FIELDS:
            value = row[key]
            if key == "dart_cfs_operating_cash_positive_two_years":
                if value is not None and type(value) is not bool:
                    raise ValueError("WATCH_CASHFLOW_BOOLEAN_INVALID")
            elif value is not None and (type(value) not in (int, float)
                                       or not math.isfinite(value)):
                raise ValueError("WATCH_CASHFLOW_VALUE_INVALID")
        cfo = row["dart_cfs_operating_cashflow_krw"]
        ppe = row["dart_cfs_ppe_purchase_raw_krw"]
        intangible = row["dart_cfs_intangible_purchase_raw_krw"]
        for raw, normalized in ((ppe, row["dart_cfs_ppe_purchase_outflow_krw"]),
                                (intangible, row["dart_cfs_intangible_purchase_outflow_krw"])):
            if normalized != (abs(raw) if raw is not None else None):
                raise ValueError("WATCH_CASHFLOW_PURCHASE_SIGN_INVALID")
        expected = cfo-abs(ppe)-abs(intangible) if all(
            x is not None for x in (cfo, ppe, intangible)) else None
        if row["dart_cfs_cash_after_ppe_intangibles_krw"] != expected:
            raise ValueError("WATCH_CASHFLOW_ARITHMETIC_INVALID")
        if cfo is not None:
            cfo_count += 1
        if expected is not None:
            after_count += 1
        pin = row.get("dart_cashflow_first_receipt_sha256")
        if pin is not None:
            available = datetime.fromisoformat(row["dart_cashflow_first_received_at_utc"])
            if (not SHA.fullmatch(pin) or pin != row.get("dart_cfs_first_receipt_sha256")
                    or available.tzinfo is None or available > stamp
                    or row["dart_cashflow_first_received_at_utc"]
                       != row.get("dart_cfs_first_received_at_utc")
                    or row.get("dart_cashflow_issuer_corp_code")
                       != row.get("dart_cfs_issuer_corp_code")
                    or row.get("dart_cashflow_fiscal_year")
                       != row.get("dart_latest_cfs_business_year")):
                raise ValueError("WATCH_CASHFLOW_ISSUER_RECEIPT_OR_FUTURE")
        elif any(row[k] is not None for k in CASH_FIELDS):
            raise ValueError("WATCH_CASHFLOW_MISSING_ORIGINAL_RECEIPT")
    if (doc.get("dart_cashflow_cfo_available") != cfo_count
            or doc.get("dart_cashflow_cash_after_purchases_available") != after_count):
        raise ValueError("WATCH_CASHFLOW_COVERAGE_INVALID")


def merge_cashflow_fields(watch: dict, cash: dict, context: dict, now: datetime) -> dict:
    """Require the same company, period and exact verified original receipt."""
    if (cash["source_watch_sha256"] != watch["content_sha256"]
            or cash["source_marketwide_sha256"] != watch["source_marketwide_sha256"]
            or cash["source_market_session"] != watch["source_market_session"]
            or cash["watch_rows"] != watch["review_candidates"]):
        raise ValueError("WATCH_CASHFLOW_SOURCE_MISMATCH")
    records = {r["security_id"]: r for r in cash["entries"]}
    if len(records) != len(cash["entries"]) or set(records) != {
            r["security_id"] for r in watch["review_queue"]}:
        raise ValueError("WATCH_CASHFLOW_COMPANY_SET_MISMATCH")
    payload = deepcopy(watch)
    for row in payload["review_queue"]:
        data = records[row["security_id"]]
        firm = context.get(row["security_id"]) or {}
        if (data["name"] != row["name"]
                or data["fiscal_year"] != firm.get("dart_latest_cfs_business_year")
                or data["first_receipt_sha256"] != firm.get("dart_cfs_first_receipt_sha256")
                or data["first_received_at_utc"] != firm.get("dart_cfs_first_received_at_utc")
                or data["previous_first_receipt_sha256"]
                   != firm.get("dart_cfs_previous_first_receipt_sha256")
                or data["previous_first_received_at_utc"]
                   != firm.get("dart_cfs_previous_first_received_at_utc")
                or any(data.get(k) != firm.get(k) for k in CASH_FIELDS)):
            raise ValueError("WATCH_CASHFLOW_VERIFIED_COMPANY_FACTS_MISMATCH")
        for key in CASH_FIELDS:
            row[key] = data.get(key)
        row.update(
            dart_cashflow_fiscal_year=data["fiscal_year"],
            dart_cashflow_first_receipt_sha256=data["first_receipt_sha256"],
            dart_cashflow_first_received_at_utc=data["first_received_at_utc"],
            dart_cashflow_issuer_corp_code=firm.get("dart_cfs_issuer_corp_code"))
    payload.update(
        dart_cashflow_method=METHOD,
        watch_cashflow_attachment_method="VERIFIED_ARCHIVED_WATCH_CASH_FIELDS_V1",
        source_cashflow_sha256=cash["content_sha256"],
        source_original_watch_sha256=watch["content_sha256"],
        original_watch_published_at_utc=watch["watch_published_at_utc"],
        source_cashflow_published_at_utc=cash["first_report_generated_at_utc"],
        archived_watch_annotation_only=True,
        watch_published_at_utc=now.isoformat(),
        dart_cashflow_cfo_available=cash["cfo_available"],
        dart_cashflow_cash_after_purchases_available=cash["cash_after_purchases_available"])
    validate_cashflow_watch_fields(payload, now)
    payload.pop("content_sha256", None)
    payload["content_sha256"] = sha256(canonical(payload)).hexdigest()
    return payload


def publish_watch_cashflow_fields(*, project: Path, marketwide: Path,
                                 watch_manifest: Path, cashflow_manifest: Path,
                                 capture_root: Path, clock: datetime | None = None) -> dict:
    from .early_leader_watch_queue import _validated, _html, watch_version, FOLDER
    from .dart_profitability_watch import dart_annual_margin_context
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("WATCH_CASHFLOW_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    watch = _validated(watch_manifest, clock=now)
    cash = read_cashflow(cashflow_manifest, clock=now)
    market, _ = _source(marketwide)
    if market["content_sha256"] != watch["source_marketwide_sha256"]:
        raise ValueError("WATCH_CASHFLOW_MARKET_SOURCE_MISMATCH")
    # Existing verified original reader rechecks company IDs, dates and bytes.
    context = dart_annual_margin_context(market=market, capture_root=capture_root,
                                        now=now, include_cashflow=True)
    payload = merge_cashflow_fields(watch, cash, context, now)
    root = _owned_output(project)/FOLDER
    if root.is_symlink():
        raise ValueError("WATCH_CASHFLOW_OUTPUT_LINKED")
    root.mkdir(mode=0o700, exist_ok=True)
    dest = root/("KR_"+watch["source_market_session"].replace("-", "")
                 +"_"+watch_version(payload))
    if dest.is_symlink():
        raise ValueError("WATCH_CASHFLOW_VERSION_LINKED")
    if dest.exists():
        previous = _validated(dest/"watch_queue.json", clock=now)
        old_core, new_core = dict(previous), dict(payload)
        for candidate in (old_core, new_core):
            candidate.pop("watch_published_at_utc", None)
            candidate.pop("content_sha256", None)
        if (old_core != new_core or (dest/"index.html").is_symlink()
                or (dest/"index.html").read_bytes() != _html(previous)):
            raise ValueError("WATCH_CASHFLOW_EXISTING_CONFLICT")
        state = "ALREADY_PUBLISHED"
    else:
        stage = Path(tempfile.mkdtemp(prefix=".watch_cash_fields_", dir=root))
        try:
            for name, body in (("watch_queue.json", canonical(payload)+b"\n"),
                               ("index.html", _html(payload))):
                fd = os.open(stage/name, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(body); stream.flush(); os.fsync(stream.fileno())
            if (_validated(watch_manifest, clock=now)["content_sha256"]
                    != watch["content_sha256"]
                    or read_cashflow(cashflow_manifest, clock=now)["content_sha256"]
                       != cash["content_sha256"] or dest.exists() or dest.is_symlink()):
                raise ValueError("WATCH_CASHFLOW_INPUT_CHANGED")
            os.rename(stage, dest)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        state = "PUBLISHED"
    return {"status": state, "manifest": str(dest/"watch_queue.json"),
            "site": str(dest/"index.html"), "watch_rows": watch["review_candidates"],
            "cfo_available": cash["cfo_available"],
            "cash_after_purchases_available": cash["cash_after_purchases_available"],
            "source_market_session": watch["source_market_session"],
            "archived_watch_annotation_only": True, "external_api_calls": 0, "orders": 0}
