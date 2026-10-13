# 148 — DART FY2023~25 10기업 실적성장 가속 실제 연결

- 날짜: 2026-10-13 KST
- 개발ID: 1_2·3_3·3_4·3_5·6_2
- 목적: 초기 가격 모멘텀+단일 YoY보다 유용한 **매출 성장 가속/둔화**를 3개 연속 공시 사업연도에서 관찰. 연구용, 정식 투자 100점/실거래 아님.

## 변경된 코드

- `scripts/publish_basic_company_screen.py`: 기존 CFS 최초 SHA 검증과 가격·WATCH·리포트 엔진 재사용. 2FY(2024/25) 및 3FY(2023/24/25)만 계약 허용, 최소 2개/최대12개 **완전한 회사당 2 또는 3 원본**, 3FY 12사 최대 36개 영수증까지 처리. 비연속/미허용 FY, 누락·불완전 원본은 자동 채우거나 0처리하지 않음.
- `tests/test_official_basic_kr_only_input.py`: 3FY 9개사×3연도=27개 독립 first SHA 입력 경계, 2022 혼합·연도 역순 등 4종 잘못된 기간 거부. 기존 2FY, KR3공급자+선택 SEC쌍 연구도 그대로.
- 기존 `official_dart_multi_company.collect_multi_company_cfs`는 **이미 2023/24/25 수집 지원**, `official_api_pit_bridge`는 **이미 3FY annual_acceleration_diagnostic 지원**, `official_basic_candidates`는 **이미 revenue_yoy_acceleration을 HTML에 표시**. 정상 기능을 재작성하지 않음.

## 실물 2026-10-13 공식 API 및 결과

- T5DATA의 2026-10-08 KRX+완전 DART 첫 원본, DART 현재 법인 디렉터리 최초 SHA, FY2024/25 20건을 재사용. 10개 기업 FY2023 기존 1건 재사용 + 신규 **9건** 공식 DART 수신/원본 최초 SHA 보존. **10/10 기업 모두 2023, 2024, 2025 총30개 실물 first receipt** 검증, `companies_with_complete_annual_cfs=10`, `CAPTURE_EXIT=0`.
- private Git-ignored local manifest: `output/multi_company_cfs_3fy_20261013.json`. 실제 API 호출 원문/키/토큰 공개 Git 제외. 원본 receipt 덮어쓰기0.
- 신규 연구 게시 `output/same_session_cohort_3fy_20261013/` + JSON/HTML (별도 feature 출력, 원래 10/08 화면/가격 WATCH 불변). `PUBLISH_EXIT=0`: 재무10사+업종10사, 선택 종목2개, broker HTTP0, 거래0, 공식 대장주0.
- 실제 3FY `basic_candidates_kr.json` 해시 검증 성공. 매출 성장 **가속 4개사, 둔화 6개사, N/A 0개사** 관찰(작은 고정 표본 10기업; 과거/미래 투자수익률 또는 정식 leader 랭킹 주장이 아님). 기존 업종 `industry_peers_kr.json` 연계 10개 모두 성공.
- Mac 로컬 임시 loopback HTTP: `index.html`, `basic_candidates_kr.html`, `industry_peers_kr.html` **3개 HTTP 200**. 임시 웹서버 정상 종료, 공개 웹 배포0.

## 검증 기록

- 11개 관련 테스트 모듈 **138 PASS / failures0 / errors0 / skipped0 / EXIT0**. JUnit `output/verification_logs/three_fy_expansion_scope_20261013.xml`; Python 가격/KRX/CFS/업종/키움 경계 변형 증거 포함.
- `output/verification_logs/dart_3fy_10company_live_20261013.log`에 인증키 아닌 요약만 저장. `same_session_3fy_live_20261013.log`에 연구 게시 및 exit 결과.
- 전체 2450+ 회귀/장기간 전향성과 검증은 이 작은 변경에서 재실행하지 않음. **10월 8일 거래일과 10월 13일 실제 최초 수신/연구 판단시각은 서로 다름**, 10/08 투자신호 소급 금지. KRX 10/13 현재 코스피·코스닥 양시장 행수0 문제 그대로, 실전 동일일자 3공급자 PIT 미인증.

## 다음 기능

1. 한 날 유효한 KRX 양시장 일별 자료 수신 → 기존 `capture_and_publish_kr_day`에서 공식 일일 WATCH 생성. 3FY 다기업 CFS/업종 manifest가 최초 시각·같은 원본 PIN/동일 관측 거래일을 만족할 때만 병합.
2. 해당 연구 코호트가 성립할 경우 기존 보수적 `kiwoom_daily_runner`로 선택 1~5개 데모 수급만 연결(거래/전체 종목 투자 순위 아님).
3. 한국 산업 동종업체 FY3 커버리지를 확대하고, 미국 가격/주권 클래스 및 첫 공시 공개시각의 실제 PIT 원천, 미래 최초 WATCH 등록 이후 5/20/60일 자연 성숙 성과는 별도 실증.
