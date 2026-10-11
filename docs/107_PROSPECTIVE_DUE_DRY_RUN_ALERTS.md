# EraLeader 5_5 · 6_5 — 전향 Top-K 만기 후 증빙 누락 DRY-RUN 운영 알림

> 2026-10-12 KST. 5_5 최초 등록 코호트의 만기일/결과자료 후속점검(`docs/106`)을 6_5 로컬 예약 실행의 **선택형, 외부 미전송 경고**에 연결. 이 기능은 실전 대장주 정확도, 독립 기관/공시 출처 또는 시간 공증이 아니다. D-017 외부 API 및 D-021 SSD 물리 탈착/재연결·재부팅은 최종 단계까지 연기.

## 개발 목적과 기존 모듈 보존

기존 `prospective_due_followups.py`는 전체 first-write 코호트의 원래 K를 보존하고, 만기 후 `outcomes` 또는 `receipts`가 없는 곳을 정확히 집계한다. 단, 사용자가 매번 수동 실행해야 해서 만기 경과·중간 서류 보강·원시 증빙 SHA 이상을 놓치기 쉬웠다. 이번 개발은 기존 실 동결·native score·원본 PIT·ranked precision/labels·MarketOS/타 프로젝트와 현재 설치된 launchd를 전혀 변경하지 않는다.

## 실제 추가 기능

- 신규 `src/eraleader/prospective_due_alerts.py`: `run_prospective_due_alerts(project,registry_dir,native_config=None,clock=None)`로 **엄격한 indexed census + 원래 native marker 필수 계약을 통과한 후에만** 정상 관측 이벤트를 만든다. 봉인 인덱스/원본 outcome/label SHA를 현재 시점에 두 차례 확인. 결측/상폐·미공인 자료는 `unknown/censored` 그대로 유지.
- `prospective_due_followups.py`에 SHA `due_evidence_state_sha256`를 **전체 만기 후 검열 코호트** 기준으로 계산. 각 `cohort_ref`, 누락·검열 상태, 최초 K와 미확인 K의 canonical hash이며, 화면의 최대 500개 노출 제한, 로컬 시각의 매번 변하는 만기 경과 일수를 포함하지 않는다. 전체 K와 코호트 수가 같아도 **500개 이후 숨은 증빙 상태 변화**까지 감지한다.
- 독립 `output/prospective_due_alerts/`에 추가 전용 `prospective_due_alerts.sqlite`, O_EXCL `prospective_due_alerts_genesis.json`, 불변 event number/서로 연결된 SHA·UTC 기록·원본 인덱스 확인 수/첫 SHA·원래 분모·검열 상태/미발송 0 확인, 파생 `prospective_due_alerts_research.json`, `site/index.html`. 기존 시장 원장, 공급자/가격 원본·native score·후행 라벨 원본 쓰기 0. 최초 등록 인덱스가 나중에 **일관성 있는 과거 버전으로 롤백되거나 다른 등록원장으로 바뀌어도**, 이전 감시에서 확인한 receipt-count/head prefix가 같지 않으면 `SOURCE_AUDIT_BLOCKED`로 분류한다.
- 경고 종류 (로컬 미전송):
  - `PROSPECTIVE_DUE_EVIDENCE_GAP_LOCAL`: 만기가 지난 최초 코호트의 자료가 부족한 최초 관측
  - `PROSPECTIVE_DUE_EVIDENCE_CHANGED_LOCAL`: 동일 개수라도 누락 대상·쌍 여부·검열 정도가 달라짐
  - `PROSPECTIVE_DUE_EVIDENCE_CLEARED_LOCAL`: **해당 first-write 원장 SHA/PIT 연구 감사를 통과한 로컬 자료**에서 만기 결과검열 gap이 0으로 바뀜 (공식 대장주 성공 또는 모든 시장원천 완전성 아님)
  - `PROSPECTIVE_SOURCE_AUDIT_BLOCKED_LOCAL`: 원장 SHA, index, native 요구증거, label/source 문서 검증 등이 보류. 마지막 검증 숫자 보존, **현재 정확도·기록 정상이라고 주장 금지**
  - `PROSPECTIVE_SOURCE_AUDIT_RESTORED_LOCAL`: 보류 이후 같은 모니터링 루트에서 기존 verified prefix에 부합하는 로컬 자료를 다시 검사해 통과 (실제 공급자 신뢰·성과 인증 아님)
