# START HERE — EraLeader 현재 작업 재개 (2026-10-14)

> **이 문서는 현재 기준·최신 확인 증거·다음 구현 작업만 포함합니다.** 과거 세션별 로그와 상세 진행경위는 `PROJECT_STATE.md` 및 Git 이력에 보존되어 있으므로 **전부 읽지 마세요**. 구버전 이 문서(약 918줄)의 완전한 원본은 `git show fa83e658:START_HERE_NEXT_CHAT.md`로 복원 가능합니다. 원본 SHA256: `a26014b198ad9c783fd503a5ea8509d139ceeaca5ee3bceae16d985b5437cbbb`.

## 1. 사용자 최상위 기준 (D-032)

- **실사용 완성 우선.** 한국·미국 대장주 입력→조기 발굴/WATCH·선정·약화·교체 처리→프로젝트 중립 JSON 및 웹 화면·보고·알림 등 **누락된 실제 기능을 최우선 구현**합니다. 검수·관리 도구를 늘려 기능을 대신하지 마세요.
- **사용자 승인 없는 신규 필수 검증/출시 게이트 승격 금지.** 이미 승인된 범위·기존 완료조건 유지. 검증마다 실제 증거가 맞으면 통과하는 **정상 경로**를 설정합니다. 변경 관련 테스트와 대표 실자료 실행만 수행하고, 원인·증거가 그대로인 차단을 반복 점검하지 않습니다.
- **보고는 3단계로 분리:** (1) 구현·변경 영향 테스트, (2) 실자료 입력→처리→출력 실행, (3) 운영·출시 설치/인수. 외부 승인·공급자 자료·경과시간의 대기는 **그 업무에만 적용**하고 독립 기능 구현은 계속합니다.
- **불변 안전 경계:** 비밀키·원본/사용자 미커밋 보호·공식 source SHA·기업/주권 식별·PIT/미래정보 누출/데이터 날짜·실주문 안전. EraLeader **매수·매도 주문 미구현/개발대상 제외**. 선택 종목을 받을 프로젝트는 **아직 지정되지 않았고** EraLeader는 중립 JSON만 발행합니다. 실적/산업/경쟁력 근거 없는 종목은 WATCH/N/A 유지.
- **최종 보고 첫머리:** 새로 작동하는 기능 또는 해소한 실행 장애 → 관련 테스트·실자료 실행 여부·Git SHA·남은 조건/다음 기능 → **API 연동 제외 실제 운영 개발 진행률**.

## 2. PC/파일/Git 현재 상태

- 원본 프로젝트: `/Volumes/T5DATA/eraleader` (원래 main의 `src/eraleader/native_first_capture.py`, `PROJECT_STATE.md`, `DECISIONS.md` 등 **미커밋 자료·공시 참고 PNG가 있음** — 절대 덮어쓰기/스테이징 금지).
- 실제 최근 독립 작업트리: `/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014`.
- 분리 브랜치: `feature/kr-marketwide-search-20261014`; 이 기준 수정 직전 마지막 확인된 정상 SHA `fa83e65865416ef46f48299a09497d2ad8819a06`. **새 대화에서는 현지 `git status --short --branch`와 `git log -1`을 단 1회 확인해 최신 SHA를 따르세요.**
- 공개 GitHub: `arirang0605-lgtm/eraleader`. 비밀키·원본 시장데이터·SQLite·개인 데이터는 커밋하지 않음. 이미 테스트된 정상 코드는 재작성하지 않음.
- `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine`과 `/Volumes/T5DATA/SharedBrokerAPI`는 기존 정상 기능 **재사용/read-only**, MarketOS·NewsCatalystOS 등과 직접 연결 확정 금지.

## 3. 현재 재현 가능한 최종 증거

