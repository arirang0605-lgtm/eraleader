"""Transparent price-led research screening; not a verified leader prediction."""
from __future__ import annotations
import hashlib
import json
import pandas as pd

MODEL_VERSION="local-price-screen-v0.1-EXPERIMENTAL"
def score_price_observations(bars: pd.DataFrame, market: str, as_of: str, limit: int=20) -> dict:
    """Ranks price strength. All missing industry/earnings values stay N/A.

    Absolutely does not label price-only observations as confirmed leaders.
    """
    if not len(bars):
        raise ValueError("Empty bars")
    if limit <= 0:
        raise ValueError("limit must be positive")
    data=bars.copy()
    data["session"]=pd.to_datetime(data["session"])
    cutoff=pd.Timestamp(as_of)
    if (data["session"] > cutoff).any():
        raise ValueError("LOOKAHEAD input")
    data=data.sort_values(["security_id","session"])
    max_date=data["session"].max()
    lag_3m,lag_6m,lag_12m = (13,26,52) if market=="US" else (60,130,250)
    g=data.groupby("security_id",sort=False)
    for lag,name in [(lag_3m,"ret_3m"),(lag_6m,"ret_6m"),(lag_12m,"ret_12m")]:
        data[name]=data["close"]/g["close"].shift(lag)-1
    latest=data.loc[data["session"]==max_date].copy()
    # Never select currently halted/no-trade securities or companies with
    # prolonged recent suspension. These are observations, not executions.
    data["is_suspended"] = data.get("is_suspended", False)
    suspended_recent=(data.loc[data["session"]>=max_date-pd.Timedelta(days=180)]
                      .groupby("security_id")["is_suspended"].any())
    risky_ids=set(suspended_recent.index[suspended_recent])
    excluded_halt=int(latest["security_id"].isin(risky_ids).sum())
    latest=latest.loc[~latest["security_id"].isin(risky_ids)].copy()
    latest=latest.loc[latest["ret_6m"].notna()].copy()
    if latest.empty:
        raise ValueError("Not enough local lookback bars to form a screening result")
    latest["pct_3m"]=latest["ret_3m"].rank(pct=True)
    latest["pct_6m"]=latest["ret_6m"].rank(pct=True)
    latest["pct_12m"]=latest["ret_12m"].rank(pct=True)
    # 12m unavailable in smaller demo windows: no invented score, but
    # still allow partial momentum score based on real 3m/6m results.
    latest["price_score_25"]=(25*(0.4*latest["pct_3m"]+0.6*latest["pct_6m"])).round(2)
    latest=latest.sort_values(["price_score_25","security_id"],ascending=[False,True]).head(limit)
    rows=[]
    for pos, row in enumerate(latest.itertuples(),1):
        def clean(num):
            return None if pd.isna(num) else round(float(num),6)
        rows.append({
            "rank":pos, "security_id":str(row.security_id),
            "name":str(row.name), "venue":str(row.venue),
            "observed_at":str(row.session.date()), "last_price":clean(row.close),
            "return_3m":clean(row.ret_3m),"return_6m":clean(row.ret_6m),
            "return_12m":clean(row.ret_12m),
            "price_strength_25":clean(row.price_score_25),
            "total_score_100":None,
            "industry_score":None,"fundamentals_score":None,
            "flow_score":None,
            "state":"WATCH",
            "reasons":["3·6개월 상대 모멘텀 관찰(가격 원자료 기반)"],
            "warnings":["재무/산업 PIT 미확보: 잠재·확정 대장주 판정 보류",
                        "과거 기업행동·상장폐지 완전성 미검증"]
        })
    return {
        "schema_version":"1.0", "model_version":MODEL_VERSION,
        "as_of_requested":as_of, "source_market":market,
        "market_last_observation":str(max_date.date()),
        "classification_quality":"PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
        "rows":rows,"shown":len(rows), "excluded_recent_suspensions":excluded_halt,
        "suspension_observations":int(data["is_suspended"].sum()),
        "scoring_policy":"3개월 RS 40% + 6개월 RS 60%, 가격 부분 점수 최대 25점; 임시 연구식",
        "note":"WATCH=가격 기반 관찰. POTENTIAL/CONFIRMED 대상이 아니며 투자 추천이 아닙니다.",
    }

def detect_watch_changes(previous: dict | None, current: dict, run_id: str) -> list[dict]:
    prev_ids={r["security_id"] for r in (previous or {}).get("rows",[])}
    events=[]
    for row in current["rows"]:
        sec=row["security_id"]
        if sec in prev_ids:
            continue
        # Only technical watch events, not promoted leader alerts.
        raw=f"{current['source_market']}|{sec}|NEW_TECHNICAL_WATCH|{current['market_last_observation']}|{MODEL_VERSION}"
        events.append({
            "event_id":hashlib.sha256(raw.encode()).hexdigest()[:24],
            "kind":"NEW_TECHNICAL_WATCH",
            "security_id":sec,"name":row["name"],
            "market":current["source_market"],
            "as_of":current["market_last_observation"],
            "run_id":run_id,
            "message":"연구용 가격 관찰 목록 신규 편입 — 대장주 후보 확정 아님",
        })
    return events

def run_id_for(market: str, as_of: str, rows: list[dict]) -> str:
    key=json.dumps({"market":market,"as_of":as_of,"rows":rows,"model":MODEL_VERSION},
                   ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:20]
