"""KRX-wide observed securities joined to available DART finance/industry facts.

This is a *coverage* ledger, not an investment ranking. Missing factors stay
None; a ten-company financial sample is not silently extended to the market.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import math
import os
import re

from .delivery import BASE_CSS
from .official_api_pit_bridge import verified_capture, _krx_frame
from .official_dart_multi_company import _all_pinned, source_eligible_universe
from .official_company_explorer import _verified, BASIC, PEER, canonical
from .official_dart_financials import verify_dart_financial, annual_growth_diagnostic
from .official_dart_industry import verify_company_profile
from .kiwoom_investor_flow import verify_flow
from .discovery import run_id_for, score_price_observations, detect_watch_changes
from .data import LEGACY_DEFAULT, read_market_bars, validate_bars
from datetime import date
from zoneinfo import ZoneInfo
import pandas as pd

SCHEMA = "eraleader.official_kr_marketwide_factor_coverage.v1"
CODE = re.compile(r"[A-Za-z0-9]{6}\Z")



def attach_observed_industry_peers(observed: dict[str,dict]) -> dict:
    """Peer diagnostics within captured CURRENT DART cohorts, not sector totals.

    A group with one member has no peer leadership rank. Missing revenue /
    operating growth is omitted from that metric's denominator, never zero.
    """
    grouped={}
    for row in observed.values():
        row.update({
            "observed_industry_sample_size": None,
            "peer_revenue_yoy_rank": None,
            "peer_revenue_yoy_denominator": None,
            "peer_operating_yoy_rank": None,
            "peer_operating_yoy_denominator": None,
        })
        industry=row.get("industry_code")
        if industry is not None and row.get("current_dart_directory_matched") is True:
            grouped.setdefault(industry,[]).append(row)
    pairs=0
    revenue_compared=0
    operating_compared=0
    groups=[]
    for industry,group in sorted(grouped.items()):
        if len(group)<2:
            continue
        pairs+=len(group)
        groups.append({"current_dart_industry_code":industry,
                       "captured_company_count":len(group)})
        for row in group:
            row["observed_industry_sample_size"]=len(group)
        for metric,rank_key,denom_key in (
                ("revenue_yoy","peer_revenue_yoy_rank","peer_revenue_yoy_denominator"),
                ("operating_income_yoy","peer_operating_yoy_rank","peer_operating_yoy_denominator")):
            valid=[r for r in group if r.get(metric) is not None]
            if len(valid)<2:
                continue
            if any(type(r[metric]) not in (int,float) or
                   not math.isfinite(r[metric]) for r in valid):
                raise ValueError("MARKETWIDE_PEER_NONFINITE_METRIC")
            valid.sort(key=lambda r:(-r[metric],r["security_id"]))
            last=None
            rank=0
            for pos,item in enumerate(valid,1):
                if last is None or item[metric]!=last:
                    rank=pos
                item[rank_key]=rank
                item[denom_key]=len(valid)
                last=item[metric]
            if metric=="revenue_yoy":
                revenue_compared+=len(valid)
            else:
                operating_compared+=len(valid)
    return {
        "same_industry_sample_groups":groups,
        "same_industry_sample_company_count":pairs,
        "revenue_yoy_peer_evaluable":revenue_compared,
        "operating_income_yoy_peer_evaluable":operating_compared,
        "industry_comparison_scope":"CAPTURED_CURRENT_COMPANIES_ONLY_NOT_OFFICIAL_SECTOR_GROWTH",
    }


def attach_matched_session_investor_flow(observed: dict[str,dict],
                                         flow_folder: Path, *,
                                         market_session: str,
                                         decision_at: datetime) -> dict:
    """Join existing read-only Kiwoom ka10059 only for the exact KRX session.

    Provider aggregate share quantities are observations, not investable ranks;
    a future/different observed day is kept as N/A instead of being backdated.
    """
    from .kiwoom_investor_flow import canonical as flow_canonical
    if (not flow_folder.is_absolute() or flow_folder.is_symlink() or
            not flow_folder.is_dir() or
            any(p.is_symlink() for p in flow_folder.parents)):
        raise ValueError("MARKETWIDE_FLOW_SOURCE_UNSAFE")
    def pairs_unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError("MARKETWIDE_FLOW_DUPLICATE_FIELD")
            result[key]=value
        return result
    manifest_file=flow_folder/"manifest.json"
    if not manifest_file.is_file() or manifest_file.is_symlink():
        raise ValueError("MARKETWIDE_FLOW_MANIFEST_MISSING")
    payload=manifest_file.read_bytes()
    manifest=json.loads(payload,object_pairs_hook=pairs_unique)
    original=dict(manifest)
    pin=original.pop("content_sha256",None)
    if (pin != sha256(flow_canonical(original)).hexdigest() or
            manifest.get("schema")!="eraleader.kiwoom_selected_flow_capture_manifest.v1" or
            manifest.get("provider")!="KIWOOM_REST_KA10059" or
            manifest.get("unit")!="shares" or
            manifest.get("environment_mode") not in ("demo","real") or
            manifest.get("trading_enabled") is not False or
            type(manifest.get("files")) is not list or
            len(manifest["files"])!=manifest.get("companies") or
            len(manifest["files"])>20):
        raise ValueError("MARKETWIDE_FLOW_MANIFEST_INVALID")
    aligned=manifest["requested_day"]==market_session.replace("-","")
    count=0
    mismatched=0
    seen=set()
    for entry in manifest["files"]:
        code=entry.get("security_id")
        if (type(code) is not str or code in seen or code not in observed or
                entry.get("filename")!=code+".json" or
                not re.fullmatch(r"[0-9]{6}",code)):
            raise ValueError("MARKETWIDE_FLOW_SECURITY_MISMATCH")
        seen.add(code)
        path=flow_folder/(code+".json")
        if not path.is_file() or path.is_symlink():
            raise ValueError("MARKETWIDE_FLOW_RECEIPT_MISSING")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=entry.get("sha256"):
            raise ValueError("MARKETWIDE_FLOW_RECEIPT_SHA_INVALID")
        detail=json.loads(raw,object_pairs_hook=pairs_unique)
        verify_flow(detail,decision_at=decision_at)
        if (detail["security_id"]!=code or
                detail["environment_mode"]!=manifest["environment_mode"] or
                detail["requested_day"]!=manifest["requested_day"] or
                detail["observed_rows"]!=entry["rows"]):
            raise ValueError("MARKETWIDE_FLOW_RECEIPT_CONFLICT")
        row=observed[code]
        row["flow_source_sha256"]=detail["content_sha256"]
        if (not aligned or detail["latest_observed_day"]!=
                market_session.replace("-","")):
            row["flow_source_quality"]="MISMATCHED_DAY_NOT_USABLE"
            mismatched+=1
            continue
        row["flow_source_quality"]="EXACT_SESSION_20_OBSERVATIONS_RESEARCH_ONLY"
        window=detail["flow_20_observed_sessions"]
        foreign=window.get("foreign_net_shares")
        institution=window.get("institution_net_shares")
        if type(foreign) is not int or type(institution) is not int:
            row["flow_source_quality"]="INCOMPLETE_20_OBSERVATIONS_NA"
            continue
        row["foreign_flow"]=foreign
        row["institutional_flow"]=institution
        row["flow_unit"]="shares_20_observed_sessions"
        count+=1
    return {
        "flow_source_manifest_sha256":sha256(payload).hexdigest(),
        "flow_capture_companies_checked":len(seen),
        "flow_matched_session_companies":count,
        "flow_mismatched_session_companies":mismatched,
        "flow_certification":"FIRST_LOCAL_RECEIPT_RESEARCH_ONLY_NOT_HISTORIC_PIT",
    }


def compare_official_price_watch(previous: dict, current: dict) -> dict:
    """Observed WATCH rotations only; use existing discovery event detector.

    No historical state rewrite or POTENTIAL/CONFIRMED promotion. Market dates
    are observed sessions, while evidence first-known times may be later.
    """
    for label, snap in (("PREVIOUS",previous),("CURRENT",current)):
        if (type(snap) is not dict or snap.get("source_market")!="KR" or
                snap.get("classification_quality")!="PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED" or
                type(snap.get("rows")) is not list or
                snap.get("run_id") != run_id_for(
                    "KR",snap["as_of_requested"],snap["rows"]) or
                snap.get("official_api_evidence",{}).get(
                    "historic_universe_pit_verified") is not False or
                snap.get("official_api_evidence",{}).get("official_leaders")!=0):
            raise ValueError("MARKETWIDE_"+label+"_WATCH_UNVERIFIED")
        ranks=[r.get("rank") for r in snap["rows"]]
        if (len(snap["rows"])>20 or not snap["rows"] or
                ranks!=list(range(1,len(ranks)+1)) or
                len({r["security_id"] for r in snap["rows"]})!=len(ranks) or
                any(r.get("state")!="WATCH" for r in snap["rows"])):
            raise ValueError("MARKETWIDE_"+label+"_WATCH_ROWS_INVALID")
        if snap["market_last_observation"]!=snap[
                "official_api_evidence"]["api_observation_day"]:
            raise ValueError("MARKETWIDE_"+label+"_WATCH_DAY_INVALID")
    earlier=date.fromisoformat(previous["market_last_observation"])
    latest=date.fromisoformat(current["market_last_observation"])
    if earlier>=latest:
        raise ValueError("MARKETWIDE_PRICE_WATCH_REQUIRES_NEWER_SESSION")
    new_events=detect_watch_changes(previous,current,current["run_id"])
    new_ids={r["security_id"] for r in current["rows"]}
    removed=[{"security_id":r["security_id"],"name":r["name"],
              "previous_price_rank":r["rank"],
              "status":"DROPPED_FROM_PRICE_WATCH_NOT_DELISTED_OR_SOLD"}
             for r in previous["rows"] if r["security_id"] not in new_ids]
    previous_rank={r["security_id"]:r["rank"] for r in previous["rows"]}
    rank_moves=[{"security_id":r["security_id"],"name":r["name"],
                 "previous_price_rank":previous_rank[r["security_id"]],
                 "current_price_rank":r["rank"]}
                for r in current["rows"] if r["security_id"] in previous_rank and
                r["rank"]!=previous_rank[r["security_id"]]]
    return {
        "previous_market_session":earlier.isoformat(),
        "current_market_session":latest.isoformat(),
        "previous_watch_run_id":previous["run_id"],
        "current_watch_run_id":current["run_id"],
        "new_technical_watch_events":new_events,
        "left_price_watch_observations":removed,
        "existing_watch_rank_changes":rank_moves,
        "new_count":len(new_events),"left_count":len(removed),
        "rank_changed_count":len(rank_moves),
        "observations_only_no_leader_state_transition":True,
    }

def build_marketwide_coverage(cohort: Path, capture_root: Path, *,
                              clock: datetime | None = None,
                              extra_cfs_manifests: tuple[Path, ...] = (),
                              extra_industry_manifests: tuple[Path, ...] = (),
                              full_price_lookback: bool = False,
                              legacy_root: Path = LEGACY_DEFAULT,
                              kiwoom_flow_folder: Path | None = None,
                              previous_watch_file: Path | None = None) -> dict:
    """Recheck pinned originals and join every observed KRX issue exactly once."""
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("MARKETWIDE_AWARE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if (not cohort.is_absolute() or cohort.is_symlink() or not cohort.is_dir() or
            not capture_root.is_absolute() or capture_root.is_symlink() or
            any(p.is_symlink() for p in cohort.parents) or
            any(p.is_symlink() for p in capture_root.parents)):
        raise ValueError("MARKETWIDE_SOURCE_DIRECTORY_UNSAFE")
    basic, _ = _verified(cohort / "basic_candidates_kr.json", BASIC)
    peers, _ = _verified(cohort / "industry_peers_kr.json", PEER)
    snapshot = json.loads((cohort / "kr_latest.json").read_bytes())
    evidence = snapshot.get("official_api_evidence")
    if (not isinstance(evidence, dict) or
            evidence.get("historic_universe_pit_verified") is not False or
            evidence.get("official_leaders") != 0 or
            snapshot.get("classification_quality") !=
            "PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED"):
        raise ValueError("MARKETWIDE_SOURCE_NOT_RESEARCH")
    if (run_id_for("KR",snapshot["as_of_requested"],snapshot["rows"])
            != snapshot.get("run_id")):
        raise ValueError("MARKETWIDE_PRICE_SNAPSHOT_TAMPERED")
    observed = evidence["api_observation_day"]
    if (basic["market_session"] != observed or peers["market_session"] != observed or
            basic["source_watch_run_id"] != snapshot.get("run_id") or
            peers["baseline_candidate_sha256"] != basic["content_sha256"]):
        raise ValueError("MARKETWIDE_COHORT_SOURCE_MISMATCH")
    decision = datetime.fromisoformat(evidence["decision_at"].replace("Z", "+00:00"))
    if decision.tzinfo is None or decision > now:
        raise ValueError("MARKETWIDE_SOURCE_FUTURE")
    matched, directory, audit = source_eligible_universe(
        cohort / "official_api_pit_research.json", capture_root, decision=now)
    if audit["market_session"] != observed:
        raise ValueError("MARKETWIDE_SOURCE_DAY_MISMATCH")
    pins = _all_pinned(capture_root)
    all_rows = {}
    current_frames = []
    for source in ("krx-kospi", "krx-kosdaq"):
        records = [x for x in evidence["sources"] if x["source"] == source]
        if len(records) != 1 or records[0]["first_receipt_sha256"] not in pins:
            raise ValueError("MARKETWIDE_KRX_PIN_MISSING")
        pin = records[0]["first_receipt_sha256"]
        meta, payload = verified_capture(pins[pin], source, pin, now)
        frame = _krx_frame(source, meta, payload)
        current_frames.append(frame)
        if len(frame) != records[0]["row_count"]:
            raise ValueError("MARKETWIDE_KRX_ROW_MISMATCH")
        for row in frame.itertuples(index=False):
            code = row.security_id
            if (not CODE.fullmatch(code) or code in all_rows or
                    row.session.date().isoformat() != observed):
                raise ValueError("MARKETWIDE_SECURITY_DUPLICATE_OR_WRONG_DATE")
            all_rows[code] = {
                "security_id": code, "name": row.name, "venue": row.venue,
                "market_session": observed, "close": float(row.close),
                "turnover": float(row.turnover), "market_cap": float(row.market_cap),
                "market_traded": bool(row.volume > 0),
                "current_dart_directory_matched": code in matched,
                "revenue_yoy": None, "operating_income_yoy": None,
                "revenue_growth_acceleration": None,
                "industry_code": None, "institutional_flow": None,
                "foreign_flow": None, "price_top20_watch_rank": None,
                "price_strength_25": None, "earnings_research_25": None,
                "two_factor_research_50": None, "two_factor_research_rank": None,
                "partial_financial_observation_order": None,
                "formal_leader_score_100": None, "verified_leader_state": None,
            }
    if len(all_rows) != audit["krx_rows"]:
        raise ValueError("MARKETWIDE_OBSERVED_COUNT_MISMATCH")
    prices = snapshot["rows"]
    if (len({p["security_id"] for p in prices}) != len(prices) or
            len({p["security_id"] for p in basic["comparisons"]}) !=
            len(basic["comparisons"])):
        raise ValueError("MARKETWIDE_DUPLICATE_ANALYSIS")
    for price in prices:
        item=all_rows[price["security_id"]]
        item["price_top20_watch_rank"] = price["rank"]
        item["price_strength_25"] = price.get("price_strength_25")
    for company in basic["comparisons"]:
        code = company["security_id"]
        if code not in matched or company["name"] != all_rows[code]["name"]:
            raise ValueError("MARKETWIDE_FINANCIAL_ISSUER_MISMATCH")
        if datetime.fromisoformat(company[
                "first_financial_locally_received_at_utc"]) > now:
            raise ValueError("MARKETWIDE_FUTURE_FINANCIAL")
        item = all_rows[code]
        item["price_strength_25"] = company.get("price_strength_25")
        item["revenue_yoy"] = company["revenue_yoy"]
        item["operating_income_yoy"] = company["operating_income_yoy"]
        item["revenue_growth_acceleration"] = company["revenue_yoy_acceleration"]
        item["partial_financial_observation_order"] = company["comparison_order"]
    observed_industry = set()
    for company in peers["companies"]:
        code = company["stock_code"]
        if (code in observed_industry or code not in all_rows or
                all_rows[code]["revenue_yoy"] is None):
            raise ValueError("MARKETWIDE_INDUSTRY_JOIN_INVALID")
        observed_industry.add(code)
        all_rows[code]["industry_code"] = company["current_industry_code"]
    if (observed_industry != {x["security_id"] for x in basic["comparisons"]} or
            peers["selected_companies"] != len(observed_industry)):
        raise ValueError("MARKETWIDE_FINANCE_INDUSTRY_COHORT_MISMATCH")
    extras = set()
    incomplete = set()
    manifest_pins = []
    for manifest_file in extra_cfs_manifests:
        if (not manifest_file.is_absolute() or manifest_file.is_symlink() or
                not manifest_file.is_file() or
                any(p.is_symlink() for p in manifest_file.parents)):
            raise ValueError("MARKETWIDE_EXTRA_MANIFEST_UNSAFE")
        raw = manifest_file.read_bytes()
        source = json.loads(raw)
        if (source.get("schema") != "eraleader.dart_bounded_multi_company_cfs.v1" or
                source.get("official_market", {}).get("market_session") != observed or
                source.get("research_only") is not True or
                source.get("real_investment_leader_ranked") is not False):
            raise ValueError("MARKETWIDE_EXTRA_CFS_SOURCE_INVALID")
        manifest_pins.append(sha256(raw).hexdigest())
        for firm in source["companies"]:
            code = firm["stock_code"]
            if (code in extras or code not in matched or
                    code not in all_rows or
                    all_rows[code]["revenue_yoy"] is not None or
                    firm["name"] != all_rows[code]["name"] or
                    code in incomplete):
                raise ValueError("MARKETWIDE_EXTRA_CFS_IDENTITY_OR_DUPLICATE")
            if not firm["research_annual_cfs_complete"]:
                incomplete.add(code)
                continue
            annual = {}
            for receipt in firm["annual_reports"]:
                year = receipt["fiscal_year"]
                pin = receipt["first_receipt_sha256"]
                if year in annual or pin not in pins:
                    raise ValueError("MARKETWIDE_EXTRA_CFS_RECEIPT_MISSING")
                verified = verify_dart_financial(pins[pin], pin,
                                                 decision_at=now,
                                                 directory=directory)
                if (verified["stock_code"] != code or
                        verified["year"] != year or
                        verified["statement"] != "CFS" or
                        verified["report_code"] != "11011"):
                    raise ValueError("MARKETWIDE_EXTRA_CFS_WRONG_ISSUER")
                annual[year] = verified
            years = sorted(annual)
            if len(years) != 2 or years[1] != years[0] + 1:
                raise ValueError("MARKETWIDE_EXTRA_CFS_TWO_CONSECUTIVE_YEARS_REQUIRED")
            growth = annual_growth_diagnostic(annual[years[0]],annual[years[1]])
            item = all_rows[code]
            item["revenue_yoy"] = growth["research_metrics"]["revenue_yoy"]
            item["operating_income_yoy"] = growth["research_metrics"]["operating_income_yoy"]
            item["financial_receipt_years"] = years
            extras.add(code)
    extra_industry = set()
    industry_pins = []
    for manifest_file in extra_industry_manifests:
        if (not manifest_file.is_absolute() or manifest_file.is_symlink() or
                not manifest_file.is_file() or
                any(p.is_symlink() for p in manifest_file.parents)):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_UNSAFE")
        raw = manifest_file.read_bytes()
        source = json.loads(raw)
        if (source.get("schema") != "eraleader.dart_industry_profile_cohort.v1" or
                source.get("source_directory_sha256") != directory[1] or
                source.get("historic_industry_pit_certified") is not False):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_INVALID")
        industry_pins.append(sha256(raw).hexdigest())
        if (source.get("companies_requested") != len(source.get("companies",[]))):
            raise ValueError("MARKETWIDE_INDUSTRY_MANIFEST_COUNT")
        for firm in source["companies"]:
            code = firm["stock_code"]
            if (code not in matched or code in extra_industry or
                    code in observed_industry or code not in extras):
                raise ValueError("MARKETWIDE_INDUSTRY_COMPANY_NOT_FINANCIAL")
            extra_industry.add(code)
            pin=firm.get("first_receipt_sha256")
            if pin is None:
                continue
            if pin not in pins:
                raise ValueError("MARKETWIDE_INDUSTRY_FIRST_PIN_MISSING")
            profile = verify_company_profile(pins[pin],pin,
                       directory=directory,decision_at=now)
            if (profile["stock_code"] != code or
                    profile["current_dart_industry_code"] != firm.get(
                        "current_dart_industry_code") or
                    profile["current_dart_industry_code"] is None):
                raise ValueError("MARKETWIDE_INDUSTRY_RECEIPT_MISMATCH")
            all_rows[code]["industry_code"] = profile["current_dart_industry_code"]
    # Optional whole-market 3/6-month price ranking. Reuse the *same*
    # research model as the original verified official PRICE WATCH20. Its
    # pre-session lookback is legacy local cache, never certified historical PIT.
    full_price_evaluable = 0
    if full_price_lookback:
        if (not isinstance(legacy_root,Path) or not legacy_root.is_absolute() or
                legacy_root.is_symlink()):
            raise ValueError("MARKETWIDE_PRICE_CACHE_ROOT_UNSAFE")
        as_of_day = date.fromisoformat(snapshot["as_of_requested"])
        old, _ = read_market_bars("KR",as_of_day,days=550,legacy_root=legacy_root)
        old = old.loc[old["session"].dt.date < date.fromisoformat(observed)].copy()
        full = validate_bars(
            pd.concat([old,*current_frames],ignore_index=True),
            as_of_day,quarantine=False)
        prices_full = score_price_observations(
            full,"KR",snapshot["as_of_requested"],len(all_rows))
        if prices_full["market_last_observation"] != observed:
            raise ValueError("MARKETWIDE_FULL_PRICE_SESSION_MISMATCH")
        expected = snapshot["rows"]
        if [(r["security_id"],r["price_strength_25"]) for r in prices_full[
                "rows"][:len(expected)]] != [
                    (r["security_id"],r["price_strength_25"]) for r in expected]:
            raise ValueError("MARKETWIDE_PRICE_MODEL_NOT_SAME_AS_WATCH")
        for price in prices_full["rows"]:
            code=price["security_id"]
            if code not in all_rows or all_rows[code]["name"] != price["name"]:
                raise ValueError("MARKETWIDE_PRICE_CACHE_SECURITY_MISMATCH")
            previous = all_rows[code]["price_strength_25"]
            if previous is not None and previous != price["price_strength_25"]:
                raise ValueError("MARKETWIDE_PRICE_FACTOR_CONFLICT")
            all_rows[code]["price_strength_25"] = price["price_strength_25"]
        full_price_evaluable = len(prices_full["rows"])
    # P2 first executable comparison: observed momentum+earnings only.
    # Missing industry growth, competitive moat or institution flows must NEVER
    # be zero-filled into the official 100-point leader model.
    comparable=[]
    for item in all_rows.values():
        a,b,p=(item["revenue_yoy"],item["operating_income_yoy"],
               item["price_strength_25"])
        if any(x is None for x in (a,b,p)):
            continue
        if any(type(x) not in (int,float) or not math.isfinite(x)
               for x in (a,b,p)) or not 0 <= p <= 25:
            raise ValueError("MARKETWIDE_PARTIAL_SCORE_INVALID_INPUT")
        earnings=round(12.5*min(max(a,0)/0.40,1)+
                       12.5*min(max(b,0)/0.60,1),6)
        item["earnings_research_25"]=earnings
        item["two_factor_research_50"]=round(p+earnings,6)
        comparable.append(item)
    comparable.sort(key=lambda x:(-x["two_factor_research_50"],
                                  -x["price_strength_25"],x["security_id"]))
    for ix,item in enumerate(comparable,1):
        item["two_factor_research_rank"]=ix
    peer_audit = attach_observed_industry_peers(all_rows)
    flow_audit = (attach_matched_session_investor_flow(
        all_rows,kiwoom_flow_folder,market_session=observed,decision_at=now)
        if kiwoom_flow_folder is not None else {
            "flow_source_manifest_sha256":None,
            "flow_capture_companies_checked":0,
            "flow_matched_session_companies":0,
            "flow_mismatched_session_companies":0,
            "flow_certification":"N/A_NO_FLOW_SOURCE",
        })
    rows = [all_rows[k] for k in sorted(all_rows)]
    local_day=now.astimezone(ZoneInfo("Asia/Seoul")).date()
    elapsed_calendar_days=(local_day-date.fromisoformat(observed)).days
    if elapsed_calendar_days < 0:
        raise ValueError("MARKETWIDE_FUTURE_MARKET_SESSION")
    result = {
        "schema": SCHEMA, "market": "KR", "market_session": observed,
        "requested_local_day":local_day.isoformat(),
        "calendar_days_since_market_observation":elapsed_calendar_days,
        "stale_research_warning":elapsed_calendar_days>=2,
        "official_trading_sessions_elapsed":None,
        "source_decision_at_utc": decision.isoformat(),
        "built_at_utc": now.isoformat(),
        "source_watch_run_id": snapshot["run_id"],
        "source_basic_sha256": basic["content_sha256"],
        "source_industry_sha256": peers["content_sha256"],
        "official_krx_observed": len(rows),
        "current_dart_directory_matched": len(matched),
        "financial_factors_observed": len(basic["comparisons"]) + len(extras),
        "extra_cfs_manifests_sha256": manifest_pins,
        "incomplete_additional_financial_companies": len(incomplete),
        "industry_factors_observed": sum(
            x["industry_code"] is not None for x in rows),
        "extra_industry_manifests_sha256": industry_pins,
        **peer_audit,
        **flow_audit,
        "flow_factors_observed":flow_audit["flow_matched_session_companies"],
        "two_factor_research_evaluable":len(comparable),
        "local_price_lookback_enabled":full_price_lookback,
        "local_price_lookback_evaluable":full_price_evaluable,
        "two_factor_research_top20":[
            {"research_order":x["two_factor_research_rank"],
             "security_id":x["security_id"],"name":x["name"],
             "observed_score_50":x["two_factor_research_50"],
             "official_leader":False} for x in comparable[:20]],
        "two_factor_scoring_note":(
            "RESEARCH ONLY. Price: existing 0..25 momentum; "
            "earnings: sales YoY capped 40% (12.5pt), operating YoY "
            "capped 60% (12.5pt); negative growth floor 0. "
            "Industry/competition/flow unscored N/A. Not a 100-point rank."),
        "official_leaders": 0, "research_only": True,
        "full_market_composite_rank_available": False,
        "warning": ("KRX prices are a pinned single-day observation. "
                    "Financial/industry facts were received later than the price date; "
                    "historic issuer/class and availability PIT are not certified."),
        "securities": rows,
    }
    if previous_watch_file is not None:
        if (not previous_watch_file.is_absolute() or
                previous_watch_file.is_symlink() or
                not previous_watch_file.is_file() or
                any(parent.is_symlink() for parent in previous_watch_file.parents)):
            raise ValueError("MARKETWIDE_PREVIOUS_WATCH_FILE_UNSAFE")
        previous=json.loads(previous_watch_file.read_bytes())
        result["watch_changes_research"]=compare_official_price_watch(
            previous,snapshot)
    else:
        result["watch_changes_research"]=None
    result["content_sha256"] = sha256(canonical(result)).hexdigest()
    return result



def refresh_saved_marketwide_flow(source_file: Path, flow_folder: Path, *,
                                  clock: datetime | None = None) -> dict:
    """Reuse the already-published *checksum-verified* KRX/DART snapshot.

    This avoids rerunning thousands of original DART checks just to add a
    newly-arrived broker research source. Original JSON is left untouched.
    """
    now=clock or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("MARKETWIDE_FLOW_UPDATE_CLOCK_UNAWARE")
    now=now.astimezone(timezone.utc)
    if (not source_file.is_absolute() or source_file.is_symlink() or
            not source_file.is_file() or
            any(p.is_symlink() for p in source_file.parents)):
        raise ValueError("MARKETWIDE_SAVED_SOURCE_UNSAFE")
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:
                raise ValueError("MARKETWIDE_SAVED_SOURCE_DUPLICATE_FIELD")
            result[k]=v
        return result
    data=json.loads(source_file.read_bytes(),object_pairs_hook=unique)
    digest=data.get("content_sha256")
    original=dict(data)
    original.pop("content_sha256",None)
    if (data.get("schema")!=SCHEMA or type(digest) is not str or
            digest != sha256(canonical(original)).hexdigest() or
            data.get("research_only") is not True or
            data.get("official_leaders") != 0 or
            data.get("full_market_composite_rank_available") is not False or
            data.get("flow_factors_observed") != 0 or
            type(data.get("securities")) is not list or
            len(data["securities"])!=data.get("official_krx_observed") or
            datetime.fromisoformat(data["built_at_utc"])>now):
        raise ValueError("MARKETWIDE_SAVED_SOURCE_INVALID")
    by_code={}
    for row in data["securities"]:
        key=row.get("security_id")
        if (type(key) is not str or key in by_code or
                row.get("foreign_flow") is not None or
                row.get("institutional_flow") is not None):
            raise ValueError("MARKETWIDE_SAVED_DUPLICATE_OR_PREJOINED")
        by_code[key]=row
    # Keep the source score untouched; add actual observed DART same-code
    # industry peer diagnostics as a separate research dimension.
    peer_audit=attach_observed_industry_peers(by_code)
    data.update(peer_audit)
    audit=attach_matched_session_investor_flow(
        by_code,flow_folder,market_session=data["market_session"],
        decision_at=now)
    data.update(audit)
    data["flow_factors_observed"]=audit["flow_matched_session_companies"]
    data["previous_research_sha256"]=digest
    data["built_at_utc"]=now.isoformat()
    local_day=now.astimezone(ZoneInfo("Asia/Seoul")).date()
    delta=(local_day-date.fromisoformat(data["market_session"])).days
    if delta < 0:
        raise ValueError("MARKETWIDE_FLOW_UPDATE_FUTURE_SESSION")
    data["requested_local_day"]=local_day.isoformat()
    data["calendar_days_since_market_observation"]=delta
    data["stale_research_warning"]=delta>=2
    data["official_trading_sessions_elapsed"]=None
    data["warning"]+=" Kiwoom research flow attached only if its latest and requested sessions match KRX."
    data.pop("content_sha256")
    data["content_sha256"]=sha256(canonical(data)).hexdigest()
    return data

def publish_marketwide_coverage(report: dict, dest: Path) -> tuple[Path, Path]:
    """Write separate immutable JSON and HTML without altering WATCH history."""
    digest = report.get("content_sha256")
    original = dict(report)
    original.pop("content_sha256", None)
    if (report.get("schema") != SCHEMA or
            report.get("full_market_composite_rank_available") is not False or
            report.get("official_leaders") != 0 or
            sha256(canonical(original)).hexdigest() != digest):
        raise ValueError("MARKETWIDE_REPORT_INVALID")
    if (not dest.is_absolute() or dest.exists() or dest.is_symlink() or
            not dest.parent.is_dir() or dest.parent.is_symlink() or
            any(p.is_symlink() for p in dest.parents)):
        raise ValueError("MARKETWIDE_DESTINATION_UNSAFE")
    dest.mkdir(mode=0o700)
    jsonfile, page = dest / "marketwide_kr.json", dest / "index.html"
    highlights = sorted((r for r in report["securities"]
                         if r["price_top20_watch_rank"] is not None),
                        key=lambda r: r["price_top20_watch_rank"])
    body = "".join(
        "<tr>" + "".join("<td>" + escape(str(value)) + "</td>" for value in (
            r["price_top20_watch_rank"], r["security_id"], r["name"],
            "Y" if r["revenue_yoy"] is not None else "N/A",
            r["industry_code"] or "N/A", "N/A")) + "</tr>"
        for r in highlights)
    research_rows = "".join("<tr>"+"".join("<td>"+
        escape(str(value))+"</td>" for value in
        (x["research_order"],x["security_id"],x["name"],x["observed_score_50"]))+
        "</tr>" for x in report.get("two_factor_research_top20",[]))
    html = (
        "<!doctype html><html lang='ko'><meta charset='utf-8'>"
        "<title>EraLeader KR 전시장 자료 결합 현황</title><style>" + BASE_CSS +
        "</style><main><h1>한국 전체시장 자료 결합 현황</h1><p>실제 거래관측일 " +
        escape(report["market_session"]) + " / 기준 UTC " +
        escape(report["built_at_utc"]) + "</p><p>KRX " +
        str(report["official_krx_observed"]) + "종목 · DART 현재 기업매칭 " +
        str(report["current_dart_directory_matched"]) + " · 재무 " +
        str(report["financial_factors_observed"]) + " · 산업 " +
        str(report["industry_factors_observed"]) + " · 공식 수급 " +
        str(report["flow_factors_observed"]) + "</p><p><strong>" +
        ("자료 지연 경고: 과거 거래일 관측 ("+
         str(report["calendar_days_since_market_observation"])+
         "달력일 경과, 실제 휴장 반영 거래세션 수 N/A).</strong> "
         if report.get("stale_research_warning") else "")+
        "가격 관찰 TOP20은 투자/대장주 종합 순위가 아닙니다. "
        "자료 부족 종목·분야는 N/A, 확정 대장주 0.</strong></p>"
        "<table><thead><tr><th>가격 관찰순서</th><th>종목코드</th>"
        "<th>종목명</th><th>재무 확보</th><th>산업코드</th><th>수급</th>"
        "</tr></thead><tbody>" + body + "</tbody></table>"
        "<h2>가격·실적 2요소 연구 비교 TOP20 (50점, 투자 우선순위 아님)</h2>"
        "<p>2요소 평가 가능 "+str(report.get("two_factor_research_evaluable",0))+
        "종목 한정. 산업성장·기업경쟁력·외국인기관 수급은 N/A.</p>"
        "<table><thead><tr><th>비교 순서</th><th>종목</th><th>회사</th>"
        "<th>관측점수 /50</th></tr></thead><tbody>"+research_rows+"</tbody></table>"
        "<h2>동일 업종 표본 내 매출·영업 성장 상대비교</h2>"
        "<p>동종 2사 이상 그룹 "+str(len(report.get("same_industry_sample_groups",[])))+
        "개 · 매출성장 비교 "+str(report.get("revenue_yoy_peer_evaluable",0))+
        "사 · 영업익 성장 비교 "+str(report.get("operating_income_yoy_peer_evaluable",0))+
        "사. 정확한 업종코드가 일치하는 수집 기업끼리만 비교하며 "
        "시장 전체 업종 성장률이나 기업 경쟁력 평가가 아닙니다. "
        "종목별 상대위치는 marketwide_kr.json에서 확인합니다.</p>" +
        ("<p><strong>공식 거래일별 기술 관찰 변화</strong> 신규 "+
         str(report["watch_changes_research"]["new_count"])+
         "종목, 가격 관찰 밖 이동 "+
         str(report["watch_changes_research"]["left_count"])+
         "종목, 기존 목록 내 순서 변경 "+
         str(report["watch_changes_research"]["rank_changed_count"])+
         "종목. 상장폐지·매도·정식 대장주 교체 신호가 아닙니다.</p>"
         if report.get("watch_changes_research") else "")+
        "<p>전체 KRX 종목별 자료 확보 여부: marketwide_kr.json (동일 폴더). "
        "재무/산업은 현재 수집 표본이며 과거 주권 PIT 인증은 N/A.</p>"
        "</main></html>")
    try:
        jsonfile.write_bytes(canonical(report) + b"\n")
        page.write_text(html, encoding="utf-8")
        os.chmod(jsonfile, 0o600)
        os.chmod(page, 0o600)
    except BaseException:
        jsonfile.unlink(missing_ok=True)
        page.unlink(missing_ok=True)
        dest.rmdir()
        raise
    return jsonfile, page
