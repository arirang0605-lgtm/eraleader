"""Local, explicitly non-certified split/dividend return reconstruction.

Trading-session bars and separate known/effective corporate-action dates are
required. Never substitutes missing delisting proceeds, converts suspected
suspensions to zero returns, or claims the source is complete.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from math import isfinite
from typing import Any

SUPPORTED = frozenset({"split", "dividend"})
UNSUPPORTED = frozenset({"delist", "merger", "ticker_change", "rights", "spin_off"})

def _date(text: str) -> date:
    return date.fromisoformat(text)

def _time(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return dt.astimezone(timezone.utc)

def _number(value: Any, *, positive: bool) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a market amount")
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Non-numeric market amount") from exc
    if not isfinite(num) or (num <= 0 if positive else num < 0):
        raise ValueError("Invalid positive/nonnegative market amount")
    return num

def reconstruct_total_return(
    bars: list[dict], actions: list[dict], *,
    decision_at: str, evaluated_at: str, security_id: str,
    market: str, price_basis: str, corporate_actions_complete: bool = False,
    price_sessions_complete: bool = False,
) -> dict:
    """Daily total return across split and cash dividend actions.

    bar: {security_id, session, close, available_at, tradable}. action: {security_id,
    action_id, action_type, effective_on, known_at, ratio / cash_amount}.
    Split ratio is new shares / old shares; dividend is cash per share
    *after* any simultaneous split. Session factor is
    (new close + cash per new share) * new shares / prior close.

    This can reconstruct one historical observed security path, but cannot
    prove that all historic corporate actions or delistings were captured.
    """
    signal_at, eval_at = _time(decision_at), _time(evaluated_at)
    # Use trading dates in the caller's timezone, never the converted UTC day.
    signal_day = datetime.fromisoformat(decision_at.replace("Z", "+00:00")).date()
    eval_day = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00")).date()
    if signal_at > eval_at:
        raise ValueError("Evaluation must not precede signal")
    if market not in ("KR", "US"):
        raise ValueError("Unknown market")
    if price_basis != "raw_unadjusted":
        raise ValueError("Only raw_unadjusted close is allowed; adjusted data double-counts actions")
    if not isinstance(bars, list) or len(bars) < 2:
        raise ValueError("Need at least two observed sessions")
    seen_days: set[date] = set()
    ordered = []
    for row in bars:
        if row.get("security_id") != security_id:
            raise ValueError("Mixed security IDs in prices")
        day = _date(row["session"])
        if day in seen_days:
            raise ValueError("Duplicate sessions")
        seen_days.add(day)
        if row.get("tradable") is not True:
            raise ValueError("Halted, missing or unknown tradability; outcome censored")
        if not row.get("available_at"):
            raise ValueError("Missing price available_at; cannot verify PIT close")
        available = _time(row["available_at"])
        # The signal must not access a close published after decision_at.
        # Every subsequent bar must also be available by evaluation_at.
        if available > eval_at:
            raise ValueError("Future price availability after evaluation cutoff")
        if day == signal_day and available > signal_at:
            raise ValueError("Decision used a price not yet available at signal time")
        ordered.append((day, _number(row["close"], positive=True)))
    if ordered != sorted(ordered):
        raise ValueError("Price sessions must be chronologically ordered")
    if ordered[0][0] >= ordered[-1][0]:
        raise ValueError("No time interval")
    if ordered[-1][0] > eval_day or ordered[0][0] > signal_day:
        raise ValueError("Future price evidence in evaluation")
    if ordered[0][0] < signal_day:
        raise ValueError("Start bar must be the decision-date bar or later")
    if not isinstance(actions, list):
        raise ValueError("Actions list required")
    dedup: set[str] = set()
    event_dates: dict[date, dict] = {}
    for event in actions:
        if event.get("security_id") != security_id:
            raise ValueError("Mixed security IDs in corporate actions")
        identity = event.get("action_id")
        if not identity or identity in dedup:
            raise ValueError("Missing or duplicate corporate action ID")
        dedup.add(identity)
        effective = _date(event["effective_on"])
        known = _time(event["known_at"])
        if known > eval_at:
            # A correction received only after evaluation cannot be treated
            # as known at the evaluation cutoff.
            raise ValueError("Future-known corporate action in evaluation")
        typ = event.get("action_type")
        if typ not in SUPPORTED:
            raise ValueError(f"Unsupported corporate action {typ}; cannot infer payout")
        if effective <= ordered[0][0] or effective > ordered[-1][0]:
            # Source may supply many actions outside the requested interval.
            # Ignore only after checking provenance/time correctness.
            continue
        if effective not in seen_days:
            raise ValueError("Action effective date absent from observed trading bars")
        daily = event_dates.setdefault(effective, {"ratio": 1.0, "dividend": 0.0,
                                                    "types": set()})
        if typ in daily["types"]:
            raise ValueError("Multiple same-type actions on same day require normalization")
        daily["types"].add(typ)
        if typ == "split":
            daily["ratio"] = _number(event.get("ratio"), positive=True)
        else:
            daily["dividend"] = _number(event.get("cash_amount"), positive=False)
    factors = []
    growth = 1.0
    for prev, curr in zip(ordered, ordered[1:]):
        day, price = curr
        prev_close = prev[1]
        action = event_dates.get(day, {"ratio": 1.0, "dividend": 0.0})
        period_return = (price + action["dividend"]) * action["ratio"] / prev_close - 1
        if not isfinite(period_return) or period_return < -1:
            raise ValueError("Impossible dividend/split-adjusted interval return")
        growth *= 1 + period_return
        factors.append({"session": day.isoformat(), "period_return": round(period_return, 12),
                        "corporate_action_on_session": day in event_dates})
    # Self-reported coverage is not independent validation. Never upgrade
    # the historical series to PIT certified on these two flags alone.
    scope_complete = corporate_actions_complete and price_sessions_complete
    return {
        "security_id": security_id, "market": market,
        "start_session": ordered[0][0].isoformat(),
        "last_session": ordered[-1][0].isoformat(),
        "session_count": len(ordered),
        "actions_applied": len(event_dates),
        "total_return": round(growth - 1, 12),
        "factor_path": factors,
        "status": "LOCAL_ADJUSTMENT_RESEARCH_ONLY",
        "coverage_attested_by_input": scope_complete,
        "pit_certified": False,
        "warnings": [
            "Corporate-action coverage has not been independently audited",
            "Delisting/merger proceeds and calendar gaps cannot be inferred from available bars",
            "Historical universe survivorship and executable prices not independently certified",
        ],
    }
