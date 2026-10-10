#!/usr/bin/env python3
"""Create the EraLeader data sourcing architecture as a standalone SVG (editable)."""
from pathlib import Path
from html import escape
from datetime import date

outdir = Path("/Volumes/T5DATA/eraleader")
W,H=2400,1510
svg=[]
def append(s): svg.append(s)
def box(x,y,w,h,color,rad=18,border="#D8E3F0",bw=1.5):
    append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rad}" fill="{color}" stroke="{border}" stroke-width="{bw}"/>')
def text(x,y,s,size=24,color="#18314B",weight=500,anchor="start"):
    append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Apple SD Gothic Neo, Noto Sans CJK KR, sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')
def arrow(x,y,s=44):
    text(x,y,"➜",s,"#4386C0",750,"middle")
def caption(x,y,s):
    text(x,y,s,20,"#63758B",550)

append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
append('''<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#FAFCFF"/><stop offset="1" stop-color="#EDF3FA"/></linearGradient><linearGradient id="banner"><stop stop-color="#072D58"/><stop offset="1" stop-color="#20578E"/></linearGradient></defs>''')
box(0,0,W,H,"url(#bg)",0,"none",0)
box(0,0,W,160,"url(#banner)",0,"none",0)
text(55,76,"EraLeader",70,"white",800)
text(423,72,"데이터 수집 · 검증 · 활용 구조",46,"#F0F6FF",800)
text(58,124,"공식 데이터 우선  ·  과거 시점(PIT) 재현  ·  Python 자동 처리  ·  비용은 검증 후 확장",25,"#C8E4FF",550)
box(1990,43,355,67,"#2B699B",14,"#75B5EB",1)
text(2167,85,"독립형 데이터 파이프라인",24,"white",750,"middle")
text(2340,139,"설계 명세 / 2026-10-10",19,"#D5E8FB",550,"end")

columns = [
    ("1","주가 · 거래량","주가·거래량 원자료에서 추세 계산","#DCEFFF","#1B68B3",
      [("한국 시세","KRX: 코스피·코스닥 일봉"),
       ("미국 시세","공급자 API: 일봉·기업행동"),
       ("실시간·분봉","별도 API/계약 필요할 수 있음"),
       ("Python 계산","주봉·월봉·RS·RSI·이평"),
       ("필수 과거이력","상장·상폐·분할·배당")],
      "한국·미국 장마감 후 수집"),
    ("2","기업 재무 · 실적","기업 실제 이익과 성장 가속도","#DDF7EA","#108665",
      [("한국 재무","OpenDART: 매출·이익·현금"),
       ("미국 재무","SEC EDGAR: 공시·XBRL"),
       ("이익 지표","성장률·영업이익률·CAPEX"),
       ("과거 EPS 전망","스냅샷 이력 별도/주로 유료"),
       ("PIT 핵심","사업연도 아닌 발표 시각")],
      "분기·연간 공시 시점에 갱신"),
    ("3","산업 · 거시","산업 구조 변화와 유동성 확인","#E9E6FF","#5C53B2",
      [("한국 경제","ECOS·KOSIS: 금리·산업통계"),
       ("미국 경제","FRED: 금리·물가·고용"),
       ("과거 빈티지","ALFRED: 과거 공개 수치"),
       ("산업 지표","매출·CAPEX·산업 RS 계산"),
       ("PIT 핵심","발표·수정일을 별도 저장")],
      "지표 공표 시점별 증분 수집"),
    ("4","공시 · 뉴스 · 이벤트","새로운 수요·수주·공급망 탐지","#FFEDDE","#C97325",
      [("기업 공시","DART·SEC: 계약·증설·수주"),
       ("산업 정책","정부 공식 발표 우선"),
       ("글로벌 뉴스","GDELT 등 약관 허용 데이터"),
       ("기업 이력","상장폐지·상호·티커 변경"),
       ("선택적 자료","점유율·공급망·대체 데이터")],
      "원문·출처·발표 시각 보존")
]
cx=40; gap=23; cw=(W-80-3*gap)/4
for i,(n,title,subtitle,bg,accent,items,frequency) in enumerate(columns):
    x=cx+i*(cw+gap)
    box(x,190,cw,542,"#FFFFFF",23,"#C8D7E9",2)
    box(x,190,cw,124,bg,23,"none",0)
    box(x,291,cw,23,bg,0,"none",0)
    box(x+22,215,53,53,accent,15,"none",0)
    text(x+48,252,n,31,"#FFFFFF",850,"middle")
    text(x+89,253,title,32,"#123252",850)
    text(x+26,299,subtitle,20,"#486783",500)
    for k,(name,desc) in enumerate(items):
        y=332+73*k
        box(x+18,y,cw-36,62,"#F7F9FD",11,"#DDE6F1",1)
        box(x+29,y+15,6,32,accent,2,"none",0)
        text(x+46,y+24,name,20,accent,750)
        text(x+46,y+49,desc,20,"#294258",550)
    box(x+18,705,cw-36,12,bg,6,"none",0)
    text(x+cw/2,691,frequency,18,accent,700,"middle")

