# EraLeader 5_4/5_5 — 동결 후보와 별도 성과 라벨 근거 대조

> 2026-10-10 KST. 이 도구는 과거에 실제 등록된 연구용 WATCH 후보의 **평가기간 만기**와 **라벨 공개 가능 상태**를 비교한다. 공급자 신원, 법적 기업행동, 발표시각의 독립 확인이나 실전 시대 대장주 적중률을 **인증하지 않는다**. API 미연결 유지.

## 기존 모듈에 추가된 실제 연결

- `holdout_maturity.py`: 파일 해시가 봉인된 `holdout_manifest.json`으로부터 종목별 사전 지정된 현지 시장 기준 평가기간 종료일을 구한다. **미래 성과 라벨을 읽지 않는다**.
- `frozen_holdout.py`: 별도 전달받은 라벨의 정의ID, 라벨 성숙시각, 실제 게시시각, 평가 cutoff, 중복 ID, 180일의 부정적 결론 조기확정 금지를 독립 검증한다.
- 신규 `src/eraleader/holdout_outcome_reconcile.py`: 두 모듈의 공통 봉인 해시·판정 결과를 연동. **라벨 없이도 실행**할 수 있고, 라벨을 제공한 경우 유효한 연구 라벨만 내부 평가 가능한 것으로 집계한다. `recorded_at_utc`와 시장 현지 KR/US 캘린더를 사용해 날짜를 계산하고 `observed_as_of` 사후 소급등록으로 기간을 늘리지 않는다. 두 기존 평가기 카운트가 불일치하면 오류 처리한다.
- 종목별 `HORIZON_PENDING_NO_LABEL`, `HORIZON_ELAPSED_NO_LABEL`, `LABEL_NOT_YET_AVAILABLE`, `PREMATURE_NEGATIVE_LABEL`, `RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED` 상태로 **5가지 이유**를 제공한다. 평가기간 경과만으로 성공·실패를 생성하지 않는다. 동결 후보에 속하지 않는 별도 결과 라벨은 `unmatched_outcome_count`로 표기하지만 분모/분자에 포함하지 않는다.
- `independent_outcome_source_certified=false`, `historic_pit_certified=false`, `leader_accuracy_certified=false`, `official_leader_promotions=0`은 항상 고정. 연구 라벨을 내부 계산에 반영하는 것과 실제 성과인증은 구분한다.
- CLI `PYTHONPATH=src python3 -m eraleader reconcile-holdout-outcomes --freeze-file <sealed> --evaluated-at '<TZ ISO>' [--outcomes <separate-labels.json>] --out <dir>`. 파생 `holdout_outcome_reconciliation_research.json`만 `backup-local`의 허용 목록에 추가하여 원래 미래 라벨/시세는 ZIP/Git에 넣지 않는다.

## 실제 실행·검증 증거

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_holdout_outcome_reconcile.py \
  tests/test_frozen_holdout.py tests/test_holdout_maturity.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

- 신규 `tests/test_holdout_outcome_reconcile.py` **12개 합성 회귀**: 라벨 미제출/평가기간 경과, 게시 완료 내부 연구 라벨, 너무 이른 부정 라벨 검열, 아직 평가기간 전의 미확인, 공개시각 지연 라벨, 동결 후보에 속하지 않은 가짜 추가 라벨, 정의ID 변조·중복·미성숙 공개/동결 manifest 변조와 symlink, CLI/백업/복원.
- 기존 429개에서 **전체 441개 pytest PASS / 0 FAIL**. 이 수는 코드 검증 건수일 뿐 실제 시대의 대장주 예측 적중률 측정값이 아니다.
- 실제 Mac의 오프라인 CLI로 **합성** 2026년 4월 등록·180일 봉인 후보 4개를 2026-10-10 17:00 KST로 대조했다. 성과 라벨 없이는 4개 모두 `HORIZON_ELAPSED_NO_LABEL` (내부 평가 가능한 라벨 0). 분리된 4개 합성 라벨을 공급하면 내부 평가 가능한 연구 결과 **3개**, 미공개/미성숙 1개; `leader_accuracy_certified=false`·공식 확정 대장주 0. 이 숫자를 2026년 실제 발견 성과로 취급하지 않는다.
- `output/continuous/holdout_outcome_reconciliation_20261010.zip`: 파생 JSON **1개**만 SHA256 확인·새 폴더 복원, 합성 원본 라벨·가격/키 제외. 실전 API/메시지 0.

## 남은 필수 연구 과제

국내외 공식 상장·상폐 기업 법적 식별자, 기업행동/배당·분할·현금 지급, 재무/산업 공시 시점, 조정가격, 이 모든 원천의 독립 기록 시각 확보가 필요하다. 사전에 동결한 미래 후보의 실제 성과를 성숙 이후 **독립된 평가 데이터로 대조**해야 진짜 조기 포착 시점과 정밀도·오탐/생존편향을 검증할 수 있다. `D-021`에 따라 실제 SSD 물리 분리/재연결·재부팅은 API 연결 완료 후 최종 단계에서만 실행한다.

## 2026-10-11 — 5_5 만기시각과 부정 라벨 대조기 일치

기존 `reconcile_holdout_outcomes`도 등록일+평가기간을 **날짜만** 비교하여 만기 1분 전을 `HORIZON_ELAPSED_NO_LABEL`로 표시하고, 같은 현지 날짜의 조기 부정 라벨을 잘못 평가 가능으로 계산했다. 후자는 이미 보강된 `evaluate_frozen_candidates`와 결과가 달라 예외까지 일으켰다. 등록 현지 **시각**+동결 horizon을 UTC로 정규화하여 날짜·서머타임 경계를 통일, 표본에 `horizon_end_utc` 보강. 라벨 전용 기존 평가기는 수정하지 않았으며 사전 봉인 모델·라벨 정의도 불변.

신규 합성 회귀 2개: KR 첫 등록 17:00, 만기일 16:59/17:00의 라벨 없는 대조 및 16:59 부정 라벨의 `PREMATURE_NEGATIVE_LABEL` 검열/기존 평가기 카운트 일치. 수정 전 신규 2건 FAIL, 수정 후 집중 재검증 PASS. 시장의 공식 데이터/미래 주도주 적중률은 여전히 미인증.
