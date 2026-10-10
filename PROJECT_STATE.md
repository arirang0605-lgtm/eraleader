# PROJECT_STATE — 실제 작업 상태

## 최상위 목표 (2026-10-10 사용자 명시적 교정)

**미래 대장주를 조기에 발견하는 능력의 구현·실운영이 최종 목적. 과거 데이터와 백테스트는 그 능력의 작동 여부를 검증하는 수단**이다. 개발/모델 성능 평가에서 이 두 역할을 절대 바꿔 말하지 않는다.

## 최신 스냅샷 — 새 대화 기준

> 2026-10-10 KST. 이 절이 현재 상태의 단일 기준(SSOT)입니다. 아래 이전 기록은 작성 당시의 역사적 상태입니다.

- **현재(2026-10-10 최신)**: 기존 1~6 로컬 기초 통합 + 2_2·2_3 오프라인 PIT/3_1~3_3 산업·실적 피처에 이어 **3_4·3_5 가격·재무·산업 시점 결합, 4_2~4_5 상태·이벤트 이력(합성 검증), 5_2 조기 발견 리드타임/오탐 계산기, 6_2 통합 연구 웹페이지** 추가. **전체 pytest 79개 PASS, 로컬 e2e·한국/미국 캐시 배치·기업행동/종목군 감사·6_5 로컬 백업/무결성 검사/복구 실행 PASS**. 5_3 워크포워드 분리/6단계 KR+US 배치 추가; `docs/30_WALKFORWARD_LOCAL_BATCH.md` 참고. 실전용 완전한 PIT·검증된 미래 대장주 성능·전체 30개 작업 완성은 **미완료**. 상세 `docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md`.
- **테스트 근거**: marcap 1995~2026 연도별 Parquet 32개 / 15,648,407행 메타데이터 대조 PASS. 005930 2025년 1월 18거래일 로컬 캐시 조회 PASS. 기존 미국 업종 모멘텀 계산 실행 PASS. **투자 성능·PIT 적합성 검증은 아님**.
- **Git 상태(2026-10-10 최신)**: 사용자 **Public GitHub 업로드 승인**. 로컬 origin을 `https://github.com/arirang0605-lgtm/eraleader.git`에 연결해 **최초 main push 성공**, 초기 원격 체크포인트 `eb439ba`. `.secrets/`는 owner-only이며 Git ignore. 이후 커밋·추가 push 상태는 이 파일 하단 최신 기록 참고.
- **기존 재활용**: `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine` 읽기 전용, `/Volumes/T5DATA/backtestengine`은 확인 당시 빈 폴더. 분할·배당·상폐·공시 이용시각·라이선스 추가 검증 필요.
- **다음 작업**: `docs/31_CORPORATE_ACTION_AND_UNIVERSE_AUDIT.md` 및 `docs/32_LOCAL_BACKUP_RECOVERY.md`의 첫 미완료 항목. 2_2·2_5 원천 PIT 커버리지/조정가격·상폐 정산 교차검증, 5단계 실제 거래가능성·비용/워크포워드 강화, 6단계 로컬 자동운영·백업/복구. **현재 분할·배당 계산 및 실측 시장 종목군 감사 프로토타입은 구현·테스트 완료(독립 PIT 인증은 아님)**. 모든 미완료 항목을 1_1~6_5로 관리하고 추가 승인 요청 없이 계속 개발. 외부 API는 로컬 기능 마무리 뒤 연결.
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

## 맥북 상시 전원/24시간 개발 요청 운영상태 (2026-10-10)

