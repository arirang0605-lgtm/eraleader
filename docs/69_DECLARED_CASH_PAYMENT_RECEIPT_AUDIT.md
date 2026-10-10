# EraLeader 2_2 / 2_5 — 현금 상폐 지급 증빙 원문·시간·금액 대조 (오프라인)

> 2026-10-11 KST. **이 기능은 로컬에 제출된 두 개의 자기선언 출처가 서로 일치하는지 검사하는 연구용 감사입니다.** 지급기관 실존성, 서명, 과거 수집시점, 전체 상장·상폐 모집단, 최종 투자수익은 독립 인증되지 않습니다. 공식 미래 대장주 확정 0건. 외부 API·스크래핑 0회.

## 추가된 기능과 이유

기존 `cash_exit_lineage.py`가 ① 결정 시점 발행인 기업 ID 빈티지, ② 평가 시점 기업 ID/행동 빈티지, ③ 미조정가격·분할·배당·현금 지급 계약을 결합하지만, *현금 지급이 실제로 발생했음을 주장하는 별도 문서 바이트*의 정합성은 확인하지 않았다. 기업/상폐 이력과 지급 계약을 제출자가 함께 임의로 생성해도 모두 일치할 수 있는 한계가 있었다.

새 `src/eraleader/cash_payment_receipts.py`의 `audit_declared_cash_payment_receipt`는 결제 증빙 manifest를 읽어 같은 폴더의 **정규화된 JSON 원문** SHA256과 실제 바이트 일치, 종목 영구 ID/국가/상폐 이벤트 ID/지급액/통화/거래종료일/효력일/지급시각/지급확인 여부, manifest가 주장하는 문서 발행·수집시각을 교차 확인한다. 자체 선언된 payout source ID가 가격 정산 계약의 source ID 또는 발행인 빈티지 source ID와 같으면 `RECEIPT_NOT_A_DISTINCT_DECLARED_SOURCE`로 보류한다. **다른 source ID를 적었다는 사실만으로 두 곳이 실제 독립 발행자였다는 증거는 절대 아니다.**

정합성이 통과한 문서가 있어도 `cash_payment_independently_authenticated=false`, `retrieval_timestamp_independently_attested=false`, `historical_universe_pit_certified=false`. SHA는 오직 제공된 파일이 함께 제출된 manifest와 일치함만 보증하며, 원본 파일과 해시를 함께 조작한 경우 검출할 수 없다.

## 입력 파일 두 종류 (선언된 자료만)

1. `eraleader.cash_payment_receipt.v1` manifest: `schema_version`, `market`(KR/US), `security_id`, `source_id_claimed`, `publisher_id_claimed`, `file` (동일 폴더 안전 JSON basename만), `sha256` (원문 파일 바이트 해시), `published_at`, `retrieved_at` (TZ 포함).
2. `eraleader.cash_payment_document.v1` 정규화 원문: `schema_version`, `source_id`, `market`, `security_id`, `event_id`, `action_type=cash_delist`, `last_trading_on`, `effective_on`, `cash_per_share`, `currency`, `paid_at`, `cash_payment_confirmed=true`.

문서·manifest의 임의 JSON 키 중복은 거부한다. 파일 symlink, 디렉터리 탈출, 누락/빈 파일, 과대 파일, 해시 불일치 및 NaN/boolean 현금액을 거부한다. `paid_at <= published_at <= retrieved_at <= evaluated_at` 및 `settlement.available_at <= retrieved_at`을 요청 시점·문서 내용과 대조하며 KR/US UTC offset/DST에 안전하게 비교한다.

## 기존 CLI 선택 확장

두 회사 계보를 제출했을 때만 아래 옵션을 허용한다. 기존 입력만 이용한 연구용 명령은 이전대로 동작하고, 엄격 모드는 문서 미제출도 수익률 `null`로 검열한다.

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader audit-cash-delist \
  --file output/cash_payment_receipt_trial_20261011/inputs/cash.json \
  --decision-lineage output/cash_payment_receipt_trial_20261011/inputs/decision_lineage.json \
  --evaluation-lineage output/cash_payment_receipt_trial_20261011/inputs/eval_lineage.json \
  --settlement-receipt output/cash_payment_receipt_trial_20261011/receipt/receipt_manifest.json \
  --require-settlement-receipt \
  --security-id SYN-CASH-EXIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-05-01T17:00:00+09:00' \
  --out output/cash_payment_receipt_trial_20261011/derived

PYTHONPATH=src python3 -m pytest tests/test_cash_payment_receipts.py tests/test_cash_exit_lineage.py tests/test_cash_exit_amount_claims.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

기존 standalone `python3 -m eraleader.cash_exit_lineage`에도 `--settlement-receipt`와 `--require-settlement-receipt` 제공. 연구 JSON 반환 상태 `LOCAL_DUAL_VINTAGE_CASH_EXIT_RESEARCH_NOT_CERTIFIED` 또는 `CENSORED_UNCORROBORATED_CASH_EXIT`; 증빙 누락·시간 역전·금액 불일치일 때 `blocking_reasons[]`와 `cash_exit_total_return=null` 확인. 파생 출력엔 원문 JSON, raw 가격, 개인키를 기록하지 않으며 지급 문서/manifest 원본은 ZIP/Git에 넣지 않는다.

## 실험과 한계

합성 KR 현금지급일 2024-04-15 / 문서 게시 2024-04-16 / 취득 2024-04-17, 기업 ID/상폐/분할 경로는 합성 fixture. 미국 DST를 포함한 별도 미국 예시도 사용. 공식 발행기관·실제 법적 상폐 정산 대가·과거 공시 원문 빈티지에 대한 독립 인증은 추후 데이터 API 공급자 선정 후 진행한다(D-017). 원본 SSD 분리·재연결 및 Mac 재부팅 테스트는 사용자 D-021대로 API 후 최종 검수.
