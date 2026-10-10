# EraLeader 2_5 — offline total-return series independent comparison contract

> 2026-10-10 local development. **Source ID difference is an assertion, NOT independent-source attestation**. Neither synthetic agreement nor signed vendor claim is sufficient to PIT-certify historic returns.

## Implemented

- `src/eraleader/adjusted_crosscheck.py`: use existing `reconstruct_total_return` on **raw unadjusted** close with separately timestamped split/dividend actions. Compare session-by-session reconstructed price+dividend total return with a separately supplied `total_return_reinvested_index` close series. Reinvestment convention for this research comparison is shares split and cash dividend reinvested at ex-date close; other vendor conventions must not be silently merged.
- Source contracts require distinct non-empty declared price/index source IDs and basis; equal sessions in chronological order, positive finite reference index, explicit reference availability timezone and <= evaluation cutoff, no as-of future data or same-day pre-close price use. 5 bp default deviation tolerance is only an audit parameter, **not** a claim of source precision.
- Every interval outside tolerance is reported with date and deviation; mismatches are flagged `RESEARCH_RETURN_SERIES_DISAGREE`. Agreements are `RESEARCH_RETURN_SERIES_MATCH_NOT_CERTIFIED`. All `historic_price_actions_pit_certified`, `independent_provider_identity_verified`, `delisting_settlement_verified` remain FALSE.
- Unsupported merger/delist/spin-off actions and non-tradability **fail closed** via existing return engine, not treated as -100%, 0% or zero settlement.
- `src/eraleader/cli.py` command `audit-total-return --file ... --security-id ... --market KR|US --decision-at <ISO timezone> --evaluated-at <ISO timezone> [--tolerance-bps 5]` takes a **local only** JSON file with schema `total_return_crosscheck_v1`, `raw_source_id`, `provenance`, `price_basis=raw_unadjusted`, `bars`, `actions`, and `reference:{source_id,basis,bars:[{session,index,available_at}]}`.
- Output `total_return_crosscheck_research.json` is now included in the allowlisted, SHA256 verified local backup; original raw price input file is never included.

## Actual execution

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_adjusted_crosscheck.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
# Isolated synthetic source files are under Git ignored output/return_crosscheck_20261010/
PYTHONPATH=src python3 -m eraleader audit-total-return \
  --file output/return_crosscheck_20261010/bundle.json \
  --security-id SYN-SPLIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-04-10T16:00:00+09:00' \
  --out output/return_crosscheck_20261010
# The mismatch fixture used the same input but changed the final index to 102:
PYTHONPATH=src python3 -m eraleader audit-total-return \
  --file output/return_crosscheck_20261010/mismatch_bundle.json \
  --security-id SYN-SPLIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-04-10T16:00:00+09:00' \
  --out output/return_crosscheck_20261010/mismatch
```

- Previous 111 tests. New total-return comparison tests 19 (including parametrized bad source, timestamp, mismatch, delisting, tolerance, CLI) plus backup allowlist test 1 = **131 pytest PASS**. Full handoff checks PASS.
- Real CLI synthetic raw split+dividend 3 sessions: reconstructed 0% compounded, reference [100,100,100] matches, **0 mismatch**. Altered reference [100,100,102] => **one 200bp exception**; both returns correctly remain uncertified.
- Local ZIP `output/continuous/return_crosscheck_20261010.zip` validated; only derived audit JSON (896 bytes), no original bars, vendor payload or secrets. Existing read-only CycleOS-Lab folder untouched; external API calls 0.

## What remains fundamentally unverified

1. Official historical corporate-action feeds with `known_at`, ex-date, correction vintages, and missing-event completeness; historical listing universe including delist consideration.
2. A truly independent second vendor's adjusted/unadjusted series (rather than two synthetic declared source IDs), local exchange calendars, currency/dividend taxes, execution times and delisting proceeds.
3. 5_4/5_5 actual holdout with predeclared leader definition, qualified early signal logs, censoring, calibrated false-positive rates. A matching total-return index is only a debugging quality control, never proof of a winning strategy.

Next smallest step: source manifest and data audit contracts for actual locally ingested historical feed vintages, then real adjusted crosschecks when approved data is present. Do not certify 1~6 complete before independent source/forward outcomes.

## 2026-10-11 — 2_3/2_5 KR·US 현지 거래일 경계 회귀 수정

- `corporate_returns.py`는 앞 회차에 시작한 `MARKET_ZONE`(KR: Asia/Seoul, US: America/New_York) 기준 신호일/평가일과 `available_at`의 현지 시장일 검사를 유지한다. `adjusted_crosscheck.py`가 호출자/UTC 타임스탬프에 들어 있는 offset을 시장 시간대로 오인한 마지막 결함을 수정하여, 참조 총수익지수 게시일도 **해당 거래소의 현지일**로 검증한다. 미국 DST 시작/종료 모두 `ZoneInfo` 사용.
- 이전 회귀 테스트 `tests/test_market_local_return_pit.py`: 조정가격 비교의 UTC 자정 전후 예상실패(xfail) 1개와 DST 종료 후 실제 실패 1개를 재현하였다. 수정 후 xfail 표시를 제거했고 신규/수정 전체 6개 사례가 정규 PASS. 집중 `PYTHONPATH=src python3 -m pytest tests/test_market_local_return_pit.py tests/test_adjusted_crosscheck.py tests/test_corporate_returns.py -q --tb=short` 40 PASS; 통합 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` exit 0; `python3 scripts/check_handoff.py` PASS(30개 작업 ID).
- 이 변경은 기존 원본 캐시를 **읽거나 변형하지 않았고**, 외부 제공자의 발행시각, 공식 전체 종목군/상폐, 기업행동, 검증된 실전 총수익률 또는 미래 대장주 적중률을 인증하지 않는다. 합성 시간대 사례로만 로직의 누출 가능성을 검증했다. 외부 API 연결 및 물리적 SSD 재연결·재부팅 시험은 D-017/D-021에 따라 연기.
