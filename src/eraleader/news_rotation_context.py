"""ER-NC-05: read-only correlation of existing prospective WATCH rotation.

Original two-positive/two-negative logic lives ONLY in watch_rotation.py.
Theme episodes and licensed news are optional evidence, never leader promotion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from .watch_rotation import audit_watch_rotation, STATUS
from .news_catalyst_adapter import _time


def correlate_watch_rotation(*, ledger: Path, market: str, model_version: str,
                             evaluated_at: str, clock: datetime,
                             theme_pit_snapshot: dict,
                             theme_episode_history: list[dict] | None = None,
                             news_snapshot: dict | None = None) -> dict:
    """Research-only as-of intersection; original prospective ledger read-only."""
    at=_time(evaluated_at,"evaluated_at")
    if type(theme_pit_snapshot) is not dict or "themes" not in theme_pit_snapshot:
        raise ValueError("Theme as-of PIT snapshot required")
    if _time(theme_pit_snapshot["as_of"],"theme_as_of")>at:
        raise ValueError("Future theme membership not eligible")
    if (theme_pit_snapshot.get("official_leaders")!=0 or
            theme_pit_snapshot.get("research_only") is not True):
        raise ValueError("Uncertified theme snapshot expected")
    rotation=audit_watch_rotation(ledger,market=market,model_version=model_version,
                                  evaluated_at=evaluated_at,clock=clock)
    if rotation.get("status")!=STATUS or rotation.get("official_leader_replacements")!=0:
        raise ValueError("Existing prospective WATCH evidence did not pass original audit")
    episodes=theme_episode_history or []
    if type(episodes) is not list:
        raise ValueError("Theme episode history must be list")
    for episode in episodes:
        if episode.get("research_only") is not True or episode.get("official_leaders")!=0:
            raise ValueError("Uncertified episode history expected")
        if _time(episode["as_of"],"episode_as_of")>at:
            raise ValueError("Future theme episode cannot affect past WATCH")
    allowed_news=[]
    if news_snapshot is not None:
        if (_time(news_snapshot["as_of"],"news_as_of")>at or
                news_snapshot.get("mode")!="LIVE_OBSERVED"):
            raise ValueError("News vintage must be historically available to as_of")
        allowed_news=[event for event in news_snapshot.get("events",[])
                     if event.get("evidence_status")=="VERIFIED_AS_OF"
                     and event.get("verification_status")=="VERIFIED"
                     and _time(event["available_at"],"available_at")<=at]
    themes=theme_pit_snapshot["themes"]
    hypotheses=[]
    unresolved=0
    late_news=0
    for raw in rotation.get("hypothesis_sample",[]):
        incumbent=raw["incumbent_security_id"]
        challenger=raw["contender_security_id"]
        first=_time(raw["contender_first_watch_at_utc"],"first_candidate_recorded_at")
        weakened=_time(raw["first_explicit_weakening_at_utc"],"weakened_at")
        if first<=weakened or first>at:
            raise ValueError("Existing rotation chronology inconsistent")
        candidate_themes=[]
        for theme in themes.values():
            if _time(theme["available_at"],"theme_available_at")>first:
                continue
            members={m["member_security_id"] for m in theme["members"]
                     if _time(m["member_first_known_at"],"first_known_at")<=first
                     and (not m.get("member_effective_from") or
                          _time(m["member_effective_from"],"effective_from")<=first)
                     and (not m.get("member_effective_to") or
                          _time(m["member_effective_to"],"effective_to")>=first)}
            if incumbent in members and challenger in members:
                candidate_themes.append(theme)
        if len(candidate_themes)!=1:
            unresolved+=1
            continue
        theme=candidate_themes[0]
        theme_id=theme["theme_id"]
        available_episodes=sorted([
            ep for ep in episodes if ep["theme_id"]==theme_id
            and _time(ep["as_of"],"episode_as_of")<=first
        ],key=lambda ep:ep["as_of"])
        episode=available_episodes[-1] if available_episodes else None
        referenced_news=[]
        for ev in allowed_news:
            if challenger in ev.get("related_issuer_ids",[]) or (
                theme_id in ev.get("theme_hints",[])):
                if _time(ev["available_at"],"available_at")<=first:
                    referenced_news.append({
                        "event_id":ev["event_id"],
                        "event_version":ev["event_version"],
                        "record_sha256":ev["record_sha256"],
                        "available_at":ev["available_at"],
                        "catalyst_state":ev["catalyst_state"]})
                else:
                    late_news+=1
        research={"status":"RESEARCH_ROTATION_HYPOTHESIS",
                  "incumbent_security_id":incumbent,
                  "challenger_security_id":challenger,
                  "theme_id":theme_id,
                  "episode_id":episode["episode_id"] if episode else None,
                  "theme_state_at_first_watch":episode["state"] if episode else "UNKNOWN",
                  "first_candidate_recorded_at":first.isoformat(),
                  "first_weakening_recorded_at":weakened.isoformat(),
                  "as_of":at.isoformat(),
                  "maturity_due_at":None,
                  "reason_codes":["EXISTING_2X2_PROSPECTIVE_WATCH_RULE",
                    "THEME_KNOWN_ASOF","NOT_A_CERTIFIED_LEADER_REPLACEMENT",
                    "MATURITY_LABEL_DEFINITION_NOT_FROZEN"],
                  "news_evidence":referenced_news,
                  "official_leader_replacements":0,
                  "prospective_performance_verified":False,
                  "research_only":True}
        research["evidence_refs_sha256"]=sha256(json.dumps(
            {"rotation":raw,"theme":theme["taxonomy_version"],
             "episode":episode.get("source_sha256") if episode else None,
             "news":referenced_news},sort_keys=True).encode()).hexdigest()
        hypotheses.append(research)
    return {"schema":"eraleader.er_nc_rotation_context.v1",
            "market":market,"as_of":at.isoformat(),
            "rotation_hypothesis_count":len(hypotheses),
            "unresolved_theme_class_pairs":unresolved,
            "post_candidate_news_not_credited":late_news,
            "source_rotation_audit_count":rotation["rotation_hypothesis_count"],
            "rotation_result_sample_truncated":(
                rotation["rotation_hypothesis_count"]>len(rotation["hypothesis_sample"])),
            "hypotheses":hypotheses,"official_leader_replacements":0,
            "historic_issuer_share_class_pit_certified":False,
            "actual_prediction_accuracy_certified":False,
            "research_only":True}
