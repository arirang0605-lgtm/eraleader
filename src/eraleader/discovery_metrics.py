"""Evaluate historically registered discoveries against independently realized outcomes.

Evaluation ONLY; labels must never enter discovery or scoring modules.
No financial PIT completeness claim follows from these statistics alone.
"""
from __future__ import annotations
from datetime import date, timedelta
from statistics import median


def _day(raw: str) -> date:
    return date.fromisoformat(raw)

def evaluate_early_discovery(
    signals: list[dict], outcomes: list[dict], *,
    evaluated_at: str, horizon_days: int,
    full_universe_certified: bool = False
) -> dict:
    """At-most-once first signal per security. Outcomes are retrospective labels.

    Each outcome must explicitly include outcome_available_at and mature_on.
    Unknown/censored are not classified as failures or omitted from coverage.
    Recall denominator requires a complete, independently certified universe.
    """
    today=_day(evaluated_at)
    if horizon_days<=0:
        raise ValueError("horizon_days must be positive")
    labels={}
    for row in outcomes:
        sec=row["security_id"]
        if sec in labels:
            raise ValueError(f"Duplicate outcome for {sec}")
        if not isinstance(row["is_future_leader"],bool):
            raise ValueError("Label must be boolean")
        mature=_day(row["mature_on"])
        known=_day(row["outcome_available_at"])
        if known < mature:
            raise ValueError("Outcome cannot be known before its maturity")
        labels[sec]=row
    first={}
    unregistered=set()
    for row in signals:
        sec=row["security_id"]
        seen=_day(row["first_seen"])
        # Backfilled first_seen cannot masquerade as the actual signal
        # registration date. Count early lead from the later date.
        if "recorded_at" in row:
            recorded=_day(row["recorded_at"])
            if recorded<seen:
                raise ValueError("Signal recorded_at precedes first_seen")
            effective=recorded
        else:
            unregistered.add(sec)
            effective=seen
        if effective>today or seen>today:
            raise ValueError("Future signal cannot enter evaluation")
        if sec not in first or effective<first[sec]:
            first[sec]=effective
    tp=fp=late=unknown=0
    premature_negative=0
    lead=[]
    for sec,seen in first.items():
        label=labels.get(sec)
        if not label or _day(label["outcome_available_at"])>today:
            unknown+=1
            continue
        matured=_day(label["mature_on"])
        if matured>today:
            unknown+=1
            continue
        if matured < seen:
            # A label that predates first detection cannot credit early discovery.
            late+=1
            continue
        if label["is_future_leader"]:
            onset=_day(label["leader_start_at"])
            if onset>matured:
                raise ValueError("Leader onset after label maturity")
            elapsed=(onset-seen).days
            if 0<elapsed<=horizon_days:
                tp+=1
                lead.append(elapsed)
            else:
                late+=1
        else:
            if matured < seen + timedelta(days=horizon_days):
                unknown+=1
                premature_negative+=1
                continue
            fp+=1
    precision=tp/(tp+fp) if tp+fp else None
    all_positives=[sec for sec,label in labels.items()
                   if label["is_future_leader"]
                   and _day(label["outcome_available_at"])<=today
                   and _day(label["mature_on"])<=today]
    recall=tp/len(all_positives) if full_universe_certified and all_positives else None
    return {
       "status":"RESEARCH_EVALUATION_ONLY_NOT_CERTIFIED",
       "evaluated_at":evaluated_at,"horizon_days":horizon_days,
       "signals":len(first),"evaluable":tp+fp+late,"censored":unknown,
       "evaluable_fraction":round((tp+fp+late)/len(first),6) if first else None,
       "premature_negative_labels_censored":premature_negative,
       "retrospective_unregistered_signals":len(unregistered),
       "all_signal_dates_independently_registered":not unregistered,
       "conservative_early_precision_floor":round(tp/len(first),6) if first else None,
       "true_early_discoveries":tp,"false_discoveries":fp,
       "late_or_post_onset":late,
       "precision_on_known_nonlate":round(precision,6) if precision is not None else None,
       "recall_certified_universe":round(recall,6) if recall is not None else None,
       "median_early_lead_days":median(lead) if lead else None,
       "full_universe_certified":full_universe_certified,
       "warnings":["Censored future outcomes excluded, NOT treated as failure",
                   "Negative labels maturing before the complete signal horizon remain censored",
                   "Missing recorded_at means signal discovery dates lack an independent registration audit",
                   "Registered signal date (not backdated first_seen) determines early lead time",
                   "Official recall unavailable until complete historical universe and labels certified",
                   "Investing return and corporate actions are not measured here"]
    }
