# PROJECT_STATE — 실제 작업 상태

## 최상위 목표 (2026-10-10 사용자 명시적 교정)

**미래 대장주를 조기에 발견하는 능력의 구현·실운영이 최종 목적. 과거 데이터와 백테스트는 그 능력의 작동 여부를 검증하는 수단**이다. 개발/모델 성능 평가에서 이 두 역할을 절대 바꿔 말하지 않는다.

## 최신 스냅샷 — 새 대화 기준

> 2026-10-10 KST. 이 절이 현재 상태의 단일 기준(SSOT)입니다. 아래 이전 기록은 작성 당시의 역사적 상태입니다.

- **현재(2026-10-10 최신)**: 기존 1~6 로컬 기초 통합 + 2_2·2_3 오프라인 PIT/3_1~3_3 산업·실적 피처에 이어 **3_4·3_5 가격·재무·산업 시점 결합, 4_2~4_5 상태·이벤트 이력(합성 검증), 5_2 조기 발견 리드타임/오탐 계산기, 6_2 통합 연구 웹페이지** 추가. **전체 pytest 54개 PASS, 로컬 e2e 및 한국·미국 실제 캐시 배치 PASS**. 5_3 워크포워드 분리/6단계 KR+US 배치 추가; `docs/30_WALKFORWARD_LOCAL_BATCH.md` 참고. 실전용 완전한 PIT·검증된 미래 대장주 성능·전체 30개 작업 완성은 **미완료**. 상세 `docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md`.
- **테스트 근거**: marcap 1995~2026 연도별 Parquet 32개 / 15,648,407행 메타데이터 대조 PASS. 005930 2025년 1월 18거래일 로컬 캐시 조회 PASS. 기존 미국 업종 모멘텀 계산 실행 PASS. **투자 성능·PIT 적합성 검증은 아님**.
- **Git 상태(2026-10-10 최신)**: 사용자 **Public GitHub 업로드 승인**. 로컬 origin을 `https://github.com/arirang0605-lgtm/eraleader.git`에 연결해 **최초 main push 성공**, 초기 원격 체크포인트 `eb439ba`. `.secrets/`는 owner-only이며 Git ignore. 이후 커밋·추가 push 상태는 이 파일 하단 최신 기록 참고.
- **기존 재활용**: `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine` 읽기 전용, `/Volumes/T5DATA/backtestengine`은 확인 당시 빈 폴더. 분할·배당·상폐·공시 이용시각·라이선스 추가 검증 필요.
- **다음 작업**: `docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md`. **2_2/2_5 역사적 상폐·기업행동/종목군 품질 강화, 4~5 실제 자료 PIT/워크포워드, 6단계 로컬 자동운영·대시보드·보고/복구성**. 모든 미완료 항목을 1_1~6_5로 관리하고 추가 승인 요청 없이 계속 개발. 외부 API는 로컬 기능 마무리 뒤 연결.
- **재개 순서**: `START_HERE_NEXT_CHAT.md` → `AGENTS.md` → 상태 상단 → 관련 상세 MD 1~2개. 기존 코드 무단 재작성, 반복 전체 대화 분석 금지.

---

## 이전 시점 기록 (최신 상태를 덮어쓰지 않음)

- 기준일: 2026-10-10 (KST)
- 저장 경로: /Volumes/T5DATA/eraleader
- 현재 단계: P0 — 설계·요구사항 Markdown 기록
- 문서 작성 상태: 이 문서와 docs/ 아래 명세 작성 중
- Git 저장소: **이 SSD 폴더에서는 아직 확인된 Git 초기화/커밋 없음**
- 실전 데이터 연결: **미구현/미검증**
- 산업·기업 점수 프로그램: **이 폴더에서 구현 여부 미확인**
- PIT 백테스트: **이 폴더에서 미구현/미검증**
- 대시보드: **미구현**
- 알림·보고서: **미구현**
- 외부 MarketOS 연결: **미구현(선택 사항)**