- 한국 공식 KRX 2026-10-13 시장 관측 2,761종목, 부분 5요소 입력500 (가격500/실적38/키움 데모 날짜별 기관·외국인 수급 연구3). 산업 성장20·기업 경쟁력20은 공식 정식 점수 미구현, 정식 리더 확정0.
- **최신 실물 작업** `docs/178_KR_DART_SECTOR_PEER_METRICS_WATCH_FEED_20261014.md`: 기존 KRX/DART 관측 자료로 WATCH 50종목의 세부업종 표본 매출성장 비교 **20종목**, 영업이익 상대 비교 **16종목**을 계산하여 중립 JSON·HTML에 연결. 현재 판본 `output/early_leader_watch_queue/KR_20261013_0933ebaddb43934c/{watch_queue.json,index.html}`; 같은 입력 반복 `ALREADY_PUBLISHED`, 선정·주문0. 부분표본 관찰이며 공식 산업성장20·기업경쟁력20 점수는 아직 N/A.
- 마지막 변경 영향 `output/verification_logs/sector_peer_operable_scope_20261014.xml`: **51 PASS / FAIL0 / ERR0 / SKIP0**. DART 동업종 표본의 positive/결측 사례와 실물 JSON/HTML/로컬 HTTP 200까지 검증. 앞서 정상 수급·WATCH 단계의 구 증거는 기존 Git·PROJECT_STATE·관련 MD에만 보존.
- **API 연동 제외 실운영 기능개발률 약67%**: 12개 운영 흐름, 완료5·부분6·미구현1, 동일 가중 `(5 + 6×0.5)/12 ≈ 67%`. 과거 코드 기준 98~99%를 실운영 준비율로 사용하지 마세요. 공식 발굴 적중률/PIT 장기 인증/전체 출시 인수는 별도 미완.

## 4. 바로 다음 하나의 구현 작업

**다음 구현**: 새 세부업종 표본 기반 WATCH 실물 경로를 보존하고, **실제 확보 가능한 공식 업종 전체 성장 수치 또는 기업 시장점유율·현금창출/ROIC 등 경쟁력 원시 자료 중 하나를 기존 입력→처리→WATCH·중립 JSON으로 연결**합니다. 아직 확보되지 않은 요소는 N/A로 두되 나머지 WATCH 운영을 차단하지 않습니다. 검증 도구를 추가로 증설하지 말고 실제 데이터 필드를 노출·처리할 수 있는 기능부터 이어갑니다.

- 먼저 현재 작업트리의 SHA·dirty·해당 공식 자료 1~2종만 확인하고, **자료가 실제 존재하는 가장 짧은 새 필드 입출력 경로**부터 구현. 자료를 구할 수 없는 하위업무만 WAIT로 표기하고 독립 기능은 계속.
- PASS 경로: 저장된 공식 원본·기업ID·수신시각을 충족한 기업 1개 이상에서 **새 실제 기능의 입력→계산→WATCH JSON·화면** 성공. 결측 N/A, 미래시각/다른 기업 데이터 거부. 원본/미커밋 변경 금지.
- 테스트/인수: 바뀐 Python 집중 테스트만 실행·수정 후 재실행하고, 새로 작동한 기능 먼저 최종 보고. 기능·실자료·운영 출시 각각 결과 구분. 정책문서만 수정한 경우 무관한 전체 pytest 불필요.

## 5. 최소 읽기 순서

1. 연결 및 현재 Git + dirty 보존 확인.
2. **이 문서** → `AGENTS.md` 첫 최상위 D-032 → `DECISIONS.md` **D-032, D-030, D-028** → `PROJECT_STATE.md` **마지막 최신 섹션만**.
3. 이번 구현과 관련된 코드·`docs/177_KR_OPERABLE_EARLY_LEADER_WATCH_QUEUE_20261014.md`를 필요한 범위만 읽고 바로 CONTINUE. 과거 918줄 인수 문서/717KB 상태 이력을 통째로 반복 읽지 않음.

## 2026-10-15 현재 최신 작업 — 공식 KRX 증분 갱신·예약 WATCH 연결

