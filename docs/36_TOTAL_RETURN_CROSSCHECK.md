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
