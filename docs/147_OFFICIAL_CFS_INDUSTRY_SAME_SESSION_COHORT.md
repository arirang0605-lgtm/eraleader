# 147 — KRX·DART 가격·재무·업종 동일 거래일 연구 코호트 자동 결선

- 날짜: 2026-10-13 KST
- 개발ID: 2_2·2_5·3_4·3_5·4_2·6_2
- 작업 브랜치: `feature/core-official-factor-coverage-20261013`; 원본 `main` 변경 금지
- 범위: 실전 투자신호가 아니라 **실제 최초 수신 원문 SHA를 결속한 연구용 후보/업종 화면**. 키움 브로커 자동 조회·주문 없음

## 재사용한 기존 정상 코드

- `official_api_pit_bridge`: KRX 코스피/코스닥·DART 공시 최초 영수증, 가격 WATCH 원장 및 일/주/월 보고.
- `official_dart_multi_company`: 2연도 DART 연결재무 first receipt, 미확정 기업 정보는 N/A.
- `official_basic_candidates` / `official_industry_peer_screen`: 실제 관찰가격 + CFS 재무 + 현재 DART 업종 비교 및 각 JSON 해시.
- `official_kiwoom_daily_bridge._inspect_official/_inspect_cohort`: 동일 거래일 및 원래 WATCH run에서 직접 KRX 두 시장+DART first receipt SHA, DART full-day SHA 비교.
- `SharedBrokerAPI`와 원래 `eraleader/main`은 읽기 전용(미수정).

## 이번 기능 구현

1. 신규 `src/eraleader/official_same_session_cohort.py` / `scripts/publish_official_same_session_cohort.py`: 별도 공식 거래관측 연구 폴더, CFS 다기업 manifest, 현재 산업 profile manifest, 보호된 first-receipt root, 선택 1~5개 종목코드 입력. 기존 두 발행기를 순서대로 호출하고 세 API 원본 pin/동일 WATCH run 및 두 JSON SHA를 모두 검증. 신규 output 디렉터리에만 원자 발표, 실패시 임시 결과 제거. 선행 공시·과거 시점으로 후보를 소급하지 않음. 기본 **외부 네트워크 호출 0**.
2. 기존 `scripts/publish_basic_company_screen.py`의 제한적 소스 계약 보완: KR 공식 당일 KRX2+DART3만 있는 연구 원문 허용. SEC submissions+companyfacts는 **둘 모두 존재할 때만** 보조 출처로 추가; 한쪽만 있으면 거부. 필수 KRX/DART PIT·첫 receipt 검증 생략 금지.
3. 기존 `scripts/run_official_kiwoom_research.py`에 명시적 `--dart-directory-first-sha` opt-in: 기존 DART 현재 법인 ZIP first SHA가 검증된 때만 공식 capture에 전달. 새로운 DART directory 조회 강제하지 않음. `--capture-official` 없는 pin 주입 금지, 증명시각 이전 사용 금지. Broker demo 명시 실행 조건/기존 보수적 gate 유지.

## 실제 SSD 연구 원문 재실행

- `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/official_api_pit_research.json` + `multi_company_cfs_20261013_v1.json` + `dart_industry_cohort_20261013_v1.json` 기존 검증 산출물 read-only 사용.
- **KRX/DART 거래관측일 2026-10-08**: 10개 기업 가격·FY24/25 재무·업종 연계 발행 실제 성공. `output/same_session_cohort_archive_probe_20261013/` (feature worktree, Git ignored)에 별도 HTML/JSON 생성.
- `selected_stock_count=2`, `financial_companies=10`, `industry_companies=10`, `broker_network_calls=0`, `historical_pit_certified=false`, `investment_ranking_available=false`, `orders_enabled=false`.
- **중요:** 10월 8일 시장 관측일과 10월 13일 첫 로컬 수신/연구 실행은 다름. 역사적 10월 8일 매매신호로 소급 금지. 10월 13일 공식 KRX 당일 0행은 이 변경으로 채워지지 않음. 최신 당일 3공급자 완전 증거가 없으면 실시간 키움 결합은 기존대로 HOLD.

## 변경 영향 및 실패 시험

- 신규 `tests/test_official_same_session_cohort.py`: 원자 발표·재실행 불변·산업 후기 실패 rollback·원본 변조·잘못된 거래일/코드/시계/symlink/출력 경로·비밀 에러 비노출.
- 신규 `tests/test_official_basic_kr_only_input.py`: 공식 KRX2+DART3만의 입력 정상, SEC 반쪽 거부.
- 신규 `tests/test_official_kiwoom_directory_reuse.py`: 정확한 DART 원본 SHA 재사용, 잘못된 SHA/이름/symlink 거부, CLI opt-in·원본 인계.
- 전체 11개 관련 모듈 scoped pytest: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_official_same_session_cohort.py tests/test_official_basic_kr_only_input.py tests/test_official_kiwoom_directory_reuse.py tests/test_official_kiwoom_daily_bridge.py tests/test_official_basic_candidates.py tests/test_official_industry_peer_screen.py tests/test_official_kr_daily_pipeline.py tests/test_dart_multi_company.py tests/test_official_api_pit_bridge.py tests/test_kiwoom_daily_runner.py tests/test_kiwoom_shared_daily_batch.py -q --tb=short`.
- JUnit: `output/verification_logs/same_session_cohort_scoped_20261013.xml`, **133 PASS, 0 FAIL/ERROR/SKIP, EXIT0**. Python compile PASS.
- 전체 2,450+ 장기 회귀는 이번 변경에서 미실행. 보관자료의 실제 주식 PIT 독립 인증과 전향적 적중률은 N/A.

## 다음 미완료

- KRX 당일 코스피/코스닥 행수가 유효한 세션에만 공식 1회 수집, DART 전 페이지와 처음 받은 법인코드/재무·업종 동시점 PIN을 묶은 실제 최신 연구 코호트 자동 생성.
- 키움 모의 수급은 **동일 시점 3원본·후행 cohort SHA 확인 후** 연구 sidecar에만 연결. 실전 주문/대장주 확정 금지.
- Prospective 후보 Top-K 실제 성과는 기록일 이후 5/20/60 거래일 자연 만기 측정. 공식 PIT/미국 전체 공급자 이력, 실제 SSD 탈착/재부팅 검증은 별개 미완료.
