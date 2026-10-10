# 2_2 / 2_5 — PIT historic membership vs. observed market cache reconciliation

> 2026-10-10. Local-only source-coverage instrument. This does **not** certify an official historic listing registry or adjusted prices.

## Working code

- `src/eraleader/pit_coverage.py`: reconcile the independently timestamped `OfflineLedger.snapshot(as_of,market)` membership universe against market-specific cached price **observations** at the last available price session <= cutoff.
- Separately measure (a) PIT membership count, (b) observed feed identities, (c) intersection, (d) membership identities missing from price feed, (e) price feed identities missing from the PIT registry, (f) suspended price observations, (g) previously exited security IDs still seen in feed.
- Emit numerator/denominator coverage ratios and small samples, explicit `last_price_observation`, alongside **all certification flags false**. No existence, listing, delisting settlement, or price adjustment is inferred from observation alone.
- Fail closed for a mismatched PIT market-day, future/invalid price timestamps, duplicate security/session price bars, missing fields, or a logical contradiction between active membership and known exited IDs.
- CLI: `PYTHONPATH=src python3 -m eraleader audit-pit-coverage --market KR --as-of '2024-09-01T17:00:00+09:00' --ledger output/demo_offline/offline.sqlite --out output/demo_offline`. This is an **example format** only; the included ledger is synthetic and should not be reconciled with real price caches as if official.
- `tests/test_pit_coverage.py` uses isolated synthetic price observations and real SQLite offline ledger operations; includes CLI contract. Seven additional tests PASS.

## Actual tests and boundary

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_pit_coverage.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

- Prior total 90, new tests 7 -> **97 pytest PASS**, 0 failures.
- No KRX official historical membership archive has yet been imported; tests **do not** establish actual authoritative coverage rate for 1995–2026 Korea or the US survivor-biased weekly cache.
- Next: independently timestamped listing and historical ticker/ID mapping, delisting cash settlement, split/dividend adjustment benchmark & verified supplier snapshots (after offline input sourcing). Without those, result must be `NOT_CERTIFIED`.
