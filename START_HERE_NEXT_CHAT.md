# START HERE — EraLeader 새 대화/새 개발 세션 인수인계

> 마지막 로컬 파일 상태 확인: 2026-10-10 KST. 기준 폴더: `/Volumes/T5DATA/eraleader`
> 이 문서가 먼저 읽을 **현재 상태와 재개 절차의 단일 입구**다. 오래된 기록은 과거 시점의 사실로만 취급한다.

## 최우선 목적 — 새 대화에서 절대 혼동하지 않기

**EraLeader의 최종 목적: 앞으로 나타날 한국·미국 시장의 미래 대장주를 가능한 한 초기에 찾아내는 능력을 구축·운영하는 것.** 과거 대장주를 맞히는 것은 목표가 아니라 **그 능력이 과거 공개정보만으로 작동했는지 검증하는 시험**이다. 백테스트 고수익률이나 과거 종목을 회고적으로 잘 설명하는 것은 최종 성공으로 인정하지 않는다. 실운영 단계에서 신규 후보를 사전에 기록하고 이후 성과를 추적해야 한다.

## GitHub 저장소 상태 (2026-10-10 확인)

- GitHub 저장소 **`arirang0605-lgtm/eraleader`** 생성 확인: https://github.com/arirang0605-lgtm/eraleader
- 기본 브랜치 `main`, 원격 크기 `0`, **확인 당시 PUBLIC(공개)**. SSD에서 로컬 Git `main` 초기화됨, **원격 연결·push 미진행**. 로컬 마지막 커밋은 `PROJECT_STATE.md` 최신 기록 확인.
- 민감한 알고리즘·API 키·데이터를 공개 push하지 않도록 **Private 여부를 사용자와 확정하고** Git 초기화/보안 검사/원격 연결을 진행할 것. 사용자 승인 없는 공개 설정 변경/강제 push 금지.
- 최신 구체 내용: `docs/26_GITHUB_REPO_HANDOFF.md`.

## 새 세션 시작: 5분 이내 복구

1. Remote Desktop Commander가 연결된 Mac `SHMOONui-MacBookAir.local`이 **Online**인지 확인. 연결이 없으면 로컬 SSD 작업을 한 것처럼 주장하지 않는다.
2. **이 파일** → `AGENTS.md` → `PROJECT_STATE.md`의 *최신 스냅샷* → `DECISIONS.md` 순으로 읽는다. 상세 작업이 정해지면 관련 `docs/*.md` 한두 개만 추가로 읽는다.
3. 경로 확인: `/Volumes/T5DATA/eraleader`, `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine`. 후자는 **READ-ONLY**.
4. `README.md`와 `docs/21_MASTER_ARCHITECTURE_NUMBERING.md`의 세부 작업 ID `1_1`~`6_5`를 그대로 사용.
5. 한 번에 **하나의 최소 작동 기능**을 선택 → 코드 작성 → 실제 실행/pytest → 결과 기록 → 상태 업데이트. 긴 계획 논의를 반복하지 않는다.

## 프로젝트의 목적 및 사용자 확정사항

- 프로젝트 이름: **EraLeader — 시대의 대장주 검색기**, MarketOS와 **독립**이며 읽기 전용 API/JSON으로 필요할 때만 연동.
- 한국·미국 주식의 **미래 잠재 대장주를 조기에 발굴**; 확정 대장주·약화·교체 신호도 추적.
- 최종 사용자 기능: **① 웹 대시보드 ② 이벤트 자동 알림 ③ 일/주/월 보고서** 모두 포함.
- 산업 성장성·경쟁력·실적 가속·상대강도·수급을 연구. 100점 배점(20/20/25/25/10) 및 65/80 임계값은 **미검증 초기 가설**이다.
- **PIT**: 의사결정 당시 실제 공개·이용 가능한 정보만 사용; 상장폐지/분할/배당·정정공시·산업 분류/종목군의 당시 이력 보존.
- 백테스트 **기반은 2단계 직후** 구축해 3·4단계 개발 시 모듈별 검증하고, 5단계에서 통합·워크포워드·홀드아웃 검증.
- 데이터 수집/지표/백테스트/알림/보고는 Python 자동 작업으로 LLM 토큰 최소화; 개발 상태는 문서/Git로 보존.

