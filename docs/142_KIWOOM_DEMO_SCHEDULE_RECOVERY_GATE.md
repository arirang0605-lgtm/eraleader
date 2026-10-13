# 142 — 키움 모의 수급 일별 자동 실행 준비·SHA 복구 게이트

**개발 ID:** 2_5·4_2·5_5·6_2·6_5 / **2026-10-13 KST**. 기존 정상 가격·PIT·WATCH·보고·수급 배치 코드는 재작성하지 않았고, 해당 기능은 기존 독립 개발 브랜치에서만 추가했다.

## 작동 범위

- 새 `src/eraleader/kiwoom_daily_runner.py`가 기존 `kiwoom_shared_daily_batch.daily_batch()`를 조합. 명시 선정한 1~5개 코드가 기존 공식 KRX/DART 후보 cohort에 포함돼야 하며, 공식 연구 후보/산업 SHA·as-of가 일치해야 한다.
- 한국 시간 **주중 + 오늘 거래일 기준 기본 자료 + 오후 18시 이후**만 모의 `ka10059` 수급 연구 조회 허용. **휴장일은 독립적으로 인증하지 않으므로**, 주중 휴장에는 공식 기준일 미갱신이면 정지하지만 공식 자료가 잘못 갱신된 경우 거래소 달력을 보증하지 못한다. 오늘 자료가 없거나 과거 기준일이면 `SKIPPED_STALE_OR_FUTURE_BASELINE`, 조회0.
- `--apply`가 없는 점검 모드가 기본이며 외부 브로커 호출/로컬 lock 작성 **0**. 명시 `--apply`에서만 기존 Mac 로컬 `SharedBrokerAPI` Unix socket `ReadOnlyClient('eraleader')` 상태 확인 후 요청한다. **실계좌/키 조회·주문·점수 승격·외부 알림 없음**.
- 한 날짜에 대한 발행본 1개만 허용. 전체 SHA+파일 canonical JSON + 회사별 연구 보고 원문/HTML·회복원본 candidate/industry SHA·시장 모드/주문 금지 확인. 이미 게시된 자료가 정상이라면 추가 브로커 요청 없이 `SKIPPED_ALREADY_PUBLISHED`.
- 메인 대시보드 링크만 사라진 장애는 개인 파일의 SHA 확인 후 `REPAIRED_MISSING_DASHBOARD_LINK`로 복원한다. 손상/변조·불완전 원본·잔여 `.kiwoom_daily_*` scratch가 있으면 자동 삭제/추정/덮어쓰기 대신 **BLOCK** 및 수동 증거 보존.
- `fcntl.flock(LOCK_EX|LOCK_NB)`로 사이트별 동시 실행 차단. 0700 디렉터리·owner-only 잠금 파일을 사용하며 키움 전송 실패 중 부분 게시 없음. 최근 시장자료를 사후 시점으로 소급하지 않는다.

## 실행 계약

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 scripts/run_shared_kiwoom_daily.py \
  --site /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/site \
  --candidate-json /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/basic_candidates_kr.json \
  --industry-json /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/industry_peers_kr.json \
  --codes 005930,000660
# 실제 조회를 명시하려면 마지막에 --apply (지금 기준 자료가 stale이면 0 API)
```

- `--generate-plist <프로젝트의 output/ 바로 아래 새 절대경로>`는 **1시간 간격 launchd 설정 파일을 생성만** 한다. 직접 설치·launchctl load·등록·백그라운드 실행은 하지 않는다. 설정 파일에는 키·토큰이 없으며 `--apply`가 명시됨. 설치하면 1시간마다 사전검사를 실시하나, 기준 데이터가 당일로 갱신되어야 실제 모의 조회를 실행한다.
- 실제 Mac/T5DATA 생성 파일은 SSD 파일시스템 권한 표시가 `0700`으로 나타남(소유자 전용). Mac 내부 합성 테스트 경로는 `0600`. 접근 권한을 0600이라고 허위 기록하지 않는다.
- 현재 생성 산출물: Git ignored `output/kiwoom_demo_hourly_opt_in_revised_20261013.plist` — **미설치**. 외장 SSD 분리/맥북 재부팅·실계좌·실전 알림 테스트는 실시하지 않음.

## 실제 검증

- 모의 거래 자료가 이미 연구로 수집된 2026-10-13 시각에 실제 `--apply` 실행: 공식 기본 분석 JSON의 기준일이 **2026-10-08**이므로 `SKIPPED_STALE_OR_FUTURE_BASELINE` 정상, API 호출0, 주문0. 이전 2사 수급 `20261013` 연구 페이지를 공식 과거 20261008 대장주 점수에 결합하지 않음.
- 변경 영향 범위 8개 테스트 모듈 **105 PASS / FAIL0 / ERROR0 / SKIP0 / pytest EXIT0**. 오프라인 fixture로 새 자료 정상 발행/재실행, 주말·시각 조기 차단, 오래된 기준일, SHA/JSON 끝 공백 변조 탐지, 죽은 프로세스 이후 링크 복구, 중복 호출 차단, 네트워크 실패 재시도 가능, 변경 파일 보호, stage 잔존 보존, 동시 잠금, 실계좌·주문 금지, plist 생성만 검사. 증거 `output/verification_logs/kiwoom_schedule_scoped_20261013.{log,xml}`.
- `pytest` 전체 수천 건 통합 회귀/20영업일 실전 전향 검증은 이 변경에서 수행하지 않았다.

## 남은 실제 운영 결선

공식 KRX/DART 오늘자 원시·회사/주권·분할/상폐/산업 PIT와 일별 후보 cohort 최신 스냅샷이 **같은 경로로 제공되는 파이프라인**을 연결해야 지속되는 무인 조회가 가능하다. 현재 baseline은 2026-10-08로 오래되었으므로 일정 파일만 설치해도 자동 수급 발행이 되지 않는다. 배치의 설치/활성화는 그 후 운영 승인·모니터링 체계와 함께 검증한다.
