# 2026-10-10 — Explicit offline PIT + price research batch integration

## Production boundary

The default `batch` and the installed `org.eraleader.offline-research` launchd scheduler **remain price-only**. They do not silently use a nearby synthetic/fake `offline.sqlite` and do not generate official leading-stock certifications or live notifications. Source-specific API connections remain deferred.

The new optional `batch --integrate-pit-research` mode explicitly joins:

1. Both KR and US `--kr-as-of` / `--us-as-of` **market-local dates** for the read-only KR marcap and US historical weekly price scans;
2. Existing local `--out/offline.sqlite` with then-known membership, financial/sector records and actions (never created just to satisfy the batch);
3. Explicit timezone-aware `--kr-decision-at` / `--us-decision-at`, each converted to the **actual exchange's timezone**, and rejected if the local market day differs from the associated price-scan date;
4. Existing `execute_integrated` (using the price scan's immutable `runs/<id>.json`) for conservative offline price/fiscal research and `ProspectiveRegistry` WATCH-only registration;
5. Existing KR+US daily/weekly/monthly Markdown reports and **dry-run-only** alert preview. Every integrated market in `batch_manifest.json` reports decision cutoff, non-certified research status, deferred screening and count of newly registered unverified research WATCH records.

The full prerequisite check runs **before any price-screen side effect**. If the user opts in without both decision stamps, uses naive/future-offset-vs-exchange-date mismatch, has no existing offline SQLite or no then-known market membership, the batch rejects rather than fabricating completeness. The optional integration does NOT authenticate the underlying issuer ID, legal stock universe, price adjustments, settlement, filing vintage or model skill. `official_leaders=0`, `pit_certified=false`, `messages_sent=0`, `external_api_calls=0` are explicit.

## Reproducible local commands

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_batch_pit_integration.py tests/test_batch.py tests/test_local_schedule.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

**Real local adapter smoke:** `output/batch_pit_integration_20261010/offline.sqlite` was populated with explicit `synthetic_fixture` documents for KR/US and `batch --integrate-pit-research` read real **read-only** T5DATA KR/US price caches at cutoff 2024-09-01 (KR) and 2024-08-30 (US), with market-local decision times 17:00+09 / 17:00-04 and `--days 550 --top 5`. Returned 2 markets, 6 reports, research price rows KR 5 / US 1; KR one synthetic historical growth WATCH record registered *now*, US one deferred screening. Six dry-run alert-preview events were generated but **zero live messages** and no API calls. Both local research HTML pages exist and all official leaders remain zero.

**Important:** a historical 2024 candidate registered by the program in 2026 is a *backfill*, never an actual 2024 forward discovery or investment win. Synthetic PIT financial data plus actual retrospective prices **do not constitute verified PIT**. This command is an offline functional integration smoke test, not prediction performance.

## Implementation & limits

- `src/eraleader/batch.py`: additive explicit preflight, existing date checks, optional cross-market `execute_integrated` calls and narrow metadata in manifest; no changes to default scheduled path.
- `src/eraleader/cli.py`: three explicit arguments. Existing per-market `offline-integrated` and annual/quarterly fiscal-freshness guards are reused (no strategy rewrite).
- `tests/test_batch_pit_integration.py`: optional mode runs 2 markets/idempotently, default mode stays price-only, four incomplete/mismatched cutoff forms rejected before price output, missing ledger and unusable US membership refused. Other pre-existing tests verify old schedule and batch.
- Real official issuer/sector/fiscal/action evidence, independent supplier vintage, delist payouts, actual future matured outcomes and source attestation are **NOT available or certified**. The 2024 price caches still carry US survivorship bias; no official era-leader selection may follow.
