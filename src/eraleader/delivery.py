"""Offline web dashboard, markdown reports, and non-sending alert previews."""
from __future__ import annotations
from html import escape
from pathlib import Path
import json
import re

BASE_CSS = """body{font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;
background:#f2f5fa;color:#152b42;margin:0}header{padding:30px 5%;background:#102f50;color:white}
h1{font-size:2rem;margin:0 0 6px}main{margin:22px auto;max-width:1250px;padding:0 18px}
.note{padding:15px;background:#ffefda;border-radius:10px;line-height:1.6;margin:16px 0}
.stats{display:flex;flex-wrap:wrap;gap:12px}.stat{background:#fff;padding:18px;border-radius:10px;min-width:180px;flex:1}
table{border-collapse:collapse;background:white;width:100%;font-size:.95rem}th,td{padding:11px;text-align:left;border-bottom:1px solid #e0e8f0}th{background:#dceaf8}
.wrap{overflow-x:auto;border-radius:12px}nav a{color:#cee9ff;margin-right:20px}
small{color:#63758b}h2{margin-top:25px}a{color:#1c5c91}
footer{padding:20px;text-align:center} @media(max-width:670px){h1{font-size:1.6rem}th,td{padding:8px;font-size:.83rem}}"""

def render_dashboard(snapshot: dict) -> str:
    def v(value):
        if value is None:
            return "N/A"
        return escape(str(value))
    rows=[]
    for item in snapshot["rows"]:
        cls=escape(item["state"])
        rows.append("<tr>"+
            "".join(f"<td>{v(value)}</td>" for value in (
              item["rank"],item["security_id"],item["name"],item["venue"],
              item["price_strength_25"],
              f'{item["return_6m"]*100:.1f}%' if item["return_6m"] is not None else None,
              item["total_score_100"],cls))+
            "</tr>")
    api_note=("공식 API 일봉 연결 · PIT/상장 이력 미인증"
              if snapshot.get("official_api_evidence") else "API 미연결")
    warning=escape(snapshot["note"])
    source=escape(snapshot.get("data_source","unknown"))
    as_of=escape(snapshot["market_last_observation"])
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>EraLeader — 로컬 후보 관찰</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 시대의 대장주 검색기</h1>
<div>한국·미국 주식, 미래 대장주 조기 발굴 연구 시스템 · 로컬 개발판</div>
<nav><a href="kr.html">한국</a><a href="us.html">미국</a></nav></header>
<main><h2>{escape(snapshot["source_market"])} 시장 · 관찰 목록</h2>
<div class="note">⚠️ <strong>검증 전 관찰 화면</strong><br>{warning}<br>
재무·산업 데이터와 상장폐지/기업행동 PIT 검증 전이므로 '잠재/확정 대장주'를 표기하지 않습니다.</div>
<div class="stats"><div class="stat">시장 데이터 기준일<br><strong>{as_of}</strong></div>
<div class="stat">관찰 종목 수<br><strong>{snapshot["shown"]}</strong></div>
<div class="stat">모델 버전<br><strong>{escape(snapshot["model_version"])}</strong></div></div>
<h2>가격 기반 관찰 순위 (최대 25점)</h2>
<div class="wrap"><table><thead><tr><th>순위</th><th>코드</th><th>기업</th><th>시장</th>
<th>가격점수/25</th><th>6개월 수익률</th><th>종합점수/100</th><th>상태</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><small>데이터 출처: {source} · 자료의 과거 조정 및 종목군 완전성 검증 필요.</small></p>
<p><small>현재 가격 관찰 순위는 투자 추천이나 확정 대장주 순위가 아닙니다.</small></p>
</main><footer>EraLeader local-first · {api_note} · 매매/자동 주문 기능 없음</footer></body></html>"""

def write_dashboard(snapshot: dict, site_dir: Path) -> Path:
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/("kr.html" if snapshot["source_market"]=="KR" else "us.html")
    path.write_text(render_dashboard(snapshot),encoding="utf-8")
    index=site_dir/"index.html"
    index.write_text("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                     "<title>EraLeader</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
                     "<body style='font:18px sans-serif;padding:36px'>"
                     "<h1>EraLeader 로컬 화면</h1><p>"+
                     ("공식 API 가격 관찰, PIT 인증 전 연구용입니다." if snapshot.get("official_api_evidence")
                      else "API 연결 전 연구용 가격 관찰 화면입니다.")+"</p>"
                     "<a href='kr.html'>한국 시장</a> | <a href='us.html'>미국 시장</a></body></html>",
                     encoding="utf-8")
    return path

def make_report(snapshot: dict, period: str, target: Path) -> Path:
    if period not in ("daily","weekly","monthly"):
        raise ValueError("Invalid report period")
    lines=[
      f"# EraLeader {period} 로컬 연구 보고",
      f"- 시장: {snapshot['source_market']}",
      f"- 시장 관측일: {snapshot['market_last_observation']}",
      f"- 모델: {snapshot['model_version']}",
      "- 품질: PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED",
      "- 경고: 재무·산업 데이터 및 PIT 검증 부족. 미래 대장주 확정 불가.",
      "",
      "## 가격 모멘텀 관찰 (투자 추천 아님)",
      "| 순위 | 종목 | 이름 | 6개월 수익률 | 가격점수(25점) | 판정 |",
      "|---:|---|---|---:|---:|---|"
    ]
    for row in snapshot["rows"]:
        r6=f"{100*row['return_6m']:.2f}%" if row["return_6m"] is not None else "N/A"
        name=re.sub(r'[\|\r\n]+'," ",row["name"])
        lines.append(f"| {row['rank']} | {row['security_id']} | {name} | {r6} | "
                     f"{row['price_strength_25']} | {row['state']} |")
    lines +=["", "## 검증 상태","- 대장주 발굴 성능: 미검증",
             "- 재무 PIT: 데이터 미연결", "- 역사 종목군/배당·분할: 검증 전",
             "- 보고서는 저장된 동일 분석 스냅샷만 사용. AI 재분석을 호출하지 않음.",""]
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("\n".join(lines),encoding="utf-8")
    return target


def render_integrated_dashboard(result: dict, *, show_provider_quality: bool = False) -> str:
    """Show PIT research with unmissable provenance and missing-value warnings."""
    from html import escape as esc
    if result.get("confirmed_leaders",0) or result.get("potential_leaders",0):
        if not result.get("pit_certified",False):
            raise ValueError("Uncertified leader classifications must not be rendered")
    body=[]
    for item in result["company_rows"]:
        def val(value):
            return "N/A" if value is None else esc(str(value))
        body.append("<tr>"+
          "".join(f"<td>{val(v)}</td>" for v in (
            item["security_id"],item["ticker"],item["industry_id"],
            item["revenue_yoy"],item["operating_income_yoy"],
            item["revenue_yoy_acceleration"],item["industry_revenue_yoy"],
            item["momentum_6m"],item["state"],
            ",".join(item["missing_factors"]+item.get("quality_flags",[]))))+"</tr>")
    trusted="검증 완료" if result.get("pit_certified") else "미검증 / 관찰·연구용"
    quality_nav=(f'<a href="provider_quality_{result["market"].lower()}.html" style="color:white">원천 검증 품질·보류 사유</a>'
                 if show_provider_quality and result.get('market') in ('KR','US') else '')
    quality=esc(", ".join(result.get("quality",{}).get("provenances",[])) or "원천 미상")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EraLeader 시점별 통합 분석</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 산업·실적·가격 통합 연구</h1>
<a href="index.html" style="color:white">처음으로</a> {quality_nav}</header><main>
<h2>기준시각: {esc(result["as_of"])} · {esc(result["market"])}</h2>
<div class="note"><strong>연구용: {trusted}</strong><br>
합성 자료 또는 불완전한 과거 원본이면 대장주 승격 금지.
과거 상장종목군/기업행동/원시 공시의 PIT 완전성이 확인되지 않았습니다.
<br>데이터 출처 상태: {quality}</div>
<div class="stats"><div class="stat">기업 수<br><strong>{result["company_count"]}</strong></div>
<div class="stat">초기 성장 관찰 (연구)<br><strong>{result["research_growth_screen_count"]}</strong></div>
<div class="stat">근거 부족으로 스크리닝 보류<br><strong>{result.get("research_screen_deferred_count","N/A")}</strong></div>
<div class="stat">확정 대장주<br><strong>0 — 검증 보류</strong></div></div>
<h2>시점별 기업 성장 관찰</h2>
<div class="wrap"><table><thead><tr><th>ID</th><th>티커</th><th>산업</th>
<th>매출 YoY</th><th>영업이익 YoY</th><th>매출성장 가속</th>
<th>산업 YoY</th><th>가격 6개월</th><th>상태</th><th>누락·보류</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p><small>완전한 과거 시점 데이터·미래 발굴 성능 인증 전 투자 추천 아님.</small></p>
</main></body></html>"""

