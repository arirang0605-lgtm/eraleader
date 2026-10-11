"""Opt-in, fail-closed scheduling bridge for independently dated WATCH briefs.

No launchd installation, new data ingestion, real-time alerts, vendor API or
automatic leader promotions. Existing price-only local scheduler remains default.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from .watch_operating_reports import (
    STATUS, PERIODS, compile_watch_operating_report,
    render_watch_operating_markdown, render_watch_operating_html,
    write_watch_operating_reports,
)

CONFIG_SCHEMA = "eraleader.scheduled_watch_research.v1"
MARKETS = ("KR", "US")
MAX_CONFIG_BYTES = 12000


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate WATCH schedule config field")
        result[key] = value
    return result


def _path(value: object, *, file: bool) -> Path:
    if not isinstance(value,str) or not value.startswith("/") or not value.strip():
        raise ValueError("WATCH schedule config path must be absolute")
    result=Path(value)
    if result.is_symlink() or result.parent.is_symlink():
        raise ValueError("symlink WATCH schedule inputs forbidden")
    if not (result.is_file() if file else result.is_dir()):
        raise ValueError("Missing WATCH schedule input ledger or features")
    return result


def read_watch_schedule_config(path: Path) -> dict:
    """Never read/watch a config unless opted in; no environmental fallback."""
    config=Path(path)
    if config.is_symlink() or config.parent.is_symlink():
        raise ValueError("symlink WATCH research config forbidden")
    if not config.is_file() or not 0 < config.stat().st_size <= MAX_CONFIG_BYTES:
        raise ValueError("Missing or oversized WATCH research config")
    raw=config.read_bytes()
    try:
        parsed=json.loads(raw,object_pairs_hook=_unique)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("Invalid WATCH schedule config JSON") from exc
    if (not isinstance(parsed,dict) or set(parsed)!={"schema_version","markets"}
            or parsed["schema_version"]!=CONFIG_SCHEMA
            or not isinstance(parsed["markets"],dict)
            or set(parsed["markets"])!=set(MARKETS)):
        raise ValueError("WATCH schedule config requires exact schema and KR/US markets")
    specs={}
    for market in MARKETS:
        item=parsed["markets"][market]
        expected={"watch_ledger","model_version"}
        if not isinstance(item,dict) or not expected.issubset(item):
            raise ValueError("Missing WATCH schedule market/model fields")
        optional=set(item)-expected
        if optional not in (set(),{"score_ledger","feature_root"}):
            raise ValueError("WATCH peer-score ledger and feature root must be paired")
        model=item.get("model_version")
        if not isinstance(model,str) or not model.strip() or len(model)>160:
            raise ValueError("Invalid pinned WATCH model version")
        spec={
            "market":market,"model_version":model,
            "watch_ledger":_path(item["watch_ledger"],file=True),
        }
        if optional:
            spec["score_ledger"]=_path(item["score_ledger"],file=True)
            spec["feature_root"]=_path(item["feature_root"],file=False)
        specs[market]=spec
    return specs


def audit_watch_schedule_sources(specs: dict, *,
                                 clock: datetime,
                                 max_age_days: int=7) -> dict:
    """Preflight BOTH markets using one captured OS UTC cutoff; no writes."""
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("WATCH scheduler clock must be aware")
    if type(max_age_days) is not int or not 0<=max_age_days<=365:
        raise ValueError("Invalid scheduled WATCH maximum age")
    if set(specs)!=set(MARKETS):
        raise ValueError("Scheduled WATCH requires both market pins")
    now=clock.astimezone(timezone.utc)
    reports={}
    fingerprint={}
    statuses={}
    for market in MARKETS:
        config=specs[market]
        result=compile_watch_operating_report(
            config["watch_ledger"],market=market,
            model_version=config["model_version"],
            evaluated_at=now.isoformat(),clock=now,
            max_age_days=max_age_days,
            score_ledger=config.get("score_ledger"),
            feature_root=config.get("feature_root"),
        )
        if (result.get("status")!=STATUS or result.get("market")!=market
                or result.get("pit_certified") is not False
                or result.get("official_leader_promotions")!=0
                or result.get("live_notifications_sent")!=0):
            raise ValueError("Unsafe WATCH research source certification claim")
        # Rendering failures are detected BEFORE the existing KR/US price
        # batch writes any output. Rendering here is pure and produces no file.
        for period in PERIODS:
            render_watch_operating_markdown(result,period)
            render_watch_operating_html(result,period)
        reports[market]=result
        statuses[market]=result["data_freshness_status"]
        score=result["peer_score_rotation"]
        fingerprint[market]={
            "market":market,
            "model_version":config["model_version"],
            "as_of_market_day":result["as_of_market_day"],
            "watch_local_sha256":result["local_eligible_watch_payload_sha256"],
            "optional_peer_score_proof_sha256":score.get(
                "local_peer_score_claim_sha256"
            ),
            "peer_score_status":score["status"],
        }
    good=all(status=="LOCAL_RESEARCH_OBSERVATIONS_RECENT_NOT_PIT_CERTIFIED"
             for status in statuses.values())
    return {
        "reports":reports,
        "watch_research_sha256":fingerprint,
        "watch_freshness_status":statuses,
        "all_markets_recent":good,
    }


def publish_watch_schedule_reports(audited: dict, out: Path) -> dict:
    """Write derived KR+US brief files only, with no raw SQLite copying."""
    built={}
    for market in MARKETS:
        result=write_watch_operating_reports(audited["reports"][market],out)
        if (result["research_report_periods"]!=3
                or result["official_leader_promotions"]!=0
                or result["pit_certified"] is not False
                or result["live_notifications_sent"]!=0
                or len(result["derived_pages"])!=6):
            raise RuntimeError("Incomplete or unsafe scheduled WATCH market reports")
        built[market]=result
    return {
        "research_report_pages":sum(len(item["derived_pages"])+1 for item in built.values()),
        "watch_market_run_ids":{
            market:audited["reports"][market]["research_run_id"]
            for market in MARKETS
        },
    }
