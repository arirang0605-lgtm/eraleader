# EraLeader 6_5 — 안전한 WATCH 운영 보고서 스케줄 연결 (API 미연결)

> 2026-10-11 KST. **기존 가격 전용 배치를 보존**하고 명시적 KR/US 로컬 WATCH 원장에 대해서만 반복 실행·중복 생략·실패 재시도·파생 보고서 ZIP 백업/검증을 연결합니다. 실제 macOS launchd 서비스 설치·기동, 이메일/텔레그램 발송, 유료 API 호출, 확정 대장주 판정은 전혀 하지 않습니다.

## 발견한 기존 실행 공백

- 기존 `local_schedule.run_scheduled`는 **가격 캐시 날짜/원본 SHA256**를 사용하여 중복 실행을 회피합니다. 가격 관측 날짜가 그대로여도 새 실시간 WATCH가 등록되는 경우, 이 사실을 체크포인트가 알지 못했습니다. 신규 `watch_operating_reports.py`의 일·주·월 후보 전이·동종업종 연구 가설도 스케줄러에 연결되지 않았습니다.
- 2026-10-11 실제 T5DATA의 레거시 가격 캐시를 읽기 전용 검사했을 때 최종 관측일은 **KR 2026-10-02 / US 2026-02-26**였습니다. 이전 `max_age_days=10` 기준으로 미국 캐시 때문에 가격 배치가 건너뛰어집니다. 최신 WATCH 원장이 나중에 들어와도 이 오래된 미국 캐시에 종속되면 미래 후보 보고서 운영이 막힙니다.
- 따라서 **두 가지 opt-in 모드**를 추가하고 기존 가격-only 기본 모드를 보존했습니다.

## 1. WATCH 소스 설정 파일 (로컬 파일만)

예: `output/watch_research.local.json` — `output/`은 Git 제외. 반드시 **절대 경로**와 실제 존재하는 파일을 사용합니다. 빈/합성 자료나 아직 없는 파일로 실전 가동하지 않습니다.

~~~json
{
  "schema_version": "eraleader.scheduled_watch_research.v1",
  "markets": {
    "KR": {
      "watch_ledger": "/Volumes/T5DATA/eraleader/output/research/prospective.sqlite",
      "model_version": "pinned-kr-model-v1"
    },
    "US": {
      "watch_ledger": "/Volumes/T5DATA/eraleader/output/research/prospective.sqlite",
      "model_version": "pinned-us-model-v1"
    }
  }
}
~~~

같은 `prospective.sqlite` 안에 두 시장이 들어 있어도 시장/모델로 엄격히 분리합니다. 선택적으로 시장마다 `score_ledger`·`feature_root` 두 필드를 **동시에** 지정하여 최근 두 관찰일 동종 업계 점수 우위 자료를 연결할 수 있습니다. 한쪽만 작성하면 오류. 설정 파일은 필수 스키마/정확히 KR+US 두 시장/추가 알 수 없는 필드·중복 JSON 키·파일 symlink·없는 경로를 차단하며 원시 자료/비밀키를 복제하거나 Git에 올리지 않습니다.

## 2. 기존 가격 배치 + WATCH 보고서 (가격캐시가 최신일 때)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --watch-research-config /Volumes/T5DATA/eraleader/output/watch_research.local.json \
  --watch-max-age-days 7
~~~

- `run_scheduled`에 신규 선택 `watch_research_config=None`, `watch_max_age_days=7`를 추가했습니다. **미제출 시** 기존 가격 배치·중복 건너뛰기·가격 캐시 검증 로직은 그대로 동작합니다.
- 선택 설정이 있으면 기존 `batch.lock` 잠금 안에서 **두 시장 WATCH 자료를 먼저** 각각 `compile_watch_operating_report`로 검증하고 Markdown/HTML을 순수 메모리 렌더합니다. 어느 한쪽이라도 `NO_PROSPECTIVE_OBSERVATIONS`/7일 초과 `STALE_RESEARCH_OBSERVATIONS_NOT_CURRENT`면 **가격 배치와 알림 미실행**, 체크포인트 미갱신 `SKIPPED_WATCH_RESEARCH_NOT_CURRENT` 반환. 과거 관찰 누락을 음성/실패로 대체하지 않습니다.
- 완료 판단 체크포인트는 **가격 관측일 + 가격 SHA + 각 시장 WATCH 원본 SHA + 선택 score 증거 + 모델·시장 현지 날짜 + 소스 설정 파일 SHA**를 비교합니다. 따라서 가격 날짜가 바뀌지 않아도 새 WATCH가 쓰이면 다시 일·주·월 연구 보고를 발행합니다. 동일 소스면 기존 백업 유효성 확인 후 중복 실행 건너뜁니다.
- 기존 가격 배치 완료/중간 보고서 생성 후, WATCH 전후 원장 변경을 **백업 전·후, 기존 백업을 재사용해 skip하기 직전에도** 재조회합니다. 다른 기업 관측 추가·재해시 source 변경·모델 설정 교체·오래된 자료 문제가 발생하면 `WATCH source revised during scheduled run`으로 오류를 발생시키며 *확인된* 체크포인트를 갱신하지 않습니다. 실패 때 재시도 가능.
- 양국 6기간 HTML+Markdown 및 시장별 JSON 2개, 총 **파생파일 14개**를 생성한 후 기존 안전 ZIP SHA 검증이 통과할 때만 `last_verified_batch.json`에 스냅샷 증거와 두 시장 run ID를 기록합니다.
- **주의**: 현재 미국 가격 캐시가 낡았으므로 기본 설정에서 이 혼합 배치 경로는 `SKIPPED_STALE_CACHE`입니다. 가격 캐시를 몰래 최신으로 주장하거나 `--allow-stale-research`를 기본 활성화하지 않습니다. 기존 가격 연구를 오래된 cache로 실행하도록 명시적으로 예외 허용해도 WATCH 자료의 7일 신선도 조건은 완화하지 않습니다.

