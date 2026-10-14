# START HERE — EraLeader 새 대화/새 개발 세션 인수인계

> 마지막 로컬 파일 상태 확인: 2026-10-10 KST. 기준 폴더: `/Volumes/T5DATA/eraleader`
> 이 문서가 먼저 읽을 **현재 상태와 재개 절차의 단일 입구**다. 오래된 기록은 과거 시점의 사실로만 취급한다.

## 최우선 목적 — 새 대화에서 절대 혼동하지 않기

**EraLeader의 최종 목적: 앞으로 나타날 한국·미국 시장의 미래 대장주를 가능한 한 초기에 찾아내는 능력을 구축·운영하는 것.** 과거 대장주를 맞히는 것은 목표가 아니라 **그 능력이 과거 공개정보만으로 작동했는지 검증하는 시험**이다. 백테스트 고수익률이나 과거 종목을 회고적으로 잘 설명하는 것은 최종 성공으로 인정하지 않는다. 실운영 단계에서 신규 후보를 사전에 기록하고 이후 성과를 추적해야 한다.

## GitHub 저장소 상태 (2026-10-10 확인)

- GitHub 저장소 **`arirang0605-lgtm/eraleader`** 생성 확인: https://github.com/arirang0605-lgtm/eraleader
- 기본 브랜치 `main`, **PUBLIC(공개)** 유지 및 사용자 명시 승인에 따라 **GitHub origin/main 연결·푸시 완료**. 최초 생성 당시 크기 0/미연결은 과거 기록이며 최신 SHA와 테스트는 `PROJECT_STATE.md` 상단·하단 및 `git status -sb`에서 확인.
- **사용자 최신 승인(2026-10-10)**: 공개(Public) 저장소에 코드·MD·설계도 GitHub push 허용. 키·토큰·원시 시세·민감 데이터는 `.secrets/` 등 로컬 전용 영역에 저장하고 Git 제외. 강제 push 금지. 6단계까지 추가 단계 승인 질문 없이 개발하되 테스트 증거 보존.
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

**최신 NEXT_TASK = 2_2·2_5 기업행동/상폐 PIT 원천 감사·조정가격 교차검증 + 5단계 실제 검증 + 6단계 로컬 자동화**. 2026-10-10 `docs/31_CORPORATE_ACTION_AND_UNIVERSE_AUDIT.md`에 분할/배당 비조정 총수익 계산·KR 종목군 관측 감사까지 구현/실행했고 **전체 pytest 79개 통과**. 6_5 SQLite 온라인 백업·파일 무결성 검사·원자적 신규 경로 복구도 `docs/32_LOCAL_BACKUP_RECOVERY.md`와 자동 테스트로 검증됨. 3_4·3_5 결합/4_2~4_5 상태 이력/5_2 계산기/6_2 연구 화면까지 `docs/29_LOCAL_STAGE3_TO_6_MILESTONE.md`로 개발됐고 **54개 테스트 통과**, 이어서 `docs/30_WALKFORWARD_LOCAL_BATCH.md`에 5_3 워크포워드 및 6단계 로컬 KR+US 일/주/월 배치 구현/실행 결과 반영. 이전 초기 TODO는 역사적 계획으로만 취급. 사용자 Public GitHub 푸시 승인 완료.

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

## 2026-10-10 최신 연속 개발 체크포인트 (기존 오래된 수치보다 우선)

- 5_2/5_4의 조기발굴 신호 평가에 실제 신호기록일(`recorded_at`) 검사 및 후행등록 조기성과 방지 추가.
- 6_5 맥북 `launchd` 로컬 연구 자동점검: 평일 18:10 KST 실행, 최초 경로 오류 고쳐 정상 exit code 0 확인. KR 2026-10-02, US 2026-02-26 자료이므로 **일반 자동 실행은 신선도 규칙상 안전 보류**. 명시적 연구용 override는 백업검증 포함 전체 배치 성공.
- 현재 **pytest 90 PASS**, 외부 API 0 / 라이브 알림 0. 상세 `docs/33_LOCAL_SCHEDULER_DISCOVERY_AUDIT.md`.
- 기존 79개, 54개, 17개 테스트 언급은 역사 기록. 실제 다음 우선 과제는 2단계 **독립 원천 PIT 인증/조정가격 검증**, 5단계 **시점별 홀드아웃 실증**. `PROJECT_STATE.md` 맨 마지막 체크포인트/Git을 다시 확인해 CONTINUE.

## 2026-10-10 최신 소스 감사 이어서 개발 (이전 체크포인트 보완)
- 2_2/2_5: `pit_coverage.py` / `audit-pit-coverage` 추가. PIT 종목군 대 기존 가격 관측 코드의 커버리지·불일치·상폐 추정 불가·거래중단을 명시. **공식 역사적 상장 원천 인증이 아님**. 7개 신규 테스트 포함 전체 **97 pytest PASS**. 상세 `docs/34_PIT_SOURCE_COVERAGE.md`; `PROJECT_STATE.md` 마지막 Git SHA 확인.

## 2026-10-10 후속: 미래 후보 최초 기록 시각 원장 및 복구 검증
- **최신 개발** `docs/35_PROSPECTIVE_SIGNAL_REGISTRY.md`: `prospective.sqlite`에 연구용 성장 관찰 신호를 실행 시각에 별도 등록, 과거 데이터 재실행의 조기 발굴 성과 소급 차단. CLI `prospective-signals`, KR/US 신규 HTML 등록화면, DB 온라인 백업·복구 포함.
- `pytest 111개 PASS`; 2024 합성자료를 2026-10-10 실행한 결과 기록일은 2026-10-10(과거자료 backfill=true). 로컬 웹/e2e, 검증 백업·복구 성공, 실제 인증 후보 0. **실전 PIT 및 실제 발견 성능 미인증**. 다음은 원천 독립 자료/기업행동·상폐/조정가격 교차검증과 봉인 홀드아웃.
- 실제 HEAD/원격 push 증거는 `PROJECT_STATE.md` 맨 마지막 체크포인트와 `git status -sb`로 먼저 확인.

## 2026-10-10 추가 개발 — 2_5 원시 주가/기업행동 대 독립 총수익지수 비교 계약
- `src/eraleader/adjusted_crosscheck.py`, CLI `audit-total-return`, 문서 `docs/36_TOTAL_RETURN_CROSSCHECK.md`. 합성 split/dividend 수익률(0%) vs 참조지수 일치/200bp 불일치 탐지, 자료 게시시각 검사. 현물 시장의 **실제 독립 공급자 검증은 미완료**, 시세/기업행동 PIT 인증 불가. 전체 `pytest 131개 PASS`, 외부 API 호출 0.
- `PROJECT_STATE.md` 맨 아래 SHA+푸시 기록 및 실제 Git 상태부터 확인. 정상 코드 보존, 다음은 역사적 실제 데이터 원본 증빙 + 5단계 홀드아웃 품질.

## 2026-10-10 이후 최신 로컬 개발 — 2_2 / 2_5 원천 빈티지 감사 (Git push 대기)

- `src/eraleader/source_vintage.py`, `tests/test_source_vintage.py`, `docs/37_SOURCE_VINTAGE_MANIFEST_AUDIT.md`, `cli.py` `audit-source-vintage` 개발/합성 실제 실행. **완전 분리된 HEAD+이번 네 파일 시험 154 pytest PASS**; 로컬 시험 source 2개 모두 과거 시점 이후 수집으로 탐지, `historical_pit_certified=false`. 원본 자료 인증·실전 조기발굴 성과 아님.
- 개발 당시 다른 세션의 `frozen_holdout.py` 등 미커밋 변경이 동시에 관측됨. **서로의 변경 보존**: 이번 변경 네 경로만 index에 선별 staged, 안전 검사 suspicious=0. `git commit`을 원격 도구 안전검사가 거부했으므로 이번 작업 GitHub push **안 됨**. `PROJECT_STATE.md` 최하단 기록과 `git status -sb`, `git diff --cached`를 반드시 다시 확인하여 다른 세션이 변경한 파일을 무단 commit하지 않을 것.
- 다음은 차단 해제 시 테스트된 네 경로만 commit/push + SHA 원격 비교 → 독립 PIT 원천 인증·상폐정산·5_4/5_5 봉인 홀드아웃 증거 보강. 외부 API 연결은 1~6단계 로컬 검증 후.

## 2026-10-10 다음 세션 인수인계 — 5_4/5_5 봉인 홀드아웃 및 6_5 복구 보강

- 개발·실측: `frozen_holdout.py` + `cli.py`의 동결/평가, `local_schedule.py` 보관 ZIP 손상 시 재작업, `local_backup.py` 홀드아웃 manifest/평가 산출물. 사전 `label_definition_id`와 `horizon_days`를 freeze 시 반드시 잠금. 이후 기간/라벨 변경·동결 전에 성숙한 라벨·자료 유출 차단.
- 전 자동 테스트 **179개 PASS**. 합성 후보 1개 실시간 원장 기록→봉인→평가(미성숙 1건, 실제 성능 0건)→백업 3개 파일 SHA 검증·복원 테스트 PASS. 상세 `docs/38_FROZEN_HOLDOUT_OPERATIONS.md`; 실전 PIT 및 미래 발견 정확도 미인증.
- 이제 우선 작업: 2_2/2_5 실제 독립 원천·상폐·기업행동 PIT, 5_5 전향적 평가 실제 라벨, 6_5 SSD 연결/재부팅 복구. 최신 Git SHA와 push 상태는 `PROJECT_STATE.md` 하단 및 git에서 확인.

## 2026-10-10 추가 — 2_2 원천 기록 정정/기업 동일성 감사 강화

- `source_vintage.py`에서 동일 기록ID의 issuer 바뀜, 개정번호 공개시간 역전, 가격의 거래일 이전 이용 가능 날짜를 차단. 상세 `docs/37_SOURCE_VINTAGE_MANIFEST_AUDIT.md`; 신규 테스트 6개 포함 **전체 185개 PASS**. 실전 원천 PIT 인증은 여전히 미완료. 최신 Git 원격 SHA는 `PROJECT_STATE.md` 맨 아래 확인.

## 2026-10-10 새 LaunchAgent 복구 경로

- `docs/39_LAUNCHD_SSD_RECOVERY.md`: 맥북 홈디스크 `~/Library/Application Support/EraLeader/offline-launcher.sh`에서 SSD 연결 확인 후 Python 로컬 배치 실행. 불연결 시 조용히 건너뛰고 다음 매시간 재검사, 평일 18:10/로그인시 실행 유지. 재생성된 사용자 LaunchAgent exit 0, 시세 신선도 규칙 유지, stderr 빈 로그 확인.
- `pytest 187 PASS`; 실제 하드웨어 SSD 제거·맥북 재부팅 테스트는 **아직 안 함**. 추가 실전 PIT/API 연결 없음. 현재 Git SHA, 코드/테스트/푸시 기록은 `PROJECT_STATE.md` 마지막 체크포인트 확인.

## 2026-10-10 최신 개발 (2_2/2_5) — KR 일봉 / US 주봉 관측 연속성 실측

- `src/eraleader/continuity_audit.py` + CLI `audit-continuity` + 문서 `docs/40_LONGITUDINAL_CACHE_CONTINUITY.md`: 한국 일별/미국 주별 관측 누락·재등장·관측 중단·거래정지를 구분하는 연구 감사 기능 및 안전 ZIP 백업. US 주봉의 서로 다른 요일로 인한 거짓 누락 27,942건을 일간 집계 문제로 확인하고 주봉 기준으로 수정해 재검증.
- 실제 T5DATA read-only 캐시: KR 83거래일/2,909코드/관측행 238,462/중간 누락 0/마지막 경계 이전 종료 36. 미국 58주/499코드/관측행 28,441/중간 주봉 누락 0/마지막 경계 이전 종료 1. **원천 상폐/PIT/기업행동 인증 아님**. 새 테스트 18개 추가해 **205 pytest PASS**. 내역 및 다음 차단점은 `PROJECT_STATE.md` 마지막 기록 확인; 외부 API는 연기.

## 2026-10-10 추가 5_5 평가기 보완

- `frozen_holdout.py`: 180일 평가 전의 성급한 부정결과를 오탐으로 확정하지 않음. 실제 신호 등록일부터 동결된 평가기간이 경과해야 부정 라벨 확정, 조기 부정은 미확정. 전체 **207 pytest PASS**. 상세 `docs/38_FROZEN_HOLDOUT_OPERATIONS.md` 하단 및 `PROJECT_STATE.md` 최신 기록. 여전히 실제 미래 성능 인증 아님. Git SHA 최신 기록/상태를 확인하고 계속.

## 2026-10-10 2_2/2_5 전체시장 캘린더 감사 확장

- `docs/41_EXCHANGE_CALENDAR_AUDIT.md` 및 `src/eraleader/calendar_audit.py`: 거래소 세션 캘린더를 **별도 로컬 JSON 계약**으로 받아 한국 일봉·미국 주봉과 비교. 관측 자료에서 시장 전체 기간이 누락되면 탐지하지만 캘린더 제공자/시점은 독립 인증 안 됨. 의도적으로 누락시킨 합성 KR/US 자료 각각 1건 탐지, 안전 JSON 백업·복원 PASS. 기준 207 테스트에서 본 기능 20개 신규 케이스; 동시 워크포워드 세션 테스트까지 포함한 전체 공유 실행은 246 PASS. 실제 PIT 완전성/대장주 발굴 성과 아님.
- 다른 세션 `walkforward_replay.py` 등 미커밋 파일은 보존·별도 staged. 최신 Git SHA 및 테스트·동기화는 `PROJECT_STATE.md` 최하단에서 재확인.

## 2026-10-10 최신 2_2/2_5 현금형 상폐 정산 연구 개발

- `docs/43_CASH_DELIST_SETTLEMENT_RESEARCH.md`, `delist_cash.py`, CLI `audit-cash-delist`: 신뢰할 수 있는 현금 정산액이 입력되지 않으면 손익을 0/마지막 종가로 지어내지 않고 미확정; 지급/게시시각·분할·배당 원시가격 수익률과 KRW/USD를 검사. 합성 KR +10%, US +5% 연구 결과 테스트, 실제 주식 성과 아님. 신규 pytest 24개 포함 동시 공유 전체 `270 PASS`. 연구 JSON ZIP 백업 SHA 및 복구 성공. 독립 원천 PIT 인증 false.
- 동시 워크포워드 코드/테스트(`walkforward_replay.py` 관련)는 다른 세션 것이므로 스테이징된 상태에서 그대로 보존. Git HEAD·원격과 다음 실제 미완료는 `PROJECT_STATE.md` 마지막 기록 확인. 외부 API는 아직 연결 금지.

## 2026-10-10 최근 2_2/2_5 — 기업 영구ID/티커 계보 감사

- `src/eraleader/issuer_lineage.py`, CLI `audit-issuer-lineage`, 문서 `docs/44_ISSUER_LINEAGE_PIT_AUDIT.md`: 영구 기업 ID와 동일 티커 재사용, 동시 충돌, 기업행동의 미등록 대상/후계 기업, 미확인 상폐 현금, 시점 후행 취득/개정 이력을 감사. 합성 3개 시나리오 CLI 및 파생 JSON 안전 백업·복원 PASS. 신규 테스트 25개 포함 작업 폴더 전체 295 PASS(다른 세션 19개 테스트 포함). 진짜 상장 이력·법적 ID·정산금 원천 인증 아님.
- 워크포워드 다른 세션 3개 staged 파일 `docs/42_*`, `src/eraleader/walkforward_replay.py`, `tests/test_walkforward_replay.py`은 손대지 말 것. Git SHA/Push은 `PROJECT_STATE.md` 마지막 검증 기록 우선.

## 2026-10-10 최신 5_5 반복 워크포워드

- 기존 스테이징 3개 파일을 HEAD+3 파일 분리 재현(297 pytest PASS) 후 별도 소스 커밋 `4ee780d` GitHub 푸시, 원격 SHA 일치. 이후 CLI `replay-walkforward` 및 파생 JSON ZIP 백업 검증, 전체 공유 소스 `pytest 300 PASS`. 2폴드 합성 3개 테스트 후보/결과 라벨 비공개. 문서 `docs/45_REPEATED_WALKFORWARD_CLI.md`; 실제 역사 원천 PIT나 미래 대장주 성공률 인증은 불가.
- 최신 Git 커밋과 원격 상태는 `PROJECT_STATE.md` 마지막 체크포인트와 `git status -sb`를 확인할 것. 다음 실제 독립 상장·상폐/기업행동 원천, 실전 홀드아웃 라벨, 6_5 하드웨어 복구 검증 우선.

## 2026-10-10 최신 2_2/2_5/5_5 PIT 근거 통합 게이트

- `src/eraleader/evidence_gate.py` + CLI `audit-evidence-gate` + `docs/46_LOCAL_EVIDENCE_GATE.md`: 원천 빈티지·영구ID/상폐·거래소 캘린더·가격 누락·상장종목군/가격 5가지 감사 결과를 **같은 시장/기준시각**으로 대조. 부족한 원천/미인증/불일치 자동 차단; 합성 5개 보고서를 모두 통과해도 **공식 대장주 인증은 불가**. 실제 한국 가격 캐시 감사만 입력한 테스트에서는 1/5영역, 차단사유 5개. 파생 결과 SHA 백업/복원 확인. 신규 25개 포함 **pytest 325 PASS**.
- 남은 실전 원천 PIT/기업행동 현금 지급 증명 및 실제 미래 대장주 검증. 최신 Git/원격 SHA·푸시 결과는 `PROJECT_STATE.md` 맨 마지막 체크포인트 확인.

## 2026-10-10 최신 6_2 PIT 근거 웹 대시보드

- `audit-evidence-gate` CLI가 이제 `site/evidence_{kr,us}.html` 정적 페이지까지 생성. 누락 PIT 증거·차단 사유가 표로 확인되고 확정 대장주 0건 명시, HTML escaping 및 위조된 인증 표시 차단. 한국 실제 가격 캐시 입력(1/5 감사지표, 5차단) 페이지 로컬 HTTP 200, JSON+HTML SHA ZIP/복원 PASS. 새 4개 테스트 포함 **329 PASS**. 상세 `docs/46_LOCAL_EVIDENCE_GATE.md`.
- 진짜 독립 PIT 원천, 기업행동/상폐정산, 미래 후보 실전 결과 미확인. 최종 SHA/푸시 기록은 `PROJECT_STATE.md` 하단에서 확인.

## 2026-10-10 17:19 5_4/5_5 원장 무결성 — 이번 실행 체크포인트

- `frozen_holdout.py`에 첫 신호 동결 이전 원장 ID/기업ID/원본 canonical JSON/SHA256/시점/연구 WATCH 검사를 추가, 12개 합성 오염 회귀; 기존 포함 전체 **341 pytest PASS**, 보안검사 3파일 이상 0.
- 문서: `docs/38_FROZEN_HOLDOUT_OPERATIONS.md`; 상세 진행/차단: `PROJECT_STATE.md` 최하단. 커밋 명령이 원격 안전검사에 차단되어 **해당 기능은 로컬 3개 경로만 staged, 아직 GitHub 미반영**. 마지막 실제 원격 SHA는 `PROJECT_STATE.md` 확인. 상태 파일 자체는 변경되어 추적 대기.
- 다음 작업자: 현재 Git 상태, staged 3경로/새 변경을 먼저 확인하고 절대 덮어쓰지 말 것. 도구의 허용 범위에서만 커밋/푸시를 재시도하고 실제 SHA를 기록. 실전 PIT·외부 공증·성숙 결과 검증은 여전히 미완료, 외부 API 연결 금지.

## 2026-10-10 5_4/5_5 WATCH 지속/약화/재진입 이력

- 전 채팅의 홀드아웃 원장 무결성 3개 파일은 별도 검증 후 `c57ec59` 원격 푸시 확인. 새 로컬 연구 원장은 스크리닝 hit true/false를 동일 트랜잭션에 명시적 저장, 누락 종목은 약화로 간주 금지. 최초 양성/지속/명시적 약화/재등장을 추적하며 3일 초과 소급 연구자료는 전향적 성과에서 제외. `audit-watch-progression`, `docs/47_PROSPECTIVE_WATCH_PROGRESSION.md`, 신규 테스트 16개, 합계 `pytest 357 PASS`. 모의·합성 4일 자료로 CLI/ZIP SHA 복구 검증. 공식 대장주/PIT 인증 여전히 0. Git 최종 SHA 및 실제 Push는 `PROJECT_STATE.md` 최신 기록과 Git을 확인.

## 2026-10-10 6_2 후보 WATCH 변화 로컬 웹 화면

- `audit-watch-progression`이 `site/watch_progression_{kr,us}.html` 생성, 명시적 최초/지속/약화/재진입·소급 제외 건수 확인. 안전 HTML escape, 확정 대장주 0건 및 미래 정확도 미인증 고정. 합성 후보 4일/로컬 HTTP 200/파생 JSON+HTML ZIP SHA 검증·복원 PASS. 신규 웹 테스트 3개 포함 전체 **360 pytest PASS**. `docs/47_PROSPECTIVE_WATCH_PROGRESSION.md` 하단, 실제 Git 상태는 `PROJECT_STATE.md` 마지막 기록에서 확인.

## 2026-10-10 6_5 캐시 정정 빈티지 감지 (직전 작업)

- `src/eraleader/local_schedule.py`: KR 550일에 포함되는 **모든 과거 연도별 Parquet** 및 US 주봉의 실제 바이트 SHA256을 정상 실행 체크포인트에 포함. 최신날짜 동일해도 전 기간 원본 정정은 재실행; 분석/백업 중 파일변경은 checkpoint 중단; 오래된 미국 캐시 신선도 FAIL이면 기존대로 작업 건너뜀. `tests/test_schedule_cache_vintage.py` +10, **370 pytest PASS**. 실제 T5DATA KR-2025/2026, US 3개 SHA 확인/원본 무수정, US 226일 stale `SKIPPED_STALE_CACHE`; 상세 `docs/48_SCHEDULE_CACHE_VINTAGE_SHA.md`.
- Git 최종 커밋/푸시 상태는 `PROJECT_STATE.md` 최신 실측 및 `git status -sb`로 확인. 1~6 글로벌 완성 및 실전 주도주 후보 확정 불가, 외부 API 연기.

## 2026-10-10 3_1~3_5 / 4_1 / 5_4 회계/산업 신선도 게이트

- `docs/49_FISCAL_SOURCE_FRESHNESS.md` + `offline_features.py`, `research.py`, `prospective.py`, `watch_progression.py`: 재무/산업 보고기간이 판단일로부터 450일 초과하거나, 매출·영업이익 보고기간 불일치/필수 수치 누락이면 **성장 스크리닝 평가 보류**. 평가 보류는 WATCH 약화(false)로 원장에 등록하지 않음. CLI 및 로컬 웹에서 `deferred_research_screens`와 STALE 플래그 표시.
- 합성 2024 당시 자료는 성장 hit 1(당시 실제 등록 아님/현재 재생 시 backfill), 2026 동일 자료에서는 성장 hit 0 / 기업 2건 보류 / 신규 미래 후보 0 / 잘못된 약화 0. 실제 로컬 HTTP 200. 신규 10케이스 포함 `pytest 380 PASS`; 실전 미래 성능 인증 안 됨, API는 사용자 지시로 미연결. Git 커밋/remote SHA 결과는 `PROJECT_STATE.md` 최하단 실제 검사 기준.

## 2026-10-10 18시대 신규 2_3 PIT 시간대 누출 회귀 (다음 세션 참고)

- **로컬 실제 수정:** `src/eraleader/offline_pit.py` 상장/상폐·기업행동 유효일은 전달 시각의 UTC나 호출자 타임존 날짜가 아닌 **해당 거래소 KR/US 현지일**로 판정. US/KR 교차 시간대 + 뉴욕 DST 합성 회귀 5개: 원래 코드 4 실패를 수정 후 5 통과. `tests/test_snapshot_market_clock.py`, `docs/50_MARKET_LOCAL_PIT_DAY.md`.
- 관련 테스트 31/31 PASS, 전체 **385 pytest PASS**, 인수인계 30개 번호 PASS, Public 안전검사 3개 파일 suspicious=0. 공급자 PIT·실전 적중률 인증은 여전히 0.
- **GitHub 중요:** 세 코드/테스트/문서 경로만 staged 상태이며 **Git commit 자체를 원격 도구 안전 검사에서 차단**, 따라서 **이 기능 GitHub push 없음**. 다른 병렬 세션의 재무 신선도 상태 커밋 `d0289e17998692f93a5b1d4d17a8dc21438df7ee`는 HEAD/원격 일치하지만 **이 기능의 커밋이 아님**. `PROJECT_STATE.md` 맨 마지막과 `git status -sb` 읽고 안전하게 이어서 개발할 것. 도구 허용 시 세 파일 범위 commit/push부터, 안 되면 staged 보존하고 독립적인 다음 로컬 기능 진행.

## 2026-10-10 검증 완료 — PIT 현지 거래일·통합 분석·옵션형 자동 배치

- 2_3 `offline_pit.py` KR/US 현지 효력일 regression **385 테스트**, 소스 commit `91715ef` 원격 푸시 확인(과거 메모의 차단은 후속 성공으로 해소). 3_5 `research.py` PIT↔가격 현지 거래일 조인 검증 7개 추가 **392 PASS**, `a73f35e` 원격 푸시. 6_1 연구 배치 `batch --integrate-pit-research`는 명시적 옵션으로만 실행, KR/US 현지 결정 시각·오프라인 원장 필수 사전검사 후 PIT 재무/산업·가격·WATCH 원장·6 Markdown 보고 및 미발송 알림 경로 연결. 신규 8개 테스트 포함 **400 PASS**, `c5f356b` 푸시, 독립 git archive 400 PASS. `docs/50_MARKET_LOCAL_PIT_DAY.md`, `docs/51_INTEGRATED_MARKET_DAY_ALIGNMENT.md`, `docs/52_EXPLICIT_OFFLINE_PIT_BATCH.md` 확인.
- 실가격 캐시는 읽기 전용 **과거 2024년**, 재무 원장은 **합성**: 2시장, 보고 6개, KR 한 건 과거 소급 WATCH, US 한 건 보류, 실제 대장주 0/메시지 0/API 0. 기본 launchd 배치 여전히 가격 연구만, 외부 API 마지막 연결. 전체 1_1~6_5 최종 인증/실전 미래 발굴 정확도 **미확인**. 최신 Git/원격 SHA는 `PROJECT_STATE.md` 최하단과 `git status -sb` 확인.

## 2026-10-10 6_1/6_5 KR/US PIT 입력 사전검증 강화

- `docs/53_BATCH_BOTH_MARKETS_PREFLIGHT.md`: 명시적 `batch --integrate-pit-research`에서 KR·US 양국의 시점별 상장종목·가격·통합 연구를 **두 시장 다 확인한 뒤** 상태원장·후보·보고서 저장. US 가격/PIT 오류일 때 KR 부분 산출물 안 남음. 소스 재읽기 없이 preflight price snapshot 재사용, 기본 자동 배치/launchd는 가격연구만 유지. 합성 테스트 4건 추가 → **pytest 404 PASS**, 독립 `git archive` 실행 404 PASS. 코드 commit `8a79e63` 푸시, 원격 SHA 일치, 비밀키/원시가격 Git 업로드 없음.
- 실가격 2024년 KR·US 캐시는 read-only, 합성 PIT 원장 분리; 2시장, 6보고, 신규 후보 중복 없음, US 보류 1, 실전 메시지 0. 입력 사전검증이지 파일시스템 오류까지 100% 원자적 커밋은 아님. 실제 공급자 PIT·전향적 미래 대장주 적중률 인증 없음. 상태/remote 최신은 `PROJECT_STATE.md` 최하단/실제 Git 기준.

## 2026-10-10 D-021 사용자 확정 — 실제 SSD 재연결 시험의 개발 순서

- **물리적 T5DATA SSD 분리·재연결 및 맥북 재부팅 복구 시험은 외부 API 연결 후 프로젝트 최종 검증 단계로 이월**한다. 그 전에는 기존 모의 SSD 부재·복귀, 장애 주입, 상태복구/백업/해시 검증만 실행. 실제 물리적 분리·재부팅을 요청하거나 임의로 진행하지 않는다. 해당 실기 시험 미완료 상태를 기록하고 인증 완료로 표기하지 말 것. 원문 확정은 `DECISIONS.md`의 **D-021**.

## 2026-10-10 6_1/6_5 두 시장 PIT 연구 산출물 안전 게시

- `src/eraleader/pit_publication.py`, `docs/54_VERSIONED_PIT_BATCH_PUBLICATION.md`: 명시적 `batch --integrate-pit-research`은 임시 세대에 양국 SQLite/HTML/6보고서를 모두 만든 뒤 파일 SHA256 영수증 검증·동일 SSD의 디렉터리 및 `current_pit_batch.json` 원자적 교체로 게시. 새 CLI `verify-pit-publication --out`으로 **현재 검증된 세대만** 조회, 이전 세대 불변, 중간 US 실패·마지막 포인터 교체 실패시 이전 정상 결과 유지, 오염된 게시 파일은 거부. 합성 오류주입 테스트 11개 신규, 전체 **pytest 415 PASS**, 실제 read-only KR/US 과거 캐시+합성 PIT 배치에서 두 세대 각각 25 산출물 검증. 기본 자동배치/launchd 및 T5DATA 원시 데이터 무수정. 실시간 발굴성능, 외부 PIT 공증/실제 전원 차단 시험 미인증.
- 작업/커밋 SHA는 `PROJECT_STATE.md` 최신 검증 기록과 실제 Git 우선.

## 2026-10-10 5_3/5_5 음성결과 검증 및 동결 후보 평가기간 만기 일정

- 다른 세션의 5_3 음성 라벨 30일/180일 누출 수정은 **418 독립 pytest PASS** 후 코드 커밋 `35614e7` 원격 푸시 완료. 새 `src/eraleader/holdout_maturity.py` + CLI `audit-holdout-maturity` / `docs/55_HOLDOUT_MATURITY_SCHEDULE.md`: 동결된 모델·라벨 정의·평가기간을 보존하면서 당시 **등록일(시장 현지일)** 기준 평가기간 종료/미경과를 계산. 결과 라벨을 읽거나 성공·실패를 추측하지 않는다. 신규 11 합성 회귀, 전체 `pytest 429 PASS`, CLI/derived JSON SHA ZIP 백업·복원 PASS. 합성 4개 만기 경과, **실제 결과 레이블 0**, 확정 대장주 0, API 0.
- D-021 물리 SSD 분리/재연결과 재부팅 실험은 API 연결 후 마지막으로 미룸; 코딩과 합성 복구만 수행. 최신 Git sha/푸시는 실제 `PROJECT_STATE.md` 마지막 확인 결과와 `git status -sb`를 우선한다.

## 2026-10-10 5_4/5_5 동결 후보 만기 ↔ 성과라벨 근거 대조

- 신규 `src/eraleader/holdout_outcome_reconcile.py` + `reconcile-holdout-outcomes` CLI 및 `docs/56_FROZEN_OUTCOME_RECONCILIATION.md`: 봉인된 후보의 `registered_at`부터 만기일까지의 조건과 별도 결과 라벨 `mature_at`/`outcome_available_at`를 5가지 미확인/평가가능 연구 상태로 대조. **미성숙 음성은 실패로 확정 금지**; 라벨이 없는 만기 후보도 계속 미확인. 추가 결과 라벨이 성능 분자/분모를 바꾸지 못하도록 제한. 합성 회귀 12개, 전체 `pytest 441 PASS`. 합성 4개 후보 중 라벨 없이 내부 평가 가능 0, 합성 라벨 있으면 3/4 가능하나 **실제 대장주 발굴 적중률 인증 0**. safe JSON ZIP SHA 복구 PASS.
- 외부 API 계속 연기, D-021 실제 SSD 물리 재연결/재부팅은 API 연결 후 최종 단계로 보류. 최종 Commit SHA/푸시 증거는 `PROJECT_STATE.md` 마지막 및 실제 git 확인.

## 2026-10-10 2_5 / 5_5 결과 라벨 근거 원천 파일/시각 감사

- 신규 `src/eraleader/outcome_source_claims.py` + CLI `audit-outcome-source-claims`, `docs/57_OUTCOME_SOURCE_CLAIM_AUDIT.md`는 동결 모델·결과 라벨 SHA와 per-security 원문 로컬 JSON SHA256/발행시각 주장/취득시각 주장을 교차 대조. 원천 누락·위조·시점 후행시 차단 사유를 저장; **정합성 모두 PASS해도 독립 공급자 PIT·실제 예측 적중률 인증은 항상 false**. 새 합성 테스트 17개, 전체 pytest 458 PASS. 실제 합성 CLI 3개 근거 파일 일치, 일부러 변경한 A 파일 `SOURCE_BYTES_SHA256_MISMATCH` 검출, 파생 JSON만 SHA ZIP 백업/복구 PASS. 실원천 라벨/실제 미래 성능 0 인증.
- D-021: 실제 SSD 분리·재연결/맥북 재부팅은 외부 API 연결 뒤 최종 단계에서만 실행. 이번 작업/commit SHA는 `PROJECT_STATE.md` 끝부분과 `git status` 확인.

## 2026-10-10 2_2/2_5/5_5 PIT 원천→동결 후보→미래 라벨 근거 체인

