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
</main><footer>EraLeader local-first · API 미연결 · 매매/자동 주문 기능 없음</footer></body></html>"""

def write_dashboard(snapshot: dict, site_dir: Path) -> Path:
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/("kr.html" if snapshot["source_market"]=="KR" else "us.html")
    path.write_text(render_dashboard(snapshot),encoding="utf-8")
    index=site_dir/"index.html"
    index.write_text("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                     "<title>EraLeader</title><meta name='viewport' content='width=device-width, initial-scale=1'>"
                     "<body style='font:18px sans-serif;padding:36px'>"
                     "<h1>EraLeader 로컬 화면</h1><p>API 연결 전 연구용 가격 관찰 화면입니다.</p>"
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


def render_integrated_dashboard(result: dict) -> str:
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
            ",".join(item["missing_factors"])))+"</tr>")
    trusted="검증 완료" if result.get("pit_certified") else "미검증 / 관찰·연구용"
    quality=esc(", ".join(result.get("quality",{}).get("provenances",[])) or "원천 미상")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EraLeader 시점별 통합 분석</title><style>{BASE_CSS}</style></head><body>
<header><h1>EraLeader · 산업·실적·가격 통합 연구</h1>
<a href="index.html" style="color:white">처음으로</a></header><main>
<h2>기준시각: {esc(result["as_of"])} · {esc(result["market"])}</h2>
<div class="note"><strong>연구용: {trusted}</strong><br>
합성 자료 또는 불완전한 과거 원본이면 대장주 승격 금지.
과거 상장종목군/기업행동/원시 공시의 PIT 완전성이 확인되지 않았습니다.
<br>데이터 출처 상태: {quality}</div>
<div class="stats"><div class="stat">기업 수<br><strong>{result["company_count"]}</strong></div>
<div class="stat">초기 성장 관찰 (연구)<br><strong>{result["research_growth_screen_count"]}</strong></div>
<div class="stat">확정 대장주<br><strong>0 — 검증 보류</strong></div></div>
<h2>시점별 기업 성장 관찰</h2>
<div class="wrap"><table><thead><tr><th>ID</th><th>티커</th><th>산업</th>
<th>매출 YoY</th><th>영업이익 YoY</th><th>매출성장 가속</th>
<th>산업 YoY</th><th>가격 6개월</th><th>상태</th><th>누락·보류</th>
</tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p><small>완전한 과거 시점 데이터·미래 발굴 성능 인증 전 투자 추천 아님.</small></p>
</main></body></html>"""

def write_integrated_dashboard(result: dict, site_dir: Path) -> Path:
    site_dir.mkdir(parents=True,exist_ok=True)
    path=site_dir/f"research_{result['market'].lower()}.html"
    path.write_text(render_integrated_dashboard(result),encoding="utf-8")
    return path
