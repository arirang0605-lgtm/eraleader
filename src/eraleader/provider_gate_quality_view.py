"""6_2: explicit, non-certifying web view of the in-process provider WATCH gate.

The caller MUST supply the gate returned by audit_candidate_provider_gate.
This renderer never reads historical source files, reconstructs claims, sends
messages, publishes positive leader status, or upgrades PIT certification.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import os
from pathlib import Path
import re
import tempfile

from .delivery import BASE_CSS
from .issuer_class_bridge import STATUS_MATCH, STATUS_BLOCKED, STATUS_LATE
from .provider_candidate_gate import GATE_WATCH, GATE_BLOCK
from .provider_dual_source_audit import (
    STATUS_CONSISTENT, STATUS_BLOCKED as PAIR_BLOCKED,
    STATUS_LATE as PAIR_LATE,
)

SHA = re.compile(r"[a-f0-9]{64}\Z")
BLOCKER_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,119}\Z")
PAIR_STATUSES = frozenset((STATUS_CONSISTENT, PAIR_BLOCKED, PAIR_LATE))
ISSUER_STATUSES = frozenset((
    STATUS_MATCH, STATUS_BLOCKED, STATUS_LATE, "NOT_EVALUATED_PAIR_BLOCKED",
))
MAX_BLOCKERS = 200


def _sha(value: object) -> bool:
    return type(value) is str and SHA.fullmatch(value) is not None


def _count(value: object, limit: int = 50000) -> bool:
    return type(value) is int and 0 <= value <= limit


def _validate(gate: dict) -> tuple[str, bool, dict[str, int]]:
    if not isinstance(gate, dict):
        raise ValueError("Missing local provider gate summary")
    market = gate.get("market")
    if market not in ("KR", "US"):
        raise ValueError("Unknown provider quality market")
    ts = gate.get("decision_at_utc")
    try:
        at = datetime.fromisoformat(ts) if type(ts) is str else None
    except ValueError as exc:
        raise ValueError("Invalid provider decision timestamp") from exc
    if at is None or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Missing timezone in provider decision cutoff")

    for key in (
        "publisher_independently_authenticated",
        "legal_issuer_identity_independently_verified",
        "historic_membership_pit_certified",
        "official_candidate_promotion_allowed",
        "leader_accuracy_certified",
    ):
        if gate.get(key) is not False:
            raise ValueError("Forged provider independence/official certification flag")
    if not _count(gate.get("official_leader_promotions"), 0):
        raise ValueError("Official leader count must remain zero")
    for key in ("source_consistency_only", "source_pair_consistency_only"):
        if gate.get(key) is not True:
            raise ValueError("Local evidence cannot be promoted beyond research")
    for key in (
        "research_watch_allowed",
        "require_original_first_ingest_pins",
        "original_first_ingest_pins_locally_consistent",
        "issuer_class_bridge_required",
    ):
        if type(gate.get(key)) is not bool:
            raise ValueError("Invalid local provider quality boolean")

    allowed = gate["research_watch_allowed"]
    if gate.get("status") != (GATE_WATCH if allowed else GATE_BLOCK):
        raise ValueError("Claimed research permission contradicts gate status")
    if gate.get("source_pair_status") not in PAIR_STATUSES:
        raise ValueError("Unrecognized claimed provider pair quality status")
    for key in (
        "source_pair_digest_sha256",
        "source_pair_bundle_sha256_a",
        "source_pair_bundle_sha256_b",
    ):
        if not _sha(gate.get(key)):
            raise ValueError("Missing/malformed local provider source digest")

    total = gate.get("candidate_issuer_count")
    matched = gate.get("locally_correlated_candidate_issuer_count")
    class_count = gate.get("issuer_class_matched_candidates")
    if (not _count(total) or not _count(matched) or not _count(class_count)
            or matched > total or class_count > total):
        raise ValueError("Invalid local candidate counts")

    blockers = gate.get("blocker_counts")
    if (not isinstance(blockers, dict) or len(blockers) > MAX_BLOCKERS or
            any(type(code) is not str or not BLOCKER_CODE.fullmatch(code)
                or not _count(count, 50000) or count == 0
                for code, count in blockers.items()) or
            not _count(gate.get("blocker_count"), 10_000_000) or
            sum(blockers.values()) != gate["blocker_count"]):
        raise ValueError("Invalid/miscounted provider quality blockers")
    if allowed and (gate["source_pair_status"] != STATUS_CONSISTENT or
                    total == 0 or matched != total or blockers):
        raise ValueError("Research WATCH cannot be permitted with missing evidence")
    if not allowed and not blockers:
        raise ValueError("Blocked research gate requires explicit blocker evidence")

    pinned = gate["require_original_first_ingest_pins"]
    if (gate["original_first_ingest_pins_locally_consistent"] is not pinned or
            (_sha(gate.get("source_pair_original_pin_sha256")) if pinned
             else gate.get("source_pair_original_pin_sha256") is None) is not True):
        raise ValueError("Unreconciled first-ingest raw PIN state")

    requires_class = gate["issuer_class_bridge_required"]
    class_status = gate.get("issuer_class_bridge_status")
    class_digest = gate.get("issuer_class_evidence_sha256")
    if requires_class:
        if not pinned or class_status not in ISSUER_STATUSES:
            raise ValueError("Issuer class gate needs pinned original sources")
        if class_status == "NOT_EVALUATED_PAIR_BLOCKED":
            if (gate["source_pair_status"] == STATUS_CONSISTENT
                    or class_digest is not None or class_count != 0):
                raise ValueError("Missing issuer audit despite consistent provider pair")
        elif not _sha(class_digest):
            raise ValueError("Invalid issuer class local evidence SHA")
        if (allowed and
                (class_status != STATUS_MATCH or class_count != total)):
            raise ValueError("Positive research WATCH lacks individual class match")
    elif class_status is not None or class_digest is not None or class_count:
        raise ValueError("Unexpected issuer class evidence when not requested")
    return market, allowed, dict(sorted(blockers.items()))


def render_provider_gate_quality(gate: dict, *, show_history: bool = False) -> str:
    """Render the ACTUAL original-receipt/candidate gate verdict as sanitized HTML."""
    market, allowed, blockers = _validate(gate)
    def safe(value: object) -> str:
        return escape(str(value), quote=True)

    raw_state = ("로컬 최초 원본 SHA 대조" if gate["require_original_first_ingest_pins"]
                 else "미요청 — 과거 원본 첫 등록 PIN 확인 없음")
    cls_status = gate["issuer_class_bridge_status"]
    if cls_status is None:
        class_state = "미요청 — 법인ID·주식클래스 보강 검증 없음"
    elif cls_status == STATUS_MATCH:
        class_state = "법인ID·주식클래스 로컬 주장 일치 (미인증)"
    elif cls_status == "NOT_EVALUATED_PAIR_BLOCKED":
        class_state = "공급자 쌍 차단으로 미실행"
    else:
        class_state = "법인ID·주식클래스 불일치 또는 소급 검열"
    pair_state = ("두 공급자 주장 일치 (미인증)" if
                  gate["source_pair_status"] == STATUS_CONSISTENT else
                  "공급자 자료 불일치 또는 동시점 이용 불가")
    verdict = ("연구용 WATCH 허용 — 공식 대장주 인증 아님" if allowed else
               "연구용 WATCH 보류 — 신규 신호 등록 금지")
    rows = "".join(
        "<tr><td>" + safe(reason) + "</td><td>" + safe(count) + "</td></tr>"
        for reason, count in blockers.items()
    ) or '<tr><td colspan="2">로컬 게이트 차단 0건 · 공식 원천 PIT 인증은 별도 필요</td></tr>'
    link = (f'<a href="research_{market.lower()}.html">통합 연구 화면</a>'
            if allowed else "후보 연구 화면 발행 보류")
    history_link=(f'<a href="provider_quality_history_{market.lower()}.html">과거 원천 검증 변화 이력</a>'
                  if show_history else "")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader {safe(market)} 원천 검증 품질 (로컬)</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 후보 원천 검증</h1>
<div>{safe(market)} 시장 · 결정시각 {safe(gate["decision_at_utc"])}</div>
<nav>{link} {history_link}</nav></header><main>
<div class="note"><strong>{verdict}</strong><p>
이 페이지는 로컬 입력 자료 간의 일치·보류 사유를 보여주는 연구 진단입니다.
거래소·공시 원천 발행자와 최초 수신시각을 독립 공증한 것이 아닙니다.
공식 확정 대장주: 0건 · 실전 적중률 N/A · 외부 API 미연결.</p></div>
<div class="stats">
<div class="stat">연구 대상 후보<br><strong>{total_value(gate, "candidate_issuer_count")}</strong></div>
<div class="stat">양 공급자 로컬 일치<br><strong>{total_value(gate, "locally_correlated_candidate_issuer_count")}</strong></div>
<div class="stat">추가 클래스 대조<br><strong>{total_value(gate, "issuer_class_matched_candidates")}</strong></div>
<div class="stat">보류 사유<br><strong>{total_value(gate, "blocker_count")}건</strong></div></div>
<h2>검증 상태의 세 단계 (모두 독립 인증 아님)</h2>
<div class="wrap"><table><thead><tr><th>검증 범위</th><th>로컬 상태</th></tr></thead>
<tbody><tr><td>서로 다른 두 공급자 선언</td><td>{pair_state}</td></tr>
<tr><td>최초 원본 SHA PIN</td><td>{raw_state}</td></tr>
<tr><td>법인ID·주식클래스</td><td>{class_state}</td></tr>
</tbody></table></div>
<h2>후보 보류 원인 (전체 코드별 건수)</h2>
<div class="wrap"><table><thead><tr><th>진단 코드</th><th>건수</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p><small>봉인한 로컬 주장 다이제스트: {safe(gate["source_pair_digest_sha256"])}
· 로컬 일치가 실제 역사 종목군/PIT 또는 미래 발굴 성능을 인증하지 않습니다.</small></p>
</main><footer>EraLeader · 실전 주문/메시지 발송 없음 · 미인증 연구 화면</footer></body></html>"""


def total_value(gate: dict, key: str) -> str:
    """Only small, type-validated integers enter the output."""
    return str(gate[key])


def write_provider_gate_quality(gate: dict, site_dir: Path, *, show_history: bool = False) -> Path:
    """Prevalidate then atomically publish only sanitized, market-scoped HTML."""
    html = render_provider_gate_quality(gate,show_history=show_history)
    market = gate["market"]
    folder = Path(site_dir)
    target = folder / f"provider_quality_{market.lower()}.html"
    if (folder.is_symlink() or folder.parent.is_symlink()
            or target.is_symlink() or (folder.exists() and not folder.is_dir())):
        raise ValueError("Unsafe symlink or non-directory provider quality target")
    folder.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=folder, prefix=".provider-quality-",
            suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(html)
        if target.is_symlink():
            raise ValueError("Unsafe symlink provider quality target")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