- 사용자: 맥북 전원 유지, 자리를 비워도 1~6단계 로컬 개발을 최대한 계속 진행, 실제 완료되면 통보.
- 맥북 `codex-cli 0.160.0` 설치 및 ChatGPT 로그인은 확인했지만, **비대화형 codex exec 실제 호출이 사용량 한도로 실패**. 반환 원문: `You've hit your usage limit ... try again at Oct 16th, 2026 6:55 PM`. **그 전 Codex CLI 무한 재시도 금지**.
- 기존 ChatGPT 자동화 `EraLeader 연속 개발`는 **매시간 재개 시도**로 유지 및 해당 한도 반영. 이는 24시간 쉬지 않는 단일 AI 프로세스를 보장하지 않는다.
- 맥북은 AC 연결 시 `pmset`의 시스템 잠자기 설정이 1분이므로, 원격 접근 지속을 위해 `nohup /usr/bin/caffeinate -is` 프로세스를 실행했다. `pmset -g assertions`에서 `PreventSystemSleep=1`, `PreventUserIdleSystemSleep=1` 확인. **덮개를 닫으면 잠들 수 있음**.
- 비대화형 Codex 사용 가능성을 시험했지만 쿼터 한도로 실행되지 않아, 검증되지 않은 24시간 연속 Codex 작업기를 가동한 척하지 않음. 미검증 작업기 초안은 실행/설치하지 않고 제거. 실제 코드와 기존 데이터 변경 없음.
- 현재 검증된 코드 기준은 **pytest 54 PASS**, 마지막 코드·상태 커밋 `509ab24` 및 원격 main 동기화(이번 운영 문서 기록 전 상태). 개발 최우선 미완료 내용은 `docs/30_WALKFORWARD_LOCAL_BATCH.md` 참고.
- 다음 실행: PC 연결 및 Codex/ChatGPT 사용 가능 여부 확인 → 기존 코드·테스트를 이어서 개발 → 실제 검사 통과 시 Public GitHub main에 push 및 결과 기록. API 연결은 로컬 기능 검증 완료 후.

## 개발 이어서 진행한 작업 — 2026-10-10 (2_2·2_5, 5_2 연구기반)

- **이번에 실제 구현**: `src/eraleader/corporate_returns.py` (raw 종가 분할·배당 재구성, 장마감 전에 알 수 없는 종가 접근 차단, 상폐·합병·권리·정지 시 불확실 정산을 0원/0%로 조작하지 않고 fail-closed), `src/eraleader/universe_audit.py` (과거 두 장의 종목 존재/무거래·관측 누락 비교). 독립 실제 소스의 완전성 검증은 여전히 필요.
- **CLI 변경**: `corporate-return` (시점/종목ID/비조정 raw 가격명시·JSON 입력), `audit-universe` (로컬 read-only 가격 캐시 사용). `output/`에 결과 저장, Git 제외.
- **테스트**: `PYTHONPATH=src python3 -m pytest tests -q` → **73 PASS / 0 FAIL** (이전 54 + 기업행동/종목군 안전 검증 19). `python3 scripts/check_handoff.py` → PASS (검사 이전 기존 필수 31개, 이후 신규 파일 추가).
- **실제 로컬 자료 실행**: `PYTHONPATH=src python3 -m eraleader audit-universe --as-of 2026-10-02 --days 35 --out output/research_universe_20261002` → PASS. marcap 자료 2026-10-02 기준 **관측코드 2,873, 거래정지·무거래 플래그 132, 직전 관측일 대비 등장 0/미관측 0**. 상폐·법적 상장 종목수로 단정하지 않음.
- **합성 계산 테스트**: 2:1 분할 및 배당 효과로 '가격 반감 = 수익 -50%'라는 오류 방지, SYN-SPLIT의 3일 구간 raw close 총수익 0% (가상 예제, 실전 성과 아님).
- **현재 제한**: 기업행동 보정 가능 원시가격 완전성, delist proceeds, 역사적 universe 전체 PIT, 공시 이용 가능 시각/최종 모델 실증 부재. 연구용 반환 결과 `pit_certified=false` 강제.
- **다음**: 2_2/2_5 source-level PIT 커버리지 증명 및 상폐 정산/보정가격 교차검증 → 5_2/5_4/5_5 비용/워크포워드/정량 발견성능 → 6_5 독립 로컬 일정 및 복구. 외부 API 연결은 로컬 완성 후, 이번에도 별도 API 호출 0.
- **세부 증거**: `docs/31_CORPORATE_ACTION_AND_UNIVERSE_AUDIT.md`. Git 변경 파일·커밋 SHA·푸시 결과는 이 작업의 최종 체크포인트에서 추가 기록.

