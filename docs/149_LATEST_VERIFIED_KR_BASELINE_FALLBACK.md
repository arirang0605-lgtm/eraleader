# 149 — KRX 당일 0행 시 최근 검증 완료 거래일로 자동 대체 (연구용)

- 날짜: 2026-10-13 KST
- 개발 ID: 1_5·2_3·2_5·4_2·6_2·6_5
- 사용자 결정: 당일 공식 KRX/DART 자료를 얻지 못하면 분석 전체 중단 대신 **가장 최근 실제 SHA/원본 코호트 검증을 통과한 거래일 연구 결과**를 날짜·지연 경고와 함께 표시한다. 과거 데이터를 오늘 실매매 신호로 소급하지 않는다.
- 원본 `eraleader/main` 및 미커밋 `native_first_capture.py` 6추가/1삭제 수정 전혀 없음. 별도 `feature/core-official-factor-coverage-20261013` 에서만 변경.

## 실제 구현

1. `src/eraleader/official_latest_baseline_fallback.py` 신규: 이전에 발행한 `official_api_pit_research.json`, `basic_candidates_kr.json`, `industry_peers_kr.json`, 원본 WATCH run, KRX2+DART first receipt SHA와 DART 전 페이지 manifest SHA를 **기존 검증함수로 다시 검사**. 파일 이름에 있는 날짜가 아니라 공식 관측 `api_observation_day`가 우선이며 미래 시점·SHA 변조·원본 혼합/가짜 사후 소급 시 차단.
2. 선택 승인된 백업 연구 root 1개 이상 또는 `--fallback-history-dir` 아래 최대 두 단계의 기존 완성 폴더를 자동 검색. 빈/미완성 자료는 제외하고 **검증된 가장 최근 관측일** 우선, 같은 날이면 더 최신 실제 연구결정 시각 우선. 서로 다른 종목의 완전한 보고서는 대상 종목이 없을 때에만 제외; 원본 SHA/권한/관측일 오류는 **다른 자료로 숨기지 않고 FAIL CLOSED**.
3. 당일 정상 자료가 있으면 기존 `advance` 원형 유지. 당일 KRX 미존재, 당일 CFS/업종 동시점 코호트 미완, 19시 이전 또는 주말은 과거 연구로 대체. `OFFICIAL_KRX_DAILY_ROWS_NOT_YET_AVAILABLE` 오류만 안전하게 catch하며 인증·SHA/파일 권한·회사 주권 PIT 오류는 catch 금지.
4. 선택한 지난 거래일 자료는 **새 개인경로** `index.html`(후보의 과거 매출/영업이익 YoY, 3개월 가격, 3개년 성장 가속 등) + `report.json`(canonical SHA)으로 원자 게시. 기존 WATCH/점수/원본/보고서·모의투자 수급·주문 수정0.
5. `scripts/run_official_kiwoom_research.py` 기존 CLI에 `--fallback-history-dir`, 반복 가능한 `--fallback-source`, `--fallback-out`을 추가. 일별 비대화식 실행을 위해 `--day today`(Mac Asia/Seoul 기준) 및 `--official-out`/`--cohort-root`/`--fallback-out` 경로 내 `{date}` YYYYMMDD 치환 지원. 옵션을 쓰지 않으면 기존 엄격한 최신일/키움 연구 기능 그대로.

## 표시되는 데이터 시각

- `request_day`: 연구 실행에서 조회한 날짜(오늘).
- `source_market_session`: 실제 공식 가격 관측 거래일(미래 날짜 불허).
- `source_first_research_decision_at_utc`, `source_last_research_decision_at_utc`, `published_at_utc`: 과거 원본 수신·연구판정 및 현재 연구게시 시간은 구분.
- `calendar_days_since_market_observation`: 달력일 간격.
- `estimated_weekday_sessions_since_market_observation`: 월~금 평일만 세는 **추정**(휴장 미반영). 2평일 이상이면 `STALE_RESEARCH_WARNING`. 금요일→월요일은 1평일 추정.
- `trading_session_lag=null`, `exchange_calendar_pit_certified=false`: 공식 거래소 캘린더/공시 PIT 인증 없이 '정확한 T-1' 또는 'N일 거래일'로 표시하지 않음. 당일 신규 투자우선순위/거래/키움 혼합0.

