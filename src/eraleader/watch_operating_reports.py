"""Local prospective WATCH daily/weekly/monthly operating briefs.

Research-only. Read both complete-screen and immutable-positive ledgers AS OF
an explicit cutoff. No outcome labels, no fake missing-is-negative transitions,
no third-party PIT attestation, no real-time messages or external data calls.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, date, timedelta
from hashlib import sha256
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import sqlite3
import uuid

from .prospective import _canonical, _SIGNAL_KIND, _STATUS
from .watch_progression import _stamp, MARKET_ZONES
from .delivery import BASE_CSS

STATUS = "LOCAL_WATCH_OPERATING_BRIEF_RESEARCH_ONLY_NOT_PIT_CERTIFIED"
TAGS = ("INITIAL_WATCH", "WATCH_PERSISTED", "SCREEN_WEAKENED",
        "SCREEN_STILL_WEAK", "SCREEN_REENTERED", "PRE_WATCH")
PERIODS = ("daily", "weekly", "monthly")
MAX_ROWS = 150000
MAX_SAMPLE = 200


def _now(clock: datetime | None) -> datetime:
    value = clock if clock is not None else datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Operating report clock must be timezone aware")
    return value.astimezone(timezone.utc)


def _read_source(ledger: Path, market: str, model_version: str):
    path = Path(ledger)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked prospective WATCH ledger")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        # One SQLite snapshot for the explicit-screen and positive-signal
        # queries, even if a separate process appends while we are reading.
        connection.execute("BEGIN")
        try:
            observed = connection.execute(
                """SELECT security_id,observed_as_of,recorded_at_utc,source_run_id,
                          screen_hit,payload_hash,payload
                   FROM research_screen_observations
                   WHERE market=? AND model_version=?
                   ORDER BY security_id,observed_as_of""",
                (market, model_version),
            ).fetchall()
            positive = connection.execute(
                """SELECT signal_id,security_id,observed_as_of,recorded_at_utc,
                          source_run_id,payload_hash,payload,status,kind
                   FROM prospective_signals
                   WHERE market=? AND model_version=?""",
                (market, model_version),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("Incomplete or invalid WATCH research tables") from exc
    finally:
        connection.close()
    if len(observed) > MAX_ROWS or len(positive) > MAX_ROWS:
        raise ValueError("Excessive WATCH research history; refuse partial summary")
    return observed, positive


def compile_watch_operating_report(
    ledger: Path, *, market: str, model_version: str,
    evaluated_at: str, clock: datetime | None = None,
    max_age_days: int = 7, sample_limit: int = 50,
    score_ledger: Path | None = None, feature_root: Path | None = None,
) -> dict:
    """Daily, week-to-date and month-to-date, anchored to market-local time.

    The earliest known WATCH, weakening and re-entry status is computed from
    earlier explicit rows first, even if that event is outside this window.
    Registration time, not arbitrary historical observation time, gates
    availability and contributes to the period's actual record counts.
    """
    if market not in MARKET_ZONES:
        raise ValueError("WATCH operating market must be KR or US")
    if not isinstance(model_version,str) or not model_version.strip():
        raise ValueError("Pinned research model_version is required")
    if type(max_age_days) is not int or not 0 <= max_age_days <= 365:
        raise ValueError("Invalid operating observation freshness period")
    if type(sample_limit) is not int or not 1 <= sample_limit <= MAX_SAMPLE:
        raise ValueError("Invalid operating event sample limit")
    if (score_ledger is None) != (feature_root is None):
        raise ValueError("Both optional score ledger and feature root are required")
    asof = _stamp(evaluated_at)
    now = _now(clock)
    if asof > now:
        raise ValueError("Future watch operating as-of cutoff not allowed")
    zone: ZoneInfo = MARKET_ZONES[market]
    asof_day = asof.astimezone(zone).date()
    starts = {
        "daily": asof_day,
        "weekly": asof_day - timedelta(days=asof_day.weekday()),
        "monthly": asof_day.replace(day=1),
    }
    observed, positive = _read_source(ledger, market, model_version)
    indexed: dict[tuple[str,str], tuple] = {}
    for signal_id,sec,seen,recorded,run,digest,payload,status,kind in positive:
        key = (sec, seen)
        if key in indexed:
            raise ValueError("Duplicate original positive WATCH signal key")
        indexed[key] = (signal_id, recorded, run, digest, payload, status, kind)
    histories: dict[str, list[dict]] = defaultdict(list)
    ignored_future = excluded_backfills = 0
    synthetic_count = 0
    verified_positive = set()
    source_evidence_keys = []
    for sec,seen,recorded,run,hit,digest,payload in observed:
        registered = _stamp(recorded)
        if registered > asof:
            ignored_future += 1
            continue
        if (not isinstance(sec,str) or not sec or
                type(hit) is not int or hit not in (0,1) or
                not isinstance(payload,str) or
                sha256(payload.encode("utf-8")).hexdigest() != digest):
            raise ValueError("WATCH operating source payload or screen hit corrupted")
        observation = _stamp(seen)
        if observation > registered:
            raise ValueError("Future WATCH observation predates local registration")
        try:
            basis = json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise ValueError("Malformed operating WATCH source JSON") from exc
        company = basis.get("company") if isinstance(basis,dict) else None
        if (not isinstance(company,dict) or _canonical(basis) != payload or
                basis.get("market") != market or
                basis.get("model_version") != model_version or
                basis.get("source_run_id") != run or
                _stamp(basis.get("as_of")) != observation or
                company.get("market") != market or
                company.get("security_id") != sec or
                _stamp(company.get("as_of")) != observation or
                company.get("research_screen_evaluated",True) is not True or
                company.get("research_growth_screen_hit") is not bool(hit) or
                company.get("state") != "WATCH" or
                company.get("full_score") is not None or
                company.get("verified_future_leader_candidate") is not False):
            raise ValueError("WATCH operating source payload identity/status mismatch")
        if any(key in company or key in basis for key in
               ("is_future_leader", "leader_start_at", "future_label",
                "realized_return", "outcome_label")):
            raise ValueError("Future outcome label leaks into operating WATCH data")
        if hit:
            stored = indexed.get((sec,seen))
            expected_signal = sha256(
                f"{market}|{sec}|{_SIGNAL_KIND}|{seen}|{model_version}".encode()
            ).hexdigest()
            if (stored is None or stored[0] != expected_signal or
                    stored[1] != recorded or stored[2] != run or
                    stored[3] != digest or stored[4] != payload or
                    stored[5] != _STATUS or stored[6] != _SIGNAL_KIND):
                raise ValueError("Original positive WATCH signal proof missing or corrupted")
            verified_positive.add((sec,seen))
        source_evidence_keys.append(
            f"{sec}|{seen}|{recorded}|{int(hit)}|{digest}"
        )
        lag = (registered.astimezone(zone).date() -
               observation.astimezone(zone).date()).days
        if lag < 0 or lag > 3:
            excluded_backfills += 1
            continue
        synthetic_count += int("synthetic_fixture" in basis.get("provenances",[]))
        histories[sec].append({
            "observed":observation,
            "registered":registered,
            "registered_market_day":registered.astimezone(zone).date(),
            "screen_hit":bool(hit),
            "run":run,
            "security_id":sec,
            "registration_lag_days":lag,
        })
    # Legacy positive-only ledgers may lack complete negative-screen history.
    # Do NOT quietly emit a reassuring operating report by ignoring missing
    # original positives: require a complete, validated row for each as-of
    # positive first-registration event, even if its old screen was backfilled.
    for key,original in indexed.items():
        if _stamp(original[1]) <= asof and key not in verified_positive:
            raise ValueError("Orphan positive WATCH signal without complete as-of screen")
    # Positive records can be submitted in older legacy ledgers, but they may
    # only contribute when the corresponding complete screen has been checked.
    periods = {
        period: {
            "window_start_market_day":start.isoformat(),
            "window_end_market_day":asof_day.isoformat(),
            "observations":0,
            "securities_screened":0,
            "research_source_runs":0,
            "transition_counts":{tag:0 for tag in TAGS},
            "event_sample":[],
            "event_sample_truncated":False,
        }
        for period,start in starts.items()
    }
    event_cache = {period:[] for period in PERIODS}
    security_set = {period:set() for period in PERIODS}
    run_set = {period:set() for period in PERIODS}
    recent_positive = []
    latest_positive = []
    last_registered = None
    valid_count = 0
    for sec,history in histories.items():
        history.sort(key=lambda item:(item["observed"],item["registered"]))
        ever_hit = False
        prev_hit = None
        prev_observed = prev_registered = None
        for row in history:
            obs,reg = row["observed"],row["registered"]
            if (prev_observed is not None and
                    (obs <= prev_observed or reg < prev_registered)):
                raise ValueError("Unordered prospective operating WATCH chronology")
            prev_observed,prev_registered = obs,reg
            if row["screen_hit"]:
                transition = ("INITIAL_WATCH" if not ever_hit else
                              "WATCH_PERSISTED" if prev_hit else
                              "SCREEN_REENTERED")
                ever_hit = True
            else:
                transition = ("PRE_WATCH" if not ever_hit else
                              "SCREEN_WEAKENED" if prev_hit else
                              "SCREEN_STILL_WEAK")
            prev_hit = row["screen_hit"]
            valid_count += 1
            if last_registered is None or reg > last_registered:
                last_registered = reg
            for period,start in starts.items():
                if start <= row["registered_market_day"] <= asof_day:
                    data = periods[period]
                    data["observations"] += 1
                    data["transition_counts"][transition] += 1
                    security_set[period].add(sec)
                    run_set[period].add(row["run"])
                    event_cache[period].append({
                        "security_id":sec,
                        "observed_at_utc":obs.isoformat(),
                        "recorded_at_utc":reg.isoformat(),
                        "transition":transition,
                        "registration_lag_days":row["registration_lag_days"],
                    })
        if history and history[-1]["screen_hit"]:
            latest_positive.append(sec)
            age = (asof_day-history[-1]["registered_market_day"]).days
            if age <= max_age_days:
                recent_positive.append(sec)
    for period in PERIODS:
        data = periods[period]
        data["securities_screened"] = len(security_set[period])
        data["research_source_runs"] = len(run_set[period])
        sample = sorted(event_cache[period],key=lambda row:(
            row["recorded_at_utc"],row["security_id"],row["observed_at_utc"]))
        data["event_sample"] = sample[-sample_limit:]
        data["event_sample_truncated"] = len(sample)>sample_limit
    age = (asof_day-last_registered.astimezone(zone).date()).days if last_registered else None
    freshness = ("NO_PROSPECTIVE_OBSERVATIONS" if last_registered is None else
                 "STALE_RESEARCH_OBSERVATIONS_NOT_CURRENT"
                 if age > max_age_days else "LOCAL_RESEARCH_OBSERVATIONS_RECENT_NOT_PIT_CERTIFIED")
    score = {"status":"NOT_REQUESTED",
             "rotation_hypotheses":None,
             "two_session_score_correlations":None,
             "official_replacements":0,
             "confidence_independently_verified":False}
    if score_ledger is not None:
        from .peer_score_series import audit_peer_score_advantage
        rated = audit_peer_score_advantage(
            Path(ledger),Path(score_ledger),Path(feature_root),
            market=market,model_version=model_version,
            evaluated_at=asof.isoformat(),clock=now,sample_limit=1000)
        score = {
            "status":"LOCAL_RESEARCH_CORROBORATION_ONLY",
            "rotation_hypotheses":rated["rotation_hypothesis_count"],
            "two_session_score_correlations":rated["locally_two_session_score_correlated"],
            "official_replacements":0,
            "confidence_independently_verified":False,
            "local_peer_score_claim_sha256":sha256(
                _canonical(rated["hypothesis_sample"]).encode("utf-8")
            ).hexdigest(),
        }
    source_hash = sha256(
        _canonical(sorted(source_evidence_keys)).encode("utf-8")
    ).hexdigest()
    local_version = {
        "market":market,"model_version":model_version,
        "as_of_utc":asof.isoformat(),"watch_rows_sha256":source_hash,
        "local_peer_score_research":score,
        "eligible_historical_observations":valid_count,
        "retrospective_backfills_excluded":excluded_backfills,
    }
    run_id=sha256(_canonical(local_version).encode("utf-8")).hexdigest()[:20]
    return {
        "status": STATUS, "market":market, "model_version":model_version,
        "research_run_id":run_id,
        "local_eligible_watch_payload_sha256":source_hash,
        "as_of_utc":asof.isoformat(), "as_of_market_day":asof_day.isoformat(),
        "source_ledger_rows":len(observed),
        "eligible_historical_observations":valid_count,
        "registered_after_cutoff_excluded":ignored_future,
        "retrospective_backfills_excluded":excluded_backfills,
        "synthetic_origin_eligible_observation_count":synthetic_count,
        "latest_explicit_registered_at_utc":last_registered.isoformat() if last_registered else None,
        "latest_evidence_age_market_days":age,
        "max_accepted_evidence_age_days":max_age_days,
        "data_freshness_status":freshness,
        "latest_explicit_positive_watch_count":len(latest_positive),
        "latest_explicit_positive_watch_ids_sample":sorted(latest_positive)[:sample_limit],
        "recent_positive_watch_count":len(recent_positive),
        "recent_positive_watch_ids_sample":sorted(recent_positive)[:sample_limit],
        "periods":periods,
        "peer_score_rotation":score,
        "actual_future_precision":None,
        "future_accuracy_certified":False,
        "real_leader_prediction_certified":False,
        "market_universe_coverage_certified":False,
        "pit_certified":False,
        "official_leader_promotions":0,
        "live_notifications_sent":0,
        "warning":(
            "Explicit local WATCH research rows only. Missing coverage is not "
            "screen weakness. Score, industry, original source timestamp, "
            "issuer PIT and future outcome validity are NOT authenticated. "
            "No official era leader or live trade/notification is produced."
        ),
    }


def _validated(report: dict, period: str) -> dict:
    if period not in PERIODS:
        raise ValueError("Invalid operating report period")
    if (report.get("status") != STATUS or report.get("market") not in MARKET_ZONES
            or report.get("pit_certified") is not False
            or report.get("market_universe_coverage_certified") is not False
            or report.get("future_accuracy_certified") is not False
            or report.get("official_leader_promotions") != 0
            or report.get("actual_future_precision") is not None):
        raise ValueError("Uncertified WATCH operating research cannot claim leader success")
    run_id=report.get("research_run_id")
    if not isinstance(run_id,str) or not re.fullmatch("[0-9a-f]{20}",run_id):
        raise ValueError("Missing or invalid pinned local operating run ID")
    entry = report.get("periods",{}).get(period)
    if not isinstance(entry,dict) or any(
        type(entry.get(field)) is not int or entry[field]<0
        for field in ("observations","securities_screened","research_source_runs")
    ):
        raise ValueError("Invalid operating event counter")
    transitions=entry.get("transition_counts")
    if (not isinstance(transitions,dict) or set(transitions)!=set(TAGS) or
            any(type(transitions[key]) is not int or transitions[key]<0 for key in TAGS)
            or sum(transitions.values())!=entry["observations"]):
        raise ValueError("Operating WATCH transition counts inconsistent")
    return entry


def _plain(value: object) -> str:
    return re.sub(r"[|\r\n<>]+"," ",str(value))


def render_watch_operating_markdown(report: dict, period: str) -> str:
    entry = _validated(report,period)
    name={"daily":"일간","weekly":"주간","monthly":"월간"}[period]
    lines=[
        f"# EraLeader {name} WATCH 운영 연구 보고",
        f"- 시장: {_plain(report['market'])}",
        f"- 고정 모델: {_plain(report['model_version'])}",
        f"- 공통 로컬 연구 run ID: {_plain(report['research_run_id'])}",
        f"- 평가 기준 UTC: {_plain(report['as_of_utc'])}",
        f"- 시장 현지 평가일: {_plain(report['as_of_market_day'])}",
        f"- 관찰 등록일 범위: {_plain(entry['window_start_market_day'])} ~ {_plain(entry['window_end_market_day'])}",
        "- **공식 대장주 0건 · 실전 발굴 성능 미검증 · PIT/전체 종목군 미인증**",
        f"- 입력 자료 신선도: {_plain(report['data_freshness_status'])} "
        f"(마지막 적격 등록시각 {_plain(report['latest_explicit_registered_at_utc'] or 'N/A')}; "
        f"현지 {report['latest_evidence_age_market_days'] if report['latest_evidence_age_market_days'] is not None else 'N/A'}일)",
        f"- 제외: 뒤늦게 소급 등록 {report['retrospective_backfills_excluded']}건, "
        f"평가시점 이후 등록 {report['registered_after_cutoff_excluded']}건",
        "",
        "## 명시적 WATCH 관찰 집계 (종목 누락은 약화로 간주하지 않음)",
        f"- 연구 관찰 {entry['observations']}건, 명시적 검사 기업 {entry['securities_screened']}개, "
        f"연구 run {entry['research_source_runs']}개",
    ]
    descriptions={
        "INITIAL_WATCH":"최초 WATCH 양성",
        "WATCH_PERSISTED":"WATCH 지속",
        "SCREEN_WEAKENED":"명시적 약화",
        "SCREEN_STILL_WEAK":"명시적 약화 지속",
        "SCREEN_REENTERED":"재진입",
        "PRE_WATCH":"첫 관심 전 음성",
    }
    for tag in TAGS:
        lines.append(f"- {_plain(descriptions[tag])}: {entry['transition_counts'][tag]}건")
    lines += [
        "",
        "## WATCH 후보의 최근 명시적 상태",
        f"- 전체 마지막 관찰 양성(신선도 미확정 포함): {report['latest_explicit_positive_watch_count']}개",
        f"- 최근 {report['max_accepted_evidence_age_days']} 현지 달력일 이내에 명시적으로 양성이었던 기업: {report['recent_positive_watch_count']}개",
        "- 이 숫자는 전체 시장 모니터링 범위/공식 대장주 수가 아님",
        "",
        "## 동종 업종 점수 근거 (선택적 원장 대조)",
        f"- 상태: {_plain(report['peer_score_rotation']['status'])}",
        f"- 연구 교체 가설: {_plain(report['peer_score_rotation']['rotation_hypotheses'])}",
        f"- 2개 서로 다른 관찰일의 로컬 점수 우위: {_plain(report['peer_score_rotation']['two_session_score_correlations'])}",
        "- 출처·PIT 독립 검증: 없음, 공식 교체 0건",
        "",
        "## 등록된 관찰 이벤트 표본 (최대 지정 개수)",
        "| 실제 등록 UTC | 영구 종목 ID | 변화 상태 |",
        "|---|---|---|",
    ]
    for row in entry["event_sample"]:
        lines.append("| "+ " | ".join(
            _plain(v) for v in (row["recorded_at_utc"],
                                row["security_id"],row["transition"]))+" |")
    if not entry["event_sample"]:
        lines.append("| N/A | 명시적 관찰 없음 | N/A |")
    lines += [
        "",
        f"- 표본 잘림: {bool(entry['event_sample_truncated'])}",
        "- 로컬 관찰 소급 입력/해시 무결성만 검사하며 실제 발행자·원천발표시각·미래정확도를 인증하지 않음",
        "- 실전 발굴 성능 미검증 · 자동 매매/라이브 알림 없음",
        "",
    ]
    return "\n".join(lines)


def render_watch_operating_html(report: dict, period: str) -> str:
    entry = _validated(report,period)
    name={"daily":"일간","weekly":"주간","monthly":"월간"}[period]
    h=lambda value:escape(str(value),quote=True)
    rows=[]
    for r in entry["event_sample"]:
        if r["transition"] not in TAGS:
            raise ValueError("Unexpected operating WATCH event transition")
        rows.append("<tr>"+"".join(
            "<td>"+h(v)+"</td>" for v in
            (r["recorded_at_utc"],r["security_id"],r["transition"]))+"</tr>")
    if not rows:
        rows=["<tr><td colspan='3'>N/A · 이 기간에 명시적 관찰 없음</td></tr>"]
    counters="".join(
        '<div class="stat">'+h(tag)+'<br><strong>'+
        h(entry["transition_counts"][tag])+'건</strong></div>' for tag in TAGS)
    evidence=report["peer_score_rotation"]
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader WATCH 운영 {h(name)} · {h(report['market'])}</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · {h(name)} WATCH 운영 연구 보고</h1>
<nav><a href="index.html">홈</a></nav></header><main>
<div class="note"><strong>공식 대장주 0건 · 실전 발굴 성능 미검증 · PIT 미인증</strong>
<p>시장 전체 종목군/공시/산업·기업행동의 독립 PIT 확인 전이므로
개별 WATCH는 실제 추천 또는 확정 대장주가 아닙니다.
명시적 음성이 없는 종목 누락은 약화로 간주하지 않습니다.</p></div>
<h2>시장 {h(report['market'])} · 모델 {h(report['model_version'])}</h2>
<p>공통 로컬 연구 run ID: {h(report['research_run_id'])}</p>
<p>평가: {h(report['as_of_market_day'])}, UTC {h(report['as_of_utc'])}<br>
기간: {h(entry['window_start_market_day'])} ~ {h(entry['window_end_market_day'])}<br>
자료 신선도: {h(report['data_freshness_status'])}<br>
마지막 적격 등록: {h(report['latest_explicit_registered_at_utc'] or 'N/A')}</p>
<div class="stats">{counters}</div>
<p>관찰 {entry['observations']}건 / 분석 기업 {entry['securities_screened']}개 /
run {entry['research_source_runs']}개; 뒤늦게 소급 등록 제외 {report['retrospective_backfills_excluded']}건,
미래 cutoff 이후 등록 제외 {report['registered_after_cutoff_excluded']}건</p>
<h2>명시적 관찰 마지막 양성</h2>
<p>전체 마지막 양성 {report['latest_explicit_positive_watch_count']}개,
최근 {report['max_accepted_evidence_age_days']} 현지일 양성 {report['recent_positive_watch_count']}개
(전체 시장 커버리지·투자 가능 종목 수 아님)</p>
<h2>업종 동료 점수 비교 (선택)</h2><p>
{h(evidence['status'])}: 연구 교체 가설 {h(evidence['rotation_hypotheses'])},
2회 국소 점수 우위 {h(evidence['two_session_score_correlations'])},
공식 교체 0건, 독립 검증 없음.</p>
<h2>명시적 이벤트 표본</h2>
<div class="wrap"><table><thead><tr><th>실제 등록 UTC</th>
<th>영구 종목 ID(자기선언)</th><th>WATCH 변화</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><small>표본 잘림 {h(entry['event_sample_truncated'])} ·
실전 성과/N/A · 외부 API 0 · 알림 발송 0 · 로컬 연구용</small></p>
</main></body></html>"""