## GitHub 동기화 및 6_5 로컬 백업 복구 체크포인트 — 2026-10-10

- **이전 개발 푸시**: `8a25c7112218c831556ca0fb53531320e847a3d3` (`feat: add PIT-gated corporate returns and observed-universe audit`)를 사용자 승인된 Public GitHub `arirang0605-lgtm/eraleader` main에 실제 푸시, `git ls-remote` SHA 일치 확인. 기존 상태 파일의 73개 테스트 기준 코드 포함.
- **이번 추가 개발 ID**: 6_5 로컬 백업·무결성 검사·다른 경로 복구 기능을 `src/eraleader/local_backup.py`, `tests/test_local_backup.py`, `src/eraleader/cli.py`, `docs/32_LOCAL_BACKUP_RECOVERY.md` 등으로 구현.
- **테스트**: `PYTHONPATH=src python3 -m pytest tests -q` → **79 PASS/0 FAIL** (기존 73 + 신규 6). SQLite WAL 미커밋 데이터 제외·복원/해시 검증·민감파일 제외·Zip 경로탈출·덮어쓰기 방지·CLI 회귀 포함.
- **실제 로컬 캐시 출력 복구**: `PYTHONPATH=src python3 -m eraleader backup-local --out output/batch_20261010 --archive output/continuous/eraleader_batch_backup_20261010.zip` → **16개 파일·162,531bytes** 수집; `verify-backup` PASS; `restore-backup --target output/continuous/restored_batch_20261010` PASS(보고서 6/HTML 3). 비밀키와 원시 시세는 archive/Git 모두 제외.
- **PIT/실전 한계**: 역사적 상장·상폐 및 기업행동·조정가격 원본 완전성, 실전 대장주 조기 발굴 성능·엄격한 워크포워드·실전 알림은 아직 미검증. 로컬 API 미연결 유지.
- **다음 미완료 ID**: 2_2·2_5 역사 구성 및 공급자 교차검증 → 5_2/5_4/5_5 정교한 평가 → 6_5 launchd 로컬 스케줄·실패/재부팅 복구 실검증. 상세 `docs/31_...`, `docs/32_LOCAL_BACKUP_RECOVERY.md`.
- **이번 추가 Git 커밋 및 푸시**: 최종 검증 후 SHA/원격 일치 기록을 계속 추가. 인수인계 문서와 Git에 실제 완료 여부를 구분하여 보존.

## 확정 Git 체크포인트 — 2026-10-10 백업·복구 구현 이후

- **로컬 코드 커밋** `0f5e356efde5f612c8967e12dee2f45b47bdc67e` (`feat: add verified atomic local backup and recovery`).
- **GitHub push 성공**: `main` → `origin/main`. `git ls-remote origin refs/heads/main` 반환 SHA와 로컬 HEAD 완전 일치 확인.
- 최종 검증 시점: **pytest 79 PASS/0 FAIL**, 인수인계 필수 40개/작업 ID 30개 PASS, 로컬 웹 3경로 HTTP200 및 e2e PASS, staged 안전 검사 **9개 파일 중 의심 0건**.
- 외부 KRX/DART/SEC 등 실제 API 호출 없음; 인증키·대형 원시 데이터·가상 검증 산출물은 원격 Git 대상에서 제외.
- **다음 미완료**: PIT 원본 기업행동/상폐 정산·기업/산업 공개 시점 완전성, 실제 조기 대장주 발굴 성능, 5단계 장기 워크포워드/강건성, 6_5 일정·휴장/실패 복구. 정상 코드 재작성 금지.

## 2026-10-10 continuation checkpoint — 5_2/5_4 metrics and 6_5 installed macOS scheduled research

