"""6_2/6_5 read-only local operations + cold-native restoration evidence bridge.

Uses existing scheduler checkpoint audits and the cold readiness observer's
first SHA history. Does NOT rerun AES-GCM, touch PINs, issue first predictions,
make source PIT claims, call an API, or send an alert.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from html import escape
from pathlib import Path
import fcntl
import json
import os
import stat

from .operations_overview import audit_local_operations, render_operations_overview
from .native_cold_restore_gate import (
    _config, _paths, _base, _audit_observer, STATES as COLD_STATES,
    OK as COLD_OK, STATUS as COLD_ORIGINAL_STATUS,
)
from .native_cold_integrity import _read_json
from .native_sha_watchdog import _utc
from .watch_operating_reports import _atomic_text

SCHEMA = "eraleader.local_operations_cold_bridge.v1"
STATUS = "LOCAL_OPERATIONS_COLD_RESTORE_SHA_BRIDGE_RESEARCH_ONLY"
OBSERVATIONS = frozenset({
    "NO_COLD_RESTORE_RECORD", "COLD_OBSERVER_CORRUPTED",
    "COLD_OBSERVATION_STALE", "COLD_INCIDENT_PRESENT",
    "RESEARCH_ONLY_PREVIOUS_REPLAY", "LOCAL_REPLAY_SHA_HISTORY_ONLY",
})
MAX_JSON_BYTES = 180_000


def _safe_clock(clock):
    now = datetime.now(timezone.utc) if clock is None else clock
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Local cold operations requires timezone-aware time")
    return now.astimezone(timezone.utc)


def _blank(state):
    return {
        "state": state, "last_cold_observation_utc": None,
        "original_replay_state_counts": {}, "total_cold_packages": 0,
        "incident_packages": 0, "research_only_packages": 0,
        "current_pin_ciphertext_reverified": False,
        "aes_gcm_replayed_now": False, "original_pit_rechecked_now": False,
        "external_offsite_notarization_attested": False,
    }


def _cold_status(project, pin_root, scratch, now, due_days, warn_days,
                 max_gap_hours, allow_colocated_research):
    # The caller supplies the original roots so a newly forged report cannot
    # silently invent a different PIN or scratch identity.
    project, pin_root, scratch = _config(
        project, pin_root, scratch, due_days, warn_days,
        max_gap_hours, allow_colocated_research)
    folder, _ = _paths(project)
    if not folder.exists() and not folder.is_symlink():
        return _blank("NO_COLD_RESTORE_RECORD")
    lock = folder / ".checks.lock"
    try:
        if lock.is_symlink() or not lock.is_file():
            return _blank("COLD_OBSERVER_CORRUPTED")
        fd = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            state = os.fstat(handle.fileno())
            if (not stat.S_ISREG(state.st_mode) or
                    state.st_uid != os.geteuid() or
                    stat.S_IMODE(state.st_mode) & 0o077):
                return _blank("COLD_OBSERVER_CORRUPTED")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Original cold SHA writer currently active") from exc
            try:
                events = _audit_observer(
                    folder, _base(project, pin_root, scratch, due_days,
                                  warn_days, max_gap_hours, allow_colocated_research))
                if not events:
                    return _blank("COLD_OBSERVER_CORRUPTED")
                latest = events[-1]
                recorded = _utc(latest["at_utc"])
                report, raw = _read_json(folder/"report.json", MAX_JSON_BYTES)
                # Legacy observer's SHA audit verifies core checkpoint fields;
                # reject an appended counterfeit live/decrypt/offsite claim too.
                required_false = (
                    "private_key_accessed", "plaintext_decrypted",
                    "operational_offsite_attested", "official_market_pit_certified",
                    "actual_future_leader_skill_certified",
                )
                if (report.get("status") != COLD_ORIGINAL_STATUS or
                        report.get("checks") != len(events) or
                        report.get("chain_head_sha256") != latest["event_sha256"] or
                        report.get("rows") != latest["rows"] or
                        any(report.get(k) is not False for k in required_false) or
                        any(report.get(k) != 0 for k in (
                            "messages_sent", "external_api_calls",
                            "official_leader_promotions")) or
                        report.get("local_artifacts_only") is not True):
                    return _blank("COLD_OBSERVER_CORRUPTED")
                values = [row["state"] for row in latest["rows"].values()]
                if (not values or len(values) > 128 or
                        any(v not in COLD_STATES for v in values)):
                    return _blank("COLD_OBSERVER_CORRUPTED")
                counts = {kind: values.count(kind) for kind in sorted(set(values))}
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (ValueError, OSError, KeyError, TypeError, UnicodeError):
        return _blank("COLD_OBSERVER_CORRUPTED")
    if recorded > now + timedelta(minutes=5):
        return _blank("COLD_OBSERVER_CORRUPTED")
    if (now-recorded).total_seconds() > max_gap_hours*3600:
        status = "COLD_OBSERVATION_STALE"
    elif any(v not in COLD_OK for v in values):
        status = "COLD_INCIDENT_PRESENT"
    elif all(v=="RESEARCH_ONLY_FRESH" for v in values):
        status = "RESEARCH_ONLY_PREVIOUS_REPLAY"
    else:
        status = "LOCAL_REPLAY_SHA_HISTORY_ONLY"
    return {
        "state":status,
        "last_cold_observation_utc":recorded.isoformat(),
        "original_replay_state_counts":counts,
        "total_cold_packages":len(values),
        "incident_packages":sum(v not in COLD_OK for v in values),
        "research_only_packages":counts.get("RESEARCH_ONLY_FRESH",0),
        "current_pin_ciphertext_reverified":False,
        "aes_gcm_replayed_now":False,
        "original_pit_rechecked_now":False,
        "external_offsite_notarization_attested":False,
    }


def audit_operations_cold_bridge(project, pin_root, scratch, *,
                                 due_days=30, warn_days=7, max_gap_hours=48,
                                 allow_colocated_research=False, clock=None):
    now=_safe_clock(clock)
    project=Path(project)
    general=audit_local_operations(project,clock=now)
    cold=_cold_status(project,pin_root,scratch,now,due_days,warn_days,
                      max_gap_hours,allow_colocated_research)
    return {
        "schema_version":SCHEMA, "evaluated_at_utc":now.isoformat(),
        "general_operations":general, "cold_evidence":cold,
        "overall_gate":"HOLD_UNVERIFIED_RESEARCH",
        "sources_reverified_now":False,
        "official_market_pit_certified":False,
        "actual_future_leader_skill_certified":False,
        "live_notifications_sent":0, "external_api_calls":0,
        "official_leader_promotions":0,
    }


def render_operations_cold_bridge(snapshot):
    if (not isinstance(snapshot,dict) or
            snapshot.get("schema_version")!=SCHEMA or
            snapshot.get("overall_gate")!="HOLD_UNVERIFIED_RESEARCH" or
            snapshot.get("sources_reverified_now") is not False or
            snapshot.get("official_market_pit_certified") is not False or
            snapshot.get("actual_future_leader_skill_certified") is not False or
            any(snapshot.get(k)!=0 for k in (
                "live_notifications_sent","external_api_calls",
                "official_leader_promotions"))):
        raise ValueError("Cannot promote cold local research to verified leader performance")
    cold = snapshot.get("cold_evidence")
    if (not isinstance(cold,dict) or set(cold)!={
            "state","last_cold_observation_utc","original_replay_state_counts",
            "total_cold_packages","incident_packages","research_only_packages",
            "current_pin_ciphertext_reverified","aes_gcm_replayed_now",
            "original_pit_rechecked_now","external_offsite_notarization_attested"} or
            cold["state"] not in OBSERVATIONS or
            any(cold.get(k) is not False for k in (
                "current_pin_ciphertext_reverified","aes_gcm_replayed_now",
                "original_pit_rechecked_now",
                "external_offsite_notarization_attested"))):
        raise ValueError("Unsafe cold recovery evidence bridge")
    counts=cold["original_replay_state_counts"]
    total=cold["total_cold_packages"]
    if (not isinstance(counts,dict) or
            any(k not in COLD_STATES or type(v) is not int or v<=0 for k,v in counts.items()) or
            type(total) is not int or total<0 or total>128 or
            sum(counts.values())!=total or
            cold["incident_packages"]!=sum(
                v for k,v in counts.items() if k not in COLD_OK) or
            cold["research_only_packages"]!=counts.get("RESEARCH_ONLY_FRESH",0)):
        raise ValueError("Forged cold recovery incident or safety counters")
    if cold["last_cold_observation_utc"] is not None:
        _utc(cold["last_cold_observation_utc"])
    base_html=render_operations_overview(snapshot["general_operations"])
    entries="".join(
        "<tr><td>"+escape(name)+"</td><td>"+str(value)+"</td></tr>"
        for name,value in sorted(counts.items()))
    table=("<table><thead><tr><th>지난 복구 상태</th><th>백업 건수</th></tr></thead>"
           "<tbody>"+entries+"</tbody></table>" if entries else "<p>관찰 기록 N/A</p>")
    section=("<h2>6_5 암호화 보관본·실복구 원장 상태 (로컬 연구)</h2>"
             "<p>원장 감사 상태: <strong>"+escape(cold["state"])+"</strong></p>"
             "<p>마지막 기록 UTC: "+escape(cold["last_cold_observation_utc"] or "N/A")
             +" | 백업: "+str(total)+" | 주의: "+str(cold["incident_packages"])+"</p>"
             +table+
             "<p><small>기존 SHA 이력만 읽었습니다. 현재 원본 암호문/PIN 재검증·"
             "AES 복호화·PIT 확인·지리적 오프사이트 공증 및 자동 알림은 실행하지 "
             "않았습니다. READY 기록도 현재 실전 준비 인증을 의미하지 않습니다.</small></p>")
    if "</main>" not in base_html:
        raise ValueError("Missing original operations page main boundary")
    return base_html.replace("</main>",section+"</main>",1)


def publish_operations_cold_bridge(project,pin_root,scratch,**kwargs):
    project=Path(project)
    out=project/"output"/"operations_cold"
    html=out/"site"/"index.html"
    report=out/"cold_operations_research.json"
    for path in (out,out/"site",html,report):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Unsafe local cold operations publication path")
    now=kwargs.pop("clock",None)
    now=_safe_clock(now)
    before=audit_operations_cold_bridge(project,pin_root,scratch,clock=now,**kwargs)
    text_html=render_operations_cold_bridge(before)
    serialized=json.dumps(before,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if audit_operations_cold_bridge(project,pin_root,scratch,clock=now,**kwargs)!=before:
        raise RuntimeError("Cold restoration SHA/operations evidence changed before publication")
    _atomic_text(html,text_html)
    _atomic_text(report,serialized)
    return {
        "status":STATUS, "cold_evidence_state":before["cold_evidence"]["state"],
        "cold_package_count":before["cold_evidence"]["total_cold_packages"],
        "local_pages_written":2,
        "source_pit_certified":False, "actual_future_leader_skill_certified":False,
        "live_notifications_sent":0, "external_api_calls":0,
    }
