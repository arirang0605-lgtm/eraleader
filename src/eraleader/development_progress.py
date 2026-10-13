"""EraLeader acceptance-gate progress snapshot — NOT code-volume completion.

30 architecture work IDs x 4 *sequential* evidence gates, manually audited.
Updating a number requires new verified test/live evidence and a new checkpoint.
This indicator never promotes research WATCHs to certified future leaders.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from html import escape
import json

AS_OF = "2026-10-13"
SCHEMA = "eraleader.acceptance_readiness.v1"
GATES = (
    "구현과 테스트 증거",
    "실제 시장·공시·운영 데이터의 부분 E2E 증거",
    "해당 ID 전체 범위의 PIT·결측·종목군·통합 검증",
    "계속 운영·장애 복구·실전 인수 검증",
)
PHASES = (
    ("1", "데이터 수집"),
    ("2", "PIT 검증·저장"),
    ("3", "대장주 발굴 분석"),
    ("4", "대장주 상태·교체"),
    ("5", "백테스트·발굴 성능"),
    ("6", "대시보드·알림·운영"),
)
# (ID, accepted sequential gates, present evidence and the remaining blocker)
# 0 = code+test not independently accepted; 1 = code/mock; 2 = real partial.
# Levels 3 and 4 are prohibited before full source PIT and operations evidence.
TASKS = (
    ("1_1",2,"KRX 2026-10-08 실제 2,765행; 미국 전체 주가·상폐 이력 없음"),
    ("1_2",2,"DART 992 공시/삼성전자 FY3·SEC 1 CIK 연결; 전종목 재무 PIT 미인증"),
    ("1_3",0,"ECOS·KOSIS·FRED/ALFRED 공식 빈티지 연동·테스트 수락 증거 없음"),
    ("1_4",2,"DART 공시 실제 확보; NewsCatalystOS 별도 브랜치, 코어 통합 미완"),
    ("1_5",1,"수집·예약 코드/모의 테스트 존재; 매일 공식 증분 연속 운영 미인증"),
    ("2_1",2,"공식 원본 SHA/중복·필드 검증과 실제 수집·거절 시험 확인"),
    ("2_2",2,"현재 DART↔KRX 코드 일치 2,651/2,765; 역사 주권·상폐/행동 미검증"),
    ("2_3",2,"첫 로컬 수신·등록 as-of 차단 실원본 검증; 첫 공개 시각 미확정"),
    ("2_4",2,"SQLite/vintage 해시 저장·암호화 복구 실증; 전종목 영구 ID 미연결"),
    ("2_5",2,"실제 first-SHA+as-of 회귀, 관련 198 테스트; 전체 PIT 커버리지 불충분"),
    ("3_1",1,"산업 성장분석/정규화 연구 코드; ECOS/KOSIS 산업 데이터 통합 전"),
    ("3_2",1,"기업 특성·상대평가 연구 코드; 점유율·FCF·경쟁우위 실측 미연결"),
    ("3_3",2,"삼성전자 FY2023~25 CFS 연간 성장 가속 실제 계산; 1개 기업 한정"),
    ("3_4",2,"3·6개월 가격 강도 최대25점 실제 순위; 외국인·기관 수급 미연결"),
    ("3_5",1,"연구용 순위/가중치 가설 코드; 공식 total_score_100 모두 N/A"),
    ("4_1",2,"실제 한국 PRICE_ONLY WATCH20/첫수신 연구 이벤트; 정식 대장주0"),
    ("4_2",1,"잠재 후보 상태모형·검증용 코드; 실제 종합 후보 승격 없음"),
    ("4_3",1,"확정 판정 모형/검증코드; 실제 검증된 확정 대장주0"),
    ("4_4",1,"주도력 약화/리스크 상태 코드; 실제 다기간 정량 판정 미인증"),
    ("4_5",1,"교체 후보·추적 연구 코드; 실제 연속 교체 판정 검증 미완"),
    ("5_1",1,"PIT baseline 연구 코드/모의 테스트; 전시장 실물 인수 검증 부족"),
    ("5_2",1,"시점재생·기업행동 감사 코드; 역사 상폐/분할 실원본 불완전"),
    ("5_3",1,"Precision@K·최초등록 연구 평가 코드; 자연 만기 성과 없음"),
    ("5_4",1,"CAGR·MDD·리스크 비교 연구 코드; 검증된 전체시장 데이터 없음"),
    ("5_5",1,"walk-forward/holdout 코드·테스트; 독립 공인 PIT·전향 실물 검증 없음"),
    ("6_1",2,"실제 PRICE WATCH20/SQLite·SHA 결과; 공식 종합 순위 DB 미완"),
    ("6_2",2,"KR 가격·실적·DART 빈티지 HTML 실제 HTTP200; 최종 대장주 UI 미완"),
    ("6_3",2,"실제 WATCH DRY-RUN 알림 20개; 실발송·재시도/운영 검증 미완"),
    ("6_4",2,"실제 일·주·월 연구 보고서3개; 장기 자동 보고·성과 추적 미인증"),
    ("6_5",2,"Mac·SSD AES-GCM 암호화 독립 복원 성공; 오프라인 외부키/20일 운영 미완"),
)


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def acceptance_progress() -> dict:
    ids=[f"{stage}_{index}" for stage in range(1,7) for index in range(1,6)]
    if ([name for name,_,_ in TASKS]!=ids or
            len({name for name,_,_ in TASKS})!=30 or
            any(type(level) is not int or not 0<=level<=4 or not isinstance(detail,str)
                or not detail for _,level,detail in TASKS)):
        raise ValueError("All thirty acceptance work IDs need explicit evidence")
    phases=[]
    for prefix,title in PHASES:
        rows=[{"work_id":key,"accepted_gates":level,
               "max_gates":4,"remaining_gates":4-level,"evidence":detail}
              for key,level,detail in TASKS if key.startswith(prefix+"_")]
        earned=sum(row["accepted_gates"] for row in rows)
        phases.append({"stage":prefix,"name":title,"earned":earned,"possible":20,
                       "percent":round(100*earned/20,1),"tasks":rows})
    total=sum(p["earned"] for p in phases)
    result={
        "schema":SCHEMA, "snapshot_date":AS_OF,
        "source_branch":"feature/core-official-factor-coverage-20261013",
        "type":"HUMAN_REVIEWED_ACCEPTANCE_GATE_ESTIMATE_NOT_PRODUCTION_CERTIFICATION",
        "earned":total,"possible":120,
        "exact_percent":round(100*total/120,1),
        "display_percent":round(100*total/120),
        "method":"30개 개발ID 각각 4개 순차 인수 관문을 동일가중(각1점) 판정",
        "gates":list(GATES), "stages":phases,
        "official_composite_leader_ranking_ready":False,
        "future_leader_accuracy_certified":False,
        "real_continuous_20_session_operation_verified":False,
        "source_notes":[
            "실제 KRX 단일 거래일(2026-10-08) 가격 관측 2,765행/DART 공시 992건",
            "DART 현재 식별 교집합 2,651개, 영구 issuer/share-class·상폐 이력 미인증",
            "삼성전자 2023~25 연결 재무 연속3년 연구/첫 등록·정정 SHA 추적",
            "연관 15개 테스트 모듈 198 PASS; core feature branch와 main 통합 미완",
            "Mac+T5DATA AES-GCM 증분 복원 PASS, 외부 오프라인 키 수탁 미완",
            "초기 뉴스 기능은 별도 Git 브랜치에 있고 운영 core/main 병합 미완",
            "미래 TopK/PIT 전수·20거래일 전향 운영 성능은 아직 검증되지 않음",
        ],
        "limitations":[
            "실제 개발 소요시간·실물 투자 성과/정식 서비스 완성도를 측정한 값이 아님",
            "코드 파일 수/단위테스트 수만으로 3·4관문을 통과시킬 수 없음",
            "단일 종목/단일 거래일 실증은 전체 시장의 PIT 커버리지를 대체하지 않음",
            "기존 99%/95%는 전체 실사용 완료율에서 철회",
        ],
    }
    result["evidence_sha256"]=sha256(_canonical(result)).hexdigest()
    return result


def _checked(report: dict) -> dict:
    original=dict(report)
    witnessed=original.pop("evidence_sha256",None)
    if original.get("schema")!=SCHEMA or witnessed!=sha256(_canonical(original)).hexdigest():
        raise ValueError("Acceptance progress snapshot changed after SHA witness")
    stages=original.get("stages",[])
    if (len(stages)!=6 or sum(p["earned"] for p in stages)!=original["earned"]
            or original["possible"]!=120 or
            any(p["earned"]<0 or p["earned"]>p["possible"] for p in stages)
            or original.get("official_composite_leader_ranking_ready") is not False):
        raise ValueError("Cannot misrepresent research as completed official leader model")
    return original


def render_markdown(report: dict) -> str:
    d=_checked(report)
    lines=[
        "# EraLeader 전체 개발 진행률 — "+d["snapshot_date"],
        "",
        f"**현재 실사용 인수 진척률: {d['exact_percent']}% (표시 {d['display_percent']}%; {d['earned']}/{d['possible']}점).**",
        "",
        "> 코드량이 아닌 30개 ID×4개 순차 인수 관문 평가. 수동 근거 심사에 따른 보수적 추정이며 발굴 정확도·개발 일정의 실측치가 아닙니다.",
        "",
        "## 산정 방법",
    ]
    lines += [f"{i}. **{gate}** — 1점" for i,gate in enumerate(d["gates"],1)]
    lines += ["", "| 단계 | 인수점수 | 가중 진행률 |",
              "|---|---:|---:|"]
    for p in d["stages"]:
        lines.append(f"| {p['stage']}단계 {p['name']} | {p['earned']}/{p['possible']} | {p['percent']}% |")
    lines += [f"| **전체** | **{d['earned']}/{d['possible']}** | **{d['exact_percent']}%** |",
              "",
              "## 30개 개발 ID별 실제 증거 및 미완료 범위",
              "",
              "| ID | 통과 관문 | 실제 증거/차단 사유 |",
              "|---|---:|---|"]
    for stage in d["stages"]:
        for row in stage["tasks"]:
            lines.append(f"| {row['work_id']} | {row['accepted_gates']}/4 | {row['evidence']} |")
    lines += ["","## 수치 해석 및 미완료",""]
    lines += ["- "+item for item in d["limitations"]]
    lines += ["","## 최신 핵심 증거",""]
    lines += ["- "+item for item in d["source_notes"]]
    lines += ["","## 운영 인수 판정",
              "- 종합 미래 대장주 100점 공식 순위: **미완료**.",
              "- 20거래일 연속 자동 실행/장애 복구: **미검증**.",
              "- 장기 전향 precision@K·조기 발견 기간: **미검증**.",
              "- 전체 PIT 종목군/공시 수정/기업행동/미국 가격: **미완료**.",
              "- 본 진척률은 추후 같은 고정 분모(120점)를 유지하고 실제 통과 증거로만 수정합니다.",
              "",
              "근거 스냅샷 SHA256: `"+report["evidence_sha256"]+"`",
              ""]
    return "\n".join(lines)


def render_html(report: dict) -> str:
    d=_checked(report)
    def safe(text):
        return escape(str(text),quote=True)
    phase_rows="".join(
        "<tr><td>"+safe(p["stage"]+"단계 · "+p["name"])+"</td><td>"+
        safe(p["earned"])+"/20</td><td>"+safe(f'{p["percent"]:.0f}%')+"</td></tr>"
        for p in d["stages"])
    details="".join("<tr><td>"+safe(row["work_id"])+"</td><td>"+
                    safe(str(row["accepted_gates"])+"/4")+"</td><td>"+
                    safe(row["evidence"])+"</td></tr>"
                    for p in d["stages"] for row in p["tasks"])
    gates="".join("<li>"+safe(item)+"</li>" for item in d["gates"])
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EraLeader 전체 개발 진행률</title>"
        "<style>body{font:15px/1.65 -apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;"
        "background:#f8f9fb;color:#1b2230;margin:0}header{background:#192b42;color:white;padding:25px 8%}"
        "header a{color:#d0eaff}main{max-width:1100px;margin:24px auto;padding:0 18px 50px}"
        "h1{font-size:26px;margin:0 0 4px}h2{font-size:20px;margin-top:25px}"
        ".pct{font-size:42px;font-weight:750;margin:7px 0}.bar{height:11px;background:#ddd;border-radius:6px}"
        ".bar>div{height:100%;background:#586777;border-radius:6px}"
        "table{width:100%;border-collapse:collapse;background:white;font-size:13px}"
        "td,th{text-align:left;padding:10px 9px;border-bottom:1px solid #e1e4e9}"
        "th{background:#ecf0f4}.scroll{overflow:auto}.warn{border-left:4px solid #888;"
        "padding:10px 15px;background:#fff;margin:16px 0}"
        "footer{padding:24px 8%;font-size:12px;color:#666}</style></head><body>"
        "<header><h1>EraLeader · 전체 개발 진행 현황</h1><div>기준일 "+safe(d["snapshot_date"])+
        " · 증거 기반 인수 판정</div><p><a href='index.html'>대시보드 메인</a> · "
        "<a href='kr.html'>KR 가격 관찰</a> · "
        "<a href='factor_readiness_kr.html'>실제 데이터 충족도</a></p></header>"
        "<main><p class='pct'>"+safe(str(d["display_percent"]))+"%</p>"
        "<div class='bar' role='img' aria-label='개발 인수 진척률 "+safe(str(d["exact_percent"]))+
        " 퍼센트'><div style='width:"+safe(str(d["exact_percent"]))+"%'></div></div>"
        "<div class='warn'><b>실사용 인수 진척 추정: "+safe(str(d["exact_percent"]))+
        "% · "+safe(str(d["earned"]))+"/120점</b><br>"
        "이 값은 코드 작성량이 아닙니다. 실제 대장주 투자순위·미래 발굴 정확도·20거래일 연속 운영은 아직 검증되지 않았습니다."
        " 종전 99% 전체 개발률은 철회했습니다.</div>"
        "<h2>1~6단계 통합 진행률</h2><div class='scroll'><table><thead><tr>"
        "<th>구분</th><th>통과 관문</th><th>가중 진행률</th></tr></thead><tbody>"+
        phase_rows+"</tbody></table></div>"
        "<h2>산정 기준</h2><p>30개 개발 ID마다 다음 네 관문을 순서대로 적용합니다. 각 관문은 1점,"
        " 전체 120점 만점입니다. 데이터/PIT 범위가 불완전한 모듈은 테스트가 많아도 전 범위 통과로 인정하지 않습니다.</p>"
        "<ol>"+gates+"</ol>"
        "<h2>30개 세부 작업의 증거와 차단 조건</h2><div class='scroll'><table><thead><tr>"
        "<th>작업ID</th><th>인수관문</th><th>현재 관측 증거·미완료 사유</th>"
        "</tr></thead><tbody>"+details+"</tbody></table></div>"
        "<p><small>수동 근거 심사로 작성된 보수적 추정치입니다. 투자 추천이나 실전 성능 검증이 아닙니다."
        " 스냅샷 SHA256 "+safe(report["evidence_sha256"][:16])+"…</small></p>"
        "</main><footer>EraLeader local-first · 공식 투자우선순위 N/A · 전향적 성능 N/A</footer>"
        "</body></html>"
    )