def write_integrated_dashboard(result: dict, site_dir: Path, *, show_provider_quality: bool = False) -> Path:
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/f"research_{result['market'].lower()}.html"
    path.write_text(render_integrated_dashboard(result,show_provider_quality=show_provider_quality),encoding="utf-8")
    return path

def render_prospective_dashboard(report: dict) -> str:
    """Display *registration* evidence, not a historical leader ranking."""
    if report.get("certified_performance") is not False or report.get("official_leader_signals") != 0:
        raise ValueError("Uncertified registry must never present certified leaders")
    market=report.get("market")
    if market not in ("KR","US"):
        raise ValueError("Unknown market for prospective dashboard")
    lines=[]
    for row in report.get("first_registration_signals",[])[:200]:
        if row.get("pit_certified") is not False:
            raise ValueError("Official leader certification absent")
        values=[row.get("security_id"),row.get("first_seen"),
                row.get("recorded_at"),"예 — 소급 입력" if row.get("historical_backfill")
                else "아니오",row.get("signal_kind"),row.get("status")]
        lines.append("<tr>"+"".join(f"<td>{escape(str(v))}</td>" for v in values)+"</tr>")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader 실제 관찰 등록 시각</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 조기 발견 시점 기록</h1>
<nav><a href="index.html">처음으로</a><a href="research_{market.lower()}.html">통합 연구</a></nav>
</header><main><h2>{escape(market)} 시장 · 등록 이력</h2>
<div class="note"><strong>미검증 연구 기록 — 확정 대장주 0건</strong><br>
관측 기준일과 실제 기록일을 별도로 표시합니다. 과거 데이터를 오늘 다시 분석한 기록은
과거 당시 발견한 신호로 인정하지 않습니다. 시계와 원본 데이터의 독립 검증이 필요합니다.</div>
<div class="stats"><div class="stat">기록된 기업 수<br><strong>{report["distinct_companies"]}</strong></div>
<div class="stat">관측 이벤트 수<br><strong>{report["total_recorded_observations"]}</strong></div>
<div class="stat">공인 조기 발굴 성과<br><strong>N/A — 검증 보류</strong></div></div>
<h2>실제 등록된 최초 연구용 관찰 (최대 200개 표시)</h2>
<div class="wrap"><table><thead><tr><th>종목 ID</th><th>시세·재무 관측 기준일</th>
<th>실제 등록일</th><th>과거 데이터 재입력</th><th>신호 유형</th><th>검증 상태</th>
</tr></thead><tbody>{''.join(lines)}</tbody></table></div>
<p><small>로컬 시간·PIT 출처 미인증 / API 미연결 / 투자 추천 아님.</small></p>
</main></body></html>"""

def write_prospective_dashboard(report: dict, site_dir: Path) -> Path:
    content=render_prospective_dashboard(report)
    site_dir.mkdir(parents=True, exist_ok=True)
    path=site_dir/f"prospective_{report['market'].lower()}.html"
    path.write_text(content,encoding="utf-8")
    return path

def render_evidence_gate_dashboard(report: dict) -> str:
    """Read-only on-disk audit page; no data fetch, no simulated promotions."""
    allowed_status = {
        "LOCAL_AUDIT_DIAGNOSTICS_COMPLETE_NOT_PIT_CERTIFIED",
        "BLOCKED_MISSING_OR_UNRESOLVED_PIT_EVIDENCE",
    }
    market=report.get("market")
    if market not in ("KR","US") or report.get("status") not in allowed_status:
        raise ValueError("Invalid evidence gate market/status")
    if (report.get("official_promotion_allowed") is not False or
            report.get("historical_pit_certified") is not False or
            report.get("model_accuracy_certified") is not False or
            report.get("official_leader_count") != 0):
        raise ValueError("Uncertified evidence cannot render an official leader state")
    rows=report.get("evidence")
    if not isinstance(rows,list) or len(rows) != report.get("required_domains"):
        raise ValueError("Evidence inventory count mismatch")
    if (sum(1 for row in rows if row.get("present") is True)
            != report.get("present_domains")):
        raise ValueError("Evidence inventory present count mismatch")
    def safe(raw):
        return escape(str(raw),quote=True)
    body=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("issues"),list):
            raise ValueError("Malformed quality gate evidence")
        domain=safe(row.get("domain"))
        present="보고서 확인" if row.get("present") is True else "보고서 없음"
        issues=", ".join(safe(item) for item in row["issues"]) or "로컬 진단상 불일치 없음 (미인증)"
        body.append("<tr><td>"+domain+"</td><td>"+present+"</td><td>"+
                    issues+"</td></tr>")
    blocker_text="".join("<li>"+safe(code)+"</li>" for code in report.get("blockers",[])[:100])
    if not blocker_text:
        blocker_text="<li>로컬 감사상 차단 사유 0건 — 하지만 독립 PIT 인증은 아직 없음</li>"
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EraLeader PIT 감사 현황 · {safe(market)}</title><style>{BASE_CSS}</style></head>
<body><header><h1>EraLeader · PIT 근거 품질 점검</h1>
<div>시장 {safe(market)} · 감사 기준 {safe(report.get("market_day"))} · 로컬 연구용</div>
</header><main>
<div class="note"><strong>대장주 공식 확정: 차단됨</strong>
<p>거래소·공시 원천의 독립 PIT 인증과 실제 미래 발굴 성능이 확인되지 않았습니다.
파일이 모두 존재하거나 로컬 진단이 통과해도 투자 추천 또는 확정 후보가 아닙니다.</p></div>
<div class="stats">
<div class="stat">필수 감사 보고서<br><strong>{report["present_domains"]}/{report["required_domains"]}</strong></div>
<div class="stat">차단 사유<br><strong>{report["blocker_count"]}건</strong></div>
<div class="stat">공식 확정 대장주<br><strong>0건 · 인증 보류</strong></div>
</div>
<h2>영역별 자료 점검</h2><div class="wrap"><table>
<thead><tr><th>감사 영역</th><th>파일 상태</th><th>미확인 사항</th></tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<h2>미해결 증거 목록 (최대 100건)</h2><ul>{blocker_text}</ul>
<p><small>출력 상태: {safe(report["status"])} · 모든 인증 플래그 false · 외부 API 미연결</small></p>
</main></body></html>"""


