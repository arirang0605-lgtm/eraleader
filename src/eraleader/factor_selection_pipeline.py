"""5-factor KR candidate state pipeline using existing StateHistory + neutral feed.

Local factor assessments are research-only attestations, NOT independently
certified historical issuer/fundamental PIT. No broker permission is created.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import os
import re

from .marketwide_live_search import _source, prepare_search
from .marketwide_auto_refresh import _owned_output
from .official_company_explorer import canonical
from .states import SCORE_MAX
from .state_history import StateHistory
from .strategy_handoff import state_history_handoff, publish_versioned_handoff, verify_handoff

SCHEMA="eraleader.kr_5factor_local_assessment.v1"
LEDGER="five_factor_local_state_history.sqlite"
CANDIDATE_OUTBOX="qualified_research_outbox"
ASSESSMENT="LOCAL_ATTESTED_RESEARCH_NOT_INDEPENDENT_PIT"
EVIDENCE=("financial_pit","historic_universe_pit","corporate_actions_pit",
          "issuer_identity_pit","fundamental_growth","confirmed_weekly_trend")


def _read_assessment(path:Path) -> dict:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or any(p.is_symlink() for p in path.parents)
            or path.stat().st_uid!=os.geteuid()
            or not 50<=path.stat().st_size<=2_000_000):
        raise ValueError("FIVE_FACTOR_INPUT_UNSAFE")
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError("FIVE_FACTOR_DUPLICATE_JSON_KEY")
            result[key]=value
        return result
    obj=json.loads(path.read_bytes(),object_pairs_hook=unique,
                   parse_constant=lambda _:(_ for _ in ()).throw(
                       ValueError("FIVE_FACTOR_NONFINITE")))
    if type(obj) is not dict or obj.get("schema")!=SCHEMA:
        raise ValueError("FIVE_FACTOR_INPUT_SCHEMA")
    clone=dict(obj)
    pin=clone.pop("content_sha256",None)
    if type(pin) is not str or pin!=sha256(canonical(clone)).hexdigest():
        raise ValueError("FIVE_FACTOR_INPUT_SHA")
    return obj


def _utc(raw) -> datetime:
    if type(raw) is not str:
        raise ValueError("FIVE_FACTOR_INSTANT_MISSING")
    try:
        stamp=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError:
        raise ValueError("FIVE_FACTOR_INSTANT_INVALID") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("FIVE_FACTOR_INSTANT_UNAWARE")
    return stamp.astimezone(timezone.utc)


def _validate(source:dict, assessment:dict, *, now:datetime) -> tuple[list[dict],str]:
    cutoff=_utc(assessment.get("decision_at_utc"))
    session=source["market_session"]
    # An operational selection belongs to the day the information was first
    # actually accepted, never to a historic price candle.
    local_day=cutoff.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    if (cutoff>now or assessment.get("market")!="KR"
            or assessment.get("market_session")!=session
            or assessment.get("source_marketwide_sha256")!=source["content_sha256"]
            or assessment.get("certification_level")!=ASSESSMENT
            or _utc(source["built_at_utc"])>cutoff
            or date.fromisoformat(session)>date.fromisoformat(local_day)):
        raise ValueError("FIVE_FACTOR_DATE_SOURCE_MISMATCH_OR_STALE")
    rows=assessment.get("factor_rows")
    if type(rows) is not list or not 1<=len(rows)<=500:
        raise ValueError("FIVE_FACTOR_NO_ROWS")
    lookups={r["security_id"]:r for r in source["securities"]}
    seen=set()
    observations=[]
    for item in rows:
        if type(item) is not dict:
            raise ValueError("FIVE_FACTOR_BAD_ROW")
        sec=item.get("security_id")
        if (type(sec) is not str or not re.fullmatch(r"[0-9]{6}",sec)
                or sec not in lookups or sec in seen
                or item.get("ticker")!=sec
                or item.get("issuer_id_validated_as_of") is not True):
            raise ValueError("FIVE_FACTOR_SECURITY_PIT_ID_MISMATCH")
        seen.add(sec)
        market=lookups[sec]
        parts=item.get("components")
        evidence=item.get("evidence")
        receipts=item.get("factor_receipts")
        if (type(parts) is not dict or set(parts)!=set(SCORE_MAX)
                or type(evidence) is not dict or set(evidence)!=set(EVIDENCE)
                or any(type(v) is not bool for v in evidence.values())
                or type(receipts) is not dict or set(receipts)!=set(SCORE_MAX)):
            raise ValueError("FIVE_FACTOR_MISSING_PROVENANCE_OR_COMPONENTS")
        if (parts["momentum"] is not None and
            (type(parts["momentum"]) not in (int,float) or
             market.get("price_strength_25") is None or
             not math.isclose(parts["momentum"],market["price_strength_25"],
                              abs_tol=1e-7))):
            raise ValueError("FIVE_FACTOR_MOMENTUM_NOT_MARKETWIDE")
        if (evidence["issuer_identity_pit"] is True and
                market.get("current_dart_directory_matched") is not True):
            raise ValueError("FIVE_FACTOR_DART_ISSUER_ID_UNMATCHED")
        for name,max_score in SCORE_MAX.items():
            value=parts[name]
            proof=receipts[name]
            if value is None:
                if proof is not None:
                    raise ValueError("FIVE_FACTOR_NULL_SCORE_WITH_RECEIPT")
                continue
            if (type(value) not in (float,int) or not math.isfinite(value)
                    or not 0<=value<=max_score):
                raise ValueError("FIVE_FACTOR_SCORE_OUT_OF_RANGE")
            if (type(proof) is not dict or
                    set(proof)!={"sha256","available_at_utc","provider"} or
                    type(proof["sha256"]) is not str or
                    re.fullmatch(r"[0-9a-f]{64}",proof["sha256"]) is None or
                    type(proof["provider"]) is not str or
                    not 2<=len(proof["provider"])<=60 or
                    _utc(proof["available_at_utc"])>cutoff):
                raise ValueError("FIVE_FACTOR_RECEIPT_INVALID_OR_FUTURE")
        trusted=evidence["issuer_identity_pit"] and all(
            evidence[k] for k in ("financial_pit","historic_universe_pit",
                                  "corporate_actions_pit"))
        # No scored selection can escape a missing local identity/PIT claim.
        # Local self-attested receipts are NOT independent provider certification.
        safe_evidence=dict(evidence)
        if not trusted:
            safe_evidence.update(financial_pit=False,historic_universe_pit=False,
                                 corporate_actions_pit=False)
        safe_evidence.pop("issuer_identity_pit")
        observations.append({
            "security_id":sec,
            "components":parts,
            "evidence":safe_evidence,
            "marketwide_source_sha256":source["content_sha256"],
            "assessment_receipt_sha256":assessment["content_sha256"],
            "first_locally_assessed_at_utc":cutoff.isoformat(),
        })
    return observations,local_day


def run_factor_selection(*, marketwide:Path, project:Path,
                         assessment_file:Path|None=None,
                         clock:datetime|None=None) -> dict:
    now=clock or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("FIVE_FACTOR_AWARE_CLOCK_REQUIRED")
    now=now.astimezone(timezone.utc)
    output=_owned_output(project)
    source,_=_source(marketwide)
    market_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    manifest, _ = prepare_search(source,request_day=market_day,clock=now)
    coverage={
        "krx_observed":manifest["observed_stocks"],
        "historical_price_observed":manifest["price_lookback_available"],
        "financial_observed":manifest["financial_available"],
        "industry_profile_observed":manifest["industry_available"],
        "same_session_flow_observed":manifest["flow_matched_session_companies"],
        "price_earnings_50_research":manifest["research_50_scored"],
        "certified_100_point_leaders":0,
    }
    base={
        "schema":"eraleader.kr_five_factor_operational.v1",
        "source_market_session":manifest["source_market_session"],
        "source_marketwide_sha256":manifest["source_marketwide_sha256"],
        "coverage":coverage,
        "formal_leader_certified":False,
        "orders_enabled":False,
        "historical_independent_pit_certified":False,
    }
    if assessment_file is None:
        return {**base,"status":"FIVE_FACTOR_INPUT_NOT_AVAILABLE",
                "research_selected":0,"state_events":0,
                "data_stale":manifest["stale_warning"]}
    assessment=_read_assessment(assessment_file)
    if manifest["stale_warning"]:
        raise ValueError("FIVE_FACTOR_STALE_MARKET_PRICE_CANNOT_PROMOTE")
    observations,day=_validate(source,assessment,now=now)
    target=output/LEDGER
    # Existing WATCH price registry uses a separate file; never share or
    # overwrite it. Pre-create before opening SQLite for T5DATA permissions.
    if target.is_symlink() or target.parent.is_symlink() or (
        target.exists() and (
            not target.is_file() or target.stat().st_uid!=os.geteuid()
            or target.stat().st_mode & 0o077)):
        raise ValueError("FIVE_FACTOR_LEDGER_UNSAFE")
    if not target.exists():
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        os.close(fd)
    ledger=StateHistory(target)
    try:
        event=ledger.record("KR",day,observations)
    finally:
        ledger.close()
    # The existing feed is immutable, receiver-neutral and never allows
    # execution authority. Historical performance/PIT not inferred.
    research=state_history_handoff(target,market="KR",as_of=day,clock=now)
    # The generic ledger exporter retains last-known candidates. For daily
    # execution-facing research, never propagate a previously selected stock
    # as "current" if it has NO refreshed five-factor assessment today.
    prior=research["selected_candidates"]
    current=[candidate for candidate in prior
             if candidate.get("source_as_of")==day]
    suppressed=len(prior)-len(current)
    if suppressed:
        research["selected_candidates"]=current
        research["selection_count"]=len(current)
        research["unresolved_selected_tickers"]=sum(
            c["ticker"] is None for c in current)
        research["status"]=("SELECTED_CANDIDATES_RESEARCH_FEED"
                            if current else "NO_SELECTED_CANDIDATES")
        research["source_sha256"]=sha256(canonical({
            "selected":current,"events":research["state_changes"],
            "as_of":day,
        })).hexdigest()
    research["stale_prior_candidates_suppressed"]=suppressed
    # Attach receipt/date caveats to the actual receiver-neutral payload.
    # Local attestation is NOT independent issuer/market PIT certification.
    research.pop("content_sha256")
    research.update({
        "factor_assurance":ASSESSMENT,
        "factor_assessment_sha256":assessment["content_sha256"],
        "source_market_session":manifest["source_market_session"],
        "first_local_decision_at_utc":_utc(assessment["decision_at_utc"]).isoformat(),
        "formal_leader_certified":False,
        "historical_independent_pit_certified":False,
    })
    research["content_sha256"]=sha256(canonical(research)).hexdigest()
    outbox=output/CANDIDATE_OUTBOX
    if outbox.is_symlink():
        raise ValueError("FIVE_FACTOR_OUTBOX_SYMLINK")
    outbox.mkdir(mode=0o700,exist_ok=True)
    published=publish_versioned_handoff(research,outbox)
    checked=verify_handoff(Path(published["path"]),expected_market="KR")
    return {**base,
        "status":"FIVE_FACTOR_LOCAL_RESEARCH_STATES_PUBLISHED",
        "certification_level":ASSESSMENT,
        "research_selected":checked["selection_count"],
        "state_events":len(checked["state_changes"]),
        "states_in_observation":len(observations),
        "state_history_file":str(target),
        "neutral_outbox_file":published["path"],
        "delivery_status":published["status"],
        "execution_authority":False,
    }
