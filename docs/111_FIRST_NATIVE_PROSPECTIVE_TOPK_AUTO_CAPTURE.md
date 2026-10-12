# EraLeader 5_3 · 5_5 · 6_5 — 최초 WATCH·자동 점수 Top-K 전향 코호트 원스텝 동결/등록

2026-10-12 KST. `docs/88`, `docs/95~99`, `docs/106~107`의 개별 작업을 실제로 이어서 실행하는 **로컬 최초 실전 검증 준비 기능**. 무작위 점수/결과라벨, 과거 시점으로 거슬러가는 예측, 새 종목/거래소 API 수집 **없음**. MarketOS/CycleOS, 정상 가격/기존 WATCH·native score 계산 및 평가 코드를 재작성하지 않음.

## 개발 목적/중요한 기존 공백

EraLeader는 ① 최초 WATCH, ② 원문 피처 4개로 재현 가능한 native 점수 최초기록, ③ 그때의 Top-K freeze, ④ 이후 미래 outcome 판정이라는 **의도적으로 분리된** 단계를 가지고 있다. ③ `freeze_native_topk`와 ④를 위한 `register_native_census`를 사람이 연속 수동 실행할 경우 너무 늦게 동결하거나, 최초 K/성공기준/원본 WATCH 점수와 등록 시각이 어긋나고, 준비 안 된 코호트만 임의 선택하는 위험이 있었다. 이번에는 **사전 등록된 모델·K·결과 규칙/ SHA·시장·원본 경로** 한 파일을 받아 두 기존 검증기를 끊김 없이 실행한다.

**신규** `src/eraleader/native_first_capture.py`:
- `read_capture_plan(plan)`: **JSON 이중 키/NaN·임의 추가키 금지**, KR/US/모델/K(1~1000)/성공 horizon(1~1095 시장 현지 일수)/점수 신선도(1~168시간), 최초 긍정 WATCH/score ledger, 원래 feature docs 디렉터리, **원래 label rule 파일의 실제 바이트 SHA-256**를 검증한다. `model_version`을 개별 first-score/native 증거와 일치시켜야 하며 label rule의 `label_definition_id`·시장/기간/원문 bytes 변경 시 무조건 중단. **현재 시계/일부 원시 정보가 실제 공인 PIT임을 인증하지는 않는다.**
- WATCH 0건 또는 native score가 아직 **전체** 긍정 WATCH에 대해 쓰이지 않았으면 `WAITING_FOR_NATIVE_FIRST_WRITE_EVIDENCE`로 대기하고 영구 코호트 파일/성공 라벨을 전혀 생성하지 않는다. 점수가 1건만 있는 2건 WATCH의 부분 상위 승자를 동결하지 않는다. 모든 점수가 존재해도 재현된 피처·공식·원본 WATCH SHA가 불일치/노후화됐거나 K가 유효하지 않으면 오류로 중단한다.
- 실제 동결 **전에** `freeze_native_topk`로 read-only 원본 WATCH·native 4-factor 점수·first-write clock·formula를 별도 임시 디렉터리에서 전수 재검사해 잘못된 입력 때문에 캡처 폴더가 미리 생성되지 않게 한다. 성공한 frozen 원본 byte를 캡처 파일로 **O_EXCL 최초 기록**, 그때 원본 label rule의 바이트를 동일하게 복사하고 처음 정한 K/일자/미래-label protocol SHA 고정. 전망 snapshot은 **실제 실행 현재 OS UTC**, 과거 WATCH 날짜 아님. 점수 최초 기록은 이전 WATCH 최초 시각과 구분하며, 오래된 점수는 지금 최초 발견이라고 소급 등록되지 않는다.
- `census_input.json`과 `native_source_proofs.json`을 자동 생성해, 이미 구현된 `register_native_census`가 원래 freeze와 모든 positive WATCH의 first written numeric score를 감사하고 **새 O_EXCL SHA 영수증 인덱스/별도 native 강제 마커**로 등록한다. 등록 즉시 기존 `audit_native_census`로 다시 점검하여 처음 선택한 모든 Top-K가 `unknown/censored`이고 공식 리더 0인지 확인. **미래 결과 파일(`future_outcomes.json`·`future_source_receipts.json`)은 쓰거나 읽지 않음**; 나중에 정해진 시각에 독립 원천 증빙으로만 별도 평가. 중간 outcome 파일이 나타나면 최초 등록 자체를 중단한다.
- 최초 등록은 **시장+원래 모델 버전 SHA 기반 고정 경로** `native_<kr|us>_<model_sha_prefix>` 사용. 사용자가 `cohort_id`·K를 바꿔 같은 모델의 동일 점수로 두 개의 "첫 예측" 코호트를 등록하지 못한다. 원래 계획 SHA, rule/first-frozen raw SHA, native proofs SHA, 등록 manifest SHA 및 **SQLite 인덱스 파일 바이트 자체 SHA + SHA chain head**를 `capture_receipt.json`에 고정한다. 리런 시 기존 원시 피처/score/witness와 전체 census를 다시 읽기 검증하고 `ALREADY_CAPTURED_FIRST_NATIVE_TOPK_RESEARCH_ONLY`로 **신규 기록 0**; 일부 파일·원장/score 변경, 같은 모델을 새 plan/K/label로 바꾼 재등록, 인덱스 끝 바이트 위변조도 fail-closed. 최초 기록 중 crash가 나서 루트/영수증이 일부만 남으면 **미래에 소급 복구/자동 재기록하지 않고** 명시적 오류로 보류한다.
- 최초 lock은 고정 모델 slot의 `.capture_<market>_<model_sha>.lock`에 `flock`; 같은 slot 동시 실행은 `SKIPPED_CONCURRENT_NATIVE_CAPTURE`(성공 아님), 삭제된 원래 동결 파일과 락만 남은 상태는 완전 초기상태로 재해석하지 않는다. 로컬 OS/파일 3개를 동시에 임의 재작성하는 고권한 위조, 외부 발행인/시계의 독립 공증은 탐지하지 못한다. **각 first source 파일은 GitHub 미업로드 `output/` 아래** 유지되고 외부 공개/실전 매매로 승격되지 않는다. 감사에는 정확한 원본 source 경로가 필요하므로 raw/native/feature 전체 파일의 영구 SHA ZIP 자동 보관은 아직 별도 작업이다.