- **Starting clean state:** Mac SHMOONui-MacBookAir.local online, /Volumes/T5DATA/eraleader mounted, `main...origin/main`, HEAD `e11858f5b17c71e73d05119c3e87a5130842f9dc`; baseline 79 pytest PASS.
- **Changed**: `src/eraleader/local_schedule.py`, `scripts/run_local_scheduled.py`, `tests/test_local_schedule.py`, `src/eraleader/discovery_metrics.py`, `tests/test_discovery_metrics.py`, `docs/33_LOCAL_SCHEDULER_DISCOVERY_AUDIT.md`; plus these current-state handoff records. Existing normal analysis/pipeline code was preserved.
- **6_5**: Weekend/weekday launchd user agent with fixed provisional 18:10 KST Mon–Fri schedule installed at `$HOME/Library/LaunchAgents/org.eraleader.offline-research.plist`. Initial external-volume working-directory log setup exited 78; corrected launch working directory and logs onto home volume. `launchctl print` then reported **last exit code 0** and automatic `SKIPPED_STALE_CACHE` log. Device must remain awake and mounted; this does **not** run autonomous AI coding.
- **6_5 actual data**: 2026-10-10 local caches KR `2026-10-02` (8d old), US `2026-02-26` (226d old), so default scheduler made no stale live claim. Explicit `--allow-stale-research` full local batch succeeded: KR+US reports 6 Markdown, safe manifest SHA verified ZIP, state checkpoint; repeat `SKIPPED_UNCHANGED_CACHE`. Local outputs under `output/scheduled`, `output/scheduler_control`, `output/scheduler_backups` (Git ignored). API calls 0, messages sent 0.
- **5_2/5_4**: Actual `recorded_at` date now determines historical early-lead credit where supplied; backdated claims no longer earn early-detection TP, malformed timelines rejected; evaluation adds censor/evaluable fraction, unregistered-date count and conservative precision floor. Previous fixture behavior remains research-only. New regression tests include post-hoc signals/future registrations and leader maturity.
- **Tests**: `PYTHONPATH=src python3 -m pytest tests -q` **90 PASS/0 FAIL** (79 prior + 7 scheduler + 4 metrics), `python3 scripts/check_handoff.py` PASS (30 IDs, 40 existing required files), `plutil -lint` PASS, installed macOS agent runtime exit 0; local backup success. Source-level real PIT claims still FALSE.
- **Next work**, in priority: 2_2/2_5 authoritative point-in-time corporate actions, delisting settlement, historic universes and adjusted-price independent comparison → 5_4/5_5 true labeled holdout, lead-time/false discovery validation and ablation → 6_5 real refreshed caches/SSD disconnect and reboot recovery. Offline-only until user-approved API phase.
- **Git SHA and push**: record final post-verification synchronization in the next checkpoint (never invent a commit SHA).

## 2026-10-10 continued source audit checkpoint — 2_2/2_5 (after 6_5 scheduler)

- **Previously verified public GitHub commit:** `40187424836d98ad5eb4a8112f8a207cd2afeabd` synchronized with origin/main, 90 passing tests, installed LaunchAgent exit code 0.
- **New working code:** `src/eraleader/pit_coverage.py`, `src/eraleader/cli.py` `audit-pit-coverage` command, `tests/test_pit_coverage.py` (7), `docs/34_PIT_SOURCE_COVERAGE.md`. PIT ledger membership × cached price observation reconciliation, missing/mismatched/exit/suspension counts, audit-only provenance/coverage; never certifies historic listings using price feed.
- **Tests:** `PYTHONPATH=src python3 -m pytest tests/test_pit_coverage.py -q` **7 PASS**, entire `PYTHONPATH=src python3 -m pytest tests -q` **97 PASS**, no test failures. Synthetic isolated data and existing SQLite fixture used; no external API or paid raw inputs.
- **Still blocked:** authoritative historical issuer registry, exact identity merges, delisting settlements, split/dividend vendor adjusted-price crosscheck and independent PIT financial source. Without these, future-leader discovery quality and full 1~6 completion remain unverified. Next source priority = official PIT universe/action coverage sources when permitted, offline reproducible audit; 5_4/5_5 holdout after trustworthy outcomes.
- **Git commit and remote status**: follow final checkpoint after staged safety scan, commit and remote SHA equality verification.

## 2026-10-10 final verified PIT audit source commit and push

