# EraLeader 5_4 / 5_5 — prospective WATCH persistence, weakening and re-entry

> 2026-10-10 KST. Additive local research monitoring, not confirmed era-leader selection. No API, live user notification, actual future-label success or real historical PIT certification.

## Why this is necessary

The original `prospective_signals` ledger recorded only positive heuristic WATCH screening hits. An absent security in a later research run could mean missing vendor input, a partial universe, no financial report, or a genuine deterioration — **absence is not a failed screen**. A positive-only ledger therefore must NOT infer weakening, revival, or a return to leadership from missing rows.

## Existing code preserved; additive implementation

- `src/eraleader/prospective.py` creates `research_screen_observations` in the same local `prospective.sqlite` (via non-destructive `CREATE TABLE IF NOT EXISTS`). Each **explicitly analyzed** security/company stores hit `true` or `false`, observed-as-of, actual registered UTC time, model version, source run ID, SHA256 and canonical input research JSON. Transactions include both complete-screen observations and original positive `prospective_signals` so all-or-none writes or rollbacks protect consistency. Existing FIRST positive event timestamp is preserved on replay of older data and is not overwritten.
- A replay of identical market/ID/as-of/model+input is idempotent; a revised result in the same identity is rejected (no look-ahead restatement). Existing original `ProspectiveRegistry.first_signals` and original candidate freeze logic are unchanged; the research-only screen observation store never promotes an official candidate.
- `src/eraleader/watch_progression.py`: `audit_watch_progression(ledger,market,model_version,max_registration_lag_days=3)` reads the ledger **read-only** and checks canonical bytes vs SHA + company/source/run/model identity before event history. A research observation registered more than 3 local calendar days after its market observation is **excluded as historical backfill**, not credited as a forward signal. No simple ticker name matching; scoped to permanent `security_id` and pinned model version.
- The explicit transitions are `INITIAL_WATCH` (first positive ever), `WATCH_PERSISTED` (continuing positive), `SCREEN_WEAKENED` (positive -> explicit negative), `SCREEN_STILL_WEAK` (continued explicit negative after previous positive), `SCREEN_REENTERED` (explicit negative -> positive after prior positive), and `PRE_WATCH` (negative before first positive). A missing row triggers **no transition**. Audit never labels true/false future leader outcomes or claims full coverage. All official promotion, PIT certification and actual prediction accuracy flags are FALSE.
- `src/eraleader/cli.py`: `audit-watch-progression --ledger <sqlite> --market KR|US --model-version <pinned> [--max-lag-days 3] --out <dir>`; outputs `watch_progression_{kr,us}_research.json`, now allowlisted as a **derived-only** SHA256 ZIP backup JSON in `src/eraleader/local_backup.py`. No original vendor market data/secret token enters Git or archive.

## Actual executed synthetic smoke

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_watch_progression.py tests/test_prospective.py tests/test_frozen_holdout.py tests/test_holdout_registry_integrity.py -q
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m eraleader audit-watch-progression \
  --ledger output/watch_progression_trial_20261010/synthetic.sqlite \
  --market KR --model-version synthetic-screen-v1 \
  --out output/watch_progression_trial_20261010/derived
```

Synthetic input clock is **injected for deterministic tests only** (four dates Oct 5,6,7,8), not a claim that EraLeader actually issued those live alerts at those times. The sequence is positive -> positive -> negative -> positive. CLI derived 4 prospective observations, 0 retrospective backfills, transitions `INITIAL_WATCH=1`, `WATCH_PERSISTED=1`, `SCREEN_WEAKENED=1`, `SCREEN_REENTERED=1`; **official promotions 0**. Saved `output/continuous/watch_progression_demo_20261010.zip`, SHA-verified and restored into `output/continuous/watch_progression_demo_restored_20261010`; derived JSON unchanged.

## Important limitations / next blocker

- Existing *historical* `prospective.sqlite` files from before this schema contain positive registered signals without full negative-screen history. A replay of an identical old positive signal reuses original positive registration time; missing past negative rows **cannot be reconstructed** from absence and are never manufactured.
- The local computer clock and provider assertions are not independently attested. A malicious actor with complete SQLite and wall-clock access could forge data, even with SHA checks. Our code only catches local inconsistency or an unrecognized altered record.
- All input data remain local research-only. Before officially identifying future leaders: verify complete PIT historical issuer/corporate-action/adjusted-price/fiscal industry sources, real contemporary input freshness, full observed universe and forward unaltered maturity labels; then validate lead time, false positives, replacement tracking on truly prospective observations. External API sources are still postponed by user.
