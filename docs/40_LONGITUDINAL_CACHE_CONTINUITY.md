# 2_2 / 2_5 — KR daily + US weekly cache observation-continuity audit

> 2026-10-10 KST. Existing T5DATA SSD price files read only. This is **observation/feed quality research**, not an official survivor-free listing or delisting registry, not PIT certification and not an investment result.

## Working code

- `src/eraleader/continuity_audit.py` examines multiple periods, rather than the two-session comparison in `universe_audit.py`. At each distinct **observed market period**, it distinguishes **internal missing bars** (security observed both before and after a gap), first observations after window start, last observations before window end, and **observed suspended/no-trade bars** (never count those as missing).
- `src/eraleader/cli.py` adds `audit-continuity --market KR|US --as-of YYYY-MM-DD --days N --out ...`, using the existing read-only local adapter; saves `continuity_kr_research.json` or `continuity_us_research.json` and source quality flags.
- Strict invalid-date, future-date, duplicate security-date/period, missing identity/columns, invalid suspension flag and sample-limit gates. Samples are bounded to 20 by default. 1st/last observations are **not** treated as listing/delisting.
- **Important US correction found in live cache:** US historical data are **weekly per ticker with differing weekday timestamps**. An initial exact-date union created **27,942 fake internal gap events**. The audit now buckets US bars into **Monday–Sunday weeks**, with a maximum of one observation per security/week, and explicitly labels the cadence; KR remains daily. Actual rerun of the same US dataset produced **zero internal weekly gap events**. Recalculation supersedes the initial invalid exact-date count.
- `src/eraleader/local_backup.py` allowlists only the two **derived JSON audit results** and uses the existing SHA256-verified archive; raw data, API keys, `.env`, sensitive files remain excluded.

## Actual SSD audit — no external API

| Observation | KR (daily) | US (weekly, survivor-affected) |
|---|---:|---:|
| Requested cutoff | 2026-10-02 | 2026-02-26 |
| Data starting | 2026-06-04 | Week of 2025-01-20 |
| Last observed period | 2026-10-02 | Week of 2026-02-23 |
| Latest raw observation | 2026-10-02 | 2026-02-26 |
| Observed periods | 83 days | 58 weeks |
| Observed securities | 2,909 | 499 |
| Bars | 238,462 | 28,441 |
| **Internal gap events** | **0** | **0** |
| First observed after window start | 32 | see JSON |
| Last observed before final period | 36 | 1 |
| Suspended/no-trade bar rows | 12,043 | 0 |
| Historic universe PIT certified | **false** | **false** |

**Interpretation:** A vendor observation sequence without gaps is not a complete market universe. Whole-market missing sessions need an independent exchange calendar. Missing prior histories, delisted companies, permanent-ID mappings, corporate actions and true source retrieval vintages remain unaudited. The current-constituent US cache is **survivorship biased** and unsuitable as a certified backtest universe.

## Executed commands and tests

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_continuity_audit.py tests/test_local_backup.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py

PYTHONPATH=src python3 -m eraleader audit-continuity \
  --market KR --as-of 2026-10-02 --days 120 --out output/continuity_kr_20261010
PYTHONPATH=src python3 -m eraleader audit-continuity \
  --market US --as-of 2026-02-26 --days 400 --out output/continuity_us_20261010
```

- **205 collected / 205 pytest PASS / 0 FAIL** (187 baseline + 17 new continuity cases + 1 backup allowlist case).
- Validated both KR and US derived reports with `backup-local`, `verify-backup`, `restore-backup`; restored report cadence, period count, certification flags matched source. KR final (cadence-aware) backup `output/continuous/continuity_kr_cadence_v2_20261010.zip`; US `output/continuous/continuity_us_verified_20261010.zip`. The earlier KR archive was retained, never overwritten.
- The backup/restore path test exposed an older KR JSON schema lacking cadence metadata. Re-running KR under current code and creating a fresh archive fixed the verification mismatch without deleting historical archives.
- Original `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine` unmodified; no source/API connection and no real leader certification.

## Next genuine blockers

1. 2_2/2_5: independently attested historical listed universe, permanent security identity changes, delisting proceeds, corporate-action revisions and official trading calendar for **whole-market missing periods**.
2. 5_4/5_5: mature, blindly evaluated real forward labels for `frozen_holdout.py` and proof of model freeze/independent clock.
3. 6_5: physical reboot/unplug test, optional off-device backup. Removable SSD recovery is simulated/tested in code, not yet hardware-validated.