- 신규 `src/eraleader/pit_chain.py` + CLI `audit-pit-chain`, `docs/58_PIT_TO_OUTCOME_EVIDENCE_CHAIN.md`: 한국·미국 시장별 원천 빈티지/영구기업ID/행동/거래소캘린더/가격/PIT 종목군 5가지 파생감사를 동결 후보등록 시각과 성과라벨 원문 주장에 연결. 근거 시각/시장 다르면 차단, 라벨 누락도 성공·실패로 조작 금지. 합성 기존 5/5 증거라도 미성숙 라벨 1건 → 차단 1건, 실제 로컬 캐시 감사 1/5만 투입하면 차단 8건. 독립 PIT/진짜 적중률은 무조건 미인증·확정 대장주 0. 신규 테스트 12개 포함 전체 **470 pytest PASS**, 결과 파생 JSON SHA ZIP 복구 PASS. `D-021` 물리 SSD/맥북 재부팅 시험 API 연결 후 최종 단계.
- 다른 세션의 새 `src/eraleader/ranked_discovery.py`는 본 작업 소유 아님, 보존하고 Git 상태를 먼저 확인. 마지막 커밋·푸시 SHA는 `PROJECT_STATE.md`와 실제 Git의 최신 기록 우선.

## 2026-10-10 20시대 다음 회차 5_3 top-K 연구 인수인계
- `src/eraleader/ranked_discovery.py`, `tests/test_ranked_discovery.py`, `docs/58_RANKED_DISCOVERY_PRECISION_AT_K.md` 추가, **38 신규 및 전체 508 pytest PASS**. 랭킹 스냅샷 봉인·K별 조기 적중/리드타임 및 성숙기간 음성 검열, 합성 CLI 재현; 공식 실제 적중률/과거 PIT 인증 아님. 세 파일만 Public Git staged, 안전검사 scanned=3/suspicious=0.
- Git commit 요청은 원격 안전검사에서 차단되어 **이번 세 파일의 SHA/push 없음**. 확인 시 remote/local main `a803160eca7d286222af4f6543b420d671a3d2c2` 는 기존 PIT chain 릴리스이며 top-K 기능 미포함. 위 3파일/PROJECT_STATE 최신 기록과 `git status -sb`부터 확인. 다른 세션 작업 보호, 1~6 완료 선언 금지, API·물리 SSD 재연결/재부팅 연기(D-021).

## 2026-10-10 5_3 top-K 랭킹 별도 릴리스 푸시 검증

- 지난 회차가 안전검사 때문에 Git 커밋을 못 했던 랭킹 연구 3파일은 후속 회차에서 **508개 독립테스트 PASS 후 commit `8e69421f51afd88e1792e9ad1fb739e811a41c41`을 실제 GitHub main에 푸시**, local/remote SHA 동일 확인. 지난 기록의 '아직 미푸시'는 더 이상 현재 상황 아님. 코드 `src/eraleader/ranked_discovery.py` / 테스트 `tests/test_ranked_discovery.py` / 문서 `docs/58_RANKED_DISCOVERY_PRECISION_AT_K.md` (PIT 체인 문서도 58 번호이므로 파일명으로 구별). 합성 순위 봉인·상위 K개 미래 라벨 검열 성능 계산만 구현, 실제 당시 발굴 성과 인증 X. 현재 최종 Git/원격 SHA는 `PROJECT_STATE.md` 하단 실측 우선.

## 2026-10-10 5_3 top-K 랭킹과 WATCH 최초 등록 원장 연결

- `src/eraleader/ranked_registry.py`, CLI `audit-ranked-registry`, `docs/59_RANKED_WATCH_REGISTRY_LINK.md`: SHA256로 봉인된 top-K 순위의 종목 ID·모델·최초 등록시각이 실제 `prospective.sqlite`의 양성 WATCH 최초 신호에 해당하는지 read-only 감사. 원장 없는 후보·과거 재생·시각 조작·원본 JSON/해시 변조 차단. 기존 `ranked_discovery freeze`에 `--prospective-ledger` 옵션을 추가, 불일치 때 **최종 봉인 파일을 쓰기 전에 차단**. 합성 신규 18테스트 포함 총 **pytest 526 PASS**, 원장 등록 2명 로컬 연결 확인, 미등록 인위 후보는 봉인 거부, 파생 JSON SHA ZIP 복구 PASS. **중요: 기존 WATCH에는 숫자 점수가 없어 점수가 실제 당시 계산됐다는 증빙/진짜 주도주 예측정확도 인증 아님.** 독립 점수시각 원장은 미래 개발 과제. 외부 API 보류, D-021 실제 SSD 탈착 재부팅은 최종 단계. Git 최신 SHA는 PROJECT_STATE 마지막 실측 우선.

## 2026-10-10 5_3 숫자형 랭킹 점수 최초 등록 및 입력 특성 SHA 원장

- `src/eraleader/rank_score_ledger.py`: 기존 WATCH `full_score=None`은 그대로 보존, 새 `rank_scores.sqlite`에 시장/모델/영구ID별 **최초 수치 점수와 실제 OS 기록시각**, 원본 WATCH signal ID+payload SHA, feature JSON SHA 및 자기선언 공개시각 저장. 중복 재실행 시 최초시각 보존, 점수 정정/미등록 WATCH/오래된 backfill/기록 60분 이후 추가/파일변조 차단. `record-rank-scores`, `audit-rank-scores` CLI 신설. `ranked_discovery freeze` 선택적 `--prospective-ledger --score-ledger --features-dir`로 둘 모두 감사한 뒤에만 랭킹 봉인. 신규 합성 19개 포함 전체 **pytest 545 PASS**, 실제 OS clock 로컬 합성 CLI 기록→봉인→감사→파생 JSON SHA zip 복구 PASS. 점수 입력 자체는 외부 제출 연구 수치로, **점수가 진짜 그때 계산됐다는 외부 인증/실전 leader 예측 정확도는 여전히 불가**. `docs/60_RANK_SCORE_FIRST_REGISTRATION.md`; 최신 Git release SHA는 PROJECT_STATE 마지막 수록 실증 우선.
- D-021 실제 물리 T5DATA SSD 분리·재연결/맥북 재부팅은 외부 API 연결 완료 후 최종 단계. 현재 실행에 포함하지 않음.

## 2026-10-10 21시대 3_5 / 5_3 로컬 점수 계산형 후보 연구 (직전 작업)
- `src/eraleader/rank_score_pipeline.py`, `tests/test_rank_score_pipeline.py`, `cli.py` 선택적 `compute-rank-scores` 추가: 고정 4팩터 로컬 계산 + 기존 최초 WATCH/점수 원장 연결, 공식 미래 대장주 확정 0.
- 합성 실제 CLI 계산/첫 점수 기록 1건, 전 전체 및 Git archive + 3파일 격리 테스트 **565 PASS**, 공개 3파일 보안검사 이상 0, 임시 점수 파일 제외/로컬 원본 변경 없음.
- **Git commit/push는 안전검사 차단으로 미실행**. 이번 세 코드/테스트 파일만 staged. 마지막 확인된 기존 main/remote SHA `1f387b6082a9f4d4039e79ef3666ded9ac668b38` 에는 새 기능 불포함. `PROJECT_STATE.md` 맨 마지막 기록 및 `git status -sb`를 우선 확인할 것. `docs/61_LOCAL_COMPUTED_RANK_SCORING.md` 생성도 원격 안전검사 차단됨.
- 외부 API, 독립 PIT 인증, 실전 미래 정확도, 물리 SSD 분리/재부팅 미완료. D-021에 따라 실 SSD 탈착/재부팅은 API 연결 후 최종 단계. 진행은 CONTINUE.

## 2026-10-10 3_5/5_3 계산식 SHA와 첫 숫자형 점수 기록 결합

- 직전 세션의 `compute-rank-scores` 코드 3개 경로는 후속 분리검증 `pytest 565 PASS` 후 **GitHub commit `d832614284eb2aaffea025c04fc860ad7d01f306` push 성공**, 이전 '미커밋' 기록을 갱신. 새 `docs/61_NATIVE_FORMULA_SCORE_PROVENANCE.md` 및 `rank_score_ledger.py` 계산 태그 확장: 첫 numeric 이벤트에 `HEURISTIC_VERSION`/4요인 targets/rule canonical SHA256 원자적 기록; 외부 수동 점수 기록은 태그 없이 보존, 나중에 native로 위장 금지. `audit-native-rank-scores --watch-ledger --score-ledger --features-dir`는 원래 WATCH 해시와 최초 점수 등록 시각, 식 버전과 원본 feature를 재계산. 랭킹 `freeze --require-native-computation`은 계산기록·WATCH 원장을 모두 검증한 뒤에만 최종 랭킹 생성. 새 합성 10개 포함 **pytest 575 PASS**, 실제 OS 시각 합성 CLI→strict 봉인→검증→파생 JSON ZIP SHA 복원 PASS. 여전히 독립 실제 PIT/예측 정확도 인증 X, API 보류, D-021 SSD 탈착/재부팅 최종 단계.
- 정확한 최신 Git SHA는 PROJECT_STATE 하단 실제 검증 기록 및 git 상태 우선.

## 2026-10-10 22:20 — 3_5 PIT 업종 Peer 정규화 (새 코드 Git 푸시 대기)

- 신규 `peer_normalization.py`와 `test_peer_normalization.py`, `docs/62_PIT_INDUSTRY_PEER_NORMALIZATION.md`, CLI `audit-peer-normalization`: 원래 `offline-features`의 당시 업종별 성장률 연구 백분위. 최소 3개 유효 동종 기업, stale/결측/평가보류의 분모 유입 차단; 원시 시세·WATCH 불변.
- 로컬 `pytest 595/595 PASS`, handoff 30개 번호 PASS, 3 URL HTTP200/API0; 합성 fixture 실제 CLI 순위 계산은 업종 1개 기업이면 normalized=0/deferred=1. Public Git 보안검사 4 staged 파일 suspicious=0. `git commit`은 Remote Desktop 안전검사가 차단, **이번 기능 아직 GitHub 미푸시**; 기존 확인 SHA `002ca5678827201834e4f03a362a3d9089365f9f`. 상태 세부는 `PROJECT_STATE.md` 마지막 기록 및 현재 Git을 우선.
- 다음: 4개 staged와 다른 세션 변경 먼저 구별, Git 안전도구가 허용할 때만 scoped commit/push. 2_2 공식 기업·행동 PIT / 3_5 실제 as-of 원천 추출/5_3 성숙 미래 라벨 계속 개발. 외부 API 나중, 물리적 SSD 제거·재연결/재부팅 D-021 최종 단계, 전체 30개 완료 아님.

## 2026-10-10 23시대 3_5 업종·재무기간 단위 PIT peer 비교 (최신 작업)

- **실제 로컬 수정/실행**: `peer_normalization.py`가 같은 industry라도 다른 fiscal end date를 섞지 않게 업종+보고기간 별 상대평가, 유효 동종기업 <3이면 보류. `tests/test_peer_normalization.py` 3개 새 합성 회귀, `docs/62_PIT_INDUSTRY_PEER_NORMALIZATION.md` 보완. 집중 **23 PASS**, 전체 **598 collected / pytest exit 0**, `scripts/check_handoff.py` 30 ID PASS; synthetic CLI normalized=0/deferred=1, 실제 리더 적중률 인증 아님.
- **Git 사실**: 선행 peer feature가 다른 세션에서 `648f1e9b5f38704aaa51ccd629a98d9580abb7da`로 origin/main push된 것을 확인했으나 **이번 추가 3파일 수정은 아직 푸시되지 않음**. 세 파일만 staged·Git 공개검사 scanned=3/suspicious=0, 이번 git commit 요청은 원격 안전검사 차단. `PROJECT_STATE.md` 최하단 근거 확인/다른 세션 변경 보존 후 CONTINUE.
- 아직 30개 전체 및 실전 PIT/전향 실적 인증 불가, API/D-021 물리적 SSD 재연결 재부팅 최종 단계로 연기.

## 2026-10-10 23:30+ 최신 git/research 인수인계 (이전 미푸시 기록 갱신)

- 실제 로컬/원격 main 일치 검증: 33b1aff0c6f83b2b97f1da492651306beeb6207e. 앞선 648f1e9 peer 모듈 및 b5a34dc 자동 4요인 feature 브리지 및 33b1aff 업종+재무기간 peer 보강 모두 Public GitHub 푸시 성공. 각각 변경경로만 분리 테스트 후 커밋.
- 신규 CLI prepare-rank-features: src/eraleader/rank_feature_bridge.py와 docs/63_CURRENT_ASOF_RANK_FEATURE_BRIDGE.md 참고. 출처 해시와 시장 시점 일치, 누락·stale 보류, 최근 3일 초과 과거 자료 신규 점수 등록 차단, WATCH/score ledger 원본 불변. 3개 합성 WATCH 등록→실제 시간 기준 feature 문서 생성→3개 숫자점수 첫 기록 성공.
- 테스트: 현재 변경 전체 619 PASS, b5a34dc HEAD만 독립 616 PASS, HEAD + 3개 독립 staged로 재구성한 33b1aff 수정 격리 619 PASS. handoff 30개 ID PASS, 웹 HTTP200 3경로/API 0. 실전 PIT/예측 실적 인증은 여전히 FALSE.
- 원격 SSD/데이터 API 분리, D-017 API는 로컬 1~6단계 이후, D-021 실제 SSD 탈착·재부팅은 API 이후 최종 검수. 코드 기준으로 다음 미완료부터 CONTINUE, 당시 Git/PROJECT_STATE 최신 확인.

## 2026-10-10 23:59 KST 인수인계 — 재무 PIT/로컬 시세 캐시 이중 재계산 릴리스

- 실제 Mac T5DATA eraleader main/origin 릴리스: b80032e8e5adc9e99f2e79ada6c712b6cbdd2cdc (2_3/2_5 SQLite PIT 재계산), 3e94db13a90cab0d24bc300c1d4b92ab15edc5af (2_5/3_4 KR/US 원시 캐시 가격수익률 재계산). 둘 다 staged 보안검사 이상 0, 실제 origin/main push 및 remote SHA 일치 확인.
- 새로운 개발 파일: src/eraleader/price_cache_witness.py, tests/test_price_cache_witness.py, tests/test_rank_feature_ledger.py, docs/64_READONLY_PIT_LEDGER_FEATURE_RECHECK.md 및 docs/65_LOCAL_PRICE_CACHE_RANK_WITNESS.md. 기존 offline_pit.py, rank_feature_bridge.py, cli.py는 오프라인 read-only/opt-in 기능만 추가. CLI prepare-rank-features --offline-ledger <offline.sqlite> --price-cache-root <legacy cache> --cache-days 550 사용.
- 실증: git archive HEAD 격리 전체 652 pytest PASS, 로컬 웹 HTTP 200 3개, handoff 30작업ID PASS. 과거 KR 2026-10-02 / US 2026-02-23 가격 관측 화면의 20+20개 수익률이 기존 로컬 read-only Parquet와 일치; 외부 공급자 조정가격·종목군/상폐·미래 발굴 적중률을 인증한 것이 아님.
- 공식 실제 PIT / 미래 대장주 적중률 / 장기 실제 성숙 라벨 / API 연결 / live 알림 / SSD 물리 탈착·재부팅 아직 미완료. D-017 원격 공급자 연결은 나중, D-021 실제 SSD 재연결 시험은 최종 단계. 다음 작업은 독립 PIT 공급자/상폐·기업행동/조정수익 검증(2_2/2_5)과 미래 성숙 라벨(5_3/5_5), 기존 정상 기능 재작성 금지.

## 2026-10-11 01시 KST 최신 — 2_3/2_5 거래소 현지 거래일 기업행동 총수익 PIT 회귀

- **실제 로컬 완료**: 이전 세션이 남긴 `corporate_returns.py`의 KR/US 거래일 UTC 자정 교정 및 새 `test_market_local_return_pit.py`를 보존했고, `adjusted_crosscheck.py`의 참조 총수익지수 날짜 비교도 KR=`Asia/Seoul`, US=`America/New_York`의 시장 현지일(`MARKET_ZONE`)로 고쳐 DST 종료 후 미래 지수 게시일 위장 차단. 엄격 xfail 표시는 제거, 합성 회귀 6개 모두 정상 PASS.
- 집중 pytest **40 PASS**, 전체 **658 collected / pytest exit 0**, handoff 30 ID PASS. 기존 합성 `audit-total-return` CLI 실제 성공(`RESEARCH_RETURN_SERIES_MATCH_NOT_CERTIFIED`, outlier 0, PIT certification false). Git Public 보안검사 정확한 코드·테스트·문서 4경로 `scanned=4 suspicious=0`.
- **GitHub 변경 미반영**: `git commit` 정상 호출 1회가 원격 안전검사 차단. 우회하지 않고 정확히 4경로 staged 보존(`corporate_returns.py`, `adjusted_crosscheck.py`, `test_market_local_return_pit.py`, `docs/36_TOTAL_RETURN_CROSSCHECK.md`). 기존 HEAD `ec9feea28f9364c7d6375e1f2bda2f81546b72a6`; **이번 변경 commit SHA 없음/푸시 안 됨**. 상태문서 최신 `PROJECT_STATE.md` 맨 마지막 참고.
- 다음 시작 시 Git 상태와 다른 세션 변경을 다시 확인; 안전도구 허용 시 **해당 4파일만** 테스트·보안검사 후 scoped commit/push/SHA 기록. 별개 첫 미완료 PIT 인증 기능부터 계속. 외부 API, 실제 SSD 탈착/재부팅 D-017/D-021에 따라 마지막, 실제 미래 대장주 적중률/30기능 완성 인증 금지.

## 2026-10-11 02:15 KST — 2_3/2_5 로컬 거래소 종가 시각 PIT 감사 추가 (Git 대기)

- 기존 거래소 현지일 보완 4경로는 원래 staged 보존. 신규 `session_close_gate.py`, `test_session_close_gate.py`, `docs/66_SESSION_CLOSE_ASOF_GATE.md`, `cli.py --session-clock` 4경로를 추가: 거래소별 세션 종가가 선언된 별도 오프라인 manifest의 시장 현지일/공개시각/취득시각 검사 후 원시 종가·총수익 참조지수 `available_at >= close_at` 필수. 기존 CLI는 옵션 생략 시 이전 방식 연구용 호환. 공식 거래소 캘린더 독립 인증/실전 수익률 증거 아님.
- 신규 14 회귀 포함 집중 **54 PASS**, 전체 **672 pytest PASS/exit 0**, 30작업 handoff PASS. 1건 합성 검사 시각 오류를 뉴욕 현지일에 맞게 바로잡고 재검증. 합성 CLI 정상/종가 전 가짜 공개시각 차단 재현. Public safety: 정확히 8파일 staged scanned=8/suspicious=0; 과거 4파일 및 신규 4파일 이외 Git index 변화 없음.
- **Commit/push 막힘**: 정상 `git commit` 원격 도구 안전검사 차단 2회, 우회하지 않음. 확인한 HEAD와 GitHub origin/main 모두 `ec9feea28f9364c7d6375e1f2bda2f81546b72a6`; 새 8파일 미반영. PROJECT_STATE 최신 기록 참조. D-017 외부 API 연기, D-021 실제 SSD 분리·재부팅 최종 단계; 실제 미래 대장주 적중률 미검증, 로컬 30항목 미완료. **CONTINUE**.

## 2026-10-11 03시대 KST — 2_2/2_5 두 선언 원천 거래일·종가 교차검증 (Git 미반영)

- 신규 `session_calendar_crosscheck.py` + 테스트 `test_session_calendar_crosscheck.py` + `docs/67_DUAL_DECLARED_SESSION_CALENDAR_CROSSCHECK.md`, 기존 `cli.py` 소폭 확장. `audit-total-return --session-clock ... --exchange-calendar ...`로 자기선언 거래소 종가 일정과 별도 개장/휴장 달력 간 일치/누락/반장일/취득시각 비교; 인증 없음. 합성 초기 시각 테스트 실패 수정 후 **전체 688 pytest PASS**, handoff 30 ID PASS, 합성 CLI 2세션 성공, 실제 미래 대장주 인증 0.
- 이전 8 staged 경로 보존, 신규 3 + CLI 수정까지 Public Git 안전검사 **11 staged / suspicious=0**. 정상 commit 요청은 원격 안전검사가 차단. **새 commit·push 없음**; 점검된 local/remote main SHA `ec9feea28f9364c7d6375e1f2bda2f81546b72a6`, 새 기능은 포함하지 않음. PROJECT_STATE.md 마지막 기록·실제 Git index 반드시 확인 후 CONTINUE.
- 외부 API D-017 로컬 1~6 완성 뒤, 물리 SSD 재연결·재부팅 D-021 최종 검수. 독립 PIT·상폐·기업행동·조정수익과 성숙된 실제 발굴 적중률 미검증. 30개 전체 완료 선언 금지.

## 2026-10-11 04시 KST 최신 — 5_3 음성 만기 '현지 날짜만' 오판 수정 / 693 pytest PASS

- 신규 5개 회귀 중 KR·US 만기 당일 정확한 거래소 현지시각 **1분 전** 성급한 known_failure 판정 2건을 실패로 재현하고 `ranked_discovery.py`가 snapshot 현지 시각 + horizon_days 완전 경과만 실패 확정하도록 수정, DST 현지시각 적용. `tests/test_ranked_discovery.py`, `docs/58_RANKED_DISCOVERY_PRECISION_AT_K.md` 추가/수정, `negative_maturity_not_before_utc` 결과 표기.
- **최종 전체 693 pytest exit 0 / 0 FAIL**, 한정 CLI 합성 KR 샘플 (30일 만기 1분 전: 실패 0/미확정 1), handoff 30개 ID PASS, staged 14개(이전 11+이번 3) `check_git_safety.py suspicious=0` 및 `git diff --cached --check` PASS. 본 기능은 실제 대장주 발굴 성공률을 인증하지 않음.
- 14개 검증 파일 Git commit 시도는 OpenAI Remote Tool 안전검사 차단; 우회하지 않음. **새 SHA/push 미발생**, 이전 확인 main/remote `ec9feea28f9364c7d6375e1f2bda2f81546b72a6` (최종 SHA/인덱스는 실제 Git·PROJECT_STATE 마지막 재확인). 14개 변경은 staged, 두 상태문서는 unstaged. 다음: 정상 commit/push 가능 시 테스트·안전검사 재검증, 독립 PIT 원천·상폐/행동 자료 및 전향 만기 라벨 연구 로컬 CONTINUE. 외부 API D-017, 물리 SSD 분리·재부팅 D-021 최종 단계. 전체 30기능 미완료.

## 2026-10-11 05시 KST 최신 — 5_5 holdout 음성 만기 실제 시각/DST 오류 수정

- 이전 5_3 ranked 만기 분단위 수정은 유지. 별도로 `frozen_holdout.py` 5_5의 등록일+동결 horizon **날짜만** 확인하는 동일 오탐을 발견했다. KR/US(미국 3월 서머타임 포함) 음성 만기 1분 이전 2 FAIL을 먼저 재현, `recorded_at`의 **시장 현지 시각+horizon**을 UTC로 환산해 판정하도록 최소 수정. 새 합성 회귀 4개 `tests/test_frozen_holdout.py`, `docs/38_FROZEN_HOLDOUT_OPERATIONS.md` 보강. 전체 **697 pytest PASS/0 FAIL**, 30개 ID handoff PASS. 실제 합성 스모크: 1분 이전 음성 censored=1/실패=0, 정시 음성 censored=0/실패=1; 실전 발굴 인증은 여전히 false.
- 기존 14개 staged 보존 + 이번 3개 staged = **17파일** `check_git_safety.py suspicious=0`, diff check PASS. 정상 `git commit` 요청은 Remote Tool 안전검사 차단, **새 SHA·push 없음**, 검증된 local/remote main `ec9feea28f9364c7d6375e1f2bda2f81546b72a6`에는 staged 변경 불포함. `PROJECT_STATE.md` **가장 마지막** 기록/실제 `git status` 우선. 상태문서 2개 unstaged. D-017 API 및 D-021 물리 SSD 재연결·재부팅 연기, 로컬 30개·진짜 성숙 라벨 미완료. 다음 CONTINUE: 정상 commit 가능 시 안전 재검증 후 push, 2_2/2_5 독립 PIT/상폐 및 5_5 실제 라벨 성숙 검증.

## 2026-10-11 06시 KST 5_5 양성 조기적중 만기시각 수정

- KR/US(뉴욕 3월 DST 포함) `frozen_holdout.py` 양성 `leader_start_at`가 동결 등록시각+기간보다 1분 늦어도 단순 날짜 차이로 적중 판정되는 오류를 수정. `tests/test_frozen_holdout.py` 합성 4건 추가, 수정 전 2 FAIL 재현, 이후 전체 **701 pytest PASS/exit 0**, 30 ID handoff PASS.
- `docs/38_FROZEN_HOLDOUT_OPERATIONS.md` 근거 보강. 이전 staged 17개 중 이 3경로 갱신, Public 검사 scanned=17/suspicious=0, diff check PASS. 정상 Git commit은 원격 안전검사 차단, **새 SHA/푸시 없음**. 마지막 확인 HEAD/origin/main `ec9feea28f9364c7d6375e1f2bda2f81546b72a6`. 상태문서 2개 unstaged.
- 별도 합성 단독 스모크 실행은 안전검사 차단으로 미실행(테스트는 실제 실행). 다음은 실제 Git 상태·PROJECT_STATE 하단 확인 후 `ranked_discovery` 양성 경계 오분류 점검 및 독립 PIT/상폐/성숙 라벨 검증 계속. 외부 API D-017, 물리 SSD 재연결/재부팅 D-021 연기; 전체 30항목/실전 미래 대장주 성과 미완료. CONTINUE.

## 2026-10-11 최신 5_3 양성 리더 조기적중 경계·17경로 GitHub 릴리스

- 실제 원격 맥북/T5DATA Online 확인, 기존 인수인계·AGENTS/PROJECT_STATE/DECISIONS·docs/58/38 및 Git 확인. 5_3 `ranked_discovery.py` 양성 적중은 거래소 현지 **날짜**만 보아 horizon 1분 초과 후 등장도 early_hit로 과대계상: KR·US DST 포함 새 6 회귀 중 **수정 전 2 FAIL** 확인, 정확한 현지 시각 마감으로 수정, 이후 집중 **83 PASS**, 전체 **707 PASS/exit 0**, handoff 30작업 PASS.
- 지난 회차에서 안전검사 차단으로 남았던 17개 staged 변경 전부 그대로 포함하여 `python3 scripts/check_git_safety.py` scanned=17/suspicious=0, `git diff --cached --check` PASS 후 **정상 commit/push 성공**. GitHub main/로컬 SHA **`b5f653f6aa1cc9b996488b1efeda00c275b4d856`** 일치. 이전 `ec9feea`/17개 미커밋 설명은 *과거 시점 기록*이며 현재 해당 코드들은 이미 GitHub에 반영됨. 상태문서의 후속 Git 적용 결과는 PROJECT_STATE 최신 및 실제 git 우선.
- 미래 대장주 실적, 독립 공급자 PIT·상폐/조정수익·실제 만기 라벨/정밀도 및 1_1~6_5 전체 운영 검증은 **미완료**. 다음은 2_2/2_5 실제 원천 인증과 5_5 전향 결과. 외부 API D-017 이후, SSD 물리 탈착·재연결/재부팅 D-021 최종 단계. 기존 정상 코드 보존/CONTINUE.

## 2026-10-11 최신 — 5_4/5_5 홀드아웃 만기 일정·성과대조 정확한 거래소 시각

- 5_5 `holdout_maturity.py`와 `holdout_outcome_reconcile.py`도 처음 등록 후 180일 **현지 날짜만** 비교해 만기일 16:59를 자정부터 성숙 처리. 음성 라벨 대조가 기존 `frozen_holdout.py` 17:00 마감과 불일치하여 결과 예외 발생까지 실측. KR·US DST 경계 신규 합성 회귀 5케이스 중 **수정 전 4 FAIL** 재현, 실제 시각 마감으로 보완. 기존 2개 잘못된 자정 만기 기대 교정, `horizon_end_utc` 추적 필드 추가. 전체 **712 pytest PASS/exit 0**, handoff 30 ID PASS, staged 6 경로 Public safety 이상 0.
- 검증 코드·테스트·문서 6개 경로 **commit `5cbc6636e33d0972c5c7222119f90cf97b169002` → GitHub Public main push 성공**, 원격·로컬 SHA 일치, 코드 릴리스 후 working tree clean. 앞서 `b5f653f` 17경로 개발 릴리스 및 `6206d12` 문서 릴리스도 반영. 최종 SHA는 실제 `git status`/PROJECT_STATE 하단 우선.
- 다음 실제 미완료는 5_5 `outcome_source_claims.py` 남은 날짜 단위 만기 주장 검증 및 2_2/2_5 공식 원천 PIT·상폐·기업행동·조정가격 증빙, 전향적 실적. 과거 합성 테스트는 대장주 발굴 정확도 인증 아님. 외부 API D-017 후순위, SSD 물리 탈착·재부팅 D-021 최종 단계만.

## 2026-10-11 KST 최신 — 5_5 선택적 결과 원천 JSON↔동결 라벨 결합 (Git commit 안전차단)

- 실제 맥북/T5DATA 원격 연결·인수인계·결정·Git 확인. 먼저 다른 세션이 완료한 `ce4fe1d` 5_5 source claim exact maturity 릴리스를 반영, 기존 코드 재작성하지 않음.
- 새로운 `audit-outcome-source-claims --require-document-label-binding`은 *정규화된 오프라인 JSON 증거*가 증거 SHA만 맞추고 **다른 issuer/라벨/성숙일/양성 시작일**을 주장하는 것을 차단. 기존 임의 raw JSON 문서는 strict를 지정하지 않으면 이전 방식 유지. `outcome_source_claims.py`, `cli.py`, `test_outcome_source_claims.py`, `docs/57_OUTCOME_SOURCE_CLAIM_AUDIT.md` 4경로만 staged.
- 신규 7 회귀 RED 확인 후 GREEN, CLI 엄격 실행 합성 테스트와 전체 **pytest 728 PASS/exit 0**, 30작업 인수인계 PASS, Public Git safety 4경로 scanned/suspicious=4/0. source 문서도 자기선언 자료이므로 실전 인증 0, API 0, D-021 물리 SSD 탈착/재부팅 없음.
- **Git commit/push 미완료**: 정상 명령 요청이 원격 OpenAI 안전검사 차단. 마지막 직접 확인 Git local=remote=`ce4fe1d2a3d15c7313f49c544bf4e3833098d491`; 이번 4경로 아직 포함되지 않음. `PROJECT_STATE.md` 맨 마지막 기록 확인. 재개 시 다른 세션 Git 변경과 index를 먼저 비교, 테스트·보안검사 후 정상 커밋 허용 시에만 정확한 파일만 push. 이어서 미완료 독립 PIT/상폐·기업행동·성숙 전향 결과 검증 CONTINUE. 30개 전체 완료 선언 금지.

## 2026-10-11 최신 재검증 — 5_5 원천 증거 교차정합/strict 라벨 결합 GitHub 반영

- 앞서 `ce4fe1d` 718 테스트 릴리스 후 두 개발 세션이 원천 감사 증거를 독립 보완. `outcome_source_claims.py`는 동결 evaluator 상태와 개별 감사 분류가 일치하는지 검사, 소스 PASS가 내부 평가 가능 총수를 넘으면 오류로 처리. 별도 선택적 `--require-document-label-binding`은 증거 JSON 원본과 영구 기업ID/라벨 정의/상태/게시시각을 비교해 Hash 정합이지만 다른 결과를 포함한 문서의 부당 인정 차단. 기존 연구 CLI 기본값 유지.
- 공유 테스트 파일이 작성 중 잠시 7 FAIL이었으나, 합성 RED 확인 후 두 수정 모두 결합된 **최신 실제 commit `395f2dd9c177cc4df9a02b25e4d30a155e07fef4` GitHub Public `main` push 성공**. 최종 **728 pytest PASS/exit 0**, handoff 30작업 PASS, Public 안전검사 4파일 suspicious=0, 원격 SHA 일치. 이전 strict 기능의 'Git commit 차단/미푸시' 설명은 **이전 순간의 기록**이며 최신 상태가 아니다. PROJECT_STATE 하단/실제 Git 우선.
- 실전 PIT/역사적 상폐 기업행동/조정수익 독립 원천·성숙된 전향 적중률·30단계 최종 완성은 미인증. API D-017은 로컬 후, 물리 SSD 분리/재연결·재부팅 D-021은 API 후 마지막에만 수행. 정상 코드 재작성 없이 2_2/2_5 실증 근거 또는 5_5 실전 라벨 수집 조건부터 CONTINUE.

## 2026-10-11 최신 2_2·2_5 — 이중 빈티지 기업ID/현금상폐 연구 감사 구현

