# EraLeader 5_4/5_5 sealed holdout, 6_5 backup retry — 2026-10-10

## Scope actually implemented

- `src/eraleader/frozen_holdout.py`: freeze a **research-only** set of first locally registered signals from `prospective.sqlite` into a once-created JSON manifest containing SHA256, source registration times, source-run fingerprint and model version. Explicit historical backfills older than the allowed lag are excluded. Frozen output contains no future labels.
- **New strict precommitment:** `label_definition_id` is required and `horizon_days` (1–1095) is frozen with the model at creation. Outcome evaluations must carry the **same** label-definition ID; requesting another horizon fails, so analysts cannot extend the winning window after observing results. Already-mature or already-known labels at the freeze timestamp are refused.
- `src/eraleader/cli.py`: `freeze-holdout` requires `--label-definition-id`, optionally `--horizon-days` (default 180), and writes only a **new** target file; `evaluate-holdout` uses the frozen horizon (optional argument only validates equality), censored results are NOT made into false positives. Local tests of historical synthetic positive, negative, late and censored outcomes.
- `src/eraleader/local_backup.py`: allowlists only frozen manifest + derived result and uses existing ZIP manifest/SHA256 for consistency; source market data and secrets are excluded.
- `src/eraleader/local_schedule.py`: on unchanged cache, the last referenced backup must actually exist and pass SHA verification; if deleted/corrupt, the local research batch and backup are retried rather than pretending the old snapshot is safe. `tests/test_local_schedule.py` includes missing/corrupted ZIP fault injection.
- `tests/test_frozen_holdout.py` verifies no future labels in freeze, no post-hoc horizon/label replacement, checksum mismatch rejection, time leakage, duplicate outcome identity, valid local market timezone, false positives, late signals, censored signals, CLI and backup. **No actual future stock-leader outcome has matured**; only synthetic tests have labels.

## Real test evidence

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_frozen_holdout.py tests/test_local_schedule.py -q
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m pytest --collect-only -q tests
python3 scripts/check_handoff.py
```

- 2026-10-10 KST: full test collection **179 cases**, all pass, no failures (131 baseline + 23 vintage + 17 earlier holdout/scheduler + 8 new protocol guards). The earlier source-vintage feature was already pushed as `779751e`; this checkpoint contains the *remaining* holdout and scheduler changes.
- Local CLI smoke (isolated `output/freeze_trial_20261010/`): one newly registered **SYNTHETIC WATCH** candidate -> frozen manifest, `model_version=trial-research-model-1`, `label_definition_id=predeclared-synthetic-v1`, horizon 180 days, **eligible=1**. Outcome list empty, so **known=0, censored=1, true early discoveries=0**. Manifest persisted and recovered via `output/continuous/frozen_holdout_trial_20261010.zip` (3 files, 22,599 bytes, SHA verified). All certification flags false.
- Installed macOS launchd agent `org.eraleader.offline-research` remains exit code 0 at last check. Its actual cache checks are conservative, no cloud, API or live alerts.

## Limits and next unfinished work

- Holdout uses a **locally writable SQLite and wall clock**; hashes are self-contained and not externally anchored. Neither timing nor model input completeness is independently certified. `label_definition_id` names a protocol but does **not** prove the label definition itself is scientifically valid or independently registered. Data source identities, corporate actions and delist proceeds still lack independently attested PIT history.
- New stock outcomes and official delisting/adjusted series require real time and suppliers; no synthetic test success can be advertised as actual early discovery performance.
- Next implement independent source completeness/issuer mapping and per-signal quality gates; then collect forward real outcomes on a predeclared evaluation horizon and evaluate after maturity, while preventing training on the holdout.
