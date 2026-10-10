# EraLeader 2_2 / 2_5 — 현금형 상장폐지 정산 수익률 연구 계약

> 2026-10-10 KST. **현금 정산액을 임의로 만들지 않는다.** 테스트용 분할/상폐 사례는 100% 합성자료이며 실제 상장폐지 종목·과거 투자 성과·PIT 원천 검증을 의미하지 않는다. 외부 API 0회, 기존 CycleOS 가격 파일은 읽기 전용·변경 없음.

## 구현 범위와 안전 경계

- `src/eraleader/delist_cash.py`: 현금 주당 정산금(`cash_per_share`)이 명시된 **cash_delist**에 한해 마지막 거래가능 raw 종가 기준 경로와 최종 현금 정산 수익률을 계산한다. 기존 `corporate_returns.reconstruct_total_return`의 분할/배당 보정·시점 검증을 그대로 재사용한다. 배당은 기존 엔진의 재투자 가정이며 세금·수수료·환율은 포함하지 않음.
- 정산 기록은 원시 `security_id`, `source_id`, `event_id`, 마지막 거래일, 상폐 실효일, 주당 현금, KRW 또는 USD, 출처 주장, 발표시각, 지급시각, 원천에서 이용가능해진 시각(모두 time-zone aware), 지급 확인 boolean을 명시해야 한다.
- 평가 기준 시각 이전에 **실제 지급되었고 공개 기록을 이용할 수 있었음이 입력상 확인**된 경우에만 연구용 수익률을 계산한다. 지급 완료 전/나중에 입력된 자료는 `CENSORED_CASH_PAYMENT_NOT_KNOWN_BY_EVALUATION`·수익률 `null`; 정산자료 자체가 없으면 `CENSORED_MISSING_CASH_SETTLEMENT`·수익률 `null`. 금액 0/음수/NaN, 종류 불명의 주식교환/합병·스핀오프, 실효일 오류, 미래 공시, 다른 통화·기업 ID, 조정가격 이중보정 등을 차단한다.
- **PIT/공신력 인증은 어떠한 경우에도 false.** 소스의 지급 확인이 true라도 실제 발행기관/법적 기업 동일성·과거 유니버스·기업행동 완전성의 독립 인증은 별도이며 지금 미구현이다. 공식 정산금 0원 확정처럼 극단적 상황도 독립 증거 없이 이번 로직에서 0원으로 보정하지 않는다.
- CLI `PYTHONPATH=src python3 -m eraleader audit-cash-delist --file <local cash_delist_research_v1.json> --security-id ... --market KR|US --decision-at <ISO time> --evaluated-at <ISO time> --out <local output>` 추가. 결과 파일 `cash_delisting_research.json`은 기존 SHA256 ZIP 백업 허용, 원본 정산자료·원시 시세는 ZIP 허용 목록에서 제외.

## 직접 검증 명령

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_delist_cash.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
# 생성한 합성 현금정산 원본은 output/cash_settlement_trial_20261010/ (Git 제외)
PYTHONPATH=src python3 -m eraleader audit-cash-delist \
  --file output/cash_settlement_trial_20261010/synthetic_paid.json \
  --security-id SYN-CASH-EXIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-05-01T17:00:00+09:00' \
  --out output/cash_settlement_trial_20261010/paid_result
```

- 실제 실행한 합성 KR 예제: raw 가격 100 → 2:1 분할 뒤 50 → 50, 주당 지급 완료 현금 정산액 55, 연구용 총수익 **+10%**. 단순 종가 하락을 -50% 손실이라고 오판하지 않음. 같은 자료에서 정산 기록을 삭제한 입력은 `cash_exit_total_return=null` 처리.
- 재현된 합성 US 시험: 달러 지급액 105, 원시가격 100→101 및 뉴욕 현지시각 지급/입수 기록으로 연구용 **+5%**. 환산/세후 실전 수익률로 사용할 수 없음.
- 로컬 ZIP `output/continuous/cash_delist_paid_verified_20261010.zip`에 파생 JSON 1개만 백업, SHA256 검증 및 `output/continuous/cash_delist_paid_restored_20261010` 복구 PASS. 실제 정산 원본과 키 제외.
- 신규 `tests/test_delist_cash.py` **23 pytest cases**, `tests/test_local_backup.py`에 파생 JSON 안전 백업 **1 case**, 총 신규 24개. 다른 세션의 untracked `walkforward_replay.py` 관련 테스트 19개가 현재 공유 작업폴더에 있어 전체 PASS 수는 기준 체크포인트 명령으로 별도 확인.

## 진짜로 남은 증거

실제 한국/미국 상장폐지 목록, 정산금 지급내역 및 기업별 식별자, 거래소 공식 공시·정정 빈티지, 주식교환/합병 대체증권 가치, 과거 회계/산업/시장 구성 PIT, 종목별 실제 체결가격·비용은 아직 확보·독립 확인하지 않았다. 따라서 1_1~6_5 최종 완성/미래 대장주 발굴 정확도 인증 **NO**. 다음 단계에서는 신뢰할 수 있는 오프라인 원천을 확보하고 증명하는 검증 체인을 이어야 한다.
