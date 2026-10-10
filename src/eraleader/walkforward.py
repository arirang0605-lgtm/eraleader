"""Walk-forward time splits with embargo and no future label exposure to selection.

This builds an auditable TEST STREAM; it does not tune model weights.
Historical market completeness and corporate actions remain unverified.
"""
from __future__ import annotations
from datetime import datetime, timedelta

def time(value: str) -> datetime:
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:
        raise ValueError("Timezone offset required")
    return t

def walk_forward_split(
    snapshots:list[dict],labels:list[dict], *,
    train_ends_at:str,test_ends_at:str,embargo_days:int=7
) -> dict:
    cutoff=time(train_ends_at)
    until=time(test_ends_at)
    if until<=cutoff or embargo_days<1:
        raise ValueError("Invalid split dates or embargo")
    begin=cutoff+timedelta(days=embargo_days)
    labels_by_key={}
    for r in labels:
        key=(r["security_id"],r["as_of"])
        if key in labels_by_key:
            raise ValueError("Duplicated outcome key")
        # Explicit confirmation timestamp required to prevent accidental
        # reusing a revision long before it was actually published.
        available=time(r["label_available_at"])
        if available<=time(r["as_of"]):
            raise ValueError("Future outcome label claims availability at selection")
        labels_by_key[key]=r
    training=[];holdout=[];unused=0
    seen=set()
    for s in snapshots:
        key=(s["security_id"],s["as_of"])
        if key in seen:
            raise ValueError("Duplicated PIT signal snapshot")
        seen.add(key)
        decision=time(s["as_of"])
        available=time(s["features_available_at"])
        if available>decision:
            raise ValueError(f"Future feature revision for {key}")
        if decision<=cutoff:
            label=labels_by_key.get(key)
            # Only genuinely matured and available labels can influence
            # training before the cutoff. Unknown targets are censored.
            if label and time(label["label_available_at"])<=cutoff:
                training.append({"security_id":s["security_id"],"as_of":s["as_of"],
                                 "feature_hash":s["feature_hash"],
                                 "target":label["is_future_leader"]})
            else:
                unused+=1
        elif begin<=decision<until:
            # Freeze test candidates but NEVER expose outcome labels here.
            holdout.append({"security_id":s["security_id"],"as_of":s["as_of"],
                            "feature_hash":s["feature_hash"]})
    return {
      "status":"WALK_FORWARD_STRUCTURE_RESEARCH_ONLY",
      "train_ends_at":train_ends_at,"test_begins_at":begin.isoformat(),
      "test_ends_at":test_ends_at,"embargo_days":embargo_days,
      "known_training_samples":len(training),
      "censored_training_samples":unused,
      "test_candidates":holdout,
      "training":training,
      "test_outcome_labels_revealed":False,
      "historic_universe_certified":False,
      "warning":"Splits and embargo verified; historical completeness and performance not certified"
    }