- **Source commit**: `e022d66234f51b2153f3fca4c46902026865ee79` (`feat: audit PIT membership coverage against observed price universes`), `git push origin main` successful; `git ls-remote origin refs/heads/main` returned the identical full SHA. Source test total **97 pytest PASS**, handoff 30 IDs PASS; six staged files scanned by `scripts/check_git_safety.py` with **0 suspected secret files**.
- Previous code checkpoint `40187424836d98ad5eb4a8112f8a207cd2afeabd` remains in history with automated local research schedule and 90 tests. Production leader accuracy or PIT source completeness is not certified.
- Next first genuine unmet task: 2_2/2_5 authenticated historical listing and delisting/corporate-action availability + independent price-adjustment comparison; then 5-stage real prospective lead-time validation; review 6_5 launchd status and logs when the machine reboots.

## 2026-10-10 continuation — 5_4/5_5 prospective-first registration and 6_2/6_5 recovery

- **Starting baseline** `ece0a741215d5dd95e0c18eec6ae7cbc860e05c5` on synchronized clean main; `PYTHONPATH=src python3 -m pytest tests -q` 97 PASS.
- **Code changes:** `src/eraleader/prospective.py` append-only-by-application SQLite `prospective.sqlite` recording actual processing datetime, source PIT as_of, market/security/model/source run, SHA256 immutable input. No future signals, duplicate/mutated replay, input PIT certification or model state promotion. Research hits only, with `historical_backfill` field and real `recorded_at` used for early-discovery metrics. Existing `offline-integrated` now records signal events; new CLI `prospective-signals` exports first registered events. `src/eraleader/delivery.py` adds escaped local `prospective_kr.html`/US audit UI. `src/eraleader/local_backup.py` backs up and restores prospective ledger using SQLite online backup plus SHA ZIP checks. `tests/test_prospective.py`, `tests/test_local_backup.py`, `docs/35_PROSPECTIVE_SIGNAL_REGISTRY.md` changed.
- **Actual tests:** `PYTHONPATH=src python3 -m pytest tests -q` **111 collected/111 PASS/0 FAIL**; `python3 scripts/check_handoff.py` PASS 30 IDs; `PYTHONPATH=src python3 scripts/verify_local_mvp.py` PASS with HTTP 200 index/KR/US, API calls 0.
- **Actually executed** using isolated fake 2024 offline input: `offline-import`, `offline-integrated`, `prospective-signals`, verified backup/restore and exported restored signals. 2024-09-01 observation recorded for first time **2026-10-10** (backfill=true). Replay new records 0; official leaders 0; six-file ZIP verified (input bytes 70441) and recovered same record. Web `site/prospective_kr.html` contains both dates, no certified claims.
- **Next outstanding**: 2_2/2_5 independently verified historical membership, delisting cash, corporate actions and vendor price cross-check; 5_4/5_5 forward frozen holdout with matured real outcomes; 6_5 restart/sleep/SSD loss tests. Input source completeness and real leader accuracy **not** certified, no external API.
- **Commit and push**: see the final verified Git checkpoint that follows. User approved Public code/doc push; secrets and raw data remain Git-ignored.

## 2026-10-10 continuation — 2_5 local total-return series crosscheck

