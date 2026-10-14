# 179 — DART 연결재무 2025 실물 수익성 → 대장주 WATCH 50종목·중립 JSON

**2026-10-14 KST | 개발ID 3_4·4_1·4_2·6_2 | feature/kr-marketwide-search-20261014**

## 실제 신규 사용 기능
- **핵심 입력**: 기존 T5DATA owner-only `/Volumes/T5DATA/eraleader/output/official_api_capture`의 OpenDART 회사식별자 원본 zip 영수증 및 개별 연결재무(CFS) 연간사업보고서 `dart_fin_*/{first_receipt.json,raw_response.json}`. 기존 `official_dart_corp_directory.verify_dart_corp_directory`·`official_dart_financials.parse_dart_financial` **재사용**. 외부 DART API 0회.
- **처리**: 신규 `dart_profitability_watch.dart_annual_margin_context`에서 회사식별자 현재 DART 매핑을 최초 SHA/UTC 기준으로 **한 번** 확인하고, 선택 가능한 각 회사의 최근 연차 연결 `CFS/11011` 첫 수신 원본 SHA·회사코드·회계연도·회계양식/관측시각·수신금액을 검증. 분모 매출액>0일 때 **영업이익률=영업이익/매출액×100, 순이익률=순이익/매출액×100** 산출. 계정·분모 누락이나 기업 매핑 부재면 N/A. 기업별 원본 중복은 동일연도 **최초 수신** 우선. 원본 raw 또는 기존 모듈을 덮어쓰지 않음.
- **출력**: 기존 `early_leader_watch_queue.py`의 WATCH 50 및 수신자 중립 `watch_queue.json`에 최근 연결재무 회계연도·매출/영업익/순이익 KRW·두 마진(%)·원본 receipt SHA·원본 로컬 수신 UTC·DART 회사ID를 필드로 합침. 기존 `index.html`에는 **DART 연결재무 실적 수익성 관찰** 표 추가. CLI `publish_early_leader_watch.py --dart-cfs-capture-root <old private receipts>` 및 `render_local_operations.py --marketwide-watch-dart-cfs-root <old private receipts>` **명시 opt-in**으로 전 단계 WATCH 우선순위·선정·PIT·직접주문 분리 유지. 기존 default 명령 및 전판 JSON/HTML 변화 없음. 신규 receipt SHA 기반 버전만 추가 발행.
- **점수 승격 없음**: 영업이익률·순이익률은 현재 CFS 원본에 있는 실자료지만 **ROIC·시장점유율·지속경쟁 해자/공인 경쟁력20점이 아니므로** `competitive_advantage_score_20=None`, 공식 industry20/competitiveness20= N/A, `selected_candidates=[]`, `orders_enabled=False`. 현재 사업연도 수신시각 이후 관찰이며 과거 장중 이용가능 PIT로 소급하지 않음.

## 실제 T5DATA E2E
- 원본 CFS 2025 연결 연차 관련 62개 주권 원본 중, 현재 확인된 DART issuer 매핑과 매출 분모/이익 수치가 활용 가능한 **53기업** 수익성 정보를 계산; 현재 WATCH 50종목 중 **46종목**의 실제 CFS 마진 출력.
- 실제 2025년 DART 연결재무 마진: SK하이닉스 영업 **48.5928%**/순익 **44.2093%**, 삼성전자 **13.0696%**/**13.5510%**, 저스템 **9.5981%**/**7.1574%**, 대덕전자 **4.6054%**/**4.4687%**, 빛샘전자 **7.4380%**/**6.3925%**. 새 KRX 가격 관측소스 2026-10-13과 2025 회계연도 시점을 명확히 구분.
- 파일은 기존 개인정보·API키·원시재무를 Git에 올리지 않고 `output/early_leader_watch_queue/KR_20261013_e1bcd6007379751e/{watch_queue.json,index.html}` (ignored) 불변 새 판본으로 저장. 최초 발행 `output/verification_logs/dart_annual_profit_watch_real_20261014.json`; 운영 opt-in `output/verification_logs/dart_annual_profit_watch_ops_20261014.json` EXIT0, 기존 운영대시보드가 새 버전 JSON 링크를 표시. 로컬 127.0.0.1 메인/상세 GET 200.
- 집중 테스트: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_dart_profitability_watch.py tests/test_early_leader_watch_queue.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/dart_cfs_profitability_scope_20261014.xml`: **56 PASS, FAIL0/ERROR0/SKIP0**. 정상 파일 연결/임의 누락값 N/A/미래 수신일 거부/반복 실행 동일 버전/기존 큐 보존/로컬 CLI opt-in 확인. Python compile, public staged safety, git diffcheck 확인.
- 사용자 동시 수정 감지: 현재 feature 브랜치의 `AGENTS.md`, `DECISIONS.md`, `PROJECT_STATE.md`, `START_HERE_NEXT_CHAT.md`, `docs/150_REAL_USE_ACCEPTANCE_POLICY.md`가 작업 시작부터 **미커밋 수정 상태**. **해당 파일은 본 작업에서 읽기만 하고, 이번 커밋에 포함하지 않음**. 재개 기록은 이 신규 docs/179에 독립 보관. 원본 main `native_first_capture.py` 포함 기존 미커밋·참고이미지 변경0.

## 3단계 상태·진행률
- **기능 구현/테스트**: CFS 영업·순이익률 → WATCH JSON·HTML 경로 PASS.
- **실자료 증빙**: 기존 개인 DART first SHA로 53기업/우선 50 중 46기업 PASS.
- **운영·출시 인수**: 로컬 opt-in 조회/표시 가능; 정기 무인 실행·외부 알림/전략 수신자 연동 및 정식 기업 경쟁력20점은 별도 미완. 외부 대기 때문에 이번 독립 기능을 막지 않음.
- **API 연동 제외 개발률 약67% 유지**: 승인 고정 12운영 흐름 완료5·부분6·미구현1 = (5+6×0.5)/12. 수익성 관찰 필드가 새로 동작하지만 경쟁력20점/시장점유율/전체 정식5요소는 미완이므로 12번째 항목 완료로 임의 승격하지 않음.
- **바로 다음 실제 개발**: 올해·직전년의 같은 DART CFS 원본으로 **영업이익률 변화/수익성 지속성**을 WATCH에 증분 노출하거나 공식 시장점유율/ROIC 출처 확보 시 기존 입력→관찰/중립 송신 경로에 연결. 새로운 관리·검수 도구 확장보다 기능 우선.
