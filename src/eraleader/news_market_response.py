"""ER-NC-06: event→price response and price anomaly→local news query.

No scraping, LLM inference, licensed article text or live API calls. Unknown
coverage cannot prove there was 'no news'. All records are as-of research.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any

from .news_catalyst_adapter import _time, _canonical, record_sha256

ALLOWED_ANOMALIES={"STRONG_EXCESS_RETURN","TURNOVER_SPIKE",
                   "PRICE_NEWS_DIVERGENCE"}
POSITIVE_TYPES={"NEW_CONTRACT","EARNINGS_BEAT","POSITIVE_GUIDANCE",
                "POSITIVE_MATERIAL_DISCLOSURE"}
ID=re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
EXPERIMENT_PRICE_PCT=8.0
EXPERIMENT_VOLUME_MULTIPLE=2.5


def _number(value,label):
    if type(value) not in (int,float) or not isfinite(value):
        raise ValueError("NEWS market invalid "+label)
    return float(value)


def make_anomaly_news_query(*, security_id: str|None, theme_id: str|None,
                            as_of: str, anomaly_type: str,
                            window_days: int=5) -> dict:
    if ((security_id is None)==(theme_id is None) or
            security_id is not None and not ID.fullmatch(security_id) or
            theme_id is not None and not ID.fullmatch(theme_id)):
        raise ValueError("Exactly one eligible market security/theme required")
    if anomaly_type not in ALLOWED_ANOMALIES:
        raise ValueError("Unknown anomaly research type")
    if type(window_days) is not int or not 1<=window_days<=30:
        raise ValueError("Bounded local research window required")
    dt=_time(as_of,"as_of")
    params={"security_id":security_id,"theme_id":theme_id,
            "as_of":dt.isoformat(),"anomaly_type":anomaly_type,
            "window_begin":(dt-timedelta(days=window_days)).isoformat(),
            "window_end":dt.isoformat(), "window_calendar_days":window_days}
    key=sha256(_canonical(params)).hexdigest()
    return {"schema":"eraleader.er_nc_anomaly_local_query.v1",
            "request_id":key,"dedup_key":key,
            "query":params,"read_only":True,
            "remote_search_permitted":False,"estimated_network_calls":0,
            "research_only":True}


class LocalAnomalyQueryCache:
    def __init__(self):
        self._cache={}

    def request(self, payload:dict) -> dict:
        if payload.get("remote_search_permitted") is not False:
            raise ValueError("Unapproved news-provider API search")
        q=payload.get("query",{})
        expected=make_anomaly_news_query(
            security_id=q.get("security_id"),theme_id=q.get("theme_id"),
            as_of=q["as_of"],anomaly_type=q["anomaly_type"],
            window_days=q["window_calendar_days"])
        if expected != payload:
            raise ValueError("NEWS query tampered or lacks immutable request ID")
        key=payload["request_id"]
        duplicate=key in self._cache
        if not duplicate:
            self._cache[key]=deepcopy(payload)
        return {"request_id":key,"queued_unique_count":len(self._cache),
                "duplicate":duplicate, "remote_api_calls":0}


def diagnose_news_market_response(*,security_id:str,
                                  news_snapshot:dict|None,
                                  as_of:str, market_session:str,
                                  market_data_available_at:str,
                                  excess_return_pct:float,
                                  turnover_multiple:float,
                                  issuer_id:str|None=None,
                                  issuer_mapping_available_at:str|None=None,
                                  trusted_coverage_sha256:str|None=None) -> dict:
    """Diagnose only as-of facts; never issue buy/sell advice."""
    if type(security_id) is not str or not ID.fullmatch(security_id):
        raise ValueError("Market response requires permanent security ID")
    now=_time(as_of,"as_of")
    cutoff=_time(market_data_available_at,"market_available")
    if cutoff>now:
        raise ValueError("Future market price cannot be linked to past news")
    delta=_number(excess_return_pct,"excess_return_pct")
    volume=_number(turnover_multiple,"turnover_multiple")
    if volume<0:
        raise ValueError("Negative turnover multiplier")
    if date.fromisoformat(market_session) > cutoff.date():
        raise ValueError("Future market session relative to price availability")
    base={"schema":"eraleader.er_nc_market_news_response.v1",
          "security_id":security_id,"as_of":now.isoformat(),
          "market_session":market_session,
          "market_data_available_at":cutoff.isoformat(),
          "excess_return_pct":delta,"turnover_multiple":volume,
          "diagnosis":"stale_or_unknown","reason_codes":[],
          "event_evidence_ids":[],"research_only":True,
          "recommendation":None,"official_leaders":0}
    # Explicit issuer-to-security mapping is required. A shared ticker or an
    # issuer-level event is never proof about one particular share class.
    if issuer_id is None or issuer_mapping_available_at is None:
        base["reason_codes"]=["ISSUER_SECURITY_MAPPING_REQUIRED"]
        return base
    if type(issuer_id) is not str or not ID.fullmatch(issuer_id):
        raise ValueError("Invalid permanent issuer ID")
    if _time(issuer_mapping_available_at,"issuer_mapping_available_at") > cutoff:
        base["reason_codes"]=["ISSUER_SECURITY_MAPPING_NOT_KNOWN_AT_PRICE"]
        return base
    if type(news_snapshot) is not dict or news_snapshot.get("mode")!="LIVE_OBSERVED":
        base["reason_codes"]=["NEWS_INPUT_UNAVAILABLE_OR_UNVERIFIED"]
        return base
    if (news_snapshot.get("schema")!="ernc.news_snapshot.v1" or
            type(news_snapshot.get("events")) is not list):
        base["reason_codes"]=["NEWS_SNAPSHOT_SCHEMA_UNTRUSTED"]
        return base
    if _time(news_snapshot["as_of"],"news_as_of")>now:
        raise ValueError("Future news vintage cannot explain earlier response")
    if news_snapshot.get("quality_status") not in {"OK","NO_VISIBLE_EVENTS"}:
        base["reason_codes"]=["NEWS_INPUT_DEGRADED"]
        return base
    if (news_snapshot.get("event_count")!=len(news_snapshot["events"]) or
            news_snapshot.get("quality_status")=="NO_VISIBLE_EVENTS"
            and len(news_snapshot["events"])>0):
        raise ValueError("NEWS snapshot event count/status mismatch")
    related=[]
    for event in news_snapshot["events"]:
        if type(event) is not dict:
            raise ValueError("NEWS event object required")
        status=event.get("evidence_status")
        if status not in {"VERIFIED_AS_OF","INVALIDATED"}:
            continue
        if (status=="VERIFIED_AS_OF" and event.get("verification_status")!="VERIFIED" or
                status=="INVALIDATED" and event.get("verification_status")!="INVALIDATED"):
            raise ValueError("NEWS evidence status mismatch")
        # The PIT adapter adds evidence_status and sometimes REVISION_PENDING.
        # Reconstruct the verified original record and check its SHA, not a
        # caller-supplied market explanation or a later rewritten field.
        original=deepcopy(event)
        original.pop("evidence_status",None)
        if record_sha256(original)!=event.get("record_sha256"):
            flags=original.get("quality_flags")
            if type(flags) is not list or not flags or flags[-1]!="REVISION_PENDING":
                raise ValueError("NEWS event record SHA mismatch")
            original["quality_flags"]=flags[:-1]
            if record_sha256(original)!=event.get("record_sha256"):
                raise ValueError("NEWS event record SHA mismatch")
        # Related issuer and verified beneficiary are different from ticker
        # equality. POTENTIAL/UNVERIFIED beneficiaries cannot prove causality.
        if not (issuer_id in event.get("related_issuer_ids",[]) or
                any(type(b) is dict and b.get("issuer_id")==issuer_id and
                    b.get("relation")=="DIRECT_VERIFIED"
                    for b in event.get("beneficiary_candidates",[]))):
            continue
        available=_time(event["available_at"],"available_at")
        if available>now:
            raise ValueError("Future news event smuggled into live research snapshot")
        related.append(event)
    related.sort(key=lambda r:(_time(r["available_at"],"available_at"),
                               r["event_id"],r["event_version"]))
    # Only a verified event known BY the market observation can potentially
    # explain that candle. Later news stays separate and never backfills cause.
    eligible=[event for event in related if
              _time(event["available_at"],"available_at")<=cutoff]
    if related and not eligible:
        observed_early=any(
            _time(event["first_seen_at"],"first_seen_at")<=cutoff
            for event in related
        )
        base["reason_codes"]=[
            "NEWS_VERIFICATION_AFTER_PRICE_OBSERVATION"
            if observed_early else "NEWS_FIRST_SEEN_AFTER_PRICE_OBSERVATION"
        ]
        return base
    if not eligible:
        # No article in an unverified/incomplete feed cannot prove no news.
        if (abs(delta)>=EXPERIMENT_PRICE_PCT or
                volume>=EXPERIMENT_VOLUME_MULTIPLE):
            witness=news_snapshot.get("coverage_witness_sha256")
            coverage_time=news_snapshot.get("coverage_available_at")
            attested=(news_snapshot.get("coverage_status")=="COMPLETE_VERIFIED_AS_OF"
                      and type(witness) is str
                      and re.fullmatch(r"[0-9a-f]{64}",witness) is not None
                      and type(trusted_coverage_sha256) is str
                      and witness==trusted_coverage_sha256
                      and type(coverage_time) is str
                      and _time(coverage_time,"coverage_available_at")<=cutoff)
            if attested:
                base["diagnosis"]="strong_price_no_verified_news"
                base["reason_codes"]=["NO_VERIFIED_EVENT_WITHIN_ATTESTED_LOCAL_COVERAGE"]
            else:
                base["reason_codes"]=["PRICE_ANOMALY_NEWS_COVERAGE_INSUFFICIENT"]
        else:base["reason_codes"]=["NO_VERIFIED_NEWS_AVAILABLE"]
        return base
    latest=eligible[-1]
    base["event_evidence_ids"]=[ev["event_id"] for ev in eligible]
    if "REVISION_PENDING" in latest.get("quality_flags",[]):
        base["reason_codes"]=["NEWS_REVISION_PENDING"]
        return base
    if latest.get("verification_status")=="INVALIDATED" or latest.get("catalyst_state")=="INVALIDATED":
        base["diagnosis"]="stale_or_unknown"
        base["reason_codes"]=["MATERIAL_FACT_INVALIDATED_AFTER_ORIGINAL_VERSION"]
    elif latest.get("novelty")=="REPEATED":
        base["diagnosis"]="repeated_news"
        base["reason_codes"]=["LICENSED_EVENT_ALREADY_REPORTED"]
    elif latest.get("event_type") in POSITIVE_TYPES and latest.get("catalyst_state")=="CONFIRMED":
        if delta>=3.0:
            base["diagnosis"]="positive_news_positive_price"
            base["reason_codes"]=["VERIFIED_POSITIVE_CATALYST_PRICE_CO_DIRECTION"]
        elif delta<=-3.0:
            base["diagnosis"]="positive_news_negative_price"
            base["reason_codes"]=["VERIFIED_POSITIVE_CATALYST_NEGATIVE_PRICE_RESPONSE"]
        else:base["reason_codes"]=["PRICE_RESPONSE_WITHIN_NEUTRAL_EXCESS_BAND"]
    else:
        base["reason_codes"]=["VERIFIED_MATERIAL_FACT_DIRECTION_UNCERTAIN"]
    return base