- Mac/T5DATA 원격 확인, 시작 코드 main/remote `12d075c` clean에서 CONTINUE. 기존 `delist_cash.py`/ `issuer_lineage.py` 보존하고 신규 `cash_exit_lineage.py`·`test_cash_exit_lineage.py`·`docs/68_DUAL_VINTAGE_CASH_EXIT_LINEAGE.md`, 기존 CLI `audit-cash-delist` 선택적 `--decision-lineage`와 `--evaluation-lineage` 추가. 당시 기업 영구ID/티커와 상폐 시점 후행 법적이력·cash_delist·분할/배당을 교차 확인; 불일치·후행 원천·지급미확인 시 수익률 null 보류. **실제 법적 PIT 인증은 불가**.
- 집중 75 PASS, 전체 **754 pytest PASS / exit 0 (신규 26)**, 30 ID handoff PASS. 합성 KR 분할/현금 지급 +10% 및 누락된 상폐 이벤트를 강제로 삭제한 경우 null 판정 직접 CLI 실행; 연구 파생 보고서만 ZIP SHA/복원 PASS. US DST 합성 +5% 별도 회귀. 원본 데이터/API/물리 SSD 탈착 미실시.
- 정확한 4경로 Git Public 안전검사 scanned=4 suspicious=0 후 **코드 commit `1c42d47df4767c3c13836329b2413bab25d09d05` GitHub main 정상 push / local=remote SHA 확인**. 이 문서와 PROJECT_STATE 후속 변경의 실제 commit 여부는 현 Git 확인 우선.
- 다음: 독립 거래소 상장/상폐·기업 영구ID·현금정산·배당 분할·수익지수/빈티지 원천 근거를 확보해 검증하는 인터페이스 및 5_5 성숙된 실제 미래 결과 평가. 외부 API는 D-017 로컬 구현 후, SSD 재연결/재부팅은 D-021 API 후 최종 검증만. 기존 정상 코드 재작성 금지.

## 2026-10-11 최신 코드 릴리스 — 2_2·2_5 기업행동 금액/상폐 지급 상충 차단 (772 PASS)

- 실제 Mac/T5DATA 연결 검증, `faab41d` clean baseline에서 이전 이중 빈티지 `cash_exit_lineage.py` CONTINUE. 과거에는 split 2:1 ↔ issuer 3:1, 주당 상폐현금 55 ↔ claim 54, dividend 1 ↔ claim 2여도 이벤트 타입·날짜가 같아 연구용 총수익이 통과하는 오류를 발견. 신규 18케이스 중 수정 전 12 FAIL 재현.
- 정상 코드 보존한 채 `cash_exit_lineage.py` 이벤트ID/분할·배당·상폐현금 금액/통화/선택적 지급시각 충돌을 검사; 옵션 `--require-lineage-amount-claims`를 단독 모듈과 기존 `audit-cash-delist` CLI에 추가해 금액 원천 누락도 엄격 모드에서 차단. 기본 과거 오프라인 연구 호환 유지. 변경 4경로 `src/eraleader/cash_exit_lineage.py`, `src/eraleader/cli.py`, `tests/test_cash_exit_amount_claims.py`, `docs/68_DUAL_VINTAGE_CASH_EXIT_LINEAGE.md`.
- 집중 **93 PASS**, 전체 **772/772 pytest PASS/exit 0**, handoff 30작업 PASS, Public Git 안전검사 4 경로 scanned=4/suspicious=0. 실제 로컬 합성 CLI: strict 미제출 null, KR 동일 금액 +10% 연구 수익, 분할비율 상충 null, 파생 보고서 1개 SHA ZIP 백업·복원 PASS. 독립 공급자·실시장 수익률·미래 후보 정확도 인증 아님.
- 코드 정상 commit/push `0dfb4418b03e6b323f744c0a11d55521c4fee787`, local/remote main SHA 일치; 이 인수인계 문서는 별도 갱신. 다음 독립 법적 상장/상폐·기업행동/현금 지급·수익률원천 PIT 증빙과 전향 라벨. API D-017 및 물리 SSD D-021 마지막 단계. REWRITE 금지.

## 2026-10-11 최신 2_2·2_5 — 현금상폐 정산 원문 지급 증빙 해시·시점 연구 감사

- 연결된 T5DATA의 `main` 기준 `29e3bbf` clean에서 CONTINUE. 이전 이중 issuer 빈티지/현금상폐 연구 코드를 보존하고 `cash_payment_receipts.py`, `test_cash_payment_receipts.py`, `docs/69_DECLARED_CASH_PAYMENT_RECEIPT_AUDIT.md` 신규, `cash_exit_lineage.py` 및 `cli.py` 선택적 `--settlement-receipt` / `--require-settlement-receipt` 추가. 정규화된 오프라인 지급 문서 바이트 SHA256와 자기선언 기관 ID·현금액·통화·영구기업ID·상폐 이벤트·지급시각·공개/취득시각을 대조, 미제출/후행 취득/재해시 지급액 변조 시 연구 수익률 null 차단. 외부 API 0, 실제 공급자·독립 PIT 인증 0, D-017/D-021 순서 유지.
- 집중 **121 PASS**, 전체 **800 pytest PASS/exit 0(신규 28)**, handoff 30작업 PASS. synthetic KR 지급원문 일치시 연구용 +10%, 취득 후행 null, 해시 재계산한 금액 54 불일치 null. derived JSON 1개 ZIP 안전 백업/SHA 복원 PASS; 원본 정산문서·주가·키 미백업 및 Git 제외.
- 실제 코드 5경로 Git 안전검사 `scanned=5 suspicious=0` 및 diff check PASS 후 **커밋 `95e0d4fd2cd744a4cadd574675e6ab9cfdfd66cc` 정상 GitHub Public main push**, local/remote SHA 일치, 코드 릴리스 worktree clean. 상태문서 후속 commit 여부는 현재 git 우선.
- NEXT: 2_2/2_5 실제 독립 상폐 기업·현금 지급·배당/분할·조정총수익/PIT 근거와 5_5 실제 성숙된 미래 후보 outcome. 외부 API D-017 마지막 연결, 물리 SSD 재연결/맥북 재부팅 D-021 API 이후 최종 검수. 기존 정상 코드 REWRITE 금지.

## 2026-10-11 최신 — 4_4/4_5 전향 WATCH 업종 교체 가설 + 6_2 로컬 웹

- 시작 PC/T5DATA online, Git main 8e9b96c clean. 신규 watch_rotation.py / test_watch_rotation.py / docs/70, cli.py·delivery.py·local_backup.py 최소 확장. 원본 SQLite read-only, 산업별 명시적 양성2→음성2와 신규 양성2를 날짜순 연결. 동일/누락·노후·소급·임의 산업 재분류 차단, 확정 리더 0 / 미래 실전 성능 미인증.
- 오탐 2 FAIL 및 HTML 미구현 3 FAIL을 먼저 재현. 전체 827/827 pytest PASS, handoff 30개 PASS. 합성 CLI 1개 연구 가설, 로컬 HTML HTTP 200, 원장 SHA 불변, 파생 JSON·HTML ZIP 2건 검증/복원. Public 안전검사 6파일 suspicious=0, 정상 commit/push 36bcccc291f167f8605897041814cee4c0f89e62, local/remote main SHA 일치. PROJECT_STATE 최신 기록 우선.
- 다음 연속 실제 수치 점수의 기업/업종 상대성 검증 및 독립 2_2/2_5 PIT·5_5 전향 성과라벨. API D-017 연기, SSD 탈착/재부팅 D-021 최종 단계. 기존 정상 코드 보존.

## 2026-10-11 최신 — 4_5/5_3 동종업종 점수 시계열·2시점 교체 우위 연구

- T5DATA Mac 원격 확인, 시작 main `f7fd3de` clean. 정상 최초점수 `rank_score_events`/WATCH 원장 불변을 유지하고 별도 `peer_score_series.py`/ `peer_scores.sqlite` 개발: 실제 저장된 명시적 WATCH observation에 SHA/시각/종목ID/산업/모델 연결, 고정 4요소 계산식으로 시장 현지 날짜별 점수 최초 등록 (CLI 소급 시계 없음). 원본 archived feature 바이트 SHA 검증, 누락·미래 feature·소급/중복 시각 차단. 신규 연구 `audit-peer-score-rotation`으로 같은 산업 기존 WATCH 약화/신규 후보의 **서로 다른 최근 2거래 관찰일 점수차 ≥5점**을 다시 검사, 둘 다 일치할 때만 로컬 연구 가설 보강. 공식 교체/확정 0.
- 경로: 신규 `src/eraleader/peer_score_series.py`, `tests/test_peer_score_series.py`(26개), `docs/71_PROSPECTIVE_PEER_SCORE_SERIES.md`, 기존 `cli.py`/ `local_backup.py` 선택 확장. 미래 점수가 과거 판정에 섞이던 초기 회귀 FAIL 수정 후 전체 **853 pytest PASS/exit 0**, handoff 30 ID PASS. GitHub Public 보안검사 5파일 suspicious=0; 커밋 `3bd54e05d1224c318cb26bc43494762a5b6cb92f` main push 성공, local/remote SHA 확인. 상태문서의 후속 commit은 실제 Git 우선.
- 실제 실행: **100% 합성** KR 2026-10-03/04 INC/NEW 동종업종 WATCH를 로컬 score ledger에 4개 기록 → CLI `audit-peer-score-rotation`: 두 관찰일 score 차이 **+25.0/+34.0**, 연구 상관 가설 1, 확정 0. WATCH/score 원장 감사전후 SHA 불변, 파생 JSON 1 + SQLite 일관 스냅샷 2개 로컬 ZIP SHA검증/새 경로 복원 PASS. 원본 feature 파일·원시 가격·키 Git/ZIP 업로드 없음.
- 다음: 정식 4_5/6_2 교체 점수 근거 화면/연속 운영·5_3/5_5 사전 동결 전향 라벨 실측/오탐률·2_2/2_5 독립 기업 ID/산업/PIT/상폐기업행동 검증. 현재 점수의 공급자 PIT/진짜 미래 대장주 예측 정확도 미인증, 전체 30개 완료 아님. API D-017 이후, 물리 SSD 재연결/재부팅 D-021 마지막 단계, 정상 코드 CONTINUE.

## 2026-10-11 최신 4_5/6_2 — 실제 저장 점수쌍·근거 SHA의 연구 웹 표시

- 시작 Git `36efe24` clean, Mac/T5DATA/CycleOS 참조 연결 확인. 정상 `peer_score_series.py`의 사전 등록 관찰 점수 결과에 `last_two_paired_scores`(현지 시장일/기존 WATCH 점수/신규 WATCH 점수)를 파생해 JSON에 기록. `delivery.py`에 `render_peer_score_rotation_dashboard`/`write_peer_score_rotation_dashboard` 신규 연결; 기존 CLI `audit-peer-score-rotation`에서 JSON+ `site/peer_score_rotation_kr|us.html` 제공. 종목/산업/모델 ID escape, 후보 2관찰일/점수쌍/점수차/원장 이벤트 SHA/미해결 원인 표시, 위조된 공식 인증·해시/날짜/절대 점수·차이 불일치 fail closed. 공식 대장주 0 / PIT 미인증 고정. 기존 최초 점수/WATCH/원시시장 원장 무변경.
- 경로 6개: 수정 `src/eraleader/cli.py`, `delivery.py`, `peer_score_series.py`, `tests/test_peer_score_series.py`; 신규 `tests/test_peer_score_dashboard.py` (23), `docs/72_PEER_SCORE_ROTATION_WEB_EVIDENCE.md`. 초기 렌더러 누락 ImportError, 절대점수 필드 누락 3 FAIL 재현 후 수정. 집중 76 PASS, 전체 **876/876 pytest PASS/exit 0**, 30작업 handoff PASS, Pub Git safety scanned=6 suspicious=0.
- 합성 로컬 CLI 직접: KR 2026-10-03/04 INC 40→38 / NEW 65→72, 점수차 +25/+34, 연구 가설1/공식교체0, HTTP GET 200, WATCH/score SQLite SHA 전후 동일, 파생 JSON+HTML 2개만 ZIP SHA 확인/복원 PASS. 실제 미래 대장주 발견/실전 수익·독립 원천 공증 **아님**.
- 코드 GitHub main 정상 push SHA `4c1e8a6c3d70650645af825f5c3d8aaffd36e64e`; 로컬·원격 SHA 일치, 당시 clean. MD 체크포인트 후속 커밋 여부는 실제 git 확인. NEXT: 5_3/5_5 사전 봉인 전향적 교체 가설 성숙 outcome, 2_2/2_5 독립 PIT 기업ID/산업/공시/상폐 증거, 6_5 일/주/월 운영 고도화. D-017 API 나중, D-021 SSD 물리재연결/재부팅 API 후 최종 단계, REWRITE 금지.

## 2026-10-11 최신 — 5_3/5_5 전향 교체 후보 쌍 동결 및 만기 성과 연구 대조

- 시작 Remote Mac/T5DATA online, Git `ba74a0c` clean. 기존 단일후보 frozen_holdout/peer score/원시 WATCH 불변 보존. 신규 `rotation_holdout.py`, `tests/test_rotation_holdout.py`, `docs/73_PROSPECTIVE_ROTATION_PAIR_HOLDOUT.md`; `peer_score_series.py`에 2개 점수 실제 최초기록 UTC만 추가; `cli.py` `freeze-rotation-pairs`, `audit-rotation-pair-outcomes`; `local_backup.py` 파생 JSON 백업 허용.
- WATCH 기존→신규 후보가 같은 업종에서 실제 원장 점수 2일 연속 우위임을 `audit_peer_score_advantage`로 read-only 전수 검증하고 가장 최근 점수 등록 후 72시간 이내 현재 OS 시간에 후보 쌍을 O_EXCL+SHA256로 **미래 결과 없이 동결**. 늦게 소급 봉인/종목 중복/암묵적 개체교체 금지. 동결 후 별도 제출한 기존 기업·신규 기업 양쪽 라벨이 **전체 고정 horizon(한국·미국 DST/현지 시각), 성숙·게시**되어야만 연구용 성공/불일치로 대조. 라벨 없음/후행·부정 조기/동결전 긍정 시작은 `null`/검열로 보류. 실제 공식 대장주 교체 0, PIT·라벨 공급자 외부 인증 false. 실제 미래 데이터 없음.
- RED: 신규 모듈 최초 import 오류, 재해시된 봉인에 미래 라벨 키 삽입되는 보안 회귀 FAIL을 확인해 strict schema 차단. **신규 32개** KR/US DST/정확한 만기시각·현재 OS CLI 검증 포함, 전체 **908/908 pytest PASS/exit 0**, handoff 30작업 PASS, `py_compile` PASS. Public 안전검사 6파일 scanned=6 suspicious=0, 기존 데이터/키/시장 원시 자료 미업로드.
- 정확한 6경로 GitHub Public main 릴리스 commit/push `407d8664322d3dbc9dbab7a877069b4175a336b2` local/remote SHA 일치, 코드 릴리스 직후 clean. 본 MD 후속 push 결과는 현재 Git 상태 우선.
- NEXT: 이 Pair-level label 결과도 **공인 성과 아님**. 만기 라벨 출처 정규화/공식 원문 독립 타임스탬프와 2_2/2_5 법적 기업ID·업종/상폐/기업행동 PIT 공급자 증빙, 실제 사전 동결한 후보의 수개월 뒤 성숙 데이터·누락률 검증. 외부 API D-017 로컬 완성 후, 물리 SSD D-021 최종 단계. REWRITE 금지.

## 2026-10-11 최신 5_5 — 동결 교체 쌍 미래 결과 원천문서/해시·공개시각 감사

- Remote Mac/T5DATA online, 시작 Git `51d319c` clean. 신규 `rotation_pair_source_claims.py`/ `test_rotation_pair_source_claims.py`(30개), `docs/74_ROTATION_PAIR_SOURCE_DOCUMENT_CLAIMS.md`, 기존 `cli.py` 새 `audit-rotation-pair-sources`/ `local_backup.py` 파생 ZIP 허용만 확장. 기존 `rotation_holdout`, 양사 WATCH/점수 원장·첫 단일후보 outcome 증거 감사 보존. 단일후보용 5_5 증거를 교체 후보 쌍에 억지 연결하지 않고, 봉인 `content_sha256` + 결과라벨 bytes SHA256 + 두 회사의 각각 normalized JSON 원문/정확한 주장 양음·성숙·공개·취득시각을 필수 교차검사. 한쪽 문서 누락/다른 회사·라벨/사후수정이면 `locally_source_corroborated_pairs=0`으로 검열, 라벨이 아직 만기 전이면 결과를 생성하지 않음. 외부 진짜 발행자/시간 독립 인증 false, 공식 교체 0.
- RED 모듈 없음 수집 오류·CLI 옵션 없음 1 FAIL을 재현한 후 구현. 집중 **109 PASS**, 전체 **938/938 pytest PASS/exit 0**(신규30), 30개 handoff 검사 PASS, pycompile PASS. 합성 CLI 시험: 문서 2개 일치 로컬 연구 쌍 1 → 문서 한 개 바이트 변조 0, 해당 blocker 검출, 원장/봉인 SHA 불변. 파생 요약 JSON 1개만 ZIP SHA 백업/복원 PASS; 원본 성숙 labels·공시 문서/시세·키 미업로드.
- Public Git safety 5 staged suspicious=0 및 diff check PASS, 코드 commit `2242ad6d7f117152cbffb8e3d49099f7dd79f004` GitHub main push 성공, 로컬·원격 SHA 일치, 코드 릴리스 당시 clean. PROJECT_STATE 및 START 추가 갱신은 별도 문서 릴리스 여부 현재 Git 우선.
- NEXT: 2_2/2_5 거래소·공시/영구 기업ID·기업행동/상폐 지급 실제 독립 PIT 자료 확보, 5_5 실전 첫 동결부터 만기까지의 검증된 outcome과 precision/오탐/선행기간. 로컬 데이터 자체 선언에 대한 해시만으로 공신력/진짜 미래 대장주 확정 인증하지 않음. API D-017 로컬 완성 뒤, 물리 SSD D-021 API 뒤 마지막 검수, REWRITE 금지.

## 2026-10-11 최신 — 6_4/6_5 전향 WATCH 일·주·월 운영 연구 보고서

- Remote Mac/T5DATA online, 시작 Git `f55dc76` clean. 기존 가격-only `batch.py`/기존 macOS `local_schedule.py` 정상 보존하고 누락된 WATCH 최초/지속/명시 약화·재진입/최근 등록/2일 동종업종 score 우위를 **로컬 일·주·월 연구 보고서**로 연결. 신규 `src/eraleader/watch_operating_reports.py`, `tests/test_watch_operating_reports.py`(24), `docs/75_WATCH_OPERATING_DAILY_WEEKLY_MONTHLY.md`; 변경 `cli.py` (신규 `report-watch-operations`), `local_backup.py` (시장별 JSON 안전 백업 허용).
- SQLite read-only 한 트랜잭션의 positive+complete screen 원장 SHA/ID·model/market/UTC 기록시각 재검사, 긍정 WATCH 원본만 남은 orphan/수정도 오류. 시장별 명시 등록현지일 기준 daily(당일)/weekly(월요일부터)/monthly(1일부터) 세 기간 상태 변화를 같은 20자리 연구 run ID로 Markdown+HTML+JSON 파생 생성. 기록 누락은 부정 신호/미래 정확도 0으로 대체하지 않음; 자료 없으면 N/A, 오래된 WATCH는 stale. 선택적 `--score-history`와 `--feature-root`는 둘 다 있어야만 실제 기존 peer score audit 재사용. 공식 확정 0/PIT false/실전 정확도 N/A.
- RED: 미구현 import ERROR, 초기 clock/CLI/ZIP 3 FAIL, orphan positive record 1 FAIL, 동일 run ID 부재 1 FAIL을 재현하고 수정. 전체 **962/962 pytest PASS/exit 0(신규24)**, 집중 81 PASS, 30작업 handoff PASS. 100% 합성 과거 fixture 로컬 실제 KR+US CLI/6기간 HTML·MD+2JSON **14개** 파생 보고서, 월간 HTML HTTP 200, KR optional score hypothesis 1/공식0, US 자료 N/A, derived ZIP 14개 SHA/새 경로 복원 PASS. 원본 SQLite/가격·성과/키 Git·ZIP 복제 없음.
- Pub 안전검사 5파일 suspicious=0, 코드 commit `ed7552d264c91db9883709c5fb11a7c02bbc821a` GitHub main push 성공, local/remote SHA 일치/코드 직후 worktree clean. 본 MD 후속 push 상태는 실제 Git 우선.
- NEXT: 6_5 실제 기존 local_schedule과 연구 운영보고의 안전한 opt-in 동기화, 2_2/2_5 진짜 공식 PIT/기업행동/상폐/산업ID, 5_5 실제 전향 후보 성숙 outcome 확보·정밀도/오탐. 외부 API D-017 마지막, SSD 탈착/재부팅 D-021 API 후 최종 검수. 자동 배치 설치/외부 메시지 송신·확정 대장주 **0건**, 30개 전부 인증 아님. CONTINUE, REWRITE 금지.

## 2026-10-11 최신 — 6_5 선택형 WATCH 스케줄러 / 가격 캐시와 분리된 WATCH-only

- 실제 Remote Mac/T5DATA online, Git 시작 `ebaf46b` clean. 기존 오래된 CycleOS 캐시 최신일은 KR **2026-10-02**, US **2026-02-26**(실제 read-only 검사). 기존 가격 배치만 사용하면 미국 10일 이상 cache age로 후보 WATCH 보고를 못 받는 공백 수정. 신규 `scheduled_watch_bridge.py`/ `test_scheduled_watch_bridge.py` **29개**/ `docs/76_SCHEDULED_WATCH_REPORT_OPTIN.md`, 기존 `local_schedule.py`/ `scripts/run_local_scheduled.py` 최소 확장; 가격-only 배치·원본 WATCH/peer score·기존 MarketOS/참고 CycleOS 정상 코드 보존.
- `--watch-research-config <LOCAL absolute JSON>` opt-in일 때 **두 시장/고정 model의 실제 WATCH 원장 SHA/현지 거래 날짜**/optional peer score를 read-only preflight·HTML·MD 검증, 7일 넘은/없는 WATCH는 배치 전체 skip·체크포인트 미발행; 가격 cache 같은 vintage에서도 새 WATCH 등록시 보고서 14파생파일 새로 발행. WATCH가 가격 배치 중, ZIP 생성 중, **검증된 기존 ZIP을 확인하며 skip하는 순간** 바뀌어도 기존 marker 성공 갱신/가짜 SKIPPED 금지.
- 추가 `--watch-only --watch-research-config`는 **가격 캐시·가격배치와 무관**하게 KR+US WATCH 일·주·월 총14파생을 로컬 `output/scheduled_watch`에 발행, 별도 `scheduler_watch_control/last_verified_watch_only.json`, 로컬 ZIP SHA 통과 후에만 성공. WATCH 원장 신선/동일 소스 중복 skip/업데이트, stale/US 없음시 보류, 모델 설정/이중 옵션 오류, 개인정보·원시 자료 업로드 없음. 선택된 launchd plist **파일 생성 기능**은 플래그 전파/SSD 미연결 안전 skip만 검증했으며 실제 `launchctl load/bootstrap`이나 전송 서비스 설치·외부 API 연결 0.
- RED: 최초 WATCH 옵션 16케이스 미지원 실패, 검증된 ZIP 중복 skip 도중 WATCH가 변경돼도 정상 생략하던 1 FAIL 재현, 예약부트스트랩 플래그 누락 FAIL, WATCH-only 미구현 8 FAIL 재현 후 수정. **전체 991/991 pytest PASS exit 0 (신규29)**, 기존 WATCH/가격 스케줄 39 집중 PASS, 30개 handoff PASS·`py_compile` PASS. 실제 Mac의 ignored `output/watch_scheduler_bridge_trial_20261011_1228`에 **100% 합성** KR+US 현재 시각 WATCH 직접 등록→watch-only 1차 14파일 VERIFIED→동일 source 중복 SKIPPED→새 KR WATCH 등록 후 정상 재실행, US fingerprint 불변·KR 변경. ZIP 14파생 SHA verify/새 경로 restore 원문 일치, 가격 배치 0·알림 0·공식 leader 0, 독립 PIT 인증 아님.
- 변경 5개 코드/테스트/MD만 공개 안전검사 scanned=5 suspicious=0·diff check PASS, 정상 GitHub `main` 코드 push `def8f01f09dae2db1c89a51e3c8f862e4ba3cece` local/remote SHA 일치, 코드 당시 clean. 이 후 PROJECT_STATE/START 체크포인트 docs commit 여부는 최신 Git 우선.
- NEXT: 독립 PIT 공급자 KR/US의 실제 기업 영구ID/공시·산업/상폐 기업행동과 5_5 실제 미래 성숙 결과, 검증된 WATCH 최신 정규 데이터 누적. 외부 API D-017은 로컬 완료 후, 실제 T5DATA SSD 물리 분리/재연결·Mac 재부팅 D-021은 API 연결 후 최종 단계. WATCH-only는 **설정 파일만 준비된 상태, 실제 Mac launchd 미설치/자동 리포트 수신·전송 없음**. 공식 대장주 확정 0, 전체 30개 실전 완성 미인증. REWRITE 금지.

## 2026-10-11 최신 — 2_2/2_5 PIT 원장 무결성·실제 캐시 공급자 준비도 진단

- 시작 Mac/T5DATA online, git `57e8316` clean. 정상 기존 `OfflineLedger`는 row import SHA·불변 버전 기록했지만 `snapshot`이 **저장 SHA/기업·자연키/available_at/source_id/provenance를 사용 전에 재확인하지 않는 결함**이 있었음. 신규 `offline_pit_integrity` 합성 테스트에서 12 FAIL 재현 후 `verify_stored_pit_record`로 SHA/중복 JSON키/정규화·자연키/소스·발행시간/허용 provenance fail-closed; int(True)·float→revision 침묵 변환 차단. 기존 SQLite/정상 PIT 파생형태·WATCH·rank 코드는 보존.
- 신규 `pit_provider_readiness.py`와 `audit-pit-provider-readiness` CLI: 실제 참조 CycleOS KR `Date/Code`, US `ts/ticker` Parquet의 마지막 가격시장일, raw-code 범위, 데이터 경과일, 지난 30달력일 breadth peak/광범위 last 날짜·소스 SHA, optional KR/US 기존 `offline.sqlite` read-only PIT 원천/기간/provenance 점검. **실측 2026-10-11 09:00 KST** KR 마지막 가격 **10-02 2873 codes / 9일 지남**, US 마지막 **02-26 1 ticker / 226일 지남**. US 실제 주간 광범위 최근 **02-23 493 ticker**, 30일 peak **494**: 파일 최종 목요일의 1 ticker를 미국 상장기업 전체 1개로 오인하면 안 됨. 80% 보조 sample completeness gate `US:PRICE_FEED_LATEST_DAY_SPARSE`; 실제 공급자 준비도 **11 blockers**, 독립 PIT false/공식 leader 0. `output/demo_offline/offline.sqlite`는 전부 synthetic fixture, 명시 등록해도 blocker 15/공식0.
- **신규 37 pytest (PIT integrity 16 + readiness 21)** 포함 전체 **1028/1028 PASS/exit 0**, 30 ID handoff PASS, py_compile PASS. 실제 로컬 CLI/읽기 전용 SHA 시험, 파생 연구 JSON 1개만 안전 로컬 ZIP SHA `LOCAL_BACKUP_VERIFIED`/새 경로 복원. 원시 parquet/SQLite/계정키 공개 Git·파생 ZIP 업로드 없음.
- 변경 7경로: `src/eraleader/offline_pit.py`, 새 `pit_provider_readiness.py`, `cli.py`, `local_backup.py`, 새 `tests/test_offline_pit_integrity.py`, `tests/test_pit_provider_readiness.py`, 새 `docs/77_PIT_LEDGER_INTEGRITY_AND_REAL_PROVIDER_READINESS.md`. Git Public safety `scanned=7 suspicious=0`, commit/push `4ae02dc9bdf9e2413fc9465699d9795f9f7a3437` main 로컬·원격 SHA 동일, 코드 당시 clean. 본 MD 후속 commit 여부는 현재 git 우선.
- 다음: **진짜 미래 시대 대장주 검색** 성능의 핵심 자료인 KRX/US 공식 법적 issuer/전체 상폐·업종·재무 공시·기업행동·상폐 현금정산 독립 원천 시각과 데이터 최신화, 사전 동결한 후보의 실제 미래 성숙 결과·오탐/리드타임 인증. 현재 가격 캐시의 최종 날짜/구성비는 실전 PIT 인증이 아님. 외부 API D-017 로컬 완료 후, SSD 물리 D-021 최종단계, REWRITE 금지.

## 2026-10-11 최신 — 2_2/2_5 공급자 독립 PIT 수입/첫 로컬 등록시각 방어

- Mac/T5DATA/CycleOS read-only 연결 확인, 시작 Git `b3748ae` clean. 기존 정상 `OfflineLedger`/PIT 빈티지/원본 시장자료 코드 보존. 신규 `src/eraleader/provider_pit_adapter.py`, `tests/test_provider_pit_adapter.py`(45 regression), `docs/78_PROVIDER_NEUTRAL_PIT_BUNDLE_ADAPTER.md` 및 기존 `offline_pit.py`, `cli.py`, `local_backup.py` 최소 확장. 외부 API 없이 로컬 provider-neutral `membership/actions/fundamentals/industry` JSONL + manifest 원본 SHA/행수/시장/기업·산업 영구ID/개정·발행·claimed 수집시간/동시 ticker 충돌 검증 후 **한 SQLite 트랜잭션**으로 기존 PIT 원장 및 `provider_ingest_receipts`/row-level `provider_ingest_rows`에 첫 로컬 등록시각+정규화행 digest 봉인. 모든 데이터 `user_supplied`, 인증 false; 동일 번들 idempotent/새 합법 빈티지 append, 재해시 변조·삭제/타인이름 원문 세탁 차단.
- **신규 중요 미래누출 실제 결함 발견**: provider 최초 등록을 receipt에 기록해도 예전 `OfflineLedger.snapshot(2024)`가 오늘 2026에 추가한 provider 원본이 오래전 공개됐다는 주장만 보고 **과거 PIT로 포함**하는 3 RED FAIL. 이제 단일 SQLite statement에서 각 provider 행의 `available_at` + `retrieved_at_claimed` + `first_registered_at_utc`가 **모두 당시 cutoff 이전**이어야 사용, 나머지는 `quality.provider_rows_unavailable_at_decision_excluded`로 제외. legacy 일반/합성 SQLite 호환 유지, 실전 source 공증 없음.
- 합성 Mac CLI 실행 (ignored `output/provider_pit_adapter_trial_20261011`): KR 4종 원본 합성 16행 수입, 2024-09-01 재조회에서 **14행 소급 투입 차단 / 확인되는 가입기업 0**, `audit-provider-pit-asof` 과거 시점 eligible=false, 공식대장주0. 최초 source 바이트·SQLite read-only SHA 불변, 파생 JSON2개만 ZIP `LOCAL_BACKUP_VERIFIED`/복원 동일. 전체 **1073/1073 pytest PASS/exit0**(기존1028+신규45), handoff 30 ID PASS, pycompile PASS.
- Pub Git 안전검사 **6 staged suspicious=0**, diff check PASS, 코드 SHA `04cf5544b09a33e48d61c7875a9800de39c7defd` GitHub Public main **push 성공**, local/remote SHA 일치/코드 릴리스 당시 clean. 본 상태/START 후속 docs commit 여부 현재 Git 우선.
- **NEXT**: 실제 KRX/DART/SEC 출처·법적 발행인/산업·전체 상폐·정정/액면분할·현금 지급/공시 원문 이용 시점 및 실전 사전 등록 WATCH 미래결과는 여전히 없음. 향후 공급자 전용 정규화 어댑터·다중 원천 교차검증 준비, API D-017 로컬 완료 후, 물리 SSD 분리·재연결/재부팅 D-021 API 후 최종. 공식 leader0, 실전 발굴정확도 N/A, 30개 최종 실전인증 아님. 정상 코드 CONTINUE.


## 2026-10-11 최신 — 2_2/2_5 일반 PIT snapshot 자체 공급자 영수증 무결성 게이트

- T5DATA 정상/main `54ff6ac` clean에서 CONTINUE. 기존 atomic bundle receipt과 manual asof audit가 이미 검증하던 원본 SHA/row inventory를 **일반 `OfflineLedger.snapshot` 경로**에서는 생략해 rehashed PIT payload/원장 fingerprint 바꿔치기를 통과시키는 문제 발견; 신규 7개 RED FAIL 재현.
- 신규 `_read_pit_snapshot_rows` SQLite SAVEPOINT 원자 읽기와 `_verify_snapshot_provider_receipts`: claim source/market 원문 일치, 등록 digest/row_key/수량·원장 누락/고아링크/시각 역전 탐지 및 cache revision 변화를 통한 재검증. 기존 `provider_pit_adapter.py`에도 동일 receipt/source/market 교차 대조. 이전 스냅샷/기간 필터·official FALSE 유지.
- 변경 4경로(실제 코드 2, 테스트 1, docs 1), 신규 **13 pytest**, 전체 **1086/1086 PASS**, 30 handoff PASS, py_compile/diff check PASS. `docs/79_PIT_SNAPSHOT_REGISTERED_RECEIPT_FAIL_CLOSED.md` 재현/한계. 외부 API/원시 데이터 조작·공식 인증 0. GitHub release/push SHA는 현재 Git 상태로 확인.
- NEXT 2_2/2_5 독립 issuer/industry/상폐/기업행동 공식 출처·공개시각 및 cross-source claims, 5_5 미래 성숙 라벨. D-017 API 이후, D-021 물리 SSD 검수 마지막; 로컬 SQLite 자체는 외부 서명·원본 인증이 아님.

