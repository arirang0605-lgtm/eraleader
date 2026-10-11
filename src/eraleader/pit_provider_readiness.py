"""2_2/2_5: inspect ACTUAL local price-cache vintages vs declared PIT inputs.

A KRX-style code or vendor ticker is NOT a legal permanent issuer identity.
All source/clock and official universe certifications remain false, even when
the optional user-provided SQLite ledger is internally hash-consistent.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .offline_pit import OfflineLedger
from .frozen_holdout import _stamp

STATUS = "BLOCKED_PIT_PROVIDER_INPUT_READINESS_RESEARCH_ONLY"
TZ = {"KR":ZoneInfo("Asia/Seoul"),"US":ZoneInfo("America/New_York")}
CACHE_PARTS = {
    "KR":("datasets","external_validation","marcap","data"),
    "US":("datasets","yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT","bars.parquet"),
}
COLUMNS = {"KR":("Date","Code"),"US":("ts","ticker")}
MAX_RECORDS = 5_000_000


def _hash_file(file: Path) -> str:
    digest=sha256()
    with file.open("rb") as source:
        for block in iter(lambda:source.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def _cache_status(root: Path, market: str, asof_day, max_age_days: int) -> tuple[dict,list[str]]:
    result = {
        "price_cache_last_market_day":None,
        "price_cache_age_calendar_days":None,
        "price_observed_symbol_count_last_session":None,
        "price_cache_file_basename":None,
        "price_cache_sha256":None,
        "price_cache_record_count":None,
        "price_observed_distinct_symbols_all_cached_dates":None,
        "price_breadth_reference_peak_symbols_trailing_30d":None,
        "last_broad_coverage_observation_day":None,
        "last_broad_coverage_observed_symbols":None,
        "price_last_day_coverage_fraction_vs_recent_peak":None,
        "price_symbols_not_permanent_issuer_ids":True,
        "official_listing_membership_covered":False,
    }
    base=root.joinpath(*CACHE_PARTS[market])
    if base.is_symlink() or root.is_symlink():
        raise ValueError("symlink market cache root is not trusted")
    if market=="KR":
        source_files=sorted(base.glob("marcap-????.parquet"))
        source=source_files[-1] if source_files else None
    else:
        source=base
    if source is None or not source.is_file():
        return result,["PRICE_CACHE_MISSING"]
    if source.is_symlink() or source.parent.is_symlink():
        raise ValueError("symlink market cache data is not trusted")
    date_column,code_column=COLUMNS[market]
    try:
        bars=pd.read_parquet(source,columns=[date_column,code_column])
    except (ValueError,KeyError,ImportError) as exc:
        raise ValueError("Invalid required KR/US cache price-symbol columns") from exc
    if not 0<len(bars)<=MAX_RECORDS:
        raise ValueError("Empty/oversized observed-symbol price cache")
    if bars[date_column].isna().any() or bars[code_column].isna().any():
        raise ValueError("Missing price session or symbol code is not acceptable")
    dates=pd.to_datetime(bars[date_column],errors="coerce")
    if dates.isna().any():
        raise ValueError("Unparseable price cache session timestamps")
    latest=dates.max().date()
    if latest>asof_day:
        raise ValueError("Future price cache session cannot enter PIT readiness")
    subset=bars.loc[dates.dt.date==latest,code_column]
    symbols=subset.astype(str)
    if (symbols.empty or symbols.str.strip().eq("").any() or
            symbols.duplicated().any()):
        raise ValueError("Duplicate or missing symbols on latest observed session")
    # Some US feeds combine a broad weekly cross-section with a few
    # off-cycle symbols on Tuesday/Thursday. The file's absolute maximum ts
    # may represent ONE ticker, not the latest complete market universe.
    # Compare the latest day against the highest locally observed breadth
    # in the last 30 calendar days; NEVER call that an official listing list.
    recent_cutoff=latest-timedelta(days=30)
    recent_mask=dates.dt.date>=recent_cutoff
    symbol_breadth=bars.loc[recent_mask].groupby(
        dates.loc[recent_mask].dt.date
    )[code_column].nunique()
    recent_peak=int(symbol_breadth.max())
    min_broad_coverage=0.8*recent_peak
    broad_dates=symbol_breadth.loc[symbol_breadth>=min_broad_coverage]
    last_broad_day=max(broad_dates.index)
    last_broad_count=int(broad_dates.loc[last_broad_day])
    fraction=round(len(symbols)/recent_peak,6)
    sparse=recent_peak>=20 and fraction<0.8
    days=(asof_day-latest).days
    result.update({
        "price_cache_last_market_day":latest.isoformat(),
        "price_cache_age_calendar_days":days,
        "price_observed_symbol_count_last_session":len(symbols),
        "price_cache_file_basename":source.name,
        "price_cache_sha256":_hash_file(source),
        "price_cache_record_count":len(bars),
        "price_observed_distinct_symbols_all_cached_dates":
            int(bars[code_column].nunique()),
        "price_breadth_reference_peak_symbols_trailing_30d":recent_peak,
        "last_broad_coverage_observation_day":last_broad_day.isoformat(),
        "last_broad_coverage_observed_symbols":last_broad_count,
        "price_last_day_coverage_fraction_vs_recent_peak":fraction,
    })
    issues=[]
    if days>max_age_days:
        issues.append("PRICE_CACHE_STALE")
    if sparse:
        issues.append("PRICE_FEED_LATEST_DAY_SPARSE")
    return result,issues


def _ledger_status(source: Path | None, market: str, cutoff: datetime) -> tuple[dict,list[str]]:
    default = {
        "source_ledger_present":False,
        "source_provenances":[],
        "known_active_membership_count":0,
        "known_fundamental_record_count":0,
        "known_industry_record_count":0,
        "known_corporate_action_count":0,
        "known_delisted_security_count":0,
        "historical_universe_complete":False,
        "permanent_issuer_identity_attested":False,
        "fundamental_publication_time_attested":False,
    }
    if source is None:
        return default,["PIT_LEDGER_MISSING"]
    source=Path(source)
    pit=OfflineLedger.open_readonly(source)
    try:
        snapshot=pit.snapshot(cutoff.isoformat(),market=market)
    finally:
        pit.close()
    prov=snapshot["quality"]["provenances"]
    members=len(snapshot["members"])
    facts=len(snapshot["fundamentals"])
    industry=len(snapshot["industry"])
    actions=len(snapshot["actions"])
    out={**default,
         "source_ledger_present":True,
         "source_provenances":prov,
         "known_active_membership_count":members,
         "known_fundamental_record_count":facts,
         "known_industry_record_count":industry,
         "known_corporate_action_count":actions,
         "known_delisted_security_count":len(snapshot["exit_security_ids"]),
    }
    blockers=[]
    if not members:blockers.append("PIT_MEMBERSHIP_NOT_PRESENT")
    if not facts:blockers.append("PIT_FUNDAMENTALS_NOT_PRESENT")
    if not industry:blockers.append("PIT_INDUSTRY_NOT_PRESENT")
    if not actions:blockers.append("CORPORATE_ACTION_COMPLETENESS_NOT_PROVEN")
    if any(p!="external_public_file" for p in prov):
        blockers.append("SELF_DECLARED_OR_SYNTHETIC_PIT_SOURCE")
    if not prov:blockers.append("KNOWN_PIT_SOURCE_PROVENANCE_NOT_PRESENT")
    return out,blockers


def audit_pit_provider_readiness(
    cache_root: Path, *, evaluated_at: str,
    kr_ledger: Path | None = None,
    us_ledger: Path | None = None,
    max_price_age_days: int = 7,
    clock: datetime | None = None,
) -> dict:
    """Read-only local source inventory for BOTH markets, never PIT certification."""
    if type(max_price_age_days) is not int or not 0<=max_price_age_days<=365:
        raise ValueError("Invalid maximum market cache age days")
    moment=_stamp(evaluated_at)
    now=clock if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Readiness clock requires timezone")
    if moment>now.astimezone(timezone.utc):
        raise ValueError("Future PIT provider readiness as-of is forbidden")
    root=Path(cache_root)
    if root.is_symlink():
        raise ValueError("symlink price cache root forbidden")
    markets={}
    reasons=[]
    for market in ("KR","US"):
        local_day=moment.astimezone(TZ[market]).date()
        cached,cache_issues=_cache_status(root,market,local_day,max_price_age_days)
        stored,source_issues=_ledger_status(
            kr_ledger if market=="KR" else us_ledger,market,moment)
        issues=sorted(set(cache_issues+source_issues+
            ["INDEPENDENT_SOURCE_AUTHENTICITY_MISSING",
             "HISTORIC_LISTING_AND_DELISTING_COVERAGE_UNPROVEN",
             "CORPORATE_ACTION_AND_CASH_SETTLEMENT_UNPROVEN"]))
        reasons.extend(f"{market}:{code}" for code in issues)
        markets[market]={
            "as_of_market_day":local_day.isoformat(),
            **cached,**stored,
            "blockers":issues,
        }
    return {
        "status":STATUS,
        "evaluated_at_utc":moment.isoformat(),
        "max_price_age_calendar_days":max_price_age_days,
        "markets":markets,
        "blocker_count":len(reasons),
        "blockers":sorted(reasons),
        "market_raw_sources_are_not_official_membership":True,
        "independent_pit_verified":False,
        "issuer_identity_independently_verified":False,
        "price_asof_availability_independently_attested":False,
        "corporate_action_completeness_certified":False,
        "delisting_cash_settlement_certified":False,
        "future_leader_accuracy_certified":False,
        "actual_future_precision":None,
        "official_leader_promotions":0,
        "external_api_calls":0,
        "message_sent_count":0,
        "warning":(
            "Real locally observed prices and self-imported PIT records do not "
            "certify official historical listing membership, issuer identity, "
            "corporate actions, cash settlement, original publisher timestamps, "
            "market completeness or true future leader success."
        ),
    }