## 3. 가격 캐시와 독립된 WATCH-only 모드 (미래 후보 운영용)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --watch-only \
  --watch-research-config /Volumes/T5DATA/eraleader/output/watch_research.local.json \
  --watch-max-age-days 7
~~~

- 새 `run_scheduled_watch_only`는 레거시 KR/US **가격 파일을 열거나 가격 `execute_local_batch`를 호출하지 않습니다**. 입력 두 시장의 현지 실제 등록 최근 WATCH 원장만 평가해 14개 파생 WATCH 보고서 작성. 가격 캐시가 아예 없어도 작동합니다. 먼저 두 시장 모두 신선한 명시적 관측 증거가 있어야 하며, 없으면 자료부족으로 보류하고 산출물을 새로 발행하지 않습니다.
- 가격 배치와 **별도** `output/scheduled_watch` 경로에만 보고서 발행, `output/scheduler_watch_control/last_verified_watch_only.json`에 별도 확인 체크포인트, `output/scheduler_watch_backups`에 검증된 ZIP 저장. 기존 가격 `last_verified_batch.json` 및 가격 보고서와 혼합하지 않습니다. 두 시장 source hash/고정 모델/설정 SHA·시장 현지 날짜가 같으면 ZIP 검증 후 `SKIPPED_UNCHANGED_WATCH_EVIDENCE`로 중복 실행 방지. 새 WATCH가 들어오면 같은 가격 날짜라도 재실행.
- source/설정파일이 분석 도중, ZIP 생성 도중 또는 중복 skip 검사 도중 수정되면 체크포인트를 진행하지 않습니다. 보고서 렌더 실패/원본 변조/ZIP 해시 실패도 실패로 종료하고 다음 실행 때 재시도. `WATCH_ONLY_RESEARCH_VERIFIED_BACKUP` 성공은 **로컬 파일·백업의 연구 정합성**에 한정되며, 실전 PIT·원천 제공자 공증·미래 대장주 확정이 아닙니다.
- 어떠한 모드에서도 외부 API 호출 0, 실제 메시지 발송 0, 확정 대장주 0, 실제 예측력 인증 false입니다.

## 4. macOS launchd 설정 파일 생성 (설치·기동 아님)

`write_launch_agent` 및 스크립트에 명시적 WATCH 설정을 전달합니다. `--watch-only`인 경우 만들어지는 홈 볼륨 bootstrap은 **프로젝트 스크립트·WATCH 설정파일 존재 여부만** 확인하며, 불필요한 옛 가격 캐시 폴더에 의존하지 않습니다. SSD가 없으면 `SKIPPED_EXTERNAL_SSD_UNAVAILABLE` 로그만 남깁니다. 상대 경로·symlink config, 모델 누락·시장 한쪽 누락이면 bootstrap 생성 전 오류.

~~~bash
PYTHONPATH=src python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --watch-only \
  --watch-research-config /Volumes/T5DATA/eraleader/output/watch_research.local.json \
  --generate-plist /Volumes/T5DATA/eraleader/output/watch_research.generated.plist
~~~

**사용자 승인 없는 `launchctl load/bootstrap`, 실행시간 설정 변경, 자동 전송 채널 연결, 원격 서버 배포는 전혀 수행하지 않습니다.** plist를 파일로 생성하는 명령은 홈 볼륨의 실행 bootstrap을 작성하지만 launchd에는 설치하지 않습니다. 사용자와 실행 정책 확정 후 별도 단계에서 실제 설치 여부를 결정해야 합니다.

## 5. 재현·테스트 범위

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_scheduled_watch_bridge.py tests/test_local_schedule.py \
  tests/test_watch_operating_reports.py tests/test_local_backup.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

기본 가격-only 동작 보존, 혼합 WATCH opt-in, WATCH-only 가격파일 미접근, 양국 중 하나 누락·과거/미존재 WATCH, 동시 점수 원장 필드 계약, 누락·중복 설정 키, 로컬 source SHA 변경/수정 감지, 실패백업 재시도, 중복 실행/캐시 같으나 새 WATCH 도착, 원본/비밀키 ZIP 제외, macOS launchd 부트스트랩 공백 경로 인용 및 가격 캐시 미의존성, 실제 외부 서비스 미설치 합성 회귀를 포함했습니다.

운영 절차와 원본 시장자료 인증은 별도입니다. 외부 API 연결은 D-017 로컬 개발 완료 후, 물리 SSD 분리·재연결·맥 재부팅 검증은 D-021 API 연결 후 최종 단계에만 진행합니다. 전체 30개 작업의 실전 데이터/PIT 인증 완료 선언 금지.
