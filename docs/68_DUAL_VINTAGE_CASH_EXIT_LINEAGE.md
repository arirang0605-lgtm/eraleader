# EraLeader 2_2·2_5 — 현금형 상폐: 기업 계보 이중 빈티지 PIT 대조

> 2026-10-11 KST. 오프라인 자체선언 자료만 사용. 실제 공급자 PIT/기업 ID/상폐 지급/미래 대장주 정확도는 절대로 인증하지 않는다. 외부 API/스크래핑 0회, CycleOS 원본 READ-ONLY.

## 해결하는 문제

기존 delist_cash.py는 명시적 원시 주가·분할·배당·현금 지급액에서 연구용 상폐 총수익을 재구성하고, issuer_lineage.py는 회사 영구ID·티커 재사용·기업행동을 감사한다. 두 모듈만 별도 실행하면 판단 당시 다른 기업이었던 티커를 사후 현금 정산금과 잘못 결합하거나, 분할/배당 누락과 늦게 입수한 상장종목군이 경로를 오염시킬 수 있다.

신규 src/eraleader/cash_exit_lineage.py는 기존 함수를 재사용해 **판단 시점 기업 빈티지, 정산 평가 시점 기업 빈티지, 현금형 상폐 원시가격 계약**의 세 입력을 독립적으로 로드하고 교차 대조한다. 자료가 부족하면 수익률을 0으로 만들지 않고 null로 검열한다.

## 입력·보안 계약

- 가격·행동·정산: 기존 cash_delist_research_v1, price_basis=raw_unadjusted, bars/actions/settlement. 현금 이외의 합병·주식교환 등은 허용하지 않는다.
- 판단 시점: eraleader.issuer_lineage_research.v1, retrieved_at은 decision_at 이하, 해당 현지일에 활성인 permanent security_id와 ticker/record_id 확인.
- 평가 시점: 같은 논리 공급자/발행자 ID의 뒤 빈티지, retrieved_at은 evaluated_at 이하, 마지막 거래일 유효 ID와 현금형 상폐 이벤트 ID/유형/효력일 대조.
- raw 가격의 split·dividend 일자는 평가 시점에 알려진 issuer events와 양방향 비교한다. 가격 경로에 없는 기업행동과 issuer 빈티지에 없는 가격 행동 모두 차단한다.
- 빈티지 source 변경, record_id 재할당, 최초 valid_from 소급 변경, 중복 티커 충돌, 지급 미확정/미입수 및 다른 기업 정산 이벤트도 검열한다.
- 각 원본 바이트 SHA256 세 개만 파생 보고서에 기록. 임의 대체 원시자료·원천 문서를 Git/백업에 재배포하지 않는다.

## CLI (기존 동작 호환, 두 플래그 동시 지정 필수)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader audit-cash-delist \
  --file output/dual_cash_vintage_trial_20261011/inputs/cash.json \
  --decision-lineage output/dual_cash_vintage_trial_20261011/inputs/decision_lineage.json \
  --evaluation-lineage output/dual_cash_vintage_trial_20261011/inputs/eval_lineage.json \
  --security-id SYN-CASH-EXIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-05-01T17:00:00+09:00' \
  --out output/dual_cash_vintage_trial_20261011/derived

PYTHONPATH=src python3 -m pytest tests/test_cash_exit_lineage.py tests/test_delist_cash.py tests/test_issuer_lineage.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

별도 독립 실행: python3 -m eraleader.cash_exit_lineage --cash-file ... --decision-lineage ... --evaluation-lineage ... --security-id ... --market ... --decision-at ... --evaluated-at ... --out NEW_FILE. 독립 실행은 기존 파일을 덮어쓰지 않는 exclusive-create를 적용한다.

## 상태와 인증 경계

모든 자기선언 계약이 내부적으로 일치할 때만 LOCAL_DUAL_VINTAGE_CASH_EXIT_RESEARCH_NOT_CERTIFIED와 계산된 **연구용** cash_exit_total_return을 반환한다. 하나라도 불일치하면 CENSORED_UNCORROBORATED_CASH_EXIT와 cash_exit_total_return=null 및 blocking_reasons를 반환한다.

다음 플래그는 어떠한 경우에도 false: historical_universe_pit_certified, issuer_identity_independently_verified, cash_payment_independently_verified, action_amounts_independently_verified, price_sessions_completeness_verified, real_leader_prediction_certified. 분할 비율·현금 정산금액·기업행동 전체 커버리지의 진실을 교차 검증하는 독립 제3자 출처는 아직 없다.

