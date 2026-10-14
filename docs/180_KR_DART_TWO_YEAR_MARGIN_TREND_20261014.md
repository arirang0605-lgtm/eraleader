# 180 — DART 2개 연도 영업이익률 변화·흑자 지속성 실물 WATCH 기능

2026-10-14 KST · 개발 ID 3_4·4_1·4_2·6_2 · feature/kr-marketwide-search-20261014

## 새로 작동한 기능
- 기존 `dart_profitability_watch.py` 연간 CFS 원본 조회 기능을 그대로 확장. 소스는 원래 owner-only `/Volumes/T5DATA/eraleader/output/official_api_capture`의 최초 DART 발행사 디렉터리 및 개별 사업보고서 본문. 같은 주권·같은 연결재무 보고서·서로 연속한 회계연도에 대해 **영업이익률/순이익률 전년 대비 변화(pp), 2년 연속 영업이익률 양수 여부**를 계산. 매출 >0인 경우에만 분모 사용. 현재 연도만 보이면 전년도/N/A, 여러 원본 버전이 있으면 해당연도 최초 수신본 우선. 정상 DART 회사ID·원본 SHA/UTC/보고서 양식 검사 재사용. 신규 API0·원본 변경0.
- 기존 `early_leader_watch_queue.py`의 WATCH 목록 50개·수신자 중립 `watch_queue.json`에 `dart_previous_cfs_business_year`, `dart_previous_cfs_operating_margin_pct`, `dart_cfs_operating_margin_change_pp`, `dart_cfs_net_margin_change_pp`, `dart_cfs_operating_margin_positive_two_years`, 양년도 원본 SHA·수신일을 추가하고 HTML에 수익성 변화 열을 표시. 현행 `dart_profitability_method` V2는 과거 V1과 별도 **불변 새 SHA 판본**으로 발행, 과거 판본은 유지. 기존 A/B/C/D 검토 우선순위 미변경. PIT 인증/정식 경쟁력20점/매수신호/직접주문 없음.
- 해당 데이터가 없는 회사는 이전 WATCH 자료를 그대로 보여주고 신규 변경필드는 N/A 처리. 외부 특정 후속전략 수신 프로젝트/계좌 미지정 유지. 오래된 정식 선정/상태원장 변경0.

## 실자료/실행 근거
- 기존 공식 KRX 2026-10-13 관측 및 SHA 검증된 5요소 부분 입력500, 로컬 WATCH50, 2024~2025년 DART CFS 연속 원본(최초 실제 수신 2026-10-14). 53개 현재 연간 수익성 관찰 기업 중 WATCH 내 **46개 기업의 2024~2025년 영업이익률 변동값**과 영업흑자 지속성 계산 성공. 새로운 원본 API 호출/데이터 다운로드0.
- 수익성 예: SK하이닉스 영업이익률 2024 **35.4529% → 2025 48.5928%, +13.1399%p**; 삼성전자 **10.8771→13.0696%, +2.1925%p**; 저스템 **-11.9095→9.5981%, +21.5076%p (2년 연속 흑자 아님)**; 대덕전자 **1.2621→4.6054%, +3.3433%p**.
- 기존 실행 CLI `python3 scripts/publish_early_leader_watch.py --project <WORKTREE> --marketwide-report <SIGNED_KR_SOURCE> --factor-input <SIGNED_5FACTOR_PARTIAL> --top 50 --dart-cfs-capture-root /Volumes/T5DATA/eraleader/output/official_api_capture`, 운영 CLI `render_local_operations.py --marketwide-source-root <SOURCE_ROOT> --marketwide-watch-queue-input <FACTOR_INPUT> --marketwide-watch-dart-cfs-root /Volumes/T5DATA/eraleader/output/official_api_capture` 기존 옵션만 사용.
- 새 파일 `output/early_leader_watch_queue/KR_20261013_f5a3041ca5838fd2/{watch_queue.json,index.html}` (Git ignored). 운영 대시보드 최신 링크/재실행 `ALREADY_PUBLISHED`; 실제 `output/verification_logs/dart_cfs_two_year_watch_real_20261014.json`, `dart_2y_margin_operations_20261014.json` 모두 성공. 기존 V1 보고서 보존.

## 변경 테스트 / 출시에 대한 구분
- 기능·변경 범위 테스트: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_dart_profitability_watch.py tests/test_early_leader_watch_queue.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/dart_2y_margin_impact_20261014.xml` → **60 PASS, FAIL0/ERROR0/SKIP0, exit0**. 실증 가능한 정상 경로(2024/2025 동일회사 수익성 차이 +10pp), 전년도 없음 N/A, 미래원본 차단, 원본변조 거부 등을 포함. 이미 통과한 전체 2000개 회귀 반복 불필요.
- 실자료 E2E: 2026-10-14 실제 DART first receipt와 기존 KRX source를 연결해 WATCH 50개 중 46개 결과 성공; SHA 버전별 원본 보존 및 로컬 운영 페이지에서 정식 선정0/주문0 유지.
- 무인 운영/출시 인수: 별도 대기. 정식 산업성장20·기업 경쟁력20의 증빙/선정모델은 이번 기능 범위 밖. 최신 사용자 D-032 정책에 따라 신규 검증을 사용자 승인 없는 필수 완료조건으로 추가하지 않음.
- 본 개발 시작 시 동시 수정 중이던 `AGENTS.md`, `DECISIONS.md`, `PROJECT_STATE.md`, `START_HERE_NEXT_CHAT.md`, `docs/150_REAL_USE_ACCEPTANCE_POLICY.md`는 **원상 보존, 이번 커밋에는 포함하지 않음**. 이번 기능 이력은 docs/180에 별도 기록.
- API 제외 실사용 개발률은 고정 12개 항목 기준 **67% 유지** (완료5/부분6/미구현1; 경쟁력 정식20점과 전체 자동선발 아직 미완).
