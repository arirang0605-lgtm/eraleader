#!/usr/bin/env python3
"""Render precise one-page Korean SVG technical diagrams for EraLeader stages 2–6.
Dependencies: Python stdlib only. PNG generated separately using installed Chrome.
All diagrams are plans (not implementation status).
"""
from pathlib import Path
from html import escape
import re, json
ROOT=Path("/Volumes/T5DATA/eraleader")
W,H=2300,1380
STAGES=[
dict(num=2, slug="PIT검증저장", title="과거 시점(PIT) 데이터 검증 · 저장", accent="#157F8E", tint="#E3F6F8",
 desc="수집한 자료를 당시 실제 알 수 있던 상태로 재현하는 신뢰성 계층",
 cols=[
 ("입력 자료","1단계 데이터 수집",[
   ("시장 시세","KRX·미국 일별 가격/거래량"),
   ("기업 공시","DART·SEC 접수·정정 시각"),
   ("종목 이력","상장·상폐·산업 편입 내역"),
   ("기업행동","분할·배당·합병·거래정지"),
   ("경제 데이터","ECOS·FRED·ALFRED 빈티지")]),
 ("구현 모듈","Python · DuckDB · Parquet",[
   ("원본 보관","API 응답을 수정 없이 저장"),
   ("종목 매핑","티커 변경에도 동일 기업 식별"),
   ("정제·검증","중복·단위·이상치·누락 검사"),
   ("시점 필터","available_at ≤ 판단 시각"),
   ("PIT 스냅샷","과거 종목군 + 당시 정보 조회")]),
 ("생성 산출물","3·5단계에서 재사용",[
   ("원본·정제 DB","수정 이력·원본 추적 가능"),
   ("PIT 스냅샷","날짜별 과거 정보 복원"),
   ("종목 마스터","상장폐지·시장/업종 이력"),
   ("품질 보고서","결측·오류·신뢰성 표시"),
   ("실행 메타","run_id·해시·코드 버전")]),
 ("검증 기준","완료 판정은 테스트 결과",[
   ("미래정보 차단","후행 공시는 과거에 보이지 않음"),
   ("정정공시 보존","정정 전 시점 값 유지"),
   ("상폐 종목 포함","생존편향 감소"),
   ("분할·배당 검증","가격계열 혼동 방지"),
   ("재실행 동일성","중복 저장·결과 변경 없음")])
 ],
 steps=["원본 데이터 스키마","종목·티커 이력","정제·품질 규칙","PIT 시점 조회","자동 회귀 테스트"],
 note="필수: period_end(사업기간)와 available_at(공시 후 이용가능시각)을 절대 혼동하지 않음",
 outputs="Gate 2  |  PIT 누출 테스트 0건 · 원본 보관 · 상폐/기업행동 재현 · 품질 보고",
 md="docs/14_STAGE2_PIT_DATA_ENGINE.md"),
dict(num=3,slug="분석엔진",title="산업 · 기업 · 주가 분석 엔진",accent="#5550BA",tint="#ECEAFF",
 desc="산업 구조 변화와 기업 실적 가속, 상대강도를 계산해 대장주 점수 산출",
 cols=[
 ("입력 자료","2단계 PIT 저장소",[
   ("업종 정보","시점별 업종구성·시장 수익률"),
   ("기업 실적","매출·영업이익·FCF·CAPEX"),
   ("과거 예상치","EPS 전망 이력 (확보 시)"),
   ("시장 데이터","종목 주·월봉·거래량"),
   ("기관 수급","사용 가능 시점별 순매수")]),
 ("구현 모듈","점수 계산은 Python 배치",[
   ("산업 분석","성장률·투자·업종 RS"),
   ("기업 분석","실적 가속·경쟁력·현금흐름"),
   ("주가 분석","6·12개월 RS·주봉 추세"),
   ("정규화","시장/산업별 과거 퍼센타일"),
   ("종합 평가","5개 영역 가중치 합산")]),
 ("생성 산출물","최초 발굴 근거까지",[
   ("산업 TOP 5","당시 강한 산업별 후보"),
   ("기업별 점수","산업20·경쟁20·실적25"),
   ("추세·수급","RS25·수급10 (초기 가설)"),
   ("선정 이유","상승 요인과 반증 조건"),
   ("품질 표시","컨센서스 결측 등 N/A")]),
 ("검증 기준","높은 점수 ≠ 성공 확률",[
   ("PIT 누수 금지","과거 시점만 사용"),
   ("모멘텀 비교","단순 RS 모델보다 개선?"),
   ("업종 편향 검사","성장·가치 성격별 비교"),
   ("독립 모듈 검증","산업/실적/RS 별도 성능"),
   ("설명 가능성","점수 분해와 원자료 추적")])
 ],
 steps=["산업 지표","실적·재무 지표","RS·모멘텀 지표","종합 100점 가설","개별 백테스트"],
 note="초기 점수 20/20/25/25/10과 임계값은 연구용 가설이며 실제 검증 뒤 변경 가능",
 outputs="Gate 3  |  산업·기업 랭킹 재현 · 후보 점수 근거 · 결측 플래그 · baseline 비교",
 md="docs/15_STAGE3_ANALYSIS_ENGINE.md"),
dict(num=4,slug="대장주상태판정",title="잠재 · 확정 대장주 및 교체 판정",accent="#B86623",tint="#FFF0E3",
 desc="종목의 주도력 변화와 신규 후보를 상태 머신과 이벤트 이력으로 관리",
 cols=[
 ("입력 자료","2·3단계 분석 결과 재사용",[
   ("현재 점수","산업·실적·RS·수급 점수"),
   ("이전 상태","최초 발굴일·전주 상태"),
   ("주봉 신호","주간 마감 확정 추세"),
   ("실적 근거","공시·당시 추정치 변화"),
   ("유효성","거래정지·결측·상폐 여부")]),
 ("구현 모듈","규칙 기반 상태 머신",[
   ("잠재 후보","가속·RS 또는 65~79 가설"),
   ("확정 후보","80+ 및 실적·추세 교차확인"),
   ("약화 감지","복수 조건·추세 훼손 확인"),
   ("교체 탐색","후발주와 기존주 상대 비교"),
   ("상태 안정화","연속확인·히스테리시스")]),
 ("생성 산출물","시간순 이벤트 원장",[
   ("잠재 TOP 20","초기 대장주 후보"),
   ("확정 TOP 10","모델상 현재 주도주"),
   ("신규·승격","최초 발견일·이유"),
   ("약화·교체","경쟁기업 우위 이벤트"),
   ("상태 이력","WATCH/POTENTIAL/PAUSED")]),
 ("검증 기준","신호·알림 중복 방지",[
   ("재실행 동일성","같은 입력이면 같은 상태"),
   ("미확정봉 금지","임시 주봉으로 승격 금지"),
   ("상태 흔들림 억제","임계값 반복 왕복 방지"),
   ("교체 후보 근거","산업 내 동일 시점 비교"),
   ("자료 오류 시","PAUSED + 신호 차단")])
 ],
 steps=["상태 정의","후보 승격 규칙","약화·교체 감지","이벤트 원장","누수·중복 테스트"],
 note="확정 대장주 = 규칙상 현재 주도주. 미래 수익률 보증이나 자동 매매 신호가 아님",
 outputs="Gate 4  |  후보 TOP20·주도주 TOP10·변화 이벤트·변화 이유·최초 발굴일",
 md="docs/16_STAGE4_LEADER_STATE_MACHINE.md"),
dict(num=5,slug="단계별백테스트",title="단계별 백테스트 · 성능 평가",accent="#7653AA",tint="#F1E9FB",
 desc="미래 대장주 조기 발견 능력과 투자 가능한 수익률을 구분해 평가",
 cols=[
 ("입력 자료","과거 자료의 당시 상태만",[
   ("가격·기업행동","상폐·분할·배당·거래 제한"),
   ("후보 이력","각 시점 후보 점수·상태"),
   ("벤치마크","시장·업종지수·단순 RS"),
   ("투자 가정","수수료·슬리피지·유동성"),
   ("미래 성공라벨","평가에만 사용, 모델엔 금지")]),
 ("구현 모듈","기초 엔진은 조기에 구축",[
   ("범용 어댑터","기존 엔진 재사용 가능성 조사"),
   ("모듈 단독검증","산업/기업/RS 별도 평가"),
   ("시간순 재생","PIT 신호·다음 체결 시점"),
   ("워크포워드","훈련과 검증 시점 분리"),
   ("홀드아웃","미사용 최종 검증 구간")]),
 ("생성 산출물","발굴 능력과 수익성 분리",[
   ("조기 발견률","precision@K · recall@K"),
   ("발견 시차","lead time · 거짓 후보율"),
   ("초과수익","1/3/5년 시장·업종 대비"),
   ("위험지표","CAGR · MDD · turnover"),
   ("재현성","설정·데이터·코드 버전")]),
 ("검증 기준","과거 승자 선정 편향 방지",[
   ("생존편향 차단","과거 상폐·당시 종목군"),
   ("미래정보 차단","후행 공시·라벨 입력 금지"),
   ("체결 시차","종가 신호 당일 종가 매수 X"),
   ("과최적화 방지","반복 홀드아웃 튜닝 금지"),
   ("공정한 비교","비용과 같은 유니버스")])
 ],
 steps=["기초 RS baseline","개별 모듈 검증","통합 전략 비교","워크포워드 검증","미사용 데이터 평가"],
 note="과거 장기 10~15년은 목표. 실제 데이터 커버리지가 부족하면 한계를 명확히 표시",
 outputs="Gate 5  |  발굴 정확도 + 조기 발견시점 + 위험조정 성과 + PIT 통과 증거",
 md="docs/17_STAGE5_BACKTEST_RESEARCH.md"),
dict(num=6,slug="대시보드알림보고",title="웹 대시보드 · 자동 알림 · 정기 보고",accent="#167E6C",tint="#E0F7EE",
 desc="발굴 결과를 PC·휴대폰에서 확인하고 중요한 상태 변화만 자동 전달",
 cols=[
 ("입력 자료","앞 단계 결과 DB만 조회",[
   ("현재 후보","산업 TOP5 · 잠재20 · 확정10"),
   ("상태 이벤트","신규·승격·약화·교체"),
   ("검증 성과","선정 이후 수익·실패 사례"),
   ("데이터 품질","마지막 갱신 시각·결측"),
   ("운영 기록","run_id · 배치 오류 상태")]),
 ("구현 모듈","Python 결과 배포 계층",[
   ("결과 조회 API","시장별 read-only 스냅샷"),
   ("대시보드","홈·후보·개별 상세·성과"),
   ("알림 Outbox","중복키·실패 재전송"),
   ("보고서 엔진","일/주/월 HTML·PDF"),
   ("운영 보안","HTTPS·로그인·백업")]),
 ("생성 산출물","3가지 사용자 제공 기능",[
   ("① 웹 화면","PC·휴대폰 순위/종목 상세"),
   ("② 자동 알림","새 후보·확정·교체·위험"),
   ("③ 정기 보고","일간·주간·월간 분석"),
   ("성과 이력","발굴 후 수익과 반증 표시"),
   ("외부 연결","선택적 JSON/API MarketOS")]),
 ("검증 기준","일상 운영 AI 호출 최소화",[
   ("동일 DB 사용","웹·알림·보고 숫자 일치"),
   ("중복 방지","동일 이벤트 다중 발송 X"),
   ("시각 확인","한국·미국 마감일 차이"),
   ("서비스 보호","인증·키 비공개·약관"),
   ("끝단 테스트","수집→후보→보고 재현")])
 ],
 steps=["읽기 전용 API","최소 웹 화면","알림 Outbox","일·주·월 PDF","보안·클라우드 운영"],
 note="웹 화면은 실시간 추천을 보장하지 않음. 데이터 기준시각·모델 버전·검증 상태를 반드시 표시",
 outputs="Gate 6  |  웹·알림·보고 3종 end-to-end 테스트 + 중복·보안·신선도 검증",
 md="docs/18_STAGE6_DASHBOARD_ALERT_REPORT.md")
]
def newdoc():
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',"""<defs><linearGradient id="canvas" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F9FBFF"/><stop offset="1" stop-color="#EEF4FA"/></linearGradient><linearGradient id="header"><stop stop-color="#062B52"/><stop offset="1" stop-color="#21578B"/></linearGradient></defs>"""]
def rect(a,x,y,w,h,fill,rad=15,stroke="#CFDDEE",width=1.6):
    a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rad}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