def _atomic_text(file: Path, content: str) -> None:
    if file.is_symlink() or file.parent.is_symlink():
        raise ValueError("Unsafe linked operating report output")
    file.parent.mkdir(parents=True,exist_ok=True)
    temporary = file.parent / ("."+file.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with temporary.open("x",encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,file)
    finally:
        temporary.unlink(missing_ok=True)


def write_watch_operating_reports(report: dict, target: Path) -> dict:
    """Atomically replace derived pages, publish JSON manifest LAST."""
    out=Path(target)
    if out.is_symlink():
        raise ValueError("Linked operating report destination")
    pages=[]
    for period in PERIODS:
        _validated(report,period)
        name=f"watch_{period}_{report['market'].lower()}"
        markdown=out/"reports"/(name+".md")
        html=out/"site"/(name+".html")
        _atomic_text(markdown,render_watch_operating_markdown(report,period))
        _atomic_text(html,render_watch_operating_html(report,period))
        pages += [str(markdown),str(html)]
    artifact=out/f"watch_operating_{report['market'].lower()}_research.json"
    _atomic_text(artifact,json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    return {
        "status":report["status"],
        "json_path":str(artifact),
        "derived_pages":pages,
        "research_report_periods":len(PERIODS),
        "official_leader_promotions":0,
        "pit_certified":False,
        "live_notifications_sent":0,
    }
