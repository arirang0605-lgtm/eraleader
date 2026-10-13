# 135 — 공식 원본 기반 대장주 5요소 데이터 충족도·상위 20위 밖 CFS 관찰 연결

**개발 ID:** 2_2/3_1/6_2 운영 통합 결선 · **검증 날짜:** 2026-10-13
**기준 소스:** main `a24400237f6a454b788ed1802ff6859c6a7a5c66` 기반 독립 feature 브랜치
**상태:** 공식 원본 재사용 1회 E2E **PASS**, *투자 우선순위/100점 모델/전향적 미래 대장주 성능은 N/A*.

## 발견한 실제 문제

기존 `discovery.score_price_observations`는 3개월 수익률 시장 내 백분위 40% + 6개월 백분위 60%로 **최대 25점 가격 관찰 순위**만 계산하고 TOP-N을 잘라낸다. `official_api_pit_bridge.build_official_price_snapshot`은 그 이후 DART CFS 연속연도 재무자료를 **그 TOP-N 행에만 붙이는 구조**였다. 따라서 실제 확보한 연결재무 기업도 가격 상위 20개에 없으면 웹의 실적 열에 노출되지 않았다. 이 순위는 투자 우선순위가 아니며, 진짜 100점 점수는 `None`이다.

2026-10-12 수집된 실제 공식 API 원시 SHA 영수증을 다시 검증한 결과(장세 데이터는 2026-10-08):
- 코스피 **942**, 코스닥 **1,823**, 총 **2,765개 당일 거래 관측 행**. 역사적 상장 주권 전수라는 의미는 아님.
- DART 해당 거래일 전체 **992건**(10페이지), 현재 DART corpDirectory **2,651/2,765개 주권코드 단일 일치**. 역사 issuer/share-class·분할/상폐 인증 아님.
- DART 실제 `005930`(삼성전자) 2024·2025 연결 사업보고서 두 건 원본 영수증/원시금액/기업코드 교차검증으로 **매출 YoY +10.8800933136%**, 원래 가격 TOP20에서는 **미포함**.
- **공인 종합 100점 평가 가능 0개**, 실제 성장 가속(3개 연도 필요), 외국인/기관 수급 및 산업/경쟁력 정규화 점수 **아직 없음**. 한 종목의 연간 매출 성장만으로 조기 대장주를 인증하면 안 됨.
- 과거 원본을 2026-10-12 수신했으므로 2026-10-08 당시에 이 정보를 미리 알고 예측한 것으로 기록하면 안 됨. 전향적 정량 적중률·precision@K·lead-days **N/A**.

## 새 코드 — 기존 정상 코드 재사용, REWRITE 0

1. `src/eraleader/official_api_pit_bridge.py`의 기존 `build_official_price_snapshot`에 소규모 opt-in 연결:
   - 원래 DART 공식 최초 SHA·이전/최근 연속 CFS 보고·현재 기업코드 교차검증을 그대로 재사용.
   - 기존 가격 20개를 먼저 점수화하는 구조/점수/순위/원장/DRY-RUN은 유지.
   - **전체 공식 KRX 관측 종목 중**, 별도 확보된 DART CFS 연속연도 비교 기업을 `official_financial_research_observations` 옆정보로 보존. 상위 20위 밖도 떨어뜨리지 않음.
   - 각 재무 관찰에는 `security_id`, 실제 당일 KRX 회사명, 보고 사업연도, `revenue_yoy`/`operating_income_yoy`/`net_income_yoy`, 원본 receipt 결합 SHA, `source_first_received_at_utc`, 원래 가격 TOP-N 순위 또는 N/A, `formal_score_100=None`, `official_leader=False`.
2. 신규 `src/eraleader/official_factor_readiness.py`:
   - 연구 snapshot과 검증된 각 provider 첫 receipt 메타정보에서 공식 당일 관측 universe·현재 DART 단일매칭·연속 CFS 비교 기업 수·가격 WATCH 수를 검증.
   - **5요소별 데이터 확보/결측**: 산업성장·경쟁력·연결실적·가격추세·기관외국인수급. 없으면 N/A/0 *자료 확보 수*이지 기업 점수 0이 아님.
   - 종합점수/PIT 역사적 인증/실전 투자 우선순위 **False/N/A** 강제. 미래 first received·미확인 receipt SHA/현재 DART 매핑 수 오류·성과/리더 승격 변조 등 fail closed. HTML 내 회사명 `escape`하여 XSS 차단.
   - 과거 저장된 `kr_latest.json`에 실적 수치가 없으면 **원본 영수증 2개로 회사 비교 가능 여부만 표시하고 실적 %는 N/A**. 없는 값을 복원했다는 허위 주장 금지.
   - 결정적 `content_sha256` 포함 구조화 JSON + 정적 HTML 모두 새 파일로만 생성 (`O_EXCL`), 원래 raw/API 키/종목 원장은 수정·복사하지 않음.