- 기능 커밋 492839584d4baa013d1300c5e5339470451e6c39, 현 브랜치 그대로. 기능·변경 영향 71 PASS, 상세 docs/184_KR_OFFICIAL_INCREMENTAL_WATCH_DAILY_20261015.md. 이전 4절의 다음 작업보다 이번 요청의 증분 경로를 우선 확인.
- scripts/run_marketwide_daily.py가 새 마감일 KRX pair → 기존 부분5요소/WATCH·일일 보고·웹 경로를 실행. 공식 수신은 --apply-official, 기본은 저장본만 사용. 새 캡처는 이 feature/output/official_api_capture, 기존 main 캡처와 CycleOS는 read-only.
- 실물 10/14 양시장0행, 관측시장일10/13 유지·새 WATCH 지연 HOLD. 당일 재실행API0 정상. 새 평일19:40 plist 준비·직접 실행exit0, 실제 launchd 미설치.
- 바로 다음 확인은 공급자 실제 최신 행 반환 시 정상 실자료 갱신→WATCH·일일 보고 발행. 날짜가 바뀌기 전 같은0행을 반복 조회하지 않음. 재무/업종은10/13 검증 캐시이며 신규 공시 갱신 아님, 다른 일자 수급 N/A.
- 공개 코드/정제문서 push는 자동 승인검토의 공개범위 승인 미확인으로 보류, 사용자 확인 요청. 기존 dirty 정책문서와 원본 main 사용자 변경 보존. API 제외 약67% 유지.

## 2026-10-15 현재 최신 기능 — WATCH 연간 현금창출 관찰

- 새 로컬 기능 커밋6202311b92c884dad4b6af8387134757741c620d, 31개 변경 영향 테스트PASS, docs/185_KR_DART_CASHFLOW_WATCH_OBSERVATIONS_20261015.md. 이전 증분 기능4928395/상태68724f5는 사용자 승인 후 공개 push 성공.
- publish_watch_cashflow.py는 기존 KRX/DART/보관 WATCH를 읽어 별도 JSON·HTML 보고/대시보드 링크를 발행. 보관시장일10/13·분석일10/15를 구분. WATCH50 중 CFO46/취득후잔여현금42, 원본/이전WATCH 불변, API0·주문0·HTTP200.
- 금일 시세·신규 WATCH 또는 완전 FCF/경쟁력20점으로 주장하지 않음. KRX10/14 양시장0행 대기는 그대로이고 반복조회하지 않았다. launchd 실제서비스 미설치, API 제외 약67% 유지.
- 새 현금흐름 커밋의 공개 push는 자동검토가 기존 사용자 승인을 이전 두 커밋으로 한정하여 거절. 추가 코드/정제문서 공개 승인이 필요하며 재시도 금지. 로컬 기능은 완성·검증되어 사용 가능.

## 2026-10-15 현재 최신 연결 — 현금흐름을 기존 WATCH·일일 보고에 추가

- 코드 SHA a8e248cb91ffbebf697aadabaff6c9acb4bb5168, 51개 직접 영향 테스트PASS. docs/186_KR_CASHFLOW_FIELDS_WATCH_DAILY_BRIDGE_20261015.md 참고. 기존 공개 HEAD d7562df까지 승인/푸시된 상태 유지.
- publish_watch_cashflow.py --connect-watch: 기존 검증 현금흐름 판본 재사용→CFS 기업/연도/원본SHA·수신시각 확인→기존 WATCH50 중립 JSON/HTML 필드 부착→일일 보고50. CFO46/잔여현금42, 세 화면HTTP200·반복ALREADY_PUBLISHED·원본/목록 불변·API0.
- 보관시장일10/13과 원본 WATCH 최초 시각을 유지. 새 부착판/보고의 실제 생성시각은 따로 기록, 새 선정·상태전이·완전FCF/경쟁력20·정식100점으로 주장하지 않음.
- 다음: 정상 새 시장자료 기반 WATCH 생성 시 현금필드를 일상 자동 경로에도 부착. KRX10/14 0행 재조회 및 launchd 설치는 이 작업에서 수행하지 않음. API 제외 약67% 유지. 새 연결 코드 공개 범위는 기존 승인된 두 커밋 밖이므로 승인 전 push하지 않음.