## 확인된 로컬 환경

- 연결 PC: SHMOONui-MacBookAir.local (macOS)
- T5DATA 외장 SSD: /Volumes/T5DATA 마운트 확인
- 이 폴더: 최초 점검 시 빈 폴더
- Python 버전: 3.12.7 확인
- 존재가 확인된 다른 프로젝트 경로:
  - /Volumes/T5DATA/CycleOS-Lab_BacktestEngine
  - /Volumes/T5DATA/backtestengine
  - /Volumes/T5DATA/marketos
- 위 폴더들의 실제 소스/API 호환성은 **아직 점검하지 않음**.

## 이전 대화에 나온 결과에 관한 주의

이전 대화에서 EraLeader v0.1 ZIP 시제품과 가상 데이터 8개 테스트 통과가 언급되었다. **이번 SSD 폴더에 그 코드/테스트 산출물이 있다고 확인된 것은 아니다.** 파일 확보 후 실제 테스트로 재검증할 것.

## 다음 작업 — 실행 우선순위

1. 문서 작성·정합성 검사 완료.
2. 사용자 승인하에 독립 Git 저장소(Private) 생성/연결. 기존 다른 프로젝트는 수정하지 않음.
3. 기존 v0.1 원본을 확보할 수 있으면 무변경으로 가져와 실행·테스트·버전 기록. 없으면 이 문서를 바탕으로 최소 코드 골격 구축.
4. /Volumes/T5DATA/CycleOS-Lab_BacktestEngine 과 /Volumes/T5DATA/backtestengine 을 **읽기 전용으로** 점검 후 범용 엔진 재사용 가능성 결정.
5. 실제 데이터 1개 소스 → PIT 보관 → 최소 점수 → 소규모 검증 → 결과 저장까지 일관 동작시켜 첫 MVP 구축.
6. Git 체크포인트와 PROJECT_STATE.md를 결과 기반으로 갱신.

## 차단/미결정 사항

- 데이터 공급자 이용 승인 및 API 인증정보(실제 수집 시 필요)
- 미국 장기 시세·상장폐지 자료의 공급 범위 및 비용
- 과거 실적 컨센서스 이력: 선택적 유료 데이터, 없이도 제한적인 MVP 가능
- 외부 서버·알림 채널·로그인 방식: MVP 이후 확정
- 과거 백테스트 엔진 호환성: 코드 점검 필요

## 최종 완료 기준

상세: docs/10_TEST_ACCEPTANCE.md
'완료'는 UI 시연이 아니라 실제 데이터 수집부터 후보 생성/검증/화면/알림/보고까지 자동 실행한 증거가 있는 경우에만 사용.

## 추가 문서화 기록 (2026-10-10)
- `docs/13_DATA_COLLECTION_IMPLEMENTATION.md`: 주가·재무·산업/거시·공시/뉴스 데이터별 공식 수집 출처, PIT, 비용·단계별 구축 명세를 **문서로** 저장함.
- `EraLeader_데이터수집_전체구조도.{svg,png}` 및 `render_data_collection.py`: 데이터 수집 구조도와 재생성 스크립트를 보존함.
- **이번 기록은 설계·자료 작성이며 실제 API 호출·백테스트·운영 기능 구현으로 간주하지 않음.**


## 2~6단계 구체 개발 문서화 결과 (2026-10-10)

