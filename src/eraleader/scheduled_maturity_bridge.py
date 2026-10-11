"""6_4/6_5: opt-in scheduled native Top-K horizon-only research briefs.

This reads *preexisting* sealed native WATCH/score evidence; it never requests
market prices or outcome labels, labels elapsed windows as successes/failures,
installs a scheduler, sends a message, or certifies market PIT.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from zipfile import ZipFile
import json

from .ranked_maturity import audit_ranked_maturity, STATUS as MATURITY_STATUS
from .delivery import render_ranked_maturity_dashboard
from .watch_operating_reports import PERIODS, _atomic_text
from .scheduled_watch_bridge import _path, _unique

CONFIG_SCHEMA="eraleader.scheduled_ranked_maturity.v1"
MARKETS=("KR","US")
KEYS={"freeze","definition_file","score_ledger","watch_ledger","features_dir"}
MAX_CONFIG_BYTES=14000
VERIFIED_STATUS="LOCAL_RANKED_MATURITY_INVENTORY_NOT_CERTIFIED"
PERIOD_NAMES={"daily":"일간","weekly":"주간","monthly":"월간"}


def published_maturity_pages_match_verified_backup(output:Path, archive:Path) -> bool:
    """Compare all 16 live derived files with the already-verified ZIP hashes.

    verify_backup() authenticates ZIP's *internal* integrity only. It says
    nothing about later edits to a still-existing local web/JSON/MD file.
    Return False and let the scheduler regenerate; never claim unchanged.
    This is local integrity checking, NOT external source attestation.
    """
    root=Path(output)
    zip_path=Path(archive)
    if root.is_symlink() or zip_path.is_symlink():
        return False
    expected=set()
    for market in ("kr","us"):
        expected.add(f"ranked_maturity_{market}_research.json")
        expected.add(f"site/ranked_maturity_{market}.html")
        for period in PERIODS:
            expected.add(f"reports/ranked_maturity_{period}_{market}.md")
            expected.add(f"site/ranked_maturity_{period}_{market}.html")
    if len(expected)!=16:
        raise RuntimeError("Incomplete maturity derived inventory")
    with ZipFile(zip_path) as saved:
        manifest=json.loads(saved.read("MANIFEST.json"))
        entries={item["path"]:item for item in manifest["files"]}
        if not expected.issubset(entries):
            return False
        for relative in expected:
            live=root/relative
            if (live.is_symlink() or live.parent.is_symlink() or
                not live.is_file() or live.stat().st_size!=entries[relative]["bytes"]):
                return False
            digest=sha256()
            with live.open("rb") as source:
                for chunk in iter(lambda: source.read(1024*1024), b""):
                    digest.update(chunk)
            if digest.hexdigest()!=entries[relative]["sha256"]:
                return False
    return True


def read_maturity_schedule_config(file:Path) -> dict:
    """Read *both* markets' explicit local evidence; never discover fallbacks."""
    location=Path(file)
    if (location.is_symlink() or location.parent.is_symlink() or
        not location.is_file() or not 0<location.stat().st_size<=MAX_CONFIG_BYTES):
        raise ValueError("Missing/linked/oversized maturity schedule config")
    try:
        parsed=json.loads(location.read_bytes(),object_pairs_hook=_unique)
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Invalid or duplicate maturity schedule config JSON") from exc
    if (not isinstance(parsed,dict) or
        set(parsed)!={"schema_version","markets"} or
        parsed["schema_version"]!=CONFIG_SCHEMA or
        not isinstance(parsed["markets"],dict) or
        set(parsed["markets"])!=set(MARKETS)):
        raise ValueError("Maturity schedule config requires exact schema and KR/US")
    specs={}
    for market in MARKETS:
        row=parsed["markets"][market]
        if not isinstance(row,dict) or set(row)!=KEYS:
            raise ValueError("Maturity schedule market config requires exact original source fields")
        spec={key:_path(row[key],file=key!="features_dir") for key in sorted(KEYS)}
        specs[market]=spec
    if (specs["KR"]["freeze"].resolve()==specs["US"]["freeze"].resolve() or
        specs["KR"]["score_ledger"].resolve()==specs["US"]["score_ledger"].resolve()):
        # A shared WATCH ledger is valid, but the two independently frozen
        # source score cohorts require explicit distinct market seal/score DB.
        raise ValueError("Maturity schedule needs distinct KR/US score+frozen source")
    return specs


