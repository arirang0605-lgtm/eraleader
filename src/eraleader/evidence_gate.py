"""Fail-closed local pre-promotion evidence gate for KR/US candidate research.

This reconciles *derived* audit summaries only. Even all-green local
diagnostics NEVER certify source authenticity, historical PIT coverage,
official leadership states or actual forecasting performance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

MARKET_ZONE = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
REPORTS = {
    "source_vintage": "source_vintage_audit_research.json",
    "issuer_lineage": "issuer_lineage_{market}_research.json",
    "exchange_calendar": "calendar_{market}_research.json",
    "price_continuity": "continuity_{market}_research.json",
    "membership_price": "pit_coverage_{market}.json",
}
EXPECTED_STATUSES = {
    "source_vintage": {"RESEARCH_RETROSPECTIVE_VINTAGE_NOT_PIT",
                       "RESEARCH_DECLARED_VINTAGE_NOT_CERTIFIED"},
    "issuer_lineage": {"RESEARCH_RETROSPECTIVE_IDENTITY_NOT_PIT",
                       "RESEARCH_ISSUER_IDENTITY_AUDIT_NOT_CERTIFIED"},
    "exchange_calendar": {"LOCAL_CALENDAR_COMPARISON_NOT_PIT_CERTIFIED"},
    "price_continuity": {"LOCAL_OBSERVATION_CONTINUITY_NOT_PIT_CERTIFIED"},
    "membership_price": {"PIT_MEMBERSHIP_OBSERVATION_AUDIT_NOT_CERTIFIED"},
}
NEVER_CERTIFIED = {
    "source_vintage": ("historical_pit_certified", "source_timestamp_independently_attested"),
    "issuer_lineage": ("historic_membership_pit_certified",
                       "permanent_identity_independently_verified"),
    "exchange_calendar": ("calendar_pit_certified", "calendar_independently_attested"),
    "price_continuity": ("historic_universe_pit_certified",
                         "exchange_calendar_completeness_verified"),
    "membership_price": ("historic_membership_pit_certified",
                         "price_availability_pit_certified"),
}


def _iso_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Decision requires timezone-aware ISO timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid decision timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Decision requires timezone-aware ISO timestamp")
    return stamp.astimezone(timezone.utc)


def _nonnegative(report: dict, field: str) -> int:
    value = report.get(field)
    if type(value) is not int or value < 0:
        raise ValueError(f"Missing or invalid evidence count: {field}")
    return value


def _add_if(condition: bool, issues: list[str], code: str) -> None:
    if condition:
        issues.append(code)


def evaluate_local_evidence(report_dir: Path, *, market: str,
                            decision_at: str) -> dict:
    """Reconcile at one decision cut; never accept summary flags as proof.

    Only fixed basename files from one local directory are read. Missing
    reports are visible blockers, not implied zero evidence or silent passes.
    """
    if market not in MARKET_ZONE:
        raise ValueError("market must be KR/US")
    cutoff = _iso_time(decision_at)
    target_day = cutoff.astimezone(MARKET_ZONE[market]).date().isoformat()
    folder = Path(report_dir)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("Source audit directory must be real and existing")
    items = []
    blockers = []
    for domain, name in REPORTS.items():
        filename = name.format(market=market.lower())
        path = folder / filename
        if path.is_symlink():
            raise ValueError(f"Unsafe symlink source audit report: {domain}")
        if not path.exists():
            items.append({"domain": domain, "present": False,
                          "filename": filename, "sha256": None,
                          "issues": ["REPORT_MISSING"]})
            blockers.append(f"{domain}:REPORT_MISSING")
            continue
        if not path.is_file() or path.stat().st_size > 3_000_000:
            raise ValueError(f"Missing or oversized evidence report: {domain}")
        blob = path.read_bytes()
        report = json.loads(blob)
        if not isinstance(report, dict) or report.get("status") not in EXPECTED_STATUSES[domain]:
            raise ValueError(f"Unexpected audit schema/status: {domain}")
        # A compromised/forged downstream report must not promote candidates.
        if any(report.get(k) is not False for k in NEVER_CERTIFIED[domain]):
            raise ValueError(f"Untrusted certified or missing status in {domain}")
        issues = []
        if domain == "source_vintage":
            asof = _iso_time(report.get("decision_at"))
            _add_if(asof != cutoff, issues, "DECISION_TIMESTAMP_MISMATCH")
            sources = report.get("sources")
            if not isinstance(sources, list) or not sources:
                raise ValueError("Source vintage rows missing")
            selected = [x for x in sources if isinstance(x, dict) and x.get("market") == market]
            _add_if(not selected, issues, "MARKET_SOURCE_MISSING")
            kinds = {x.get("kind") for x in selected}
            for kind in ("membership", "actions", "fundamentals", "industry",
                         "raw_prices", "total_return_index"):
                _add_if(kind not in kinds, issues, f"NO_{kind.upper()}_SOURCE")
            for item in selected:
                if item.get("sha256_verified") is not True:
                    raise ValueError("Source-vintage checksum attestation missing")
                _add_if(item.get("retrospective_backfill") is True, issues,
                        "RETROSPECTIVE_SOURCE_VINTAGE")
                _add_if(item.get("retrieved_by_decision_claimed") is not True,
                        issues, "SOURCE_RETRIEVED_AFTER_DECISION")
        else:
            _add_if(report.get("market") != market, issues, "MARKET_MISMATCH")
            key = {
                "issuer_lineage": "decision_at",
                "exchange_calendar": "cutoff",
                "price_continuity": "as_of_requested",
                "membership_price": "requested_as_of",
            }[domain]
            instant = report.get(key)
            if key == "decision_at":
                _add_if(_iso_time(instant) != cutoff, issues,
                        "DECISION_TIMESTAMP_MISMATCH")
            else:
                _add_if(instant != target_day, issues,
                        "DECISION_MARKET_DAY_MISMATCH")
            if domain == "issuer_lineage":
                _add_if(report.get("retrospective_retrieval") is not False,
                        issues, "RETROSPECTIVE_ISSUER_VINTAGE")
                for field in ("active_ticker_conflict_count",
                              "observed_tickers_unmatched_count",
                              "corporate_events_with_unknown_parent_count",
                              "corporate_events_with_missing_successor_count",
                              "cash_exit_events_without_verified_proceeds_count"):
                    _add_if(_nonnegative(report, field) > 0, issues,
                            f"UNRESOLVED_{field.upper()}")
            elif domain == "exchange_calendar":
                _add_if(report.get("calendar_retrospectively_retrieved") is not False,
                        issues, "RETROSPECTIVE_EXCHANGE_CALENDAR")
                _add_if(report.get("calendar_complete_claimed") is not True,
                        issues, "EXCHANGE_CALENDAR_NOT_COMPLETE")
                for field in ("reference_only_missing_market_periods",
                              "feed_only_unexpected_periods"):
                    _add_if(_nonnegative(report, field) > 0, issues,
                            f"UNRESOLVED_{field.upper()}")
            elif domain == "price_continuity":
                required_cadence = "daily" if market == "KR" else "weekly"
                _add_if(report.get("observation_cadence") != required_cadence,
                        issues, "PRICE_CADENCE_MISMATCH")
                for field in ("internal_gap_event_count",
                              "right_boundary_last_observations"):
                    _add_if(_nonnegative(report, field) > 0, issues,
                            f"UNRESOLVED_{field.upper()}")
            else:
                _add_if(report.get("synthetic_or_uncertified_input") is not False,
                        issues, "HISTORICAL_MEMBERSHIP_SOURCE_UNCERTIFIED")
                for field in ("member_without_price_count",
                              "price_without_member_count", "observed_exited_count"):
                    _add_if(_nonnegative(report, field) > 0, issues,
                            f"UNRESOLVED_{field.upper()}")
        issues = sorted(set(issues))
        items.append({
            "domain": domain, "present": True, "filename": filename,
            "sha256": sha256(blob).hexdigest(), "status": report["status"],
            "issues": issues,
        })
        blockers.extend(f"{domain}:{issue}" for issue in issues)
    blockers = sorted(set(blockers))
    diagnostics_complete = not blockers and all(r["present"] for r in items)
    return {
        "status": ("LOCAL_AUDIT_DIAGNOSTICS_COMPLETE_NOT_PIT_CERTIFIED"
                   if diagnostics_complete else "BLOCKED_MISSING_OR_UNRESOLVED_PIT_EVIDENCE"),
        "market": market, "decision_at": cutoff.isoformat(),
        "market_day": target_day, "required_domains": len(REPORTS),
        "present_domains": sum(r["present"] for r in items),
        "research_diagnostics_complete": diagnostics_complete,
        "blocker_count": len(blockers), "blockers": blockers,
        "evidence": items,
        "official_promotion_allowed": False,
        "official_leader_count": 0,
        "historical_pit_certified": False,
        "model_accuracy_certified": False,
        "warning": ("Completing local diagnostics NEVER authenticates publisher, "
                    "archive retrieval time, historic listed/delisted universe, "
                    "corporate action coverage, or future leader performance."),
    }