## 현재 실제 구현 여부 — 과장 금지

| 항목 | 지금 검증한 사실 |
|---|---|
| 1~6단계 개발/데이터 명세 | Markdown 작성됨 |
| 전체 그림/단계별 그림 | PNG+SVG 총 7장 쌍 보존; 전체도는 `1_1`~`6_5` |
| EraLeader 소스 패키지/배포·독립 Git | **Python src/eraleader + tests 존재, 17 pytest PASS**. Git 초기화·원격 연결 상태는 `PROJECT_STATE.md` 최신 기록으로 확인 |
| EraLeader 분석·후보 상태·PIT DB | **가격전용 WATCH 관찰 엔진·SQLite/PIT fixture 일부 구현**, 산업·실적 PIT 및 후보 확정은 미구현 |
| 실전용 PIT 백테스트/대시보드/알림/보고 | **로컬 HTML/JSON/SQLite·dry-run 알림·Markdown 보고 구동**, 실전 백테스트·라이브 전달은 미구현 |
| 외부 SSD 주가 파일 재사용 | read-only Parquet 검증·예제 조회 테스트 통과 |
| 기존 업종 모멘텀 스모크 실행 | 계산 실행 성공; EraLeader 투자 성능 검증은 아님 |

과거 대화의 'v0.1 가상데이터 8개 테스트' ZIP 파일은 **이 SSD 안에서 확인되지 않았다**. 존재한다고 가정해 코드를 다시 만들거나 완료 선언하지 않는다.

## 기존 SSD 자산 — 먼저 로컬에서 재사용

- `/Volumes/T5DATA/backtestengine`: 조사 시 **빈 폴더**.
- `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine`: 1995~2026년 한국 주식 `marcap` Parquet 32개/15,648,407행(원본 검증 요약과 일치), 미국 S&P500/NASDAQ100 주봉 데이터 및 모멘텀 테스트 코드.
- 미국 주봉은 2026년 현재 종목군에 편향될 수 있어 그대로 장기 PIT 테스트에 사용 불가.
- 원본 가격의 split/dividend 보정·상폐 완전성·공시 PIT·재배포 라이선스는 **미검증**.
- 재현 명령(네트워크 없음):
  ```bash
  /Volumes/T5DATA/CycleOS-Lab_BacktestEngine/.venv/bin/python /Volumes/T5DATA/eraleader/scripts/verify_backtestengine_reuse.py
  /Volumes/T5DATA/CycleOS-Lab_BacktestEngine/.venv/bin/python /Volumes/T5DATA/eraleader/scripts/read_cached_marcap.py --code 005930 --start 2025-01-02 --end 2025-01-31
  ```
- 검증 결과 경로: `results/reuse_probe/{local_assets_audit.json,marcap_sample_query.json,sector_mom_baseline_one_config.csv}`.
- **기존 프로젝트/데이터는 읽기 전용. 기존 poller/GCS/유료 API를 허가 없이 실행하지 말 것.**

## 다음 실제 개발 작업 (가장 우선, 아직 미완료)

**최신 NEXT_TASK = 3_4·3_5 가격/산업/실적 PIT 피처 통합 + 4단계 안전 판정 연결**. 기존 2_2·2_3·3_1~3_3 오프라인 입력/증분/정정·성장률은 `docs/28_OFFLINE_PIT_FEATURE_IMPLEMENTATION.md`까지 **33개 테스트 통과**. 아래 초기 계획은 역사적 기록이므로 재개발 금지.

