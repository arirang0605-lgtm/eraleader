# 2026-10-10 — 5_4/5_5 prospective signal timestamp registry + 6_2/6_5 preservation

## Why

EraLeader must actually timestamp its **future** discovery hypotheses when it generates them. A later replay of a 2024 synthetic file on 2026-10-10 cannot claim a 2024 prospective lead. The independent history from a past model run and its actual first local processing time must be separate. This is essential infrastructure for future true lead-time validation, not evidence of any validated investment edge.

## Implemented

- `src/eraleader/prospective.py`: `ProspectiveRegistry` SQLite append-only-by-app ledger, with local UTC recorded timestamp and local KR/US calendar dates. Each integrated **research growth screen hit** gets stable identity scoped by market/security/kind/source as_of/model version, source run ID, SHA256 input fingerprint, normalized provenances and immutable WATCH-research-only status. Replayed inputs are idempotent; a changed payload at a previously registered key is rejected; inserts use a SQLite immediate transaction so a conflict rolls the whole batch back.
- Future timestamps, timezone-naive timestamps, duplicate security IDs, missing run/model identity, forged 100pt score, PIT-certified promotion and official leader states are rejected. No future outcome labels are stored. Legacy historical files replayed today are tagged `historical_backfill=true`. Actual registration date is exported as `recorded_at` so the existing `discovery_metrics.evaluate_early_discovery` gives **no spurious early-lead credit**.
- `src/eraleader/cli.py`: existing `offline-integrated` now records research signals without changing previous research files/leader states; new `prospective-signals --market KR|US --out ...` exports first *actual* registration per security with separate observed vs registered dates, no false official leader certification.
- `src/eraleader/delivery.py`: additional local HTML `site/prospective_kr.html` or `prospective_us.html` with observed date, actual registration date, explicit historical-backfill marker and 0 official leaders. Escapes external text and refuses to display forged certification.
- `src/eraleader/local_backup.py`: the allowlisted `prospective.sqlite` and research JSON reports are included in SHA256-verified local archives using SQLite online backup, so restored original timestamps survive. No raw market prices, credentials or .env are archived.
- API/SEC/DART/KRX external data calls and real message sends remain zero. SQLite/HTML/JSON artifacts are local under ignored `output/` only.

## Commands tested locally

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_prospective.py tests/test_local_backup.py tests/test_research.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 -m eraleader offline-import \
  --file tests/fixtures/offline_synthetic.json --out output/prospective_trial_20261010
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2024-09-01T17:00:00+09:00' --out output/prospective_trial_20261010
PYTHONPATH=src python3 -m eraleader prospective-signals \
  --market KR --out output/prospective_trial_20261010
# Backup/recovery also actually exercised for this isolated output.
PYTHONPATH=src python3 -m eraleader verify-backup \
  --archive output/continuous/prospective_trial_20261010.zip
```

## Verified results and limits

- Before changes **97 PASS**. New prospective tests (incl. four parametrized official-promotion denials), backup-recovery test, dashboard-XSS/certification test = **111 pytest collected/PASS**, zero failures.
- Isolated real CLI workflow on **synthetic** 2024 research: one growth WATCH registered **on 2026-10-10**, with `first_seen=2024-09-01`, `recorded_at=2026-10-10`, `historical_backfill=true`, `official_leader_signals=0`. Second identical run wrote zero new registrations. SHA-verified ZIP includes the signal ledger; restore into new path preserved its date. No 2024 prospective success was claimed.
- System time is not externally attested and DB file can be edited outside the Python application. These are app-level immutability protections only, not cryptographically verifiable archival records. Source provenance, corporate actions, survivor-free universe, delisting proceeds, share-adjusted series, actual future leader labels and strict out-of-sample evaluation still need independent verification.

## Next actual task

**2_2 / 2_5:** independently sourced historical listing and corporate-action/proceeds PIT data; reconcile observed codes, adjusted-vs-raw return series, feed availability timestamp, and coverage. **5_4 / 5_5:** freeze a candidate model, create untouched forward holdout with predeclared label horizon/false-positive definitions, measure precision and lead time once outcomes mature. **6_5:** verify scheduler behavior after reboot, external SSD loss and official holiday calendar; no API until local development acceptance.
