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
