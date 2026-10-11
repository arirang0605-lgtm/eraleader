# EraLeader 5_3 / 5_5 — 전향적 WATCH 교체 후보 쌍 홀드아웃 동결 및 만기 결과 대조

> 2026-10-11 KST. 이 기능은 **로컬 사전 동결과 별도 제공된 미래 결과 주장 간의 내부 정합성**을 검증하는 오프라인 연구 모듈입니다. 실제 시대 대장주 교체 성과, 법적 기업동일성, 시장 구성 PIT, 공급자 진위 및 수익률은 어떠한 경우에도 인증하지 않습니다. 실전/증권 API 0회.

## 필요성, 기존 자산 보존

`peer_score_series.py`가 같은 산업의 WATCH 약화와 후발 후보 점수 우위 **최근 2개 현지 관찰일 모두 5점 이상**을 확인합니다. 기존 `frozen_holdout.py`는 **단일 양성 WATCH 최초 등록 종목**의 결과 성숙·발표를 감사합니다. 이 두 체계는 정상 동작하며 변경·재작성하지 않습니다. 그러나 기존 WATCH의 음성 변화와 신규 WATCH의 양성 변화가 결합된 *쌍 교체 가설*은 후일 특정 성공 사례를 골라 발표하거나 평가기간·두 원장의 회사 ID를 바꾸는 오류에 노출되어 있었습니다.

별도 `src/eraleader/rotation_holdout.py`에서 **동결 전(결과 미열람)**과 **동결 후(별도 성숙 라벨)**를 분리합니다. 기존 WATCH, `rank_score_events`, `peer_scores.sqlite`, frozen holdout 모듈, 원시 가격·현금 상폐·법적 기업 ID 모듈을 수정하지 않습니다. 시간대 계산·불변 JSON SHA/파일 exclusive-create는 검증된 공통 모듈을 재사용합니다.

## 동결 계약

`freeze_rotation_pairs(watch_db,score_db,feature_root,output,...,clock=None)`

- 기존 `audit_peer_score_advantage`를 사용해 점수 원본/관찰일/실제 등록시각/해시/업종과 WATCH 원본을 **read-only 전수 재검사**합니다. `locally_score_correlated=True`인 연구용 쌍만 포함하며 결과 전체가 1000 표본보다 클 때 임의 상위 일부만 골라 봉인하지 않고 오류 처리합니다.
- 주도주 진위 인증 없이 **첫 명시적 약화 뒤 신규 양성** 및 **최근 2 시장 현지 관찰일 기존·신규 점수 우위**를 포함. 각 날짜의 기존/신규 점수·SHA256와 *실제 로컬 최초 점수 등록시각*을 함께 봉인합니다. 두 스코어/업종·서로 다른 영구 기업 ID가 모호하거나 한 신규 후보가 다수의 서로 다른 기존 후보에 무분별하게 중복 연결되면 연구 코호트에서 제외합니다.
- 동결 시각은 실제 OS UTC(생산 CLI에는 임의 시각 옵션 없음). 가장 최근 점수 최초등록이 동결 시각 기준 **72시간 초과로 오래되면** 미래 예측을 했던 것처럼 소급 봉인할 수 없습니다. 이 72시간은 주말 포함 로컬 시간연결 규칙이자 검증 전 임시 기준이며, 투자 신호/성과 최적화 결과가 아닙니다.
- 평가기간은 **사전 명시** `horizon_days=1..1095`, 결과 정의도 `label_definition_id` 버전으로 동결. 새 파일에만 `O_EXCL`/fsync로 쓰고 이미 있는 봉인파일 덮어쓰기를 금지. 해시 `content_sha256` 및 각 쌍 `pair_id`는 이후 변경과 중복을 차단합니다. `outcome_labels_included=false`, `historic_pit_certified=false`, `official_leader_replacements=0` 고정.
- 적격 쌍이 하나도 없으면 0건을 임의 성과 코호트로 승인하지 않고 오류 반환합니다. 동결 파일에는 **미래 성과/원시 결과 라벨을 절대 포함하지 않습니다.** 해시는 로컬 제출자료 정합성이며 신뢰기관의 시간공증이 아닙니다.

## 만기 대조 계약

`audit_rotation_pair_outcomes(frozen_file,evaluated_at,outcome_file=None,...)`