def write_evidence_gate_dashboard(report: dict, site_dir: Path) -> Path:
    rendered=render_evidence_gate_dashboard(report)
    site_dir.mkdir(parents=True, exist_ok=True)
    target=site_dir/f"evidence_{report['market'].lower()}.html"
    target.write_text(rendered,encoding="utf-8")
    return target

def render_watch_progression_dashboard(report: dict) -> str:
    """Read-only research WATCH lifecycle, never a certified leader board."""
    if (report.get("status") != "LOCAL_WATCH_TRANSITIONS_RESEARCH_ONLY_NOT_CERTIFIED"
            or report.get("market") not in ("KR","US")
            or report.get("official_state_promotions") != 0
            or report.get("pit_certified") is not False
            or report.get("leader_prediction_accuracy_certified") is not False):
        raise ValueError("Uncertified WATCH progression cannot show leader promotions")
    totals=report.get("transition_counts")
    entries=report.get("transition_event_sample")
    if not isinstance(totals,dict) or not isinstance(entries,list):
        raise ValueError("Missing WATCH progression data")
    tags=("INITIAL_WATCH","WATCH_PERSISTED","SCREEN_WEAKENED",
          "SCREEN_STILL_WEAK","SCREEN_REENTERED","PRE_WATCH")
    if any(type(totals.get(tag)) is not int or totals[tag]<0 for tag in tags):
        raise ValueError("Invalid WATCH transition counts")
    if sum(totals[tag] for tag in tags)!=report.get("eligible_prospective_observations"):
        raise ValueError("WATCH transition total mismatch")
    def safe(value):
        return escape(str(value),quote=True)
    rows=[]
    for row in entries[:200]:
        if not isinstance(row,dict) or row.get("transition") not in tags:
            raise ValueError("Invalid WATCH transition entry")
        values=(row.get("security_id"),row.get("observed_at"),
                row.get("registered_at"),row["transition"],
                row.get("registration_lag_days"))
        rows.append("<tr>"+"".join(f"<td>{safe(v)}</td>" for v in values)+"</tr>")
    summary="".join(
        f'<div class="stat">{safe(tag)}<br><strong>{totals[tag]}</strong></div>'
        for tag in tags)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader 후보 변화 관찰 · {safe(report["market"])}</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 후보 WATCH 변화 기록</h1>
