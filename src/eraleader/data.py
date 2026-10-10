"""Local-only adapters. The legacy vault is opened strictly read-only."""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

LEGACY_DEFAULT = Path("/Volumes/T5DATA/CycleOS-Lab_BacktestEngine")
MARCAP_COLS = ["Code", "Name", "Date", "Market", "Open", "High", "Low", "Close", "Volume", "Amount", "Marcap"]
US_COLS = ["ts", "ticker", "open", "high", "low", "close", "volume"]

def read_market_bars(
    market: str, as_of: date, *, days: int = 550,
    legacy_root: Path = LEGACY_DEFAULT, tickers: list[str] | None = None
) -> tuple[pd.DataFrame, dict]:
    """Load existing cached prices; NEVER contacts an external API.

    KR is observed historical marcap daily universe; US is 2026-03 universe
    weekly cache and unsuitable for survivor-free historic validation.
    """
    if market not in ("KR", "US"):
        raise ValueError("market must be KR or US")
    if days < 30:
        raise ValueError("days must be >=30")
    start = as_of - timedelta(days=days)
    if market == "KR":
        chunks = []
        for year in range(start.year, as_of.year + 1):
            path = legacy_root / f"datasets/external_validation/marcap/data/marcap-{year}.parquet"
            if not path.is_file():
                raise FileNotFoundError(f"Missing local marcap year {year}: {path}")
            chunk = pd.read_parquet(path, columns=MARCAP_COLS, filters=[
                ("Date", ">=", pd.Timestamp(start)), ("Date", "<=", pd.Timestamp(as_of))])
            if tickers:
                chunk = chunk.loc[chunk.Code.isin([v.zfill(6) for v in tickers])]
            if not chunk.empty:
                chunks.append(chunk)
        if not chunks:
            raise ValueError("No local prices found in requested range")
        df = pd.concat(chunks, ignore_index=True).rename(columns={
            "Code": "security_id", "Name": "name", "Date": "session",
            "Market": "venue", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
            "Amount": "turnover", "Marcap": "market_cap"})
        df["session"] = pd.to_datetime(df["session"]).dt.normalize()
        df["security_id"] = df["security_id"].astype(str).str.zfill(6)
        quality = {"source":"FinanceData/marcap (local readonly)", "market":"KR",
                   "price_only":True, "price_adjustments_verified":False,
                   "historic_membership_verified":False,
                   "corporate_actions_verified":False, "financial_pit_verified":False,
                   "scope":"historical listed observations; not a certified survivor-free universe"}
    else:
        path = legacy_root / "datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing US weekly cache: {path}")
        df = pd.read_parquet(path, columns=US_COLS,
                             filters=[("ts",">=",pd.Timestamp(start)),
                                      ("ts","<=",pd.Timestamp(as_of))])
        if tickers:
            df = df.loc[df.ticker.isin(tickers)]
        if df.empty:
            raise ValueError("No US price records in local cache window")
        df = df.rename(columns={"ts":"session","ticker":"security_id"})
        df["session"] = pd.to_datetime(df["session"]).dt.normalize()
        df["name"] = df["security_id"]
        df["venue"] = "US_CURRENT_SP500_SAMPLE"
        df["turnover"] = df["close"] * df["volume"]
        df["market_cap"] = pd.NA
        quality = {"source":"yfinance S&P500 2026-03 survivor-affected weekly cache (local readonly)",
                   "market":"US","price_only":True,"historic_membership_verified":False,
                   "price_adjustments_verified":False,"corporate_actions_verified":False,
                   "financial_pit_verified":False,
                   "scope":"current constituents only; historical PIT/backtest not certified"}
    clean = validate_bars(df, as_of, quarantine=True)
    quality["excluded_anomalous_rows"] = clean.attrs.get("quarantined_rows", 0)
    quality["excluded_anomalies_sample"] = clean.attrs.get("quarantined_sample", [])
    quality["halted_observation_rows"] = int(clean["is_suspended"].sum())
    return clean, quality

def validate_bars(df: pd.DataFrame, as_of: date, *, quarantine: bool=False) -> pd.DataFrame:
    """Reject invalid rows instead of silently correcting financial inputs."""
    if df.empty:
        raise ValueError("Empty bar set")
    if df[["security_id","session"]].isna().any().any():
        raise ValueError("Missing security_id or timestamp")
    if (df["session"].dt.date > as_of).any():
        raise ValueError("Lookahead price bars detected")
    if df.duplicated(["security_id","session"]).any():
        raise ValueError("Duplicate security-date prices")
    numeric = ["open","high","low","close","volume"]
    df = df.copy()
    for col in numeric:
        df[col] = pd.to_numeric(df[col],errors="coerce")
    # marcap records zero OHLC with a nonzero carried close and volume=0
    # for suspended/non-trading securities. Retain the raw observation,
    # label it, and NEVER synthesize a fake tradable OHLC price.
    suspended = ((df["open"] == 0) & (df["high"] == 0) &
                 (df["low"] == 0) & (df["close"] > 0) & (df["volume"] == 0))
    df["is_suspended"] = suspended | (df["volume"] == 0)
    invalid = (df[numeric].isna().any(axis=1)
           | (df[["open","high","low","close"]] <= 0).any(axis=1)
           | (df["volume"]<0)
           | (df["high"] < df[["open","close","low"]].max(axis=1))
           | (df["low"] > df[["open","close","high"]].min(axis=1)))
    bad = invalid & ~suspended
    bad_count=int(bad.sum())
    bad_sample=(df.loc[bad,["security_id","session"]].head(5).assign(
        session=lambda z:z["session"].dt.strftime("%Y-%m-%d")
    ).to_dict("records") if bad_count else [])
    if bad_count and not quarantine:
        raise ValueError(f"Invalid non-suspension OHLCV rows: {bad_count}")
    if bad_count:
        df=df.loc[~bad].copy()
    ordered=df.sort_values(["security_id","session"]).reset_index(drop=True)
    ordered.attrs["quarantined_rows"]=bad_count
    ordered.attrs["quarantined_sample"]=bad_sample
    return ordered
