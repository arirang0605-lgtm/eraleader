# 98 — 5_3 / 5_5 최초 WATCH·native 점수 코호트와 전수평가 강제 연결

2026-10-11 KST. 목표는 이미 개발한 **첫 WATCH → 실제 네 요소 계산점수(first-write) → 처음 Top-K 동결**이 공식 전망 성과 평가의 로컬 후보 원장에 연결되지 않고, 일반적인 숫자 순위 JSON도 전향적 후보처럼 기입할 수 있는 연결 공백을 메우는 것. 기존 WATCH/점수 계산기, 기존 Top-K freeze, label/성과 평가, 인덱스와 기존 무옵션 명령은 보존한다.

## 신규 opt-in 기능

- 신규 `src/eraleader/native_census_gate.py`: `register_native_census` / `audit_native_census`. 기존 `ranked_maturity.audit_ranked_maturity`의 **전수 provenance 검증**(원래 WATCH와 screen 양성/첫 점수 숫자, 동일 모델/전 종목군 일치, 원본 피처 bytes·네 요소 재계산, first score 시각·고정 label 원문 SHA, native binding SHA)을 *재활용*한다. 새 공식이나 점수 기준을 만들어 과거 종목에 맞추지 않는다.
- 사용자 로컬 JSON `native_evidence_config.json`의 `schema_version="eraleader.native_census_proof_paths.v1"`, `cohorts[]` 각 원소는 `frozen_sha256`, `score_ledger`, `watch_ledger`, `features_dir` 정확히 4개 필드. 로컬 절대경로만 허용하고 symlink/누락·중복 SHA/추가·누락 코호트 거부. **등록 시 선언된 모든 동결 Top-K**, **평가 시 영수증 인덱스에 존재하는 모든 코호트**를 점검하며 Top-K 분모 축소 불허. 파일 경로·종목ID·원시 피처는 보고/ZIP/Git에 기록하지 않는다.
- `scripts/run_prospective_census.py register|audit --receipt-index --native-evidence-config ...` 명시 시에만 활성화. 등록 전 original WATCH + 수치점수 + 공식 provenance 전수 감사 → 기존 `indexed_register_census`의 O_EXCL + SQLite SHA chain 최초 등록 → 원본 native source를 재감사한다. 보존된 first-score와 해당 최초 WATCH의 결합이 깨지면 등록 보류. **일반 score-only ranked freeze는 `native_cohort_binding`이 없으므로 차단**.
- 신규 O_EXCL 모드 보존 파일 `<registry_dir>_native_required.json`을 최초 strict native 등록 **전에** 작성하며, 원문 고정 바이트 SHA를 매번 확인한다. 이 경로가 있으면 이후 CLI에서 `--native-evidence-config`를 생략해 약한 검증으로 되돌리는 것을 거부한다. 예전에 이미 등록된 *일반* census를 나중에 native 최초등록인 양 소급 인증할 수 없다. 멀티파일 등록 중 중단 시 orphan marker/registry가 남으면 자동 재시도·삭제하여 회복하지 않고 수동 근거 조사 대상으로 차단한다.
- 평가: 먼저 **기존 인덱스/원장 전수 감사** → 모든 frozen SHA와 native WATCH/score/feature 원본 전수 감사 → 같은 인덱스 감사 + native 원본 2차 재검증 → 강한 증거 일치 때만 `prospective_census_research.json` 파생 보고 작성. 없거나 수정된 원본 점수·피처·룰·인덱스·모드 marker, 합성 시장의 만기 전 미래 라벨, 미등록 코호트/중복은 fail-closed. 고정 K·unknown/known 성과 집계는 기존 로직을 그대로 이용한다.
- 출처 불변성은 **단일 Mac 로컬 SHA/원장**에 대한 증거로, 독립 KRX/DART/SEC 발행사 진위·공시 공개시각·전체 생존/상폐/분할·배당 PIT를 인증하지 않는다. 로컬 marker/인덱스/전부를 함께 삭제하는 공격이나 OS 시간 독립증명은 여전히 미해결. 실제 확정 대장주 0 / 실전 precision N/A / 외부 API 0.

## 사용 예시

