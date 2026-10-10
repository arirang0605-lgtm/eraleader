"""As-of sector peer percentiles, descriptive research only (3_5)."""
from __future__ import annotations
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
from .offline_features import MAX_RESEARCH_FISCAL_AGE_DAYS
from .offline_pit import iso_time

FACTORS = ("revenue_yoy", "operating_income_yoy")
ZONES = {"KR": "Asia/Seoul", "US": "America/New_York"}


def normalize_growth_peers(snapshot: dict, *, min_peers: int = 3) -> dict:
    """Compare only eligible companies in the same historical industry group."""
    if type(min_peers) is not int or not 3 <= min_peers <= 100:
        raise ValueError("min_peers must be 3..100")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "offline_research_v1":
        raise ValueError("Expected offline_research_v1")
    market = snapshot.get("market")
    if market not in ZONES:
        raise ValueError("Invalid market")
    cutoff = datetime.fromisoformat(iso_time(snapshot.get("as_of")))
    day = cutoff.astimezone(ZoneInfo(ZONES[market])).date()
    companies = snapshot.get("companies")
    if not isinstance(companies, list) or snapshot.get("company_count") != len(companies):
        raise ValueError("Incomplete as-of company count")
    seen = set()
    results = []
    groups = {}
    for row in companies:
        if not isinstance(row, dict):
            raise ValueError("Invalid company row")
        sid, industry = row.get("security_id"), row.get("industry_id")
        if (not isinstance(sid, str) or not sid.strip() or sid in seen
                or not isinstance(industry, str) or not industry.strip()
                or row.get("market") != market):
            raise ValueError("Duplicate identity or mixed-market industry")
        seen.add(sid)
        if type(row.get("screen_evaluated")) is not bool:
            raise ValueError("Missing as-of quality gate")
        ages = row.get("financial_period_age_days")
        if not isinstance(ages, dict):
            raise ValueError("Missing source period ages")
        period = row.get("latest_revenue_period")
        if period is not None:
            fiscal_day = date.fromisoformat(period)
            if fiscal_day > day or ages.get("revenue") != (day - fiscal_day).days:
                raise ValueError("Future or inconsistent fiscal period age")
        reasons = []
        if not row["screen_evaluated"] or row.get("fundamental_periods_aligned") is not True:
            reasons.append("PIT_SOURCE_SCREEN_DEFERRED")
        for field in ("revenue", "operating_income", "industry_revenue"):
            age = ages.get(field)
            if type(age) is not int or age < 0 or age > MAX_RESEARCH_FISCAL_AGE_DAYS:
                reasons.append("MISSING_OR_STALE_" + field.upper())
        if period is None:
            reasons.append("MISSING_REVENUE_PERIOD")
        for field in FACTORS:
            v = row.get(field)
            if type(v) not in (int, float) or not math.isfinite(v):
                reasons.append("MISSING_OR_INVALID_" + field.upper())
        result = {"security_id": sid, "industry_id": industry,
                  "peer_count": 0, "percentiles": None, "mean_peer_percentile": None,
                  "status": "DEFERRED" if reasons else "ELIGIBLE",
                  "reasons": sorted(set(reasons))}
        results.append(result)
        if not reasons:
            groups.setdefault(industry, []).append((row, result))
    for industry, peers in groups.items():
        count = len(peers)
        for row, item in peers:
            item["peer_count"] = count
            if count < min_peers:
                item["status"] = "DEFERRED"
                item["reasons"] = ["INSUFFICIENT_SAME_INDUSTRY_ASOF_PEERS"]
                continue
            scaled = {}
            for field in FACTORS:
                values = [p[0][field] for p in peers]
                value = row[field]
                below = sum(x < value for x in values)
                tied = sum(x == value for x in values)
                scaled[field] = round(100 * (below + (tied - 1) / 2) / (count - 1), 6)
            item["percentiles"] = scaled
            item["mean_peer_percentile"] = round(sum(scaled.values()) / len(FACTORS), 6)
            item["status"] = "RESEARCH_NORMALIZED"
    results.sort(key=lambda x: (x["industry_id"], x["security_id"]))
    qualified = sum(x["status"] == "RESEARCH_NORMALIZED" for x in results)
    return {"schema_version": "eraleader.peer_normalization_research.v1",
            "market": market, "as_of": cutoff.isoformat(), "min_peers": min_peers,
            "source_company_count": len(results), "normalized_count": qualified,
            "deferred_count": len(results) - qualified, "companies": results,
            "independent_historical_pit_certified": False,
            "future_leader_skill_certified": False, "official_leader_promotions": 0,
            "warning": "Relative research percentiles only: universe/source PIT and live outcomes unverified"}


def normalize_peer_file(source: Path, target: Path, *, min_peers: int = 3) -> dict:
    source, target = Path(source), Path(target)
    if source.is_symlink() or not source.is_file() or target.is_symlink():
        raise ValueError("Missing or symlinked source/target")
    if source.resolve() == target.resolve():
        raise ValueError("Cannot overwrite original feature evidence")
    raw = source.read_bytes()
    report = normalize_growth_peers(json.loads(raw), min_peers=min_peers)
    report["source_sha256"] = sha256(raw).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        fh.write("\n")
    return {"status": "ASOF_PEER_RESEARCH_ONLY", "path": str(target),
            "normalized": report["normalized_count"],
            "deferred": report["deferred_count"], "source_sha256": report["source_sha256"],
            "future_leader_skill_certified": False}
