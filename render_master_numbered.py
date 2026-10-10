#!/usr/bin/env python3
"""EraLeader 1~6 numbered development master. Creates editable SVG.
One overall image, stable step IDs 1_1..6_5.
Only uses Python stdlib. PNG is rendered by Chrome separately.
"""
from pathlib import Path
from html import escape
ROOT=Path("/Volumes/T5DATA/eraleader")
W,H=3240,2600
LANES=[
 dict(num=1,title="데이터 수집",desc="한국·미국 시세·공시·산업 변화",out="산출: 원본 시세·재무·이벤트",
      color="#176BB0",pale="#E6F3FF",
      steps=[
       ("1_1","한국·미국 주가","KRX 일봉·미국 시세 API","상장·상폐·기업행동","실시간·분봉은 별도 검토"),
       ("1_2","기업 재무·공시","OpenDART · SEC EDGAR","분기·연간 보고/현금흐름","공시 접수시각 보존"),
       ("1_3","거시·산업 통계","ECOS · KOSIS · FRED","ALFRED 과거 빈티지","산업 성장·투자 통계"),
       ("1_4","공시·뉴스·기타","계약·수주·정책·GDELT","컨센서스는 필요시 유료","출처·발표일 기록"),
       ("1_5","자동 증분 수집","API 어댑터·호출 제한","원본 캐시·재시도","원자료 변경 없이 보관")]),
 dict(num=2,title="PIT 검증·저장",desc="과거 당시 알 수 있었던 정보 복원",out="산출: PIT DB·품질보고서",
      color="#0C867E",pale="#E1F7F2",
      steps=[
       ("2_1","원본 품질검사","중복·결측·이상치 탐지","가격·재무 단위 정합성","오류/누락 명시"),
       ("2_2","종목·기업행동","상장·상폐·티커 변경","분할·배당·거래정지","당시 시장 구성 재현"),
       ("2_3","PIT 시점 필터","공시일 ≠ 사업기간 종료일","available_at ≤ 판단 시각","미래정보 유입 차단"),
       ("2_4","표준화·저장","공통 종목ID·통화·시간","DuckDB / Parquet","수정·정정 버전 보존"),
       ("2_5","품질 회귀검증","후행 공시 추가해도 과거 불변","스냅샷/실행 해시","결측 시 평가 보류")]),
 dict(num=3,title="발굴 분석 엔진",desc="산업·기업·주가 정량 평가",out="산출: 산업 TOP·기업 점수",
      color="#5D54BE",pale="#ECEAFE",
      steps=[
       ("3_1","산업 성장성","산업 매출·투자·CAPEX","업종 RS·산업 확산","초기 가중치 20점"),
       ("3_2","기업 경쟁력","시장점유율·수익성","마진·FCF·성장 지속성","초기 가중치 20점"),
       ("3_3","실적 모멘텀","매출/영업이익 성장 가속","EPS 예상 상향(자료 있을 때)","초기 가중치 25점"),
       ("3_4","주가 RS·수급","6·12개월 상대강도·주봉","신고가·기관 수급(가용 시)","초기 가중치 25+10점"),
       ("3_5","종합 점수·근거","업종 내 퍼센타일 평가","실적·추세·위험 분해","기준값은 백테스트로 검증")]),
 dict(num=4,title="대장주 판정",desc="잠재 → 확정 → 약화·교체 추적",out="산출: 후보 순위·상태 이벤트",
      color="#C46C24",pale="#FFF0E0",
      steps=[
       ("4_1","관찰 종목군","전체 산업·기업 후보 추적","기본 점수·최초 발견일","상태: WATCH"),
       ("4_2","잠재 대장주","성장 가속·RS 조기 신호","잠재 후보 TOP 20","65~79점은 초기 가설"),
       ("4_3","확정 대장주","실적 + 추세 복수 조건","확정 후보 TOP 10","80점 이상도 검증 필요"),
       ("4_4","주도력 약화","실적 둔화·RS·주봉 훼손","상태 변경·위험 사유","미확정봉은 경고만"),
       ("4_5","교체 후보·이력","업종 내 후발주와 비교","연속 확인·중복 이벤트 방지","상태 전이 로그 보존")]),
 dict(num=5,title="단계별 백테스트",desc="조기 발굴 능력과 위험 별도 평가",out="산출: 평가보고서·모델 검증",
      color="#8A50A6",pale="#F3EAFB",
      steps=[
       ("5_1","초기 검증 기반","PIT 직후 최소 baseline 구축","산업·실적·RS 개별 평가","백테스트를 뒤로 미루지 않음"),
       ("5_2","과거 시점 재현","당시 종목군·공시만 사용","다음 거래가능 시점 체결","상폐·분할·비용 반영"),
       ("5_3","발굴 능력 검증","precision@K · recall@K","최초 발견 리드타임","허위 후보율·실패 이력"),
       ("5_4","수익·위험 평가","시장·업종대비 초과수익","CAGR · MDD · 회전율","수수료·슬리피지 차감"),
       ("5_5","최종 강건성","Walk-forward 반복 검증","미사용 Holdout 분리","과최적화/미래 누수 방지")]),
 dict(num=6,title="사용자 결과 제공",desc="웹·알림·보고서 3종 모두 제공",out="산출: 휴대폰·PC 결과 조회",
      color="#168369",pale="#E2F7EC",
      steps=[
       ("6_1","공통 결과 DB/API","확정 랭킹·이벤트 스냅샷","모델 버전·데이터 기준시각","선택적 외부 읽기 API"),
       ("6_2","웹 대시보드","한국·미국 대장주/잠재 순위","종목 상세·성과·근거","휴대폰·PC 반응형"),
       ("6_3","상태변경 자동 알림","신규·확정·약화·교체","텔레그램/메일 등 설정","중복·재전송 방지"),
       ("6_4","정기 분석 보고서","일간/주간/월간 자동 생성","실제 선정 이후 성과 비교","웹·PDF·이메일 옵션"),
       ("6_5","독립 운영·연동","배치 스케줄·로그·백업","GitHub/PROJECT_STATE 보존","MarketOS는 선택적 연동")])
]
allids=[s[0] for l in LANES for s in l['steps']]
assert len(allids)==30 and len(set(allids))==30
a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
a.append("""<defs>
<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#FAFCFF"/><stop offset="1" stop-color="#EFF4FA"/></linearGradient>
<linearGradient id="head" x1="0" x2="1"><stop stop-color="#082C53"/><stop offset="1" stop-color="#1B5489"/></linearGradient>
</defs>""")
def rect(x,y,w,h,col,rx=12,stroke="none",sw=1):
 a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{col}" stroke="{stroke}" stroke-width="{sw}"/>')