## 2026-10-11 최신 — 1_3/2_2/2_5 KR·US staged 공급자 원천 → 기존 PIT 번들 정규화

- 맥북/T5DATA online/pong, 실제 시작 Git 기존 다른 대화 작업까지 들어온 `ba27e83` clean. 정상 `provider_pit_adapter`와 `offline_pit` receipt/원본 대조 보존. 새 `provider_export_normalizer.py`/ `test_provider_export_normalizer.py` **30개**, `docs/80_PROVIDER_STAGED_KR_US_NORMALIZER.md`; 변경 `cli.py` (새 `normalize-provider-export`) + `local_backup.py` (안전 파생 `provider_stage_normalization_research.json`만 추가).
- **중요 구분**: `KRX_DART_STAGED_V1`/`SEC_EXCHANGE_STAGED_V1`은 공식 거래소/SEC API 원시 스키마가 아니라 별도 수집자가 선언한 **오프라인 중간 export** 입력 계약. KR 법인 `corp_code(8)`/개별 `issue_uid`/거래 `stock_code(6)` 분리, 미국 SEC `cik`/명시 `share_class_uid`/거래 `ticker` 분리. 각 행 source document claim/UTC 공개일, manifest/raw 실제 SHA/수량, KR/US 시장/산업/기업행동/재무·revision 공통 수입 완전 검사 후, **새** staged 폴더에만 기존 `eraleader.provider_pit_bundle.v1` JSONL과 normalized manifest + 원본행→정규화행 해시 witness 출력. 기존 normalized PIT `import-provider-pit`가 최초 등록시각 소급 차단/영수증 유지. 진짜 증권 ID·공식 문서 제공자/실제 발행일 공증은 false.
- RED: 미구현 모듈 수집 오류, CLI 누락 1 FAIL 재현, 보완 완료. 기존 공급자/원장/백업 집중 **116 PASS**, 전체 **1116/1116 pytest PASS exit0**(신규30), 30개 handoff PASS, py_compile PASS. Mac `output/provider_stage_translation_trial_20261011_1613` 실제 CLI KR+US 합성 staged 자료 각 4개 행 → normalized 각4 → PIT import 각4 → 2025-09-01 당시 등록 안 된 기업 0 → 현재 연구용 각 기업1, 공식0. 실제 source SHA·PIT 감사 전후 bytes 불변, 파생 연구 JSON 시장별 3파일 ZIP `LOCAL_BACKUP_VERIFIED`/동일 bytes 복원. 네트워크 API/키/유료원본 외부유출 없음.
- GitHub Public 5경로 staging `PUBLIC_GIT_SAFETY scanned=5 suspicious=0`, diff check PASS. 코드 commit `32ef18e9fa623da78e25a78287a53a99e51fc81c` origin main push 성공 및 local/remote SHA 일치, 코드 당시 clean. 본 PROJECT_STATE/START 체크포인트 별도 docs commit 상태는 Git 기준 확인.
- NEXT 1_3/2_2/2_5: 외부 API D-017 이전 공급자 별 실제 원천 export 필드 검증·법적 issuer/security/class 독립 식별/공시·발행/수집 시각/업종·상폐/기업행동 빈티지, 5_5 전향 실전 코호트의 미래 성숙 label, false discovery 및 lead time. 실제 SSD 분리/재연결/맥 재부팅 D-021 외부 API 최종 단계. 공식 대장주 확정0, 실전 발굴 적중률 N/A; CONTINUE without REWRITE.

## 2026-10-11 최신 — 2_2 / 2_5 두 로컬 공급자 PIT 영수증 교차검증

- 맥북 `SHMOONui-MacBookAir.local`, T5DATA EraLeader·CycleOS reference online; Git 시작 `9e51557` clean. 기존 `offline_pit.py`, `provider_pit_adapter.py`, `provider_export_normalizer.py` 정상 코드 보존. 신규 `src/eraleader/provider_dual_source_audit.py`와 신규 `tests/test_provider_dual_source_audit.py`(33), `docs/81_PROVIDER_DUAL_SOURCE_PIT_CORROBORATION.md`, `cli.py` 신규 `audit-provider-source-pair --ledger-a --bundle-a --ledger-b --bundle-b --decision-at`, `local_backup.py` 파생 `provider_source_pair_research.json` 1파일 allowlist.
- 각 원본 SQLite read-only, 기존 공급자 receipt SHA/원본 최초등록시각/claimed 수집시각 검증 재사용. 두 claimed source ID와 publisher 이름·market/SQLite 경로 분리 필수; 판단일 뒤 수입·후행 수집은 **두 출처 간 일치 비교 전체 검열**. 동일 자체선언 issuer ID의 ticker/industry/상장 시작·상폐 날짜, split ratio·dividend cash·기업행동 ID 차이, fundamental+industry 기간/value/unit/revision, one-sided missing/ticker↔issuer name collision을 거짓 확정없이 기록. 동일 선언 일치도 독립 source authenticity / legal issuer / PIT completeness 증명 불가, official leader 0/실제 미래 prediction precision N/A.
- 신규 **33 pytest**, 전체 **1149/1149 PASS exit0**(이전1116+33), 집중 기존 supplier+PIT+backup **140 PASS**, handoff 30 IDs PASS, pycompile PASS. Mac 실제 합성 별도 공급자 원장 2개/CLI: active issuer 주장 2·corporate events 2 국소 일치, split ratio conflict 및 늦은 영수증 입력 전부 차단, 입력 두 SQLite 감사 전후 SHA 불변, 파생 JSON 1개 안전 ZIP hash `LOCAL_BACKUP_VERIFIED` + restore 동일. Path `output/provider_dual_source_trial_20261011` ignored synthetic only, 원본 유료시장/비밀키/public Git 제외.
- Public Git exact5 safety `scanned=5 suspicious=0`, code commit+push `970082522fd0614d12e38e0eac52f79107c70bf0`, local/remote main SHA 일치, 코드 직후 clean. 이번 문서 후속 체크포인트 SHA는 최신 Git 우선.
- **NEXT** 2_2/2_5 공급자 주장 충돌 입력을 stage3/4 신규 후보의 안전한 연구 보류 게이트/웹 데이터품질 배너에 연결 또는 5_5 만기 source receipt 검증, 실제 공식 독립 issuer/class/ticker 히스토리·상폐 현금지급/공시/업종 PIT와 미래 적중/리드타임 인증은 여전히 없음. D-017 API 뒤, D-021 실제 SSD 탈착/맥 재부팅 API 후 최종. API 제외 로컬 개발 진행률 **약 76%(추정)**, 공식 완료율 아님; user 요청에 따라 이후 개발 응답마다 **마지막 줄에 API 제외 진행율 표기**. CONTINUE, REWRITE 금지.

## 2026-10-11 최신 — 2_5/4_1~4_3 출처 충돌을 실제 offline-integrated 후보 WATCH 보류 게이트에 연결

- Remote Mac/T5DATA online, Git 시작 `d877e07` clean. 기존 `provider_dual_source_audit`/PIT 원장·상태/연구용 WATCH 정상 코드 보존. 새 `src/eraleader/provider_candidate_gate.py`, 새 `tests/test_provider_candidate_gate.py` **27개**, `docs/82_CANDIDATE_PROVIDER_PAIR_PIT_FAIL_CLOSED.md`, 기존 `cli.py` `offline-integrated --provider-ledger-a --provider-bundle-a --provider-ledger-b --provider-bundle-b` (all-four opt-in), `local_backup.py` 파생 `provider_candidate_gate_research.json` 한 파일 허용.
- 실제 두 공급자 독립 claimed 원장/번들 최초등록 영수증을 재감사 후 현재 **실제** offline candidate source `snapshot(asof)`의 영구 회사ID/티커/산업/상장종료일·기업 실적 기간/수치/단위·산업 수치·split/dividend/과거 상폐·합병 이벤트 전부 대조. 결측·출처 간/연구 원장 불일치·후행 수집은 `BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH`, 신규 joined run, state_history, prospective WATCH, 웹 **생성 전에 중단**. 일치해도 `LOCAL_CANDIDATE_PIT_PAIR_MATCHED_WATCH_RESEARCH_ONLY`로 연구용 WATCH만 허용/공식 리더 0/PIT false/precision N/A, 신호 run ID에는 source pair digest 고정. 옵션 없음이면 기존 미인증 연구 경로 호환 유지.
- RED 최초 ImportError, CLI 옵션 누락 6 FAIL→보완, 로컬 원장 재무/산업 값 및 SHA 동시 변조·상폐 기업 이벤트 미대조 5 FAIL→실제 4영역 대조로 수정. 전체 **1176/1176 pytest PASS exit0** (기존1149+신규27), handoff 30 ID PASS, pycompile PASS. Mac `output/provider_candidate_gate_trial_20261011` 전부 synthetic + 주입 source clock 실제 CLI 스모크: 좋은 쌍은 연구용 WATCH만, split ratio 차이/서로 일치하는 둘과 다른 로컬 매출값 변조는 원장 새 기록/웹 생성0; 입력 SQLite read-only SHA 불변, 파생 JSON1개 ZIP SHA `LOCAL_BACKUP_VERIFIED`/동일 bytes restore, 원시 price·키·PIT DB ZIP·Git 제외.
- GitHub Public scoped 5경로 `PUBLIC_GIT_SAFETY scanned=5 suspicious=0`, diff check PASS, 코드 commit/push `1e838509f43f74c35fda268bf82d542e86dceca5`, local/remote SHA 동일/코드 당시 clean. 본 상태/START docs checkpoint 커밋은 최신 Git 우선.
- NEXT 실제 공식 KR/US 법적 issuer/class/업종·기업행동/상폐 현금 정산/원천 공시 발행·실제 수집시각·전체 역사 유니버스 PIT/사전 등록 실전 WATCH 만기 outcome 실증. D-017 외부 API 로컬 기능 이후, D-021 실제 SSD 물리 탈착/재부팅 API 이후 마지막. 공식 대장주 확정0, 실전 hit-rate N/A; **API 연동 제외 개발 진행률 약 77%(추정)**. User 요청에 따라 모든 후속 EraLeader 개발 보고 **마지막 줄에 API 제외 진행율 표기**. 기존 정상 코드 CONTINUE, REWRITE 금지.

## 2026-10-11 최신 | 5_3/5_5 Top-K 성공판정기준 원문 SHA 동결 + source 문서 검열

- Mac/T5DATA 연결 확인, 시작 main=f4bd8cf clean; 정상 old ranked discovery/WATCH/PIT code 보존. 신규 ranked_outcome_receipts.py, tests/test_ranked_outcome_receipts.py(31), docs/83_PREDECLARED_RANKED_OUTCOME_SOURCE_BOUNDS.md, 기존 ranked_discovery.py/cli.py/local_backup.py 최소 확장.
- 기존 Top-K 동결의 치명적 미완료: label_definition_id 및 그 실제 positive_criterion/measurement_method/universe_scope/delisted_handling JSON rule 원문 SHA가 최초 freeze와 결합되지 않아 사후 '미래 대장주 성공 기준' 바꿔 성능 과장 가능. 신규 freeze --label-definition-id --label-definition-file SHA256 고정; strict audit-ranked-outcome-receipts --definition-file 및 source manifest/label original file/document SHA/claimed timestamp/maturity 검사. 미성숙·소스없는 label은 known failure 아님, source-censored; denominator frozen top-K 고정. retrospective freeze는 source document가 있어도 prospective precision null. KR/US exact horizon/DST 기존 evaluator 유지. 공식 PIT/source 인증 false, official leader promotion0.
- 기존 1176 + 신규31 = 전체 1207/1207 pytest PASS(exit0), 신규+기존 ranked/registry/provenance/backup 집중120 PASS, handoff 30개 ID PASS, py_compile PASS. Mac ignored output/ranked_outcome_source_trial_20261011 synthetic fixture 주입 Jan1 freeze에서는 local doc-matched known2/early1/precision 0.5 연구 수치; 실제 Mac OS clock으로 과거 rank를 지금 freeze하면 retrospective로 감지되어 prospective precision null. 파생 JSON1개 ZIP/manifest LOCAL_BACKUP_VERIFIED+복원 byte equality; 원본 labels 및 시장 데이터/비밀키 Git/ZIP 업로드 없음.
- GitHub Public main scoped code push edd3dc12dd88074b5c0294f7f682938b5e3f2696, staged 6파일 PUBLIC_GIT_SAFETY suspicious0/diff check PASS, local/remote equal/코드 직후 clean. 본 상태 MD 추가 docs commit SHA는 현재 Git 우선.
- NEXT: 5_5 최초 실전 WATCH와 사전 등재한 native score/Top-K freeze 연동, 미래 결과의 실제 독립 source 인증/PIT issuer/delist cash/completeness; 6단계 웹/알림 사용자 운영은 실전 데이터 없어 검증 미완료. D-017 API 이후, D-021 SSD 실제 분리/재부팅 API 후 최종. API 연동 제외 로컬 진행률 약78%(추정), 후속 보고 끝에 반드시 진행률 표시. REWRITE 금지.


## 2026-10-11 최신 5_3/5_5 — 네이티브 점수 최초기록 전향 Top-K 일괄 봉인

- 맥 SHMOONui-MacBookAir.local/T5DATA online, 시작 main dc22328 clean. 기존 최초 WATCH(positive+screen observations)·첫 numeric score·ranked freeze/leader rule·source outcome 모듈 보존. 신규 native_topk_freeze.py 및 test_native_topk_freeze.py(17 regression), docs/84_NATIVE_FIRST_WRITE_WATCH_TOPK_FREEZE.md, cli.py의 freeze-native-topk opt-in: **시장+모델의 모든 양성 WATCH를 native 점수로 전수 커버해야만** first SCORE write 실제시각으로 현재 시점 Top-K, K/horizon, 미래 label definition 원문 SHA를 O_EXCL 동결. WATCH 첫시각으로 numeric score 소급 가정 금지, native 공식/원본바이트/원장 이중 preflight 및 늦은 소스 변조 차단. 공급자 PIT/OS시계 독립 인증 false, 실전 예측성공 N/A, 공식 leader0.
- 신규 시점변조 preflight 중간 1 RED FAIL 실제 재현 후 마지막 원본 피처/공식 재검증으로 GREEN. 전체 **1224/1224 pytest PASS(exit0)**(기존1207+17), handoff 30 작업 PASS, pycompile PASS. 실제 Mac synthetic KR CLI 최초 WATCH2→native-score2→Top-K 봉인1→감사 blocker0, 이후 synthetic source 변경 시 CLI exit2/동결파일 미생성; 원본 WATCH/score 파일 SHA 불변.
- Public Git staged 4 경로 safety scanned4 suspicious0/diff PASS; 커밋/푸시 **3f592dd13ec648a50491768a45630e0690fbfa5e**, local/remote SHA 일치/코드 직후 clean. 다음은 **2_2/2_5 실제 독립 issuer/class·공시/상폐 cash/기업행동·시장 PIT 출처**, 실제 최초 신규 WATCH/Top-K 운영 cohort 확보 후 5_5 만기 future outcome 검증. D-017 API 나중, D-021 물리 SSD 재연결 최종 단계, 기존 코드 REWRITE 금지. API 제외 로컬 진행률 약79% 추정, 이후 개발 응답 마지막에 표기.


## 2026-10-11 최신 — 2_2/2_5 staged 원본→정규화→first-ingest 출처 계보 감사

- Mac SHMOONui-MacBookAir.local/T5DATA online, 시작 git 709a55a clean. 기존 KR/US offline provider normalizer와 최초 SQLite receipt/dual provider/후보 WATCH 정상 코드 보존. 신규 provider_staged_lineage.py, test_provider_staged_lineage.py(25), docs/85_PROVIDER_STAGED_SOURCE_LINEAGE.md, cli.py audit-provider-staged-lineage, local_backup.py 파생 JSON 하나 허용. staged original source row SHA/claimed doc ID/natural key → normalized original bytes/witness/manifest **완전 재계산** + normalized bundle의 first local ingest receipt/시점 재검증, 뒤늦은 수입은 CENSORED. 원본/SQLite 감사 read-only, 중간 변조/재해시 공격 fail closed. 단 최초 ingestion은 normalized SHA만 봉인했으므로 **원본 문서 ID와 witness를 함께 다시 쓴 공격의 최초 당시 동일성은 인증 불가**: original_doc_id_hash_attested_at_first_ingest=false, real issuer/source PIT false/official leaders0 고정.
- 전체 **1249/1249 pytest PASS(exit0)** (기존1224+25), 30 IDs handoff PASS, py_compile PASS, KR+US Mac real CLI synthetic 4rows/market→첫 수입→lineage audit local true→파생-only ZIP hash restore 성공, raw action+manifest 재해시 조작 양국 CLI exit2. Public Git 5파일 안전검사 scanned=5 suspicious=0, 코드 push SHA **9cd7f4f7d4188e862b08864d1092e0e98cc354f2**, local/remote main equal, clean. Docs checkpoint 후속 SHA는 실제 Git 우선.
- NEXT 2_2/2_5 최초 raw+witness seal/법적 issuer/class/상장·기업행동·상폐 현금정산 공식 원천 시각/독립 인증 및 5_5 실전 첫 WATCH/Top-K future outcome. D-017 외부 API는 로컬 이후, D-021 실제 SSD 물리 분리/재부팅은 API 후 최종. 정상 REWRITE 금지. **API 제외 진척 약80% 추정**, 개발 답변 마지막에 반드시 표기.


## 2026-10-11 최신 — 2_2/2_5 최초 원본 문서 claimed ID/witness raw SHA와 first-ingest SQLite 원자 동결

- 시작 T5DATA main 19c8468 clean, Mac online, CycleOS reference read-only. 이전 docs/85의 normalized bundle만 시점 고정하고 raw staged source/witness 문서ID는 first-ingest에 미봉인하던 결함 개선. 신규 staged_first_ingest_pin.py, test_staged_first_ingest_pin.py(20), docs/86_FIRST_INGEST_ORIGINAL_STAGED_SHA_PIN.md, 기존 provider_pit_adapter.py/provider_staged_lineage.py/cli.py 선택 확장. import-provider-pit --staged-manifest로 원본 raw stage/doc-ID witness/normalized manifest SHA를 **같은 BEGIN IMMEDIATE 첫 수입 트랜잭션**에서 원본 receipt + 기존 normalized receipt digest marker로 동시 기록; 후행 소급 pin 불허. audit-provider-staged-lineage --require-original-first-ingest-pin으로 엄격 read-only 검사, 원본 pin 제거·digest 훼손·원시 문서ID+normalized witness 동반 재해시 변조 차단. 기존 일반 수입 및 본래 staged lineage 계속 정상/legacy 당시 PIN false 유지.
- TDD 신규 미구현 17 RED, 원본 영수증 삭제/marker 빈틈 2 RED를 재현·수정. **전체 1269/1269 pytest PASS(exit0)**, handoff 30개 ID PASS, py_compile PASS. 실제 Mac synthetic KR+US 각 4 raw rows→normalizer→CLI first raw-pin import→strict CLI local PIN 감사→derived ZIP SHA 복원 통과, claimed document ID+raw+witness 동반 재해시 공격 strict audit exit2/파일 미발행. 공식 PIT/실전 미래 리더 정확도 N/A, official leader0.
- Public Git 6파일 safety scanned=6 suspicious=0, 코드 push **dfc0c5157e5f92a072a347e25942911a5b1d24f3** local/remote equal, 코드 릴리스 당시 clean. 상태MD 후속 docs commit 여부는 실제 Git 우선.
- NEXT raw+normalized 최초 PIN을 2_2/2_5 provider-dual source candidate WATCH strict opt-in gate에 연결할지 검토, 실제 issuer/class 법적 정합/공시·상폐 현금지급/기업행동/전체 시장 PIT/5_5 실전 cohort maturity 필요. D-017 API는 이후, D-021 SSD 물리 재연결·재부팅 마지막, 정상 코드 REWRITE 금지. **API 연동 제외 진행률 약81% 추정**. 답변 마지막에 표시.


## 2026-10-11 최신 2_2/2_5/4_1~4_3 — 두 공급자 최초 raw source SHA PIN을 실제 WATCH 전 연구 게이트에 연결

- PC/T5DATA/CycleOS read-only online, starting git main 3f93de8 clean. 신규 provider_pair_original_pins.py, tests/test_provider_pair_original_pin_gate.py(15), docs/87_DUAL_PROVIDER_ORIGINAL_PIN_WATCH_GATE.md, 기존 provider_dual_source_audit.py/provider_candidate_gate.py/cli.py strict 선택 옵션. pair A/B raw staged manifest 2개 + normalized manifest 2개 + 최초 SQLite 영수증 PIN SHA까지 모두 read-only 재검증, 후행/수정/결측·문서ID+witness+원문 SHA 재해시로 normalized 값 보존하는 공격도 WATCH 전 차단. 모든 4 original manifest 요구, partial/legacy original unpinned 모두 strict 차단; 기본 이전 기능 호환. strict first PIN pair SHA를 candidate run_id provenance에 포함; official leader0/실전 PIT false.
- 전체 **1284/1284 pytest PASS exit0**(이전1269+신규15), handoff 30작업/40 필수경로 PASS, py_compile PASS. Mac 실제 합성 현재 OS first ingest KR+US 각 2 claimed suppliers, 8 raw rows씩→정규화/첫 original PIN→CLI strict offline-integrated 각 1개 positive research WATCH + source evidence pair true. raw claimed document ID와 witness 동반 변경/재해시 뒤 동일 normalized bundle인데도 KR/US 모두 CLI exit2/새 WATCH·state·site·run 없음; 파생 JSON만 ZIP 안전 백업/복원 PASS; 공급자 공식 인증·투자 성능 아님.
- Public Git scoped 6파일 safety scanned6 suspicious0/diff PASS, main 코드 commit/push **04531cf0e756624a7d70a14344f72e75dd55bad3**, local/remote equal, 코드 릴리스 당시 clean. 상태MD 문서 후속 commit SHA는 실제 git 우선.
- NEXT: 2_2/2_5 실제 법적 issuer/share-class/industry·공시·상폐 정산 원문/독립 공개시각·과거 전체 PIT coverage, 5_3/5_5 진짜 사전 동결 WATCH native topk의 미래 만기·오탐 precision/lead days, 선택 6단계 데이터품질 웹 보고. D-017 API 후순위, D-021 SSD 분리/재부팅 마지막, REWRITE 금지. API 제외 진행률 약82%(추정). 모든 후속 결과 마지막에 표기.


## 2026-10-11 최신 — 5_3/5_5/6_2 사전 native Top-K 후보의 만기·미확인 성과 로컬 웹

- 시작 T5DATA main 5931dae clean, Mac online, CycleOS 참조 read-only. 새 src/eraleader/ranked_maturity.py, tests/test_ranked_maturity.py(24), docs/88_NATIVE_TOPK_MATURITY_WEB.md, 선택 확장 cli.py/delivery.py/local_backup.py. 기존 WATCH 첫 기록·native score first-write/label 정의 bytes SHA를 검증하고 현지 KR/US(DST) 정확한 +horizon일 만기 시각을 계산, 기간 중/기간 경과 후 결과 미확인/소급 동결을 정확히 구분. **Outcome 라벨 입력 자체 없음 → mature라도 positive/negative/precision/recall null**, 원본 native score/WATCH/원문 feature SHA/4요소 공식 및 frozen label rule 재감사. 기존 웹/원장 미변경; JSON ranked_maturity_kr|us_research.json + HTML site/ranked_maturity_kr|us.html 생성. 샘플 축소해도 Top-K 원래 분모 유지, fake success/공식 인증 렌더 금지.
- 신규 TOCTOU 2 RED FAIL(감사 중 feature 바꾸기/frozen rehashed 갱신) 재현 후 마지막 원본 공식·frozen 재조회로 GREEN. 전체 **1308/1308 pytest PASS/exit0** (이전1284+24), handoff 30작업/40 경로 PASS, py_compile PASS. 실제 Mac 현재 clock KR+US 가상 WATCH→native score→first freeze→maturity CLI pending1/market 각각→local HTML HTTP200, N/A/leader0, derived JSON+HTML 2파일 ZIP SHA 검증/복원. 공식 주가/리더 예측 성과/시장 PIT 인증 아님.
- Public Git 정확히 6파일 scanned6 suspicious0 + diff check PASS; code main commit/push **c43a11ae54b8698c845fdce165ef76f3aeda314d**, local/remote 일치/코드 릴리스 당시 clean. 상태MD 후속 push SHA는 현재 실제 Git 우선.
- NEXT: 6_4/6_5 기존 WATCH schedule opt-in과 native Top-K maturity read-only 보고서 결합(실제 label 미확인 N/A), 5_5 실제 사전 동결 후보 만기 outcome·실전 precision/lead days; 2_2/2_5 실제 법적 issuer/class/업종/상폐 cash/독립 발표시각/역사 전체 PIT 원천 필요. D-017 API 및 D-021 SSD 물리 분리/재부팅은 최종 후순위, REWRITE 금지. API 제외 진행률 약83% 추정. 답변 마지막에 표기.


## 2026-10-11 최신 6_4/6_5 — native Top-K 사전등록 성숙도 별도 일·주·월 예약 보고

- T5DATA eraleader Mac online, 시작 main 3224480 clean; 과거 가격cache 및 최근 WATCH 7일 신선도와 **독립적**으로 180일+ 사전 frozen Top-K 만기 상태를 별도 예약 재검증하도록 추가. 새 scheduled_maturity_bridge.py, test_scheduled_maturity_bridge.py(25), docs/89_SCHEDULED_NATIVE_TOPK_MATURITY_BRIEFS.md; 기존 local_schedule.py/scripts/run_local_scheduled.py에 --maturity-only --ranked-maturity-config 완전한 KR+US 각각 5경로 입력/strict preflight. native rank 원본 WATCH·score·feature formula, label rule SHA 검사→KR/US 각 JSON+기본HTML+일/주/월 MD/HTML 3쌍씩 총 16 derived, pending/elapsed/unknown 유지, 실제 정답 outcome 미수입/N/A/official leaders0.
- batch.lock, 독립 last_verified_ranked_maturity_only.json, backup SHA 검사 전후 원본 재감사, 원본/설정변조·유실/손상 ZIP·누락 page 복구, 현지 같은 날짜 horizon 임계시각 전후 만기 상태 변경 시 새 실행. 기존 price/watch-only 모드 코드 보존. launchd **설정 생성만**(서비스 ID ranked-maturity, 독립 launcher/log), load/start 자동화/메일·텔레그램 0. 초기 3 FAIL(마크다운 미확인 표현/zipfile.BadZipFile/launchd 출력경로 변수 shadowing) 수정 후 통과.
- 전체 PYTHONPATH=src pytest tests **1333/1333 PASS exit0**(이전1308+25), handoff 30 ID/40 required PASS, pycompile PASS. 실제 Mac OS-clock KR/US 가상 사전 WATCH/점수/동결 복사 source 대상으로 isolated project CLI 16 report/HTTP200 양국/derived ZIP hash 복원/동일 상태 중복 skip/합성 KR 피처 훼손 exit2·기존 checkpoint SHA 불변, 모두 실전 데이터 아님. ignored output/maturity_schedule_e2e_trial_20261011_111410_649487. Public Git code5 files safety suspicious0, code commit/push **5562f7d47fb41e8005cc78e2e65c8015dc396163**, local/remote 같고 clean. 최신 docs 체크포인트 git SHA는 실제 git 확인.
- NEXT 6단계 사용자용 운영 대시보드/로그인·라이브 전송 정책(승인 전 install/메시지 금지), 5_5 실전 독립 원천 matured outcome/false discovery/precision/lead days, 2_2/2_5 KRX/SEC 법적 issuer/class/상폐 현금·기업행동/역사 전체 PIT/원천 시각 인증. D-017 API/외부 연결 후순위, D-021 SSD 물리 분리·재부팅 마지막. REWRITE 금지. **API 연동 제외 로컬 진행률 약84% 추정**, 후속 최종 보고 마지막 줄에 포함.


## 2026-10-11 최신 6_5 — 예약 native Top-K 웹 보고서 본문 변조 SHA 검사·복구

- 원격 맥/T5DATA/CycleOS 참조 online, 시작 main `6458110` clean. 기존 6_4/6_5 예약 보고서 16개 존재만으로 SKIP되던 **실제 무결성 결함** 해결: 신규 `published_maturity_pages_match_verified_backup`는 검증 ZIP `MANIFEST.json`의 SHA/크기를 현 KR/US JSON·HTML·일/주/월 MD/HTML **16개 현재 바이트**와 전수 대조, 왜곡·동일 크기 숫자 `N/A`→`100`·파일 누락/링크·외부 폴더 ZIP 포인터면 SKIP 대신 원본 first frozen WATCH/score 재감사 후 정상 보고서·ZIP·atomic checkpoint 재발행. 정상 파일 전부 같으면 기존 ZIP 효율적으로 재사용. 새로운 외부 데이터나 live 경로 없음.
- 변경 4개: 수정 `src/eraleader/local_schedule.py`, `scheduled_maturity_bridge.py`, `tests/test_scheduled_maturity_bridge.py` (+6 케이스), 신규 `docs/90_MATURITY_PUBLISHED_BYTES_REPAIR.md`. 신규 5 RED FAIL 직접 재현 후 집중 **31/31 GREEN**, 전체 **1339/1339 pytest PASS exit0**, handoff 30 ID/40파일 PASS, pycompile/diffcheck PASS. Mac 실제 synthetic KR+US CLI 3회: 최초 full 16 + ZIP → 파일 위조 뒤 재발행/ZIP → 안정화 정상 skip; 원본 8파일 SHA 불변. `output/maturity_bytes_cli_trial_r2k4xm26` ignored, 실제 PIT/성능 인증 아님.
- Public repo staged4 safety suspicious0, 코드 main commit+push `d48f3bb4f5b79106cc242f72ba949760b7560208`, local/remote SHA 일치, 코드 직후 clean. 본 문서/PROJECT_STATE 후속 체크포인트 Git SHA는 최신 실제 git 확인.
- **NEXT** 6_2/6_5 사용자 로컬 운영 대시보드 및 접근·라이브 전달 안전 정책, 5_5 실제 전향 코호트 성숙 결과 독립 검증, 2_2/2_5 KRX/SEC 법적 기업ID/share-class·현금상폐/기업행동/산업/공시 PIT 역사 전체 검증. D-017 API 후순위, D-021 실제 SSD 분리/재연결/맥 재부팅 최종까지 금지. 공식 대장주0 / 실전 precision N/A. **API 연결 제외 개발 진행률 약85%(추정)**. 답변 최종 줄에 표기. 정상 코드 CONTINUE/REWRITE 금지.


## 2026-10-11 최신 — 6_2/6_5 메인 운영 상태 read-only 증거 웹·JSON

- Mac/T5DATA/CycleOS 참조 online, 시작 main `eb83e24` clean. `src/eraleader/operations_overview.py`, `scripts/render_local_operations.py`, `tests/test_operations_overview.py`, `docs/91_LOCAL_OPERATIONS_OVERVIEW.md` 신규. **메인** 가격/기존 WATCH/Top-K maturity 체크포인트 3개만 read-only 조회하며 `*trial*` 합성 자료를 실전으로 승격하지 않음. ZIP SHA 검증+허용 KR/US JSON·HTML·MD 원본파생 10/14/16 경로 등 모든 보고서 live 바이트 SHA 대조, 오염·누락·외부 zip/심볼릭 링크·잘못된 완료/라이브/PIT 주장/미래시각 차단. 최소 10개 가격 필수 경로, WATCH 14, maturity 16; 가격관측 지연 10일/과거 WATCH 예약7일 구별, maturity 180일 지난 cohort는 결과없음 N/A 유지. 마지막 read-only 재감사 일치하면 `output/operations/site/index.html`+`operations_health_research.json` 단 2파일 로컬 atomic 발행. 원본 시장 DB/키/뉴스/실제 알림/구동 daemon 전혀 접근/실행 없음.
- 테스트 신규 **32**, 전체 **1371/1371 pytest PASS exit0**, handoff 30 IDs/40 files PASS, pycompile/diffcheck PASS. 실제 기존 price checkpoint는 구형 WATCH flag 미포함: RED 재현 후 가격-only 호환, KR2026-10-02/US2026-02-26 ⇒ 유효 ZIP/live SHA true + STALE_PRICE_OBSERVATIONS; 메인 WATCH/Top-K 예약 checkpoint 없음 ⇒ NO_CHECKPOINT/실전 precision N/A. Mac 실제 정적 serve localhost HTTP 200와 화면 경고 확인, 시험 서버 종료. `output/` Git 제외.
- Public Git 신규 정확 4파일 staged safety suspicious0, 코드 commit/push `7377df904e4ed010b5be47ff54bc36b895357b55`, local/remote main equal, code 직후 clean. 체크포인트 PROJECT_STATE/START 후속 문서 commit은 최신 Git으로 확인.
- NEXT 6_4/6_5 데이터 실패 로컬 dry-run outbox/복구 알림(실전 발송/인증 아직 금지), 2_2/2_5 외부 독립 공식 issuer/상폐 cash/기업행동/공시 PIT, 5_5 실제 첫 WATCH/미래 라벨 만기 precision·false discoveries·lead-days 실측. D-017 API 최종 뒤, D-021 SSD 물리분리/재부팅 최종. REWRITE 금지, API 제외 진행률 **약86%(추정)**; EraLeader 개발 완료 보고 마지막에 표기.


