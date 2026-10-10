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