def _validate_report(report:dict,market:str) -> str:
    if (not isinstance(report,dict) or report.get("status")!=MATURITY_STATUS or
        report.get("market")!=market or
        report.get("outcome_labels_read") is not False or
        report.get("official_leader_promotions")!=0 or
        report.get("actual_future_leader_skill_certified") is not False or
        report.get("precision_at_k") is not None or
        report.get("recall_at_k") is not None):
        raise ValueError("Unsafe maturity schedule research/outcome certification")
    html=render_ranked_maturity_dashboard(report)
    return html


def _fingerprint(report:dict) -> dict:
    """Capture locally pinned sources + market day + due-status transition.

    Deadline may pass *within* an exchange local day, so date alone cannot
    control deduplication. The two status counts are part of the fingerprint.
    """
    return {
        "market":report["market"],
        "model_version":report["model_version"],
        "market_as_of_day":report["market_as_of_day"],
        "ranked_snapshot_sha256":report["frozen_rank_sha256"],
        "definition_rule_sha256":report["label_definition_sha256"],
        "original_watch_first_numeric_sha256":
            report["native_first_watch_score_binding_sha256"],
        "first_score_cohort_size":report["frozen_first_score_count"],
        "top_k":report["selected_top_k_count"],
        "horizon_pending":report["full_horizon_pending_count"],
        "horizon_elapsed":report["full_horizon_elapsed_count"],
        "retrospective_seal":report["retrospective_freeze"],
    }


def audit_maturity_schedule_sources(
    specs:dict, *, clock:datetime, sample_limit:int=100,
) -> dict:
    """Preflight BOTH sealed cohorts before writing a single scheduled page."""
    if (clock.tzinfo is None or clock.utcoffset() is None or
        type(sample_limit) is not int or not 1<=sample_limit<=1000):
        raise ValueError("Scheduled maturity requires aware cutoff/sample_limit")
    if not isinstance(specs,dict) or set(specs)!=set(MARKETS):
        raise ValueError("Scheduled maturity requires both market source paths")
    now=clock.astimezone(timezone.utc)
    reports={}
    fingerprints={}
    ids={}
    for market in MARKETS:
        source=specs[market]
        if not isinstance(source,dict) or set(source)!=KEYS:
            raise ValueError("Missing paired market maturity source paths")
        report=audit_ranked_maturity(
            source["freeze"],source["definition_file"],
            source["score_ledger"],source["watch_ledger"],source["features_dir"],
            as_of=now.isoformat(),clock=now,sample_limit=sample_limit,
        )
        _validate_report(report,market)
        for period in PERIODS:
            render_maturity_period_markdown(report,period)
            render_maturity_period_html(report,period)
        reports[market]=report
        fingerprints[market]=_fingerprint(report)
        ids[market]=sha256(json.dumps(
            fingerprints[market],sort_keys=True,separators=(",",":")
        ).encode()).hexdigest()[:20]
    return {
        "reports":reports,
        "maturity_market_fingerprints":fingerprints,
        "maturity_market_run_ids":ids,
        "evaluated_at_utc":now.isoformat(),
        "reported_outcome_labels":False,
        "independent_source_pit_certified":False,
        "official_leader_promotions":0,
    }


def _plain(value:object) -> str:
    return str(value).replace("|"," ").replace("\r"," ").replace("\n"," ").replace("<"," ").replace(">"," ")


