# 182 — 최신 KR 시장자료→5요소 입력→WATCH→일일 보고→대시보드 단일 운영 명령

**2026-10-14 KST · 개발ID 3_4·4_1·6_2·6_3 · 작업 브랜치 feature/kr-marketwide-search-20261014**

## 새로 작동하는 기능 (실사용 경로, 기존 정상 모듈 재사용)
- **입력**: `--marketwide-source-root`에 저장된 공식 KRX/DART `marketwide_kr.json`, 프로젝트 내부 `output/partial_factor_inputs`에 저장된 날짜·시장원본 SHA가 맞는 5요소 부분 평가 자료. 추가 옵션 `--marketwide-watch-dart-cfs-root`는 기존 개인 비공개 DART 연간 CFS 원본(읽기 전용)만 활용.
- **처리**: 기존 `scripts/render_local_operations.py`에 **`--marketwide-watch-auto` 옵션 한 개 추가**, 이미 구현된 `refresh_latest_marketwide`, `factor_selection_pipeline._read_assessment/_validate`, `derive_partial_factor_input`, `publish_early_watch`, `publish_daily_brief`, `publish_operations_overview`의 정상 기능만 **순차 재사용**한다. 동일 시장원본 SHA·관측일에 유효한 기존 5요소 평가 500행/실적·수급 포함 자료를 선택; 같은 행수면 기존 실적·수급 커버리지가 더 큰 판본 우선. 아직 전혀 평가 입력이 없을 때만 **기존** 가격+실적 PARTIAL을 원천에서 자동 생성. 실제 공식 출처가 오래됐거나 없는 경우에는 `NO_FRESH_VERIFIED_SOURCE`로 보류하고 기존 WATCH·보고·대시보드 화면을 변경 없이 보존.
- **출력**: 최신 WATCH 후보 중립 JSON+HTML → 동일 WATCH SHA와 당일 KST가 일치하는 읽기 전용 **일일 재무 관찰 보고서 JSON+HTML** → 운영 대시보드 링크까지 한 명령으로 완성. 기존 `--marketwide-watch-queue-input`/ `--watch-daily-brief-manifest` 수동 모드와 충돌을 피하며 예전 CLI 사용법은 그대로 유지. 데이터가 10월13일 시장일인데 보고일이 10월14일이면 명확히 구분하고 오늘 새로운 대장주 상태강화/이탈 사건을 만들어내지 않는다. 외부 시장 API **0회**, 실주문/브로커 권한 **0**, 특정 전략 수신 프로젝트 지정/전달 없음.
- **대표 명령**:
```bash
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
 --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
 --marketwide-watch-auto \
 --marketwide-watch-dart-cfs-root /Volumes/T5DATA/eraleader/output/official_api_capture
```
- **실물 T5DATA E2E** `output/verification_logs/marketwide_auto_operating_e2e_20261014.json`: `_FLOWV1_` SHA-검증된 기존 500행 평가 자동 선택 → WATCH **50개** (실물 2024~2025 DART 수익성 비교 **46개**) → 일일 보고 **50개**, 개선24·악화22·미비4 → 운영 메인/WATCH 상세/보고서 상세 모두 local HTTP **200**. 모든 단계 반복 `ALREADY_PUBLISHED`로 기존 SHA 증거 불변. 원시장일 `2026-10-13`과 보고발행일 `2026-10-14` 구분. 리더 확정0/거래주문0/추가 API0.
- **변경 부분 집중 테스트**:
```bash
PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest \
 tests/test_operations_one_command_auto_watch.py tests/test_marketwide_auto_refresh.py \
 tests/test_early_leader_watch_queue.py tests/test_early_watch_daily_brief.py \
 tests/test_operations_overview.py -q --tb=short \
 --junitxml=output/verification_logs/one_command_watch_scope_20261014.xml
```
  **69 PASS, 0 FAIL/ERR/SKIP, EXIT0**. 정상 1명령 결과, 기존 시점·SHA 일치 수급 입력 우선, 새 일자 입력 없을 때 기존 PARTIAL 자동 생성, 데이터가 2영업일+ 오래됐을 때 신규 신호 보류, 원천 누락 보류, 수동/자동 혼합 잘못 사용 차단, 멱등 재실행 확인. Python compile, Git diffcheck PASS.
- **범위·보존**: 원본 `/Volumes/T5DATA/eraleader`·CycleOS/SharedBrokerAPI 코드/원시데이터 수정0. 이 개발 시작부터 같은 feature 브랜치에서 이미 다른 작업자가 미커밋한 `AGENTS.md`, `DECISIONS.md`, `PROJECT_STATE.md`, `START_HERE_NEXT_CHAT.md`, `docs/150_REAL_USE_ACCEPTANCE_POLICY.md` 변경은 **이번 커밋 대상에서 제외**, 원래 내용 그대로. 현행 증거는 본 새 `docs/182`에 독립 기록.
- **인수 구분**: 코드 기능/테스트 완료, 실제 저장시장자료 end-to-end 완료, 스케줄러/매일 무인 실행 실제 설치 및 외부 알림은 **별도 운영·출시 인수 전**. 고정 12개 항목 진행률 **API 연동 제외 약67% 유지**(완료5·부분6·미구현1) — 무인 실행·업종 성장20/경쟁력20 정식 점수는 아직 미완, 이번 수동 한 명령 완성만으로 자동운영 전체완료라고 승격하지 않는다.
- **다음 핵심 개발**: 동일 기존 파이프라인에 새 공식 일자 KRX/DART 캐시가 추가되면 자동 입력·후속 정식 경쟁력 요소를 갱신하고, 승인된 실제 산업 성장성20·기업 경쟁력20 채점 규칙/원천 공급자 연결을 구현. 중복 WATCH 비교엔진/검수 시스템 확대는 하지 않는다.