1. 이 경로가 Git 미초기화 상태임을 확인하고 독립 Python 패키지 구조·pytest 환경을 만든다. 새 GitHub **Private** 저장소 연결은 사용자 승인 후 시행.
2. `scripts/read_cached_marcap.py`의 로컬 가격 읽기 기능을 **새 패키지의 read-only 데이터 어댑터**로 편입하되 원본 경로를 강제 의존으로 만들지 않는다.
3. 데이터 원본/종목ID/시점(available_at)/품질 보고의 최소 스키마 구현: 날짜별 PIT 기준 `available_at <= decision_at`. **주가는 이 스키마의 일부일 뿐**이며 재무 공시 공개시각은 별도 확보해야 한다.
4. **먼저 자동 테스트 4개**: 미래 공시 투입 후 과거 snapshot 불변, 중복 재수집 idempotency, 샘플 005930 가격조회 18행(환경 존재 시), 과거 ticker/상폐 필드 누락 시 검증 보류.
5. 주간 모멘텀 baseline을 기존 엔진 로직과 비교하는 5_1 최소 계약/테스트. **수익률 공식 검증은 금지**(PIT 미완료).
6. 결과 증거를 `results/`에 남기고 `PROJECT_STATE.md` 최신 상태 및 실행 명령/테스트 PASS/FAIL/Git 상태 갱신.

세부 실제 실행순서·인수조건: [NEXT_IMPLEMENTATION_SPRINT](docs/25_NEXT_IMPLEMENTATION_SPRINT.md).

## 그림/문서 빠른 길잡이

- 전체 투자·개발지도(고유 30개 작업): [PNG](EraLeader_전체설계도_1-6단계_세부번호.png), [SVG](EraLeader_전체설계도_1-6단계_세부번호.svg)
- 데이터 수집 상세: [PNG](EraLeader_데이터수집_전체구조도.png), [MD](docs/13_DATA_COLLECTION_IMPLEMENTATION.md)
- 단계별 상세: [2~6단계 인덱스](docs/19_STAGES_2_TO_6_INDEX.md)
- 정확한 30개 번호: [21_MASTER_ARCHITECTURE_NUMBERING.md](docs/21_MASTER_ARCHITECTURE_NUMBERING.md)
- 기존 데이터·백테스트 재활용: [23_BACKTESTENGINE_LOCAL_REUSE.md](docs/23_BACKTESTENGINE_LOCAL_REUSE.md)
- 추가로 필요한 명세/그림 평가: [24_ARCHITECTURE_GAP_REVIEW.md](docs/24_ARCHITECTURE_GAP_REVIEW.md)

## 운영 시 사용자 보고 형식

`작업 ID | 실제 변경한 파일 | 실행 명령 | 통과/실패/미실행 | 현재 차단점 | 다음 작업`

**원칙: REWRITE 아닌 CONTINUE / 설계 그림보다 WORKING CODE / 완료 선언보다 TEST RESULT.**

## 빠른 인수인계 점검(오프라인·재다운로드 없음)

`python3 /Volumes/T5DATA/eraleader/scripts/check_handoff.py`

- 실제 마지막 실행: 2026-10-10, `handoff=PASS`, 필수 14파일, 작업번호 30개, 그림 PNG 7장/SVG 7장, 오류 0건.
- 이 검사는 파일·링크·핵심 산출물을 확인할 뿐 실제 데이터 수집/PIT 전략 검증은 수행하지 않는다.

## 로컬 개발 실제 구현 시작 (2026-10-10 갱신)

- 외부 API 연결은 사용자 결정에 따라 **로컬 1~6단계 기능 완성 후**로 연기. 현재 SSD에서 이미 `src/eraleader` 독립 코드가 작동하므로 **기존 코드를 다시 만들지 말 것**.
- 실제 통합 개발 기록: `docs/27_LOCAL_FIRST_IMPLEMENTATION.md`. 가격 전용 KR/US 데이터 로딩/점수·PIT fixture/SQLite 원장/모멘텀 baseline·정적 웹·알림 모의·Markdown 보고; pytest **17개 통과**.
- 현재 단일 다음 목표: **2_2 역사 종목/기업행동 PIT + 3_1~3_3 실제 이용 가능 시각이 있는 오프라인 재무·산업 자료 계약**, 이후 4단계 실제 후보 검증. 백테스트 수익률보다 미래 조기 발견 능력 검증 우선.
- 로컬 웹: `PYTHONPATH=src python3 -m eraleader serve --port 8765`, 브라우저 `http://127.0.0.1:8765/`; 실행 출력은 `output/` (Git 추적 제외).
- GitHub `arirang0605-lgtm/eraleader`는 Public 확인됨. 로컬 commit 결과와 remote 연결 여부는 `PROJECT_STATE.md` 및 `git status -sb`로 재확인하고 승인 전 push 금지.
