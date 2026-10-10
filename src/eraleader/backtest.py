"""Conservative diagnostic of delayed momentum selections.

This is NOT a PIT-certified leader backtest. Current US universe, historic KR
corporate actions and fundamentals require further independent verification.
"""
from __future__ import annotations
import pandas as pd

def delayed_momentum_baseline(bars: pd.DataFrame, *, lookback: int = 26,
                              top_n: int = 3, rebalance: int = 4,
                              weekly: bool = True) -> dict:
    if lookback < 2 or top_n < 1 or rebalance < 1:
        raise ValueError("Invalid strategy parameter")
    df=bars.sort_values(["security_id","session"]).copy()
    df["session"]=pd.to_datetime(df["session"])
    # Non-trading/halted price carries must not be treated as executable fills.
    if "is_suspended" in df.columns:
        df=df.loc[~df["is_suspended"]].copy()
    if not weekly:
        # Vectorized weekly grouping: no per-row Python callbacks on 1M+ bars.
        df["week"]=df["session"].dt.to_period("W-SUN").dt.end_time.dt.normalize()
        df=df.sort_values("session").groupby(["security_id","week"],as_index=False).tail(1)
        df["session"]=df["week"]
    px=df.pivot(index="session",columns="security_id",values="close").sort_index()
    daily=px.pct_change(fill_method=None)
    # Decision at end of time t, returns only from (t,t+1].
    momentum=px/px.shift(lookback)-1
    nav=1.0;bench=1.0;turnover=0;observations=0
    trades=[]
    n=len(px)
    selection=None
    for i in range(lookback,n-1):
        if (i-lookback)%rebalance==0:
            avail=momentum.iloc[i].dropna()
            selection=avail.nlargest(top_n).index.tolist()
            turnover+=int(bool(trades))
        if not selection:
            continue
        # Survivorship and liquidity checks are NOT PIT-certified.
        r=daily.iloc[i+1][selection].dropna()
        if len(r)!=len(selection):
            continue
        market_return=daily.iloc[i+1].dropna()
        if market_return.empty:
            continue
        nav*=1+float(r.mean())
        bench*=1+float(market_return.mean())
        observations+=1
        trades.append({"as_of":str(px.index[i].date()),
                       "next_date":str(px.index[i+1].date()),
                       "selected":selection, "next_period_return":float(r.mean())})
    if not trades:
        raise ValueError("No complete returns to evaluate")
    return {
      "status":"RESEARCH_ONLY_NOT_PIT_CERTIFIED",
      "selection_time_rule":"signal at t; portfolio returns from t to t+1 (not at signal close)",
      "price_adjustments_verified":False,
      "historic_universe_verified":False,
      "observations":observations,"first_signal":trades[0]["as_of"],
      "last_signal":trades[-1]["as_of"],
      "gross_growth_factor":round(nav,6),"benchmark_growth_factor":round(bench,6),
      "excess_growth_factor":round(nav/bench,6),
      "rebalance_events":turnover,
      "costs_included":False,
      "lookback_weeks":lookback,"top_n":top_n,"rebalance_weeks":rebalance,
      "warning":"연구용 모멘텀 baseline만 계산. PIT 종목군/기업행동/거래비용 검증 전 수익성 판단 금지",
    }