def render_maturity_period_markdown(report:dict,period:str) -> str:
    _validate_report(report,report.get("market"))
    if period not in PERIOD_NAMES:
        raise ValueError("Invalid ranked maturity brief period")
    horizon=report["predeclared_horizon_days"]
    total=report["selected_top_k_count"]
    elapsed=report["full_horizon_elapsed_count"]
    pending=report["full_horizon_pending_count"]
    waiting=report["awaiting_mature_outcome_evidence_count"]
    title=PERIOD_NAMES[period]
    lines=[
        f"# EraLeader {title} Top-K 미래 대장주 후보 평가기간 만기 연구",
        f"- 시장: {_plain(report['market'])}, 모델: {_plain(report['model_version'])}",
        f"- 연구 평가시각 UTC: {_plain(report['as_of_utc'])}",
        f"- 최초 순위 스냅샷: {_plain(report['snapshot_at_utc'])}",
        f"- 최초 봉인: {_plain(report['frozen_at_utc'])}",
        f"- 사전 규칙: {_plain(report['label_definition_id'])} / 기간 {horizon}일",
        "- **확정 대장주 0건 · 실전 적중률 N/A · 실제 정답 라벨 없음**",
        f"- 고정 Top-K 분모 {total}개, 기간 미경과 {pending}개, 기간 경과 {elapsed}개",
        f"- 기간 경과 후 독립 결과 **미확인**/검증 대기 {waiting}개 · 부정 또는 실패로 해석 금지",
        f"- 다음 종료 시각 UTC: {_plain(report['next_horizon_end_utc'] or 'N/A')}",
        f"- 소급 봉인 여부: {bool(report['retrospective_freeze'])} (소급이면 전향 예측 아님)",
        "",
        "## 사전 고정 후보 표본 (실적 성과가 아니라 최초 score 기록)",
        "| 순위 | 로컬 영구 연구 ID | 평가기간 종료 UTC | 상태 |",
        "|---|---|---|---|",
    ]
    for item in report["selected_candidate_sample"]:
        lines.append("| "+ " | ".join(_plain(item.get(field)) for field in (
            "rank","security_id","horizon_end_utc","status"
        ))+" |")
    if not report["selected_candidate_sample"]:
        lines.append("| N/A | 표본 미표시 | N/A | N/A |")
    lines += [
        "",
        "- 표본 누락이 평가 분모를 축소하지 않으며 WATCH 누락을 실패나 후보 약화로 간주하지 않음",
        "- 원천 PIT·시계/발행자 독립 공증·현재 실제 미래 성과 확인 없음",
        "- 가격캐시 및 최근 WATCH 신선도와 무관한 별도 READ-ONLY 로컬 스케줄 모드",
        "- 외부 API 0회 · 메시지 발송 0회 · 자동 주문 0회 · 실전 성과 미검증",
        "",
    ]
    return "\n".join(lines)


def render_maturity_period_html(report:dict,period:str) -> str:
    base=_validate_report(report,report.get("market"))
    if period not in PERIOD_NAMES:
        raise ValueError("Invalid ranked maturity brief period")
    heading=f"<h2>{escape(PERIOD_NAMES[period])} 연구 스냅샷 — 실전 성과 N/A</h2>"
    if "<main>" not in base:
        raise ValueError("Maturity dashboard does not have its expected main region")
    return base.replace("<main>","<main>"+heading,1)


def publish_scheduled_maturity_reports(audited:dict,out:Path) -> dict:
    """Write 16 safe derived KR+US files: two JSON + two base HTML + twelve briefs.

    Each per-market JSON research manifest is written LAST. Scheduler commits
    its verified checkpoint only after an archive SHA+source recheck.
    """
    if (not isinstance(audited,dict) or
        set(audited.get("reports",{}))!=set(MARKETS)):
        raise ValueError("Two-market maturity preflight required before publishing")
    target=Path(out)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("Symlink maturity report output forbidden")
    all_files=[]
    for market in MARKETS:
        report=audited["reports"][market]
        dashboard=_validate_report(report,market)
        pages=[]
        for period in PERIODS:
            markdown=target/"reports"/f"ranked_maturity_{period}_{market.lower()}.md"
            html=target/"site"/f"ranked_maturity_{period}_{market.lower()}.html"
            _atomic_text(markdown,render_maturity_period_markdown(report,period))
            _atomic_text(html,render_maturity_period_html(report,period))
            pages.extend((markdown,html))
        dashboard_path=target/"site"/f"ranked_maturity_{market.lower()}.html"
        _atomic_text(dashboard_path,dashboard)
        artifact=target/f"ranked_maturity_{market.lower()}_research.json"
        _atomic_text(artifact,json.dumps(report,sort_keys=True,
                                        ensure_ascii=False,indent=2)+"\n")
        all_files.extend((*pages,dashboard_path,artifact))
    if len(all_files)!=16 or not all(p.is_file() for p in all_files):
        raise RuntimeError("Scheduled maturity publication requires 16 derived pages")
    return {
        "ranked_maturity_report_pages":len(all_files),
        "ranked_market_run_ids":audited["maturity_market_run_ids"],
        "official_leader_promotions":0,
        "messages_sent":0,
        "external_api_calls":0,
        "outcome_labels_read":False,
        "derived_paths":[str(p) for p in all_files],
    }
