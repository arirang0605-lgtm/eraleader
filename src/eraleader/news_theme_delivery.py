"""ER-NC-08: opt-in, research-only HTML + reports + deduplicated dry-run preview.

Only consumes already-derived PIT news-market and theme-lifecycle summaries.
Original price ranking, official data adapters, live delivery and brokers unchanged.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
from typing import Any

from .delivery import BASE_CSS
from .news_catalyst_adapter import _time

SCHEMA = "eraleader.er_nc08_public_sidecar.v1"
THEME_STATES = {
    "EMERGING", "RISING", "CONSOLIDATING", "WEAKENING",
    "DORMANT", "REACTIVATING", "UNKNOWN",
}
NEWS_DIAGNOSES = {
    "positive_news_positive_price", "positive_news_negative_price",
    "strong_price_no_verified_news", "repeated_news", "stale_or_unknown",
}
MAX_DIAGNOSTICS = 250
MAX_THEMES = 150


def _safe(value: Any) -> str:
    return escape(str(value if value is not None else "N/A"), quote=True)


def _markdown(value: Any) -> str:
    text = str(value if value is not None else "N/A")
    return escape(re.sub(r"[\r\n|]+", " ", text).strip(), quote=True)


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def validate_research(report: dict) -> dict:
    """Validate public research *derived fields* before any rendering."""
    if type(report) is not dict or report.get("schema") != SCHEMA:
        raise ValueError("News/theme research schema is not supported")
    if (report.get("research_only") is not True or
            report.get("official_leaders") != 0 or
            report.get("trading_enabled") is not False):
        raise ValueError("Uncertified news cannot be displayed as official trade")
    if report.get("market") not in ("KR", "US"):
        raise ValueError("Unknown news-theme research market")
    decision = _time(report["as_of"], "as_of")
    market_session = report.get("market_session")
    if type(market_session) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", market_session):
        raise ValueError("Invalid market session date")
    if date.fromisoformat(market_session) > decision.date():
        raise ValueError("Future market session cannot enter historic research")
    diagnostics = report.get("news_diagnostics")
    themes = report.get("themes")
    if (type(diagnostics) is not list or len(diagnostics) > MAX_DIAGNOSTICS or
            type(themes) is not list or len(themes) > MAX_THEMES):
        raise ValueError("Oversized or missing derived news/theme rows")
    quality = report.get("news_quality_status", "UNVERIFIED")
    if quality not in ("OK", "NO_VISIBLE_EVENTS", "STALE", "UNVERIFIED", "MISSING", "UNKNOWN"):
        raise ValueError("Unrecognized news coverage quality")
    for row in diagnostics:
        if (type(row) is not dict or
                row.get("schema") != "eraleader.er_nc_market_news_response.v1" or
                row.get("research_only") is not True or
                row.get("official_leaders") != 0 or
                row.get("recommendation") is not None or
                row.get("diagnosis") not in NEWS_DIAGNOSES or
                type(row.get("reason_codes")) is not list or
                type(row.get("event_evidence_ids")) is not list):
            raise ValueError("News row is not an authorized research diagnostic")
        if _time(row["as_of"], "news_row_as_of") > decision:
            raise ValueError("Future news diagnostic cannot be displayed")
        if _time(row["market_data_available_at"], "price_available_at") > decision:
            raise ValueError("Future price diagnostic cannot be displayed")
    for row in themes:
        if (type(row) is not dict or
                row.get("schema") != "eraleader.er_nc_theme_lifecycle.v1" or
                row.get("research_only") is not True or
                row.get("official_leaders") != 0 or
                row.get("state") not in THEME_STATES or
                type(row.get("reason_codes")) is not list):
            raise ValueError("Theme row not certified for research display")
        if _time(row["as_of"], "theme_as_of") > decision:
            raise ValueError("Future theme outcome cannot be displayed")
    strategies = report.get("author_strategies", [])
    if type(strategies) is not list or len(strategies) > 4:
        raise ValueError("Author status list contract invalid")
    for row in strategies:
        if (type(row) is not dict or row.get("trade_permission") != "NO_ORDER"
                or row.get("executable") is not False
                or row.get("status") not in ("UNKNOWN", "NOT_READY")):
            raise ValueError("Unverified author strategy must remain non-trading")
        if _time(row["as_of"], "author_as_of") > decision:
            raise ValueError("Future author review not eligible")
    return report


def _dedup_alerts(report: dict) -> list[dict]:
    """Deterministic preview, not a live outbox or an alert transmission."""
    alerts: dict[str, dict] = {}
    for row in report["news_diagnostics"]:
        kind = ("NEWS_INVALIDATED" if
                "MATERIAL_FACT_INVALIDATED_AFTER_ORIGINAL_VERSION" in row["reason_codes"]
                else "NEWS_STALE" if "NEWS_INPUT_DEGRADED" in row["reason_codes"]
                else None)
        if kind is not None:
            ref = str(row.get("security_id", "UNKNOWN"))
            material = {"kind": kind, "reference": ref}
            key = sha256(_json_bytes(material)).hexdigest()
            alerts[key] = {**material, "dedup_key": key, "status": "DRY_RUN_ONLY"}
    for row in report["themes"]:
        kind = {"REACTIVATING": "THEME_REACTIVATING",
                "WEAKENING": "THEME_WEAKENING"}.get(row["state"])
        if kind is not None:
            material = {
                "kind": kind,
                "reference": str(row.get("theme_id", "UNKNOWN")),
                "episode_id": str(row.get("episode_id") or "UNKNOWN"),
            }
            key = sha256(_json_bytes(material)).hexdigest()
            alerts[key] = {**material, "dedup_key": key, "status": "DRY_RUN_ONLY"}
    return [alerts[key] for key in sorted(alerts)]


def render_research_html(report: dict) -> str:
    report = validate_research(report)
    news_rows = []
    for row in report["news_diagnostics"]:
        cells = (
            row.get("security_id"), row["diagnosis"],
            ", ".join(map(str, row["reason_codes"])),
            ", ".join(map(str, row["event_evidence_ids"])) or "N/A",
            row.get("market_data_available_at"),
        )
        news_rows.append("<tr>" + "".join(f"<td>{_safe(v)}</td>" for v in cells) + "</tr>")
    theme_rows = []
    for row in report["themes"]:
        cells = (
            row.get("theme_id"), row["state"], row.get("episode_id"),
            row.get("catalyst_state"), row.get("as_of"),
            ", ".join(map(str, row["reason_codes"])) or "N/A",
        )
        theme_rows.append("<tr>" + "".join(f"<td>{_safe(v)}</td>" for v in cells) + "</tr>")
    strategy_rows = []
    for row in report.get("author_strategies", []):
        cells = (
            row.get("strategy_id"), row["status"],
            row["trade_permission"], row.get("as_of"),
        )
        strategy_rows.append("<tr>" + "".join(f"<td>{_safe(v)}</td>" for v in cells) + "</tr>")
    strategy_table = (
        "<h2>저자 원형 전략 출처 확인 (비거래)</h2><div class='wrap'><table>"
        "<tr><th>전략</th><th>준비</th><th>주문</th><th>시점</th></tr>"
        + "".join(strategy_rows) + "</table></div>"
        if strategy_rows else "<p><small>저자 원형 전략 규칙: 아직 독립 검증 전 / N/A</small></p>"
    )
    warning = (
        "뉴스 수신상태 미확인 또는 부재 — 호재/악재 없음으로 해석 금지"
        if report["news_quality_status"] not in {"OK", "NO_VISIBLE_EVENTS"}
        else "뉴스는 증거 옆정보이며 가격·후보를 자동 승격하지 않습니다"
    )
    alert_count = len(_dedup_alerts(report))
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 뉴스·테마 읽기 전용 연구</title>"
        f"<style>{BASE_CSS}</style></head><body>"
        "<header><h1>EraLeader · 뉴스·테마 관측</h1>"
        "<nav><a href='index.html'>기존 화면</a> "
        "<a href='kr.html'>한국</a> <a href='us.html'>미국</a></nav>"
        "</header><main>"
        "<div class='note'><strong>연구용 · 실전 매수·매도/대장주 확정 금지</strong>"
        f"<p>{_safe(warning)}</p>"
        "<p>기사 원문·미검증 수혜주·실전 신호를 출력하지 않습니다.</p></div>"
        "<div class='stats'>"
        f"<div class='stat'>시장 {_safe(report['market'])}<br>{_safe(report['market_session'])}</div>"
        f"<div class='stat'>시점 {_safe(report['as_of'])}</div>"
        f"<div class='stat'>뉴스 품질 {_safe(report['news_quality_status'])}</div>"
        f"<div class='stat'>DRY-RUN 알림 {alert_count}건 / 실발송 0건</div>"
        "</div><h2>뉴스 ↔ 주가 반응 (미검증 설명 연구)</h2>"
        "<div class='wrap'><table><tr><th>주권 ID</th><th>진단</th><th>사유</th>"
        "<th>확인된 이벤트</th><th>시세 이용가능시각</th></tr>"
        + "".join(news_rows) + "</table></div>"
        "<h2>테마 주도력·생존·재활성화 (가격 연구)</h2>"
        "<div class='wrap'><table><tr><th>테마 ID</th><th>가격상태</th>"
        "<th>episode</th><th>뉴스 재료 상태(별도)</th><th>근거시각</th>"
        "<th>불확실성</th></tr>" + "".join(theme_rows) + "</table></div>"
        + strategy_table +
        "<p><small>상장/상폐·기업행동 PIT, 미래 대장주 적중률은 N/A. "
        "모든 경보는 연구용 DRY-RUN이며 실제 알림/주문이 없습니다.</small></p>"
        "</main></body></html>"
    )


def render_research_markdown(report: dict, period: str) -> str:
    report = validate_research(report)
    if period not in {"daily", "weekly", "monthly"}:
        raise ValueError("Unknown research reporting period")
    lines = [
        f"# EraLeader {period} 뉴스·테마 연구 보고 (DRY-RUN)",
        f"- 시장: {_markdown(report['market'])}",
        f"- 세션: {_markdown(report['market_session'])}",
        f"- 보고 시점: {_markdown(report['as_of'])}",
        f"- 뉴스 수신품질: {_markdown(report['news_quality_status'])}",
        "- 공식 대장주·매수추천·실전 알림: 없음 / N/A",
        "- 첫 관측시각·원문 라이선스·상장/기업행동 PIT 검증 전",
        "",
        "## 뉴스/시장 반응: 인과 확정 아님",
        "| 주권ID | 진단 | 시장관측 이용시각 | 근거 사건 ID | 사유·불확실성 |",
        "|---|---|---|---|---|",
    ]
    for row in report["news_diagnostics"]:
        lines.append(
            f"| {_markdown(row.get('security_id'))} | {_markdown(row['diagnosis'])} | "
            f"{_markdown(row['market_data_available_at'])} | "
            f"{_markdown(','.join(map(str,row['event_evidence_ids'])))} | "
            f"{_markdown(','.join(map(str,row['reason_codes'])))} |"
        )
    lines += [
        "", "## 테마 가격 상태 (뉴스 근거와 별도)",
        "| 테마 | 상태 | episode | 재료 상태 | 기준시각 |",
        "|---|---|---|---|---|",
    ]
    for row in report["themes"]:
        lines.append(
            f"| {_markdown(row.get('theme_id'))} | {_markdown(row['state'])} | "
            f"{_markdown(row.get('episode_id'))} | {_markdown(row.get('catalyst_state'))} | "
            f"{_markdown(row.get('as_of'))} |"
        )
    alerts = _dedup_alerts(report)
    lines += [
        "", "## 중복 제거 DRY-RUN 경고",
        f"- 생성 {len(alerts)}건, 실제 전송 0건",
        "- 동일 종류/종목/episode 상태는 하나의 미리보기로 제한",
        "",
        "## 검증 보류",
        "- 실제 역사 PIT 전체/기업행동·상폐/전향 적중률 N/A",
        "- 저자 매매 원형 독립 출처·실행 규칙 검증 N/A",
        "- NEWS OFF일 때 기존 대장주 점수·목록·기존 보고는 불변",
        "",
    ]
    return "\n".join(lines)


def _payload_files(report: dict) -> dict[str, bytes]:
    preview = {
        "schema": "eraleader.er_nc08_dry_run_alert_preview.v1",
        "market": report["market"],
        "as_of": report["as_of"],
        "alerts": _dedup_alerts(report),
        "delivery_mode": "DRY_RUN_ONLY",
        "real_messages_sent": 0,
    }
    return {
        "site/er_nc08_research.html": render_research_html(report).encode("utf-8"),
        "reports/er_nc08_daily.md": render_research_markdown(report, "daily").encode("utf-8"),
        "reports/er_nc08_weekly.md": render_research_markdown(report, "weekly").encode("utf-8"),
        "reports/er_nc08_monthly.md": render_research_markdown(report, "monthly").encode("utf-8"),
        "alerts_preview.json": _json_bytes(preview),
    }


def write_research_bundle(
    report: dict, output_root: str | Path, *, enabled: bool = False
) -> list[Path]:
    """Atomic fresh research bundle; repeated identical output is a no-op.

    Never edits existing original market dashboards, WATCH, SQLite or reports.
    Caller must explicitly opt in and choose a new isolated output directory.
    """
    if not enabled:
        return []
    validate_research(report)
    import shutil
    import tempfile

    output_root = Path(output_root)
    if output_root.is_symlink() or not output_root.parent.is_dir():
        raise ValueError("Output root must be ordinary new directory under existing parent")
    if any(parent.is_symlink() for parent in output_root.parents):
        raise ValueError("Output root cannot be under symlink")
    contents = _payload_files(report)
    expected = [output_root / name for name in contents]
    if output_root.exists():
        if not output_root.is_dir():
            raise FileExistsError("Research output path is not a directory")
        for name, data in contents.items():
            target = output_root / name
            if target.is_symlink() or not target.is_file() or target.read_bytes() != data:
                raise FileExistsError("Different or incomplete research output already exists")
        return expected

    scratch = Path(tempfile.mkdtemp(prefix=".er_nc08_stage_", dir=output_root.parent))
    os.chmod(scratch, 0o700)
    try:
        for relative, data in contents.items():
            destination = scratch / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(destination.parent, 0o700)
            with destination.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(destination, 0o600)
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError("Research output appeared during preparation")
        # A new *directory* appears in one atomic operation after all five
        # outputs have been fully written. The caller owns the chosen new name.
        os.rename(scratch, output_root)
    except BaseException:
        if scratch.exists():
            shutil.rmtree(scratch)
        raise
    return expected