- 먼저 *동결파일 원본*의 content SHA/정해진 필드/원래 행사 SHA/기록시간 및 cohort 수를 재검사합니다. 파일 symlink, 중복 JSON 키, 결과 라벨의 재해시 후 봉인 임계값/정의/기업ID 변경, 공식 인증 true 주장 시 오류.
- 고정 기간 만기는 **동결된 실제 시장 현지 시각**에 `horizon_days`를 더한 뒤 UTC로 비교합니다. `KR / US` 시간대 및 미국 DST 전환에서도 만기 1분 전은 미만기. 평가 cutoff가 실제 사용자의 OS 시간보다 미래면 차단.
- 별도 `labels.json`에는 양 기업 각각 `security_id, label_definition_id, is_future_leader, mature_at, outcome_available_at`와 양성일 때만 `leader_start_at`를 허용. 두 라벨 모두 동결 후 성숙·알려졌음을 주장해야 하며 `outcome_available_at >= mature_at`. 부정 결론은 **동결 시각+평가기간 전체**까지 만기여야 합니다. 양성 onset이 동결 당시 이미 알려질 수 있었거나 onset > label maturity면 결과 확정 불가.
- **두 기업의 성숙/게시 라벨이 모두 존재하고 평가기간 전체가 지나야만** `RESEARCH_PAIR_CONFIRMED_SOURCE_UNVERIFIED` 또는 `RESEARCH_PAIR_NOT_CONFIRMED_SOURCE_UNVERIFIED` 분류. 신규 후보의 기간 내 양성·기존 종목의 기간 전체 부정이 모두 주장될 때만 *내부 연구용* 교체 확인. 실제 일시·시장 완전성/label 출처의 객관적 진위는 **확인하지 못합니다**.
- 미제출·미게시·미성숙 음성·해당 후보로의 라벨 혼합을 실패로 대신 계산하지 않고 `HORIZON_PENDING`, `HORIZON_ELAPSED_NO_COMPLETE_LABELS`, `LABEL_NOT_YET_AVAILABLE`, `PREMATURE_NEGATIVE_LABEL`, `PREEXISTING_OR_UNRELIABLE_POSITIVE_ONSET`로 검열하고 분모 별도 유지. unmatched 제3기업 라벨은 성과에 포함하지 않음.
- `research_known_pair_confirmation_fraction` 및 `research_pair_confirmation_floor`는 **오직 나중에 자체 선언된 연구 라벨의 내부 산술**이며 실제 precision/false discovery/leader rotation accuracy가 아닙니다. 원본 라벨 배열과 특성/시세는 결과에 복사되지 않고 해시 및 요약만 남습니다. `independent_future_label_source_certified=false`, `historic_pit_certified=false`, `real_leader_replacement_certified=false`, `official_leader_replacements=0`은 모든 성공 케이스에서도 불변입니다.

## 기존 EraLeader CLI에 추가한 기능

~~~bash
cd /Volumes/T5DATA/eraleader

# 반드시 현대 시점의 최초 기록 WATCH/점수 데이터. CLI 임의 clock 설정 불가.
PYTHONPATH=src python3 -m eraleader freeze-rotation-pairs \
  --watch-ledger output/research/prospective.sqlite \
  --score-history output/research/peer_scores.sqlite \
  --feature-root output/research/peer_features_vault \
  --market KR --model-version local-screen-v1 \
  --label-definition-id 'rotation-protocol-v1' --horizon-days 180 \
  --freeze-file output/research/frozen_pair_cohorts/rotation_20261011.json

# 별도 성숙 결과가 없으면 --outcomes 생략: 만기 일정·미확인 상태만 기록
PYTHONPATH=src python3 -m eraleader audit-rotation-pair-outcomes \
  --freeze-file output/research/frozen_pair_cohorts/rotation_20261011.json \
  --evaluated-at '2027-04-11T11:00:00+09:00' \
  --out output/research/rotation_pair_outcomes_derived

# 실제 별도 원천 자료 연결 이후 --outcomes 추가하고 시점·정의 검증
PYTHONPATH=src python3 -m eraleader audit-rotation-pair-outcomes \
  --freeze-file output/research/frozen_pair_cohorts/rotation_20261011.json \
  --outcomes output/research/labels/later_independently_researched.json \
  --evaluated-at '2027-04-11T11:00:00+09:00' \
  --out output/research/rotation_pair_outcomes_derived_later
~~~

상단 명령의 2027년 날짜는 **미래 만기 이후 실행 양식의 예시일 뿐 지금 실행 가능한 날짜가 아닙니다**. 현재 테스트는 별도의 synthetic 2026-10-04 봉인·10-09 만기 **주입 시계**로 재현하며 실전 과거 예측이 아닙니다.

CLI 감사 결과 `rotation_pair_outcomes_research.json` **파생 요약만** `src/eraleader/local_backup.py` 안전 allowlist에 추가. 동결된 원본 manifest/원본 성숙 라벨/가격·특성 원문/증권 API 키는 파생 ZIP/Git에 제외합니다.

### 재검증

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_rotation_holdout.py tests/test_peer_score_series.py tests/test_frozen_holdout.py tests/test_holdout_outcome_reconcile.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

## NEXT

현재 전향적 실전 WATCH 교체 코호트와 향후 수개월 성숙될 실제 결과는 독립 검증되지 않았습니다. 5_5 추가 단계에서 국가별 공식 issuer/산업/기업행동·상폐를 포함하는 `2_2/2_5` PIT와 실제 매일 신규 봉인파일의 지속 기록, 별도 source receipt가 확인된 후에야 실제 조기 대장주 발견 성능/오탐률/리드타임을 측정할 수 있습니다. API D-017은 로컬 구현 완료 뒤, 실제 SSD 분리·재연결/재부팅 D-021은 API 연결 후 최종 단계에 진행. REWRITE/무근거 결과 인증 금지.
