# EraLeader 5_5 — 동결한 교체 후보 쌍의 미래 라벨 원천 문서·시점 대조

> 2026-10-11. **오프라인 자기선언 JSON의 바이트와 시각·라벨 내용 정합성만 검사합니다.** 서로 다른 claimed source ID, 로컬 SHA256, 게시/수집시각은 실제 발행자 진위·독립 PIT·성숙된 실전 미래 대장주 성공을 입증하지 않습니다.

## 정확히 해결한 단절

기존 `rotation_holdout.py`는 2개 WATCH 후보(기존 약화·신규 유망)의 두 관찰일 점수 차이를 사전에 봉인하고, 나중에 별도 결과라벨을 받아 양쪽 모두 만기·게시됐을 때만 **연구용 교체 성공/미성공**을 분류합니다. 반면 `outcome_source_claims.py`는 기존 단일 WATCH 후보 `eraleader.holdout.v1`에 귀속되어 있어 신규 쌍 `eraleader.rotation_pair_holdout.v1` 원천을 대조할 수 없었습니다. 로컬 제공자가 임의로 작성한 `labels.json`이 있을 때 증빙 파일 없이 교체 성공이 기록되는 연구 오인 가능성이 있었습니다.

신규 `src/eraleader/rotation_pair_source_claims.py`는 이미 검증된 `audit_rotation_pair_outcomes`를 **그대로 재사용**하고, 두 종목 각각의 정규화된 미래 라벨 원문을 별도 파일로 제출받아 교차 점검합니다. 기존 독립된 연구용 평가기/첫 WATCH 원장/점수 원장과 동결 내용은 변경하지 않습니다.

## 제출 계약

- **봉인 파일**: 기존 `freeze-rotation-pairs`가 만든 변경 불가능 연구용 JSON, `content_sha256` 및 종목쌍 `pair_id`.
- **사후 결과**: 기존 `audit-rotation-pair-outcomes` 입력 `labels.json`, 선언된 `security_id`, `label_definition_id`, `is_future_leader`, `mature_at`, `outcome_available_at`, 양성일 때만 `leader_start_at`.
- **원천 증거 manifest**: `eraleader.rotation_pair_label_receipts.v1` 객체. 필수 `schema_version`, `market`, `label_definition_id`, `rotation_freeze_sha256`, `outcomes_sha256`, `claims`. `claims[]`의 각 항목은 기업 ID, 자기선언 `source_id` / `publisher_id_claimed`, 같은 디렉터리 `file` 안전 .json basename, 실제 바이트 SHA256 `sha256`, 시간대가 있는 `published_at`, `retrieved_at`.
- **원천 문서**: 각 종목마다 `eraleader.outcome_label_evidence.v1` 스키마의 정규화된 JSON 원문. `schema_version`과 위에서 지정한 label 필드만 허용. 원본과 선언된 라벨의 기업 ID/정의/양음/성숙·이용가능시각/양성 개시시각을 **UTC 동등 시각으로** 대조합니다. 다른 회사 결과가 hash만 맞는 상태로 승인되지 않습니다. 원본 문서는 Git 및 파생 ZIP에 미포함.

## Fail-closed 결과 판정