## 남은 작업

합성 KR 2:1 분할 후 현금 55 연구수익 +10%, 미국 DST를 통과한 합성 현금 105 연구수익 +5%는 단위 시험이며 실제 종목/성과가 아니다. 실전 독립 PIT 법적 기업ID·상폐현금·행동/배당/조정총수익·상장폐지 포함 종목군 증빙과, 사전 동결한 미래 대장주 성숙 결과가 필요하다. 외부 API 연동은 로컬 1~6단계 구현 후(D-017), 실제 SSD 분리·재연결/재부팅은 API 연결 후 최종 검수(D-021)로 연기한다.

## 2026-10-11 후속 — 기업행동 금액·현금지급 조건 교차검사 (2_2 / 2_5)

기존 이중 빈티지 감사는 raw 주가 경로와 발행인 행동 이력의 **action_type + effective_on**만 비교했다. 즉 raw 2:1 분할인데 issuer 문서가 3:1, 원천은 주당 현금 54인데 정산 계약은 55, 원천 배당금이 2인데 raw 계산은 1인 경우에도 연구 수익률이 그대로 나올 수 있었다. 정확히 동일한 날짜이지만 다른 action_id인 경우도 탐지하지 못했다.

추가 로컬 계약: 결제기관/법적 원천과 **독립적으로 확인됐다는 뜻이 아닌** 자기선언 issuer 이벤트의 `ratio`(split), `cash_amount`(dividend), `cash_per_share`/`currency`(cash_delist), 선택적 `paid_at`/`cash_payment_confirmed`. 원시 수익률 입력과 이벤트 ID·비율·금액·통화·지급 상태가 서로 충돌하면 기본 호환 모드에서도 오류 차단(`cash_exit_total_return=null`). 양쪽 숫자는 Decimal 유한성 검사 및 정확한 금액 비교(부정확한 부울/NaN/Inf/음수 금지)를 사용한다. 수치가 **애초에 없는** 과거 issuer JSON은 기본 연구 호환을 유지하지만, 선택적 `--require-lineage-amount-claims`로 실행하면 각 raw split/dividend와 현금형 상폐의 정규화된 금액·통화 주장까지 필수화하여 미제출을 명시적 blocker로 남긴다.

- `SPLIT_RATIO_CLAIM_MISMATCH`, `DIVIDEND_CASH_CLAIM_MISMATCH`, `CASH_EXIT_AMOUNT_CLAIM_MISMATCH`, `CASH_EXIT_CURRENCY_CLAIM_MISMATCH`, `CORPORATE_ACTION_ID_MISMATCH`: 서로 모순되는 원천값이 있을 때 결과 보류
- `MISSING_SPLIT_RATIO_CLAIM`, `MISSING_DIVIDEND_CASH_CLAIM`, `MISSING_CASH_EXIT_AMOUNT_CLAIM`, `MISSING_CASH_EXIT_CURRENCY_CLAIM`: strict 모드에서 미제출을 결과 보류
- `CASH_EXIT_PAID_AT_CLAIM_MISMATCH`, `CASH_EXIT_PAID_CONFIRMATION_CLAIM_MISMATCH`: 제출된 지급 사실/시각에 모순이 있으면 결과 보류
- 추적 필드 `lineage_amount_claims_required`, `action_amount_claims_matched`, `cash_exit_currency_claim_matched` 추가. 기존 `action_amounts_independently_verified=false`, `cash_payment_independently_verified=false`, `historical_universe_pit_certified=false`는 절대 승격되지 않는다.

실행 형식은 기존 `audit-cash-delist --file ... --decision-lineage ... --evaluation-lineage ... --security-id ... --market KR|US --decision-at ... --evaluated-at ... --out ...` 뒤에 `--require-lineage-amount-claims`를 추가한다. 새 standalone 모듈에서도 동일 옵션 지원. 코드·합성 테스트: `src/eraleader/cash_exit_lineage.py`, `src/eraleader/cli.py`, `tests/test_cash_exit_amount_claims.py`. **이 기능은 금액/일치 여부를 확인할 뿐 실제 정산액의 진위, 기업행동 원본 완전성, 실제 PIT/발굴 적중률을 증명하지 못한다.** 외부 API는 D-017대로 나중, 물리 SSD 재연결 시험은 D-021대로 마지막 검수.