- \`docs/14_STAGE2_PIT_DATA_ENGINE.md\`부터 \`docs/18_STAGE6_DASHBOARD_ALERT_REPORT.md\`까지 **단계별 상세 개발 명세 5개 신규 작성**.
- \`docs/19_STAGES_2_TO_6_INDEX.md\` — 전체 단계별 자료 수집·입력, 코드 목표, 결과, 테스트 및 PNG/SVG 찾아보기.
- \`EraLeader_2단계_...\` ~ \`EraLeader_6단계_...\` PNG/SVG 각 1장(총 10개)와 \`EraLeader_2-6단계_통합구조도\` PNG/SVG(2개), \`render_stages_2_to_6.py\` 생성.
- 실제 SSD 원본 파일 존재, SVG XML 파싱, PNG 크기·내용을 검증함. 아래 추가 검증 기록 참조.
- **실제로 개발된 분석·백테스트·대시보드 프로그램은 아직 이 폴더에서 확인되지 않았으며 문서/그림 작업만 완료됨.**
- 다음 단계는 P1 독립 코드 골격 및 P2/PIT 최소 코드를 검증하는 것. 5단계의 백테스트 기초를 PIT 구현 직후 조기 구축하는 사용자 확정 원칙 유지.

## 2~6단계 파일 검증 (2026-10-10)
- 신규 개발 상세 MD 5개, 문서 인덱스 1개, 파일 무결성 보고서 1개를 생성함.
- 개별 PNG 5개+통합 PNG 1개, 개별 SVG 5개+통합 SVG 1개: 실제 저장 확인.
- PNG 6개 전부 2300×1380, SVG 6개 XML 파싱 정상, README/인덱스의 상대 링크 오류 0개.
- 검사 보고서: `docs/20_STAGES_2_TO_6_VALIDATION.md`.
- **검사한 것은 문서·그림 파일이다. 실제 기능 구현 및 전략 성능은 미검증 상태 유지.**

## 전체설계도 세부 번호 일원화 및 그림 정리 (2026-10-10)
- 새 통합 전체설계도: `EraLeader_전체설계도_1-6단계_세부번호.png` / `.svg` (1_1~6_5, 총 30개 작업 ID).
- 상세 개발 번호표: `docs/21_MASTER_ARCHITECTURE_NUMBERING.md`.
- 중복 이미지 삭제 기록: `docs/22_IMAGE_CLEANUP_LOG.md` (구형 그림 7개 삭제).
- 유지한 그림: 최신 통합 1장, 1단계 상세 1장, 2~6단계 상세 5장, 각각 PNG+SVG(총 14개).
- 옛 합본을 재생성하지 않게 개별 상세도 생성 스크립트 호출 변경, README/인덱스 링크 갱신.
- 문서·그림 정리 완료이며 실데이터 API 및 발굴/백테스트 코드 완료로 해석 금지.

## 기존 로컬 백테스트 자산 점검 (2026-10-10, 사용자 요청)

- \`/Volumes/T5DATA/backtestengine\`: 빈 폴더로 확인.
- \`/Volumes/T5DATA/CycleOS-Lab_BacktestEngine\`: 활용 대상. 기존 소스 **수정 없이** 데이터·코드 확인.
- \`datasets/external_validation/marcap/data\`: 32개 연도별 Parquet(1995~2026), 파일 메타데이터 합계 15,648,407행이 원본 검증 요약과 일치. 원 검증 요약의 종목코드 수 6,953, 날짜 최대 2026-10-02. 가격조정/PIT 적격성은 미검증.
- 미국 S&P500 주봉 901,171행, NASDAQ100 주봉 153,582행 등의 기존 로컬 데이터를 확인함. 구성 종목군 시점 편향 주의.
- **재사용 테스트 실행 PASS**: \`scripts/verify_backtestengine_reuse.py\` -> \`results/reuse_probe/local_assets_audit.json\`.
- **실제 기존 전략 스모크 실행 PASS**: \`tools/backtest_mvp/grid_mom_rotation.py\` 단일 설정 -> \`results/reuse_probe/sector_mom_baseline_one_config.csv\`. 모멘텀 업종 baseline 연산 결과이지 투자/주도주 검증 아님.
- 재사용 점검 상세: \`docs/23_BACKTESTENGINE_LOCAL_REUSE.md\`.
- **다음 단계:** 기존 marcap/미국 자료를 읽기 전용으로 사용하는 EraLeader 어댑터 구축→최초 종목/기간 최소 재현→PIT 공시·기업행동 보완→기존 baseline과 신규 발굴 점수 공정 비교.
- 외부 백테스트 폴더의 로직·데이터·Git 상태는 이번 작업 중 변경하지 않았음.

- **첫 기존 데이터 연결 테스트 PASS:** \`scripts/read_cached_marcap.py\`가 외부 \`marcap-2025.parquet\`에서 005930의 2025-01-02~01-31 **18개 거래일**을 실제 조회. 인터넷·원본 복사 없이 \`results/reuse_probe/marcap_sample_query.json\` 저장. 이는 read-only 가격 조회 최소 어댑터이며 PIT 적격성은 미검증.

### 최신 추가 증거: 새 대화 인수인계 자동 점검
- `scripts/check_handoff.py` 최초 실행 **PASS**, 필수 14개 파일, 1_1~6_5(30개), 통합 그림 3240×2600, 전체 PNG 7장/SVG 7장, 손상된 링크/누락 파일 0개.
- 새 대화에서는 이 스크립트 1회 실행 후 `docs/25_NEXT_IMPLEMENTATION_SPRINT.md`의 가장 첫 미완료 개발 작업부터 진행.
- 이 PASS는 문서·연동 경로/기존 재사용 **기초 증거 존재**에 대한 검사이며 PIT 완성/대장주 검증 성공은 아님.

## 목표 역할 정정 기록 — 2026-10-10

- 사용자 명시적 교정: **최종 목적=미래 대장주를 조기에 발견하는 능력의 구현과 실운영**. **과거 데이터와 백테스트=그 능력이 당시 알 수 있던 정보로 작동하는지 검증하는 수단**.
- 변경 문서: `README.md`, `START_HERE_NEXT_CHAT.md`, `AGENTS.md`, `DECISIONS.md`, `PROJECT_STATE.md`, `docs/00_VISION_SCOPE.md`, `docs/04_BACKTEST_VALIDATION.md`, `scripts/check_handoff.py`.
- 실제 검증: `python3 scripts/check_handoff.py` → **PASS**, 필수 14개 파일, 고유 작업번호 30개, 구조도 PNG 7개/SVG 7개, 오류 0개.
- 미해결: 아직 실제 미래 발굴 엔진 및 PIT 통합 장기 성능 검증은 미구현; 역사적 성능도 미래 탐지 능력을 보장하지 않음.
- 다음 개발: `docs/25_NEXT_IMPLEMENTATION_SPRINT.md`에서 첫 미완료 코딩/PIT 테스트부터 진행. 이 목적 정의를 신규 알고리즘·사용자 화면·사후 성과 검증의 상위 기준으로 유지.
- Git: 독립 저장소 미초기화/커밋 없음.

## GitHub 저장소 실확인 및 인수인계 지침 업데이트 (2026-10-10)

- GitHub 커넥터로 `arirang0605-lgtm/eraleader` 실제 생성 확인; 기본 브랜치 `main`, size 0, PUBLIC, 계정에 admin/push/pull 권한 있음.
- 로컬 SSD `eraleader/.git` 없음. Git 원격 연결·코드 업로드는 아직 수행하지 않았으며, 공개 저장소 상태에서 임의 push하지 않음.
- 변경 파일: `README.md`, `AGENTS.md`, `PROJECT_STATE.md`, `DECISIONS.md`, `START_HERE_NEXT_CHAT.md` 및 신규 `docs/26_GITHUB_REPO_HANDOFF.md`.
- 테스트: `python3 scripts/check_handoff.py` → PASS, 필수 14개 파일·30작업ID·그림 PNG/SVG 각각 7개, 오류 0개; README/START_HERE 내부 링크 오류 0개.
- 미해결: GitHub 공개/비공개 설정 사용자 확인 필요; 이후 로컬 초기화·`.gitignore`/비밀정보 검사·remote 연결·최초 commit/push.
- 다음 작업: 기존 데이터 우선 재사용하면서 P1 로컬 독립 Python 패키지와 PIT 최소 구현 진행, Git 보안 설정은 최초 commit 이전에 처리.
- Git 커밋/푸시 정보: 없음(실행하지 않음).

## 로컬 우선 개발 첫 통합 실행 결과 — 2026-10-10

**개발 목표 변경:** 사용자 결정에 따라 외부 API 연결은 나중으로 미루고 **1~6단계 로컬 작동 기능**부터 만든다. 세부 구현/실행 명령/제약은 `docs/27_LOCAL_FIRST_IMPLEMENTATION.md`.

- **P1 / 1_1·1_5**: `src/eraleader/data.py`는 `CycleOS-Lab_BacktestEngine`의 KR marcap 및 US S&P500 주간 캐시를 **읽기 전용**으로 로딩. 외부 데이터 다운로드 0건.
- **2_1·2_3·2_4(부분)**: 원본 0값 OHLC 거래정지/무거래 자료는 거래 불가능으로 표시·주요 순위에서 제외. 550일 한국 데이터 **1,062,518행 중 정지/무거래 51,213행, 별도 이상 1행**을 발견했고 이상 1행은 격리해 출처·건수를 기록. SQLite PIT fixture의 공시 공개시각/정정 버전·중복 방지 테스트 PASS.
- **3_4·3_5(가격 전용)**: 한국/미국 3·6개월 RS 가격 관찰 점수 및 상위 20개를 생성. 실적/산업 데이터 없어 종합 100점 및 POTENTIAL/CONFIRMED **보류(WATCH)**.
- **4_1~4_5(부분)**: WATCH 이벤트·상태 저장. 미래 PIT 근거가 모두 확보된 경우에만 승격하는 순수 상태 머신을 합성 fixture로 검증(실제 확정 대장주 없음).
- **5_1(연구 baseline)**: t신호 → t+1 수익률 연구용 주간 모멘텀 baseline 실행 성공, 52개 평가기간. 기업행동·시장구성 PIT 및 거래비용 검증 전이므로 결과 수익률 **공식 성과 아님**.
- **6_1~6_5(부분)**: SQLite/JSON 스냅샷, 브라우저용 `output/site/index.html`, KR/US HTML, 상태변경 알림 dry-run, KR 일·주·월/US 주간 Markdown 보고 생성. localhost HTTP 3개 경로 200 확인, 연구용 WATCH 이벤트 44개 중복 없고 재실행 경고 0개.
- **테스트**: `PYTHONPATH=src python3 -m pytest tests -q` → **17 PASS**; `PYTHONPATH=src python3 scripts/verify_local_mvp.py` → **PASS**; `python3 scripts/check_handoff.py` → **PASS**(초기 Git 확인 이전).
- **주요 파일**: `pyproject.toml`, `.gitignore`, `src/eraleader/*.py`, `tests/*.py`, `scripts/verify_local_mvp.py`, `docs/27_LOCAL_FIRST_IMPLEMENTATION.md`. 실행 결과는 **SSD의 `output/`** 아래 저장하며 원격 Git 업로드 제외.
- **Git**: 로컬 `main` 초기화·파일 추가됨. 현재 원격 origin 설정 및 GitHub push **없음** (GitHub가 Public이므로 승인 전 push 금지). 커밋 SHA는 후속 실행 기록에 기재.
- **최우선 다음 작업**: **2_2 역사 종목군/기업행동 PIT 보완 + 3_1~3_3 오프라인 재무·산업 입력 계약**을 구현하고, 4단계 후보 승격을 실제 검증 가능한 PIT 자료로 연결. 사용자의 최종 목표는 미래 대장주 조기 발굴이며 과거는 검증 수단이다.

## 로컬 Git 체크포인트 결과 (2026-10-10)

- Git 초기화: `/Volumes/T5DATA/eraleader/.git`, 브랜치 `main` (독립 로컬 저장소).
- 최초 커밋: `72ef51487d6bd997e819d744fbbc26713f46e6a3` (`feat: bootstrap EraLeader offline local-first pipeline`), **68개 파일** 추적.
- 테스트: `PYTHONPATH=src python3 -m pytest tests -q` → **17/17 PASS**.
- 로컬 통합: `PYTHONPATH=src python3 scripts/verify_local_mvp.py` → **PASS**. 웹 3페이지 HTTP 200, 결과/이벤트/보고 로컬 확인.
- 인수인계: `python3 scripts/check_handoff.py` → **PASS** (작업 ID 30개·PNG 7·SVG 7 정상).
- 개발 출력 `output/`, `results/`, 기존 가격 원시자료, `.env`, 비밀키는 Git 추적 제외. 유출 의심 패턴 4종 확인 결과 매칭 파일 0개.
- **GitHub:** `arirang0605-lgtm/eraleader` 존재, 이전 확인 당시 **Public**; origin 연결/원격 push **미실행**. 공개범위 승인 후에만 연동.
- 다음 미완료 작업: **2_2 역사 종목군·기업행동 PIT / 3_1~3_3 오프라인 재무·산업 시점 자료 수입 및 상태 엔진 연결**. API는 로컬 1~6단계 검증 후.
- 실제 테스트·실행 결과는 SSD의 `results/local_mvp/` 및 `output/`에 보존.

## 이번 개발 실측 기록 (2026-10-10, 2_2·2_3·3_1~3_3)

- 코드 추가: `src/eraleader/offline_pit.py`, `src/eraleader/offline_features.py`; CLI `offline-import`와 `offline-features` 추가.
- 자동 테스트 추가: `tests/test_offline_pit.py`(합성 PIT fixture: `tests/fixtures/offline_synthetic.json`).
- `PYTHONPATH=src python3 -m pytest tests -q` → **33/33 PASS**. 고유 종목/상폐/분할·배당, 출처/시간대, 정정공시 미래 유입 차단, 멱등·충돌 원자성, 산업·실적 성장 계산, 초기 징후와 WATCH 유지 등 포함.
- 실제 명령: `offline-import --file tests/fixtures/offline_synthetic.json`와 `offline-features --market KR --as-of 2024-07-01/2024-09-01` 실행 성공. 출력은 **합성 자료만** `output/demo_offline/`에 별도 보존.
- 예시 SYN-A 매출 YoY 7월 +25% → 9월 +60%, 영업이익 +100%, 산업 매출 +15% (전부 가상 입력; 실제 종목 아님).
- **제약:** 외부 공시 PIT/산업 역사, 기업행동/상장폐지 전체 완전성 미확인으로 종합 점수·POTENTIAL/CONFIRMED 승격 금지. 실전 데이터와 가상 입력 분리.
- 다음: **3_4·3_5 정량 피처 결합 + 4_2~4_5 안전 상태 변경 실연결**, 이후 조기 발굴 성능 검증.
- 상세: `docs/28_OFFLINE_PIT_FEATURE_IMPLEMENTATION.md`; Git 변경 파일·테스트·커밋 SHA는 후속 체크포인트에서 갱신.

## 이번 오프라인 PIT 개발 Git 체크포인트 — 2026-10-10

- **개발 ID**: 2_2·2_3·3_1~3_3 오프라인/PIT 연구용 일부 기능. 공시 공급자·역사 유니버스의 전체 완전성은 별도 검증 필요.
- **변경 파일**: `src/eraleader/offline_pit.py`, `offline_features.py`, `cli.py`, `tests/test_offline_pit.py`, `tests/fixtures/offline_synthetic.json`, `docs/28_OFFLINE_PIT_FEATURE_IMPLEMENTATION.md` 등 총 11개.
- **테스트 명령**: `PYTHONPATH=src python3 -m pytest tests -q` → **33 PASS / 0 FAIL**; `PYTHONPATH=src python3 scripts/verify_local_mvp.py` → PASS(HTTP 200 3경로); `python3 scripts/check_handoff.py` → PASS(필수 19개/전체 30작업 ID).
- **오프라인 예제 실행**: `offline-import` 및 `offline-features`를 2024-07-01, 2024-09-01 기준으로 실행 PASS. 자료는 `tests/fixtures/offline_synthetic.json`의 명시적 가상정보이며 `output/demo_offline/`에 별도 저장, 실제 시장 후보와 혼합 금지.
- **로컬 코드 커밋 SHA**: `14f41f4ef6d38215f085b487d1804dec184f7e6b` (`feat: add offline PIT membership actions and earnings industry imports`).
- **보안**: 커밋된 11개 파일에서 비밀키 패턴 4종 검사 결과 의심 파일 0개. 기존 재사용 SSD 폴더는 읽기 전용이며 수정하지 않음.
- **GitHub**: `arirang0605-lgtm/eraleader`는 마지막 확인 시 Public. origin 연결·push **하지 않음**. 사용자 공개 범위 승인 또는 Private 전환 확인 전 push 금지.
- **미해결 문제**: 과거 상장/상폐와 분할·배당/산업 분류 전 범위 PIT 인증 미완료, 유료 컨센서스 이력 없음, 실제 재무·산업 데이터 연결 없음, 잠재/확정 대장주 생성 불가.
- **다음 첫 작업**: 3_4·3_5 가격 RS/산업/실적 시점 피처 결합 → 4단계 상태/이벤트 게이트 실제 데이터 연동 → 5단계 조기 발견 검증.

## GitHub 최초 공개 push 및 3~6단계 연구 엔진 연동 (2026-10-10)

- **사용자 승인:** Public 저장소 `arirang0605-lgtm/eraleader` 코드/문서 푸시 허용, 인증키 별도 보관, 추가 단계 승인 질문 없이 **6단계까지 개발 지속**. 원시 데이터/API 연결은 로컬 완성 뒤로 연기.
- **최초 원격 push:** `origin=https://github.com/arirang0605-lgtm/eraleader.git`, `git push -u origin main` 성공. 최초 push HEAD `eb439ba` (이전 `5513ffb`, `14f41f4` 등 포함).
- **비밀정보:** `.secrets/` 로컬 생성 `drwx------`, 파일 없음(사용자 키 미제공), `.gitignore`에서 제외; `scripts/check_git_safety.py` staged 검사 0건 의심. 키값 로그/대화/Git에 기록하지 않음.
- **추가 개발 ID:** 3_4·3_5 결합 연구 엔진(`src/eraleader/research.py`), 4_2~4_5 오프라인 상태 변경·불변 이력(`state_history.py`), 5_2 이후 조기 발견 품질 평가 기반(`discovery_metrics.py`), 6_2 산업/실적/가격 통합 연구 HTML(`delivery.py`). CLI `offline-integrated`, `validate-discovery` 추가.
- **실행/테스트:** `PYTHONPATH=src python3 -m pytest tests -q` → **49 PASS**; `PYTHONPATH=src python3 scripts/verify_local_mvp.py` → PASS(HTTP 200 3개); `python3 scripts/check_handoff.py` → PASS. 합성 검증 예시는 첫 발견 1·오탐 1·검증 전 1, **실제 투자성과 아님**.
- **실제 검증 가능한 산출물:** `output/demo_offline/runs/joined_kr_*.json`, `output/demo_offline/site/research_kr.html`, `output/demo_offline/validation_research.json`. 실전용 기업/산업 자료와 분리.
- **미완료:** 실제 공시 PIT/산업원천·상폐·기업행동 총체 검증, 타임머신·워크포워드/홀드아웃/ablation, 라이브 자동 보고·알림, 1~6단계 전체 30개 세부 기능. 최종 목표 미래 대장주 조기 발견 성능은 아직 실증되지 않음.
- **다음 미완료:** `docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md`에 따라 2_2·2_5 PIT 강화 → 4~5 실증/워크포워드 → 6 로컬 자동 운영 검증. 외부 API는 마지막.
- **추가 push 커밋 SHA/결과:** 바로 다음 체크포인트 기록에서 확인.

## 2026-10-10 추가 체크포인트 — 5_3 워크포워드 / 6_1~6_5 로컬 배치 부분 완성

- **변경**: `src/eraleader/walkforward.py`, `src/eraleader/batch.py`, `src/eraleader/cli.py`, `tests/test_walkforward.py`, `tests/test_batch.py`, `docs/30_WALKFORWARD_LOCAL_BATCH.md`. 시점별 오프라인 연구 결과 `state_history.sqlite` 연결·재실행 안정성 보강.
- **검증**: `PYTHONPATH=src python3 -m pytest tests -q` → **54 PASS**. 기존 한국·미국 웹/보고서 회귀 포함.
- **실제 SSD 배치 명령**: `PYTHONPATH=src python3 -m eraleader batch --kr-as-of 2026-10-02 --us-as-of 2026-02-23 --out output/batch_20261010 --top 20 --days 550` → PASS (국가 2개, Markdown 보고서 6개, 신규 WATCH 알림 미리보기 최초 40건). 동일 재실행 → PASS, 신규 알림 0건.
- **워크포워드**: 학습 컷오프 이후 라벨 누수 차단·7일 embargo 등 구조 테스트 PASS. 독립 역사 PIT 백테스트/실전 투자성과는 아직 검증 전.
- **한계**: KR·US 마지막 시세 기준일이 다르며 실시간 아님; 재무·산업 신뢰된 PIT 불완전 → 실제 대장주 확정 0건. 라이브 API/알림 없음. 전체 30개 작업 완성 선언 금지.
- **다음**: 상폐/기업행동 시점별 수익 조정, 실제 오프라인 자료 커버리지, 최종 상태/리드타임 검증, 로컬 일정·복구/운영 품질 (상세 `docs/30_WALKFORWARD_LOCAL_BATCH.md`).
- **Git 후속 SHA/푸시**: 다음 체크포인트 기록에서 확인.

## GitHub 최종 동기화 체크포인트 — 2026-10-10 (54개 테스트)

- **커밋 SHA**: `3993eed440262e4d7aa0a71a6587532522df8712` (`feat: add offline walkforward and KR US reporting batch`).
- **원격 푸시**: `git push origin main` 성공; `git ls-remote origin refs/heads/main` 결과 위와 **일치**. 로컬 `git status -sb` → `## main...origin/main` (동기화됨).
- **테스트**: `PYTHONPATH=src python3 -m pytest tests -q` → **54 PASS**, `python3 scripts/check_handoff.py` → **PASS(필수 31개 확인/작업번호 30개)**, `PYTHONPATH=src python3 scripts/verify_local_mvp.py` → PASS(HTTP 200 3개 경로).
- **공개 푸시 보안**: `python3 scripts/check_git_safety.py` → staged 파일 11개 검사 **의심 0건**. `.secrets/`는 로컬만, 키 미입력.
- **실제 자료 통합 배치**: KR 자료 2026-10-02/US 자료 2026-02-23, 두 시장 보고서 6개 생성 PASS, 재실행 알림 dry-run 0개. 서로 다른 날짜이므로 최신 동일 시점 실전 보고로 취급하지 않는다.
- **다음 개발 승인 재확인 불필요**: 사용자 지시에 따라 추가 질문 없이 코드·테스트 기준 첫 미완료 작업(2단계 상폐/기업행동 PIT 품질 → 4~5단계 미래 발굴 성능 검증 → 6단계 로컬 자동화 완성)을 계속 진행. 단 외부 API는 로컬 우선 개발 후 연결.