def t(a,x,y,label,sz=25,color="#163451",bold=500,anchor="start"):
    a.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Apple SD Gothic Neo, Noto Sans CJK KR, sans-serif" font-size="{sz}" font-weight="{bold}" text-anchor="{anchor}">{escape(str(label))}</text>')
def render_one(s):
    a=newdoc();rect(a,0,0,W,H,"url(#canvas)",0,"none",0);rect(a,0,0,W,173,"url(#header)",0,"none",0)
    t(a,44,72,"EraLeader",73,"white",800)
    t(a,445,65,f'{s["num"]}단계  |  {s["title"]}',43,"white",820)
    t(a,47,126,s["desc"],27,"#CEE8FF",560)
    rect(a,1880,49,365,60,"#2C6B9D",12,"#70B4E8",1)
    t(a,2062,88,"독립 설계 · 실개발 명세",23,"white",740,"middle")
    # cards
    x0,gap=48,22;cw=(W-96-3*gap)/4; card_y=209
    for i,(h,subtitle,items) in enumerate(s["cols"]):
        x=x0+(cw+gap)*i
        rect(a,x,card_y,cw,679,"#FFFFFF",24,"#CBD9E8",2)
        rect(a,x,card_y,cw,111,s["tint"],22,"none",0)
        rect(a,x,card_y+88,cw,23,s["tint"],0,"none",0)
        rect(a,x+21,card_y+22,54,53,s["accent"],13,"none",0)
        t(a,x+48,card_y+59,str(i+1),29,"white",800,"middle")
        t(a,x+90,card_y+59,h,31,"#173855",800)
        t(a,x+20,card_y+102,subtitle,20,"#4B6580",550)
        for j,(k,v) in enumerate(items):
            yy=card_y+138+j*101
            rect(a,x+18,yy,cw-36,89,"#F7F9FD",11,"#E2EAF3",1)
            rect(a,x+31,yy+13,8,60,s["accent"],4,"none",0)
            t(a,x+52,yy+32,k,24,s["accent"],760)
            t(a,x+52,yy+67,v,21,"#294760",550)
        rect(a,x+17,card_y+652,cw-34,8,s["tint"],4,"none",0)
        if i<3:t(a,x+cw+gap/2,card_y+370,"›",62,"#4D8FCD",800,"middle")
    rect(a,48,913,W-96,195,"#FFFFFF",20,"#CDDEED",2)
    t(a,77,962,f"{s['num']}단계 개발 실행 순서",34,"#173B60",800)
    stgap=19;sw=(W-152-4*stgap)/5
    for j,label in enumerate(s["steps"]):
        xx=78+j*(sw+stgap)
        rect(a,xx,986,sw,91,s["tint"],14,"#D8E6F1",1)
        rect(a,xx+13,1007,50,50,s["accent"],13,"none",0)
        t(a,xx+38,1041,str(j+1),27,"white",800,"middle")
        t(a,xx+75,1041,label,24,"#193A56",720)
    rect(a,48,1132,W-96,93,"#ECF2FB",15,"#D1DFEE",1)
    t(a,79,1173,"핵심 방지 규칙",29,"#173A5B",790)
    t(a,79,1207,s["note"],23,"#344D66",570)
    rect(a,48,1249,W-96,92,s["tint"],16,"#D2E1ED",1)
    t(a,75,1302,s["outputs"],27,s["accent"],750)
    t(a,55,1370,f'문서: {s["md"]}      |      상태: 구현 설계 · API/실데이터 연결은 검증 전',18,"#627892",550)
    t(a,W-46,1370,"T5DATA / eraleader    •    2026.10.10",18,"#627892",500,"end")
    a.append("</svg>")
    name=f"EraLeader_{s['num']}단계_{s['slug']}_구조도.svg"
    p=ROOT/name;p.write_text("\n".join(a),encoding="utf-8")
    return name,p.stat().st_size
