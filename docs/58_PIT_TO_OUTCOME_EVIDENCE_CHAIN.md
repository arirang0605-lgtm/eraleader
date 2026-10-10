# EraLeader 2_2/2_5/5_5 — 시장 PIT 근거부터 동결 성과까지 단일 대조

> 2026-10-10 KST, 로컬 SSD 실제 코드·CLI. **공식 출처·진짜 PIT·주도주 예측 정확도를 인증하는 기능이 아니라, 서로 다른 감사 결과를 연결해 미완료 근거를 막는 연구용 통합 게이트다.**

## 왜 필요한가

지금까지 각자 동작하던 (1) 원천 데이터 빈티지, (2) 회사 영구ID·기업행동, (3) 거래소 캘린더, (4) 가격 연속성, (5) 당시 상장종목군-가격 대조, (6) 후보 동결/평가기간, (7) 미래 성과 라벨 원문 해시·발표/취득시각을 **한 화면의 한 판단 흐름**으로 연결하지 않았다. 특히 후보를 등록한 **이후** 생성한 자료를 당시 신호의 PIT 근거로 잘못 연결하거나, 미래 라벨 1건이 없어도 나머지가 맞으면 완성됐다고 보고할 수 있다.

## 구현 및 실행 계약

`src/eraleader/pit_chain.py` → `audit_pit_to_outcome_chain`. CLI:

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader audit-pit-chain \
  --market KR \
  --decision-at '2026-04-02T16:00:00+09:00' \
  --evaluated-at '2026-10-10T17:00:00+09:00' \
  --report-dir output/pit_chain_trial_20261010/audits/existing_reports \
  --freeze-file output/pit_chain_trial_20261010/labels/holdout_manifest.json \
  --outcomes output/pit_chain_trial_20261010/labels/labels.json \
  --receipt-manifest output/pit_chain_trial_20261010/labels/claims.json \
  --out output/pit_chain_trial_20261010/derived
```

- `evaluate_local_evidence`: KR/US 해당 시장과 동일 판단시각의 5개 **기존 파생 감사 JSON**만 사용. 누락·후행 다운로드·티커 충돌·상폐정산 미증빙·주봉/일봉·종목군 불일치 등의 차단 사유와 SHA256를 전달한다. 각 감사의 자체 "완전" 주장은 공급자 인증이 아니다.
- `frozen_holdout`: 사전 동결된 KR/US 시장, 모델버전, 라벨 정의ID, 평가기간, 등록일 및 동결 원본 content SHA 검증. **시장 입력 감사 cutoff가 그 후보의 실제 등록시각보다 늦거나 동결 이후라면** 합성 실험이라도 근거 시점 모순으로 차단한다.
- `reconcile_holdout_outcomes`: 후보 만기와 라벨 성숙/공개 시각, 미성숙 음성 검열. 라벨 파일을 생략할 수 있지만 그러면 `SOURCE_LABEL_RECEIPTS_NOT_PROVIDED`와 미확인 대상 차단이 남는다. 라벨을 제공할 때는 receipt manifest까지 **동시에** 필수.
- `audit_outcome_source_claims`: 제공된 라벨의 원문 SHA와 자기선언된 소스 발행·취득 시각 재검사. 변조/누락/후행 수집은 차단 사유로 통합한다. 소스 라벨 SHA와 동결 hash, 모델·label-definition도 서로 맞아야 한다.
- 산출 `pit_chain_{kr,us}_research.json`: 원본 회사/시세/성과 내용은 포함하지 않고 각 영역별 감사 SHA, 동결 hash, outcome hash, blocker code 및 동결/성숙/원문 근거 숫자만 저장한다. 파생 JSON만 `backup-local` 허용 목록에 포함.
- **모든 5개 감사를 통과하고 전 라벨 근거가 내부적으로 일치해도** `publisher_independently_authenticated=false`, `source_availability_independently_attested=false`, `historic_universe_pit_certified=false`, `independent_outcome_labels_certified=false`, `leader_prediction_accuracy_certified=false`, `official_leader_promotions=0`이다. 자체 해시·자체 시각의 일관성은 공식 거래소 원천 또는 실전 예측 적중률이 아니다.

## 실제 테스트와 오프라인 CLI

```bash
PYTHONPATH=src python3 -m pytest tests/test_pit_chain.py \
  tests/test_evidence_gate.py tests/test_outcome_source_claims.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

`tests/test_pit_chain.py`는 12개 합성 회귀(조건별 각 시장 감사, missing source/label, 후보등록 이후 source cutoff, 반대 시장 연결, 기업ID 충돌, 성과 원문 변조, 동결 이후 의사결정, 라벨/receipt 일부 누락, 2027 synthetic 전 라벨 자체 문서 일치 시에도 인증 false, CLI/derived ZIP)로 구성됐다.

- **합성** 시장 감사 보고 5개를 사용한 경우: 만기 봉인 후보 4개, 라벨 3개만 내부적으로 이용 가능, 근거 문서 3개 일치, 라벨 1개 미래 이용 → `blocker_count=1`, **official 0/PIT certified false**.
- **실제 SSD에 남아 있는 과거 한국 가격 연속성 파생 보고 1개**만 사용한 별도 실제 CLI: 감사 파일 1/5, 원천 누락 4개와 관측일 불일치 및 미해결 가격 관측, 라벨 미제공 → `blocker_count=8`, 미래 대장주 확정 불허.
- `output/continuous/pit_chain_research_verified_20261010.zip`: 연구 요약 JSON 한 개만 SHA 검증·새 폴더 복원, 원본 유료 시세/문서/성과 라벨 저장 안함.
- 전체 **458개 기존 테스트 + 12개 신규**와 실제 Git 보안 검증 결과는 `PROJECT_STATE.md`의 최신 체크포인트에서 확인.

## 제한·향후

이 체계는 **독립 공급자 공증을 대체하지 않는다**. 원본 법적 식별자, 상장·상폐 포함 역사적 종목군, 상폐 현금 정산, 기업행동/배당 및 재무/산업 원천 공시, 독립 수집시각, 실전 미래 동결 후보와 성숙된 결과가 필요하다. 사용자 D-017: API 연결은 오프라인 개발 후. 사용자 D-021: 실제 물리 SSD 분리/재연결·맥북 재부팅 시험은 **API 연결 완료 후 최종 검증 단계로만** 수행한다.