- 같은 시점/동일 원본 상태의 반복 실행은 신규 이벤트·미발송 경고 0. 새 첫 기록 원장이 증가할 때에는 기존 prefix SHA를 증분 검증하며, 만기 차이가 없더라도 새 인덱스 head를 기록. 첫 원장/모니터링 대상 폴더 결합 SHA는 자체 genesis와 DB meta에 기록해, 나중에 다른 registry/native config를 은밀히 가리키는 downgrade를 차단한다. 별도 오류 원장이 유실/부분 삭제/내용 조작됐으면 자동 재시작·복구하지 않는다.
- `src/eraleader/local_backup.py` 안전 allowlist에 파생 `prospective_due_alerts.sqlite`, genesis JSON, 보고 JSON만 추가. 기존 `site/*.html` 안전 규칙 재사용. 기존 `create_backup` 온라인 SQLite snapshot → ZIP MANIFEST SHA 검사 → 새 폴더 복원 4파생-only. 파생 내용에는 티커·원문 기업코드·회사명·원본 종목ID·원본 원천파일 경로 포함하지 않는다.

## 사용법 — 실제 CLI, 예약 실행 선택 옵션

```bash
cd /Volumes/T5DATA/eraleader

# 외부 API 및 스케줄러 없이 로컬 감시를 직접 실행
python3 scripts/run_prospective_due_alerts.py \
  --project /Volumes/T5DATA/eraleader \
  --registry-dir /Volumes/T5DATA/eraleader/output/your_cohort_registry

# 예약 연구 파이프라인 끝에 선택 연결(기존 stale-cache 보류 유지)
python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --prospective-due-registry /Volumes/T5DATA/eraleader/output/your_cohort_registry

# native 최초 score 증빙 필수로 등록했으면 두 명령에:
# --native-evidence-config /Volumes/T5DATA/eraleader/output/your_native_source_config.json
# 또는 예약 스크립트: --prospective-due-native-config 동일 경로
```

`--prospective-due-registry`가 없으면 기존 scheduler/알림/시장 검증 동작 변화 0. `--generate-plist`와 이 경고 옵션의 동시 사용은 금지하므로 설치된 macOS LaunchAgent는 변경되지 않는다. 기존 가격 스케줄이 신선도 때문에 실행을 거절해도 **원래 실패를 성공으로 덮지 않으면서** 본 증빙 추적은 독립적으로 시도하고 (감시 오류는 원래 예외에 note 기록), 성공 시에도 실제 전송 0을 강제한다. 다른 로컬 경고 옵션과 동시 사용 가능.

## 테스트/한계

- 신규 `tests/test_prospective_due_alerts.py`: first-write 미만기→만기 경계 경고, 반복 중복0, 결과서류 일부 추가 시 **같은 미확인 수에서 증빙 상태 변경**, partial/claim-censored를 실패0으로 속이지 않음, 모든 K=2 로컬 자료만 확인되면 gap 해소를 공식 대장주로 승격하지 않음, source/first-write index 삭제·변조·이전 버전 일관 롤백/출처 시각 변경 시 `SOURCE_AUDIT_BLOCKED`, 이후 로컬 복구와 기존 원장 SHA prefix, 출처·native config downgrade/다른 root 차단, 발송 위조/원장 시계역행·O_EXCL marker 삭제/조작·동시 잠금, 안전 ZIP 복원, 웹 XSS·기본 scheduler 불변/실패 전파 검증.
- 원본 `tests/test_prospective_due_followups.py`에서는 **500개 이상 중 UI에 보이지 않는 코호트의 검열 이유가 변경되더라도 전체 SHA가 바뀌는지** 검증 강화.
- 공개 GitHub 릴리스 전 테스트: `PYTHONPATH=src python3 -m pytest -q tests/test_prospective_due_alerts.py tests/test_prospective_due_followups.py tests/test_prospective_census_seal.py tests/test_local_backup.py --tb=short`, `PYTHONPATH=src python3 -m pytest tests -q --tb=short`, `python3 scripts/check_handoff.py`, `python3 scripts/check_git_safety.py`, `git diff --cached --check`.
- 한계: 수개월 미래 독립 원천 진위·상장폐지 cash settlement·공시 시점/본인 법적 신원·전체 종목군 PIT가 미인증이며, OS 시계와 원본/감시 원장을 **함께** 임의로 재작성하는 공격자는 단일 장비 SHA만으로 막을 수 없다. `SOURCE_AUDIT_BLOCKED` 숫자는 마지막 **로컬** 검증의 당시 참고값이며 현재 정상 판정이 아니다. 이벤트는 **외부 메일/텔레그램/Webhook/매수주문 어떤 형태로도 전송하지 않음**.