## 사전 정의 plan 계약

입력은 **처음 결과를 보거나 처음 Freeze를 수행하기 전에** 작성해야 한다. 아래의 로컬 절대 경로는 형식 예이며 **실제 설치된 원천이나 공인 데이터라고 주장하는 것이 아니다**.

```json
{
  "schema_version": "eraleader.native_first_capture_plan.v1",
  "cohort_id": "KR_20261012_MODEL_A",
  "market": "KR",
  "model_version": "my_first_native_model_v1",
  "score_ledger": "/Volumes/T5DATA/eraleader/output/native/score.sqlite",
  "watch_ledger": "/Volumes/T5DATA/eraleader/output/native/watch.sqlite",
  "features_dir": "/Volumes/T5DATA/eraleader/output/native/features",
  "label_definition_file": "/Volumes/T5DATA/eraleader/output/native/pinned_leader_rule.json",
  "label_definition_sha256": "<64자리, 규칙 파일 전체 원본 바이트 SHA256>",
  "label_definition_id": "PREDECLARED_LEADER_180D_V1",
  "horizon_days": 180,
  "top_k": 3,
  "max_age_hours": 24
}
```

```bash
cd /Volumes/T5DATA/eraleader

# 수동으로 WATCH/score/criterion이 사전에 준비된 모델의 최초등록.
python3 scripts/capture_native_first_topk.py \
  --plan /Volumes/T5DATA/eraleader/output/native/my_first_plan.json \
  --capture-root /Volumes/T5DATA/eraleader/output/native_first_captures

# 기존 예약 배치 종료 후 opt-in 최초 동결·등록; 같은 옵션을 두 번 주면 KR+US 둘 다.
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader \
  --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
  --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/us_first_plan.json
```

예약 연결은 기존 `run_local_scheduled.py` 기본 옵션을 바꾸지 않는다. explicit `--native-first-capture-plan`이 없으면 캡처·추가 검사·파일 생성 0. 입력 예비 WATCH가 부족하면 안전 WAIT. 두 시장의 코호트는 서로 다른 시장/model slot; 중복 plan은 거부하고 두 번째 시장 오류가 나면 "두 시장 완료"를 출력하지 않는다. 기존 정상 예약 배치가 원천 부족 때문에 실패할 경우 원래 예외를 덮지 않으면서 선택된 첫 동결을 **독립 시도**한다. `--generate-plist`와 함께 사용할 수 없어 macOS 설치 LaunchAgent는 수정하지 않는다. **자동 예약 자체의 활성화/설치는 하지 않았고**, 이미 실행되는 스케줄러의 명시 옵션을 통해서만 사용 가능하다.

## 실측 검증과 분명한 한계

- `tests/test_native_first_capture.py`, `tests/test_scheduled_native_first_capture.py`: KR/US first-WATCH 전체 점수 확보→원래 freeze+strict native census 등록, 원래 TOP-K/성공기준/원본 증빙 일치, 아직 WATCH/점수 없으면 WAIT, 점수 일부만 있는 상황에서 이익 선택 금지, 원본 데이터/첫 계획/라벨 SHA 위조·점수 formula·source timestamps·초기 결과파일 조기 생성·SQLite 인덱스 바이트 변조/복구, O_EXCL/partial crash·시장+모델 중복 replay, 실제 CLI 노후 데이터 소급 봉인 거부, 기본 scheduler 회귀, 다중 KR/US 자동 실행/실패 노출, 실전 전송/공식 리더 승격 0 검증.
- **실제 Mac 현재 OS 시각 synthetic end-to-end**: `output/verification_logs/native_first_capture_os_e2e.py` (ignored)에서 KR/US 각각 **사전 원문 leader rule·plan 생성 → 최초 WATCH 전 WAIT → native 점수 전 WAIT → 최초 WATCH2+4-factor score2 local first write → CLI capture K1 → 같은 CLI 두 번째 실행 중복0 → 기존 strict `audit_prospective_due_followups`에서 미래 성숙 전 unknown1** 완료. 실제 OS clock가 기록됐지만 공급자는 전부 합성이고 실전 종목이 없다. 값과 소스 SHA 전후 불변, 외부 API0/실전 알림0/공식 leader0.
- 원본 영수증·원시 소스는 output Git ignored. 최초 암호화 보존/복구와 **전향적 실제 시장 후보가 자연스럽게 향후 1~12개월 성숙한 뒤 공인 독립 원천으로 검증하는 작업**은 남아 있다. 서로 다른 신규 model_version을 무분별하게 생성하면 실험 선택편향 문제가 있으므로 모델 버전 사전 관리와 모든 코호트 전수 평가가 필수. 로컬 SHA/시계/자체 선언 발행자만으로 공인 거래소 전시장 PIT나 진짜 시대의 대장주 예측 정확도를 주장하면 안 된다. D-017 외부 API 마지막, D-021 실제 T5DATA SSD 탈착·재연결·재부팅 마지막.
