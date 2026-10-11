# EraLeader 5_5 — 사전등록 Top-K 전 코호트 누락 방지 로컬 평가

2026-10-11 KST. **발굴 성능이 높은 코호트만 뒤늦게 골라 보고하는 선택편향을 줄이기 위한 최초 기록 원장**이다. 기존 `ranked_discovery.py`, `ranked_outcome_receipts.py`, native WATCH/score 및 역사적 PIT/backtest 엔진을 변경하지 않는다.

## 추가한 실행 기능

- `src/eraleader/prospective_census.py`: 현재 **최초 사전 Top-K 동결** 문서(시장/모델/K/평가기간/사전 성공기준 원문 SHA)가 있는 동일 폴더의 JSON 배열 `census_input.json`을 입력으로 받는다. 각 항목은 `frozen`, `definition`, `outcomes`, `receipts` **안전한 로컬 파일명**만 선언한다.
- `register_census`는 현재 OS 로컬 UTC 시각이 **원래 rank freeze 시각부터 60분 이내**인 경우에만 `census_*.json`을 O_EXCL로 최초 기록한다. `retrospective_freeze=true`, 아직 기록되지 않은 성공기준, 이미 존재하는 outcome/receipt, 중복 동결ID, 시장/문서 SHA 불일치를 차단. 새 등록문서는 원래 순위 파일의 SHA, 규칙 원문 SHA, 각 Top-K **선택 분모**, 로컬 시장 시간대(DST) 평가 만기시각과 최초 등록 시각을 바이트 SHA로 함께 봉인한다. 이후 동일 이름 덮어쓰기 불허.
- `audit_all_registered_censuses`는 등록 디렉터리의 **모든 `census_*.json`**을 순회하여, 일부 코호트만 선택 평가하는 옵션을 제공하지 않는다. 다른 파일로 숨기려는 시도/중복 코호트/registry digest 변조·K 축소를 차단한다. 결과 파일이 없거나 미래 만기 전이면 **미확인**, 기간이 지났지만 결과가 없으면 **만기·원천 미확인**, 원본 결과/receipt 중 하나만 존재하면 **부분자료·미확인**으로 집계한다. 정답을 0으로 가정하거나 전체 선택 K에서 제거하지 않는다.
- 두 결과 입력 모두 나중에 존재하면 기존 `audit_ranked_outcome_receipts`가 당시 고정한 성공 정의·코호트·문서 claimed 시각·normalized evidence SHA를 감사한 연구용 결과만 누적한다. 전체 고정 분모와 소스 일치 hit/known negative/unknown, known만의 precision, unknown 최악/최선 가정의 full-K 상하한을 표시한다. **이 수치는 공인 precision, 통계적 신뢰구간 또는 공식 대장주 추천이 아니다.**
- 로컬 `scripts/run_prospective_census.py`는 등록 `register`와 전체 점검 `audit` 두 명령 제공, API/시장자료 재다운로드/실제 알림/주문 0. `audit`는 실전 종목ID, 원천 원문, 비밀키를 출력하지 않고 `prospective_census_research.json` 하나를 derived 폴더에 원자적으로 기록. `local_backup.JSON_NAMES`에 **이 파생 JSON 하나만** 추가하여 기존 6_5 안전 ZIP SHA/새 경로 복원 지원; 원본 ranked freeze·outcome/source 문서는 ZIP에 넣지 않음.

## 사용 예 — 경로는 예시이며 실제 데이터 존재를 의미하지 않음

```bash
cd /Volumes/T5DATA/eraleader

# output/live/cohort_evidence/census_input.json 예:
# [{"frozen":"frozen_rank.json","definition":"leader_rule.json",
#   "outcomes":"future_outcomes.json","receipts":"future_receipts.json"}]
# 등록 전에 실제 미래 결과 파일 2개는 존재하면 안 됨.
python3 scripts/run_prospective_census.py register \
  --spec output/live/cohort_evidence/census_input.json \
  --registry-dir output/live/registered_censuses \
  --name census_20261011_kr.json

# 원래 모든 사전등록 코호트 포함; outcome 없는 후보도 분모에 유지
python3 scripts/run_prospective_census.py audit \
  --registry-dir output/live/registered_censuses \
  --evaluated-at '2026-10-11T21:00:00+09:00' \
  --out output/live/derived
```

## 검증 및 명확한 한계

- `PYTHONPATH=src python3 -m pytest tests/test_prospective_census.py -q --tb=short`: 첫 구현 22 GREEN; 추가 누락 숨김·백업 2건에서 **2 RED FAIL 재현 후 24/24 GREEN**. 테스트는 합성 clock와 synthetic K를 사용, 진짜 미래 대장주 적중 인증이 아님.
- 기존 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short`, `scripts/check_handoff.py`, `py_compile` 및 Git 공개 보안검사를 릴리스 전에 확인.
- **절대적 한계**: 로컬 OS 시계/순위 파일/manifest 자체가 외부 공증이 아니며, 등록 디렉터리 자체를 삭제하고 다시 만드는 공격의 '보이지 않는 코호트'는 인증할 수 없다. 이 구현이 보장하는 것은 **현재 디렉터리에 기록된 코호트 전체의 누락 없는 로컬 감사**다. 자연스럽게 수개월 뒤 도래하는 독립 outcome/KRX/DART/SEC 법적 상장·상폐 및 기업행동·발행자 공개시각의 원천 진실성은 **미검증**.
- D-017 외부 API 연결은 로컬 1~6단계 기능 이후, D-021 실제 SSD 탈착·재연결/맥북 재부팅은 마지막 단계. 공식 확정 리더0 / 진짜 prospective precision N/A 유지.

## 실제 Mac OS clock 합성 CLI 스모크

- Git ignored `output/cohort_census_os_clock_trial_*` 임시 자료에서 **지금 OS 시각**에 synthetic KR 2종목 점수 생성 → 최초 rank frozen/K=2/30일/사전 label 원문 SHA → 미래 outcome/receipt 파일 미생성 상태에서 CLI `register` O_EXCL → CLI `audit` 실행.
- 실제 결과: 첫 등록 코호트1/원래 선택 분모2/기간 미도래2/known positive0/known negative0/전향 실전 precision **N/A**/공식 leader0/API0. `prospective_census_research.json`만 로컬 SHA ZIP 검증 및 신규 경로 바이트 동일 복원. 원본 score/rule/frozen/spec 파일 감사 전후 SHA 불변.
- 이는 100% synthetic 실행 예제이며 실제 시장 신규 대장주 발굴·미래 성과 인증이 아니고, 추후 시세 원천 연동 전 정책과 오류 처리 검증에 한정된다.

## 2026-10-11 완료 검증

- 변경 테스트 신규 **24개**, 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1456/1456 PASS, exit0**(이전1432+24); collect-only **1456**, handoff 30 작업ID/40 필수 경로 PASS, py_compile PASS, diffcheck PASS.
- 첫 22개 GREEN 후 미등록 파일명으로 불리한 코호트를 숨기는 실질 결함 + 파생 JSON 백업 누락 2건을 별도 RED 테스트로 검출하고 수정(24 GREEN). 입력 디렉터리의 지원하지 않는 파일/링크 존재 시 평가 전체 중단, 기존 백업 allowlist에는 신규 파생 JSON 하나만 포함.
