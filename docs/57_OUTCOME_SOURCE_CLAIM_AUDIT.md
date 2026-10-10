# EraLeader 2_5 / 5_5 — 동결 후보 성과 라벨 원천 파일·시각 주장 감사

> 2026-10-10 KST, 오프라인 코드 경로. **원본 파일 SHA256/시각 주장에 대한 정합성 점검만 수행하며, 출처 신원 또는 실제 미래 대장주 성과를 인증하지 않는다.**

## 추가한 기능

기존 `reconcile-holdout-outcomes`는 동결된 모델·후보·평가기간과 별도 미래 라벨의 성숙일·이용가능일을 대조했지만 **그 라벨을 뒷받침하는 로컬 원문 파일이 실제로 존재하고 해시가 맞는지**까지는 검사하지 않았다. 새 `src/eraleader/outcome_source_claims.py`는 파일과 자기선언된 문서 발행·수집시각을 대조해 누락·시점 모순을 명시적인 미해결 근거로 출력한다.

- `audit-outcome-source-claims --freeze-file <holdout_manifest.json> --outcomes <unverified_labels.json> --receipt-manifest <claims.json> --evaluated-at '<TZ ISO>' --out <dir>`
- `claims.json` 형식 `eraleader.outcome_evidence_claims.v1`. 상위 키 `schema_version`, `market`, `label_definition_id`, `frozen_manifest_sha256`, `outcomes_sha256`, `claims`. `claims[]` 각 항목은 `security_id`, `publisher_id_claimed`, `source_id`, `file`(동일 폴더 안의 안전한 .json basename), `sha256`, `published_at`, `retrieved_at`(모두 UTC 오프셋이 붙은 ISO 시각).
- **먼저 기존 동결 검증 및 라벨 성숙/공개 대조 재사용**. 이 단계에서 full-horizon 음성 라벨과 출처 시각, 서로 다른 모델/label-definition ID, 추가된 미등록 라벨, 중복 결과 ID 등을 검증한다. 기존에 미성숙하거나 cutoff 이후 이용 가능한 결과 라벨은 원천 문서 SHA가 정확하더라도 성과 인정 대상이 아니다.
- 내부적으로 평가 가능한 라벨별로 실제 원천 JSON 파일을 열어 SHA256을 계산하고 제출된 해시와 비교한다. 문서 발행일이 라벨 성숙일보다 이르면 `SOURCE_PUBLISHED_BEFORE_LABEL_MATURITY`, 라벨의 자기선언 이용 가능일보다 문서 발행이 늦으면 `LABEL_AVAILABLE_BEFORE_CLAIMED_PUBLICATION`, 수집 시각이 발행 시각보다 빠르면 `SOURCE_RETRIEVED_BEFORE_PUBLICATION`, 수집이 평가 cutoff 이후라면 `SOURCE_RETRIEVED_AFTER_EVALUATION`으로 명시. 파일 누락, symlink, 비정상 경로, 과대 파일, SHA 불일치도 차단·표기.
- 원천이 부족하면 `MISSING_OUTCOME_SOURCE_RECEIPT`로 기록한다. **이것을 잘못된 투자 실패 음성 라벨로 대체하지 않는다.** 다른 종목의 근거를 섞거나 발표·수집을 과거로 소급한 척하는 흔한 PIT 오류를 예방한다.
- 파일 존재·SHA·자기선언 날짜가 일치해도 `independently_source_authenticated=false`, `historical_universe_pit_certified=false`, `actual_leader_prediction_certified=false`, `official_leader_promotions=0`이 **불변**이다. 공격자가 출처 문서·manifest·수집시각을 함께 임의 작성했다면 이 로컬 감사만으로 식별할 수 없다. 원천 공급자·실제 시각에 대한 외부 검증은 향후 API/공식 공시 연동 단계에서 진행.
- 결과 `outcome_source_claims_research.json`만 기존 `backup-local` 안전 허용 목록에 추가하며 사용자 제공 원문 JSON/성과 라벨을 ZIP/Git에 포함하지 않는다.

## 재현 및 실제 테스트

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_outcome_source_claims.py \
  tests/test_holdout_outcome_reconcile.py tests/test_frozen_holdout.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

신규 `tests/test_outcome_source_claims.py`의 합성 테스트는 3개 문서 해시 정합성·날짜 비교, 문서 SHA 변경, 원천 근거 누락, 발행/수집 시각 충돌 4종, 중복/미등록 ID, 경로 순회/숨김 파일 거부, 소스 symlink/receipt symlink, 너무 이른 부정 라벨이 문서로 인증되는 오류 차단, CLI 및 파생 JSON SHA256 백업·복원을 포함한다.

**합성 연구 입력**: 2026년 4월 등록된 가짜 동결 후보 4개·180일 평가기간, 별도 합성 라벨 4개 중 시점상 내부 평가 가능한 3개(A/B/C), 미래 이용 가능 1개(D). 합성 공급자의 3개 JSON 증거를 작성해 SHA/자기선언 시간을 점검한다. 통과하는 문서가 있어도 **공식적으로 확인된 실전 대장주 0건**이며 외부 API·실제 메시지 발송 없음.

## 미완료

독립적으로 검증된 기업 ID·상장/상폐 종목군, 현금 정산·액면분할·배당 및 조정수익, 공시 발행자 서명/원시 timestamp, 실제 전향적 후보 등록 후 성숙한 미래 outcome이 필요하다. 이에 앞서 로컬 문서의 해시만으로 평가 성과를 인증하지 않음. 사용자 확정 D-021에 따라 물리적 SSD 분리·재연결/재부팅 시험은 외부 API 연결 후 최종 단계에서만 실시.

## 2026-10-11 — 5_5 결과 원천 감사의 음성 만기 시각/DST 게이트

기존 `audit_outcome_source_claims`는 봉인된 WATCH 최초 등록의 **현지 날짜+horizon**만 비교하여 종료 당일 **1분 전** 성숙한 음성 라벨도 `RESEARCH_LABEL_AVAILABLE_SOURCE_UNVERIFIED`로 분류했다. 이미 고친 `reconcile_holdout_outcomes`는 이 음성을 `PREMATURE_NEGATIVE_LABEL`로 보류하므로 동일 라벨의 두 모듈 결과가 불일치했고, 원천 claim PASS 수가 실제 내부 평가 가능 건수보다 커질 수 있었다.

이 감사도 `recorded_at_utc`의 **KR/US 거래소 현지 시각**에 고정 `horizon_days` 달력일을 더한 뒤 UTC 절대시각으로 검사한다. 결과 라벨 공개/인용 문서 SHA 검증은 바꾸지 않는다. KR 180일 종료 16:59(보류), 17:00(가능), 17:01(가능) 및 US 2026년 3월 EST→EDT 10일 만기 15:59(보류), 16:00·16:01(가능) 등 **6개 신규 합성 회귀**. 수정 전 KR 16:59가 FAIL인 실제 결함을 재현하고 수정 후 원천 감사·기존 홀드아웃 평가기 수치 일치 확인. 이는 로컬 모의 원천의 시각 내부 일치성이지 실제 발굴 성과, 독립 공급자 공증 또는 상폐/기업행동 인증이 아니다. 외부 API/D-021 SSD 물리 시험은 마지막으로 연기.
