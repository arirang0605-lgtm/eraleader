# 165 — 최신 KR 가격 WATCH 연구 이력과 중립 JSON 송신 연결

- 기준: **2026-10-14 KST**, 개발 ID **4_1·4_2·4_3·6_4**. `feature/kr-marketwide-search-20261014`의 기존 정상 코드만 CONTINUE.
- 목표: 직전 최신 KRX 검증본 검색/가격 WATCH20/중립 JSON 송신 단계에 기존 **`StateHistory` 연구 원장**을 opt-in 연결. 전체 5요소가 충족되지 않았으므로 **POTENTIAL/CONFIRMED/WEAKENING의 정식 상태 전이는 아직 아님**.

## 재사용 / 실제 변경

1. 다른 완료 브랜치 `feature/core-official-factor-coverage-20261013`에서 이미 검증한 `src/eraleader/official_watch_state_bridge.py`를 **원본 SHA 동일하게 보존하며 선택 재사용**. 정상 `StateHistory.record`, `strategy_handoff.marketwide_research_handoff`, SHA 기반 시장전체 검증과 `KR_PRICE_OBSERVED:코드` 식별자를 그대로 사용.
2. `marketwide_handoff_bridge.publish_latest_marketwide_handoff(...,record_watch_history=True)`: 새 소스 SHA와 시장 관측일/price WATCH20 재검증 → 독립 `output/official_price_watch_state_history.sqlite` (owner only)에 연구 WATCH 이력 기록 → 기존 불변 source-versioned JSON outbox 발행. 동일 거래일 가격 WATCH는 중복 기록되지 않으며, 다른 날짜는 시점 순서대로 누적. 빠진 TOP20 구성원을 자동 `EXITED`로 처리하지 않음. 가격 관찰 ID는 영구 회사 ID가 아님.
3. 운영 CLI `scripts/render_local_operations.py --marketwide-source-root ... --marketwide-publish-outbox --marketwide-record-watch-history` 명시 opt-in. 옵션 단독 사용 거부, 기존 기본 로컬 운영/기본 중립 JSON/사전 생성된 launchd 시간 설정은 변경하지 않음. CLI 결과는 `marketwide_watch_state_status`, `marketwide_watch_state_rows`, `marketwide_verified_leader_events=0`, `marketwide_handoff_orders=0`.
4. **실제 Mac T5DATA SQLite 버그 수정**: 다른 브랜치에서 복사된 기존 구현은 `StateHistory(path)`로 파일을 먼저 열고 `chmod(0600)`을 뒤에 호출해 T5DATA 실제 볼륨에서 열린 SQLite 연결이 `attempt to write a readonly database`로 실패. 실제 owner-only 파일모드가 0700인 macOS SSD 동작을 확인. `os.open(O_EXCL|O_NOFOLLOW,0600)`으로 신규 원장 파일을 **먼저 안전 생성한 뒤** `StateHistory`를 여는 최소 수정으로 해결. 정상 WAL/원장/후속 StateHistory 구현 재작성 없음. 이미 열린 파일 chmod 금지 회귀 테스트 추가.
5. 원본 `/Volumes/T5DATA/eraleader`의 사용자 미커밋 `native_first_capture.py`와 문서 및 사용자 PNG/MD, 다른 Feature worktree 원시 API/SQLite, 외부 MarketOS·NewsCatalystOS·후속 전략 코드는 읽기전용 또는 변경0.

## 실제 보관 데이터로 검증

- 독립 격리 연구원장 `output/verification_logs/actual_kr_watch_sequence_20261014/official_price_watch_state_history.sqlite`에 **기존 KRX 2026-10-08 WATCH20 → 2026-10-13 WATCH20** 순서로 등록: 총 `state_history` **40행**, `WATCH` **40건**, 상태전이 이벤트0, 확정/추천/주문0. 기업 동일성/기간 누락/진짜 상폐/실제 PIT 신호는 인증 N/A.
- 운영 출력의 별도 최신 연구원장 `output/official_price_watch_state_history.sqlite`: 2026-10-13 WATCH20 / 이벤트0, 동일 명령 반복 실행 **idempotent**. 본 개발 디버그 중 생성한 빈 진단 테이블은 검증 후 안전 정리, 원래 시장/계좌 DB 미수정.
- 실제 운영 CLI `python3 scripts/render_local_operations.py --project "$PWD" --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' --marketwide-publish-outbox --marketwide-record-watch-history` → exit0, WATCH20·선정0·주문0·원장 중복0. 기존 `output/strategy_outbox/KR_20261013_a59b7ecdfaa0b707.json` SHA/선정0 검증, 외부 recipient 연결0.
- 변경 영향 `PYTHONPATH=src python3 -m pytest tests/test_marketwide_handoff_bridge.py tests/test_state_history.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_live_search.py tests/test_strategy_handoff.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/marketwide_state_history_final_20261014.xml` **97 PASS, failures0/errors0/skips0**, Python 컴파일 및 git diffcheck PASS. 실제 SQLite readonly 실패→원인 재현→수정→실 T5DATA 40행 정상 재검증 PASS.

## 다음 핵심 구현

- 공식 가격 WATCH 이력과 **추가 5요소**의 실제 동시점 평가 자료 결합. 특히 독립기업 ID, 경쟁력/산업성장 점수, 투자자수급의 동일거래일·매매권한 분리, 역사 PIT 충족 여부가 보류.
- 완전한 근거가 확보된 종목에만 기존 `evaluate_leader_state` + `StateHistory`의 `POTENTIAL → CONFIRMED → WEAKENING`을 활성화하고 프로젝트 중립 JSON `selected_candidates`/전이 상태를 갱신. 실제 수급1/2요소38의 가격중심 WATCH를 **투자 1~20위로 홍보하지 않음**.
- 본 브랜치 결과는 원본 `main`에 자동 병합하지 않음. 외부 수신전략 시스템 선택·실거래 기능은 범위 제외.