3. 기존 `run_official_research` 마지막 단계에 **실제 자료 충족도 페이지**를 붙이고 새 사이트의 `index.html`·`kr.html`에서 연결:
   - `site/factor_readiness_kr.html`
   - `factor_readiness_kr.json`
   - 기존 순위/상태 `WATCH`/3개 기간별 보고·알림 미리보기는 그대로.
   - 기존 `official_kr_daily_pipeline.capture_and_publish_kr_day`는 비공개 임시 폴더에 전부 만들고 최종 atomic rename하므로 새 페이지도 같은 원자적 게시 경로를 따른다.

## 재현 및 실물 화면

- 네트워크/API HTTP 추가 호출 **0**, 사전에 T5DATA `output/official_api_capture`에 비공개 보관했던 공인 첫 receipt SHA, DART full day manifest SHA와 금융 원본 2개를 다시 직접 읽고 검증.
- 실제 신규 출력 (Git ignored):
  `/Volumes/T5DATA/eraleader/output/official_core_factor_20261013_v2`
- 새 별도 로컬 미리보기 접속: `http://127.0.0.1:8766/factor_readiness_kr.html`, 기존 가격 순위 `http://127.0.0.1:8766/kr.html`. 기존 8765 대시보드와 다른 research 출력이며 실시간 주문/매수 신호 없음.
- 실제 출력 및 CLI 구조에서 `krx_rows=2765`, `dart_full_rows=992`, `dart_financial_comparable_companies=1`, `financial_comparables_not_in_price_top=1`, `reports=3`, `messages_sent=0`, `official_leaders=0`, 새 `kr.html`로부터 별도 실적 페이지 링크 PASS.

## 테스트 및 제약

- 신규 `tests/test_official_factor_readiness.py`: 정상 최초 SHA/공식 관측수·현재 DART 매칭·재무 외부 TOP20 분리·HTML escaping·idempotency·fail-closed·미래 데이터/과거 소급·잘못된 100점 승격·중복/비정상 가격행·CFS 증거 연도 오류·SHA 조작 방어.
- 기존 `tests/test_official_api_pit_bridge.py`에 PRICE TOP1 밖 CFS 성장 기록 보존→별도 factor page/수치+클릭 링크+원래 가격 1위 불변 E2E synthetic 추가.
- `PYTHONPATH=src python3 -m pytest tests/test_official_factor_readiness.py tests/test_official_api_pit_bridge.py tests/test_official_api_capture.py tests/test_official_dart_corp_directory.py tests/test_official_dart_daily.py tests/test_official_dart_financials.py tests/test_official_kr_daily_pipeline.py tests/test_official_sec_pit_features.py tests/test_research.py -q --tb=short` ⇒ **9개 영향범위 모듈 총 129/129 PASS EXIT0**.
- 이 단계는 전체 수천 pytest·20거래일 전향적 성능·적중률 인증이 아니다. 과거 "API 제외 99%"는 *전체 실사용 완성률 지표에서 철회*. 기업 전체 산업/수급/3년 실적가속까지 실제 투자우선순위에 연결된 상태가 아니라는 사실을 계속 정량적으로 표시한다.

## 후속 단일 개발 타깃

**1순위:** DART 사업보고서 원본/정정 시점별 PIT 및 3개 연속 사업연도 성장 가속을 수집·검증하여 *가격순위와 독립적인* 실제 실적 후보 스크린을 확장. **2순위:** 한국 시장 산업/기관·외국인 수급 공식 데이터 정규화, 미국 전체시세/기업 class 증거 확보. **3순위:** 전체 5요소의 공통 인증 기준·100점 가중치와 후보 최초 관측시각·연속 일별 통합, 전향적 검증. 종합점수는 *모든 필수 지표가 독립 시점 검증될 때만* 산출. 아직 전략 주문/알림 전송 금지.

## 폴더 작업 유의사항

이 세션 확인 시 앞서 만들었던 `/Volumes/T5DATA/EraLeader_통합관리`가 **실제 SSD에서 보이지 않았으며** 기존 5개 다른 worktree가 Git 기준 `prunable`로 표시됐다. 다른 사용자/세션 작업물을 임의 정리·재설정·prune하거나 복구하지 않았다. 이번에는 안전한 독립 새 작업 공간 `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013`에 분기했고 원래 `/Volumes/T5DATA/eraleader`의 미커밋 6+1줄 패치(기존 SHA `6d3139f0...`)를 수정·stage하지 않았다. 이 Git worktree 경로/백업 복구 상태는 뒤이어 별도 확인할 필요가 있다.