## 2026-10-11 최신 — 6_4/6_5 로컬 데이터 오류·로컬 파일 복구 DRY-RUN outbox

- Remote Mac/T5DATA/CycleOS 참조 online, 시작 main `31ce539` clean. 신규 `src/eraleader/local_failure_outbox.py`, `scripts/run_local_failure_outbox.py`, `tests/test_local_failure_outbox.py`, `docs/92_LOCAL_FAILURE_DRY_RUN_OUTBOX.md`, 기존 `local_backup.py` allowlist 2개 이름만 추가. 기존 메인 KR/US price/WATCH/native Top-K 스케줄러 read-only `audit_local_operations`를 재활용해 **`DATA_FAILURE_LOCAL` 최초·원인 변경·기록유실/중복 방지**, `LOCAL_ARTIFACTS_RESTORED`(로컬 ZIP+파생 페이지 무결성만 복구, 실제 PIT/시장 자료 인증 아님) 감사 로그/HTML/JSON 발행. 최초 WATCH/Top-K 미설정은 `UNCONFIGURED`이고 외부 공급자 장애로 오인 금지. SQLite `BEGIN IMMEDIATE`/flock와 전체 사건 event SHA256 chain·count/condition SHA 재검증/UTC 소급 및 위조 SENT fail closed; live 발송 모듈 없음(0건).
- 전체 **1399/1399 pytest PASS exit0**(이전1371 + 신규 **28**), handoff 30 ID/40 필수 PASS, py_compile, Public Git exact5 파일 `scanned=5 suspicious=0`, git diff check PASS. Mac 실제 CLI 기존 price KR2026-10-02/US2026-02-26의 stale로 local DATA_FAILURE 1 최초 기록 → 재실행 0/누적1, WATCH/Top-K production checkpoint 없음은 failure0. 파생 SQLite+JSON+HTML 총3개의 SHA ZIP `LOCAL_BACKUP_VERIFIED`/새 경로 복원/동일 event chain PASS, 기존 원본 가격 checkpoint·KR/US 화면 3바이트 SHA 무변경, localhost HTTP 200 및 미전송/N/A 문구 확인. 실제 실전 알파/라이브 메시지/공급자 독립 인증 N/A.
- Public GitHub main 코드 commit+push `bbd6391a3684a3495279c3986b8a7b04561cccc6`, local/remote SHA 동일 코드 당시 clean. STATE/START 후속 docs checkpoint은 현재 git 확인.
- **NEXT** 6_4/6_5 기존 scheduler에 선택적 안전 게이트로 로컬 outbox 평가 통합(기본가동/launchd load/실제 메일·텔레그램 금지), 5_5 실제 사전 동결 후보의 장기 미래 outcome/false positives/lead days와 2_2/2_5 독립 KRX/DART/SEC 법적 기업ID·상폐 현금·공시 PIT 인증. D-017 외부 API는 로컬 완료 후, D-021 물리 SSD 분리/재부팅 API 연결 후 마지막. 정상 코드 CONTINUE/REWRITE 금지. **API 제외 로컬 개발 진도 약87%(추정)**; 후속 개발 결과 마지막 줄에 표시.

## 2026-10-11 최신 — 6_4/6_5 기존 예약 배치와 데이터오류/파일복구 로컬 DRY-RUN outbox 선택 연결

- 실제 맥/T5DATA 원격 online, 시작 Git `ccb2378` clean. 기존 `local_schedule.py`/ `local_failure_outbox.py` 정상 구현 보존. **신규 `scripts/run_local_scheduled.py --local-outbox-dry-run`**는 명시 옵션에서만 기존 가격/WATCH/maturity 배치 후 운영상태를 read-only 감사하여 로컬 사건 원장에 기록; 배치 실패면 원래 오류 우선/보조 감사 시도. ZIP SHA 검증·잠금/송신·가짜 성과 주장 안전 게이트, plist 생성 조합 금지(자동설치·외부 전송 0). 무옵션 실행은 기존과 동일.
- 정확히 3파일 변경: scripts/run_local_scheduled.py, 신규 tests/test_scheduled_failure_outbox_bridge.py(12), docs/93_SCHEDULE_FAILURE_OUTBOX_OPT_IN.md. 초기 **10 RED → 신규 12 GREEN**, 전체 **1411 pytest PASS(exit0)**, handoff 30작업/40필수 PASS, pycompile/diffcheck PASS. Mac 실 CLI `SKIPPED_STALE_CACHE` 이후 outbox `LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP`/중복 신규0/총1/라이브0/API0; 기존 main 가격 checkpoint SHA 불변. Git public 안전검사 scanned3 suspicious0; 코드 Git commit/push **`ccd37ea129b8d1e1d222eceb2a538ad361553936`** local/remote 동일, clean. 최신 docs 인수인계 커밋은 실제 git 우선.
- NEXT 2_2/2_5 실제 issuer/share-class/공시·상폐 cash/기업행동 독립 PIT 원천+전시장 역사 커버리지, 5_5 실제 사전 봉인 미래 cohort 만기 outcome/precision/오탐/lead days. 공식 대장주0/실전 성능 N/A; D-017 API 연결 후순위, D-021 SSD 실제 분리·재연결/재부팅은 최종 단계. **API 연동 제외 로컬 진도 약88%(추정)**. 정상 코드 CONTINUE/REWRITE 금지.

## 2026-10-11 최신 — 6_2/6_5 로컬 운영+DRY-RUN 장애원장 SHA 증빙 웹

- Mac/T5DATA online, 시작 main `8668e95` clean. 이전 scheduler/watch/native Top-K/PIT/로컬 outbox 정상코드 보존. opt-in `scripts/render_local_operations.py --include-local-outbox`는 기존 3종 예약 감사 + 기존 사건 SQLite chain·verified ZIP 정확히 3파생·live JSON/HTML·아카이브 SQLite 메모리 snapshot를 모두 검증하고, 현 예약 SHA와 동일/변경 및 원장 미설정/변조를 분리. 신규 `output/operations_alerts` HTML/JSON 2파생만 출력(기본 operations 기존 기능 불변), 공식 리더0/실전 precision N/A/라이브0.
- 정확히 4개 코드 파일: 신규 `operations_alert_bridge.py`, `test_operations_alert_bridge.py`(21), `docs/94_OPERATIONS_ALERT_EVIDENCE_BRIDGE.md`, 스크립트 옵션 한정 확장. TDD 모듈 ImportError RED 후 **1432/1432 pytest PASS(exit0)**(이전1411+21), handoff 30 ID/40파일, pycompile PASS. Mac 실제 기존 outbox 사건1 및 가격 최신 KR2026-10-02/US2026-02-26 stale 상태에서 read-only CLI/HTTP200 검증, 기존 DB/control/report SHA 전후 무변경. Public Git staged4 safety suspicious0, code main commit/push **`8f3b5ed1360b258814d68d1aecdcffb67681eb23`** local/remote 같고 code 직후 clean. 최신 docs 후속 SHA는 git 확인.
- NEXT 독립 KRX/DART/SEC issuer/class·상폐 cash·기업행동·공시 PIT, 5_5 실제 미래 WATCH/Top-K 만기 독립 outcome 조기발굴 정확도 및 6단계 로그인·실전 발송 정책. D-017 API 마지막, D-021 물리 SSD 분리·재연결/재부팅 최종 단계. **API 제외 로컬 진척 약89%(추정)**. 실전 인증 leader0, skill N/A, 정상 코드 CONTINUE/REWRITE 금지.

## 2026-10-11 최신 5_3/5_5 — 최초 prospective Top-K 전 코호트 빠짐없는 로컬 정량 평가

- T5DATA/Mac online 시작 main `9afa4ec` clean. 신규 `prospective_census.py`, `scripts/run_prospective_census.py` register/audit, 신규 `test_prospective_census.py`(24), `docs/95_PROSPECTIVE_TOPK_COHORT_CENSUS.md`, 기존 `local_backup.py` 파생 census JSON allowlist 1개 확장. 기존 WATCH/native score/rank/outcome strict/PIT/MarketOS 재작성0. rank freeze 시점부터 60분 안의 당초 predeclared K/label bytes SHA 첫 등록(O_EXCL), 미래 outcome/receipt 사전존재 금지. **모든 로컬 first-write registry 코호트**를 읽고 미만기·미확인/누락·검열을 K 원분모에서 제외하지 않음. 나중에 source가 있으면 기존 strict outcome receipts audit 재사용, local precision/bounds만 계산(실전 precision N/A, official leader0). 로컬 OS/원천 공증 및 registry 자체 삭제 감지는 불가.
- 처음 신규22 GREEN, 누락 코호트 숨김·안전 백업 누락 신규2 RED→FIX→**24/24 신규 PASS**, **전체 1456/1456 pytest PASS(exit0)**, handoff 30 ID/40필수 PASS, py_compile/diffcheck PASS. Mac 실제 OS clock 가상 KR Top-K=2 처음 동결→CLI register/audit→기간미도래 unknown2/0 실전정답, derived-only ZIP SHA 신규 경로 복원 및 원본 SHA 불변. Public Git exact5 staged 안전검사 scanned5 suspicious0, main commit/push **`a928611455f7ae6ae19af83257833d03d5eed6ec`** local/remote equal code 직후 clean. 최신 checkpoint docs SHA는 실제 git 우선.
- NEXT 실제 first WATCH/native Top-K 미래 cohort와 시점별 독립 outcome 확보, 2_2/2_5 공인 issuer/class·상폐 cash·기업행동·공시 PIT 전시장 독립 원천. 외부 API D-017 마지막/SSD 물리분리·재부팅 D-021 마지막. **API 연동 제외 개발률 약90%(추정)**. 정상코드 REWRITE 금지.

## 2026-10-11 최신 5_3/5_5 — 최초 등록 코호트 삭제·수정 감지용 SQLite SHA index

- Mac/T5DATA online, 시작 main `12d2be1` clean. 신규 `src/eraleader/prospective_census_seal.py`, `tests/test_prospective_census_seal.py`(15), `docs/96_PROSPECTIVE_CENSUS_RECEIPT_INDEX.md`, 기존 `scripts/run_prospective_census.py`에 **명시적 `--receipt-index`** 옵션 최소 추가. 기존 정상 census/Top-K/MarketOS/PIT REWRITE 0. O_EXCL first census에 별도 형제 SQLite index seq/원문 SHA/UTC/SHA event chain을 하나씩 추가, 원래 코호트 삭제·rename·개조 및 index 상실/위조·소급/중도 orphan 감지 시 감사 보류. 인덱스 있는 곳에서 기본 weak CLI downgrade도 방지. **공급자 원천·Mac clock 독립 인증과 모든 파일 공동 삭제 방지는 아님**, 실전 leader0/precision N/A.
- 신규 15 + 기존 24 집중 PASS, 전체 **1471/1471 pytest PASS exit0**(이전1456+15), handoff 30작업/40필수 PASS, pycompile PASS. Mac 현지 실제 OS clock 합성 KR+US 두 cohort/Top-K 원분모4/unknown4/영수증2, 파생 JSON ZIP SHA 복원, 원본 시세·증빙 SHA 불변, API0. Public git exact4 scoped safety scanned4 suspicious0, code commit/push **`14ec1347c322a720d043e7ef921dfcb03b1e9b7e`**, remote SHA same/직후 clean. 최신 STATE/START docs 이후 SHA는 git에서 확인.
- **NEXT** 2_2/2_5 실제 KRX/DART/SEC issuer/class·상폐 cash·기업행동·독립 공시 PIT 원천 및 5_5 미래 first-write 코호트 만기 outcome 실증. D-017 API 연결 나중, D-021 물리 SSD 분리/재연결·재부팅 최종. **API 제외 로컬 개발률 약91%(추정)**. 정상코드 CONTINUE/REWRITE 금지.

## 2026-10-11 최신 — 2_2/2_5 양 공급자 PIT 종목군·이미 효력 발생한 상폐/합병 모순 차단

- Mac/T5DATA 온라인, 시작 main `5e43bcc` clean. 기존 두 공급자 `provider_dual_source_audit.py`가 **각각 이미 알려진 delist/merger 이벤트(유효 종료일 도래)를 보유하면서도 동일 ID를 open-ended active membership으로 선언한 경우**, 서로 자료가 일치한다는 이유만으로 STATUS_CONSISTENT를 반환하던 **실제 RED 결함 수정**. 신규 blocker SOURCE_A/B_KNOWN_TERMINAL_EXIT_STILL_ACTIVE와 과거 종료종목 active count 제외, 미래 exit/이미 종료된 interval은 정상 처리. `provider_candidate_gate.py`의 기존 PAIR blocker 전달로 정상 WATCH 생성 차단. 별도 API/실제 시장원천 조회 0, 실전 인증 false.
- 정확히 4개 코드 릴리스: `src/eraleader/provider_dual_source_audit.py`, `tests/test_provider_dual_source_audit.py`, `tests/test_provider_candidate_gate.py` 수정(신규 회귀6), 신규 `docs/97_TERMINAL_EVENT_MEMBERSHIP_PIT_CONTRADICTION.md`. focused **66/66 PASS**, 전체 **1477/1477 pytest PASS(exit0)**(기존1471+6), handoff 30 작업ID/40 필수 PASS, pycompile PASS. Mac synthetic KR claimed supplier A/B 실제 CLI 결함쌍 BLOCKED/정상쌍 research matched, 원본 SQLite SHA 불변, derived JSON-only ZIP 복원 PASS, API0/공식리더0. Public Git code4 safety scanned4 suspicious0, code push SHA **`780991a211894dc6fb982de855f8e0a249d6e72a`**, 원격·로컬 동일/code 직후 clean.
- NEXT **실제** KRX/DART/SEC 기업ID·상폐 cash/기업행동/공시 발표·수집시각 및 PIT 당시 전체시장 독립 원천 검증, 미래 first WATCH/Top-K 코호트 결과 성숙 후 precision/오탐/lead days. D-017 API 연결 나중, D-021 SSD 실제 탈착·재연결/재부팅 최종. **API 제외 개발 진도 약91~92%(추정)**, 공식 leader0/실전 precision N/A. 정상 코드 CONTINUE/REWRITE 금지.

## 2026-10-11 최신 — 5_3/5_5 native WATCH·첫 계산점수 원본을 코호트 성능평가 원장에 강제 연결

- Mac/T5DATA Online, 시작 main `3f470ec` clean. 이번 신규 `native_census_gate.py`, `test_native_census_gate.py`(22), `docs/98_NATIVE_PROSPECTIVE_CENSUS_GATE.md`, 선택 CLI `scripts/run_prospective_census.py --receipt-index --native-evidence-config`만 수정. 기존 WATCH/score/native freeze/PIT/MarketOS 정상코드 REWRITE0. 최초 native WATCH 양성 전체·4요소 계산식/피처 bytes/첫 numeric score·native binding 원문 SHA를 `ranked_maturity.audit_ranked_maturity`로 재검증, O_EXCL census 등록 전후 및 전체 indexed registry 평가에서 fail closed. 일반 순위 파일·누락 점수·위조 자료가 native cohort로 들어갈 수 없음. strict 최초 marker `<registry_dir>_native_required.json` 생략/변조 CLI 다운그레이드 금지. 로컬 OS/공급자 원본 독립 인증 아님.
- 신규22·관련 기존 56 포함 집중 **78/78 PASS**, 전체 **1499/1499 pytest PASS(exit0)** (이전1477+22), handoff 30ID/40필수 PASS, pycompile PASS. Mac 실제 OS-clock synthetic KR WATCH2→native score2→Top1 freeze→strict CLI register/audit/JSON-only ZIP SHA 복구 PASS, 원본 SHA 불변, 시세 실물/미래 outcome 없는 연구용 N/A·official leader0; 시험 feature 손상 시 CLI exit2. Public scoped Git code4 안전검사 scanned4 suspicious0, code main push **`53ce563d5d6965c873cfbfda8a097134362ccb70`**, local/remote 동일/코드 직후 clean. 현재 상태문서 후속 commit SHA는 실제 Git 우선.
- NEXT 2_2/2_5 **진짜 공인** issuer/security-class/상폐 cash·기업행동/공시 최초 게시·수집시각/전체 역사 PIT 공급자 증거, 5_5 지금부터 누적될 prospective WATCH/Top-K의 미래 만기 실제 outcome/오탐/precision·lead-days 실증. D-017 외부 API 이후, D-021 SSD 물리분리·재연결/재부팅 마지막, 실전 leader0·precision N/A. **API 연동 제외 로컬 기능 진행률 약92%(추정)**. 정상 코드 CONTINUE/REWRITE 금지.

## 2026-10-11 최신 5_5 — 첫 prospective Top-K 전체 코호트 선행일/오탐률 검열 통합평가

- Mac/T5DATA online, 시작 main `6403a54` clean. 이전 WATCH/native score/freeze/원장/MarketOS 정상코드 REWRITE0. 수정 `ranked_outcome_receipts.py`(source 일치 early lead-day full-K histogram + known 실패율), `prospective_census.py`(전체 코호트 수치 histogram 실제 pooled median, 전체 K 결과 미확인 검열 고려 FDR floor/ceiling), 신규 `test_census_lead_discovery_metrics.py`(**13**), `docs/99_CENSUS_POOLED_LEAD_AND_FALSE_DISCOVERY.md`. 개별 코호트 중앙값 단순 평균 금지, 원래 고정 K 보존, 가짜 lead/오염 source/자료 누락은 성과0으로 오인하지 않음. 13 RED → 13 GREEN, 전체 **1512/1512 pytest PASS(exit0)**(이전1499+13), handoff 30ID/40필수 PASS, pycompile PASS.
- 실제 Mac CLI 합성 사전 KR+US 2-cohort K6 / hit3 / failure1 / unknown2 → 전체 중앙 lead4일(2/4/24), known 오탐률25%, K 전체 오탐 하한16.6667%·상한50%; indexed registry SHA 및 derived-only ZIP 복원·원본 SHA 불변. **인위시점 합성 평가로 실전 prospective precision/FDR N/A**, 독립 실제 주식 공시/issuer PIT 인증 없음, 공식 리더0/API0. Public code4 staged safety suspicious0, code commit/push **`813ded88c1246bca90407ca10b88592cf23832e6`** local/remote equal code 직후 clean. 이후 checkpoint docs SHA는 실제 git 우선.
- NEXT 진짜 KRX/DART/SEC issuer/security-class/상폐 현금·기업행동·공시 최초 발표와 시점별 전체 종목군 PIT 인증, 살아 있는 first WATCH/native Top-K 장기 미래 outcome 적중/오탐/lead days 실측. D-017 API 및 D-021 SSD 물리 재연결 최종 보류. **API 제외 로컬 개발 진행율 약93%(추정)**, 정상 코드 CONTINUE/REWRITE 금지.

## 2026-10-12 최신 — 2_2/2_5 상폐 지급 근거가 같은 claimed 기관인 경우 차단 + 자료 중간변조 차단

- Mac/T5DATA Online, 시작 main `694c9f5` clean. 기존 정상 WATCH/PIT/native score/Top-K/MarketOS/CycleOS 재작성0. 정확히 코드4파일: `src/eraleader/cash_payment_receipts.py`(issuer `publisher_id_claimed`와 결제증빙 `publisher_id_claimed` 동일할 때 research payout 차단, source alias 공백·대소문자 우회 거부), `src/eraleader/cash_exit_lineage.py`(그 issuer publisher 전달·cash/결정 및 평가 시점 issuer 입력 SHA 재검증·영수증 manifest/지급문서 최초/마지막 비교), `tests/test_cash_payment_receipts.py` 신규11, 신규 `docs/100_CASH_PAYOUT_PUBLISHER_SOURCE_INTEGRITY.md`. 합성 자료 TDD 5개 duplicate vendor RED 및 5개 mid-audit source revision RED 후 fix GREEN.
- 집중 **106/106**, 전체 **1523/1523 pytest PASS exit0**(기존1512+11), handoff 30 ID/40 required PASS, pycompile PASS. Mac 실제 `python -m eraleader audit-cash-delist` 합성 KR 동일 vendor source2 근거는 BLOCKED/payoff null, 서로 다른 self-claimed 기관이면 여전히 비공인 연구용 결과/합성10% payoff, 원본 파일 SHA 불변, derived ZIP 검증·새 폴더 복원 PASS, API/공식 leader0. PUBLIC Git 안전검사 staged4 suspicious0, code commit/push **`3ffd5a289f516be71bb57d64e8550e60c925b342`** local/remote SHA identical, code 직후 clean. 체크포인트 docs 후속 commit SHA는 git 우선.
- NEXT 2_2/2_5 실제 KRX/DART/SEC issuer/share class·상폐 cash·원본 공시 첫 공개시각/상장 상폐 전시장 PIT와 5_5 *실제* 미래 WATCH/Top-K outcome 장기 만기 증거. D-017 외부 API 연결 최종, D-021 물리 SSD 분리/재연결·재부팅 최종. 실제 PIT·실전 precision N/A/공식 leader0. **API 제외 로컬 진행률 약93%(추정)**, 정상코드 CONTINUE/REWRITE 금지.

## 2026-10-12 최신 2_2/2_5 — 회사 법인ID와 개별 주식클래스 PIT 로컬 원천 교차검증

- Mac/T5DATA online, 시작 main `a634e87` clean. 신규 `src/eraleader/issuer_class_bridge.py`, `scripts/audit_issuer_class_bridge.py`, `tests/test_issuer_class_bridge.py`(**24 테스트**), `docs/101_ISSUER_SECURITY_CLASS_DECLARED_PIT_BRIDGE.md`, 기존 `local_backup.py` sanitized issuer-class JSON allowlist 하나 추가. stage normalizer/issuer lineage 기존 read-only 재사용, KR corp_code+issue_uid / US SEC CIK+share_class_uid **회사+개별 class와 ticker/상장구간을 함께 비교**; ticker만 같은 다른 issuer/class 잘못 연결 차단, 1 issuer 여러 클래스2는 class2/entity1, 공시 시각·두 주장 공급자 독립성/상폐 effective action 및 US DST 검열, 중간 JSON/JSONL SHA 변조 검사. 정상 시장 소스/PIT/WATCH/native rank/MarketOS/CycleOS REWRITE0. 일치해도 official issuer PIT와 실전 skill N/A, research WATCH 자동승격0.
- TDD 신규 ImportError RED→24/24 GREEN, 전체 **1547/1547 pytest PASS(exit0)**(기존1523+24), handoff 30ID/40필수 PASS, pycompile/diffcheck PASS. Mac 실제 CLI 합성 KR matched class1, US same CIK two classes2, US ticker-only fake BLOCKED, KR source late RETROSPECTIVE_CENSORED 4가지, 원본 SHA 불변/파생 JSON ZIP SHA/새 경로 복원 PASS. Public Git stage5 safety suspicious0, code commit/push **`774355b69754748de27e0f0185982c22f3a87d73`**, remote/local equal code 직후 clean. 최신 STATE/START 후속 인계 docs SHA는 Git 최종 우선.
- NEXT 실제 KRX/DART/SEC issuer/class·상폐 cash·기업행동·공시 PIT 원본 최초 게시/수신시각/전시장 역사 universe 인증, 실제 미래 신규 첫 WATCH/native Top-K 코호트 수개월 뒤 만기 독립 performance/오탐·lead-days 실측. D-017 API 및 D-021 SSD 물리 탈착·재연결·재부팅 최종 보류. **API 제외 로컬 진행률 약94%(추정)**, 실제 대장주 확정0/실전 성능 N/A. REWRITE 금지.


## 2026-10-12 최신 — 최초 원시 SHA PIN과 법인/주식클래스 교차대조를 후보 WATCH 게이트에 실제 연결

- 시작 Mac/T5DATA `main 080aae2` clean, 기존 WATCH·Top-K·PIT·CycleOS/MarketOS 정상코드 REWRITE 0. 이전 `issuer_class_bridge` 단독 결과가 실제 후보 생성의 필수 증빙은 아니던 공백을 해결: 신규 `issuer_candidate_evidence.py` + `provider_candidate_gate.py`/CLI 최소 선택 확장. 기존 공급자 A+B 최초 원본 SHA PIN 선검증을 반드시 요구한 상태에서, 별도 issuer lineage와 실제 후보별 법인/주식클래스ID·ticker·상장구간 일치까지 봉인. 사후 공시·같은 ticker 다른 주식클래스·다른 claimed source·중도 원문 변경은 fail closed. 기본 파이프라인 불변, 실전 인증/PIT/공식 leader0.
- 코드·테스트·문서 정확히 5개 파일 (`docs/102_FIRST_PINNED_ISSUER_CLASS_WATCH_GATE.md` 참조), 신규 **15 pytest**, 관련 집중 54 PASS, 전체 **1562/1562 PASS exit0**, handoff 30개 ID/40필수 PASS, py_compile/diffcheck PASS. Mac 독립 CLI 합성 KR/US 각 WATCH1/ZIP SHA 복구 및 위조 KR WATCH0, 공급자/시장 SQLite SHA 불변, API·라이브 알림·SSD 물리 분리0.
- Public Git staged 5 `suspicious=0`; 코드 commit/push **`ffe8e85bb9d8704c0ed31e3efc6e453cd6d4c238`** local/remote main 동일/code 직후 clean. 최신 STATE/START docs 후속 SHA는 실제 git 우선 확인.
- **NEXT** 6_2 strict 원천 품질·보류 원인 표시의 opt-in 웹 화면, 2_2/2_5 KRX/DART/SEC 공인 최초 공개·수신·상폐현금/기업행동/PIT 역사 종목군 확보, 5_5 진짜 처음 신호 미래 outcome 만기 인증. D-017 API 연결 마지막·D-021 실제 SSD 물리 탈착/재부팅 최종. **API 제외 개발 진척 약94~95%(추정), 실제 예측 정확도 N/A**. 기존 정상 코드 보존.


## 2026-10-12 최신 — 6_2 후보 원천 품질/보류 사유 웹 대시보드 연결 (전체 1599 PASS)

- Remote Mac/T5DATA 기존 `main 1d06835` clean에서 시작. 기존 2-provider+first raw SHA PIN+issuer/class 연구 WATCH 게이트를 직접 재사용하며 선택 `offline-integrated --show-provider-gate-quality`의 실제 in-process gate verdict를 `site/provider_quality_kr.html`/`site/provider_quality_us.html`로 원자 출력. 양 공급자 일치·첫 원본 등록 PIN 확인/미요청·회사ID/주식클래스 정확 대조/미요청·불일치 차단 사유별 숫자를 별도 표시. 실제 WATCH blocked면 연구 성과·상태·joined runs **신규 0**, 진단 HTML만 출력. 미요청/합성 공급자 주장을 공인 PIT 인증으로 오인 금지; 원본 시세·CIK·회사 법인코드·개인키 웹/Git 배출0.
- 정확히 코드/테스트/문서 5경로: `provider_gate_quality_view.py`(신규), `cli.py`/`delivery.py` 최소 옵션·연구 화면 링크, `test_provider_gate_quality_view.py`(**신규37**), `docs/103_PROVIDER_GATE_QUALITY_LOCAL_WEB.md`. 전체 **1599/1599 pytest PASS(exit0)** (기존1562+37), handoff 30 ID/40파일 PASS, Python compile/공개 SHA 검증, Mac 합성 KR/US CLI 연구 WATCH 각1 / API0·공식 leader0, 충돌 자료 품질 HTML에서 blocker 보임/신규WATCH0, derived-only ZIP SHA/새 위치 복구, HTTP 200. 원본 provider/시장 SQLite SHA 불변. 실전 precision N/A.
- Public Git 안전검사 staged5 `suspicious=0`, 코드/main commit+push **`15d119ffc2d43f1f812906ebb6249c63e9dceb62`**, local/remote equal/code 직후 clean. 최신 STATE/START docs 후속 SHA는 실제 git 먼저 확인.
- **NEXT** 2_2/2_5 공인 KRX/DART/SEC issuer·security-class/공시 최초 이용 시점·거래소 역사 종목군·상폐 cash/기업행동 PIT 증거, 5_5 실제 초기 WATCH/Top-K 장기 미래 outcome/오탐·lead days. 이후 로컬 6_2 증빙상태 스냅샷 변동 추적 고려. D-017 외부 API 후순위, D-021 실제 SSD 분리·재연결/재부팅 마지막. **API 제외 진행률 약95%(추정)**, 실전 예측 정확도 N/A. 정상 코드 REWRITE 금지.

## 2026-10-12 최신 — 6_2·6_5 로컬 공급자 후보 품질 최초 기록/약화·보류 전환 SHA history (총1629개 green)

- Remote Mac/T5DATA 계승 `main 0cb2482` clean, 기존 정상 PIT/WATCH/native Top-K/MarketOS/CycleOS 재작성 0. 신규 `provider_quality_history.py`로 기존 실 후보 `audit_candidate_provider_gate` verdict를 **in-process** 원천으로 하는 opt-in 첫 이력 기록. 신규 `--record-provider-quality-history`는 기존 `--show-provider-gate-quality` + A/B provider ledger/bundle 필요. 글로벌 SQLite event_no+SHA chain과 별도 O_EXCL 최초 genesis SHA marker 연동, 내용/시간/삭제·중간변조 fail closed, 동일 증빙 재평가 이벤트 중복0, 당초 결정시각과 Mac OS 기록 시각 분리/소급 방어. WATCH 연구 허용→보류/재허용, 최초 PIN·issuer/class 증빙 강화/약화, blocker 변경을 기록. 실제 공인 PIT/시간 공증 아님.
- 신규 `site/provider_quality_history_kr|us.html`(품질 검증 페이지 링크) 및 sanitized market history JSON 안전 출력. 기존 기본 CLI·웹/상태·스케줄러 불변, vendor raw/비밀키 포함0. 코드/테스트/문서 정확히 6경로: `provider_quality_history.py`·`test_provider_quality_history.py`(신규30)·`docs/104_PROVIDER_QUALITY_HISTORY_LOCAL_FIRST_WRITE.md`, 기존 `cli.py`·`provider_gate_quality_view.py`·`local_backup.py` 선택 확장.
- TDD ImportError RED → 집중 PASS, 전체 `pytest tests -q --tb=short` **1629/1629 녹색 100%·실패0** (이전1599+30); 최초 실행 후 테스트 래퍼가 zsh 예약변수 `status` 대입 문제로 wrapper exit1을 냈지만 pytest 출력 100% green, 이후 Mac 실제 CLI/집중 EXIT0으로 동작 확인. handoff 30 ID/40파일, compile/diffcheck PASS. 실제 Mac KR·US synthetic 첫 연구 WATCH1·재실행 신규0, KR 후행 공급자충돌 신규WATCH0 / 검증이력 `WATCH_GATE_BLOCKED`, localhost HTTP200, 원본 SHA 무변형, sanitized ZIP SHA verified/신규 복원·체인 감사 PASS. API/실전 발송0, official leader0, 실전 미래 적중 N/A.
- Public Git staged6 suspicious0, code commit/push **`1dfc9ee552405d0b027cc860ff8c09361685b978`** local/remote main 동기화/code 직후 clean. 이 START/PROJECT_STATE 별도 docs checkpoint SHA는 실제 git 우선.
- **NEXT** 6_5 로컬 이력 chain 실패·품질약화 DRY-RUN 운영 탐지 또는 5_5 미래 최초 등록 WATCH/native Top-K 후속 outcome 검열 검증. 실제 공식 KRX/DART/SEC PIT/상폐 cash·첫 공개·수신·시장전체 역사 인증과 장기 실전 적중은 미완료. D-017 외부 API 마지막, D-021 SSD 물리 탈착/재연결/재부팅 최종. **API 제외 진행률 약95~96%(추정), 실전 leader accuracy N/A**. REWRITE 금지.

## 2026-10-12 최신 — 6_5 품질 약화 및 SHA 무결성 이상 DRY-RUN 감시/예약 연계 (전체 1660 PASS)

- 원격 Mac/T5DATA `main c63e804` clean에서 CONTINUE. 원본 `provider_quality_history`의 전체 SHA 체인/genesis/순번을 잠금 아래 **READ-ONLY**로 검사하고 별도 O_EXCL marker·SQLite SHA 체크포인트 `provider_quality_watchdog.py`를 신규 구현. 과거 이력의 자기일관적 롤백·공동 재생성/개별삭제·원문 변조·미래시각, first-PIN/issuer-class 강도 약화·실 WATCH 보류/새 blocker를 **미발송 로컬 경고**로 탐지. 동일 상태 재실행 경고0, 기존 정상 WATCH/native score·PIT·MarketOS/시세·scheduler 기본 동작 재작성0.
- `scripts/run_local_scheduled.py --provider-quality-dry-run` **선택 예약 연계**, 독립 `scripts/run_provider_quality_dry_run.py` 명령, 정적 HTML·파생 JSON·SHA ZIP 4개 파일 온라인 백업·신규 경로 복원. 신규31 pytest + 기존1629 → 전체 **1660/1660 PASS(exit0)**, handoff 30 ID/40필수 PASS, pycompile/diffcheck PASS. Mac 현지 합성 KR/US CLI 원본 복제본 신규 경고2→반복0→자기일관적 원장 교체 경고1→복원 경고1, 원본 SHA 불변/API·발송·공식 leader0. 실전 PIT·prospective precision N/A.
- Public Git staged6 safety `suspicious=0`, 코드 commit/push **`4a68464367e50b2104b6663a3dfc41235016aad5`** 원격과 동일/직후 clean. 상세 `docs/105_PROVIDER_QUALITY_DRY_RUN_SHA_WATCHDOG.md` 및 `PROJECT_STATE.md` 맨 아래. **NEXT** 공인 KRX/DART/SEC 역사 PIT·상폐 cash·공시 최초시각 및 5_5 실제 미래 등록 코호트 장기 outcome; 6_5 OS launchd 옵션 실설치는 후속 운영 단계. D-017 API 마지막·D-021 SSD 실제 탈착/재연결/재부팅 최종. **API 제외 기능 진행률 약96%(추정)**, 실제 발견 정확도 미인증. 정상 코드 보존.

