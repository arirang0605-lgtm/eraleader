"""Conservative official KRX/DART daily research -> Kiwoom demo research admission.

Current-day official raw WATCH capture is NOT a current-day financial/industry
candidate cohort. A broker read requires a separately published, internally
pinned same-session candidate+industry pair. No investment promotion.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import re

from .official_kiwoom_flow_overlay import build_overlay
from .kiwoom_daily_runner import run as run_kiwoom
from scripts.publish_kiwoom_flow_overlay import read

KST = ZoneInfo("Asia/Seoul")
ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
OFFICIAL_SCHEMA = "eraleader.official_api_pit_research_bridge.v1"


def reject_empty_live_krx(url: str, headers: dict, *, day: str, fetch):
    """Validate KRX rows before archiving the SAME original response bytes.

    Zero-row KRX does not prove trading, nor does it establish a holiday.
    """
    from urllib.parse import urlsplit
    from .official_api_capture import SOURCES, _decoded
    raw = fetch(url, headers)
    path = urlsplit(url).path
    for name in ("krx-kospi", "krx-kosdaq"):
        if path == SOURCES[name][1]:
            rows, _ = _decoded(raw, name, day=day, cik=None)
            if rows < 1:
                raise ValueError("OFFICIAL_KRX_DAILY_ROWS_NOT_YET_AVAILABLE")
            break
    return raw


def _regular(path: Path) -> bool:
    return (path.is_absolute() and not path.is_symlink() and
            path.is_file() and not any(p.is_symlink() for p in path.parents))


def _inspect_official(path: Path, day: str, now: datetime) -> dict | None:
    evidence = path / "official_api_pit_research.json"
    if not evidence.exists() and not evidence.is_symlink():
        return None
    if not _regular(evidence):
        raise ValueError("OFFICIAL_DAY_EVIDENCE_UNSAFE")
    data = read(evidence)
    rows = data.get("dart_full_day")
    sources = data.get("sources")
    tags = {x.get("source"): x for x in sources} if (
        type(sources) is list and all(type(x) is dict for x in sources)) else {}
    expected = {"krx-kospi", "krx-kosdaq", "dart-disclosures"}
    if (data.get("schema") != OFFICIAL_SCHEMA
            or data.get("api_observation_day") != day
            or data.get("official_leaders") != 0
            or data.get("historic_universe_pit_verified") is not False
            or data.get("issuer_share_class_verified") is not False
            or type(rows) is not dict or rows.get("market_day") != day
            or type(rows.get("row_count")) is not int
            or rows["row_count"] < 0
            or type(rows.get("page_count")) is not int or rows["page_count"] < 1
            or not re.fullmatch(r"[a-f0-9]{64}", str(rows.get("manifest_sha256")))
            or not expected.issubset(tags) or len(tags) != len(sources)
            or any(type(tags[x].get("row_count")) is not int or
                   tags[x]["row_count"] <= 0 for x in ("krx-kospi", "krx-kosdaq"))
            or any(not re.fullmatch(r"[a-f0-9]{64}", str(tags[x].get("first_receipt_sha256")))
                   for x in expected)
            or any(not _regular(path / "site" / page)
                   for page in ("kr.html", "official_api.html"))):
        raise ValueError("OFFICIAL_DAY_PIT_RESEARCH_EVIDENCE_INVALID")
    decision = data.get("decision_at")
    if type(decision) is not str:
        raise ValueError("OFFICIAL_DAY_CLOCK_MISSING")
    received = datetime.fromisoformat(decision.replace("Z", "+00:00"))
    if (received.tzinfo is None or received.utcoffset() is None
            or received.astimezone(timezone.utc) > now):
        raise ValueError("OFFICIAL_DAY_CLOCK_INVALID")
    return {"day": day, "official_decision_at": received.astimezone(timezone.utc),
            "source_pins": {x: tags[x]["first_receipt_sha256"] for x in expected},
            "dart_manifest_sha256": rows["manifest_sha256"],
            "source_tags": sorted(tags), "dart_rows": rows["row_count"]}


def _inspect_cohort(root: Path, day: str, now: datetime, official: dict,
                    codes: list[str]) -> tuple[Path, Path, Path] | None:
    if root.is_symlink() or not root.is_absolute():
        raise ValueError("COHORT_ROOT_UNSAFE")
    basic = root / "basic_candidates_kr.json"
    industry = root / "industry_peers_kr.json"
    site = root / "site"
    if not (basic.exists() and industry.exists()):
        return None
    if not (_regular(basic) and _regular(industry) and
            site.is_dir() and not site.is_symlink()):
        raise ValueError("COHORT_EVIDENCE_UNSAFE")
    a, b = read(basic), read(industry)
    if a.get("market_session", "").replace("-", "") != day.replace("-", ""):
        return None
    if b.get("market_session", "").replace("-", "") != day.replace("-", ""):
        return None
    verified = build_overlay(a, b, flows={}, decision_at=now)
    # Date-matching alone is insufficient: the candidate's original WATCH
    # run must use EXACTLY the KRX/DART first receipts of this day's capture.
    run_id = a.get("source_watch_run_id")
    if type(run_id) is not str or re.fullmatch(r"[a-f0-9]{20}", run_id) is None:
        raise ValueError("COHORT_RUN_ID_MISSING")
    run_path = root / "runs" / (run_id + ".json")
    if not _regular(run_path):
        raise ValueError("COHORT_RUN_ORIGINAL_MISSING")
    run_data = read(run_path)
    proof = run_data.get("official_api_evidence")
    if (run_data.get("run_id") != run_id or
            type(proof) is not dict or proof.get("api_observation_day") != day or
            proof.get("official_leaders") != 0 or
            proof.get("issuer_share_class_verified") is not False or
            type(proof.get("sources")) is not list or
            not all(type(x) is dict for x in proof["sources"])):
        raise ValueError("COHORT_SOURCE_RUN_INVALID")
    selected = {r.get("source"): r.get("first_receipt_sha256")
                for r in proof["sources"]}
    if (len(selected) != len(proof["sources"]) or
            any(selected.get(k) != pin for k, pin in official["source_pins"].items())
            or (proof.get("dart_full_day") or {}).get("manifest_sha256")
               != official["dart_manifest_sha256"]):
        raise ValueError("COHORT_FIRST_ORIGINAL_RECEIPTS_DIFFER")
    from .kiwoom_investor_flow import utc
    if utc(a["decision_at_utc"]) < official["official_decision_at"]:
        raise ValueError("COHORT_PREDATES_OFFICIAL_RECEIPT")
    valid = {x["security_id"] for x in verified["comparisons"]}
    if not set(codes).issubset(valid):
        raise ValueError("SELECTED_SECURITIES_OUTSIDE_COHORT")
    return basic, industry, site


def advance(*, market_day: str, official_out: Path, cohort_root: Path,
            codes: list[str], clock: datetime | None = None,
            capture_official=None, apply_capture: bool = False,
            apply_kiwoom: bool = False, client_factory=None) -> dict:
    """Network and writes occur only in opt-in branches and after close."""
    if type(market_day) is not str or not ISO_DAY.fullmatch(market_day):
        raise ValueError("INVALID_OFFICIAL_MARKET_DAY")
    parsed = date.fromisoformat(market_day)
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("OFFICIAL_REFRESH_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    local = now.astimezone(KST)
    if (type(codes) is not list or not 1 <= len(codes) <= 5 or
            len(set(codes)) != len(codes) or
            any(type(x) is not str or re.fullmatch(r"[0-9]{6}", x) is None for x in codes)):
        raise ValueError("INVALID_OFFICIAL_RESEARCH_COHORT")
    if not official_out.is_absolute() or official_out.is_symlink() or        not cohort_root.is_absolute() or cohort_root.is_symlink():
        raise ValueError("OFFICIAL_REFRESH_PATH_UNSAFE")
    def status(name, **extra):
        return {"status": name, "market_day": market_day,
                "broker_orders": 0, "investment_rank_changed": False,
                "official_pit_certified": False, **extra}
    if parsed != local.date():
        return status("HOLD_NOT_CURRENT_MARKET_DAY")
    if local.weekday() >= 5:
        return status("HOLD_WEEKEND")
    if local.time() < time(19, 0):
        return status("HOLD_MARKET_RESEARCH_CUTOFF_19_KST")
    official = _inspect_official(official_out, market_day, now)
    if official is None and apply_capture:
        if not callable(capture_official):
            raise ValueError("OFFICIAL_CAPTURE_HANDLER_REQUIRED")
        if official_out.exists() or official_out.is_symlink():
            raise ValueError("OFFICIAL_OUTPUT_ALREADY_EXISTS_UNVERIFIED")
        result = capture_official()
        if (type(result) is not dict or result.get("status") != "OFFICIAL_KR_DAY_RESEARCH_ONLY"
                or result.get("market_session") != market_day):
            raise ValueError("OFFICIAL_CAPTURE_DID_NOT_CONFIRM_DAY")
        official = _inspect_official(official_out, market_day, datetime.now(timezone.utc)
                                     if clock is None else now)
        if official is None:
            raise ValueError("OFFICIAL_CAPTURE_EVIDENCE_MISSING")
    if official is None:
        return status("WAIT_OFFICIAL_KRX_DART_RESEARCH", api_calls=0)
    cohort = _inspect_cohort(cohort_root, market_day, now, official, codes)
    if cohort is None:
        return status("WAIT_SAME_DAY_CFS_INDUSTRY_COHORT",
                      official_research_exists=True, broker_requests=0)
    if not apply_kiwoom:
        return status("READY_TO_CHECK_KIWOOM_DEMO_NO_NETWORK",
                      official_research_exists=True, broker_requests=0)
    kiwoom = run_kiwoom(site=cohort[2], candidates=cohort[0],
                        industries=cohort[1], stock_codes=codes,
                        client_factory=client_factory, clock=clock, apply=True,
                        cutoff_hour=19)
    return status("KIWOOM_" + kiwoom["status"],
                  official_research_exists=True,
                  broker_requests=kiwoom.get("network_calls", 0))