box(40,757,2320,312,"#FFFFFF",20,"#C8D6E8",2)
text(72,815,"공통 자동 수집·처리 파이프라인",35,"#173A61",850)
text(2342,808,"Python 배치 · 원본 캐시 · 중복 방지 · 자동 테스트",22,"#5A718C",600,"end")
steps=[
  ("1. API 수집","공식/계약된 공급자","호출 제한·재시도"),
  ("2. 원본 보관","원 응답 불변 저장","수신 시각·이력"),
  ("3. 표준화","종목ID·통화·단위","시점/기업행동"),
  ("4. 데이터 검증","중복·결측·이상치","품질 실패 표시"),
  ("5. PIT 저장","당시 이용 가능 자료","정정·상폐 반영"),
  ("6. 발굴 분석","산업·실적·RS 점수","잠재/확정 판정"),
  ("7. 결과 제공","웹·알림·보고서","백테스트·이력")]
sx=66; gap=26; sw=(2270-6*gap)/7
for i,(name,a,b) in enumerate(steps):
    x=sx+i*(sw+gap)
    color=["#E0F0FF","#DDF8F1","#EBECFF","#FFF1E0","#E4F5FF","#F0E9FF","#DFF5E7"][i]
    box(x,855,sw,162,color,14,"#D2DFED",1.5)
    text(x+sw/2,898,name,23,"#163A5E",800,"middle")
    text(x+sw/2,948,a,20,"#314E68",600,"middle")
    text(x+sw/2,985,b,20,"#314E68",600,"middle")
    if i<6:
        arrow(x+sw+gap/2,944,27)
text(72,1053,"검증 조건: 미래 데이터 유입 방지 · 당시 종목군 재현 · 결과 버전 관리 · 장애 후 재실행 가능",22,"#4C6884",580)

box(40,1093,2320,274,"#FFFFFF",20,"#C7D9EB",2)
text(74,1147,"데이터 확보 및 개발 순서",34,"#123858",850)
phases=[
    ("1차 · 필수 기초","KR·US 일봉 + DART·SEC 재무","종목·상폐·기업행동/PIT 필수 확보","#DBEFFD","#1B6EAC"),
    ("2차 · 산업 조기 탐색","ECOS·KOSIS·FRED·ALFRED","산업 성장·거시·공시 이벤트 강화","#E0F8E9","#187A61"),
    ("3차 · 성능 입증 후","과거 EPS 추정치 · 시장점유율","추가 성능을 확인한 뒤 유료 도입","#FFF0DC","#AA641D")]
px=72; pgap=28; pw=(2254-2*pgap)/3
for i,(h,line1,line2,fill,accent) in enumerate(phases):
    x=px+i*(pw+pgap)
    box(x,1173,pw,145,fill,14,"#D2E0EE",1)
    text(x+20,1213,h,27,accent,850)
    text(x+20,1256,line1,23,"#1D3B55",650)
    text(x+20,1295,line2,21,"#425D73",540)
box(40,1389,2320,83,"#E8EFF8",14,"#CFDDEB",1)
text(68,1438,"핵심 주의  |  실시간·분봉 및 과거 컨센서스는 별도 공급자가 필요할 수 있음",26,"#203D5B",700)
text(2330,1438,"설계 문서 저장 완료 · 실제 API 연결은 미완료",22,"#516B85",550,"end")
text(45,1498,"EraLeader  /  T5DATA  /  데이터 수집 구조도  /  초기 설계·미검증 가정은 실제 백테스트로 검증",18,"#627890",550)
append("</svg>")
f=outdir/"EraLeader_데이터수집_전체구조도.svg"
f.write_text("\n".join(svg),encoding="utf-8")
print(f"SVG={f} BYTES={f.stat().st_size} ELEMENTS={len(svg)}")