```bash
cd /Volumes/T5DATA/eraleader

# 실제 첫 WATCH/first score native freeze 원본이 있는 경우에만:
# native_evidence_config.json:
# {"schema_version":"eraleader.native_census_proof_paths.v1",
#  "cohorts":[{"frozen_sha256":"<실제 SHA256>",
#              "score_ledger":"/absolute/local/native_scores.sqlite",
#              "watch_ledger":"/absolute/local/prospective.sqlite",
#              "features_dir":"/absolute/local/features"}]}

python3 scripts/run_prospective_census.py register \
  --spec output/live/census_input.json \
  --registry-dir output/live/first_write_registry \
  --name census_KR_first.json --receipt-index \
  --native-evidence-config output/live/native_evidence_config.json

python3 scripts/run_prospective_census.py audit \
  --registry-dir output/live/first_write_registry \
  --evaluated-at '2026-10-11T22:30:00+09:00' \
  --receipt-index --native-evidence-config output/live/native_evidence_config.json \
  --out output/live/derived
```

지금은 실제 시장 최초 코호트가 확보됐다는 주장이 아니므로 위 경로는 사용 예시. `--native-evidence-config`는 **`--receipt-index`와 같이** 요구되며 과거 이미 등록한 일반 코호트의 소급 승격은 금지.

## 실제 검증

- TDD 새 `tests/test_native_census_gate.py`에서 일반 순위 위장, 누락·여분 config, 코호트 전체 분모 KR/US, 피처·원본 WATCH/점수 SQLite 변조·삭제, 소급 upgrade, marker 삭제/링크/바이트 변조, 기존 CLI 검증 우회, 감사 중 source 변조를 합성 회귀로 확인.
- Mac OS 현시각 **synthetic** KR 최초 양성 WATCH2→계산된 실제 수치점수 2→native Top1 freeze→CLI O_EXCL + 최초 영수증/모드 pin→CLI 전체 감사(선정 분모1/unknown1/실전 precision N/A)→JSON-only ZIP SHA 검증 및 새 폴더 완전복원. 원래 원장/watch/score/feature SHA 변동 없음. 이후 feature 파일 실험적 변조 후 동일 strict audit exit2 및 새 보고서 미발행. **미래 성과·실전 대장주 확인이나 실전 데이터 API 검증은 수행하지 않음.**
- 전체 자동 테스트와 공개 Git 안전검사·커밋/푸시 결과는 `PROJECT_STATE.md` 마지막 체크포인트가 단일 기준.

## 다음 단계

2_2/2_5 공식 법적 issuer/share-class/과거 상장·상폐/현금지급/기업행동·최초 공개시각/정확한 전체 시장 종목군 PIT 독립 원본 인증, 5_5 진짜 사전 WATCH/Top-K에 대한 수개월 후 독립 미래 outcome(precision·오탐·lead days) 검증. D-017 외부 API와 D-021 SSD 물리 분리·재연결/맥 재부팅은 사용자 결정대로 최종까지 보류.

## 2026-10-11 macOS 로컬 최종 테스트 및 실제 실행 증거

- 신규 `tests/test_native_census_gate.py` **22/22 PASS**; 관련 기존 WATCH/native Top-K/최초 코호트/SQLite 영수증 포함 집중 **78/78 PASS**. 첫 구현 일반 랭킹 위장·미등록 cohort·피처/수치점수 원장 변조 차단. 추가 native-mode marker에 JSON 바이트 뒤 공백을 붙이면 파싱상 동일 JSON으로 통과하는 **실제 1 RED FAIL** 확인→expected 최초 원문 bytes 완전 대조로 수정해 GREEN.
- 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1499/1499 PASS(exit0)**(직전 1477 +22); `pytest --collect-only` 1499, `python3 scripts/check_handoff.py` 30 ID/40필수파일 PASS, `py_compile` PASS, `git diff --check` PASS. 전체 실행 로그는 Git ignored `output/verification_logs/native_census_full_20261011.txt`.
- 실제 Mac 현재 OS시각 synthetic KR: 원본 WATCH 양성2→실제 native 4요소 계산 첫점수 2→Top1 first-freeze/사전 label rule→`scripts/run_prospective_census.py register --receipt-index --native-evidence-config ...`→`audit ...` 성공. 원래 선정분모 1/unknown1, 실전 적중률 N/A·공식 대장주0/API0. 전용 JSON 파생 ZIP SHA 검증·새 경로 복원, 원본 WATCH·점수·feature·규칙 SHA 원래 그대로. 이어서 실험적 피처 훼손 시 CLI exit2·새 JSON 미발행(합성 원본 훼손 테스트는 ignored trial 내부에서만 수행).
- `--native-evidence-config` 없는 과거 일반 코호트 실행과 등록 기능은 유지하며 native-proof 검증 완료로 **표시하지 않음**. strict-native registry가 생성되면 별도 최초 marker로 CLI 약화 옵션을 거부. Git Public 업로드에는 native watch/score SQLite, feature 원문/개인 데이터/키/실제 결과 모두 포함하지 않는다.