def render_overview():
    a=newdoc(); rect(a,0,0,W,H,"url(#canvas)",0,"none",0);rect(a,0,0,W,173,"url(#header)",0,"none",0)
    t(a,46,74,"EraLeader",72,"white",800)
    t(a,439,68,"2~6단계 개발 통합 구조도",51,"white",800)
    t(a,45,126,"1단계 데이터 수집 이후  |  검증 → 분석 → 선정 → 성과검증 → 결과 전달",29,"#D0EBFF",560)
    rect(a,1870,51,369,59,"#2C6B9D",12,"#75B7E6",1)
    t(a,2054,89,"독립 실행 + 모듈별 테스트",24,"white",710,"middle")
    gap=20;cw=(W-80-4*gap)/5
    for i,s in enumerate(STAGES):
        x=40+i*(cw+gap)
        rect(a,x,215,cw,798,"white",20,"#CBD9E9",2)
        rect(a,x,215,cw,135,s["tint"],20,"none",0)
        rect(a,x,325,cw,25,s["tint"],0,"none",0)
        rect(a,x+20,238,54,53,s["accent"],12,"none",0)
        t(a,x+47,275,s["num"],29,"white",800,"middle")
        smalltitles={2:"PIT 검증·저장",3:"발굴 분석 엔진",4:"후보 상태 판정",5:"백테스트",6:"사용자 결과 제공"}
        t(a,x+22,321,smalltitles[s["num"]],28,"#173751",800)
        # five data rows from input and implementation, avoid verbosity
        lines=[
          ("자료",s["cols"][0][2][0][1]),
          ("자료",s["cols"][0][2][1][1]),
          ("구현",s["cols"][1][2][0][1]),
          ("구현",s["cols"][1][2][3][1]),
          ("출력",s["cols"][2][2][0][1]),
          ("출력",s["cols"][2][2][1][1]),
          ("테스트",s["cols"][3][2][0][1])]
        for k,(type_,v) in enumerate(lines):
            yy=365+k*86
            rect(a,x+13,yy,cw-26,75,"#F6F9FD",10,"#DFE8F2",1)
            t(a,x+26,yy+28,type_,18,s["accent"],820)
            t(a,x+26,yy+57,v,19,"#2C4C68",550)
        rect(a,x+13,978,cw-26,16,s["tint"],5,"none",0)
        if i<4:t(a,x+cw+gap/2,589,"›",47,"#4A91CE",800,"middle")
    rect(a,40,1037,W-80,166,"#FFFFFF",20,"#CDDEED",2)
    t(a,69,1088,"실행 순서",32,"#153B5C",800)
    route=["1단계 원본 수집","2단계 PIT 스냅샷","3단계 산업·실적·RS","4단계 잠재/확정/교체","5단계 시점별 검증","6단계 웹·알림·보고"]
    for i,label in enumerate(route):
        xx=63+i*369
        rect(a,xx,1110,338,67,STAGES[min(max(i-1,0),4)]["tint"],12)
        t(a,xx+169,1154,label,22,"#203E5B",730,"middle")
        if i<5:t(a,xx+350,1154,"→",28,"#4989C3",780,"middle")
    rect(a,40,1221,W-80,110,"#E8EFF8",16)
    t(a,71,1269,"공통 원칙: 미래정보 차단 · 과거 상폐 포함 · 단순 모델 비교 · 발굴 리드타임 측정 · 중복 알림 방지",27,"#173F64",720)
    t(a,71,1306,"AI 토큰 절약: Python이 정상 반복 작업 수행 / GitHub + PROJECT_STATE로 연결이 끊겨도 개발 재개",24,"#395A76",550)
    t(a,49,1370,"상태: 기술 설계서/구조도 작성 단계. 실데이터 연동·전략 검증·운영 시스템 구축은 아직 별도 개발 필요.",20,"#647B91",560)
    a.append("</svg>")
    p=ROOT/"EraLeader_2-6단계_통합구조도.svg";p.write_text("\n".join(a),encoding="utf-8");return p.name,p.stat().st_size

for s in STAGES:print("SAVED",*render_one(s))
# Deprecated 2-6 combined diagram replaced by 1-6 numbered master. Do not regenerate.