- **Start clean main** `af177dca2eb9d44213b72b2810f5d4554314d859`, previous 111 pytest PASS after prospective audit ledger.
- **Working code**: `src/eraleader/adjusted_crosscheck.py` raw split/dividend total-return vs a separate declared source of total-return-reinvested index, session-by-session divergence, missing/future timestamps and false independent source claims fail-closed; `src/eraleader/cli.py` command `audit-total-return`; `src/eraleader/local_backup.py` safe derived JSON allowlist; `tests/test_adjusted_crosscheck.py`, `tests/test_local_backup.py`, `docs/36_TOTAL_RETURN_CROSSCHECK.md`.
- **Tests**: `PYTHONPATH=src python3 -m pytest tests -q` **131 collected / 131 PASS / 0 FAIL**; `python3 scripts/check_handoff.py` PASS (30 work IDs), local-only actual CLI match/differ/backup/verify checks PASS. This adds 20 new pytest cases (19 reference validation parametrized, 1 allowlist backup) vs 111.
- **Synthetic actual execution**: 2024-04-01 to 2024-04-03 raw 2:1 split+1 cash dividend correctly reconstructed at 0% return; synthetic reference [100,100,100] matched 0 deviations, changed reference [100,100,102] gave one 200bps mismatch. Both `historic_price_actions_pit_certified=false`, independent source certification=false. Derived audit ZIP `output/continuous/return_crosscheck_20261010.zip` one file, SHA verification PASS; original raw input not archived. No live data/API.
- **Next**: independently sourced historical membership/corporate actions/delist proceeds+true adjusted price vendor, PIT data coverage and mature holdout precision/lead-time; existing local agent `launchd` requires mounted SSD, periodic cache still stale. No future leader selection can be certified yet.
- **Git SHA/push**: append separate final verified status checkpoint after `git push origin main` and remote SHA equality test.

## 2026-10-10 verified Git synchronization — 2_5 return comparison

- **Code commit/push** `a7898bc47af6dd4826f8314a7e1cf966c49b4917` (`feat: audit split dividend returns against separate total-return index`); `git push origin main` success and independently queried `git ls-remote origin refs/heads/main` exactly matched full local SHA; branch initially clean.
- **Validation before push**: `pytest 131 collected, 131 PASS/0 FAIL`; handoff PASS/30 IDs, staged public safety scan 8 files and **suspicious 0**. Research return match and 200bps exception both reproduced, API calls 0.
- **Reminder:** synthetic comparison is non-certified; next 2_2/2_5 authoritative historical corp action+listing+delist proceeds and real independent adjusted feed source, then 5_5 sealed forward evaluation. Last 6_5 local scheduled agent runtime evidence remained exit code 0, caches may still be stale.

## 2026-10-10 KST continuation — 2_2 / 2_5 local source-vintage contract, commit temporarily blocked

- **Actual machine**: `SHMOONui-MacBookAir.local` Online/PING PASS, `/Volumes/T5DATA/eraleader` and read-only `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine` accessible. Baseline clean HEAD before this work was `ab6070484f82386d02972a5d4f0e53a92e6e2a92` on synced main. No Codex CLI or external API called.
- **First unfinished local contract delivered**: `src/eraleader/source_vintage.py` + `tests/test_source_vintage.py` + `docs/37_SOURCE_VINTAGE_MANIFEST_AUDIT.md` + surgical `src/eraleader/cli.py` `audit-source-vintage` integration. This audits immutable JSONL SHA256 versus a declared vintage manifest, issuer/event IDs and revisions, timezone-aware `known_at`/`available_at`, a claimed retrieval vintage and decision cutoff. Future revisions are excluded, known superseded revisions collapsed, and post-decision retrievals treated as **retrospective backfill with zero historical as-of coverage**. Official source identity, PIT universe completeness, corporate action/delist proceeds and independent provider availability **remain unverified**; no real future-leader performance is claimed.
- **Actual synthetic smoke**: `python3 output/source_vintage_trial_20261010/build_trial.py` and `PYTHONPATH=src python3 -m eraleader audit-source-vintage --manifest output/source_vintage_trial_20261010/manifest.json --decision-at 2024-04-04T18:00:00+09:00 --out output/source_vintage_trial_20261010` → `RESEARCH_RETROSPECTIVE_VINTAGE_NOT_PIT`, source_count=2, retrospective_source_count=2, historical_pit_certified=false. Trial source inputs, scripts, local JSON and test logs under Git-ignored `output/` only, synthetic data not market results.
- **Test evidence**: local focused `PYTHONPATH=src python3 -m pytest tests/test_source_vintage.py -q` exit=0 (22 cases initially, then 1 further revision-collapse case added); `python3 output/source_vintage_trial_20261010/test_staged_snapshot.py` extracted original HEAD + **only the four proposed source-vintage paths** and ran full pytest in isolated checkout → **154 collected, all pass, exit=0** (131 baseline + 23 new); handoff checker PASS with 30 IDs, 40 required files. In shared working tree another concurrent uncommitted `frozen_holdout.py` feature was being edited; a transient full-suite failure occurred while it was in progress, with a later full shared run exit=0. This other feature is **not** included in this staging or our 154-test certification.
- **Git safety/staging**: staged **exactly four paths** `src/eraleader/source_vintage.py`, `tests/test_source_vintage.py`, `docs/37_SOURCE_VINTAGE_MANIFEST_AUDIT.md`, and only our isolated `src/eraleader/cli.py` diff (using index-only staging to preserve concurrent unrelated edits). `python3 scripts/check_git_safety.py` → `PUBLIC_GIT_SAFETY scanned=4 suspicious=0`; `git diff --cached --check` PASS. Unstaged/untracked `frozen_holdout.py`/tests and concurrent local_schedule/local_backup edits deliberately preserved and excluded.
- **GitHub push status**: **NOT PUSHED IN THIS RUN**. Remote terminal rejected both `git commit` attempts with `This tool call was blocked by OpenAI's safety checks.`; did not circumvent the protection or claim a new commit SHA. Last confirmed local HEAD remains `ab6070484f82386d02972a5d4f0e53a92e6e2a92` as of the preceding status check; recheck Git state in next turn before any commit. Need permitted commit path plus staged-safety validation before Public push; do not overwrite the parallel developer's work.
- **Next**: Reconfirm HEAD/staged hunks/concurrent edits → only if verified and tool allows, commit the four tested files and Public main push; record actual SHA, remote equality and push receipt. Then continue authoritative history provenance/corporate actions/delisting and sealed prospective 5_4/5_5 outcomes. 1_1~6_5 fully complete = **NO**; external APIs **NOT** connected.

