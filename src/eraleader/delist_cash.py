"""Offline cash-delisting payoff calculation; never infer delisting proceeds.

Only simple *cash-per-final-share* exits are supported, conditional on an
explicit post-payment source record. Stock mergers, spinoffs, rights and unknown
zero-value bankruptcy consideration are NEVER implicitly priced.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from .corporate_returns import reconstruct_total_return

CURRENCY = {"KR": "KRW", "US": "USD"}
MARKET_ZONE = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
ALLOWED_PROVENANCE = {"synthetic_fixture", "external_public_file", "user_supplied"}


def _time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timezone-aware settlement timestamp required")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid settlement timestamp") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Timezone-aware settlement timestamp required")
    return t.astimezone(timezone.utc)


def _price(value: Any) -> float:
    if isinstance(value,bool):
        raise ValueError("Invalid cash consideration")
    try:
        v=float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid cash consideration") from exc
    if not isfinite(v) or v<=0:
        raise ValueError("Cash consideration must be positive and finite")
    return v


def reconstruct_cash_delisting(
    bars: list[dict], actions: list[dict], settlement: dict | None, *,
    security_id: str, market: str, decision_at: str, evaluated_at: str,
    price_basis: str = "raw_unadjusted",
) -> dict:
    """Research-only reinvested-dividend terminal cash-exit return.

    This returns a payoff only when a cash-payment confirmation and its
    local publication timestamp are both available before evaluation.
    It NEVER certifies source authenticity or corporate-action completeness.
    """
    if market not in CURRENCY:
        raise ValueError("Market must be KR/US")
    if not isinstance(security_id,str) or not security_id:
        raise ValueError("Missing security ID")
    decision,until=_time(decision_at),_time(evaluated_at)
    if until<decision:
        raise ValueError("Evaluation cutoff precedes decision")
    if price_basis!="raw_unadjusted":
        raise ValueError("Raw unadjusted price required to avoid double counting")
    if not isinstance(bars,list) or len(bars)<2 or not isinstance(actions,list):
        raise ValueError("Need observed raw bars and separate corporate actions")
    if not isinstance(settlement,dict):
        return {
            "status":"CENSORED_MISSING_CASH_SETTLEMENT",
            "security_id":security_id,"market":market,
            "cash_exit_total_return":None,"pit_certified":False,
            "settlement_source_independently_verified":False,
            "warning":"Missing cash exit terms or payment confirmation; no assumed payoff."
        }
    for key in ("security_id","source_id","event_id","action_type",
                "last_trading_on","effective_on","currency","provenance",
                "announced_at","paid_at","available_at"):
        if not isinstance(settlement.get(key),str) or not settlement[key].strip():
            raise ValueError(f"Missing settlement field {key}")
    if settlement["security_id"]!=security_id:
        raise ValueError("Settlement permanent security identity mismatch")
    if settlement["action_type"]!="cash_delist":
        raise ValueError("Unsupported noncash/merger delisting consideration")
    if settlement["provenance"] not in ALLOWED_PROVENANCE:
        raise ValueError("Unsupported settlement provenance")
    if settlement["currency"]!=CURRENCY[market]:
        raise ValueError("Cash consideration currency mismatch")
    if type(settlement.get("cash_payment_confirmed")) is not bool:
        raise ValueError("Explicit cash_payment_confirmed boolean required")
    cash=_price(settlement.get("cash_per_share"))
    last_trade=date.fromisoformat(settlement["last_trading_on"])
    effective=date.fromisoformat(settlement["effective_on"])
    if not last_trade<=effective:
        raise ValueError("Delisting effective date precedes last trade")
    if bars[-1].get("session")!=last_trade.isoformat():
        raise ValueError("Last observed tradable session differs from settlement terms")
    announcement=_time(settlement["announced_at"])
    paid=_time(settlement["paid_at"])
    known=_time(settlement["available_at"])
    local_zone=MARKET_ZONE[market]
    if paid.astimezone(local_zone).date()<effective or announcement>paid or known<paid:
        raise ValueError("Inconsistent payment/publication chronology")
    if not settlement["cash_payment_confirmed"] or paid>until or known>until:
        return {
            "status":"CENSORED_CASH_PAYMENT_NOT_KNOWN_BY_EVALUATION",
            "security_id":security_id,"market":market,
            "cash_exit_total_return":None,"pit_certified":False,
            "settlement_source_independently_verified":False,
            "warning":"Cash payment/availability not independently observed by cutoff."
        }
    # Force an error if extra unsupported exit actions appear in the action
    # stream. Never treat liquidation as a supported split/dividend adjustment.
    if any(x.get("action_type") not in ("split","dividend") for x in actions):
        raise ValueError("Unsupported corporate action in raw-return path")
    if any(date.fromisoformat(x["effective_on"])>last_trade for x in actions):
        raise ValueError("Corporate action after last tradable session requires separate model")
    standard=reconstruct_total_return(
        bars,actions,security_id=security_id,market=market,
        decision_at=decision_at,evaluated_at=evaluated_at,
        price_basis=price_basis)
    final_close=_price(bars[-1].get("close"))
    # Earlier cash distributions are assumed reinvested per the existing
    # return engine's per-interval factor, NOT held as separate bank cash.
    factor=(1+standard["total_return"])*(cash/final_close)
    if not isfinite(factor) or factor<0:
        raise ValueError("Invalid cash-exit growth factor")
    return {
        "status":"LOCAL_CASH_DELISTING_RESEARCH_ONLY",
        "security_id":security_id,"market":market,
        "start_session":standard["start_session"],
        "last_trading_session":last_trade.isoformat(),
        "exit_effective_on":effective.isoformat(),
        "cash_paid_at_claimed":paid.isoformat(),
        "settlement_known_at_claimed":known.isoformat(),
        "cash_per_final_share":cash,
        "currency":settlement["currency"],
        "raw_last_tradable_close":final_close,
        "return_to_last_tradable_close":standard["total_return"],
        "cash_exit_total_return":round(factor-1,12),
        "settlement_source_id_claimed":settlement["source_id"],
        "cash_payment_attested_by_input":True,
        "settlement_source_independently_verified":False,
        "historic_universe_pit_certified":False,
        "corporate_actions_complete_verified":False,
        "pit_certified":False,
        "warnings":[
            "Cash-payment confirmation is user/source asserted, not independently attested",
            "Dividend factor assumes reinvestment; taxes, fees and FX excluded",
            "Only explicit positive cash consideration per final share supported",
            "Delisted universe/earlier corporate-action coverage not independently certified",
        ],
    }
