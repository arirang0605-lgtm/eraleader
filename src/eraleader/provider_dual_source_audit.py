"""2_2/2_5: compare TWO already received, separately declared PIT bundles.

An internal matching hash and two different claimed publisher strings do not
authenticate either publisher, prove independent acquisition, certify the
whole listed universe, or imply a genuine future leader prediction.
"""
from __future__ import annotations

from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3

from .frozen_holdout import _stamp
from .offline_pit import OfflineLedger,verify_stored_pit_record
from .provider_pit_adapter import (
    audit_registered_provider_asof,_now,SHA
)

STATUS_CONSISTENT="LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED"
STATUS_BLOCKED="BLOCKED_CONFLICTING_DECLARED_PIT_SOURCES"
STATUS_LATE="CENSORED_NOT_CONTEMPORANEOUSLY_REGISTERED_SOURCES"
ZONES={"KR":ZoneInfo("Asia/Seoul"),"US":ZoneInfo("America/New_York")}


def _full_receipt_source(ledger_file:Path,bundle_hash:str,cutoff:datetime):
    """Read only rows belonging to one validated exact bundle, not vendor ticker joins."""
    ledger=OfflineLedger.open_readonly(ledger_file)
    try:
        conn=ledger.db
        conn.execute("BEGIN")
        try:
            rows=conn.execute(
                """SELECT r.kind,r.record_key,r.available_at,r.source_id,
                          r.provenance,r.payload,r.fingerprint,x.normalized_sha256
                   FROM provider_ingest_rows x
                   JOIN offline_records r
                     ON r.kind=x.kind AND r.record_key=x.record_key
                   WHERE x.bundle_sha256=?
                   ORDER BY r.kind,r.record_key""",(bundle_hash,)
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Provider bundle receipt rows missing or corrupt") from exc
        by_kind=defaultdict(list)
        for entry in rows:
            row=verify_stored_pit_record(*entry[:7])
            if entry[6]!=entry[7] or row["provenance"]!="user_supplied":
                raise ValueError("Provider bundle receipt normalized source digest mismatch")
            available=_stamp(entry[2])
            if available<=cutoff:
                by_kind[entry[0]].append(row)
        return by_kind
    finally:
        ledger.close()


def _membership_asof(rows:list,day:str):
    """Latest then-known membership interval for each asserted permanent ID."""
    by_company={}
    for r in rows:
        if r["valid_from"]>day:
            continue
        key=r["security_id"]
        prior=by_company.get(key)
        if prior is None or (
            r["valid_from"],r["known_at"],r["revision"]
        )>(prior["valid_from"],prior["known_at"],prior["revision"]):
            by_company[key]=r
    return by_company


def _latest(rows:list,identity:tuple[str,...]):
    by_key={}
    for row in rows:
        key=tuple(row[field] for field in identity)
        prior=by_key.get(key)
        pub=row.get("known_at",row.get("available_at"))
        old_pub=(prior.get("known_at",prior.get("available_at"))
                 if prior is not None else None)
        if prior is None or (pub,row["revision"])>(old_pub,prior["revision"]):
            by_key[key]=row
    return by_key


def _events(rows:list,issues):
    """Publisher-local action_id can differ, but economic semantics cannot."""
    # Latest revision for one publisher's action ID is authoritative.
    revised=_latest(rows,("security_id","action_id"))
    indexed=defaultdict(list)
    for r in revised.values():
        key=(r["security_id"],r["action_type"],r["effective_on"])
        indexed[key].append(r)
    result={}
    for key,items in indexed.items():
        if len(items)!=1:
            issues("AMBIGUOUS_ACTION_SEMANTIC_KEY","actions",key)
        else:
            result[key]=items[0]
    return result


def audit_provider_source_pair(
    ledger_a:Path,bundle_a:str,ledger_b:Path,bundle_b:str,*,
    decision_at:str,clock:datetime|None=None,sample_limit:int=40,
) -> dict:
    """Record *local* semantic agreement and conflicts at one decision cut.

    All matches require the exact self-declared permanent security_id;
    matching ticker alone is explicitly treated as a suspicious identity
    collision. Empty domains/one-sided companies NEVER imply consensus.
    """
    if type(sample_limit) is not int or not 1<=sample_limit<=200:
        raise ValueError("Invalid provider dual-source sample limit")
    now=_now(clock)
    cutoff=_stamp(decision_at)
    if cutoff>now:
        raise ValueError("Future dual-provider as-of decision forbidden")
    paths=[Path(ledger_a),Path(ledger_b)]
    if (paths[0].is_symlink() or paths[1].is_symlink() or
            not paths[0].is_file() or not paths[1].is_file()):
        raise ValueError("Two existing non-symlink PIT ledgers required")
    if paths[0].resolve()==paths[1].resolve():
        raise ValueError("Two different PIT ledgers needed for source comparison")
    for s in (bundle_a,bundle_b):
        if not isinstance(s,str) or not SHA.fullmatch(s):
            raise ValueError("Invalid sealed provider bundle SHA256")
    # The existing receipt audits check original row digests, source/market
    # identity, first-local-registration and claimed retrieval chronology.
    # Do not duplicate the normalizer/receipt integrity implementation.
    sources=[
        audit_registered_provider_asof(p,d,decision_at=cutoff.isoformat(),clock=now)
        for p,d in zip(paths,(bundle_a,bundle_b))
    ]
    left,right=sources
    if left["market"]!=right["market"]:
        raise ValueError("Cross-market publisher PIT sources cannot be compared")
    if (left["source_id"].casefold()==right["source_id"].casefold()
            or left["publisher_id_claimed"].strip().casefold()
               ==right["publisher_id_claimed"].strip().casefold()):
        raise ValueError("Two distinct claimed publisher and source identities required")
    market=left["market"]
    day=cutoff.astimezone(ZONES[market]).date().isoformat()
    counters=Counter()
    observed=[]
    def issue(code:str,domain:str,key:tuple|str):
        counters[code]+=1
        if len(observed)<sample_limit:
            observed.append({
                "code":code,"domain":domain,
                "research_identity":":".join(map(str,key))
                    if isinstance(key,tuple) else str(key),
            })
    def root_report(status:str)->dict:
        return {
            "status":status,
            "market":market,
            "decision_at_utc":cutoff.isoformat(),
            "decision_market_day":day,
            "source_a_bundle_sha256":bundle_a,
            "source_b_bundle_sha256":bundle_b,
            "source_a_first_registration_by_decision":
                _stamp(left["first_registered_at_utc"])<=cutoff,
            "source_b_first_registration_by_decision":
                _stamp(right["first_registered_at_utc"])<=cutoff,
            "source_a_retrieval_claimed_by_decision":
                _stamp(left["retrieved_at_claimed_utc"])<=cutoff,
            "source_b_retrieval_claimed_by_decision":
                _stamp(right["retrieved_at_claimed_utc"])<=cutoff,
            "distinct_claimed_publishers":2,
            "locally_eligible_contemporaneous_provider_pair":
                left["eligible_for_contemporaneous_research"]
                and right["eligible_for_contemporaneous_research"],
            "source_consistency_only":True,
            "matched_known_issuer_count":0,
            "matched_active_issuer_count":0,
            "matched_corporate_event_count":0,
            "matched_fundamental_fact_count":0,
            "matched_industry_fact_count":0,
            "problem_count":sum(counters.values()),
            "blocker_counts":dict(sorted(counters.items())),
            "problem_sample":observed,
            "problem_sample_truncated":sum(counters.values())>len(observed),
            "publisher_independently_authenticated":False,
            "permanent_issuer_identity_independently_attested":False,
            "independently_proven_source_availability":False,
            "official_historical_universe_pit_certified":False,
            "corporate_action_cash_settlement_verified":False,
            "fundamental_publication_independently_attested":False,
            "historic_pit_certified":False,
            "real_future_leader_precision":None,
            "official_leader_promotions":0,
            "warning":(
                "Different claimed publishers can be controlled by the same actor. "
                "A common normalized ID and SHA prove only local declared-source "
                "consistency. No exchange issuer, delist cash, release-time, "
                "all-listed universe, or future leadership certification."
            ),
        }

    if not (left["eligible_for_contemporaneous_research"]
            and right["eligible_for_contemporaneous_research"]):
        for name,item in (("A",left),("B",right)):
            if _stamp(item["first_registered_at_utc"])>cutoff:
                issue("SOURCE_"+name+"_FIRST_REGISTERED_AFTER_DECISION",
                      "provenance",name)
            if _stamp(item["retrieved_at_claimed_utc"])>cutoff:
                issue("SOURCE_"+name+"_RETRIEVED_AFTER_DECISION",
                      "provenance",name)
        return root_report(STATUS_LATE)

    inputs=[
        _full_receipt_source(p,d,cutoff)
        for p,d in zip(paths,(bundle_a,bundle_b))
    ]
    # Different sources can be edited by another process during evaluation:
    # re-audit receipts at the end as a fail-closed safety recheck.
    a,b=inputs
    ma,mb=(_membership_asof(x["membership"],day) for x in inputs)
    matched_known=matched_active=matched_events=matched_facts=matched_industry=0
    for sec in sorted(set(ma)|set(mb)):
        ra,rb=ma.get(sec),mb.get(sec)
        if ra is None or rb is None:
            issue("MEMBERSHIP_ONLY_A" if ra is not None else
                  "MEMBERSHIP_ONLY_B","membership",sec)
            continue
        consistent=True
        for key,code in (
            ("ticker","MEMBERSHIP_TICKER_CONFLICT"),
            ("industry_id","MEMBERSHIP_INDUSTRY_CONFLICT"),
            ("valid_from","MEMBERSHIP_VALID_FROM_CONFLICT"),
            ("valid_to","MEMBERSHIP_VALID_TO_CONFLICT"),
        ):
            if ra.get(key)!=rb.get(key):
                issue(code,"membership",sec)
                consistent=False
        if consistent:
            matched_known+=1
            if (ra.get("valid_to") is None or ra["valid_to"]>day):
                matched_active+=1
    active_tickers=[]
    for m in (ma,mb):
        active_tickers.append({
            v["ticker"]:sec for sec,v in m.items()
            if v["valid_to"] is None or v["valid_to"]>day
        })
    for ticker in sorted(set(active_tickers[0])&set(active_tickers[1])):
        if active_tickers[0][ticker]!=active_tickers[1][ticker]:
            issue("CROSS_PROVIDER_TICKER_ISSUER_CONFLICT",
                  "membership",(ticker,))

    ea,eb=(_events(inp["actions"],issue) for inp in inputs)
    for key in sorted(set(ea)|set(eb)):
        ra,rb=ea.get(key),eb.get(key)
        if ra is None or rb is None:
            issue("ACTION_ONLY_A" if ra is not None else "ACTION_ONLY_B",
                  "actions",key)
            continue
        if key[1]=="split" and ra.get("ratio")!=rb.get("ratio"):
            issue("SPLIT_RATIO_CONFLICT","actions",key)
        elif key[1]=="dividend" and ra.get("cash_amount")!=rb.get("cash_amount"):
            issue("DIVIDEND_CASH_AMOUNT_CONFLICT","actions",key)
        else:
            matched_events+=1

    fa,fb=(_latest(inp["fundamentals"],("security_id","metric","period_end"))
           for inp in inputs)
    ia,ib=(_latest(inp["industry"],("industry_id","metric","period_end"))
           for inp in inputs)
    for domain,la,lb in (("FUNDAMENTAL",fa,fb),("INDUSTRY",ia,ib)):
        for key in sorted(set(la)|set(lb)):
            ra,rb=la.get(key),lb.get(key)
            if ra is None or rb is None:
                issue(domain+("_ONLY_A" if ra is not None else "_ONLY_B"),
                      domain.lower(),key)
            elif ra["unit"]!=rb["unit"]:
                issue(domain+"_UNIT_CONFLICT",domain.lower(),key)
            elif ra["value"]!=rb["value"]:
                issue(domain+"_VALUE_CONFLICT",domain.lower(),key)
            elif domain=="FUNDAMENTAL":
                matched_facts+=1
            else:
                matched_industry+=1
    # Empty source domains or no active members is not evidence of a
    # matching complete historical exchange universe.
    for domain,items in (("MEMBERSHIP",matched_active),("ACTIONS",matched_events),
                         ("FUNDAMENTALS",matched_facts),("INDUSTRY",matched_industry)):
        if not items:
            issue("NO_MATCHING_"+domain+"_EVIDENCE","coverage",domain)
    rechecked=[
        audit_registered_provider_asof(p,d,decision_at=cutoff.isoformat(),clock=now)
        for p,d in zip(paths,(bundle_a,bundle_b))
    ]
    if rechecked!=sources:
        raise RuntimeError("PIT provider receipt revised during source comparison")
    result=root_report(STATUS_BLOCKED if counters else STATUS_CONSISTENT)
    result.update({
        "matched_known_issuer_count":matched_known,
        "matched_active_issuer_count":matched_active,
        "matched_corporate_event_count":matched_events,
        "matched_fundamental_fact_count":matched_facts,
        "matched_industry_fact_count":matched_industry,
    })
    return result
