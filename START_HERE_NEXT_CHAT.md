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
