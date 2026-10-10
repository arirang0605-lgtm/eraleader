"""Read-only cache witness for six-month rank price inputs (2_5 / 3_4).

Selected price-only screen rows are recomputed from the existing KR/US cached
OHLCV bars. This does NOT verify provider authenticity, adjustments, listed
universe completeness, trade execution prices, or leader prediction skill.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import json
import math

from .data import read_market_bars

LAGS = {"KR": {"3m": 60, "6m": 130, "12m": 250},
        "US": {"3m": 13, "6m": 26, "12m": 52}}
RETURN_FIELDS = {"3m": "return_3m", "6m": "return_6m", "12m": "return_12m"}


def _num(value):
    return type(value) in (int, float) and math.isfinite(value)


def recheck_price_cache(
    price: dict, *, legacy_root: Path, days: int = 550,
) -> dict:
    """Independently recompute displayed returns from the existing local cache.

    This is *local content consistency*, never third-party PIT authentication.
    All price observation ids in the screen must have a complete as-of 6-month
    raw close history and no recent suspended observations. Missing = BLOCKED.
    """
    if not isinstance(price, dict) or price.get("source_market") not in LAGS:
        raise ValueError("KR/US source market required for cached-price recheck")
    market = price["source_market"]
    if type(days) is not int or not 200 <= days <= 1095:
        raise ValueError("Cache lookback days must be 200..1095")
    rows = price.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError("Price witness requires 1..1000 selected price rows")
    tickers = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("security_id"), str):
            raise ValueError("Invalid selected price screen identity")
        ticker = row["security_id"]
        if not ticker or ticker in tickers:
            raise ValueError("Duplicate or empty selected price ticker")
        tickers.append(ticker)
    asof = date.fromisoformat(price["as_of_requested"])
    expected_last = date.fromisoformat(price["market_last_observation"])
    if expected_last > asof:
        raise ValueError("Price screen has a future observation")
    root = Path(legacy_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Original local market cache directory missing or symlinked")
    bars, quality = read_market_bars(market, asof, days=days,
                                     legacy_root=root, tickers=tickers)
    # Fallback to comparing original observations, NOT global top-K ranks.
    # We cannot infer full-market ranking/survivor-free membership from a
    # selected subset of existing price cache bars.
    basis = []
    for item in rows:
        sid = item["security_id"]
        history = bars.loc[bars["security_id"] == sid].sort_values("session")
        lag6 = LAGS[market]["6m"]
        if len(history) < lag6 + 1:
            raise ValueError(f"{sid}: missing local six-month close history")
        last = history.iloc[-1]
        observed = last["session"].date()
        if observed != expected_last or item.get("observed_at") != observed.isoformat():
            raise ValueError(f"{sid}: latest cached trading session differs from screen")
        recent = history.loc[
            history["session"] >= last["session"] - timedelta(days=180)]
        if bool(recent["is_suspended"].any()):
            raise ValueError(f"{sid}: recent market halt cannot enter price ranking")
        close = float(last["close"])
        if not _num(item.get("last_price")) or abs(float(item["last_price"]) - close) > 0.0000005:
            raise ValueError(f"{sid}: displayed last close differs from source cache")
        witness = {"security_id": sid, "observed_at": observed.isoformat(),
                   "last_close": close}
        for horizon in ("3m", "6m", "12m"):
            lag = LAGS[market][horizon]
            field = RETURN_FIELDS[horizon]
            claimed = item.get(field)
            if len(history) < lag + 1:
                if claimed is not None:
                    raise ValueError(f"{sid}: {field} claimed without original lookback")
                continue
            former = float(history.iloc[-1-lag]["close"])
            if not _num(former) or former <= 0:
                raise ValueError(f"{sid}: invalid original close lookback")
            actual = round(close / former - 1, 6)
            if not _num(claimed) or abs(actual-float(claimed)) > 0.0000005:
                raise ValueError(f"{sid}: {field} differs from original local close series")
            witness[field] = actual
        basis.append(witness)
    canonical = json.dumps(basis, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {
        "status": "LOCAL_SELECTED_PRICE_RETURNS_RECOMPUTED_NOT_PIT_CERTIFIED",
        "market":market,
        "as_of":asof.isoformat(),
        "original_cache_source":quality["source"],
        "rechecked_selected_price_count":len(basis),
        "original_selected_price_returns_sha256":sha256(canonical.encode()).hexdigest(),
        "source_price_adjustments_independently_verified":False,
        "official_delisted_universe_verified":False,
        "provider_source_independently_authenticated":False,
        "future_leader_skill_certified":False,
    }