## 2026-10-12 최신 — 5_5 최초 코호트 만기·미확인 결과증빙 전수 추적 (전체 1692 PASS)

- Mac/T5DATA main `65a2eae` clean에서 CONTINUE. 새 `prospective_due_followups.py`는 sealed census + SQLite first-write receipt index/native positive WATCH·original feature SHA 검증을 재사용, **전체 KR/US 최초 등록 Top-K** 만기 UTC와 outcome/receipt 미수집·쌍 미완성·자료 검열·현지 연구상 known을 분리. 누락/검열 K를 성과0으로 오인하지 않고, source 폴더·티커/issuer ID 웹 반출0. 새 선택 `scripts/run_prospective_census.py audit --receipt-index --due-followups [--native-evidence-config ...]`는 `prospective_due_followups_research.json`·로컬 HTML 원자 발행, 기본 CLI 불변. 파생-only 안전 ZIP 복원/로컬 HTTP200 실측.
- 신규32·전체 **1692/1692 pytest PASS(exit0)**, handoff 30 ID/40필수 PASS, py_compile/Git Public safety staged5 suspicious0. 실제 Mac 합성 KR/US 첫 등록 코호트2/K4 미만기2, 과거 합성 코호트2/K6 만기2/unknown2, 결과자료 누락 오탐 승격0/API·메시지0. 정확히 5파일 코드 릴리스 commit/push **`751532086a537b897f44d798b7bc904039933ddb`**, local==remote main/code 직후 clean. 세부 `docs/106_PROSPECTIVE_COHORT_DUE_FOLLOWUPS.md`·`PROJECT_STATE.md` 맨 아래.
- **NEXT** 5_5 실제 전향 WATCH/native Top-K가 미래 만기된 뒤 공식 independent outcome/first published data 확보 및 2_2/2_5 KRX/DART/SEC issuer/security-class/상폐 현금/기업행동/공시 최초 수신·전시장 PIT 독립 증빙, 6_5 local 운영 통합. D-017 외부 API 마지막, D-021 SSD 물리 재연결·재부팅 최종. **API 제외 기능 진행률 약96~97%(추정)**, 실전 발견 정확도·공식 리더 인증 N/A. 정상 코드 보존.

## 2026-10-12 최신 — 5_5·6_5 만기 코호트 미확인 outcome DRY-RUN 예약 경고 (전체 1724 PASS)

- Mac/T5DATA 원격 온라인, main `e5f4e0d` clean 기준 기존 sealed census/native WATCH/score/PIT/MarketOS/CycleOS 코드 그대로 CONTINUE. 신규 `prospective_due_alerts.py` + standalone CLI 및 `scripts/run_local_scheduled.py --prospective-due-registry ... [--prospective-due-native-config ...]` **명시적 선택**. 기존 `prospective_due_followups.py`의 만기 gap 전체 코호트 SHA fingerprint(표시500개 넘어도 탐지)를 재사용, 최초 gap/변경/로컬 해소 및 원시 index·native 증빙 불신/부분삭제/이전 버전 SHA rollback을 별도 O_EXCL+SQLite event SHA chain에 **DRY_RUN_NEVER_SENT** 기록. 동일 상태 중복0, 신선도 차단·기존 알림·실제 LaunchAgent 설정 보존. derived JSON+웹+SQLite+genesis 4파생 ZIP SHA/새 경로 복원 PASS.
- 코드/테스트/문서 8경로, 신규 **32** pytest·전체 **1724/1724 pytest PASS EXIT0**(기존1692+32), handoff 30ID/40필수 PASS, compile/diffcheck PASS. Mac 실 OS-clock 기존 KR/US 합성 첫등록 원장 *복제본* 최초 경고1/반복0/index 부분삭제 감지1/복원 경고1, 외부 메시지0/API0, localhost HTTP200. 공개 Git staged8 safety suspicious0, code commit/push **`5164eaf887380b4405bc454b1559b0409c30a64f`** 로컬/원격 동기화/직후 clean. 세부 `docs/107_PROSPECTIVE_DUE_DRY_RUN_ALERTS.md`, `PROJECT_STATE.md` 맨 아래.
- **NEXT** 2_2/2_5 KRX/DART/SEC 공인 issuer/class·cash delist/기업행동/공시 최초 게시·수신시각/전체 역사 universe PIT 독립 자료 + 5_5 자연 만기 prospective watch/native Top-K의 실제 미래 outcome 정답·오탐·lead-days 확보. D-017 외부 API 최종, D-021 SSD 물리 탈착·재연결/재부팅 마지막. **API 연결 제외 개발률 약97%(로컬 기능 추정, 공식 대장주 성능 N/A)**. REWRITE 금지.

## 2026-10-12 최신 — 2_2·2_5 제3 선언 거래소 전체 증권 클래스 명부 PIT 대조 (전체1757 PASS)

- T5DATA Mac online, 시작 local/remote main `ca3bdb1` clean. **신규** `exchange_roster_crosscheck.py`가 기존 issuer-class bridge/공시 revision/기업행동 source를 READ-ONLY 재사용하여 **세 번째 claimed 전시장 전 클래스 명부**의 법인+주식클래스·ticker·상장기간·KR/US 당시 시장 현지 day/DST/선행 발표·late retrieval/동일 claimed 발행기관 여부를 정확히 대조. 기존 두 출처가 모두 빠뜨린 클래스/같은 ticker 다른 주식 클래스를 차단. 모든 일치도 **공식 거래소 원본 PIT 아님**, leader0/실전 precision N/A/API0.
- 실제 신규 5경로(신규 src+CLI+test33+docs108, 기존 `local_backup.py` derived allowlist 하나만 확장), 새 33/33 + 기존1724 **전체1757/1757 pytest PASS(exit0)**, handoff 30ID/40필수 PASS, Python compile/diffcheck PASS. Mac 실제 CLI 합성 KR·US 각 일치1 및 제3 명부 가짜 extra class 차단1, 원본 SHA 보존/파생 JSON-only ZIP SHA 신규 디렉터리 복원 PASS. Public Git staged5 safety suspicious0, code commit/push **`20ad04b011550a53add2b6258711dddf934302b3`** local/remote 동일/코드 직후 clean. 세부 `docs/108_THIRD_EXCHANGE_ROSTER_PIT_CROSSCHECK.md`, `PROJECT_STATE.md` 마지막 기록 참조.
- **NEXT** 2_2/2_5 실제 KRX/DART/SEC·공식 거래소 issuer/class/기업행동/상폐현금/당시 전체 universe 및 **최초 게시·수신시각** 독립 근거, 5_5 실제 first prospective WATCH/native Top-K 수개월 만기 결과. D-017 외부 API 맨 뒤, D-021 실제 SSD 물리 탈착·재연결·재부팅 최종. **API 제외 진행률 약97%(로컬 기능 추정), 실전 발굴 성능/공식 PIT 인증 N/A**. 정상코드 CONTINUE/REWRITE 금지.

## 2026-10-12 최신 — 제3 전체 거래소 명부를 실제 WATCH 게이트에 필수 조건으로 opt-in 연결 (1784 PASS)

- Mac/T5DATA 온라인, 시작 `main db00f4c` clean. 기존 2공급자 최초 원문 SHA PIN + issuer/share-class candidate gate에 **제3 whole-exchange roster SHA/당시 전체시장 목록**을 실제 `offline-integrated` 후보 WATCH 발행 전 opt-in으로 연결. `provider_candidate_gate.py` `exchange_roster_file`/`exchange_roster_sha256`, CLI `--require-provider-exchange-roster --provider-exchange-roster --provider-exchange-roster-sha256`는 반드시 기존 4 raw PIN·issuer-lineage 선택을 요구하며, 명부 누락/과잉/명부 위조·미수집 출처는 신규 WATCH/run/prospective 0. 무옵션 기본 동작 유지, 원천 법적 PIT 인증/실전 성능 N/A.
- 코드/테스트/문서 **4파일**, 신규27+기존1757 **전체1784/1784 pytest PASS(exit0)**, 관련 집중 PASS, handoff 30ID/40필수 PASS, compile/diffcheck PASS. Mac 실제 CLI KR/US synthetic 각각 연구 WATCH1, 각 시장 제3 roster 가짜 extra class BLOCKED/WATCH0, 원본 SHA 불변/파생 JSON-only ZIP SHA/신규 위치 복원 PASS, API·실전 발송·공식 leader0. Public scoped Git safety staged4 suspicious0, 코드 main commit/push **`d1671acf913795456082dcfda4dc7e170efdf401`** local/remote 동일/직후 clean. 상세 `docs/109_PINNED_EXCHANGE_ROSTER_PRE_WATCH_GATE.md`, `PROJECT_STATE.md` 최하단.
- **NEXT** 2_2/2_5 공식 KRX/DART/SEC 최초 공개/받은 시각과 issuer/share-class/상폐 현금·기업행동/거래소 역사 full universe 외부 증거, 5_5 real first-WATCH/native Top-K 미래 만기 outcome. D-017 API 연결 후순위, D-021 SSD 실제 물리 분리·재연결/재부팅 최종. **API 제외 로컬 개발률 약97~98%(추정), 실전 skill/PIT 인증 미완료**. 정상 코드 보존.

## 2026-10-12 최신 — 제3 전체시장 roster WATCH 엄격모드 최초 고정/다운그레이드 차단 (전체1806 PASS)

- Remote Mac/T5DATA `main ff55f8f` clean 시작, 2_2/2_5/4_1/6_5 **신규 `exchange_roster_policy.py`** + `cli.py.execute_integrated` 얇은 보호 래퍼. 최초 사용한 **완전한** 2 supplier raw PIN + issuer/class + 3rd whole exchange roster SHA 엄격 옵션을 시장별 KR/US **O_EXCL first-write policy/guard SHA 두 문서**로 자동 봉인. 이후 해당 출력루트/해당 시장에서 무옵션·원본검사 하나라도 빠진 WATCH 재실행/배치 직접 호출은 원본 SQLite 접근 전에 차단. 원래 엄격 최초 BLOCKED 후에도 fallback 금지, 기존 미사용 저장소와 기본 동작은 보존. 다음 거래일 새로운 roster SHA는 strict 검증 시 허용. 파일 한쪽/동시삭제(락 남음), 위변조, 동시 실행, 중도변조 fail-closed; 단 로컬 전체 파일 동시 삭제/위조 및 OS clock은 공식 공증 아님.
- 신규22 + 기존1784 → **1806/1806 pytest PASS(EXIT0)**, 91 modules, handoff 30ID/40필수 PASS, pycompile/diffcheck PASS. Mac KR/US 합성 CLI 각 strict WATCH1, roster fake 클래스 차단 WATCH0, 이후 약한 재실행 2시장 각 exit2·prospective SHA 불변. derived output ZIP SHA verified(시장별 10파일)/새 폴더 restored marker+guard 확인 후 downgrade 재실행 exit2. 신규 `docs/110_STICKY_EXCHANGE_ROSTER_WATCH_POLICY.md`, 정확히 코드/테스트/문서 **5파일** scoped release Public Git safety scanned5 suspicious0; commit/push **`bbd43ce9e7c62bf29f9be5533d7f9ab4a87ded1d`**, local==remote clean/code 직후. `PROJECT_STATE.md` 최하단 상세 참조.
- **NEXT** 2_2·2_5 공인 KRX/DART/SEC 법적 issuer·상폐 현금/기업행동/첫 공시 공개·실제 first retrieval/거래소 전체 역사 universe PIT 인증, 5_5 실전 prospective first WATCH/native Top-K 수개월 미래 진짜 outcome/precision/FDR/lead-days. D-017 외부 API 최종, D-021 SSD 실제 물리 탈착·재연결·재부팅 최종. **API 제외 로컬 기능 진행률 약98%(추정); 실전 예측·공식 PIT 인증 N/A**. 정상코드 보존.

## 2026-10-12 최신 — 6_5 첫 엄격 거래소 명부 정책 무결성 DRY-RUN 예약 경고 (전체 1888 PASS)

- 직전 기준 GitHub origin/main 코드 커밋 `ac52d6a7ffa853bf7dc2dab5775e51ff83955b0a` 푸시/원격 SHA 동일 검증. 정확히 5개 코드/테스트/문서 경로 릴리스: `docs/112_STICKY_ROSTER_POLICY_SCHEDULED_WATCHDOG.md` 참조. 현재 별도의 기존 미커밋 `src/eraleader/native_first_capture.py` 7줄은 **다른 작업 수정으로 보존하고 무단 포함하지 말 것**.
- KR/US 기존 first-write whole-exchange WATCH 정책·guard·lock의 파일 전체 소실/수정/자체 일치 위조·록 부재를 SHA 제3 이력으로 독립 읽기 확인; 최초 정상 policy SHA·감시 첫 event O_EXCL/보고서 head SHA·UTC 체인 봉인. 기존 정상 WATCH/Top-K·PIT·원본 주가 수정 0. `scripts/run_exchange_policy_watchdog.py --project ... --policy-out <원래 strict output>`, opt-in `scripts/run_local_scheduled.py --exchange-policy-out <동일경로>`. 미전송 DRY-RUN 보고 JSON+사이트만 출력.
- 신규 감시 집중 **25/25 PASS**, 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1888/1888 PASS(EXIT0)** / 94 modules, handoff PASS, Git Public staged scanned 5 suspicious 0. 외부 API/실전 메시지/SSD 물리 분리·재부팅 0. OS clock·사용자 주장 issuer/exchange roster는 **공인 PIT 인증 아님**.
- **NEXT**: 5_5 최초 native 코호트 original first-WATCH/numeric score/features/label의 원본 SHA 검증·비공개 안전 보관/복원과 prospective 장기 followup. 실제 독립 KRX/DART/SEC issuer/class/상폐/기업행동/공시 first-published, 미래 공식 outcome은 D-017 API 연결·자연 성숙 후; SSD 물리 재연결은 D-021 마지막. API 제외 구현 약 98%(추정). REWRITE 금지, CONTINUE 우선.


## 2026-10-12 최신 — 5_5·6_5 최초 native WATCH 원본 피처·score·census 안전 백업/복원 (1906 PASS)

- 실제 Mac/T5DATA에서 기존 main 73285b9 기반 CONTINUE. 원래 first-native Top-K 완료 코호트의 first WATCH SQLite, numeric score SQLite, 전수 feature JSON, label definition, predeclared plan, frozen Top-K, first source config, census manifest/index/marker, first capture receipt·lock을 함께 SHA-256 private ZIP으로 묶는 신규 모듈 src/eraleader/native_evidence_archive.py 및 CLI scripts/archive_native_first_evidence.py. docs/113_PRIVATE_NATIVE_ORIGINAL_EVIDENCE_VAULT.md 참조. 기존 native_first_capture.py의 다른 세션 미커밋 7줄은 이번 릴리스 미포함/보존.
- 최초 ZIP 저장/검증→별도 새 폴더 복원(원본 절대경로 덮어쓰기0)→복원된 first WATCH·score·feature 근거 계산/첫 census index SHA chain 확인. 복원 시 최초 별도 저장된 ZIP SHA 요구. T5DATA hard link 미지원 Errno45 확인 후 O_EXCL 새 ZIP 스트리밍 복사·fsync+SHA 검증으로 고쳐, Mac의 기존 KR+US **합성** 증거 각 15파일 원본 SHA 불변/복원 replay PASS, 실제 API0·전송0·공식 leader0. private ZIP과 원본 경로는 output Git ignore, 암호화/외부 안전 보관 미설치. README성 문서 docs/113.
- 집중 신규 18/18 PASS, 전체 1906/1906 pytest PASS EXIT0, 95 modules, handoff 30ID/40files PASS, pycompile/diffcheck·Git staged security scanned4 suspicious0. 코드 commit+push ab50c92ae239d7c8044aca104284fb6005747d0e origin/main·로컬 동일. PROJECT_STATE.md 최신 기록 참조.
- 다음 미완료: 5_5·6_5 이미 first-native capture 성공 후 source ZIP 보관을 수동으로 빠뜨리지 않도록 **명시적 opt-in 예약 자동화** + 독립 안전 SHA 백업 정책, 다수 prospective Top-K 장기 실증. 공식 독립 KRX/DART/SEC issuer/share class·상폐/기업행동/공시 최초 수신과 1~12개월 진짜 미래 outcome은 API D-017 최종·관측 기간 후, 물리 SSD 분리·재연결/재부팅은 D-021 최종. API 제외 기능 구현 약98%(추정, 성능 인증률 아님). CONTINUE NOT REWRITE.


## 2026-10-12 최신 — 5_5·6_5 최초 Top-K 직후 private 원본 ZIP/SHA 자동 봉인 예약 (1929 PASS)

- 시작 local/origin main 09f5665, Mac T5DATA 온라인. 기존 first-native freeze/registered census와 민감 원본 private archive 기능을 재구현하지 않고 연결. 신규 src/eraleader/scheduled_native_archive.py + tests/test_scheduled_native_archive.py + docs/114_SCHEDULED_NATIVE_FIRST_PRIVATE_ARCHIVE.md 및 기존 scripts/run_local_scheduled.py 1개만 최소 선택 변경. --native-first-private-archive 는 기존 --native-first-capture-plan 과 동시 사용 시에만 활성화. WAIT 원본 미확보 시 파일0, 완료되면 docs/113 private ZIP 자동 생성 + 별도 로컬 O_EXCL SHA 첫 receipt/guard/lock 봉인. 동일 모델 반복에서는 새 ZIP0·기존 SHA 검증. 부분손상/결손·archive 중단은 새 첫 SHA로 소급 복구 불가. KR/US 멀티 모델 preflight 중복 차단, 기존 stale 오류·무옵션/LaunchAgent 보존.
- Mac 실제 합성 KR+US native 첫 원본 각 read-only 관측 → ZIP/receipt 첫 등록 → 재실행 첫 SHA 동일·원본 바이트 SHA 6개 각각 보존, API·실전 발송0. 결과 ignored output/verification_logs/scheduled_native_archive_os_e2e_20261012.json. 신규 **23/23** 집중, 전체 **1929/1929 pytest PASS FULL_EXIT0, 96 modules**, handoff 30ID/40files, Public Git scanner scanned4 suspicious0. 코드 commit+push 8f37dc4db012dab83bb8527da53b14e7ccb85b4c origin/main, 로컬 SHA 동일 검증. 기존 별도 미커밋 src/eraleader/native_first_capture.py (7줄)은 stage/commit하지 않고 보존. 본 STATE/START는 후속 docs-only checkpoint.
- **한계/NEXT**: private ZIP과 별도 첫 SHA receipt가 동일 T5DATA에 있어 외부 공증/동기화/암호화 백업은 아님, 문서 README docs/114 확인. 공식 KRX/DART/SEC PIT/상폐cash/issuer-class/기업행동·공시 첫 게시/수신, 실전 미래 Top-K 만기 결과는 API D-017 및 자연 시간경과 뒤. SSD 물리 분리·재연결·재부팅 D-021 최종. API 제외 로컬 기능 추정 **약98%**, 실제 미래 대장주 발견 성능 인증률과 구분. REWRITE 금지, 정상 코드 보존.


## 2026-10-12 최신 — 6_5 native 첫 ZIP SHA 영수증 Mac 별도 디스크 선택 보관 (1956 PASS)

- 시작 local/origin 9a15810 main, Remote Mac/T5DATA Online. 직전 docs/113~114 기존 first native Top-K 등록+민감 private ZIP SHA를 재작성하지 않고, opt-in 별도 파일시스템 witness를 실제 연결. 신규 src/eraleader/native_sha_witness.py + scripts/verify_native_sha_witness.py + tests/test_native_sha_external_witness.py(17), tests/test_scheduled_native_witness_bridge.py(10), docs/115_CROSS_VOLUME_NATIVE_SHA_WITNESS.md, 기존 scripts/run_local_scheduled.py 최소 확장. --native-first-internal-witness-root 절대 경로는 기존 --native-first-capture-plan + --native-first-private-archive와 함께 입력할 때만 활성. Mac stat.st_dev가 T5DATA SSD와 동일이면 실행 전 차단, symlink/원본 경로 중첩/개방 권한 및 첫 SHA partial write 차단. 별도 디스크에는 원본 ZIP/issuer/시세가 아닌 SHA+로컬 당시 시각/nonce/guard만 O_EXCL 최초 기록, 후속 동일 슬롯 최초 재기록0·ZIP/SHA 변조 사전 검증, 별도 읽기 전용 CLI. OS 시각/같은 Mac 관리자 2디스크 공동 위조의 외부 독립 공증은 불가능.
- 실제 Mac T5DATA와 /private/tmp 다른 디바이스 검증, 기존 합성 KR+US 최초 원본 ZIP SHA와 Mac 임시 별도 SHA witness 각 first+repeat+read-only subprocess CLI 검증 PASS, 원본 6파일 x KR/US SHA 변화0, API·발송·공식 leader0. 임시 Mac witness는 테스트 종료 후 제거돼 운영용 Mac 내부 witness 자동 설치0. ignored output/verification_logs/native_sha_cross_volume_mac_e2e_20261012.json.
- 신규 집중 27/27 PASS, 전체 **1956/1956 pytest PASS FULL_EXIT0 / 98 modules**, handoff30ID/40files PASS, Python compile/Git diffcheck PASS, staged 공개 Git 보안 scanned6 suspicious0. 코드 commit/push 9023182b004d9894426993dfc149de61d35c22c0 origin/main remote SHA 직접 동일 확인. 별도 이전부터 있던 미커밋 src/eraleader/native_first_capture.py 7줄은 재작성·stage·commit 없이 계속 보존. 본 STATE/START docs는 후속 docs-only checkpoint.
- NEXT: 6_5 다중 모델 native first ZIP SHA witness 누락·변조 로컬 DRY-RUN 감사 화면/알림, 암호화 원본 ZIP 외부 보관은 미구현 별도 기능. KRX/DART/SEC 공식 역사 PIT 및 자연 1~12개월 만기 미래 대장주 outcome 검증은 D-017 API 후반·미래 기간 경과 이후, 실제 물리 T5DATA SSD 탈착/재연결/재부팅은 D-021 최종. API 제외 기능 구현 약98% 추정, 공식 PIT/실제 예측성능 인증 아님. CONTINUE; NO REWRITE.

## 2026-10-12 최신 — 6_5 다중 코호트 native SHA 별도 디스크 DRY-RUN 자동 감시 · 로컬 웹 연결 (1986 PASS)

- Mac/T5DATA 원격 online, 시작 main f1fffe8에서 **실제 6_5 신규 기능**: docs/113~115의 기존 original first ZIP/SSD SHA receipt/별도 Mac SHA witness 재사용; src/eraleader/native_sha_watchdog.py로 KR/US 최초 native 코호트 다중 계획 1~128개 전체 감시, 최초 성공한 원본 ZIP+외부 witness SHA PIN 고정, 목록에서 탈락/ZIP·영수증·guard/lock·외부 SHA 손상·교체, 대기/부분 봉인 구분, 중복 사고 경고0/복구 RESTORED. 기원/첫 event/전수 상태 chain+checkpoint 첫 SHA 검증, 원본 수정0/API·전송0.
- 신규 scripts/run_native_sha_dry_run.py 단독 CLI, scripts/run_local_scheduled.py --native-sha-dry-run-plan(반복) --native-sha-dry-run-witness-root 예약 opt-in, 기존 stale 차단/무옵션/LaunchAgent 유지. output/site/native_sha_dry_run.html 안전 미러+기존 index 진입 링크 및 output/native_sha_alerts/site/index.html.
- 신규 집중 **30/30 PASS** / 최종 **1986/1986 pytest PASS EXIT0, 100 modules**, 30 개발ID/40 필수 handoff PASS, compile/diffcheck PASS. Mac T5DATA vs /private/tmp 실제 이기종 dev에서 합성 KR·US 두 코호트 CLI 첫정상0→반복0→실험 guard 이상신규1→반복0→복구1, HTTP 200, raw original SHA 불변, 실전 공인 PIT/leader0. 정확한 코드/테스트/문서 6경로 보안검사 scanned6 suspicious0. **코드 main commit/push f2265f4a90fa647e0c1bf16b7e1f741f09526f5b**, remote 동일. 기존 별도 미커밋 src/eraleader/native_first_capture.py 7줄 변경은 이번 작업 stage/수정/commit 제외해 보존.
- **NEXT**: 6_5 상시 운영 내부 witness 실제 경로 설치 여부(지금은 사용자 명시적 옵션만), 암호화 원본 ZIP 외부 백업, 2_2/2_5 KRX/DART/SEC 법적 PIT/상폐cash/최초 timestamp 공식 교차검증 및 5_5 native prospective 최초 진짜 만기 outcome. D-017 API 맨 뒤, D-021 실제 SSD 탈착·재연결/재부팅 최종. **API 제외 약98~99% 로컬 기능 추정, 공식 미래 성능/PIT 인증 N/A**. docs/116, PROJECT_STATE.md 맨 아래를 기준으로 CONTINUE/REWRITE 금지.

## 2026-10-12 최신 — 6_5 별도 디스크 first native 원본 AES-256-GCM 암호화 ZIP/SHA 재해복구 (2009 PASS)

- Mac/T5DATA online, 시작 local/origin main 13af8d8. 기존 docs/113~116 original first native score/WATCH/census·비공개 ZIP/SHA witness 재사용: OpenSSL CMS AES-256-GCM + RSA-OAEP **암호문만** 별도 Mac 디스크에 O_EXCL 최초 SHA receipt/guard/lock으로 저장하고, 원본 ZIP+first SHA+인증서 SHA를 봉인. 새 src/eraleader/native_encrypted_vault.py, CLI scripts/native_encrypted_original_vault.py backup/verify/restore, 예약 --native-first-encrypted-vault-root/--native-first-encryption-cert opt-in만 추가. verify는 SHA만, restore는 owner600 private key로 GCM 인증 복호화+새 경로의 원래 first WATCH/score/census 완전 재생 검증. 원본 SSD가 없어도 별도 Mac SHA/암호문/키로 복구 가능. 사용자 운영 키 생성·vault 자동 설치0, API/메시지0, 실제 PIT 및 리더 성능 승격0.
- 신규 **23/23 집중 PASS**·최종 **2009/2009 pytest PASS(EXIT0), 102 modules**, handoff 30ID/40files, Mac 실제 서로 다른 device에서 KR 합성 original ZIP 암호화→반복0→원본 숨김 후 복원/replay 및 암호문 위변조 거부 exit2 PASS. Public staged6 files scanner suspicious0. 코드 main commit/push **c07c208eb27b60bb939f2f78716c6f9bd2547e03**, local/remote SHA 동일. 이전 미커밋 src/eraleader/native_first_capture.py 7줄은 미수정·무단 포함/commit 없이 보존. 실제 증빙·명령 docs/117 및 PROJECT_STATE.md 맨 아래.
- **NEXT**: 6_5 encrypted vault 자체 주기적 무결성/결손 감시 DRY-RUN 웹 결선(옵트인), 안전한 별도 Mac 비밀키/파일시스템 운영 설치는 사용자 명시 조합 이후. 2_2/2_5 공인 KRX/DART/SEC 원천 PIT/상폐 현금/첫 수신시각 및 5_5 실제 prospective future outcome은 D-017 API 후반 및 기간경과 뒤. D-021 실제 SSD 분리·재연결·재부팅 맨 마지막. **API 제외 로컬 개발률 약99% 추정 (실제 발굴/PIT 인증과 구분)**. REWRITE 금지, CONTINUE.

## 2026-10-12 최신 — 6_5 encrypted vault SHA 무결성/분실 다중 코호트 DRY-RUN 감시·로컬 웹 (2046 PASS)

- 시작 Mac/T5DATA origin main 2428988 clean(기존 별도 미커밋 native_first_capture.py 7줄 보존). 기존 docs/113~117 original first-native ZIP/SSD SHA/외부 SHA witness/암호문 AES-256-GCM을 재작성하지 않고 **src/eraleader/native_encrypted_watchdog.py**로 암호문·cert·first witness SHA-first PIN 감시, 1~128개 KR/US 모델 익명 슬롯 전체 경고/WAITING/RESTORED/목록누락/다운그레이드 탐지. 별도 O_EXCL genesis/first event + append-only SHA chain/마지막 report·private lock, 원본 자료/사용자 개인키/암호문 수정을 하지 않고 fail-closed. 독립 scripts/run_native_encrypted_dry_run.py, 기존 예약 scripts/run_local_scheduled.py --native-encrypted-watch-slot(반복)/--native-encrypted-watch-vault-root/--native-encrypted-watch-witness-root/--native-encrypted-watch-cert **명시적 opt-in**. output/site/native_encrypted_dry_run.html 및 index 링크. 설치된 launchd 변경/실전 전송/API/SSD 물리 제거·재부팅0.
- 신규 집중 **37/37 PASS**, 최종 **2046/2046 pytest PASS EXIT0 (104 modules)**, 30 개발ID/40필수 handoff PASS, compile/diffcheck PASS. Mac KR/US 실 OS 다른 filesystem 합성 crypt/witness 원본 실측 독립 CLI 정상0→반복0→guard 삭제경고1→반복0→복구경고1, localhost HTTP200, 원본 ZIP SHA 불변. Public Git staged6 안전 scanned6 suspicious0, 코드 commit/push **07a856a66d5aa1a94c5e0dd68406c9bcdb3a9e31**, 원격/local 코드 동일. 기존 native_first_capture.py 미커밋 수정은 이번 stage/commit 제외 보존. 자세한 새 문서 docs/118 및 PROJECT_STATE.md 최신.
- **NEXT**: 6_5 키 만료/수명·비밀키 권한·암호화 ZIP 복구 drill 이력, 별도 오프사이트 보관 설계/선택 설치. 2_2/2_5 공식 KRX/DART/SEC PIT·issuer/security class/상폐 정산·공시 첫 이용가능시각, 5_5 진짜 prospect outcome은 D-017 외부 API 후반 + 자연 경과 후 검증. D-021 SSD 물리 탈착/재연결/재부팅 최종. **API 제외 로컬 기능 진행률 약99%(추정)**, 실전 대장주 적중률/독립 PIT 인증 N/A. REWRITE 금지, CONTINUE 우선.

## 2026-10-12 최신 — 6_5 first native 암호화 원본 X509 만료·복구 비밀키 readiness (전체2073 PASS)

- Mac/T5DATA online, 시작 local/origin main 47d01c7에서 정상 6_5 암호화 original ZIP·cross-volume witness·DRY-RUN 코드 그대로 CONTINUE. src/eraleader/native_encrypted_vault.py **버그 수정**: X509 만료 이후에도 기존 최초 암호문 first cert SHA 일치/검증·AES-GCM 복구를 유지, 새 backup 최초 발행에는 유효기간 내 X509 필수. 신규 src/eraleader/native_recovery_readiness.py + CLI scripts/run_native_recovery_readiness.py와 기존 run_local_scheduled.py --native-recovery-readiness [--native-recovery-check-key ...] [--native-recovery-warn-days 90] opt-in. 기존 encrypted watch slot/vault/first witness/public cert 옵션 필수. 다른 디스크 AES-256-GCM 저장 첫 SHA 검증, 공개 인증서 실제 notBefore/notAfter·만료 임박 및 Git 밖 owner600 RSA 키에서 공개 SPKI만 대조. 키/path/issuer/raw ZIP 웹 반출0, 실제 decrypt/복구 drill0, API·전송·LaunchAgent/SSD 재부팅/물리연결0.
- 신규 **27/27 집중 PASS** + 전체 **2073/2073 pytest PASS EXIT0 (106 modules)**, handoff30ID/40files, 변경 compile/Git diffcheck PASS. Mac T5DATA vs /private/tmp 실제 서로 다른 st_dev에서 KR·US 합성 original AES-GCM SHA 2슬롯/올바른 owner600 private 공개키 매칭·만료임박·chmod644 위험·미설정 key 비확정, localhost HTTP200, 원본 fixture SHA 불변 E2E PASS. expired 합성 OpenSSL X509 과거 인증서의 새백업 거부/옛 SHA parse 허용 테스트. 정확히 7 code/test/docs 경로 공개 Git 보안 scanned7 suspicious0, **코드 GitHub main commit/push c7c9b78a306782568d48222ca12fd8048263e66d**, origin 동일 확인. 미커밋 src/eraleader/native_first_capture.py 7줄은 변경·stage·commit 제외 보존. 재현 docs/119 / PROJECT_STATE 맨 아래.
- **NEXT**: 사용자 명시적 Mac 키 escrow·오프사이트 암호문/first SHA 독립 보관·실제 periodic restore drill 기록/로그 안전 운영은 후속. 공식 KRX/DART/SEC PIT 및 미래 Top-K 자연 성숙 실제 outcome은 D-017 API 연동 최종+시간 필요. D-021 SSD 실제 탈착·재연결·재부팅 최종. **API 제외 기능 구현률 약99%(추정), 대장주 발굴 공식 인증/실전 정확도 N/A**. REWRITE 금지, CONTINUE 우선.