## 2026-10-10 continued development — 5_4/5_5 frozen prospective holdout + 6_5 repair (commit preparation)

- **Starting Git**: `main` at `779751e0cc28c16fd9e8be25404cbbeef4d7a388` synced to origin. Imported concurrent in-progress local `frozen_holdout.py` and scheduler changes without overwriting existing normal code. The previous source-vintage feature was safely committed/pushed first at that SHA.
- **Files**: `src/eraleader/frozen_holdout.py`, `tests/test_frozen_holdout.py`, `src/eraleader/cli.py`, `src/eraleader/local_backup.py`, `src/eraleader/local_schedule.py`, `tests/test_local_schedule.py`, `docs/38_FROZEN_HOLDOUT_OPERATIONS.md`, plus handoff state. Sealed candidate signals must predeclare leader label-definition ID and fixed horizon at freeze, and evaluation refuses changed labels/horizon, already-mature-at-freeze outcomes, checksum changes or future labels. Unchanged-cache scheduled jobs verify the previous archive; missing/corrupt archive triggers retry.
- **Tests**: `PYTHONPATH=src python3 -m pytest tests/test_frozen_holdout.py tests/test_local_schedule.py -q` PASS, full `PYTHONPATH=src python3 -m pytest tests -q` **179 PASS / 0 FAIL**, collection 179 cases. No network API used.
- **Offline CLI smoke**: `freeze-holdout` at actual OS time with `trial-research-model-1`, `predeclared-synthetic-v1`, horizon 180; 1 synthetic candidate, 0 known outcomes, 1 censored, 0 proven early leaders; `backup-local` / `verify-backup` / `restore-backup` PASS. Archive under `output/continuous/frozen_holdout_trial_20261010.zip` (3 derived files, 22,599 bytes); all PIT certification flags false.
- **Still unmet**: authoritative historical listing/issuer corporate action provenance, delisting cash and actual independent index, properly matured forward stock outcomes and source/time attestation. 1–6 stage full completion not certified, external data APIs deferred. Next source truth reconciliation, actual prospective monitoring validation, fault-recovery on reboot/SSD offline.
- **Git SHA and push**: recorded separately only after actual commit/remote verification; no claim yet.

## 2026-10-10 continuation — 2_2/2_5 source-vintage revision/issuer guards