1. 원천 manifest의 `rotation_freeze_sha256` 및 `outcomes_sha256`가 각각 동결/결과 실제 바이트와 다르면 즉시 오류. 다른 KR/US 시장이나 다른 label definition 불허.
2. 자체 원천 문서가 없어도 봉인 자체와 결과라벨 감사는 바뀌지 않습니다. 기존 `audit_rotation_pair_outcomes`의 full market-local horizon, 후행 게시, 조기 부정, 동결 전 이미 알고 있던 긍정 개시시점 게이트를 통과하지 못한 쌍은 **`PAIR_OUTCOME_NOT_EVALUABLE`**. 원천 주장만으로 미성숙 결과를 승인하지 않습니다.
3. 기존 쌍의 양쪽 라벨이 모두 평가가능한 경우에만 **양쪽 원문이 모두 필요**합니다. 하나라도 빠짐/해시 불일치/원문 안에서 다른 ID나 양음·날짜 주장, 시각 역전/후행 수집이면 `CENSORED_MISSING_OR_CONFLICTING_PAIR_SOURCE`, `locally_source_corroborated_pairs` 증가 **금지**. 이를 가짜 negative/false discovery로 계산하지 않습니다.
4. 날짜 흐름: `mature_at ≤ published_at ≤ outcome_available_at ≤ retrieved_at ≤ evaluated_at`, `retrieved_at ≥ published_at`. 이 검사는 **manifest에 적힌 시각**의 내부 정합성일 뿐 실제 외부 발행·취득시각 공증이 아닙니다.
5. manifest/source 문서의 중복 JSON 키, 경로 순회·숨김파일, symlink, 고용량·빈 원본, 부정확한 SHA, 중복/미등록 후보 ID, 허용 외 필드는 차단. 연구 API는 보안 오류를 실패라고 기록하지 않고 예외 또는 blocker를 출력합니다.
6. 모든 로컬 자료가 맞더라도 결과 `LOCAL_TWO_OUTCOME_DOCUMENT_CLAIMS_MATCH_NOT_AUTHENTICATED`, `locally_source_corroborated_research_confirmations`은 **자기선언 데이터의 일치 건수**에 불과합니다. `publisher_independently_authenticated=false`, `source_retrieval_time_independently_attested=false`, `historic_pit_certified=false`, `actual_leader_replacement_certified=false`, `official_leader_replacements=0` 불변.

누락·미성숙 결과 때문에 로컬 문서 정합성이 하나도 확보되지 않으면 `research_pair_confirmation_fraction_locally_corroborated=null` 처리해 실제 관찰실패 0%라는 오해를 방지합니다.

## 실제 CLI 사용

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader audit-rotation-pair-sources \
  --freeze-file output/research/frozen_rotation_pair.json \
  --outcomes output/research/later_declared_labels.json \
  --receipt-manifest output/research/claim_documents/manifest.json \
  --evaluated-at '2026-10-11T11:00:00+09:00' \
  --out output/research/rotation_pair_source_derived

# 결과: output/research/rotation_pair_source_derived/rotation_pair_source_claims_research.json
PYTHONPATH=src python3 -m pytest tests/test_rotation_pair_source_claims.py \
  tests/test_rotation_holdout.py tests/test_outcome_source_claims.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

평가시각은 현재 OS의 실제 시간 이후로 지정할 수 없습니다. **현재 성숙된 공식 교체 후보 성과 라벨은 없으므로**, 위 CLI 예시를 실행하려면 당시 별도로 제출되고 시점이 맞는 자체 실험 자료가 있어야 합니다. 실제 검증은 모두 인위적 합성 fixture/주입 시계로 실행한 것이며 2026년 실전 대장주 발견의 증거가 아닙니다.

파생 `rotation_pair_source_claims_research.json` 한 파일만 `local_backup.py` ZIP 허용 목록에 추가. 원래 동결 파일, labels JSON, 원문 증빙 문서, 시세·재무·개인키는 공개 Git과 연구 파생 ZIP에서 제외합니다.

## 실제 미완료

현재 법적 기업 ID·산업분류·상장/상폐·기업행동·현금정산을 공식 PIT 원문과 독립 확인하지 못했습니다. 실전 **전향적** 발견 후보와 실제 성숙된 결과/전수 모집단/독립 발행시각 서명, 정밀도·오탐률·리드타임도 미인증입니다. D-017 API는 로컬 개발 이후, D-021 물리 SSD 분리/재연결·Mac 재부팅은 API 연결 후 최종 검수에만. 전체 30개 최종 실전 완성 선언 금지.
