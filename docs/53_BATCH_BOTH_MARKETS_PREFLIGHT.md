# EraLeader 6_1 / 6_5 — both-market input preflight before PIT research batch writes

> 2026-10-10 KST. Applies **only** to explicitly selected `batch --integrate-pit-research`. Installed hourly/weekday macOS launchd and default price-only batch remain unchanged. No external API or live alerts.

## Found defect

The initial opt-in `batch` rejected missing KR/US membership or invalid decision timestamps ahead of price writes, but after that it **wrote KR price snapshots and prospective WATCH records before loading/validating US prices**. If the US Parquet or PIT/price date failed only in the second market, the first-market state and reports could remain without a complete cross-market batch. A final `batch_manifest.json` was not written, but downstream local readers could still see partial artifacts.

## Narrow fix

- `src/eraleader/batch.py` preflights **both** KR and US market inputs in one logical phase before any execution writes: required timezone-aware decision dates, market-local day correspondence, existing immutable offline ledger and then-known members, actual read-only market price bars, normal price scanner/quality calculation, and `integrated_snapshot`'s PIT/price source and future-date gates.
- Only if **both markets** pass does the batch invoke existing `execute_run`, `execute_integrated`, 6 Markdown reports and dry-run alerts. The already-scored and verified price-screen snapshot is passed to `execute_run` through an **internal-only** `prepared_snapshot` argument (CLI has no user-facing flag). Thus each market's source is read/scored just **once**, not twice; the prior default market CLI and scheduled runs still use the original price-adapter path.
- `src/eraleader/cli.py` checks the in-memory prepared snapshot's market, requested date and deterministic run ID before saving it. This is not externally signed PIT evidence. No mutation of original KRX/US Parquet datasets, no issuer certifications, no crypto/trading dependencies.
- **Scope**: this prevents partial persistence for failures discovered during *input preflight*. It does **not** claim a cross-filesystem atomic transaction across SQLite files, HTML, Markdown, and archives if a disk crashes or fails **after** preflight. A final batch manifest is only written after the full flow. Full durable transactional publication/recovery remains a separate 6_5 enhancement.

## Verified regressions

- Existing `tests/test_batch_pit_integration.py` synthetic fixture patched so **both** the CLI adapter and new preflight read from the synthetic test data, never accidentally from T5DATA. Existing default batch/schedule tests preserved.
- Four newly added tests: deliberate US cache-read failure after KR is prepared, US PIT/price join validation failure after KR passes, exactly one price source read per market, and default price-only batch never invoking PIT research preflight. Under either US preflight failure, there is **no KR `state.sqlite`, `prospective.sqlite`, `batch_manifest.json`, `kr_latest.json`, research HTML or reports**; the function fails closed rather than generating an incomplete cross-market research batch.
- Real read-only market cache rerun with deliberately **synthetic** fiscal/sector and membership `offline.sqlite`: `output/batch_pit_integration_20261010/`. Repeat `PYTHONPATH=src python3 -m eraleader batch --integrate-pit-research --kr-as-of 2024-09-01 --us-as-of 2024-08-30 --kr-decision-at '2024-09-01T17:00:00+09:00' --us-decision-at '2024-08-30T17:00:00-04:00' --out output/batch_pit_integration_20261010 --top 5 --days 550` returned two markets, 6 reports, KR 5 price observations, US 1, zero **new** prospective WATCH records on repeat run, US screen deferred 1, **0 real messages, 0 APIs, 0 official leaders**.
- `PYTHONPATH=src python3 -m pytest tests/test_batch_pit_integration.py tests/test_batch.py tests/test_local_schedule.py -q` → 23 focused PASS.
- Repeat source test and public safety scan before commit; never call this actual future-leader early discovery accuracy or full historical PIT certification.

## Remaining priority

- 2_2/2_5 official historical issuer/corporate-action/filing PIT sources and valid delisting consideration; US S&P500 cached history is survivor affected.
- 5_4/5_5 truly *prospective* candidates, independent source-label maturity and falsification.
- 6_5 stronger durable commit/publish barrier across SQLite+HTML+reports under filesystem failures, SSD-disconnect/restart hardware test. External data API postponed by user.
