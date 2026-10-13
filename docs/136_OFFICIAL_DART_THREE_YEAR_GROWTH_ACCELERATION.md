# 136 — DART 3개 연속 연결재무 사업연도 실적 성장 가속 연구 결선

**개발 ID:** 2_2·3_1·3_2·6_2, 실제 Mac/T5DATA, 2026-10-13 KST
**기준:** core feature `f5522c431469246901bed1783d54fa5887ced5ed`부터 CONTINUE. 기존 정식 대장주·100점 판정·주문 연결 없음.

## 실제 해결된 문제

1. 이전에는 2024·2025 연결 사업보고서 CFS 두 건만 독립 원본 SHA로 확인해 **FY2025 성장률 하나**를 계산했다. FY2024의 성장률이 없어 성장 가속도 판단은 불가능했다.
2. `scripts/capture_dart_financial.py`를 **기존 Mac owner-only DART 인증정보를 이용**해 005930 FY2023, `reprt_code=11011`, `statement=CFS` **정확히 1번 실행**해 2023 원본 회신·최초 로컬 수신시각·첫 receipt SHA의 신규 비공개 보관본을 확보했다. DART 응답 `FINANCIAL_ROWS_RECEIVED_RESEARCH_ONLY`, 비교 지표 3개, 재수신·비밀키 출력/업로드/메시지 발송 없음.
3. 기존 2024·2025 first receipt 원본과 추가 FY2023 receipt **세 건을 각각 재검증**하고 DART 현재 corpCode 공식 ZIP 원문과 005930 회사코드가 일치할 때만 원장/조회에서 이용 가능. 서명 원문이 먼저 로컬에 수신된 시각 이후 결정에서만 성장률 계산.
4. `src/eraleader/official_dart_financials.py` 신규 `annual_acceleration_diagnostic`: 기존 2년 함수 `annual_growth_diagnostic`를 2023→2024 / 2024→2025에 **두 번 재사용**해 후반 YoY - 전반 YoY를 계산. 동일 주권·법인·연간 사업보고 코드11011·CFS·연속3년·연도별 다른 14자리 접수번호·첫 로컬 수신 UTC≤결정시점이 모두 충족되지 않으면 fail-closed. 매출/영업익/순익 전기 기준값 0·음수·누락 시 해당 비교/가속은 N/A.
5. `official_api_pit_bridge.py`: 기존 2년 분기 완전 보존. 동일 회사의 서로 다른 독립 first receipt가 연속 3개 연도 존재할 때 **실적 가속 연구**를 `official_financial_research_observations`에 연결. 회사가 가격 상위20개에 없어도 노출, 원래 PRICE WATCH/가격 순위/점수, 기존 로컬 SQLite와 DRY-RUN 동작 변경하지 않음. 같은 FY 연도의 여러 원본(정정판 모호성)·기업고유번호 오류는 입력 전에 거절. 4개년 이상 입력은 현재 N/A가 아닌 명시적 오류로 차단(추후 설계 확장 대상).
6. `official_factor_readiness.py`: 3년의 독립 영수증 SHA·연속 연도와 이전/현재 YOY 차이 **교차검산**, 뒤늦게 덮어쓴 가속도/잘못된 금액·누락/미래 첫 수신·가짜 PIT 인증 거절. JSON은 기존 `annual_cfs_comparable_companies`와 독립 `annual_cfs_acceleration_companies`, `previous_revenue_yoy`, `revenue_yoy`, `revenue_yoy_acceleration` 등 개별 정보를 저장. HTML은 +16.20%, +10.88%, **-5.32 pp**처럼 2개 연간 성장률과 가속도의 단위·차이를 분리 표시. 원시 기사/키는 로컬 private 위치에만 보관.

## 실물 3개 사업연도 연구 결과 (삼성전자, 005930)