## 일상 연구 실행 예시 (기본 네트워크 호출 0)

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src python3 scripts/run_official_kiwoom_research.py \
  --day today \
  --official-out '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/official_{date}' \
  --cohort-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/cohort_{date}' \
  --codes 005930,000660 \
  --fallback-history-dir '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' \
  --fallback-out '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/latest_verified_{date}'
```

기존 `official_out`이 실제로 없다면 어떤 공식 API도 자동 호출하지 않고 검증된 과거 연구 결과만 표시한다. 실제 당일 시장 수신은 별도 명시적 `--capture-official`와 보호된 `--capture-root`를 함께 지정한 운영일에만 실행. `--apply-demo-flow`를 지정했어도 과거 자료 fallback 때는 Kiwoom API를 호출하지 않으며 동일일자 결합·매매/리더판정은 0. 기존 폴더 덮어쓰기를 하지 않으므로 재발행은 다른 output 경로로 명시해야 한다. 스케줄러 자동 설치/로드는 이번 작업에서 하지 않음.

## 2026-10-13 T5DATA 실제 원본 E2E

- 기존 `output/same_session_cohort_3fy_20261013/` 및 이전 2FY 연구 아카이브에서 최근 관측일을 자동 판별. 2026-10-13 공식 양시장 신뢰 가능한 당일 연구가 없으므로 **2026-10-08 공식 KRX 관측일**을 선택. 이 데이터는 10월 13일 최초 수신/연구 판정으로 사용되었으므로 **10월 8일 당시의 사전 투자 결정은 결코 아님**.
- `output/latest_verified_market_baseline_20261013_v2/{index.html,report.json}` 생성 성공: 요청 10/13, 관측 10/08, 달력 5일 차이, 평일 3일 **추정**, 실전 신선도 경고 true, 선택 2개 기업 연구 데이터 보존, JSON SHA 재검증 PASS, HTTP `index.html`/`report.json` 각 200.
- 공급자 KRX/DART/키움 외부 신규 네트워크0, 기존 원본/WATCH 변경0, 주문0, 공식대장주0. 독립 장기 역사 PIT/시장 휴일 캘린더 및 미래 실전 발굴 적중률은 미인증.

## 자동 테스트/오류 수정

- 신규 `tests/test_official_latest_baseline_fallback.py`: 전일/이틀 경고/금→월 평일 추정, 최신 완성 후보 선택, 타임스탬프·SHA·회사 id 변경/심볼릭 링크/미완성원본/미래일/실패 시 원본 불변, 현재 실데이터 정상경로 보존, KRX 0행만 fallback 허용, 인증·권한 실패 차단, 브로커 미실행, HTML escaping, 자동 archive 검색·빈 역사 처리, CLI `today`/경로 날짜 치환.
- 관련 14개 모듈 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest ... --junitxml=output/verification_logs/latest_baseline_fallback_final_20261013.xml` → **189 PASS, FAIL0, ERROR0, SKIP0, EXIT0**.
- Python 컴파일, Git 공개 단계에서 변경파일만 staging/safety scan 필수. 전체 수천 건 장기 회귀는 API/완성도 검증 단계에서 별도.

## 다음 미완료

공식 거래소 세션 캘린더의 원본 게시/수신시각 인수 → 정확한 거래일(T-1/T-2) 추적. 당일 KRX 양시장 0행 원인·공식 배포 지연 확인 → 현재일 KRX/DART/CFS/업종 동일시점 첫 SHA 자동 확보. 실제 정기 구동·자동 보고·알림의 20거래일 운영 및 최종 SSD 탈착/재부팅은 미완료. 매수·매도 시스템에는 연결하지 않음.
