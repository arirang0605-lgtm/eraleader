# EraLeader 6_5 removable-SSD resilient scheduled local research — 2026-10-10

## Implemented and actually deployed

- The existing user LaunchAgent `org.eraleader.offline-research` remains local and uses the Mac login session, no cloud or external API. Its `ProgramArguments` now invoke **`/bin/sh` plus a small bootstrap on the Mac home disk**, rather than a Python file residing on a removable SSD. The generated helper is at `~/Library/Application Support/EraLeader/offline-launcher.sh`; executable owner-only permission 700. `write_launch_agent` generates helper and plist; helper creation does not install agent.
- Bootstrap checks if `/Volumes/T5DATA/eraleader/scripts/run_local_scheduled.py` and the read-only local cache root exist. If absent, prints `SKIPPED_EXTERNAL_SSD_UNAVAILABLE` and exits successfully **without** fabricating market snapshots or raising a launchd configuration error. When available, it executes the existing offline Python entrypoint with properly shell-quoted paths.
- The LaunchAgent retains local Mon–Fri **18:10 KST** calendar trigger and `RunAtLoad`, plus a **3600-second recovery interval** so a late-mounted SSD can be retried after login. This does not run an AI coding agent, collect external prices, deliver live alerts, guarantee exact execution while the Mac is asleep, or recover the SSD's physical failure.
- Existing `run_scheduled` lock prevents parallel jobs, verifies previous archive before skipping unchanged cache, and blocks stale KR/US data. Real current cache age at test: KR 2026-10-02 (8 days), US 2026-02-26 (226 days). Therefore launchd normally logs `SKIPPED_STALE_CACHE` and sends no messages.
- At regeneration, the previous installed plist was first copied to `output/scheduler_control/launch_agent_pre_recovery_20261010.plist` (Git ignored), the new plist validated by `plutil -lint`, then user `launchctl bootout` / `bootstrap`. New agent was really started and **last exit code 0** with normal stale-cache output; stderr empty.

## Tests and exact reproduction

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_local_schedule.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader \
  --generate-plist output/scheduler_control/org.eraleader.offline-research.plist
plutil -lint output/scheduler_control/org.eraleader.offline-research.plist
/bin/sh "$HOME/Library/Application Support/EraLeader/offline-launcher.sh"
launchctl print gui/$(id -u)/org.eraleader.offline-research
```

- **Focused 10 pytest PASS**, including launchd weekday/hourly configuration, home-bootstrap path, filenames containing spaces, **simulated missing and remounted cache**, symlink-launcher rejection, and old archive corruption forcing reprocessing. All **187 pytest PASS**, 0 FAIL. The external drive was NOT physically unplugged; actual reboot/unplug hardware integration remains a separate on-device test.
- The generated helper and installed plist on the Mac home volume are local operations, not tracked in Git; tests always point helper to a temporary location. `.env`, credentials, source raw data and market archives are never copied to Git.
- Mac user login, wake state, macOS launchd delivery, storage read health and new PIT-complete upstream data remain prerequisite. This is operations fault-tolerance, **not** future leader detection performance certification.
