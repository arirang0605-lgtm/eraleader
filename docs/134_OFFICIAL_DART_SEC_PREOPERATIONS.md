# EraLeader 공식 데이터 통합 개발 — 2026-10-12

개발ID: 1_2, 2_2, 2_5, 3_1, 3_2, 4_2, 6_2, 6_4. 사용자 요청에 따라 실전 운영 검증(20거래일) 이전 개발을 진행한다. 기존 정상 WATCH, SQLite, 보고서·대시보드 코드를 유지하고 새 공식 자료를 first-received SHA로 붙이는 방식이다.

## 추가 구현

- official_dart_daily.py / complete_dart_disclosures.py: 기존 최초 DART 100건을 변경하지 않고 나머지 페이지를 원자적 0700 신규 보관. 모든 원문 SHA, 첫 확보 시각, 페이지 수/전체 건수, 서로 다른 접수번호, 일자, 중복/탈락/변조·부분 작업을 검사한다.
- official_dart_corp_directory.py / capture_dart_corp_directory.py: 공식 corpCode.xml ZIP 첫 SHA·로컬 최초 수신시각/DTD·ZIP 안전/코드 중복·모호성 검사. 현재 기업코드를 KRX 주권코드에 연구용으로 매핑하되 상장 당시 법적 issuer/share-class라고 주장하지 않는다.
- official_dart_financials.py / capture_dart_financial.py: 공식 fnlttSinglAcntAll.json, 지정 회사·사업연도·연결/별도 재무 및 보고서코드. source corp 코드·공시번호·원시금액·계정코드·SHA·수신시각 검사, IFRS/DART 정확한 항목에만 매출/영업익/순익을 배정. 연속 사업보고서 2개가 있는 경우에만 매출·영업익·순익 YoY 연구 진단.
- official_sec_pit_features.py / audit_sec_first_financials.py: 기존 SEC submissions + companyfacts 동일 CIK first-receipt SHA, acceptanceDateTime 및 accession/form/filed 교차확인, US GAAP 지표를 as-of 별 연구용으로 추출. 최신 submissions에 없는 과거 fact는 보류. 미국 전체 주권군이나 주가 PIT 미확보로 종합 대장주 판정 미실시.
- official_api_pit_bridge.py / run_official_api_pit.py: DART 전체공시 SHA+원본 최초 PIN, corpDirectory SHA, 여러 재무 CFS PIN을 선택 입력. KRX/DART 기업고유코드 충돌·분할·변조/미수신은 첫 WATCH 작성 전에 차단. 기존 score run-ID에 원본 증거 SHA 결박, 기존 WATCH 20/SQLite/DRY-RUN/일주월 3종 보고/HTML 재사용. 재무 피처는 N/A와 미검증 연구 열로만 표시, 공식 승격 0.
- official_kr_daily_pipeline.py / run_official_kr_daily.py: 명시적인 1회 개발자 호출에서 KRX 양시장+당일 DART 전체 첫 원문→PIN 검증→기존 발굴/웹/보고서 실행. 데이터/API 결손 시 WATCH 게시 차단, 날짜/신선도 검사, 새 출력만 허용. 연구결과는 비공개 형제 임시 폴더에서 SQLite·보고서·HTML 전부 완성/경로 검증 후 최종 경로로 한 번에 공개(rename); 후반 보고서 실패/대상 폴더 경쟁 발생 시 출력 미공개·사용자 파일 비덮어쓰기 테스트. 원본 API 첫 수신 보관은 유지. launchd 실전 자동운영/외부메시지/자동매매 연결하지 않음.
- 새 합성 mock transport+타임머신·변조·중복·누락·거래일/공시시각/첫 SHA 테스트. 전체 회귀 검증과 Git 증거는 PROJECT_STATE.md 최신 체크포인트 참조.

## Mac의 공식 실제 데이터 연결 증거

- 실제 KRX 2026-10-08 코스피 942 + 코스닥 1,823 = 2,765 일별 거래 행.
- 실제 DART 2026-10-08 기존 첫 페이지 100행에서 최종 10페이지 전체 992행 확보, 첫 수신 원본·새 페이지 SHA 검증.
- DART 현재 corpCode.zip 119,601개 공시대상 기업, 종목코드 기재 3,998개, 내부 모호 0. 2026-10-08 KRX 2,765개와 현재 코드를 직접 비교해 정확한 단일 DART 법인코드 2,651개 관측 일치, 114개 미일치/결측. 이 비율은 과거 상장·class/상폐 완전성 인증이 아니다.
- 당일 DART 공시에서 KRX 주권코드와 교집합 291. 그날 공시하지 않은 기업은 삭제 또는 부실로 해석 금지.
- DART 실제 005930 연결 2024 사업보고서 213행, 2025 사업보고서 229행 각각 매출/영업익/순익 3개 안전 매핑. 연구용 2025 YoY 매출 +10.88%, 영업익 +33.23%, 순익 +31.22% (2026-10-12 이후 최초 확보이므로 역사적 성과 소급 금지).
- SEC 실제 단일 CIK submissions 1,001개와 companyfacts 사용, accession/공개시각 확인 가능한 322개 연구 재무 관측, 매칭 불가 532건은 부재/0으로 채우지 않음.
- 실제 전체 교차 결선 KRX 2,765 + DART 992 + DART code 매칭 2,651 + 실 CFS 1개 기업 연간 비교 → 기존 WATCH 20, 보고서 3, DRY-RUN 알림 20, 실전 발송 0. 정식 대장주 인증 0.
- 민감 원시 API 본문, SHA receipt, 분리 ZIP, 실제 종목별 자료는 Git ignored output/에서만 보관. Public Git에는 코드·합성 테스트·MD만 올린다. native_first_capture.py의 미커밋 6+/1- 변경은 보존한다.

## 아직 해결되지 않은 개발·검증

이 단계는 실사용 완성이 아니다. 한국 전체 종목의 필요한 재무·산업·기관 수급/PIT 커버리지와 주권 클래스·상장폐지·분할·배당/정정 공시 원천, 미국 주가 전시장 및 기업·주권 이력·SEC/PIT 시차, 상시 실제 데이터 증분 수집/주간장애 복구, 실발송 수단과 알림채널 관리, 공식 대장주 판정의 사전 검증이 남아 있다. 그 이전에는 WATCH 연구·DRY-RUN과 결측/N/A가 기본이며 100점 종합 대장주 확정 또는 투자 매매 판단을 만들지 않는다.

KRX 코스피/코스닥 승인기간은 2026-10-12~2026-11-11. SSD 물리 재연결 및 Mac 재부팅(D-021)과 20거래일 실전 모의운영은 사용자 지시대로 마지막 검증 단계에 남긴다. 실제 출력 시각·공급자 자료 공시일·처음 로컬 수신 시각을 구분한다.

공식 참고:
https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001
https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018
https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020

## 독립적인 공식 API 1회 통합 스모크
2026-10-12 기존 보호 Mac 인증 설정으로, 새 scripts/run_official_kr_daily.py를 한번 명시 실행했다. 2026-10-08 KRX 코스피/코스닥 2회와 DART 전체 10페이지 신규 실제 HTTP 수신부터 실행, 공식 KRX 관측행 2765, 전체 DART 공시 992, 새 first receipts/SHA, 기존 WATCH 연구 20/보고서 3/DRY-RUN 알림 20, 메시지0/PIT인증false. 출력은 Git ignored output/official_manual_pipeline_live_20261012. 자동예약/실전 20거래일 운용은 실행하지 않았다.
