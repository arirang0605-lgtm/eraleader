"""One-way EraLeader selection -> downstream strategy candidate feed.

EraLeader owns discovery and selection *information*, not execution. A receiver
may use the watchlist for research or selected states for its independent
strategy; neither grants permission to place orders. Only existing local
registries or signed research snapshots are read. No recipient is selected
or coupled; an operator chooses a JSON publication file, normally within
EraLeader output. Receiver-side integration will be decided later.
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
import sqlite3
import stat
import tempfile

from .official_company_explorer import (_verified, build_explorer,
                                        canonical, BASIC, PEER)

SCHEMA = "eraleader.strategy_selection_handoff.v1"
MARKET_ZONES = {"KR": ZoneInfo("Asia/Seoul"), "US": ZoneInfo("America/New_York")}
STATES = frozenset(("WATCH", "POTENTIAL", "CONFIRMED",
                    "WEAKENING", "PAUSED", "EXITED"))
ACTIVE = frozenset(("POTENTIAL", "CONFIRMED"))
TRANSITIONS = {"POTENTIAL": "ADD_CANDIDATE",
               "CONFIRMED": "LEADER_CONFIRMED",
               "WEAKENING": "LEADER_WEAKENING",
               "PAUSED": "DATA_PAUSED",
               "EXITED": "EXITED_UNIVERSE",
               "WATCH": "WATCH_ONLY"}
KR_CODE = re.compile(r"[0-9]{6}\Z")
KRX_OBSERVED_CODE = re.compile(r"[A-Z0-9]{6}\Z")
US_CODE = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")
INTERNAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}\Z")


def _at(value: str, market: str) -> datetime:
    if type(value) is not str:
        raise ValueError("HANDOFF_SOURCE_TIME_REQUIRED")
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(
                tzinfo=MARKET_ZONES[market]).astimezone(timezone.utc)
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("HANDOFF_SOURCE_TIME_INVALID") from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("HANDOFF_SOURCE_TIME_UNAWARE")
    return stamp.astimezone(timezone.utc)


def _now(clock: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if clock is None else clock
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("HANDOFF_AWARE_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _symbol(value: str, market: str) -> str:
    check = KR_CODE if market == "KR" else US_CODE
    if type(value) is not str or check.fullmatch(value) is None:
        raise ValueError("HANDOFF_TRADING_TICKER_INVALID")
    return value


def _identity(value: str) -> str:
    if type(value) is not str or INTERNAL_ID.fullmatch(value) is None:
        raise ValueError("HANDOFF_PERMANENT_SECURITY_ID_INVALID")
    return value


def _identity_tickers(source: Path | None, *, market: str,
                      as_of: str, now: datetime) -> dict[str,str]:
    if source is None:
        return {}
    if (not source.is_absolute() or source.is_symlink() or
            not source.is_file() or any(p.is_symlink() for p in source.parents)):
        raise ValueError("HANDOFF_IDENTITY_LEDGER_UNSAFE")
    # Reuse the actual PIT membership reader, including delisting and ticker
    # changes. Never infer a trading symbol from an internal company ID.
    from .offline_pit import OfflineLedger
    if len(as_of) == 10:
        cutoff = datetime.combine(date.fromisoformat(as_of),
                                  datetime.max.time(),tzinfo=MARKET_ZONES[market])
        cutoff = min(cutoff.astimezone(timezone.utc),now)
    else:
        cutoff = _at(as_of,market)
    db = OfflineLedger.open_readonly(source)
    try:
        snapshot = db.snapshot(cutoff.isoformat(),market=market)
    finally:
        db.close()
    return {_identity(sec):_symbol(row["ticker"],market)
            for sec,row in snapshot["members"].items()}


def _finalize(payload: dict, now: datetime) -> dict:
    payload.update({
        "schema": SCHEMA,
        "producer": "EraLeader",
        "generated_at_utc": now.isoformat(),
        "consumer_intent": "STRATEGY_CANDIDATE_UNIVERSE_ONLY",
        "execution_authority": False,
        "order_instruction": False,
        "broker_account": None,
        "research_only": True,
    })
    payload["content_sha256"] = sha256(canonical(payload)).hexdigest()
    return payload


def research_cohort_handoff(cohort: Path, *, request_day: str,
                            clock: datetime | None = None) -> dict:
    """Send real currently screened symbols as OBSERVATION, never selected."""
    if (not cohort.is_absolute() or cohort.is_symlink() or
            not cohort.is_dir() or
            any(path.is_symlink() for path in cohort.parents)):
        raise ValueError("HANDOFF_COHORT_DIRECTORY_UNSAFE")
    basic, _ = _verified(cohort / "basic_candidates_kr.json", BASIC)
    peers, _ = _verified(cohort / "industry_peers_kr.json", PEER)
    now = _now(clock)
    source = build_explorer(basic, peers, request_day=request_day, now=now)
    # A later repeat with the same immutable sources must be idempotent;
    # the explorer's page-generation clock is not part of source identity.
    source_digest = sha256(canonical({
        "basic":source["source_candidate_sha256"],
        "industry":source["source_industry_sha256"],
        "market_session":source["source_market_session"],
    })).hexdigest()
    observed = []
    for row in source["companies"]:
        observed.append({
            "market": "KR", "security_id": _symbol(row["code"], "KR"),
            "name": row["name"], "selection_state": "WATCH",
            "category": "RESEARCH_OBSERVATION_NOT_LEADER_SELECTION",
            "research_order": row["observed_order"],
            "score_100": None,
            "source_market_session": source["source_market_session"],
            "first_known_at_utc": source["industry_decision_at_utc"],
            "evidence": {"candidate_sha256": source["source_candidate_sha256"],
                         "industry_sha256": source["source_industry_sha256"]},
        })
    return _finalize({
        "market": "KR",
        "source_kind": "OFFICIAL_PRICE_CFS_INDUSTRY_RESEARCH",
        "as_of": source["source_market_session"],
        "source_observed_as_of": source["source_market_session"],
        "source_decision_at_utc": source["industry_decision_at_utc"],
        "source_sha256": source_digest,
        "data_stale": source["stale_warning"],
        "selected_candidates": [],
        "research_watchlist": observed,
        "state_changes": [],
        "selection_count": 0,
        "watchlist_count": len(observed),
        "status": "WATCHLIST_ONLY_NO_VERIFIED_LEADER_SELECTION",
    }, now)



def marketwide_research_handoff(path: Path, *, request_day: str,
                                clock: datetime | None = None) -> dict:
    """Forward current full-KRX price WATCH20; never promote incomplete factors."""
    from .official_marketwide_coverage import SCHEMA as COVERAGE
    now = _now(clock)
    if (not path.is_absolute() or path.is_symlink() or not path.is_file() or
            any(p.is_symlink() for p in path.parents) or
            path.stat().st_uid != os.geteuid() or
            path.stat().st_size > 5_000_000):
        raise ValueError("HANDOFF_MARKETWIDE_FILE_UNSAFE")
    def no_duplicate(pairs):
        output = {}
        for key,value in pairs:
            if key in output:
                raise ValueError("HANDOFF_MARKETWIDE_DUPLICATE_FIELD")
            output[key] = value
        return output
    report = json.loads(path.read_bytes(),object_pairs_hook=no_duplicate,
                        parse_constant=lambda _: (_ for _ in ()).throw(
                            ValueError("HANDOFF_MARKETWIDE_NONFINITE")))
    fingerprint = report.get("content_sha256")
    original = dict(report)
    original.pop("content_sha256",None)
    if (report.get("schema") != COVERAGE or
            fingerprint != sha256(canonical(original)).hexdigest() or
            report.get("research_only") is not True or
            report.get("full_market_composite_rank_available") is not False or
            report.get("official_leaders") != 0 or
            type(report.get("securities")) is not list or
            len(report["securities"]) != report.get("official_krx_observed")):
        raise ValueError("HANDOFF_MARKETWIDE_SOURCE_INVALID")
    if (len(request_day) != 10 or
            date.fromisoformat(request_day) > now.astimezone(
                MARKET_ZONES["KR"]).date() or
            _at(report["source_decision_at_utc"],"KR") > now or
            _at(report["built_at_utc"],"KR") > now or
            date.fromisoformat(report["market_session"]) >
                date.fromisoformat(request_day)):
        raise ValueError("HANDOFF_MARKETWIDE_FUTURE_DATA")
    watch = []
    for item in report["securities"]:
        rank = item["price_top20_watch_rank"]
        if rank is None:
            continue
        code = item["security_id"]
        if (type(code) is not str or KRX_OBSERVED_CODE.fullmatch(code) is None):
            raise ValueError("HANDOFF_MARKETWIDE_KRX_CODE_INVALID")
        if (type(rank) is not int or not 1<=rank<=20 or
                item.get("verified_leader_state") is not None or
                item.get("formal_leader_score_100") is not None):
            raise ValueError("HANDOFF_MARKETWIDE_FALSE_LEADER")
        watch.append({
            "market":"KR","security_id":code,"name":item["name"],
            "selection_state":"WATCH",
            "category":"RESEARCH_OBSERVATION_NOT_LEADER_SELECTION",
            "research_order":rank,"score_100":None,
            "source_market_session":report["market_session"],
            "first_known_at_utc":report["source_decision_at_utc"],
            "evidence":{"marketwide_coverage_sha256":fingerprint},
        })
    watch.sort(key=lambda x:x["research_order"])
    if [x["research_order"] for x in watch] != list(range(1,len(watch)+1)):
        raise ValueError("HANDOFF_MARKETWIDE_NONCONTIGUOUS_PRICE_ORDER")
    # The 50-point score is an explicitly separate research *comparison*.
    # Never turn this into a POTENTIAL/CONFIRMED strategy candidate.
    security_rows={r["security_id"]:r for r in report["securities"]}
    research=[]
    for item in report.get("two_factor_research_top20",[]):
        code=item.get("security_id")
        score=item.get("observed_score_50")
        rank=item.get("research_order")
        if (code not in security_rows or
                item.get("name") != security_rows[code]["name"] or
                item.get("official_leader") is not False or
                type(score) not in (int,float) or
                not math.isfinite(score) or not 0<=score<=50 or
                type(rank) is not int or not 1<=rank<=20):
            raise ValueError("HANDOFF_RESEARCH_50_POINT_INPUT_INVALID")
        observed=security_rows[code]
        if (observed.get("two_factor_research_50")!=score or
                observed.get("two_factor_research_rank")!=rank):
            raise ValueError("HANDOFF_RESEARCH_SCORE_COHORT_MISMATCH")
        research.append({
            "market":"KR","security_id":code,"name":item["name"],
            "research_order":rank,"observed_score_50":float(score),
            "selection_state":"WATCH","score_100":None,
            "strategy_research_allowed":False,
            "research_basis":"PRICE_25_EARNINGS_25_RESEARCH_ONLY",
            "peer_revenue_yoy_rank":observed.get("peer_revenue_yoy_rank"),
            "peer_revenue_yoy_denominator":observed.get("peer_revenue_yoy_denominator"),
            "source_market_session":report["market_session"],
            "first_known_at_utc":report["built_at_utc"],
        })
    research.sort(key=lambda r:r["research_order"])
    if [r["research_order"] for r in research]!=list(range(1,len(research)+1)):
        raise ValueError("HANDOFF_RESEARCH_50_POINT_ORDER_INVALID")
    technical=[]
    changes=report.get("watch_changes_research")
    if changes is not None:
        if (type(changes) is not dict or
                changes.get("observations_only_no_leader_state_transition") is not True or
                changes.get("current_market_session")!=report["market_session"] or
                any(type(changes.get(k)) is not list or len(changes[k])>20
                    for k in ("new_technical_watch_events",
                              "left_price_watch_observations",
                              "existing_watch_rank_changes")) or
                changes.get("new_count") != len(changes["new_technical_watch_events"]) or
                changes.get("left_count") != len(changes["left_price_watch_observations"]) or
                changes.get("rank_changed_count") != len(changes["existing_watch_rank_changes"])):
            raise ValueError("HANDOFF_TECHNICAL_ROTATION_SOURCE_INVALID")
        in_watch={r["security_id"] for r in watch}
        for event in changes["new_technical_watch_events"]:
            code=event.get("security_id")
            if (code not in in_watch or event.get("kind")!="NEW_TECHNICAL_WATCH"):
                raise ValueError("HANDOFF_NEW_WATCH_SOURCE_INVALID")
            technical.append(("NEW_TECHNICAL_WATCH",code))
        for event in changes["left_price_watch_observations"]:
            code=event.get("security_id")
            if (code in in_watch or
                    event.get("status")!="DROPPED_FROM_PRICE_WATCH_NOT_DELISTED_OR_SOLD"):
                raise ValueError("HANDOFF_LEFT_WATCH_SOURCE_INVALID")
            technical.append(("LEFT_TECHNICAL_WATCH",code))
        for event in changes["existing_watch_rank_changes"]:
            code=event.get("security_id")
            if code not in in_watch:
                raise ValueError("HANDOFF_RANK_CHANGE_SOURCE_INVALID")
            technical.append(("PRICE_WATCH_RANK_MOVED",code))
    observations=[]
    for kind,code in technical:
        if type(code) is not str or KRX_OBSERVED_CODE.fullmatch(code) is None:
            raise ValueError("HANDOFF_TECHNICAL_ROTATION_ID_INVALID")
        observations.append({
            "market":"KR","security_id":code,"kind":kind,
            "observed_market_session":report["market_session"],
            "category":"PRICE_OBSERVATION_NOT_LEADER_STATE_TRANSITION",
            "first_known_at_utc":report["built_at_utc"],
            "score_100":None,"strategy_research_allowed":False,
        })
    return _finalize({
        "market":"KR","source_kind":"MARKETWIDE_KRX_DART_COVERAGE_RESEARCH",
        "as_of":request_day,"source_observed_as_of":report["market_session"],
        "source_decision_at_utc":report["source_decision_at_utc"],
        "source_sha256":fingerprint,
        "data_stale":report["market_session"] != request_day,
        "selected_candidates":[],"research_watchlist":watch,
        "two_factor_research_watchlist":research,
        "two_factor_research_count":len(research),
        "technical_watch_changes":observations,
        "technical_watch_change_count":len(observations),
        "state_changes":[],
        "selection_count":0,"watchlist_count":len(watch),
        "status":"WATCHLIST_ONLY_NO_VERIFIED_LEADER_SELECTION",
    },now)

def state_history_handoff(ledger: Path, *, market: str, as_of: str,
                          clock: datetime | None = None,
                          identity_ledger: Path | None = None) -> dict:
    """Export latest per-security registered state, with de-selection events."""
    if market not in MARKET_ZONES:
        raise ValueError("HANDOFF_MARKET_UNKNOWN")
    now = _now(clock)
    cutoff = _at(as_of, market)
    # Date-only source is a research-date ceiling; it is not an intraday PIT clock.
    if len(as_of) == 10:
        if date.fromisoformat(as_of) > now.astimezone(MARKET_ZONES[market]).date():
            raise ValueError("HANDOFF_ASOF_IN_FUTURE")
    elif cutoff > now:
        raise ValueError("HANDOFF_ASOF_IN_FUTURE")
    if (not ledger.is_absolute() or ledger.is_symlink() or
            not ledger.is_file() or any(p.is_symlink() for p in ledger.parents) or
            ledger.stat().st_uid != os.geteuid()):
        raise ValueError("HANDOFF_STATE_LEDGER_UNSAFE")
    db = sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        rows = db.execute(
            """SELECT security_id,as_of,previous,current,input_hash,
                      first_candidate_at,body
                 FROM state_history WHERE market=?""", (market,)).fetchall()
        changes = db.execute(
            """SELECT event_id,security_id,as_of,previous,current,reason
                 FROM state_events WHERE market=?""", (market,)).fetchall()
    finally:
        db.close()
    if len(rows) > 150_000 or len(changes) > 150_000:
        raise ValueError("HANDOFF_LEDGER_EXCEEDS_RESEARCH_LIMIT")
    tickers = _identity_tickers(identity_ledger,market=market,
                                as_of=as_of,now=now)
    chosen: dict[str,tuple[datetime,dict]] = {}
    for security_id, when, previous, state, fingerprint, first, body in rows:
        try:
            observed = _at(when, market)
        except ValueError:
            raise ValueError("HANDOFF_LEDGER_TIME_CORRUPT") from None
        if (observed > now or observed > cutoff and len(as_of) > 10 or
                len(as_of) == 10 and observed.astimezone(
                    MARKET_ZONES[market]).date() > date.fromisoformat(as_of)):
            continue
        _identity(security_id)
        if state not in STATES or previous not in STATES or not re.fullmatch(
                r"[0-9a-f]{64}", str(fingerprint)):
            raise ValueError("HANDOFF_STATE_ROW_INVALID")
        try:
            stored = json.loads(body)
        except (ValueError, TypeError):
            raise ValueError("HANDOFF_STATE_BODY_INVALID") from None
        if (type(stored) is not dict or
                stored.get("market") != market or
                stored.get("security_id") != security_id or
                stored.get("as_of") != when or
                stored.get("previous") != previous or
                stored.get("state") != state or
                stored.get("input_hash") != fingerprint or
                stored.get("first_candidate_at") != first or
                stored.get("model") != "stage4-pit-state-v0.1"):
            raise ValueError("HANDOFF_STATE_BODY_MISMATCH")
        score = stored.get("score")
        if state in ACTIVE and (type(score) not in (int,float) or not 0 <= score <= 100):
            raise ValueError("HANDOFF_SELECTED_SCORE_UNAVAILABLE")
        if first is not None and _at(first, market) > observed:
            raise ValueError("HANDOFF_FIRST_CANDIDATE_TIME_FUTURE")
        prior = chosen.get(security_id)
        if prior is None or observed > prior[0]:
            chosen[security_id] = (observed, stored)
        elif observed == prior[0]:
            raise ValueError("HANDOFF_DUPLICATE_SNAPSHOT")
    candidates = []
    for sec, (_, row) in sorted(chosen.items()):
        if row["state"] not in ACTIVE:
            continue
        ticker = tickers.get(sec)
        if ticker is None and (KR_CODE if market=="KR" else US_CODE).fullmatch(sec):
            ticker = sec
        candidates.append({
            "market": market, "security_id": sec, "ticker": ticker,
            "ticker_resolved": ticker is not None,
            "selection_state": row["state"],
            "score_100": row["score"],
            "first_candidate_at": row["first_candidate_at"],
            "source_as_of": row["as_of"],
            "model_version": row["model"],
            "state_input_sha256": row["input_hash"],
            "selection_reason": row["reason"],
            "strategy_research_allowed": ticker is not None,
        })
    messages = []
    for event_id, sec, when, previous, current, reason in changes:
        if len(as_of) == 10:
            if when[:10] != as_of:
                continue
        elif _at(when, market) > cutoff or _at(when, market) > now:
            continue
        _identity(sec)
        if current not in STATES or previous not in STATES:
            raise ValueError("HANDOFF_EVENT_STATE_INVALID")
        if not re.fullmatch(r"[0-9a-f]{24}", str(event_id)):
            raise ValueError("HANDOFF_EVENT_ID_INVALID")
        messages.append({
            "event_id": event_id,
            "market": market, "security_id": sec,
            "ticker": tickers.get(sec) or (sec if
                (KR_CODE if market=="KR" else US_CODE).fullmatch(sec) else None),
            "source_as_of": when, "previous": previous,
            "current": current, "event_type": TRANSITIONS[current],
            "reason": reason,
        })
    messages.sort(key=lambda x:(x["source_as_of"], x["security_id"]))
    source_sha = sha256(canonical({
        "selected": candidates, "events": messages, "as_of": as_of,
    })).hexdigest()
    return _finalize({
        "market": market,
        "source_kind": "LOCAL_STATE_HISTORY",
        "as_of": as_of,
        "source_observed_as_of": as_of,
        "source_decision_at_utc": now.isoformat(),
        "source_sha256": source_sha,
        "data_stale": None,
        "selected_candidates": candidates,
        "research_watchlist": [],
        "state_changes": messages,
        "selection_count": len(candidates),
        "unresolved_selected_tickers": sum(
            row["ticker"] is None for row in candidates),
        "watchlist_count": 0,
        "status": ("SELECTED_CANDIDATES_RESEARCH_FEED" if candidates
                   else "NO_SELECTED_CANDIDATES"),
    }, now)


def verify_handoff(path: Path, *, expected_market: str | None = None) -> dict:
    """Receiver-side reader: checksum and contract, never an execution intent."""
    if (not path.is_absolute() or path.is_symlink() or not path.is_file() or
            any(p.is_symlink() for p in path.parents) or
            path.stat().st_uid != os.geteuid() or
            path.stat().st_size > 3_000_000):
        raise ValueError("HANDOFF_FILE_UNSAFE")
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("HANDOFF_DUPLICATE_FIELD")
            result[name] = value
        return result
    source = path.read_bytes()
    payload = json.loads(source, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ValueError("HANDOFF_NONFINITE")))
    if type(payload) is not dict or source != canonical(payload) + b"\n":
        raise ValueError("HANDOFF_NONCANONICAL")
    digest = payload.get("content_sha256")
    original = dict(payload)
    original.pop("content_sha256", None)
    if (payload.get("schema") != SCHEMA or
            not isinstance(digest,str) or
            sha256(canonical(original)).hexdigest() != digest or
            payload.get("execution_authority") is not False or
            payload.get("order_instruction") is not False or
            payload.get("research_only") is not True or
            payload.get("broker_account") is not None or
            payload.get("consumer_intent") != "STRATEGY_CANDIDATE_UNIVERSE_ONLY" or
            payload.get("market") not in MARKET_ZONES or
            expected_market not in (None,payload.get("market"))):
        raise ValueError("HANDOFF_UNTRUSTED_OR_WRONG_MARKET")
    if (type(payload.get("selected_candidates")) is not list or
            type(payload.get("research_watchlist")) is not list or
            type(payload.get("state_changes")) is not list or
            payload.get("selection_count") != len(payload["selected_candidates"]) or
            payload.get("watchlist_count") != len(payload["research_watchlist"])):
        raise ValueError("HANDOFF_COUNTS_INCONSISTENT")
    if "two_factor_research_watchlist" in payload:
        research=payload["two_factor_research_watchlist"]
        if (payload.get("source_kind")!="MARKETWIDE_KRX_DART_COVERAGE_RESEARCH" or
                type(research) is not list or len(research)>20 or
                payload.get("two_factor_research_count")!=len(research)):
            raise ValueError("HANDOFF_50_RESEARCH_COUNTS_INVALID")
        for pos, row in enumerate(research,1):
            score=row.get("observed_score_50")
            if (row.get("research_order")!=pos or
                    type(row.get("security_id")) is not str or
                    KRX_OBSERVED_CODE.fullmatch(row["security_id"]) is None or
                    row.get("selection_state")!="WATCH" or
                    row.get("score_100") is not None or
                    row.get("strategy_research_allowed") is not False or
                    row.get("research_basis")!="PRICE_25_EARNINGS_25_RESEARCH_ONLY" or
                    type(score) not in (int,float) or not math.isfinite(score) or
                    not 0<=score<=50):
                raise ValueError("HANDOFF_50_RESEARCH_ROW_INVALID")
    if "technical_watch_changes" in payload:
        changes=payload["technical_watch_changes"]
        if (payload.get("source_kind")!="MARKETWIDE_KRX_DART_COVERAGE_RESEARCH" or
                type(changes) is not list or len(changes)>60 or
                payload.get("technical_watch_change_count")!=len(changes) or
                payload["state_changes"]):
            raise ValueError("HANDOFF_TECHNICAL_CHANGE_CONTRACT_INVALID")
        for row in changes:
            if (type(row) is not dict or
                    row.get("kind") not in (
                        "NEW_TECHNICAL_WATCH",
                        "LEFT_TECHNICAL_WATCH",
                        "PRICE_WATCH_RANK_MOVED") or
                    type(row.get("security_id")) is not str or
                    KRX_OBSERVED_CODE.fullmatch(row["security_id"]) is None or
                    row.get("observed_market_session")!=payload.get(
                        "source_observed_as_of") or
                    row.get("category")!="PRICE_OBSERVATION_NOT_LEADER_STATE_TRANSITION" or
                    row.get("score_100") is not None or
                    row.get("strategy_research_allowed") is not False or
                    "selection_state" in row):
                raise ValueError("HANDOFF_TECHNICAL_CHANGE_ROW_INVALID")
    for row in payload["selected_candidates"]:
        _identity(row["security_id"])
        ticker = row.get("ticker")
        if ticker is not None:
            _symbol(ticker,payload["market"])
        if (row.get("selection_state") not in ACTIVE or
                row.get("ticker_resolved") is not (ticker is not None) or
                row.get("strategy_research_allowed") is not (ticker is not None)):
            raise ValueError("HANDOFF_SELECTED_ROW_INVALID")
    for row in payload["research_watchlist"]:
        if (payload["market"] == "KR" and payload.get("source_kind") ==
                "MARKETWIDE_KRX_DART_COVERAGE_RESEARCH"):
            if (type(row.get("security_id")) is not str or
                    KRX_OBSERVED_CODE.fullmatch(row["security_id"]) is None):
                raise ValueError("HANDOFF_WATCH_CODE_INVALID")
        else:
            _symbol(row["security_id"],payload["market"])
        if row.get("selection_state") != "WATCH" or row.get("score_100") is not None:
            raise ValueError("HANDOFF_WATCH_MISLABEL")
    return payload



def publish_versioned_handoff(report: dict, outbox: Path) -> dict:
    """Project-neutral immutable daily selection feed directory.

    Repeated publication of the same source reuses its deterministic filename.
    A changed input SHA gets a different filename, never overwrites another
    release, and never writes to a receiver project's filesystem.
    """
    if (not outbox.is_absolute() or outbox.is_symlink() or
            not outbox.is_dir() or any(p.is_symlink() for p in outbox.parents)
            or outbox.stat().st_uid != os.geteuid()):
        raise ValueError("HANDOFF_OUTBOX_UNSAFE")
    market = report.get("market")
    moment = report.get("source_observed_as_of")
    pin = report.get("source_sha256")
    if (market not in MARKET_ZONES or type(moment) is not str or
            type(pin) is not str or re.fullmatch(r"[0-9a-f]{64}",pin) is None):
        raise ValueError("HANDOFF_VERSION_SOURCE_INVALID")
    try:
        observed = date.fromisoformat(moment[:10])
    except ValueError:
        raise ValueError("HANDOFF_VERSION_OBSERVED_DATE_INVALID") from None
    if moment != observed.isoformat() and moment[:10] != observed.isoformat():
        raise ValueError("HANDOFF_VERSION_OBSERVED_DATE_INVALID")
    # Multiple safe research-contract revisions can refer to the same immutable
    # market originals. Their JSON must occupy different immutable paths.
    semantic=dict(report)
    semantic.pop("generated_at_utc",None)
    semantic.pop("content_sha256",None)
    if report.get("source_kind")=="LOCAL_STATE_HISTORY":
        semantic.pop("source_decision_at_utc",None)
    contract_pin=sha256(canonical(semantic)).hexdigest()[:12]
    filename=(f"{market}_{observed.strftime('%Y%m%d')}_"
              f"{pin[:12]}_{contract_pin}.json")
    result = publish_handoff(report,outbox / filename)
    result["outbox_mode"] = "IMMUTABLE_VERSIONED_RESEARCH_FEED"
    return result

def publish_handoff(report: dict, output: Path) -> dict:
    """Publish immutable receiver-neutral JSON at an explicit output location."""
    if (not output.is_absolute() or output.is_symlink() or
            not output.parent.is_dir() or output.parent.is_symlink() or
            any(p.is_symlink() for p in output.parents) or
            output.parent.stat().st_uid != os.geteuid()):
        raise ValueError("HANDOFF_DESTINATION_UNSAFE")
    if type(report) is not dict:
        raise ValueError("HANDOFF_PREPUBLICATION_INVALID")
    source = dict(report)
    digest = source.pop("content_sha256",None)
    if (report.get("schema") != SCHEMA or type(digest) is not str or
            digest != sha256(canonical(source)).hexdigest() or
            report.get("market") not in MARKET_ZONES or
            report.get("execution_authority") is not False or
            report.get("order_instruction") is not False or
            report.get("research_only") is not True or
            report.get("broker_account") is not None or
            report.get("consumer_intent") != "STRATEGY_CANDIDATE_UNIVERSE_ONLY" or
            type(report.get("selected_candidates")) is not list or
            type(report.get("research_watchlist")) is not list or
            type(report.get("state_changes")) is not list or
            report.get("selection_count") != len(report["selected_candidates"]) or
            report.get("watchlist_count") != len(report["research_watchlist"])):
        raise ValueError("HANDOFF_PREPUBLICATION_INVALID")
    payload = canonical(report) + b"\n"
    if output.exists():
        previous = verify_handoff(output,expected_market=report.get("market"))
        comparable = dict(report)
        comparable["generated_at_utc"] = previous["generated_at_utc"]
        # Source decision is equal for research cohorts. A new state snapshot
        # can legitimately arrive later, even if the observation date is same.
        if report.get("source_kind") == "LOCAL_STATE_HISTORY":
            comparable["source_decision_at_utc"] = previous["source_decision_at_utc"]
        comparable.pop("content_sha256",None)
        comparable["content_sha256"] = sha256(canonical(comparable)).hexdigest()
        if previous != comparable:
            raise ValueError("HANDOFF_NEW_SELECTION_REQUIRES_VERSIONED_DESTINATION")
        return {"status":"ALREADY_DELIVERED","path":str(output),
                "content_sha256":previous["content_sha256"],
                "selected_count":previous["selection_count"]}
    fd, scratch = tempfile.mkstemp(prefix=".strategy_handoff_",dir=output.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        fd=-1
        if output.exists() or output.is_symlink():
            raise ValueError("HANDOFF_DESTINATION_APPEARED")
        os.rename(scratch,output)
    finally:
        if fd>=0:
            os.close(fd)
        if os.path.exists(scratch):
            os.unlink(scratch)
    verify_handoff(output,expected_market=report["market"])
    return {"status":"DELIVERED_TO_INBOX","path":str(output),
            "content_sha256":report["content_sha256"],
            "selected_count":report["selection_count"],
            "watchlist_count":report["watchlist_count"]}