<nav><a href="index.html">처음으로</a></nav></header><main>
<div class="note"><strong>연구용 관찰 · 확정 대장주 0건</strong>
<p>명시적으로 분석한 신호의 최초 관찰, 지속, 약화, 재진입만 기록합니다.
관찰 목록에 종목이 없다는 이유만으로 약화로 판정하지 않습니다.
로컬 등록 시각과 데이터 원천은 독립 PIT 인증되지 않았으며 투자 추천이 아닙니다.</p></div>
<h2>시장 {safe(report["market"])} · 모델 {safe(report.get("model_version"))}</h2>
<div class="stats">{summary}</div>
<p>전향적 관측: {report["eligible_prospective_observations"]}건 ·
소급 입력 제외: {report["excluded_retrospective_observations"]}건</p>
<h2>관측 전이 샘플 (최대 200건)</h2>
<div class="wrap"><table><thead><tr>
<th>종목 식별자</th><th>관측일</th><th>실제 기록일</th><th>변화 유형</th><th>기록 지연일</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><small>검증 완료된 미래 대장주 성능: N/A · 공식 승격: 0 · 자동 매수/매도 없음.</small></p>
</main></body></html>"""


def write_watch_progression_dashboard(report: dict, site_dir: Path) -> Path:
    html=render_watch_progression_dashboard(report)
    site_dir.mkdir(parents=True,exist_ok=True)
    file=site_dir/f"watch_progression_{report['market'].lower()}.html"
    file.write_text(html,encoding="utf-8")
    return file


def render_watch_rotation_dashboard(report: dict) -> str:
    """Safe, explicit research-only rendering of peer WATCH rotation hypotheses."""
    if (report.get("status") != "RESEARCH_PEER_WATCH_ROTATION_NOT_CERTIFIED"
            or report.get("market") not in ("KR", "US")
            or report.get("official_leader_replacements") != 0
            or report.get("historic_pit_certified") is not False
            or report.get("industry_membership_pit_certified") is not False
            or report.get("peer_universe_coverage_certified") is not False
            or report.get("actual_prediction_accuracy_certified") is not False):
        raise ValueError("Uncertified research rotation must never show official promotions")
    n=report.get("rotation_hypothesis_count")
    sample=report.get("hypothesis_sample")
    if (type(n) is not int or n<0 or not isinstance(sample,list)
            or len(sample)>n or len(sample)>1000):
        raise ValueError("Research rotation sample/count mismatch")
    def safe(item):
        return escape(str(item),quote=True)
    body=[]
    for entry in sample[:200]:
        if (not isinstance(entry,dict) or
                entry.get("kind") != "RESEARCH_PEER_WATCH_REPLACEMENT_HYPOTHESIS"
                or entry.get("incumbent_is_certified_leader") is not False
                or entry.get("contender_is_certified_leader") is not False or
                entry.get("incumbent_security_id")==entry.get("contender_security_id")):
            raise ValueError("Invalid research rotation sample kind/leader certification")
        keys=(
            "industry_id","incumbent_security_id","contender_security_id",
            "first_explicit_weakening_at_utc","second_explicit_weakening_at_utc",
            "contender_first_watch_at_utc","contender_second_watch_at_utc",
        )
        if any(not isinstance(entry.get(k),str) or not entry[k] for k in keys):
            raise ValueError("Invalid incomplete research rotation sample")
        body.append("<tr>"+"".join(f"<td>{safe(entry[key])}</td>" for key in keys)+"</tr>")
    if not body:
        body=["<tr><td colspan='7'>현재 기준 명시적 교체 가설 없음 — 누락 자료를 약화로 추정하지 않음</td></tr>"]
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EraLeader WATCH 교체 후보 · {safe(report['market'])}</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 업종 WATCH 교체 후보 관찰</h1>
<nav><a href="index.html">처음으로</a></nav></header><main>
<div class="note"><strong>로컬 연구 가설 · 확정 대장주 0건</strong>
<p>기존 WATCH 종목의 명시적 연속 약화와 같은 산업의 신규 WATCH 연속 양성을
서로 비교한 연구입니다. 현재 공식 대장주 확정 또는 실제 투자 추천이 아닙니다.
완전한 종목군, 공식 업종분류, 데이터 원천 PIT 및 미래 성과라벨은 검증되지 않았습니다.
관찰 목록에서 기업이 빠졌다는 이유만으로 약화 또는 교체로 판단하지 않습니다.</p></div>
<h2>시장 {safe(report['market'])} · 모델 {safe(report.get('model_version'))}</h2>
<div class="stats">
<div class="stat">교체 연구 가설<br><strong>{n}건</strong></div>
<div class="stat">전향적 입력 관찰<br><strong>{safe(report.get('eligible_observation_count'))}건</strong></div>
<div class="stat">소급입력 제외<br><strong>{safe(report.get('excluded_hindsight_or_backfill_count'))}건</strong></div>
<div class="stat">공식 교체/확정<br><strong>0건 · 미인증</strong></div>
</div>
<p>평가 기준 (UTC): {safe(report.get('evaluated_at_utc'))}</p>
<h2>WATCH 교체 후보 샘플 (최대 200건, 확정 아님)</h2>
<div class="wrap"><table><thead><tr>
<th>자기선언 업종 ID</th><th>기존 WATCH ID</th><th>신규 WATCH ID</th>
<th>첫 명시적 약화(UTC)</th><th>두 번째 약화(UTC)</th>
<th>신규 첫 양성(UTC)</th><th>신규 두 번째 양성(UTC)</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p><small>공식 대장주 교체 0 · 미래 조기발굴 성과 N/A · 자동 거래/투자 추천 없음 ·
외부 인증된 PIT 자료 없이 확정 승격 불가.</small></p>
</main></body></html>"""


