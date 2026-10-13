# ER-NC-06 — 뉴스 ↔ 시장반응 양방향 분석 (2026-10-13)

**상태: 구현 및 변경 영향범위 자동 테스트 PASS / 연구용.** NewsCatalystOS 수집기·기사 원문·LLM 분류·실제 주문 기능을 EraLeader에 중복 구현하지 않는다.

## 인계·백업/원본 보존

- 기존 주 저장소 `main` 기준 `a24400237f6a454b788ed1802ff6859c6a7a5c66`; ER-NC-B00 실제 T5DATA + Mac 별도 실패 도메인 AES 암호화 백업, 파일 SHA/SQLite 273개/독립 복원 및 smoke EXIT0 검증 완료.
- 기존 ER-NC-00~05 기능 작업트리 `feature/er-nc-20261013` (`bbe9be5`)의 미추적 `news_market_response.py`를 1:1 사본으로 복제하여 **새로운 별도** `feature/er-nc-06-complete-20261013`에서 CONTINUE. 원래 파일과 기존 `main`의 `native_first_capture.py` 미커밋 수정 7줄 편집/커밋하지 않았다.
- 개인 키/원시 뉴스 기사/재배포 비허용 기사/비공개 운영 DB를 Git에 추가하지 않는다.

## 실제 추가 기능

- `src/eraleader/news_market_response.py`: 기존 미완성 소스의 세 연구 API를 이어 완성.
  - `diagnose_news_market_response`: PIN된 현지 뉴스 snapshot의 verified/invalidated 버전과 당시 가격 관측의 최초 이용가능 시각 비교. 원시 뉴스 내용을 출력하지 않고 이벤트 ID/진단/품질사유만 반환.
  - 결과 후보: `positive_news_positive_price`, `positive_news_negative_price`, `repeated_news`, `strong_price_no_verified_news`, 기본 `stale_or_unknown`. 시장반응 동행은 매수·상승 인과의 증명 아님.
  - 원본 이벤트 record SHA256 재계산, 별도 `issuer_id`와 `issuer_mapping_available_at` 계약, 수혜 미확정 연결 제외, 실시간 이후 공시·늦은 검증·무효화·정정대기 분리. 각 뉴스의 사용 가능 시각은 timezone-aware UTC로 비교하고 ISO 문자열 시간대 정렬 오류를 제거.
  - `strong_price_no_verified_news`는 **사용자가 독립적으로 확인한 동일 SHA PIN**(`trusted_coverage_sha256`)과 news source의 coverage witness·당시 이용가능시각이 모두 맞는 로컬 범위에서만 연구 표시. 임의 뉴스 부재를 세계 전체 뉴스 부재로 인증하지 않는다.
  - `make_anomaly_news_query` + `LocalAnomalyQueryCache`: 특정 종목 또는 테마/기준시각/이상유형/최대 30일 관측창의 결정적 요청 ID·중복0 추적, 네트워크 검색·API·뉴스 수집 0건. 호출자가 입력 payload를 수정해도 캐시 불변.
  - 임계값 `abs(excess_return_pct)>=8.0`, `turnover_multiple>=2.5`, 동행수익률 `±3.0`은 **미검증 설명용 실험값**, 종목 선정점수·자동매수에 영향 없음.
- `scripts/run_er_nc06_research.py`: 별도 독립 source SHA 입력 필수, 기존 `NewsCatalystEvents.load` read-only → PIT `snapshot(as_of)` → 가격 대비 뉴스 진단 → 로컬 anomaly request → JSON(stdout). 허가권 없는 뉴스 전문, 외부 API, 실거래 호출·파일 덮어쓰기 전부 없음.
- 기존 WATCH/score/state/official KRX·DART·SEC/paper/서버·보고 코드 수정 **0파일**; NEWS_ENABLED OFF 기존 실행 경로는 그대로.

## 검증 증거

- **새로운 집중 모듈 42/42 PASS + 실행 CLI 4/4 PASS = 46/46 PASS, EXIT0.**
- 기존 `test_news_catalyst_adapter.py`, `test_news_rotation_context.py`, `test_theme_lifecycle.py`, `test_watch_rotation.py`, `test_market_regime_experiment.py` 포함 7개 모듈 **합계 156/156 PASS, EXIT0**.
- 재현: `PYTHONPATH=src python3 -m pytest tests/test_news_market_response.py tests/test_er_nc06_cli.py tests/test_news_catalyst_adapter.py tests/test_news_rotation_context.py tests/test_theme_lifecycle.py tests/test_watch_rotation.py tests/test_market_regime_experiment.py -q --tb=short`.
- 대표 결함 차단: 무효화 정정이 예전 호재로 남는 문제, 사후 뉴스 소급, 같은 발행사의 다른 share class 추정, `POTENTIAL` 수혜를 확정 취급, 서로 다른 뉴스 timezone 문자열 정렬, 가격 이후 검증/최초수신 구분, 증거 SHA 위변조, 간접 진단을 실거래 명령으로 오인, 독립 뉴스 부재 증거 없을 때 UNKNOWN, 로컬 요청 ID 변조/중복.
- E2E 합성 JSONL→local CLI 결과 구조, 연구용 설명·실제 주문0·원 기사 URL 출력0 확인. 공식 뉴스 원본의 독립 최초공개/PIT 적격성/과거 실시간 재현·미래 주도주 precision@K/lead-days는 **N/A**. 전체 pytest(수천 건) 재실행은 뉴스 확장 통합 수락 ER-NC-10에서 **한 번** 하도록 유예.

## 운영 차단 및 다음 작업

- `strong_price_no_verified_news`는 엄격히 *공급자 및 시간창 범위에서 찾지 못함*을 의미한다. 진짜 포괄적 뉴스 커버리지 인증과 독립 SHA PIN 보관 체계를 준비하기 전에는 OFF.
- 본 CLI는 수신 뉴스가 없거나 원문 권리가 없을 때 확정 주도주 추천으로 승격시키지 않고, 실패 시 명시 EXIT2.
- 다음 ER-NC-08: 기존 local HTML + 일/주/월 보고서 + DRY-RUN 알림에 위 뉴스·테마 자료를 `NEWS_ENABLED` opt-in으로 **읽기 전용 추가**, 원래 점수/기존 URL/API 호출 유지.
- 별도 ER-NC-07 저자 4전략의 *원문 근거 검증 완료*는 아직 NOT_READY이며, 규칙 수치 임의 확정 금지. 전략별 매수·매도 신호·백테스트 인증은 별도 검증.
