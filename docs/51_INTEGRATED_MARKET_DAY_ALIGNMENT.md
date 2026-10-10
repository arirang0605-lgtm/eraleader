# EraLeader 2_3 / 3_4–3_5 — Exchange-local PIT-to-price join alignment

> 2026-10-10 KST. This is a **synthetic unit + real CLI contract** for avoiding cross-timezone lookahead, not independent US/KR exchange-data PIT attestation or verified leader selection. External APIs deferred.

## Identified integration bug

The local OfflineLedger already normalizes membership and corporate-action validity to its exchange's actual calendar day (KR Asia/Seoul, US America/New_York). However, integrated_snapshot formerly used `datetime.fromisoformat(decision_at).date()` (the **caller's timestamp offset date**) to accept a price-screen `as_of_requested`. At May 1 00:30 KST the true US market day is **April 30**. This mismatch could accept a May 1 US price header and accidentally join a next-day price while the offline issuer membership state was correctly dated April 30.

## Implemented narrowly

- `src/eraleader/research.py` now derives `asof` from the timezone-aware cutoff, converted to the **actual exchange zone**, not from the input's offset. It checks `offline["trading_day"]` equals this market-local date, and still compares the UTC decision instant to immutable `offline["as_of"]`. Research never marks provider PIT, issuer-price ticker association, or an official leader as certified.
- Existing price market crosscheck, header last-observed and 10-day freshness checks remain intact, including individual price-row future-date and duplicate identity rejection.
- `tests/test_integrated_market_clock.py` adds **7 synthetic regressions**: US KST-midnight decision preceding New York midnight; correct US May 1 after local rollover; KR date rollover when caller gives New York offset; corrupted offline trading day rejection; time-equivalent offsets; US full `offline-integrated --price-json` CLI acceptance of correct price reference date and rejection of future US reference.
- Existing `tests/test_snapshot_market_clock.py` 5 regression tests from preceding code release confirm the first step's market-local membership and action dates. Whole suite **392/392 PASS** (385 preexisting +7 integrated date tests).

## Actual reproduction

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_integrated_market_clock.py \
  tests/test_snapshot_market_clock.py tests/test_research.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

The tests create only `tmp_path` synthetic database and JSON; the original T5DATA SSD price datasets and reusable CycleOS engine are **not modified**. Non-source input file names and hashes are not treated as official evidence. A real past US constituent list and action/payoff/fiscal-release PIT remains unavailable. API, real messaging and trading disabled.