- 원본: FY2023·FY2024·FY2025 DART 연결 사업보고서 **3건**, 공시 현시점 조회로 확보한 사업연도 원본별 `thstrm_amount`, DART 원시 response 및 SHA 확인. 거래일 `2026-10-08` KRX KOSPI 942 + KOSDAQ 1,823 = **2,765 일별 관측행**와 DART 동일 일자 완전 공시 **992건** (10페이지), 현재 corpDirectory 교차 연결2,651개.
- 실제 계산: 매출 FY2024 YoY **+16.1953%** / FY2025 YoY **+10.8801%** / YoY 변화 **-5.3152 percentage points**. 영업익 FY2024 YoY +398.3414%, FY2025 +33.2308%, 변화 -365.1106pp, 순익 FY2024 +122.4519%, FY2025 +31.2193%, 변화 -91.2327pp. **이 변화는 성장률의 둔화 관측이지 기업투자 매도신호가 아니다.** 전기 작은 분모가 백분율 크기에 크게 영향을 준다.
- 가격 WATCH Top20 **미포함** 회사도 독립 실적 화면에 표시된다. 해당 종목의 `full_investment_score=None`, `official_leader=False`. 기준 시장일 2026-10-08, 최초 로컬 2023 원본은 2026-10-13 수신이므로 **2026-10-08 또는 FY2023 당시 사전 발견·과거 백테스트 실적이라고 주장할 수 없다**.
- 실제 전체 3년 영수증은 **005930 단 1개 기업에 한정**. 전 종목/시장 평균 성장 가속을 달성한 것이 아니다. 추가 DART 전국/미국 통합 발행사 분류, 최초 공시·정정 vintage/PIT 법적 issuer/share-class, 상폐·분할/배당, 3년 연속 CFS 미수신 기업은 모두 N/A.

## 직접 실행 결과 / 재현

- 첫 `build_official_price_snapshot` + `run_official_research`: **원시 SHA→가격 WATCH 20/실적 3연도 1사/일주월 보고 3/DRY-RUN 외부 전송0→HTML/JSON** 전체 PASS. 별도 Git 무시 output: `output/official_core_3yr_acceleration_20261013`.
- 기존 정식 `scripts/run_official_api_pit.py` CLI를 **PIN3개, KRX/SEC/DART 기보관 공식 수신 원본 SHA, full DART 10페이지 manifest SHA, corpCode 첫 PIN**으로 재실행: `CLI_E2E_PASS EXIT0`, `2026-10-13` 연구결정, 005930 기존 price Top20 제외, 전기 매출+16.20% / 최근+10.88% / 가속 -5.32pp UI PASS, `messages_sent=0`, `official_leaders=0`. 별도 최종 출력 `output/official_core_3yr_acceleration_20261013_final`; 기존 결과 1바이트 덮어쓰기 없음. 새 8768 로컬 화면: `http://127.0.0.1:8768/factor_readiness_kr.html`.
- `scripts/capture_dart_financial.py`은 이미 제공되는 공식 인증을 사용하고 원본 first receipt를 비공개 `output/official_api_capture/dart_fin_.../` 0700/0600 소유자 권한에만 보존. **동일 2023 원본 재수집하지 말 것.** 재현 시 기존 원본을 SHA로 검색하여 선택하고 `scripts/run_official_api_pit.py --dart-financial PATH PIN`을 연도별 3번 지정한다.

## 테스트·검증 한계

- 새로운 `tests/test_dart_annual_acceleration.py`, 확장 `tests/test_official_factor_readiness.py` 및 `tests/test_official_api_pit_bridge.py`에 첫 SHA/미래수신/접수번호 불일치·재무액 0/음수/기업코드 틀림/기간 누락/가짜 PIT승격/HTML 표기 pp/가격 Top1 밖 독립 실적 노출 테스트 포함.
- 이전 2년 성장률 기존 테스트와 DART·KRX·SEC·원자 게시·PIT/연구 화면 등 **영향범위 테스트** 통과 증거를 `PROJECT_STATE.md` 최신 커밋에 기록. 전체 2,000개 이상 장기 회귀는 ER-NC-10 최종 통합 수락에서 실행.
- DART 연도별 API 현재 조회가 과거 처음 게시된 재무 수치 그대로라는 독립 출처 증빙은 **없음**. `historic_publication_time_certified=False`, `original_report_revision_history_certified=False`, `issuer_share_class_pit_certified=False`, `prospective_backtest_eligible=False`를 유지한다. 따라서 공식 실전 100점·대장주 확정/약화 판정·투자 1~20위·실전 정확도 모두 **N/A**.

## 다음 개발 1순위

공식 KRX 종목군→DART 법인·주권 클래스 기간 이력·공시 최초 공개 및 정정 관리 등 전체 시점별 데이터 완전성, 이후 산업·경쟁력·기관·외국인 수급 수집 및 **가격과 실적을 병합한 검증된 공통 후보군** 구축. 기존 정상 모듈 재작성·미완료 상태를 완료로 표기하는 일 금지.

**개발/운영 현실 보고:** 옛 99%/95% 추정 진행률 철회 유지. 기존 뉴스 확장 5개 worktree 경로가 이번 실제 SSD에서는 사라져 Git `prunable`로 보임. 다른 사용자 데이터 삭제·Git worktree prune/복구를 본 작업에서 임의로 하지 않는다. 원본 main 미커밋 `native_first_capture.py` SHA 원래값 보존.