## 2026-10-12 최신 — 6_5 AES-GCM 최초 native ZIP 실제 복구 리허설·SHA 이력 검증 (전체 2093 PASS)

- Mac/T5DATA Online. 이전 코드 HEAD aad8141(key/cert readiness 병렬 코드 정상 반영)에서 `src/eraleader/native_recovery_drill.py`, `scripts/run_native_recovery_drill.py`, `tests/test_native_recovery_drill.py`, `docs/120_ENCRYPTED_NATIVE_RECOVERY_DRILL_SHA_HISTORY.md` **독립 신규 4파일**로 CONTINUE. 기존 정상 crypt/witness/readiness/scheduler/native WATCH/score/census API0·재작성0. 명시적 0600 owner private key와 SSD 밖 private0700 scratch 사용 시만, 기존 AES-GCM ciphertext→태그 인증 복호화→첫 WATCH/score/features/label/census 원장 재생 검증→임시복원경로 삭제→O_EXCL first event+SHA append history/report 웹(로컬 DRY-RUN). 삭제=secure erase/외부 timestamp 공증 주장 금지. 실패는 기록하고 CLI exit2; 원본/private 경로 웹·Git 반출0. 상시 scheduler/실운영 키 자동 설치0.
- 신규 **20/20 집중 PASS**, 전체 **2093/2093 pytest PASS EXIT0 (107 modules)**, handoff 30 ID/40 필수 PASS, Python compile/scoped Git safety staged4 suspicious0. Mac/T5DATA 서로 다른 실물 st_dev에서 합성 KR 실제 subprocess E2E: 원본 비암호화 ZIP 임시 숨김 후 성공3회, ciphertext 위조 실패1회(exit2), first WATCH+cohort 원장 replay/임시 scratch 제거/HTTP200 및 감사 SHA chain PASS, 실전 API·메시지0. 원본 합성 ZIP SHA 보존, 물리 SSD 탈착·재부팅0.
- 코드 commit/push **7e46fd460ec1a7ea2c050879c544b46254992813** origin/main/local SHA 동일. 기존 미커밋 `src/eraleader/native_first_capture.py` 7줄은 무변경·stage/commit 제외. 상세 `docs/120_ENCRYPTED_NATIVE_RECOVERY_DRILL_SHA_HISTORY.md` 및 PROJECT_STATE.md 최하단.
- NEXT: 주기적으로 복구 리허설이 필요한지 판단하는 만기 read-only 로컬 운영 정책, 키수명/rotation·offsite 관리자 정책 및 향후 공식 2_2/2_5 KRX/DART/SEC PIT 연동 준비. D-017 API 마지막, D-021 실물 SSD 재연결·재부팅 최종. **API 제외 개발률 약99%(로컬 기능 추정)**, 실전 미래 대장주 lead-days/precision 및 공인 PIT 인증 아직 N/A. CONTINUE, REWRITE 금지.

## 2026-10-12 최신 — 6_5 native recovery DRILL 만기 SHA 감시·DRY-RUN 웹 (2136 PASS)

- 시작 Mac/T5DATA online, main/origin **a8985a9** 기준 독립 `src/eraleader/native_recovery_due.py`, `scripts/run_native_recovery_due.py`, `tests/test_native_recovery_due.py`, `tests/test_scheduled_native_recovery_due.py`, `docs/121_NATIVE_RECOVERY_DRILL_DUE_WATCHDOG.md` 및 기존 `scripts/run_local_scheduled.py` opt-in 최소 연결로 CONTINUE. 기존 최초 native WATCH/score/census/PIT/암호화 원본 ZIP/첫 SHA 증거·실제 scheduler 정상코드 REWRITE0. 기존 별도 미커밋 `src/eraleader/native_first_capture.py` 7줄 수정은 이번 작업 stage/수정/commit하지 않고 보존.
- 기본 복구 리허설 주기 30일/사전경고7일(서버시간 UTC, 실증값 아닌 운영 가설)을 원래 `output/native_recovery_drills` 첫 O_EXCL SHA 체인 검증에 기반해 1~128 KR/US 모델 슬롯별 HEALTHY/DUE_SOON/OVERDUE/NEVER_TESTED/FAILED/INVALID_EVIDENCE/MISSING_SCAN_INPUT으로 기록. 별도 원장/genesis/first event/checkpoint SHA가 기존 PASS 이력 count+HEAD를 PIN하여 지난 성공 이력 소급삭제/묶음대체를 건강으로 취급하지 않음. 독립 CLI·선택 예약 `--native-recovery-due --native-recovery-due-scratch-root`를 기존 encrypted watch 4설정과 함께 연결. 키·복호화·메시지·API 호출0, 영구 LaunchAgent 설치0, stale 기본오류 유지. output/site/native_recovery_due.html 로컬 웹 연결.
- 집중 **43/43 PASS** (28 watcher+15 scheduler), 전체 **2136/2136 pytest PASS EXIT0, 109 modules**, handoff **30 ID/40필수** PASS, pycompile/Git Public stage scanner6 suspicious0. 실제 Mac T5DATA↔/private/tmp 합성 KR 외부 ZIP/witness/리허설·독립 CLI 첫 미실시1→연구용 과거시각 PASS로 OVERDUE1→중복0→실제 재실행 HEALTHY1→원래 원장 위조 INVALID→복구 HEALTHY; localhost HTTP200, 원본 ZIP SHA 불변, 운영용 키 설치0. 원격 GitHub 코드 main commit/push **94a0ee0e4a5afb68511f5400c6e8d1ca2a038f92**, local/remote SHA 동일. 자세한 `docs/121` 및 PROJECT_STATE.md 최신.
- **NEXT**: 6_5 사용자 지정 안정적 백업 저장소/실운영 리허설 주기 운영 준비(기본은 명시 opt-in, 임의 개인키 복호화 자동화 금지). 2_2/2_5 공인 KRX/DART/SEC PIT·share class/상폐·기업행동·first received 및 5_5 진짜 prospective future outcome은 D-017 API 최종/시간 경과 뒤. 실제 SSD 물리 탈착·재연결·재부팅 D-021 최종. **API 제외 로컬 기능 구현 약99%(추정, 공식 PIT/미래 대장주 실적 미인증)**. 정상코드 유지, CONTINUE/REWRITE 금지.

## 2026-10-12 최신 — 6_5 첫 native AES 암호문·Mac SHA witness 휴대용 cold custody / 외부 PIN 검증 (2164 PASS)

- 원격 Mac/T5DATA Online, 시작 main f8ab0262a4ad9bbd8643a68254eee440002c8ea7. 신규 src/eraleader/native_cold_custody.py, scripts/native_cold_custody.py, tests/test_native_cold_custody.py, docs/122_PORTABLE_ENCRYPTED_NATIVE_COLD_CUSTODY.md 4파일만 추가. 기존 raw original WATCH/score/Top-K/PIT/시장시세/MarketOS/CycleOS/첫 SHA/AES 원본 정상코드 재작성·수정 0, 예약 API·메시지0. 다른 세션 미커밋 src/eraleader/native_first_capture.py **7줄 원형 보존, staging/commit 제외**.
- 기존 첫 AES-GCM CMS(암호문)+first receipt/guard/lock + 별도 Mac SHA-only first witness/guard/lock + 원래 PUBLIC X509 cert만 고정 allowlist로 휴대용 ZIP_STORED에 묶어 다른 filesystem에 명시 export. 실제 평문 원본 ZIP/개인키/원시시세 복제0. 기본 보관은 원본 T5DATA SSD·기존 Mac vault/witness에서 **세 번째 stat.st_dev 다른 파일시스템 필수**(별도 물리/지역 offsite 인증 아님). 없으면 fail-closed, --allow-colocated-research-only 명시 플래그는 E2E 시험용으로만 허용·offsite attest false. archive package SHA-256을 외부 따로 보존해야만 verify/restore가 작동하며, 원래 local cold ZIP를 조작·재포장해도 최초 본문 검증 불변. restore는 새 encrypted vault/witness/public cert만 재구성, 실제 AES-GCM WATCH/score/census replay는 원래 개인키를 별도 명시할 때만 가능.
- 집중 신규 **28/28 PASS**, 전체 **2164/2164 pytest PASS(EXIT0), 110 modules**, handoff 30개 개발ID/40필수 PASS, Python py_compile/staged safety scanned4 suspicious0, cached diffcheck PASS. Mac 실제 T5DATA↔/private/tmp 다른 st_dev에서 KR+US synthetic first ZIP/witness/encrypted-only transport/package를 원래 Mac vault/witness 가린 상태에서 독립 CLI SHA 검증·새 경로 복원→테스트 키로 original WATCH/score/census full replay PASS. Mac 세 번째 FS가 없어서 실제 strict offsite export 거절 성공/연구용 co-located opt-in만 시험됨, 원본 ZIP SHA 불변/API·메시지0. docs/122, PROJECT_STATE.md 최신과 ignored output/verification_logs/native_cold_custody_mac_e2e_20261012.json 참고.
- 코드 main GitHub push **443ee4df5aa31f0e86a785cd5e2345a032061d80** local/origin 동일, 본 상태 문서는 별도 docs-only commit 이후 최신 SHA 참조. NEXT: 실제 사용자 제3 filesystem/보호된 외부 SHA PIN 위치를 지정해야만 operational cold custody 시험 가능(지금 자동 설치 없음), 키 escrow·외부 geographic offsite 검증/타임스탬프 독립 공증, 공식 2_2/2_5 KRX/DART/SEC PIT 및 5_5 미래 first-native Top-K outcome 성숙은 D-017 API/시간 경과 이후. D-021 실물 SSD 분리·재연결·재부팅 최종. **API 제외 로컬 진행률 약99% 추정**. CONTINUE/REWRITE 금지.

## 2026-10-12 최신 — 6_5 암호화 native cold 보관 ZIP 정기 무결성·독립 SHA 최초 PIN (2191 PASS)

- Remote Mac/T5DATA SSD Online; 시작 local/origin main aa58dd9. **CONTINUE** docs/113~122의 original first native ZIP/SHA witness/AES-GCM encrypted vault/portable cold custody 기본 작동 코드는 보존. 신규 src/eraleader/native_cold_integrity.py + 독립 scripts/run_native_cold_integrity.py enroll/scan/verify-history, 테스트 두 파일, docs/123 문서, 기존 scripts/run_local_scheduled.py 최소 명시 opt-in --native-cold-pin-root. 기존 별도 미커밋 **src/eraleader/native_first_capture.py 7줄(6추가1삭제) 스테이지·수정·커밋 없이 계속 보존**.
- 최초 신뢰 SHA256을 사용자가 제공해야 PIN root에 O_EXCL first/guard, SHA chain genesis/append history/checkpoint 기록. 정기 scan이 encrypted-only ZIP 전체 멤버·첫 SHA witness를 재검증해 변조/분실/시간경과/누락 경고 1회·반복0·복구 RESTORED 표시, local DRY-RUN 웹에 암호문/키/원본경로 노출0. strict 설정은 원본 SSD·PIN 저장소·cold ZIP 서로 필요한 다른 st_dev 요구. Mac에 제3장치 없어 실제 strict cold export는 차단됨; 연구용 Mac co-located 시험만 했고 offsite 인증 아님. 키복호화/운영 설치/API·주문·실전 발송/물리 SSD 재연결·재부팅0.
- 집중 신규 **27/27 PASS**, 전체 **2191/2191 pytest PASS EXIT0 (112 modules)**, 30 개발ID/40 필수 인계 PASS, pycompile/diffcheck, Public Git scanner scanned6 suspicious0. T5DATA+Mac 내부 실제 별도 st_dev에서 합성 original SHA 불변, 첫 PIN→정상/변조 경고1/중복0/복원1/독립 CLI/HTML HTTP200 전부 PASS. 코드 push main **afa74d083a313812156560d14c38226fe6b8078e** 로컬/원격 동일. 상세 docs/123 및 PROJECT_STATE.md 맨 아래.
- **NEXT**: 실제 제3 독립 filesystem/비공개 SHA PIN 위치 사용자 지정 전 운영 strict 설치 대기. D-017 공인 KRX/DART/SEC 실전 PIT 및 5_5 prospective 미래 Top-K 자연 만기 검증 마지막, D-021 물리 SSD 분리/재연결/재부팅 최종. **API 제외 로컬 구현 약99% 추정, 실전 발굴 성능/공인 PIT 인증 N/A**. 정상 코드 REWRITE 금지.

## 2026-10-12 최신 — 6_5 독립 PIN으로 cold ZIP → AES-GCM → 최초 native WATCH/score/census 실복구 (2215 PASS)

- 인수 시작 main 36a8646, Mac/T5DATA 원격 Online. 기존 first native ZIP+SHA witness/AES vault/cold ZIP/SHA PIN 코드 재작성0, 외부 API·실전 전송·launchd 자동 키 복구 설치/실물 SSD 재연결·재부팅0. 이전 별도 미커밋 src/eraleader/native_first_capture.py 7줄(6추가1삭제) 보존, stage·commit0.
- 신규 src/eraleader/native_cold_replay_drill.py, scripts/run_native_cold_replay_drill.py, tests/test_native_cold_replay_drill.py, docs/124: 원래 다른 장치 SHA PIN과 portable encrypted ZIP full SHA/Witness 인증 후 사용자가 **명시적 0600 key/0700 별도장치 scratch** 공급시에만 AES-256-GCM 복호화 및 실제 first WATCH/score/features/census replay. 실패/partial evidence/cleanup은 PASS 금지. 원래 SSD private ZIP+Mac AES vault/witness가 논리적으로 없는 상태에서도 합성 실제 Mac CLI 복원 성공; ZIP 위조시 실패(exit2), 복구 후 재성공, 원본 SHA 불변, 임시 plaintext 폴더 비움, localhost HTTP200. 복호화 자동 예약0, history 읽기는 키 없이 수행.
- 신규 집중 **24/24 PASS**, 최종 **2215/2215 pytest PASS EXIT0 (113 modules)**, handoff 30ID/40파일 PASS, compile/Git safety staged4 suspicious0. 코드 main push **37022d2f21be49bb051ab27d22a344f4e56f03d2** local/origin SHA 동일. 상세 docs/124 및 PROJECT_STATE.md 최신. Mac 제3 cold 저장장치 미존재로 실제 strict/offsite physical 검증은 아직 불가, 합성 research-only 두 filesystem만 시험. 향후 D-017 외부 API·공식 PIT/실전 prospective 성과 검증, D-021 SSD 실제 연결/부팅은 최종. **API 제외 개발 약99% 추정, 실제 주도주 예측/PIT 인증 N/A**. CONTINUE, NO REWRITE.

## 2026-10-12 후속 6_5 — 콜드 PIN 암호문+최초 native 실복구 이력 SHA 증거 통합 준비도 (집중29 PASS)

- SSD code 시작 main e3b527b, Remote Mac online. src/eraleader/native_cold_restore_gate.py, scripts/run_native_cold_restore_gate.py, tests/test_native_cold_restore_gate.py, tests/test_scheduled_native_cold_restore_gate.py, docs/125 신규 + 기존 scripts/run_local_scheduled.py의 opt-in 최소 연결. 원래 docs/122~124 ZIP/SHA PIN/AES-GCM first WATCH/score/census 원장 정상 코드는 REWRITE 0, 개인키 자동 접근/API/실전 메시지/실물 SSD 연결·재부팅0, 별도 미커밋 src/eraleader/native_first_capture.py **7줄 반드시 보존**.
- 전체 SHA PIN history/콜드 package deep verifier/각 KR+US native 슬롯의 마지막 실제 PASSED AES 복구 history를 묶어 NEVER_REPLAYED/FAILED/DUE_SOON/OVERDUE/UNTRUSTED SHA/역사 rollback/RESEARCH_ONLY_FRESH와 strict READY 분리. 최초 SHA 이력/보고서 및 로컬 DRY-RUN 대시보드, 예약 opt-in/원래 stale 차단 유지. 집중 신규 **18+11=29 PASS**, 합성 T5DATA↔Mac distinct st_dev E2E 검증/변조경고/복구 및 독립 CLI 이력·웹 HTTP200 PASS. py_compile/handoff 30ID/40files PASS. collect-only **2244 cases/115 modules**.
- **사용자 새 지시: 전체 회귀는 외부 API 연동 후 실행**. 진행중이던 전체 pytest는 약29%에서 종료 코드143으로 중단, 전체2244 PASS 주장 금지. 개발은 변경된 부분 테스트/실제 기능 구현 우선. API 제외 약99% 추정, 진짜 공인 PIT·실전 대장주 발굴 정확도 N/A. Docs/125 및 PROJECT_STATE 맨 아래, GitHub 최신 main을 인수 기준으로 삼을 것. D-017 API 최종/물리 SSD D-021 최종.

## 2026-10-12 최신 — 6_2·6_5 로컬 운영 상태·암호화 cold 실복구 SHA 이력 통합 화면 (변경 테스트 46 PASS)

- Mac/T5DATA 원격 Online, 시작 main fa2d5d5. 기존 운영 3모드/WATCH·census/AES-GCM/cold SHA PIN/예약 코드 REWRITE0. 새 `src/eraleader/operations_cold_bridge.py`, `scripts/render_local_cold_operations.py`, `tests/test_operations_cold_bridge.py`, `docs/126_LOCAL_OPERATIONS_COLD_RECOVERY_BRIDGE.md`만 구현. 원래 PIN root/별도 scratch 정책을 명시했을 때, 기존 운영 Overview+6_5 restore gate SHA 체인을 read-only 감사해 현재 `output/operations_cold/` 새 HTML/JSON 2건 생성, **기존 대시보드/첫 SHA/PRIVATE KEY/자동 배치 수정0**. 표시 상태는 최근 증거의 미검사·손상·실패/만기·RESEARCH_ONLY만 구별, 공식 PIT·미래 적중률·offsite·현재 AES 복호화 인증은 주장하지 않는다.
- 새 집중 **14/14 PASS**, 기존 운영 화면 영향 테스트 **32/32 PASS**, Mac T5DATA↔/private/tmp 실제 다른 st_dev 합성 AES original replay/cold gate 상태→새 CLI·HTML HTTP200 PASS, 원본 SHA 불변, API·메시지0. 보안 scanner staged4 suspicious0, handoff30ID/40files PASS. `PYTHONPATH=src python3 -m pytest tests` **전체 회귀는 API 이후로 명시 연기**, 이번 완료 근거로 사용하지 않음. 코드 main commit/push **9fe82f10ea24d2118e55fa0dfd11415fc6b00c7b** 원격 동일, 기존 미커밋 `src/eraleader/native_first_capture.py` 7줄 untouched/unstaged 보존.
- 다음: D-017 KRX/DART/SEC 실제 provider/API+first-received/PIT/issuer·shareclass/기업행동·상폐cash/전향적 Top-K 성숙 증거 및 D-021 실제 SSD 재연결·재부팅(모두 최종)와 진짜 별도 제3 storage/offsite 수동 지정. **API 제외 로컬 기능 구현 추정99%, 공식 실전 발견/PIT 인증 N/A**. 다음 채팅은 Git main/PROJECT_STATE 최신 확인 후 CONTINUE, 정상 코드 재작성 금지.

## 2026-10-12 최신 — 2_2/2_5 declared KR/US 두 공급자 최초 PIT 수입 원자화 (194 scoped PASS)

- **새로운 실제 기능**: `src/eraleader/provider_pair_atomic_onboard.py` + `scripts/onboard_provider_pair.py`, 신규 집중 tests, docs/127. 기존 provider staged 원본/정규화/첫 SHA witness/SQLite first receipt/두 출처 의미 충돌 검증 코드를 그대로 재사용해 한쪽 B가 실패해도 A만 부분 publish하지 않는 0700 private scratch → 단일 최종 디렉터리 원자 발행. 원본 SHA 변경, claimed publisher 중복, 시장 혼합, 수집/첫등록 시간, 상장/기업행동·분할·재무·산업 모순, 신규경로·권한 위험 등 fail closed. PIT/공식 공급자 독립 공증·실전 leader 승격0.
- **신규 23/23 PASS**, 기존 직접영향 포함 **194/194 PASS (6 test modules)**, py_compile/handoff30ID/40files/Public staged4 suspicious0, 합성 KR/US Mac Python CLI. **전체 회귀 API 연결 후**(이번엔 미실행). 코드 Git commit `4a0a789d92c6eaa0e5cbdaaad8965bd54afa9c88`; 다음 docs-only commit 후 최신 origin/main 참조. 기존 미커밋 `src/eraleader/native_first_capture.py` 7줄 그대로 unstaged. API/실전 전송·SSD 물리 재연결0.
- **NEXT** D-017 KRX/DART/SEC 진짜 공식 raw first-received clock·역사 상장/상폐 issuer/share-class/cash/action PIT 자료, 5_5 미래 Top-K 자연 성과 확인, D-021 물리 SSD/재부팅 최종. **API 제외 진행률 약99%(추정), 실제 대장주/공인 PIT 인증 N/A**. 기존 코드 NO REWRITE / CONTINUE.

## 2026-10-12 최신 — 2_2/2_5 두 공급자 최초 first-pair SHA PIN·as-of 원본 재감사 (217 scoped PASS)

- Remote Mac/T5DATA Online, 시작 local/origin main 443b745. 기존 provider staged/first original SHA+normalized PIN/SQLite/두 출처 PIT 의미대조/first native WATCH 정상 코드 보존. 기존 별도 미커밋 `src/eraleader/native_first_capture.py` 7줄(6추가1삭제) **수정/스테이지/커밋 금지, 지금도 unstaged 보존**.
- `src/eraleader/provider_pair_atomic_onboard.py`에 최초 원자 발행 직전 mode0600 O_EXCL `first_pair_receipt.json` 기록, 별도로 보존할 `first_pair_receipt_sha256` 출력. 신규 `src/eraleader/provider_pair_asof_seal.py` + `scripts/audit_provider_pair_asof.py`, `tests/test_provider_pair_asof_seal.py`, `docs/128_FIRST_PINNED_PROVIDER_PAIR_ASOF_REAUDIT.md`, 기존 atomic onboard 테스트 최소 수정. 정확히 6파일 코드 릴리스. 독립 첫 SHA 공급 필수, 원래 source A/B raw stream/manifest SHA, normalized A/B, SQLite first receipt/doc SHA, 최초 의미적 4영역 count와 당시/현재 as-of membership·분할/배당·기초실적·산업·상폐 타이밍 불일치 read-only 차단. 최초 수입 이전 소급 asof는 RESEARCH BLOCK, 정상 결과도 local WATCH 연구만 가능. API/실거래/알림/공식 PIT 승격0.
- 신규+기존 집중 **46/46 PASS**, 변경 영향범위 7모듈 **217/217 PASS EXIT0**, handoff30ID/40files, py_compile/Public Git safety6 suspicious0. Mac 실제 T5DATA 원시 합성 staged source와 Mac /private/tmp 서로 다른 st_dev에서 first pair 원자 발행→CLI asof 성공→raw 원본 변조 exit2→원상 복원 exit0, 원본 SHA 불변/민감경로 비노출/API0. 코드 commit `9b5e6267650570a0bfeeaf2123d1385029c3a88f`; 최종 main SHA는 docs-only checkpoint 이후 Git HEAD 확인. **전체 pytest 회귀는 사용자 결정대로 D-017 외부 API 연결 후**. NEXT 실제 KRX/DART/SEC PIT 공인 원문/법적 class·상폐 cash/발행+수신시각과 5_5 실제 전향 Top-K 성숙, D-021 SSD 재연결/재부팅 최종. **API 제외 개발 약99%(추정), 실제 대장주 성능/N/A**. CONTINUE, NO REWRITE.

## 2026-10-12 최신 — 2_2·2_5 최초 atomic A/B PIT PIN → 4_2·5_5 WATCH 게이트 연결 (128 영향 테스트 PASS)

- 기준 Mac/T5DATA online, 시작 main `5a2b979`. 신규 `provider_pair_candidate_bridge.py`, 기존 `cli.py`에 `offline-integrated --provider-atomic-pair-root --provider-first-pair-sha256` opt-in, 신규 테스트 `test_provider_pair_candidate_bridge.py`, 문서 `docs/129_ATOMIC_PAIR_PINNED_PROSPECTIVE_WATCH_BRIDGE.md`. 최초 SHA 독립 보관 필수, 원래 두 provider raw/normalized/first-receipt/as-of 전체 PIT 연구 대조 통과 시에만 기존 candidate 게이트로 전달. 실행 직전 두 번째 원본 불변 검사/출력경로 분리, SHA 오류·소급 as-of·A/B 혼합·변조 시 first WATCH 작성 전 차단. 기존 normal/manual watch 유지; 투자 인증0.
- 실제 Mac synthetic KR+US 및 변경 영향 6모듈 **128 PASS EXIT0**, handoff30ID/40files PASS, py_compile/Git diffcheck/Public staged 보안 scanner 4파일 suspicious0. 전체 회귀는 사용자 요청대로 공식 API 연결 후. GitHub main code commit/push `864379d496b7697ecd953d4941ed4f44314300f7` 원격 SHA 일치, 이 인계 docs-only commit 후 최신 HEAD 확인. 미커밋 `src/eraleader/native_first_capture.py` **7줄 그대로 보존, 변경·스테이지·커밋 제외**.
- **NEXT**: 기존 감시 중복 없이 first A/B 공급자 새 자료의 원본 정정·후행 빈티지와 후보 약화/교체의 증거 이력을 전향적으로 연결하거나 D-017 최종 외부 KRX/DART/SEC 공인 PIT/issuer/class/상폐cash·공시 첫발행/수신, 5_5 실제 미래 Top-K 1~12개월 성과를 준비. API 0/실전 알림 0/SSD 물리 재연결·재부팅0(최종 D-021). **API 제외 로컬 구현 약99% 추정**, 실전 대장주 발굴/PIT 인증 N/A. 코드 REWRITE 금지.

## 2026-10-12 최신 — 2_2·2_5 → 4_4·4_5·5_5 최초 SHA 봉인된 A/B 공급자 빈티지↔실제 WATCH 약화·교체 연결 (169 PASS)

- 시작 local/origin `2c6d57d`; Remote Mac/T5DATA Online. 신규 `src/eraleader/provider_pair_vintage_watch.py`, `scripts/audit_pair_vintage_watch.py`, `tests/test_provider_pair_vintage_watch.py`, `docs/130_PINNED_PAIR_VINTAGE_PROSPECTIVE_WATCH_CORRELATION.md` 정확히4파일 추가. 이전/새로운 atomic A/B 원본 SHA·개별 PIT asof·불변 연구 run_id·prospective 원장의 최초 등록시각/관찰 내용/payload SHA/스크린 결과를 read-only 교차검증. 새 first-ingest 뒤에 재실행한 과거 first WATCH는 조기성과에서 배제; 가짜 negative/상장종료·업종 재분류·회계/분할 correction을 WATCH 약화로 만들지 않음. 이전 양성→새 명시 음성·반대 방향은 1회 연구 관찰로만 기록하고 기존 2+2 업종 교체 가설 재사용, 공식 진짜 대장주 승격0.
- **KR/US synthetic Mac e2e 및 영향권 8모듈 169/169 PASS EXIT0**, 집중 신규 17 PASS, Python compile/인계30ID·40파일/PUBLIC staged4 suspicious0 PASS. 전체 회귀는 D-017 API 연결 후 의도적으로 미실행. GitHub `main` 코드 commit/push `070dcbd0a84f4a9c373fe005937a6bd1d7ab7684` SHA 원격 일치; 인계 docs-only commit 후 실제 최신 SHA 확인. `src/eraleader/native_first_capture.py` 기존 별도 **미커밋 수정 7줄(6+,1-) 절대 수정·스테이징·커밋하지 않고 계속 보존**.
- **NEXT**: 필요한 경우 새로운 A/B 공급자 3회 이상 consecutive vintage 및 WATCH/rotation의 prospective 이력·SHA DRY-RUN 운영 보고 연결(기존 감사·알림 중복 구현 금지). KRX/DART/SEC 독립 공인 PIT와 최초 공개/수신시각·상장/상폐 issuer/class·cash/actions·미래 Top-K 1~12개월 실제 성과는 D-017 외부 API/시간 경과 후. SSD 물리 재연결/맥북 재부팅 D-021 최종. **API 제외 로컬 개발률 약99% 추정; 실전 발굴 성능/PIT 인증 N/A**. 실제 테스트/코드 기준 CONTINUE, NO REWRITE.

## 2026-10-12 최신 API 연동 우선 전환 — KRX/DART/SEC 실제 HTTPS 최초 원문 수집 어댑터 (140 scoped PASS)

- 사용자 **D-022**로 D-017 API 연결 연기 철회: 지금 공식 KRX/DART/SEC 첫 원문 수집/실전 PIT 입력 경로를 개발. Mac/T5DATA online, 시작 main `179b0e7`. 새 `src/eraleader/official_api_capture.py`, `scripts/capture_official_api.py`, `tests/test_official_api_capture.py`, `docs/131_OFFICIAL_KRX_DART_SEC_LIVE_API_FIRST_CAPTURE.md` 4파일만 코드 릴리스, 기존 WATCH/native/PIT/SSDs 정상 코드 재작성0. 비밀키는 EraLeader `.secrets/official_api.env` owner-only 또는 OS 환경변수에서만 읽고 공개 GitHub 업로드 금지. 비공개 raw bytes/로컬 최초 수신시각/첫 SHA 보관, 직접 자동 WATCH 승격0.
- **실측**: 실제 Mac에서 KRX `data-dbg.krx.co.kr`, DART `opendart.fss.or.kr`, SEC `data.sec.gov` TLS handshake 성공(각각 TLS 1.3/1.2/1.3). 그러나 키·실연락처 User-Agent가 EraLeader 로컬에 미등록되어 `--check-config` 세 기관 모두 준비 FALSE; **실제 인증 API 수신 0건**. 테스트 29 신규+기존 111 = **140/140 scoped PASS**, Py compile/handoff30ID·40필수/Public scanner 4파일 suspicious0 PASS. 전체 회귀는 실제 API 성공·PIT 실제 자료 연결 뒤. 코드 push `d2961b645f8cf6ecb76d5a9229194f4c3bc53318` remote main SHA 동일, docs-only 인계 후 최신 HEAD 확인. 별도 미커밋 `src/eraleader/native_first_capture.py` 7줄(6+/1-) 건드리지 않고 unstaged 보존.
- **NEXT 첫 필수 작업**: 사용자 Mac의 `.secrets/official_api.env` 0600에 실 KRX `ERALEADER_KRX_AUTH_KEY`, DART `ERALEADER_DART_API_KEY` 및 SEC 실제 연락 가능 이메일 포함 `ERALEADER_SEC_USER_AGENT` 중 준비된 것을 입력 (키는 채팅/ GitHub에 보내지 않음). 이후 1회 최소 규모 인증 공식 데이터 수신→원문·SHA 검증→official PIT/법인코드·주권클래스·공개/최초 수신 시각 정합성 → 기존 데이터·WATCH 검증→전체 회귀. SSD 물리 재연결/재부팅 D-021 최종. **API 실전 인증 수신 0/3**, 발굴능력 실제 검증 N/A. 먼저 `PROJECT_STATE.md` 마지막 기록·현재 Git/실제 credential presence(값 출력 금지) 후 CONTINUE.


## 2026-10-12 API 실제 수신 2차 검증 — KRX HTTP 401 / DART 100건
- API 세 설정 Mac 내부 0600 파일에 보관·기밀 유지. DART 공식 API 2026-10-08 응답 100건 첫 페이지만 성공. KRX KOSPI/KOSDAQ 실제 요청 HTTP401로 미완료; KRX 사이트에서 API별 관리자 활용 승인/키 유효성 확인 후 다시 호출. SEC submissions 1001/Apple companyfacts 2 taxonomy 실수신 확인. 공식 PIT/전체시장 성과 인증 아님.

## 2026-10-12 이후 최신 — KRX 공식 API 활용승인·생산 HTTPS 첫 수신 검증 완료

- 맥 Chrome Apple Events 접근 성공, 사용자 로그인된 KRX `API 인증키 발급내역`의 2026-09-08~2027-09-07 키와 Mac 내부 보호된 키가 **일치** 확인(키 문자열을 채팅/콘솔/로그에 미출력). `API 이용현황`에서 코스피·코스닥 일별매매정보 **둘 다 승인**, 이용기간 **2026-10-12~2026-11-11**. 초기 401 해소.
- 실제 KRX 생산 API **2026-10-08 코스피 942행·코스닥 1,823행** HTTPS 200; `output/official_api_capture/first_*` 원문·첫 SHA 영수증 캡처 후 파일 재해시 PASS. DART/SEC도 단일 실수신 완료. 회사/주권/상폐의 공인 역사적 PIT 인증이나 투자 실적 검증은 여전히 N/A. 다음: 정식 공급자별 원문 수집 지속성과 고유 issuer/share class, 정정·상폐·공시 발표시각 mapping, 단계별 API E2E 및 최종 전체 회귀. KRX 이용 종료 11/11 갱신 필요. SSD 분리·재부팅 D-021 최종.
- 기존 별도 `native_first_capture.py` **미커밋 6+/1-** untouched. Chrome 자동화 허용 설정은 사용자가 수동으로 켠 상태이며 작업 후 직접 해제 가능.