def txt(x,y,s,size=27,color="#153251",weight=500,anchor="start"):
 a.append(f'<text x="{x}" y="{y}" font-family="Apple SD Gothic Neo,Noto Sans CJK KR,sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(s))}</text>')
rect(0,0,W,H,"url(#bg)",0)
rect(0,0,W,196,"url(#head)",0)
txt(60,87,"EraLeader",90,"white",820)
txt(568,84,"시대의 대장주 검색기  |  1~6단계 전체 설계도",54,"#F5FAFF",760)
txt(65,150,"각 단계 세부 작업의 고유 번호를 1_1 → 6_5로 통일 · 자료 수집부터 PIT 검증, 발굴, 백테스트, 결과 제공까지",30,"#D2E8FF",530)
rect(2768,49,405,69,"#286595",17,"#8ABEEB",1.4)
txt(2970,95,"독립 프로젝트 · 필요 시 연동",24,"white",740,"middle")
txt(3175,171,"개발 설계 / 2026-10-10",23,"#E0EFFF",500,"end")

starty=225;pitch=351;h=318
leftx=44;leftw=366
cardx=430;gap=14;cw=543
for n,l in enumerate(LANES):
 y=starty+n*pitch
 rect(43,y,3154,h,"#FFFFFF",23,"#C9D8E9",2.2)
 rect(leftx,y,leftw,h,l["pale"],19)
 rect(leftx+21,y+23,79,78,l["color"],20)
 txt(leftx+60,y+78,str(l["num"]),48,"white",820,"middle")
 txt(leftx+24,y+141,l["title"],40,"#123754",780)
 txt(leftx+24,y+190,l["desc"],24,"#405C78",540)
 rect(leftx+22,y+229,leftw-44,60,"#FFFFFF",11,"#C9DEEB",1)
 txt(leftx+35,y+267,l["out"],22,l["color"],720)
 for j,(key,title,v1,v2,v3) in enumerate(l["steps"]):
  x=cardx+j*(cw+gap)
  rect(x,y+17,cw,h-35,"#F8FAFD",17,"#D9E4F0",1.2)
  rect(x,y+17,cw,77,l["pale"],15)
  rect(x+14,y+30,102,52,l["color"],13)
  txt(x+65,y+67,key,31,"white",830,"middle")
  txt(x+132,y+68,title,30,"#173A58",790)
  for k,v in enumerate([v1,v2,v3]):
   yy=y+141+k*46
   rect(x+26,yy-18,7,18,l["color"],4)
   txt(x+49,yy,v,25,"#324F6A",550)
  if j<4:
   txt(x+cw+gap/2,y+178,"›",40,"#5091C6",800,"middle")
 if n<5:
  txt(226,y+h+30,"▼",28,l["color"],760,"middle")

rect(43,2360,3154,185,"#E5EFFA",19,"#C5D8EC",1.5)
txt(73,2414,"개발·검증의 고정 원칙",37,"#173D60",820)
txt(74,2464,"미래정보 사용 금지(PIT) · 상장폐지 포함 · 점수/임계값은 검증 전 가설 · 백테스트는 초기에 기반 구축 후 매 단계 반복",27,"#375872",630)
txt(74,2514,"Python 자동 실행으로 토큰 절약 · GitHub 상태 보존 · 화면/알림/보고는 동일 결과 DB 사용 · MarketOS와 분리 운영",27,"#375872",600)
txt(53,2586,"현재 상태: 개발 명세·설계도 문서화  |  실제 API 연결·정량 전략의 투자성과·실서비스는 아직 구현 및 검증 전",22,"#516A85",540)
txt(W-53,2586,"EraLeader / Master Blueprint v2",21,"#516A85",540,"end")
a.append("</svg>")
p=ROOT/"EraLeader_전체설계도_1-6단계_세부번호.svg"
p.write_text("\n".join(a),encoding="utf-8")
print("SVG",p,p.stat().st_size)
print("IDs"," ".join(allids))
