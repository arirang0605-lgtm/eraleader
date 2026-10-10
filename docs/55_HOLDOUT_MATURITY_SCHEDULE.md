# EraLeader 5_4/5_5 — 선행 WATCH 동결 홀드아웃 평가기간 만기 일정

> 2026-10-10, 오프라인 구현. **평가기간이 지났다는 사실은 결과 라벨을 알거나 투자 성능을 검증했다는 뜻이 아니다.** 합성 데이터의 만기일 계산과 실제 미래 대장주 검증을 혼동하지 않는다.

## 목적

실제 후보를 최초 등록한 시각에서 미래 대장주 확인을 위한 **사전 동결된 평가기간(horizon)**이 언제 끝나는지 계산한다. 현재 `freeze_registered_candidates`는 시간·모델·라벨 정의를 봉인하고 `evaluate_frozen_candidates`는 추후 별도 outcome 라벨을 읽는다. 두 작업 사이에서 사용자가 아직 검증할 수 없는 종목을 조기 실패 처리하지 않고 “전체 기간 경과/미경과”만 모니터링할 수 있는 로컬 입력검사가 필요하다.

## 코드·계약

- `src/eraleader/holdout_maturity.py`의 `audit_holdout_maturity(frozen_file,as_of,...)`는 기존 검증 함수 `_read_frozen`로 frozen JSON의 SHA256, 연구용 상태, 모델·라벨 정의·180일 등의 고정 기간을 재사용한다. 원본 `prospective.sqlite`나 미래 성과 라벨을 **읽지 않는다**.
- 시장별 실제 시간대 `Asia/Seoul` 또는 `America/New_York`를 사용하고 `recorded_at_utc`의 현지 날짜부터 사전 동결된 `horizon_days`만큼 계산한다. `observed_as_of`가 기록일보다 빠르더라도 “역사적 첫 신호”로 대체하지 않으며, backfill은 freeze 단계에서 제외된다.
- 각 동결 종목은 `horizon_end_market_day`, `days_until_horizon_end`, `full_horizon_elapsed`와 별도로 **`leader_outcome_known=false`**, `outcome_source_independently_verified=false`를 출력한다. 전체 집계 `horizon_elapsed_count`/`horizon_pending_count`는 만기 기간만 의미하고 true/false leader label을 생성하지 않는다. `actual_known_outcomes=0`, `official_leader_promotions=0`, `historic_pit_certified=false`는 불변.
- 과거 freeze cutoff 이전 시각, 미래 시각이라고 현재인 척 하는 시각, timezone-naive 시각, 시그널 중복/변조/시간 순서 역전 및 symlink 파일은 오류로 거부한다. 이 검증은 로컬 SHA 및 날짜의 내부 정합성만 확인한다. 외부 공인 거래소·시각 공증을 대체하지 않는다.
- 명령: `PYTHONPATH=src python3 -m eraleader audit-holdout-maturity --freeze-file <sealed.json> --as-of '2026-10-09T17:00:00+09:00' --out <dir>`. 산출 `holdout_maturity_research.json` 한 개만 기존 `backup-local` 허용 목록에 추가한다. 동결 원본, 미래 outcome labels, 유료 자료 및 개인정보는 Git에 업로드하지 않는다.

## 검증 결과

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_holdout_maturity.py tests/test_frozen_holdout.py tests/test_discovery_negative_maturity.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

- `tests/test_holdout_maturity.py`의 **11개 합성 테스트**: 모든 후보 미만기→만기, 정확한 180일 도달, 두 후보의 다른 등록일/남은 일수, 라벨 파일 없이 미인증 유지, 미국 DST와 현지 날짜, 미래/이전 시각 거부 3건, 변조·symlink 파일 거부, 재해시 중복 ID 거부, CLI와 원본 성과 라벨 제외 ZIP/복구 검증.
- 전체 스위트: 기존 418개 + 11개 = **429/429 PASS / 0 FAIL** (Git 독립 격리 검증은 별도 결과 기준).
- 합성 동결 후보 4개(2026년 4월 등록/사전 동결 180일)를 이용하여 2026-10-09 연구 일정으로 실행: `eligible_frozen_candidates=4`, `horizon_elapsed_count=4`, `horizon_pending_count=0`, **실제 확인된 outcome=0**. 이는 실제로 4개 기업의 성과를 안다는 뜻이 아니다.
- 파생 JSON만 `output/continuous/holdout_maturity_research_verified_20261010.zip`에 SHA256 검증 및 복원; 원본 성과·개인키·미래 라벨 파일 제외. 외부 API 사용 0.
- 사용자 D-021: 실제 SSD 물리 분리·재연결 및 맥북 재부팅은 외부 API 연결 후 최종 검증 단계에 실시한다. 이번에는 수행하지 않았다.

## 미완료

**가장 중요한 다음 작업은 독립 공급자/공시/기업행동 이력과 실제 미래 결과 자료 연결**이다. 기간 경과한 후보를 `evaluate-holdout`로 실제 평가할 때에도 outcome source authenticity, maturity/published_at, delisting consideration, market-local trading days, PIT bias 및 predeclared label definition을 독립 검증해야 한다. 실제 시대 대장주 발굴 정확도, precision/recall, 운영 인프라 최종 완성을 인증하지 않는다.

## 2026-10-11 — 5_5 만기 일정 현지 시각/DST 정확성 보강

기존 `audit_holdout_maturity`는 현지 **날짜**가 `recorded_at + horizon_days`에 도달한 자정부터 `full_horizon_elapsed=true`로 보고했다. 최초 WATCH가 17:00에 등록되었다면 같은 날 16:59는 아직 만기 전이다. KR/US 시장 현지 시각 기준 사전 고정 달력일을 더해 UTC 절대시각으로 비교하도록 수정. 기존 `horizon_end_market_day`/일수 표시 유지하고 감사 추적 가능한 `horizon_end_utc` 필드를 추가했다. 종료일에 `days_until_horizon_end=0`이라도 `full_horizon_elapsed=false`일 수 있다.

KR 종료 1분 전/정시, 미국 2026년 3월 DST 전후(최초 16:00 EST → 10일 뒤 16:00 EDT) 신규 합성 회귀 3개와 이전 '자정부터 만기' 두 테스트의 기대값 교정. 수정 전 새 회귀 2건 실패, 수정 후 집중 재검증 성공. 결과 라벨/주도주 성공을 생성하지 않으며 독립 PIT 인증 false.
