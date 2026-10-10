# 2026-10-10 — 6_5 macOS local scheduler + 5_2 early-discovery registration audit

## Implemented (offline only; not live investment advice)

- `src/eraleader/local_schedule.py` detects the actual last KR marcap `Date` and US weekly-cache `ts` without any remote request. A scheduled run rejects future timestamps and requires both cache series to be no more than ten calendar days old. This is a conservative *operating gate*, not a market holiday calendar.
- A nonblocking OS `flock` stops concurrent instances. The checkpoint `output/scheduler_control/last_verified_batch.json` is atomically replaced **only after** a successful two-market batch, six reports, and verified local ZIP backup. A failed batch/backup leaves the prior checkpoint for retry. An unchanged KR+US cache pair is skipped.
- `scripts/run_local_scheduled.py`: executes the existing `batch` and `local_backup` modules. It never sends alerts; all WATCH items remain local previews; KRX/SEC/DART/API calls remain zero. `--allow-stale-research` bypasses only the age gate, explicitly labels the result research-only, and never enables live notifications.
- Generates a user LaunchAgent at `output/scheduler_control/org.eraleader.offline-research.plist`. Installed copy is `$HOME/Library/LaunchAgents/org.eraleader.offline-research.plist`, label `org.eraleader.offline-research`, weekday 18:10 **Mac local time (KST at installation)**, with RunAtLoad. Working directory and logs under `$HOME` avoid launchd startup EX_CONFIG=78 accessing unmounted removable SSD. Normal execution verified exit code **0**.
- `src/eraleader/discovery_metrics.py`: when an evaluation signal provides `recorded_at`, the **actual recorded date** rather than retrospectively backdated `first_seen` controls lead-time credit. Reject recorded dates earlier than first-seen or later than evaluation, impossible leader onset after outcome maturity. Report coverage, unregistered signals, and conservative early precision floor. Without independently recorded dates, no historical discovery certification is claimed.

## Real local run and test evidence

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader
# Ordinary schedule result: SKIPPED_STALE_CACHE; US cache out of date.
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --allow-stale-research
# Research-only two-market batch, six reports, verified backup.
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --allow-stale-research
# SKIPPED_UNCHANGED_CACHE; no duplicate batch.
launchctl print gui/$(id -u)/org.eraleader.offline-research
```

- Initial baseline: 79/79 tests pass. New scheduler unit tests 7, new discovery-metrics tests 4; **90/90 tests pass**, 0 failures. Handoff inspection passed (30 task IDs).
- On 2026-10-10 the latest cached **KR observation 2026-10-02 (8 days old)**, **US observation 2026-02-26 (226 days old)**. Default automatic run appropriately skipped, no reports were mislabeled as fresh.
- Local explicit stale-data research override created two-market report files (6 Markdown), checkpoint and SHA-verified ZIP. A second override with unchanged observations skipped. **Messages sent=0 / API calls=0**.
- Initially the LaunchAgent failed with `EX_CONFIG=78` when working directory and log paths were on the external SSD. Changed them to `$HOME`; after reloading the user LaunchAgent, `launchctl print` displayed `last exit code = 0` and logged `SKIPPED_STALE_CACHE`.
- LaunchAgent is a finite **daily Python batch**, not an always-running AI coding agent. It needs an awake Mac and mounted SSD; future source updates must happen separately. A scheduled run cannot supply missing PIT data.

## Controls, inspection and removal

```bash
launchctl print gui/$(id -u)/org.eraleader.offline-research
tail -30 "$HOME/Library/Logs/EraLeader/scheduled.log"
tail -30 "$HOME/Library/Logs/EraLeader/scheduled_error.log"
# To stop scheduled operation (not needed in normal use):
launchctl bootout gui/$(id -u)/org.eraleader.offline-research
# To also prevent registration on next user login, remove the
# specific file: $HOME/Library/LaunchAgents/org.eraleader.offline-research.plist
```

## Still unfinished; do not certify 1-6 stages

- **2_2/2_5** source-level historic membership, independently verified corporate actions/delist proceeds, official adjusted-price cross-checks; external API withheld as directed.
- **5_2/5_4/5_5** independently timestamped prospective signals and historical labels, coverage/ablation, embargo and locked holdout. Tests are mostly synthetic, not a demonstrated early leader detection edge.
- **6_5** restart/sleep/holiday and SSD disconnect fault-injection tests, actual fresh two-market scheduled output, external backup redundancy, real delivery channels deferred.
- No secret files or raw market archives are included in Git. Output backups remain locally only.
