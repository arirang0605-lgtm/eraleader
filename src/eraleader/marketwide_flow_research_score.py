"""KR investor flow heuristic V1: explicitly provisional 0-10 research component.

Unchanged dated KRX volume/SharedBrokerAPI witnesses must be re-verified
for each code at the *current* local decision time. The heuristic is
a deterministic research convention, not a validated investment signal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import math
import os
import re

from .marketwide_auto_refresh import _owned_output
from .marketwide_dated_volume import evaluate_exact_volume
from .marketwide_live_search import _source, prepare_search
from .official_company_explorer import canonical
from .factor_selection_pipeline import _read_assessment, SCHEMA as FACTOR_SCHEMA, ASSESSMENT

SCHEMA = "eraleader.kr_flow10_observed_volume_heuristic.v1"
PROVIDER = "KR_FLOW_VOLUME_HEURISTIC_V1_NOT_VALIDATED"
FOLDER = "research_flow10_assessments"
MAX_STOCKS = 20
WEIGHT_5 = 0.60
WEIGHT_20 = 0.40
POINTS_PER_NET_PCT = 0.50
MIDPOINT = 5.0


def _clock(clock):
    value = clock or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FLOW_HEURISTIC_AWARE_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _bounded_source(marketwide, now):
    report, _ = _source(marketwide)
    manifest, _rows = prepare_search(
        report, request_day=now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat(),
        clock=now,
    )
    if manifest["stale_warning"]:
        raise ValueError("FLOW_HEURISTIC_STALE_MARKET_SOURCE")
    return report


def _component(dated):
    """Neutral 5 points. +/- 0.5 point per 1% weighted joint net flow."""
    components = []
    for n in ("5", "20"):
        period = dated["periods"][n]
        if (period["all_observation_dates_matched"] is not True or
                period["matched_price_volume_days"] != int(n) or
                period["missing_price_volume_dates"] or
                type(period["exact_matched_daily_volume_total_shares"]) not in (int, float) or
                period["exact_matched_daily_volume_total_shares"] <= 0):
            raise ValueError("FLOW_HEURISTIC_PERIOD_NOT_EXACTLY_MATCHED")
        total = 0.0
        for investor in ("foreign", "institution"):
            amount = period[f"{investor}_net_shares"]
            value = period[f"{investor}_pct_of_matched_daily_volume"]
            if (type(amount) is not int or type(value) not in (int, float)
                    or not math.isfinite(value)):
                raise ValueError("FLOW_HEURISTIC_PERIOD_INVALID")
            recomputed = round(100 * amount / period["exact_matched_daily_volume_total_shares"], 6)
            if not math.isclose(recomputed, value, rel_tol=0, abs_tol=1e-6):
                raise ValueError("FLOW_HEURISTIC_PERIOD_CALC_MISMATCH")
            total += value
        components.append(round(total, 6))
    weighted = WEIGHT_5 * components[0] + WEIGHT_20 * components[1]
    score = round(max(0.0, min(10.0, MIDPOINT + POINTS_PER_NET_PCT * weighted)), 4)
    return score, components, round(weighted, 6)


def build_flow_research(*, marketwide: Path, project: Path,
                        sources: dict[str, Path],
                        clock: datetime | None = None) -> dict:
    now = _clock(clock)
    output = _owned_output(project)
    market = _bounded_source(marketwide, now)
    if type(sources) is not dict or not 1 <= len(sources) <= MAX_STOCKS:
        raise ValueError("FLOW_HEURISTIC_SOURCE_COUNT")
    known = {x["security_id"] for x in market["securities"]}
    rows = []
    for code, overlay in sorted(sources.items()):
        if (type(code) is not str or re.fullmatch(r"[0-9]{6}", code) is None or
                code not in known or not isinstance(overlay, Path)):
            raise ValueError("FLOW_HEURISTIC_SECURITY_INVALID")
        dated = evaluate_exact_volume(
            marketwide=marketwide, project=project, code=code,
            official_volume_overlay=overlay, clock=now)
        if dated.get("status") or (
                dated["source_marketwide_sha256"] != market["content_sha256"] or
                dated["stock_code"] != code or dated["orders_enabled"] is not False or
                dated["formal_flow_score_10"] is not None or
                dated["official_volume_overlay_sha256"] is None):
            raise ValueError("FLOW_HEURISTIC_SOURCE_NOT_PROVEN")
        score, sums, weighted = _component(dated)
        rows.append({
            "security_id": code, "market_session":market["market_session"],
            "research_score_10":score,
            "foreign_institution_joint_net_5_pct":sums[0],
            "foreign_institution_joint_net_20_pct":sums[1],
            "weighted_joint_net_pct":weighted,
            "price_marketwide_sha256":market["content_sha256"],
            "dated_flow_sha256":dated["dated_flow_sha256"],
            "official_volume_overlay_sha256":dated["official_volume_overlay_sha256"],
            "cache_file_sha256":dated["cache_file_sha256"],
            "first_local_assessed_at_utc":now.isoformat(),
            "independent_historical_pit_certified":False,
            "flow_score_formally_validated":False,
        })
    statement = {
        "schema":SCHEMA,"market":"KR","source_market_session":market["market_session"],
        "source_marketwide_sha256":market["content_sha256"],
        "computed_at_utc":now.isoformat(),
        "provider":PROVIDER,"rule_version":"0.60*5d + 0.40*20d; neutral5 + 0.5*joint_pct",
        "component_weight_5":WEIGHT_5,"component_weight_20":WEIGHT_20,
        "score_midpoint":MIDPOINT,"points_per_net_pct":POINTS_PER_NET_PCT,
        "research_only":True,
        "independent_historical_pit_certified":False,
        "formal_flow_score_10_available":False,
        "issuer_corporate_actions_verified":False,
        "official_leaders":0,"orders_enabled":False,
        "rows":rows,
    }
    statement["content_sha256"] = sha256(canonical(statement)).hexdigest()
    parent = output / FOLDER
    if parent.is_symlink():
        raise ValueError("FLOW_HEURISTIC_OUTPUT_SYMLINK")
    parent.mkdir(mode=0o700, exist_ok=True)
    version = sha256(canonical({"source":statement["source_marketwide_sha256"],
                                "witnesses":[(row["security_id"],row["dated_flow_sha256"],
                                              row["official_volume_overlay_sha256"])
                                             for row in rows],
                                "clock":now.isoformat()})).hexdigest()[:16]
    target = parent / ("KR_" + market["market_session"].replace("-","") + "_" + version + ".json")
    b = canonical(statement) + b"\n"
    if target.is_symlink():
        raise ValueError("FLOW_HEURISTIC_TARGET_LINK")
    if target.exists():
        if target.read_bytes() != b:
            raise ValueError("FLOW_HEURISTIC_EXISTING_CONFLICT")
        state = "ALREADY_PUBLISHED"
    else:
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(b); stream.flush(); os.fsync(stream.fileno())
        state = "PUBLISHED"
    return {"status":state,"file":str(target),
            "research_scored":len(rows),"formal_scored":0,
            "scores":{r["security_id"]:r["research_score_10"] for r in rows},
            "decision_at_utc":now.isoformat(),"orders":0}


def read_flow_research(path: Path, *, expected_market_sha: str, clock=None) -> dict:
    now = _clock(clock)
    if (not path.is_absolute() or path.is_symlink() or
            any(x.is_symlink() for x in path.parents) or
            not path.is_file() or not 100 <= path.stat().st_size <= 100_000 or
            path.stat().st_uid != os.geteuid()):
        raise ValueError("FLOW_HEURISTIC_EVIDENCE_FILE_UNSAFE")
    b = path.read_bytes()
    doc = json.loads(b)
    signed = dict(doc)
    pin = signed.pop("content_sha256",None)
    if (type(doc) is not dict or b!=canonical(doc)+b"\n" or
            pin!=sha256(canonical(signed)).hexdigest() or
            doc.get("schema")!=SCHEMA or
            doc.get("source_marketwide_sha256")!=expected_market_sha or
            doc.get("research_only") is not True or
            doc.get("independent_historical_pit_certified") is not False or
            doc.get("formal_flow_score_10_available") is not False or
            doc.get("official_leaders")!=0 or
            doc.get("orders_enabled") is not False or
            doc.get("provider")!=PROVIDER or
            doc.get("rule_version")!="0.60*5d + 0.40*20d; neutral5 + 0.5*joint_pct" or
            doc.get("component_weight_5")!=WEIGHT_5 or
            doc.get("component_weight_20")!=WEIGHT_20 or
            doc.get("score_midpoint")!=MIDPOINT or
            doc.get("points_per_net_pct")!=POINTS_PER_NET_PCT):
        raise ValueError("FLOW_HEURISTIC_EVIDENCE_CONTRACT")
    first = datetime.fromisoformat(doc["computed_at_utc"])
    if first.tzinfo is None or first.astimezone(timezone.utc)>now:
        raise ValueError("FLOW_HEURISTIC_FUTURE")
    rows = doc.get("rows")
    if type(rows) is not list or not 1 <= len(rows) <= MAX_STOCKS:
        raise ValueError("FLOW_HEURISTIC_ROWS")
    codes = set()
    for row in rows:
        code=row["security_id"]
        if (type(code) is not str or not re.fullmatch(r"[0-9]{6}",code)
                or code in codes or row.get("price_marketwide_sha256")!=expected_market_sha
                or row.get("flow_score_formally_validated") is not False
                or row.get("independent_historical_pit_certified") is not False
                or row.get("first_local_assessed_at_utc")!=doc["computed_at_utc"]
                or any(type(row.get(k)) is not str or
                       re.fullmatch(r"[0-9a-f]{64}",row[k]) is None for k in (
                       "dated_flow_sha256","official_volume_overlay_sha256"))
                or type(row.get("research_score_10")) not in (int,float)):
            raise ValueError("FLOW_HEURISTIC_ROW_EVIDENCE_INVALID")
        recomputed = round(max(0,min(10,5+0.5*(
            0.6*row["foreign_institution_joint_net_5_pct"]+
            0.4*row["foreign_institution_joint_net_20_pct"]))),4)
        if recomputed != row["research_score_10"]:
            raise ValueError("FLOW_HEURISTIC_SCORE_TAMPER")
        codes.add(code)
    return doc


def join_flow_into_partial(*, base_assessment: Path, flow_file: Path,
                           project: Path, clock: datetime | None = None) -> dict:
    now = _clock(clock)
    output = _owned_output(project)
    base = _read_assessment(base_assessment)
    flow = read_flow_research(
        flow_file,expected_market_sha=base["source_marketwide_sha256"],clock=now)
    if (base["market_session"]!=flow["source_market_session"] or
            base["certification_level"]!=ASSESSMENT):
        raise ValueError("FLOW_HEURISTIC_BASE_MISMATCH")
    rows = {r["security_id"]:r for r in flow["rows"]}
    joined = json.loads(canonical(base))  # deep copy, do not mutate preexisting file
    joined.pop("content_sha256")
    included = 0
    for row in joined["factor_rows"]:
        flow_row = rows.get(row["security_id"])
        if not flow_row:
            continue
        if (row["components"]["flow"] is not None or
                row["factor_receipts"]["flow"] is not None):
            raise ValueError("FLOW_HEURISTIC_EXISTING_FLOW_SCORE")
        included += 1
        row["components"]["flow"]=flow_row["research_score_10"]
        row["factor_receipts"]["flow"]={
            "sha256":flow["content_sha256"],
            "available_at_utc":flow["computed_at_utc"],
            "provider":PROVIDER,
        }
    decision=max(datetime.fromisoformat(base["decision_at_utc"]).astimezone(timezone.utc),
                 datetime.fromisoformat(flow["computed_at_utc"]).astimezone(timezone.utc))
    joined["decision_at_utc"]=decision.isoformat()
    joined["content_sha256"]=sha256(canonical(joined)).hexdigest()
    folder=output/"partial_factor_inputs"
    if folder.is_symlink():
        raise ValueError("FLOW_HEURISTIC_FACTOR_OUTPUT_LINK")
    folder.mkdir(mode=0o700,exist_ok=True)
    dest=folder/("KR_"+base["market_session"].replace("-","")+"_"
                 +base["source_marketwide_sha256"][:16]+"_FLOWV1_"
                 +joined["content_sha256"][:16]+".json")
    b=canonical(joined)+b"\n"
    if dest.is_symlink():
        raise ValueError("FLOW_HEURISTIC_FACTOR_TARGET_LINK")
    if dest.exists():
        if dest.read_bytes()!=b:
            raise ValueError("FLOW_HEURISTIC_FACTOR_VERSION_CONFLICT")
        state="ALREADY_JOINED"
    else:
        fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as sink:
            sink.write(b);sink.flush();os.fsync(sink.fileno())
        state="FLOW_RESEARCH_JOINED"
    return {"status":state,"file":str(dest),
            "flow_research_codes":len(rows),
            "scored_in_partial":included,
            "unmatched_flow_codes":sorted(set(rows)-{
                row["security_id"] for row in joined["factor_rows"]}),
            "factor_input_first_usable_utc":decision.isoformat(),
            "formal_leaders":0,"orders":0,
            "existing_state_history_modified":False}