## 2026-10-12 KST 최신 API 실연결 체크포인트
- Chrome 로그인 세션에서 KRX 공식 서비스 신청 상태 최종 확인: 코스피/코스닥 2026-10-12~2026-11-11 모두 **승인**. 브라우저 계정 인증키와 Mac owner-only 0600 보관 키 일치(원문 노출 0). 실제 KRX 2026-10-08 KOSPI 942행/KOSDAQ 1823행 production HTTPS 200, raw/first receipt 양 시장별 SHA 재해시 PASS. 기존 SEC/ DART 실제 HTTP 첫 수신도 성공. 아직 PIT/주권 class/상폐 정산/실제 미래 대장주 검증 아님.
- SEC/KRX/DART 보호 로컬 API 입력 UI(브라우저·Mac 내부 파일) 코드 commit/push `eaaada8ca173257c2b083fe316e148f7e3dd554b`; 변경 관련 49 tests PASS, 보안 staged5 suspicious0, full API-integrated 회귀는 자료 연결 후 실행. KRX 사용기한 11/11 갱신 필요, 사용자 직접 켠 Chrome JavaScript from Apple Events 권한은 작업 후 수동 비활성화 권장. `src/eraleader/native_first_capture.py` 별도 미커밋 7줄 untouched. 다음 개발은 새 모듈 무분별 추가 대신 실제 공식 원시/API→PIT 정규화→WATCH/웹·보고서 최소 결선. 본 상태 문서는 docs-only followup SHA 참조.

## 2026-10-12 최종 최신 — KRX/DART/SEC 실수신 SHA → 기존 가격 WATCH/HTML/일·주·월 리포트
- **Git 코드 commit/push** `cd10e184a5cb39a149be241b69ca0e1d4bc9c6c8`, 이후 인수 docs-only 최신 main은 `PROJECT_STATE.md`/Git 실제 최하단 확인. `docs/133_OFFICIAL_API_PIT_WATCH_INTEGRATION.md`, `src/eraleader/official_api_pit_bridge.py`, `scripts/run_official_api_pit.py`부터 이어서 개발. 실제 KRX 2026-10-08 코스피942+코스닥1823=2765행을 기존 가격 연구 score → WATCH20건/SQLite event 등록일 2026-10-12 → 로컬 HTML/3종 보고서 및 DRY-RUN 경고까지 통합해 실행. DART 첫 페이지100건 불완전·SEC 단일 CIK/재무 topology만 출처 증거, 공식 PIT/leader promotion0. 전체 `pytest` 2403/2403 progress dots 100% (단 래퍼의 zsh 예약 status 변수 오류로 outer exit1, pytest 자체 exit 숫자 별도 캡처 못함), 별도 집중 46 PASS. 세부 증거 PROJECT_STATE 하단.
- **반드시 보존** `src/eraleader/native_first_capture.py` 별도 미커밋 7줄(6+,1-) 수정/스테이징/커밋하지 말 것. 다음은 KRX/DART issuer/class 및 최초 공시 이용시각·기업행동/상폐 PIT 정합성, DART pagination, SEC CIK/share-class, 미국 실거래 가격시장 전체자료, 5_5 실제 prospective 1~12개월 만기. SSD 물리 분리·재부팅 마지막. API 제외 약99% 추정, **전체 기술구현 추정 약95%**(실전 예측력 인증 미완료).

## 2026-10-12 최신 CONTINUE — 공식 API 사전 운영 결선 (코드 `0ce3aad`)
- 기존 staged 20개 공식 KRX+DART 전체 페이지/corpCode/fnlttSinglAcntAll/SEC 재무 as-of/1회 일별 연구 WATCH 통합 코드·테스트·문서 완성. 구체 구현·실데이터 수신 근거 `docs/134_OFFICIAL_DART_SEC_PREOPERATIONS.md`, 최신 `PROJECT_STATE.md` 말미. 미완성 사이트 게시를 막는 원자 rename + 실패 주입 2건 추가. 한국 2026-10-08 2,765 KRX 행·992 DART 공시·현재 기업코드 2,651 단일매칭/114 미연결(인증된 역사적 PIT 아님), WATCH 20/보고서 3/DRY-RUN 20/실전발송0.
- 이번 공식 모듈 영향 테스트 91 PASS, 원자 게시 영향 테스트 41 PASS(exit0), Public 보안검사 20파일 suspicious0. 전체 suite의 **완료/실패 여부는 최신 로그/PROJECT_STATE.md 갱신을 확인**(현재 문서만으로 PASS 간주 금지). `native_first_capture.py` unstaged 6+/1- 보존 필수. API 제외 추정99%, 통합 기능 추정95%, 역사 PIT·미래 성과는 아직 미인증. 다음은 매일 원시 증분·한미 전 종목 법인/주권·상폐/기업행동 PIT와 데이터 공급원 확장, 보수적 NO-LEADER 유지.

## 2026-10-12 최신 전체 pytest 확정
- 20파일 공식 KRX+DART 전체/법인코드/재무·SEC PIT 연구/실패시 원자 게시의 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **2,450 PASS, 프로세스 EXIT=0, 마지막 100%**, 로그 `output/verification_logs/official_preoperations_full_20261012.txt`; 해당 전체 회귀는 실제 미래 선행 적중률/PIT 공식인증/20거래일 모의운용을 대체하지 못함. GitHub 최종 main/로컬 SHA 확인 후 CONTINUE; 네이티브 capture 미커밋 7줄 보존.

## 2026-10-13 2_2·3_1·6_2 최신 개발 worktree — 원본 유지, 실제 Factor Coverage 신규

- **별도 개발 workspace:** `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013` · `feature/core-official-factor-coverage-20261013`, 부모 `main/a244002`. 먼저 `PROJECT_STATE.md` 마지막 기록 및 `docs/135_OFFICIAL_FACTOR_COVERAGE_AND_CFS_SIDECAR.md`를 읽고 CONTINUE.
- 변경 핵심: 공식 DART CFS 두 연도 현재기업 연구실적을 **가격 TOP20 밖**에서도 `official_financial_research_observations`와 새 `site/factor_readiness_kr.html`로 노출, 5요소 자료 충족도/결측을 보여준다. 투자 1~20위와 100점 모델 결선은 아직 미완료(정식 순위 **N/A**). 공식 KRX 실제2,765/현재 DART2,651/연속 CFS1(005930 FY 매출 YoY +10.88%, 가격 TOP20 제외) 실제 raw SHA 재검증. 새 8766 UI 로컬 PASS.
- 자동회귀 관련 9모듈 129/129 PASS(EXIT0), 실제 공식 첫 receipt read-only E2E 2회 PASS. 추후 KRX-DART 공시 최초 공개·3개 연속 사업연도 성장가속/기관 수급·산업 데이터+법적 클래스 PIT 검증부터 이어서 구현.
- 원본 main `src/eraleader/native_first_capture.py` 미커밋 6+1 유지 SHA `6d3139f0...`. 이번 확인에서 이전 `/Volumes/T5DATA/EraLeader_통합관리` 폴더 **부재** 및 이전 5개 worktree `prunable`; 지우거나 `git worktree prune`하지 말 것. B00 암호화 백업·이전 다른 기능 브랜치 소스는 별도 보호.
- 완성 추정 95/99%는 전체 실사용 완료율로 **철회**. 기능별 독립 인증 결과로 개발 상태를 표현한다. 이후 GitHub branch SHA는 `PROJECT_STATE.md` 및 git log/latest origin에서 확인.

## 2026-10-13 최신 핵심 개발 — 공식 3개 사업연도 연결실적 가속/별도 화면

- 최신 개별 브랜치 `feature/core-official-factor-coverage-20261013`, 작업 경로 `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013`. 원래 main과 보호 미커밋 파일 변동 금지. `PROJECT_STATE.md` 마지막 및 `docs/136_OFFICIAL_DART_THREE_YEAR_GROWTH_ACCELERATION.md` 참조.
- 가격관찰 TOP20와 별도 DART FY2023·2024·2025 공식 첫 SHA CFS 실적 연구: 005930 실제 YoY 2024 +16.1953%, 2025 +10.8801%, 가속 -5.3152pp; 최초 수신/결정시각 후 이용, 과거 예측 성과 N/A. 기존 WATCH/3종 보고/DRY-RUN/가격순위 보존. 실제 CLI 원본 재생 1회 E2E PASS, `http://127.0.0.1:8768/factor_readiness_kr.html` 로컬 화면. 관련 테스트 10모듈 **153 PASS EXIT0**.
- 현재 여전히 전체 산업·경쟁력·기관외국인 수급 공식 데이터, DART 최초공개·정정 vintage/PIT 기업클래스·상폐·기업행동, 미국 전체시장 가격 및 종합100점/전향적 적중률은 미완료. 99%/95% 실전 완료율 표현 철회. ER-NC 뉴스 확장 브랜치 작업트리 경로 `prunable` 표시되므로 임의 prune/삭제/강제 복구 금지.
- 다음 1개 기능: DART 최초공개·정정 시계열 진본성 및 영구 기업/주권 PIT 증거부터 보강해 실제 공통 5요소 후보 평가를 연결. 본 소스 브랜치의 Git 최종 SHA는 `git rev-parse HEAD`·GitHub 원격 확인.

## 2026-10-13 최신 개발: DART FY CFS 최초 인지·정정 빈티지 registry 및 실제 대시보드

- 별도 Git worktree `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013`, branch `feature/core-official-factor-coverage-20261013`; `PROJECT_STATE.md` 최신 137 체크포인트 + `docs/137_DART_CFS_VINTAGE_REGISTRY_AND_DASHBOARD.md`부터 CONTINUE.
- `official_dart_vintage_registry.py`은 기존 원본 SHA 확인 DART FY CFS를 Mac 내부(owner-only) 전향적 SQLite 장부에 첫 수신/등록 두 시각으로 append-only 등록, 같은 FY 신규 접수번호·동일 접수번호 재무 변경 차단. 원래 2023/24/25 CFS를 실제 새 3건 등록해서 역사 거래일 2026-10-08 as-of [0,0,0], 실제 등록 후 [1,1,1], correction trigger/chain 검증. 실제 화면 `http://127.0.0.1:8769/dart_cfs_vintages.html` HTTP200.
- `scripts/run_dart_cfs_vintage.py` register/as-of/checksum, `scripts/run_official_api_pit.py --vintage-ledger /abs/mac_local.sqlite` **명시적 옵션**으로 KRX2765/DART992/CFS3 1개 기업/첫 등록 원본 3개와 가격 WATCH20/별도 자료 충족도 화면 연결. **누락·정정 충돌 시 화면/SQLite 발행 전 실패**. 공식 공시 최초공개시각/전체 정정·issuer-class PIT/공식 대장주·종합100점/실전매매는 N/A.
- 영향 범위 **13개 테스트 모듈, 178/178 pytest PASS EXIT0**, 합성 신규25건, Mac 공식 영수증 E2E PASS. 전체 수천 테스트는 ER-NC-10 최종 수락 전 계획, 지금 PASS로 주장하지 않음.
- 실제 Mac 내부 DB `~/Library/Application Support/EraLeader/research-ledgers/dart_cfs_vintage_forward_20261013.sqlite`는 외장 SSD의 새 SQLite 파일 첫 INSERT가 읽기전용 오류를 보인 까닭에 분리. **본 신규 DB의 독립 암호화 오프라인 복제/복원은 아직 미완료** — 다음 작업 1순위. 외장 SSD 시험 DB와 삭제된 듯 보이는 이전 관리 worktree를 절대 임의 제거하지 말 것. 원본 main 미커밋 `native_first_capture.py` 보존 SHA `6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6`.
- 기존 전체 95%/99% 완료율 주관값은 철회. 한정된 회사/날짜의 공식 최초수신 연구 진척과 전국/미국 전향적 대장주 예측 검증을 별개로 보고. Git 최종 SHA는 `git rev-parse HEAD`과 원격 브랜치로 확인.

## 2026-10-13 신규 6_5 후속 결선 — Mac CFS 최초수신 이력 독립 암호화 백업 및 복원

- 현재 개발 worktree `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013`, branch `feature/core-official-factor-coverage-20261013`. 먼저 `PROJECT_STATE.md` 최신 마지막 체크포인트 및 `docs/138_DART_CFS_VINTAGE_ENCRYPTED_DISASTER_RECOVERY.md`를 읽고 CONTINUE.
- 새 `dart_cfs_vintage_backup.py` + `scripts/run_dart_cfs_backup.py`(init-keys/backup/verify/restore-test). 기존 Mac 유저 SQLite FY2023~25 삼성전자 DART 실적 원본 first registered 이벤트3의 일관된 온라인 DB 스냅샷을 기존 native OpenSSL AES256-GCM/RSA-OAEP로 암호화, `T5DATA/EraLeader_Recovery_Backups/VintageCFS/cfs_20261013T051710Z_fe24a7df3513` 및 Mac `~/Library/Application Support/EraLeader/ProtectedBackups/VintageCFS/` 동일 슬롯 **물리 장치별 2개** 보관, 소유자 제한·SHA + X509 고정/덮어쓰기 금지.
- **실제 isolated decrypt restore-test PASS**: SQLite integrity, 이벤트3/chain SHA, 각 첫 등록 이전0/이후1 as-of 확인, 평문 복원파일 남김0. 키는 Mac `~/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/`에 RSA3072 owner0600, **Mac 분실 대비 키의 독립 암호화 에스크로/오프라인 복구는 미완료**. AES ciphertext 두개가 있어도 개인키 없으면 복구 불가! 키 원문/경로/암호문을 Public Git에 절대 복사하지 말 것.
- 신규 9개 포함 DART/KRX/SEC 관련 **14모듈/187 pytest PASS(EXIT0)**, 전체 2450+ 재실행은 이번엔 하지 않음. 추가 코드/상태 SHA는 `git rev-parse HEAD`와 GitHub origin에서 확인.
- **다음 개발**: 키 독립 보관 승인·암호화 복구 시험, 공식 DART 최초 공시 공개시간/전체 정정 원본·영구 issuer/share-class 상폐 기업행동 PIT와 산업·외국인 기관수급 데이터 공통 시점 확대. 전향적 미래 대장주 성능/종합100점 N/A, 과거 99% 전체 진행률 추정은 폐기.

## 2026-10-13 6_5 다음 체크포인트 — 외부 복구 개인키 공개키 에스크로 구현됨, 실제 OFFLINE 키 수탁 대기

- 최신 core worktree `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013` → `START_HERE_NEXT_CHAT.md→AGENTS.md→PROJECT_STATE.md(맨 아래)→DECISIONS.md→docs/139_DART_CFS_EXTERNAL_OFFLINE_KEY_ESCROW.md` 확인. 기존 main/미커밋/기본 CFS DB 원본 절대 재작성 금지.
- `dart_cfs_external_key_escrow.py`, `scripts/run_dart_cfs_external_escrow.py`: **별개의 오프라인 수탁자 RSA 공개 인증서**로 기존 Mac CFS 복구 개인키 AES-256-GCM/RSA-OAEP 암호문 외장 저장, SHA 봉인, 외부키로 두 단계 CFS SQLite 독립 restore-test 계약. 코드+합성 외부키 실제 암호학 복원, 신규 11 테스트 포함 관련 15모듈 **198/198 pytest PASS EXIT0**. 인증서가 미설정이므로 실물 외부 offline 복구키 수탁/패키지 발행/실제 키 복원은 **미완료**. 외부 개인키를 이 Mac에서 임의 생성해 완료 선언하지 말 것.
- 다음 개발 타깃: 사용자가 별도 오프라인 장치에서 생성/보관한 private escrow key와 공개 인증서를 확보하면 **공개 cert만** Mac에 넣어 실제 SHA 암호화 escrow 발행/감사/독립 DR drill. 지금은 전국/미국 주권 클래스/상폐/공시 공개시각·정정 PIT+산업/수급 실데이터 확대를 우선. CFS 백업 슬롯 `cfs_20261013T051710Z_fe24a7df3513` 및 original Mac DB는 이전 restore-test verified 상태로 보존. 전체 95/99% 진행률 추정은 폐기.

## 2026-10-13 전체 진행률 최신 기준: 38% (실사용 인수 45/120)

- 2026-10-13 요청에 따라 **전체 인수 진척률 37.5%(표시 38%)**를 `docs/140_Eraleader_OVERALL_ACCEPTANCE_PROGRESS_20261013.md`와 실제 로컬 웹 화면 `http://127.0.0.1:8769/development_progress_20261013.html`에 반영. 1~6단계 각각 **35% / 50% / 35% / 30% / 25% / 50%**.
- 30개 개발 ID×4개 순차 인수 관문(테스트 증거→실제 일부 E2E→요구 전체 PIT 통합→연속 안정 운영) 정량 체크는 `src/eraleader/development_progress.py`. 전체 99% 또는 95%라고 말한 과거 코딩 추정은 **전면 철회**. 본 38%는 수동 보수 인수 판정/진척 척도일 뿐 실제 개발 시간 비율·전향 투자 적중률 아님.
- 신규 상태 생성 `scripts/publish_development_progress.py`, 신규 단위테스트 `tests/test_development_progress.py` 8개, 관련 API 대시보드 2모듈 포함 총 **64/64 PASS EXIT0**. 공식 대장주 종합순위·뉴스 기능 코어/main 병합, 20거래일 실운영·미국 전체·공시 수정시각 등은 계속 N/A.
- 다음 작업은 늘어나는 코드 모듈수보다 실제 통합과 미래 대장주 발견의 인증 게이트 위주로 진행. 원본 main `native_first_capture.py` 미커밋 SHA `6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6` 그대로 보존. 최신 SHA는 `git rev-parse HEAD`·GitHub 원격 확인.

## 2026-10-13 BASIC-FIRST 개발 우선순위 전환 — 다수 기업 가격·실적 실제 후보 관찰

- 최신 코드 `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013`, `feature/core-official-factor-coverage-20261013`에서 CONTINUE. 앞선 백업·복구 외부키 기능 확장보다 사용자 명시 지시에 따라 **대장주를 찾는 본기능(1_2·3_3·3_4·3_5·4_1·6_2)** 먼저.
- KRX/DART 실제 원문 PIN으로 서로 다른 산업 실제 **10종목** FY2024/25 CFS **20본**(기존 삼성전자2재사용+새 DART18 수집); 마감 가격 2026-10-08 KRX 관측2765+공시992/첫수신2026-10-13. `scripts/capture_dart_multi_company.py`, `official_dart_multi_company.py`의 제한 배치, `--only-existing` 재사용 및 중복 FY 수정 원본 차단.
- `official_api_pit_bridge.build_official_price_snapshot(...basic_candidate_screen=True)` opt-in 가격 전체 관찰+실적10개 근거 별도 추출, `official_basic_candidates.py`/ `scripts/publish_basic_company_screen.py`으로 기본 후보 연구표 사이트 `http://127.0.0.1:8770/basic_candidates_kr.html` HTTP200. **10개 모두 가격·실적 계산 가능**, 3방향(3개월 가격+매출+영업익) +일치 **0개**; 이를 숨기지 말고 표시. 연구용 비교순서만 제공/공인 100점·매수순위/추가 PIT·전향적 적중률 **N/A**. 기존 가격 TOP20 WATCH/일주월 보고/모든 API 원본 그대로.
- 직접 영향범위 7개 모듈 **96/96 pytest PASS EXIT0**, 합성 신규 collector/candidate 및 기존 공식/API 브리지 opt-in 회귀 E2E; 실제 KRX+DART first PIN 다시 verify 후 새로운 result `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013`에만 게시. 상세 `docs/141_KR_OFFICIAL_MULTI_COMPANY_BASIC_CANDIDATES.md`와 PROJECT_STATE 최하단 확인. 원본 main 미커밋 `native_first_capture.py` SHA `6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6` 건드리지 말 것.
- 다음 실제 본기능: 공식 산업 성장·기관외국인 수급·동일 산업 peer 비교, 실제 시점별 DART 수정/기업class/상폐/기업행동 PIT를 연결한 후보/기초순위; 새 security/backup side-project 확대 금지. 인수 진척률 38%(45/120) 유지, 이번 일부 종목 확대만으로 완료율 상향 금지.

## 2026-10-13 새 핵심 개발 — 공식 DART 업종 첫 수신 + 업종 대분류별 후보 실제 비교

- 개발 feature `/Volumes/T5DATA/eraleader-core-factor-coverage-20261013` / branch `feature/core-official-factor-coverage-20261013`; 원본 main 미커밋 `native_first_capture.py` SHA `6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6` 보호. `PROJECT_STATE.md` 최신과 `docs/142_DART_INDUSTRY_PEER_ACTUAL_DATA.md` 먼저 확인.
- 기존 10종목 FY2024/25 DART 재무+가격 후보에 **공식 DART company.json 현재 업종코드 10건 첫SHA** 연결(세부9코드, 대분류7), 실제 표본에서 2개 이상 비교 가능한 3개 대분류(26 전자/29 기계/30 자동차), 합계 6종목의 업종 내 매출·영업익·3개월 주가 상대 순서. 원형 한국 PRICE WATCH20/일주월 보고/주문0 보존, 공식 대장주100점·투자1~20위 N/A. 첫 수신 2026-10-13을 과거 2026-10-08 예측으로 소급 금지.
- 실제 대시보드 `http://127.0.0.1:8770/industry_peers_kr.html`, DART 실제 시장/재무·업종 원본 PIN SHA 검증, HTTP200·Chrome 오픈 PASS. 상세 `docs/142_DART_INDUSTRY_PEER_ACTUAL_DATA.md`.
- 신규 테스트+기존 공식 DART/CFS/가격 브리지 영향범위 **9모듈 124/124 pytest PASS(EXIT0)**, 전체 2450+ 회귀 재실행은 미수행. 전체 실사용 인수 38%(45/120) 유지: 일부 샘플 업종 연결로 시장 전체 PIT 인수합격을 과장하지 않음.
- 다음 기본 기능 우선: 산업내 대표기업 3~5개로 확장/산업 실제 통계·기관외국인 수급 최초 원본 연결/단계별 동종 비교와 종합 후보 도출. 사용자 요청 따라 추가 백업·에스크로·보안 부가 기능 개발 후순위.

## 2026-10-14 최신 사용자 지시 — 기능 구현 우선·실제운용 수준 (D-027·D-028)

모든 EraLeader 개발·설계·검증·백업·보안·운영의 기준은 **실제 미래 대장주 검색 시스템 운영에 필요한 수준**. 기능 구현 > 최소 변경 테스트·실데이터 E2E > 필요한 운영 안정화 > 장기 인증. 과거 38% 엄격 기준은 기록만 유지하고 최신 실사용률로 보고하지 말 것. 실매매·자동주문 기능 없음; 실거래 방지 반복 검증·주문 E2E는 범위 밖. 키움 모의/실계좌는 조회 자료 프로파일만 분리하고 연결 변경 시 read-only만 확인. 원본 main/별도 미커밋 7줄 보존, 정상 코드 재작성 금지. 최신 기능 브랜치 /Volumes/T5DATA/eraleader-core-factor-coverage-20261013, 진행상태는 해당 PROJECT_STATE.md 최하단/최신 Git 기준. 코드 변경과 실측 증거: docs/152_REAL_USE_KR_COMPANY_EXPLORER.md.

## 2026-10-14 최신 개발 — D-029 선정 종목을 후속 매매전략에 전달

사용자 확정: EraLeader는 실제 주문은 하지 않지만 **선정된 대장주를 매매전략 후속 프로젝트에 전달해야 한다**. `src/eraleader/strategy_handoff.py`, `scripts/export_strategy_handoff.py`, `src/eraleader/cli.py`의 `offline-integrated --strategy-handoff-out` opt-in 및 `tests/test_strategy_handoff.py`를 분리 feature 브랜치에서 구현. 관찰 WATCH와 전략 선정 POTENTIAL/CONFIRMED 분리, 약화·제외 이벤트 제공. 현재 실물 KRX/DART 10사는 WATCH 10·정식선정 0; 모의 PIT fixture로 진짜 선정상태 출력 경로 확인. 세부 증거·최신 SHA: docs/153_STRATEGY_SELECTION_HANDOFF.md 및 PROJECT_STATE.md 맨 아래. 다른 프로젝트 원본 코드, main 미커밋 7줄 보존.

## 2026-10-14 최신 사용자 확정 — 수신 프로젝트 미지정 (D-030)

EraLeader는 대장주 발굴 및 **범용 JSON 송신·발행**까지만 개발한다. 후속 수신 프로젝트는 CoreAStock/MarketOS 등으로 미리 정하지 않으며 연결은 **사용자가 추후 별도 결정**한다. 외부 프로젝트의 수신기·전략 연동·직접 전송 작업 금지. 기존 `strategy_handoff.py`와 JSON 발행기·대장주 상태이력을 재사용하고, 다음 작업은 EraLeader 자체 선정·발행/자동 갱신 기능으로 이어간다. 관련 최종 정책 DECISIONS.md D-030, docs/153_STRATEGY_SELECTION_HANDOFF.md.

## 2026-10-14 최신 P1/P2 CONTINUE — 공식 전체시장 가격 피처·추가 재무/업종·범용 JSON outbox
- 별도 feature/core-official-factor-coverage-20261013 최신 작업부터 계속. `PROJECT_STATE.md` 마지막 checkpoint 및 `docs/155_KR_MARKETWIDE_REAL_PRICE_AND_OUTBOX_20261014.md` 확인. 기존 main의 미커밋 `native_first_capture.py` 절대 건드리지 않음.
- KRX 실제 2026-10-08 관측 2,765 전시장 종목; DART 현재 33사 CFS+산업 첫 수신 결합; 기존 읽기전용 가격 캐시에서 3/6개월 상대강도 2,261사, 2요소 연구순위 25사. **정식 5요소 TOP20·실전 상태 확정 0**, 기관/외국인 수급 N/A; 2026-10-08을 오늘 가격으로 오해하지 말 것.
- `src/eraleader/strategy_handoff.py` + `scripts/export_strategy_handoff.py --outbox-dir`에 버전별 전략 후보 읽기전용 송신 원장. 실제 WATCH20 연구 JSON 확인, 선정/주문0. D-030 사용자 지정 전 수신 프로젝트 연결 금지. 다음 필수 기능은 *새 거래세션 공식 수집·전체산업/기업경쟁력/수급 인자 결합 → 실사용 5요소 종합 평가 → 선정·약화·교체 상태 및 송신*.

## 2026-10-14 최근 코드 기능 CONTINUE — 업종 Peer · 수급 거래일 게이트 · 연구 TOP20 송신
- 최신 feature 브랜치 SHA는 `git rev-parse HEAD` 확인. 자세한 실제 증거 `docs/156_KR_PEER_FLOW_COHORT_RESEARCH_AND_HANDOFF.md`, `PROJECT_STATE.md` 맨 끝. 원본 main·미커밋 `native_first_capture.py`는 절대 덮어쓰지 않음.
- 전시장 가격·DART33사 연구 50점 후보25 중 연구 상위20과 별개 가격 WATCH20의 **두 목록**을 선정결과 JSON에서 구분(정식 선정 0); 동업종 표본 비교6그룹/매출15/영업익9, 실제 흐름 최신세션 불일치 수급 N/A. KRX 2026-10-08 자료를 2026-10-14 당일 자료로 표시 금지.
- 다음 개발: 같은 최신 실제 세션 데이터 수집과 산업·기업경쟁력·기관/외국인 수급의 실측 결합, 기존 5요소 100점 종합 선정+상태+범용 전달. 과도한 전체회귀/장기인증보다 기능 우선, 변경 영향 pytest+실데이터 E2E. 수신 프로젝트 지정되지 않았으므로 외부 수신기/주문 작업 금지.

## 2026-10-14 최신 성공 체크포인트 — KR 전일 공식시장 실데이터 + WATCH 변동/중립 송신
- 분리 작업 브랜치 `feature/core-official-factor-coverage-20261013`, 실제 HEAD/remote 최신 먼저 확인. `docs/157_LATEST_KR_OFFICIAL_SESSION_WATCH_ROTATION_20261014.md` + PROJECT_STATE 맨 끝 참고, 원본 main의 기존 미커밋 native_first_capture.py/증빙 변경 금지.
- 한국 KRX 실제 2026-10-13 2,761종목, DART공시456건, 가격 RS2,263, 비교가능 CFS/산업 각18, 50점 부분요소 평가11사, 동일일 Kiwoom read-only 관측 1사. 가격 WATCH 10/08→10/13 새4/이탈4/순위변경14, 실제 이력/JSON 별도 연구표/송신. 정식 100점/STATE 선정과 투자성과 N/A, 주문/특정 수신기 없음.
- P1 전시장 업종·기관/외국인·경쟁력 실데이터 확대, P2 기존 종합100점/정식 TOP20, P3 StateHistory/신호 전달을 순서대로. 정상 코드 REWRITE 금지, 작은 변경 테스트+실데이터 E2E 후 Git.

## 2026-10-14 최신 P1 CONTINUE | 원본시장 2,761 + 현재 재무/산업 30사 증분 연결
- 마지막 검증 정상 코드 `feature/core-official-factor-coverage-20261013`에서 계속. 정확한 SHA는 `git rev-parse HEAD`; 기존 main의 미커밋 native_first_capture.py/원본 비밀키·시장자료 불변.
- `docs/158_INCREMENTAL_KR_FINANCIAL_INDUSTRY_CONTINUE_20261014.md` 참고. 기존 KRX 2026-10-13 2,761 일봉/RS 2,263/재무·산업 18/수급 1 연구 본을 DART FY2024/25 원본 12사 + 업종 12사로 증분 확장하여 재무30/산업30/50점 연구22. 원형 WATCH20·기존 SQLite 변경하지 않음. 추가 실적은 10/14 첫 인지 자료이므로 가격관측일 과거 매수신호로 소급 금지.
- 최신 output/kr_20261013_marketwide_30f30i_20261014 JSON+HTML 및 receiver-neutral strategy_outbox (price WATCH20/연구20/정식 선정0) E2E 실행. 다음 P1 데이터 확대→P2 기존 5요소 실제 종합 선정·P3 상태/송신. 사용자 수신 프로젝트 결정 전 외부 수신 어댑터 연결 금지.

## 2026-10-14 P1 마지막 체크포인트 — 40사 공식 연결/다음 수집 중복 방지
- 분리 브랜치 feature/core-official-factor-coverage-20261013 실제 SHA/git 상태를 기준으로 CONTINUE, 원본 main과 사용자 미커밋 변경·인증정보 그대로 보존. `PROJECT_STATE.md` 최신 항목 및 `docs/159_MARKETWIDE_DART_ATTEMPT_DEDUP_AND_40_20261014.md` 참조.
- KRX 2026-10-13 실제 2,761, 공식 DART 현재 재무·산업 각40사, 가격 RS2,263, 연구용 가격+실적 50점30사, 동일세션 Kiwoom 흐름1사. 정식 100점/선정0, WATCH/연구 JSON 자동 송신·원본불변 유지.
- `capture_dart_multi_company.py --auto-marketwide-report --skip-attempted-manifest <현 세션 이미 시도한 CFS JSON>`로 불필요한 동일기업 재조회 없이 다음 12사 자동 선택. 재무·산업/기관수급/경쟁력 실제 원본 확대 후 기존 100점 공식 선정·상태추적에 연결.

## 2026-10-14 최신 P1/P3 CONTINUE — 한국시장 공식 재무·산업49사 + Stage4 연구 WATCH20 상태 원장
- `feature/core-official-factor-coverage-20261013` 최신 HEAD/원격 실제 Git 확인하고 CONTINUE. 원본 main 기존 미커밋 `native_first_capture.py`·설정/첫원문을 건드리지 말 것. 상세 `docs/160_KR_RESEARCH_WATCH_STATE_HISTORY_AND_49_FACTORS.md` 및 PROJECT_STATE 마지막 항목.
- 현재 실물 KRX 2026-10-13 2,761주권, 상대강도2,263, 재무/업종49, 가격+실적 50점 연구38, 키움 실측일치 수급1. 정식 5요소100점/CONFIRMED0. 추가 FY DART 수신 당시 10/13 이전 이용 가능 PIT로 소급하지 않음.
- 신규 `src/eraleader/official_watch_state_bridge.py` + `scripts/record_official_watch_history.py`는 공식시장 PRICE WATCH20을 기존 Stage4 `StateHistory` 별도 연구 SQLite에 기록, 10/08/10/13 실제 각20 행=총40 WATCH, 상태전이0, selected0, orders0. `scripts/publish_official_marketwide_coverage.py --watch-state-ledger`로 JSON/HTML+해당 SQLite+중립 JSON outbox 한 번에 작업 가능.
- 다음 최우선은 **정식 5요소 확인 가능한 실사용 후보 TOP20·잠재/확정/약화/교체** 결선. 소규모 수정 테스트/실물 E2E 후 Git, 외부 수신기(D-030) 미결정 유지.
