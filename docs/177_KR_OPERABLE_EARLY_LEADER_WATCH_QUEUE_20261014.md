# 177 · 실제 한국 대장주 우선관찰 50종목 큐 / receiver-neutral JSON (2026-10-14)

개발 ID: 3_4·4_1·4_2·6_2. 분리 브랜치 feature/kr-marketwide-search-20261014.

## 실제 신규 기능
- `early_leader_watch_queue.py`, `scripts/publish_early_leader_watch.py`: 기존 SHA-봉인 KRX 2,761종목 전체시장 관측과 시장일·실제 평가시각이 맞는 부분 5요소 데이터 최대 500개를 사용. 별도의 후보 WATCH 검토 우선목록 기본 50종목을 자동 생성한다. 외부 API 0, 직접 주문 0.
- 운영 검토 등급 A=가격+실적원본 연구 38종목, B=가격+키움 수급 연구3, C=가격 Top20 중 나머지6, D=그 밖의 가격 관측453. 실제 출력 상위50은 A38+B3+C6+D3. 가격·실적·수급은 이미 저장된 점수와 증거만 재사용. 산업 성장20/기업 경쟁력20은 현재 출처 부족으로 미산출.
- Tier 내 관측점수로 자료검토 순서 정렬. **투자 1~50순위 또는 매수추천/정식 대장주 선정 아님**. 기존 시장 원본 `earnings_research_25`와 `two_factor_research_50` 일치도 재검증. 단계 상태 자동 승격·원장 수정 없음.
- 기존 `render_local_operations.py --marketwide-source-root <reports> --marketwide-watch-queue-input <SHA-verified factor file> --marketwide-watch-queue-top 50` opt-in. 기존 `operations_overview.py`에 검증한 최신 URL 링크 추가. 중립 JSON은 `receiver_project=null`, `selected_candidates=[]`, `formal_leader_selection_count=0`, `order_instruction=false`, `execution_authority=false`, `watch_only=true`, `orders_enabled=false`. 후속전략 연결 대상 미지정. 이 자료를 자동매매 주문으로 해석 금지.
- owner-only immutable 보관 `output/early_leader_watch_queue/KR_20261013_c29ba0bf7695e6c0/{watch_queue.json,index.html}`, 기존 입력 sourceSHA와 factorSHA/top 수 기준 동일 재실행 `ALREADY_PUBLISHED`. 변경된 원본·위조 SHA/HTML·미래판정/시장지연 방어.
- 실제 Mac SSD KRX 2026-10-13, watch후보 500개에서 WATCH 50개 생성, 대시보드 링크와 JSON 실물 열람/반복 CLI 통과, 실거래0. 산출 근거 `output/verification_logs/early_watch_ops_real_20261014.json`, `early_watch_real_cli_20261014.json`.
- 변경영향 검증: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_early_leader_watch_queue.py tests/test_official_partial_factor_bridge.py tests/test_factor_selection_pipeline.py tests/test_marketwide_live_search.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_handoff_bridge.py tests/test_operations_overview.py tests/test_marketwide_flow_research_score.py tests/test_operations_dated_flow_all_stocks.py -q --tb=short --junitxml=output/verification_logs/early_watch_operational_scope_20261014.xml` → **142 PASS, failures0/errors0/skips0**. `py_compile`, diffcheck, 실제 운영 로컬 HTML/JSON 확인 성공.
- 원본 main의 user-uncommitted native_first_capture.py·PROJECT_STATE/DECISIONS와 공시분류 참고 이미지, SharedBrokerAPI/MarketOS/NewsCatalystOS/원시데이터 변경 0. Git Public에 비밀키/개별 캡처/SQLite/output 산출물 업로드 금지.

## 개발 진행률: API 연동 제외 **실운영 기능 구현 약67% (기준 고정)**

과거 98~99%는 기존 로컬 코드/검증모듈 구현 기준이며 **실제 운영 완성률과 다름**. 이번부터 12개 실제 운영 흐름마다 완료1, 부분0.5, 미구현0으로 동일 가중: 완료5 + 부분6×0.5 + 미구현1 = 8/12 = 66.7%, 반올림 **67%**.

- **완료 5:** KR 공식 시장관측, 가격 상대강도/WATCH 탐색, 이번 후보50 WATCH 큐, 후속전략 중립 WATCH JSON, 로컬 웹 대시보드/검색.
- **부분 6:** 미국 최신 전체시장 발굴, DART 재무 전시장 커버리지(현재49), 기관외국인 수급 종목 확대(현재 정밀3), 실제 후보 POTENTIAL/CONFIRMED/WEAKENING 전환(현물 WATCH만), 정기 무인 수집/실행(명시 opt-in), 일·주·월 운영보고/외부 알림(부분 로컬).
- **미구현 1:** 실데이터 기반 산업 성장성20 및 기업 경쟁력20 정식 요소와 전체 5요소 실제 선정 통합.
- 이 67%는 사용자 요청한 **API 연동 제외 실제 운영 기능 구현 추정치**이며, 시장예측 성능·공식 PIT 인증·실거래 승인률은 아니다. 매 작업 최종보고에 산정기준과 진행율을 표시한다.

NEXT: 산업 성장20·기업 경쟁력20 실제 독립 원천 연결과 데이터 증분 갱신을 우선. 정상 코드 재작성 금지.