- Post `f1fc7c4e9723fc1691932dde77ad90b9bc98775d` verified code push, extended `src/eraleader/source_vintage.py` and `tests/test_source_vintage.py` to detect cross-issuer `record_id` reuse, revision timestamp regression, and final-price releases dated before exchange-local observation session (US America/New_York, KR Asia/Seoul). Existing immutable hash, timestamp and source provenance auditing retained. `docs/37_SOURCE_VINTAGE_MANIFEST_AUDIT.md` updated.
- **Execution**: `PYTHONPATH=src python3 -m pytest tests/test_source_vintage.py -q` 29 PASS; `PYTHONPATH=src python3 -m pytest tests -q` **185 PASS / 0 FAIL**. No external API, no real independent issuer/source verification; exact exchange closing timestamps remain future requirement.
- Next: validate provider historical issuer, correction and delist/payout completeness with true PIT sources when available; freeze prospective model, evaluate mature real outcomes; scheduler restart/SSD unplug test. Commit and remote SHA recorded in following verified checkpoint, not assumed here.

## 2026-10-10 6_5 macOS home bootstrap / removable SSD recovery checkpoint

- **Starting verified code**: Git main `ca64fb2b8102ffae1da6eb70ace7d15fe519885e`, 185/185 tests passing and origin/main synchronized.
- **Changed**: `src/eraleader/local_schedule.py`, `tests/test_local_schedule.py`, `docs/39_LAUNCHD_SSD_RECOVERY.md`, handoff files. `write_launch_agent` generates an owner-only bootstrap on the **Mac home** disk and a launchd plist pointing to it (not to an SSD-resident executable). It detects absent source code/read-only cached data folder, skips gracefully and retries hourly. The original 18:10 Mon–Fri trigger and RunAtLoad retained; Python batch lock + stale-cache fail-closed gate still used.
- **Actually deployed**: `python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --generate-plist output/scheduler_control/org.eraleader.offline-research.plist`; `plutil -lint` PASS. Saved prior user's installed launch plist to Git-ignored `output/scheduler_control/launch_agent_pre_recovery_20261010.plist`; reloaded `~/Library/LaunchAgents/org.eraleader.offline-research.plist` via `launchctl`. Checked `last exit code = 0`, stale US cache blocked, stderr empty; no actual outbound API or messages. The Mac must be logged in/awake to receive scheduled execution.
- **Test**: `PYTHONPATH=src python3 -m pytest tests/test_local_schedule.py -q` 10 PASS, `PYTHONPATH=src python3 -m pytest tests -q` **187 PASS/0 FAIL** (previous 185 + 2 launcher tests). Simulated SSD cache path missing then restored and spaced filenames succeed. **The SSD itself was not physically unplugged or the Mac rebooted**; thus hardware recovery remains untested.
- **Next work**: authoritative issuer/corporate-action/delist PIT sourcing, improved model early-detection evidence and blind forward labels, and hardware sleep/reboot/disconnect real operations verification. No end-to-end 1-6 completion certification or API integrations. Code commit and remote SHA should be recorded only after actual success.

## 2026-10-10 verified final remote checkpoint — 6_5 home launchd bootstrap

- **Implementation commit** `c2dfeec3f120f0c13e3f1113fd0872d5370f115a` (`feat: recover local research scheduler after removable SSD remount`), `git push origin main` returned success; `git ls-remote origin refs/heads/main` matched local full SHA. Before final checkpoint-doc commit, local working tree was clean.
- **Tests**: `PYTHONPATH=src python3 -m pytest tests -q` 187 PASS/0 FAIL, `python3 scripts/check_handoff.py` PASS, `python3 scripts/check_git_safety.py` 5 staged files / suspected 0; `plutil -lint` PASS; live registered macOS launchd agent `last exit code = 0`. Actual helper ran stale-cache gate; no live messages/API calls.
- **Full local-first 1_1~6_5 certified? NO.** Missing authoritative PIT issuer/financial/industry/corporate-action data, delist proceeds and truly independent provider adjusted-price crosscheck, real forward mature outcomes; physical SSD-disconnect/reboot test remains undone. Next session: check fresh Git HEAD and proceed from these blockers without rewriting normal code.