def write_watch_rotation_dashboard(report: dict, site_dir: Path) -> Path:
    html=render_watch_rotation_dashboard(report)
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/f"watch_rotation_{report['market'].lower()}.html"
    path.write_text(html,encoding="utf-8")
    return path


def render_peer_score_rotation_dashboard(report: dict) -> str:
    """Sanitized, locally evidenced peer-score hypotheses, never official leaders."""
    from datetime import date
    from math import isfinite
    from .peer_score_series import MIN_SCORE_ADVANTAGE

    if (report.get("status") != "LOCAL_PEER_SCORE_ADVANTAGE_HYPOTHESES_NOT_CERTIFIED"
            or report.get("market") not in ("KR", "US")
            or report.get("source_watch_rotation_status")
                != "RESEARCH_PEER_WATCH_ROTATION_NOT_CERTIFIED"
            or report.get("official_leader_replacements") != 0
            or report.get("issuer_industry_pit_certified") is not False
            or report.get("rank_scores_independently_authenticated") is not False
            or report.get("real_leader_replacement_certified") is not False):
        raise ValueError("Research peer score is not an official certified leader")
    needed=("rotation_hypothesis_count", "locally_two_session_score_correlated",
            "uncorroborated_rotation_hypotheses", "score_history_event_count",
            "score_history_events_available_by_cutoff")
    if any(type(report.get(key)) is not int or report[key]<0 for key in needed):
        raise ValueError("Invalid peer score hypothesis counts")
    total=report["rotation_hypothesis_count"]
    matched=report["locally_two_session_score_correlated"]
    other=report["uncorroborated_rotation_hypotheses"]
    if (matched+other != total or
            report["score_history_events_available_by_cutoff"] >
                report["score_history_event_count"] or
            type(report.get("minimum_score_difference_hypothesis")) not in
                (int,float) or
            report["minimum_score_difference_hypothesis"] != MIN_SCORE_ADVANTAGE):
        raise ValueError("Inconsistent peer score hypothesis count or threshold")
    sample=report.get("hypothesis_sample")
    if not isinstance(sample,list) or len(sample)>min(total,1000):
        raise ValueError("Invalid peer score evidence sample length")

    def safe(value):
        return escape(str(value),quote=True)

    rows=[]
    correlated_sample=0
    for entry in sample[:200]:
        if not isinstance(entry,dict):
            raise ValueError("Invalid peer score hypothesis sample")
        keys=("industry_id","incumbent_security_id","contender_security_id")
        if (any(not isinstance(entry.get(k),str) or not entry[k] for k in keys)
                or entry["incumbent_security_id"]==entry["contender_security_id"]):
            raise ValueError("Malformed peer score identity evidence")
        checks=entry.get("locally_score_correlated")
        issues=entry.get("issues")
        if type(checks) is not bool or not isinstance(issues,list) or len(issues)>100:
            raise ValueError("Invalid peer score corroboration/issue fields")
        if any(not isinstance(issue,str) or not issue for issue in issues):
            raise ValueError("Malformed peer score issue")
        count=entry.get("paired_market_day_count")
        days=entry.get("last_two_paired_market_days")
        diffs=entry.get("last_two_contender_minus_incumbent_scores")
        pairs=entry.get("last_two_paired_score_event_hashes")
        scores=entry.get("last_two_paired_scores")
        if (type(count) is not int or count<0 or
                not all(isinstance(v,list) for v in (days,diffs,pairs,scores)) or
                not (len(days)==len(diffs)==len(pairs)==len(scores)==min(count,2))):
            raise ValueError("Incomplete paired peer score evidence")
        try:
            parsed_days=[date.fromisoformat(day) for day in days]
        except (ValueError,TypeError) as exc:
            raise ValueError("Invalid paired peer score market dates") from exc
        if (any(type(day) is not str or len(day)!=10 for day in days) or
                parsed_days!=sorted(set(parsed_days))):
            raise ValueError("Unordered or duplicated peer score evidence dates")
        if any(type(diff) not in (int,float) or
               not isfinite(diff) or not -100<=diff<=100 for diff in diffs):
            raise ValueError("Invalid paired numeric score evidence")
        for day,diff,score_pair in zip(days,diffs,scores):
            if (not isinstance(score_pair,dict) or set(score_pair)!={
                    "market_day","incumbent_score","contender_score"} or
                    score_pair["market_day"]!=day or
                    any(type(score_pair[k]) not in (int,float) or
                        not isfinite(score_pair[k]) or not 0<=score_pair[k]<=100
                        for k in ("incumbent_score","contender_score")) or
                    round(score_pair["contender_score"]-score_pair["incumbent_score"],6)!=diff):
                raise ValueError("Original paired peer score witness mismatch")
        for item in pairs:
            if not isinstance(item,dict) or set(item)!={
                    "incumbent_event_sha256","contender_event_sha256"}:
                raise ValueError("Malformed peer score event SHA evidence")
            if any(not isinstance(item[field],str) or
                   not re.fullmatch("[0-9a-f]{64}",item[field])
                   for field in item):
                raise ValueError("Invalid peer score evidence SHA256")
        if checks:
            if (issues or len(days)<2 or
                    diffs[-1]<MIN_SCORE_ADVANTAGE or
                    diffs[-2]<MIN_SCORE_ADVANTAGE):
                raise ValueError("Research score evidence falsely claims corroboration")
            correlated_sample+=1
        elif not issues:
            raise ValueError("Missing reasons for uncorroborated peer-score hypothesis")

        label="2회 연속 점수 우위 충족 · 연구용" if checks else "점수 근거 미충족"
        recorded=" / ".join(
            f"{safe(day)} (기존 {scores[i]['incumbent_score']:.2f} → "
            f"신규 {scores[i]['contender_score']:.2f}, 차이 {diff:+.2f}점)"
            for i,(day,diff) in enumerate(zip(days,diffs))
        ) or "관찰일 미확인 · N/A"
        hashes=" / ".join(
            "<span title='"+safe(a["incumbent_event_sha256"])+"'>"
            +safe(a["incumbent_event_sha256"][:12])+"</span> ↔ "
            +"<span title='"+safe(a["contender_event_sha256"])+"'>"
            +safe(a["contender_event_sha256"][:12])+"</span>"
            for a in pairs
        ) or "N/A"
        reason=", ".join(safe(reason) for reason in issues) if issues else "로컬 점수 정합성 충족"
        cells=(entry["industry_id"],entry["incumbent_security_id"],
               entry["contender_security_id"])
        rows.append("<tr>"+"".join("<td>"+safe(value)+"</td>" for value in cells)
                    +"<td>"+safe(label)+"</td><td>"+recorded+"</td><td>"+hashes
                    +"</td><td>"+reason+"</td></tr>")
    if correlated_sample>matched or len(sample[:200])-correlated_sample>other:
        raise ValueError("Peer score evidence sample contradicts aggregate counts")

    if not rows:
        rows=["<tr><td colspan='7'>관측된 교체 가설 없음 — N/A, 미검증 데이터를 실패 신호로 대체하지 않음</td></tr>"]
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader 점수 기반 교체 후보 · {safe(report["market"])}</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 점수 기반 교체 후보</h1>
<nav><a href="index.html">처음으로</a></nav></header>
<main><div class="note"><strong>연구용 검증 · 확정 대장주 0건 · PIT 미인증</strong>
<p>동일 업종 기존 WATCH의 명시적 약화와 신규 WATCH의 연속 양성 관찰을
각 시장 현지 관찰일의 실제 로컬 저장 점수로 비교한 연구입니다.
두 점수 우위가 일치하더라도 공식 대장주 교체·투자 추천이 아닙니다.
거래소 법적 기업ID, 시점별 업종 분류, 실적 공시/기업행동 및 미래 결과는
독립 인증되지 않았습니다. 관찰 누락은 약화 판정으로 사용하지 않습니다.</p></div>
<h2>시장 {safe(report["market"])} · 모델 {safe(report.get("model_version"))}</h2>
<div class="stats">
<div class="stat">WATCH 교체 연구 가설<br><strong>{total}건</strong></div>
<div class="stat">2회 점수 우위의 로컬 근거<br><strong>{matched}건</strong></div>
<div class="stat">점수 근거 미충족<br><strong>{other}건</strong></div>
<div class="stat">공식 교체 0건<br><strong>미인증</strong></div></div>
<p>평가 기준 UTC: {safe(report.get("evaluated_at_utc"))} ·
점수 이력 전체 {report["score_history_event_count"]}건 ·
평가시점 이용 가능 {report["score_history_events_available_by_cutoff"]}건 ·
최근 두 비교일 점수차 가설 기준 {MIN_SCORE_ADVANTAGE:g}점 이상</p>
<h2>동종기업 연구 점수 근거 샘플 (최대 200건)</h2>
<div class="wrap"><table><thead><tr>
<th>자기선언 업종</th><th>기존 WATCH ID</th><th>신규 WATCH ID</th>
<th>연구 판정</th><th>최근 두 시장 관찰일 · 기존/신규 점수와 차이</th>
<th>원장 증거 SHA256 앞 12자리 (원문은 툴팁)</th><th>미해결 사유</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><small>최종 대장주 성과: N/A · 공식 확정/교체: 0 · 임계값은 연구 가설 ·
실제 외부 공시/PIT 증빙 및 전향 성숙 결과 라벨 필요 · 자동 매수/매도 없음.</small></p>
</main></body></html>"""


def write_peer_score_rotation_dashboard(report: dict, site_dir: Path) -> Path:
    html=render_peer_score_rotation_dashboard(report)
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/f"peer_score_rotation_{report['market'].lower()}.html"
    path.write_text(html,encoding="utf-8")
    return path


def render_ranked_maturity_dashboard(report: dict) -> str:
    """Render only a strictly censored maturity schedule, never an outcome."""
    from .ranked_maturity import STATUS
    if not isinstance(report,dict) or report.get("status")!=STATUS:
        raise ValueError("Invalid native ranked maturity research status")
    for key in ("official_leader_promotions",):
        if report.get(key)!=0 or type(report.get(key)) is not int:
            raise ValueError("False official leader promotion prohibited")
    for key in ("actual_future_leader_skill_certified",
                "source_document_outcome_corroborated","outcome_labels_read"):
        if report.get(key) is not False:
            raise ValueError("Unverified outcome/leader certification forbidden")
    for key in ("precision_at_k","recall_at_k",
                "known_positive_leaders","known_failures"):
        if report.get(key) is not None:
            raise ValueError("Unverified future leader performance must be N/A")
    if (report.get("local_native_provenance_rechecked") is not True or
        report.get("predeclared_rule_sha256_verified") is not True or
        report.get("market") not in ("KR","US") or
        type(report.get("selected_top_k_count")) is not int or
        report["selected_top_k_count"]<1):
        raise ValueError("Missing local native proof or maturity cohort identity")
    total=report["selected_top_k_count"]
    elapsed=report.get("full_horizon_elapsed_count")
    pending=report.get("full_horizon_pending_count")
    waiting=report.get("awaiting_mature_outcome_evidence_count")
    if (type(elapsed) is not int or type(pending) is not int or
        type(waiting) is not int or elapsed<0 or pending<0 or
        elapsed+pending!=total or waiting!=elapsed):
        raise ValueError("Ranked maturity pending/elapsed count inconsistent")
    if (report.get("retrospective_freeze") is True and
        report.get("prospective_maturity_eligible") is not False):
        raise ValueError("Retrospective rank cannot be presented as prospective")
    candidates=report.get("selected_candidate_sample")
    if (not isinstance(candidates,list) or len(candidates)>total or
        report.get("sample_truncated") is not (len(candidates)<total)):
        raise ValueError("Ranked maturity sample/count inconsistent")
    rows=[]
    statuses={
        "HORIZON_PENDING":"만기 전 · 결과 미확인",
        "HORIZON_ELAPSED_OUTCOME_UNKNOWN":"만기 경과 · 결과 원천 미확인",
        "RETROSPECTIVE_SEAL_NOT_A_PREDICTION":"소급 동결 · 전향적 예측 아님",
    }
    for item in candidates:
        if (not isinstance(item,dict) or item.get("status") not in statuses or
            item.get("leader_outcome_known") is not False or
            item.get("source_verified_future_leader_outcome") is not False or
            type(item.get("rank")) is not int or
            type(item.get("hours_until_horizon_end")) is not int or
            item["hours_until_horizon_end"]<0):
            raise ValueError("Invalid ranked maturity sample/outcome status")
        if (report.get("retrospective_freeze") is True and
            item["status"]!="RETROSPECTIVE_SEAL_NOT_A_PREDICTION"):
            raise ValueError("Retrospective rank sample claims prospective status")
        if (report.get("retrospective_freeze") is False and
            item["status"] != ("HORIZON_PENDING" if pending else
                               "HORIZON_ELAPSED_OUTCOME_UNKNOWN")):
            raise ValueError("Invalid rank sample maturity state")
        content=[
            item["rank"],item.get("security_id"),item.get("first_native_score"),
            item.get("native_score_first_written_utc"),
            item.get("horizon_end_utc"),
            statuses[item["status"]],
        ]
        rows.append("<tr>"+"".join(
            "<td>"+escape(str(value))+"</td>" for value in content
        )+"</tr>")
    es=lambda value:escape(str(value))
    future=es(report.get("next_horizon_end_utc") or "N/A · 모든 후보의 평가기간 경과")
    retrospective=("소급 동결된 자료이므로 전향적 예측 기록이 아닙니다."
                   if report.get("retrospective_freeze") is True else
                   "사전 동결된 로컬 연구 후보로, 실제 성과 인증은 아닙니다.")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EraLeader · Top-K 평가 만기 및 미확인 결과</title>
<style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 미래 대장주 후보 만기 추적</h1>
<nav><a href="index.html">처음으로</a></nav></header><main>
<h2>{es(report["market"])} · Top-K 사전 동결 · {es(report["market_as_of_day"])}</h2>
<div class="note"><strong>미검증 연구용 · 확정 대장주 0 · 실제 적중률 N/A</strong>
<p>{retrospective} 평가기간이 지났어도 양성/음성 결과를 추정하지 않습니다.
원본 결과 문서의 공개·수집시각과 독립 PIT 증빙이 필요합니다.</p></div>
<div class="stats">
<div class="stat">사전 고정 Top-K<br><strong>{total}</strong></div>
<div class="stat">기간 경과 전<br><strong>{pending}</strong></div>
<div class="stat">기간 경과 · 결과 미확인<br><strong>{waiting}</strong></div>
<div class="stat">확정 대장주 0 · 실전 적중률<br><strong>N/A</strong></div>
</div>
<h2>평가 기준과 다음 만기</h2>
<p>모델: {es(report["model_version"])} · 선동결 성공기준: {es(report["label_definition_id"])}
· 고정 기간: {es(report["predeclared_horizon_days"])}일</p>
<p>신호 스냅샷: {es(report["snapshot_at_utc"])} · 실제 동결:
{es(report["frozen_at_utc"])} · 다음 평가기간 종료: {future}</p>
<h2>사전등록 후보의 결과 대기 상태</h2>
<div class="wrap"><table><thead><tr>
<th>순위</th><th>연구 ID</th><th>첫 점수</th><th>점수 최초 저장 UTC</th>
<th>평가기간 만기 UTC</th><th>결과 상태</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p><small>표시 후보 {len(candidates)}/{total} · 점수 원장과 WATCH 근거는
로컬 해시 재검증만 수행했습니다. 외부 API/시장 전체 PIT/공신력 있는
결과 라벨 검증 전 실전 예측 성공·실패 또는 투자 권유가 아닙니다.</small></p>
</main></body></html>"""


def write_ranked_maturity_dashboard(report: dict, site_dir: Path) -> Path:
    """Write a derived research-only HTML after every safety check passed."""
    content=render_ranked_maturity_dashboard(report)
    site_dir=Path(site_dir)
    if site_dir.is_symlink():
        raise ValueError("Linked ranked maturity output site directory forbidden")
    site_dir.mkdir(parents=True,exist_ok=True)
    dest=site_dir/f"ranked_maturity_{report['market'].lower()}.html"
    if dest.is_symlink():
        raise ValueError("Linked ranked maturity page forbidden")
    dest.write_text(content,encoding="utf-8")
    return dest
