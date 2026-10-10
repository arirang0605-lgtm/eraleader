"""Cross-check raw-price corporate-action returns against a second local index.

Research-only: distinct declared source IDs do not establish actual vendor
independence, historical completeness, executable prices or PIT certification.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite

from .corporate_returns import MARKET_ZONE, reconstruct_total_return

def _time(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Reference availability timestamp requires timezone")
    return stamp.astimezone(timezone.utc)

def _positive_number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Invalid reference index value")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid reference index value") from exc
    if not isfinite(number) or number <= 0:
        raise ValueError("Invalid reference index value")
    return number

def compare_total_return_indexes(
    bars: list[dict], actions: list[dict], reference: dict, *,
    decision_at: str, evaluated_at: str, security_id: str,
    market: str, raw_source_id: str, tolerance_bps: float = 5.0,
) -> dict:
    if not isinstance(raw_source_id,str) or not raw_source_id.strip():
        raise ValueError("Raw price source ID required")
    if not isinstance(reference, dict):
        raise ValueError("Reference source contract required")
    ref_source = reference.get("source_id")
    if not isinstance(ref_source,str) or not ref_source.strip() or ref_source==raw_source_id:
        raise ValueError("Reference source must declare a distinct identity")
    if reference.get("basis")!="total_return_reinvested_index":
        raise ValueError("Reference must explicitly use total_return_reinvested_index basis")
    if isinstance(tolerance_bps,bool) or not isinstance(tolerance_bps,(int,float)) or (
        not isfinite(tolerance_bps) or not 0<=tolerance_bps<=1000
    ):
        raise ValueError("Invalid tolerance basis points")
    calculated=reconstruct_total_return(
        bars,actions,decision_at=decision_at,evaluated_at=evaluated_at,
        security_id=security_id,market=market,
        price_basis="raw_unadjusted")
    observed_sessions=[row["session"] for row in bars]
    imported=reference.get("bars")
    if not isinstance(imported,list) or len(imported)!=len(observed_sessions):
        raise ValueError("Reference session coverage differs from raw bars")
    limit=_time(evaluated_at)
    decision=_time(decision_at)
    reference_values=[]
    for i, (source_session, row) in enumerate(zip(observed_sessions,imported)):
        if not isinstance(row,dict) or row.get("session")!=source_session:
            raise ValueError("Reference session mismatch or reordering")
        session=date.fromisoformat(row["session"])
        available=_time(row["available_at"])
        if available>limit or (i==0 and available>decision):
            raise ValueError("Reference index was not available by decision/evaluation")
        # A request's UTC/offset date is not the exchange session date.
        # Resolve in the market timezone (including US DST) just like raw bars.
        if available.astimezone(MARKET_ZONE[market]).date() < session:
            raise ValueError("Reference index reported before its observed session")
        reference_values.append(_positive_number(row.get("index")))
    discrepancies=[]
    for (entry,previous,current) in zip(calculated["factor_path"],
                                         reference_values, reference_values[1:]):
        reference_return=current/previous-1
        diff_bps=abs(reference_return-entry["period_return"])*10000
        discrepancies.append({"session":entry["session"],
                              "reconstructed_return":entry["period_return"],
                              "reference_return":round(reference_return,12),
                              "deviation_bps":round(diff_bps,6),
                              "outside_tolerance":diff_bps>tolerance_bps+1e-7})
    failures=[r for r in discrepancies if r["outside_tolerance"]]
    return {
        "status": ("RESEARCH_RETURN_SERIES_DISAGREE" if failures
                   else "RESEARCH_RETURN_SERIES_MATCH_NOT_CERTIFIED"),
        "market":market,"security_id":security_id,
        "start_session":calculated["start_session"],
        "last_session":calculated["last_session"],
        "raw_source_id":raw_source_id,"reference_source_id":ref_source,
        "reference_basis":"total_return_reinvested_index",
        "requested_tolerance_bps":tolerance_bps,
        "compared_intervals":len(discrepancies),
        "reconstructed_total_return":calculated["total_return"],
        "reference_total_return":round(reference_values[-1]/reference_values[0]-1,12),
        "maximum_abs_deviation_bps":max(x["deviation_bps"] for x in discrepancies),
        "intervals_outside_tolerance":len(failures),
        "exception_samples":failures[:20],
        "independent_provider_identity_verified":False,
        "historic_price_actions_pit_certified":False,
        "delisting_settlement_verified":False,
        "warning":("Declared distinct source IDs do not prove vendor independence. "
                   "Any statistical agreement cannot certify complete corporate actions, "
                   "survivor-free historical coverage or delisting proceeds."),
    }
