"""2_2/2_5: third-source exchange-wide, individual-share-class PIT roster audit.

Offline staged provider and independent claimed issuer lineage are already
cross-checked in issuer_class_bridge. This adds an independently DECLARED
whole-exchange security-class inventory for the same decision day. Publisher
names, local files and claimed timestamps are NOT official exchange proof.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re

from .issuer_class_bridge import (
    STATUS_MATCH as ISSUER_MATCH,
    _claimed, _entity, _read_reference, _reference_active, _stage_active,
    audit_staged_issuer_class,
)
from .issuer_lineage import _timestamp, _date, ZONES
from .provider_export_normalizer import _preflight
from .provider_pit_adapter import _json, _now

SCHEMA="eraleader.declared_exchange_roster.v1"
MATCH="LOCAL_THREE_DECLARED_SOURCES_COMPLETE_SCOPE_MATCH_NOT_CERTIFIED"
BLOCKED="BLOCKED_DECLARED_EXCHANGE_SCOPE_CONFLICT"
CENSORED="CENSORED_DECLARED_EXCHANGE_SCOPE_NOT_CONTEMPORANEOUS_OR_INDEPENDENT"
ROOT_KEYS={
    "schema_version","market","source_id","publisher_id_claimed",
    "scope_id","complete_scope_claimed","session_day",
    "published_at","retrieved_at","security_classes",
}
CLASS_KEYS={"security_id","ticker","valid_from","valid_to"}
NAME=re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,80}\Z")
KR_STOCK=re.compile(r"[0-9]{6}\Z")
US_TICKER=re.compile(r"[A-Z][A-Z0-9.-]{0,18}\Z")
MAX_ROSTER_BYTES=12_000_000
MAX_CLASSES=100_000


def _read_roster(path:Path) -> tuple[dict,str]:
    p=Path(path)
    if (p.is_symlink() or p.parent.is_symlink() or not p.is_file() or
            not 0<p.stat().st_size<=MAX_ROSTER_BYTES):
        raise ValueError("Missing, unsafe, or oversized declared exchange roster")
    raw=p.read_bytes()
    if not 0<len(raw)<=MAX_ROSTER_BYTES:
        raise ValueError("Empty/oversized declared roster")
    # Reuse provider strict duplicate JSON key/nonfinite-number reader.
    roster=_json(raw)
    if (type(roster) is not dict or set(roster)!=ROOT_KEYS or
            roster["schema_version"]!=SCHEMA or roster["market"] not in ZONES or
            type(roster["complete_scope_claimed"]) is not bool or
            not isinstance(roster["security_classes"],list) or
            not 1<=len(roster["security_classes"])<=MAX_CLASSES):
        raise ValueError("Invalid/incomplete declared exchange-wide roster contract")
    for key in ("source_id","publisher_id_claimed","scope_id"):
        value=roster[key]
        if type(value) is not str or not NAME.fullmatch(value):
            raise ValueError("Invalid claimed exchange source/scope identifier")
    if roster["scope_id"]!="ALL_LISTED_EQUITY_CLASSES":
        raise ValueError("Exchange roster must explicitly declare full listed equity share-class scope")
    return roster,sha256(raw).hexdigest()


def _roster_members(roster:dict,day:str) -> dict:
    market=roster["market"]
    result={}
    for entry in roster["security_classes"]:
        if type(entry) is not dict or set(entry)!=CLASS_KEYS:
            raise ValueError("Declared exchange share class missing required interval/identity")
        sec=entry["security_id"]
        ticker=entry["ticker"]
        if (type(sec) is not str or _entity(sec,market) is None or
                type(ticker) is not str or
                not (KR_STOCK if market=="KR" else US_TICKER).fullmatch(ticker)):
            raise ValueError("Invalid exchange issuer/share-class or ticker")
        start=_date(entry["valid_from"])
        end=_date(entry["valid_to"]) if entry["valid_to"] is not None else None
        if end is not None and end<=start:
            raise ValueError("Nonpositive exchange listing interval")
        if sec in result:
            raise ValueError("Duplicate exchange permanent security class in roster")
        # A complete *as-of listing* inventory must contain active classes only.
        if not start.isoformat()<=day or (end is not None and day>=end.isoformat()):
            raise ValueError("Exchange roster contains expired or not-yet-listed security class")
        result[sec]=entry
    # Ticker is market-wide unique in the stated active share-class scope.
    tickers=[row["ticker"] for row in result.values()]
    if len(tickers)!=len(set(tickers)):
        raise ValueError("Duplicate active exchange ticker points to different share classes")
    return result


def _one_pass(stage_file:Path,reference_file:Path,roster_file:Path, *,
              cutoff:datetime,now:datetime) -> dict:
    # Baseline reuses all existing stage JSONL SHA/revisions, corporate-event,
    # separate-company / individual-class and source-time validators.
    baseline=audit_staged_issuer_class(stage_file,reference_file,
                                       decision_at=cutoff.isoformat(),clock=now)
    stage,normalized,_,meta=_preflight(stage_file,now)
    reference,reference_sha=_read_reference(reference_file)
    roster,roster_sha=_read_roster(roster_file)
    market=stage["market"]
    if market!=reference["market"] or market!=roster["market"]:
        raise ValueError("Exchange roster market disagrees with source markets")
    session=_date(roster["session_day"])
    day=cutoff.astimezone(ZONES[market]).date()
    if session>day:
        raise ValueError("Future exchange roster session would leak information")
    if session!=day:
        raise ValueError("Different decision-day exchange roster cannot prove snapshot completeness")
    published=_timestamp(roster["published_at"])
    retrieved=_timestamp(roster["retrieved_at"])
    if published>retrieved or retrieved>now:
        raise ValueError("Impossible exchange roster publication/retrieval/observation order")
    # A forward-dated entire-exchange snapshot is not an observed session;
    # otherwise future listings could masquerade as pre-known PIT membership.
    if published.astimezone(ZONES[market]).date()<session:
        raise ValueError("Exchange roster published before its claimed market session")
    source_claims=(
        (_claimed(stage["source_id"]),_claimed(stage["publisher_id_claimed"])),
        (_claimed(reference["source_id"]),_claimed(reference["publisher_id_claimed"])),
        (_claimed(roster["source_id"]),_claimed(roster["publisher_id_claimed"])),
    )
    issues=Counter()
    if len(set(s for s,_ in source_claims))!=3:
        issues["NOT_THREE_DISTINCT_CLAIMED_SOURCES"]+=1
    if len(set(p for _,p in source_claims))!=3:
        issues["NOT_THREE_DISTINCT_CLAIMED_PUBLISHERS"]+=1
    if not roster["complete_scope_claimed"]:
        issues["ROSTER_NOT_CLAIMED_COMPLETE_EXCHANGE_SCOPE"]+=1
    if published>cutoff:
        issues["ROSTER_NOT_PUBLISHED_BY_DECISION"]+=1
    if retrieved>cutoff:
        issues["ROSTER_NOT_RETRIEVED_BY_DECISION"]+=1
    late_keys=frozenset({
        "NOT_THREE_DISTINCT_CLAIMED_SOURCES",
        "NOT_THREE_DISTINCT_CLAIMED_PUBLISHERS",
        "ROSTER_NOT_PUBLISHED_BY_DECISION",
        "ROSTER_NOT_RETRIEVED_BY_DECISION",
    })
    current_roster=_roster_members(roster,day.isoformat())
    left={}
    right={}
    if baseline["status"]!=ISSUER_MATCH:
        issues.update({"PAIR_"+key:value for key,value in baseline["blocker_counts"].items()})
        if not baseline["blocker_counts"]:
            issues["STAGED_ISSUER_PAIR_NOT_CORROBORATED"]+=1
    if not (late_keys & set(issues)) and baseline["status"]==ISSUER_MATCH:
        source_issues=Counter()
        left=_stage_active(normalized,cutoff,day.isoformat(),source_issues)
        right=_reference_active(reference,cutoff,day.isoformat(),source_issues)
        # Do not silently accept a previously validated pair changing while
        # the third source is being read.
        for reason,count in source_issues.items():
            issues["PAIR_"+reason]+=count
        for sec in sorted(set(current_roster)|set(left)|set(right)):
            exchange=current_roster.get(sec)
            a=left.get(sec)
            b=right.get(sec)
            if exchange is None:
                issues["PIT_PAIR_CLASS_MISSING_FROM_EXCHANGE_ROSTER"]+=1
            elif a is None:
                issues["EXCHANGE_CLASS_MISSING_FROM_STAGED_SOURCE"]+=1
            elif b is None:
                issues["EXCHANGE_CLASS_MISSING_FROM_ISSUER_LINEAGE"]+=1
            elif exchange["ticker"] not in (a["ticker"],b["ticker"]) or a["ticker"]!=b["ticker"]:
                issues["EXCHANGE_CLASS_TICKER_CONFLICT"]+=1
            elif (exchange["valid_from"],exchange["valid_to"])!=(
                    a["valid_from"],a.get("valid_to")) or (
                    exchange["valid_from"],exchange["valid_to"])!=(
                    b["valid_from"],b.get("valid_to")):
                issues["EXCHANGE_CLASS_LISTING_INTERVAL_CONFLICT"]+=1
        # Baseline counted complete classes, not merely ticker matches.
        if len(left)!=baseline["matched_security_class_count"] or len(right)!=len(left):
            issues["PAIR_ACTIVE_CLASS_DENOMINATOR_CHANGED"]+=1
    censored=bool(late_keys & set(issues) or baseline["status"] not in (
        ISSUER_MATCH,"BLOCKED_STAGED_ISSUER_CLASS_MISMATCH"))
    status=CENSORED if censored else BLOCKED if issues else MATCH
    canonical=json.dumps({
        "market":market,"cutoff":cutoff.isoformat(),
        "roster_sha":roster_sha,
        "reference_sha":reference_sha,
        "stage_sha":meta["source_raw_manifest_sha256"],
        "stage_stream_sha":meta["source_file_sha256"],
        "base_status":baseline["status"],
        "blockers":dict(sorted(issues.items())),
    },ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
    return {
        "status":status,
        "market":market,
        "decision_at_utc":cutoff.isoformat(),
        "declared_exchange_roster_sha256":roster_sha,
        "declared_exchange_session_day":day.isoformat(),
        "staged_source_sha256":meta["source_raw_manifest_sha256"],
        "issuer_lineage_source_sha256":reference_sha,
        "research_three_way_evidence_sha256":sha256(canonical.encode()).hexdigest(),
        "staged_issuer_bridge_status":baseline["status"],
        "declared_exchange_class_count":len(current_roster),
        "staged_asof_class_count":baseline["staged_asof_active_security_classes"],
        "issuer_lineage_asof_class_count":baseline["issuer_lineage_asof_active_security_classes"],
        "locally_matched_full_scope_classes":(
            len(current_roster) if status==MATCH else 0),
        "complete_exchange_scope_claimed":roster["complete_scope_claimed"],
        "three_distinct_publishers_claimed":len(set(p for _,p in source_claims))==3,
        "asof_roster_retrieved_claimed":retrieved<=cutoff,
        "blocker_counts":dict(sorted(issues.items())),
        "blocker_count":sum(issues.values()),
        "historical_exchange_universe_pit_certified":False,
        "legal_security_class_independently_authenticated":False,
        "publisher_identity_independently_verified":False,
        "claimed_publication_clock_independently_attested":False,
        "official_leader_promotions":0,
        "real_future_leader_precision":None,
        "external_api_calls":0,
        "warning":"Matching three separately CLAIMED sources is a research discrepancy check, not official market completeness, PIT/issuer identity, or a first-publication attestation.",
    }


def audit_declared_exchange_roster(
    staged_manifest:Path,issuer_lineage_file:Path,roster_file:Path, *,
    decision_at:str,clock:datetime|None=None,
) -> dict:
    """Read-only double-pass whole-roster source comparison; never promote."""
    now=_now(clock)
    cutoff=_timestamp(decision_at)
    if cutoff>now:
        raise ValueError("Future roster decision is forbidden")
    first=_one_pass(Path(staged_manifest),Path(issuer_lineage_file),
                    Path(roster_file),cutoff=cutoff,now=now)
    second=_one_pass(Path(staged_manifest),Path(issuer_lineage_file),
                     Path(roster_file),cutoff=cutoff,now=now)
    if first!=second:
        raise ValueError("Exchange roster/staged issuer inputs revised during audit")
    return first
