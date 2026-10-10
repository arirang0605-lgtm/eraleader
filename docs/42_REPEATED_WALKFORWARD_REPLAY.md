# EraLeader 5_5 — repeated walk-forward replay (offline local)

2026-10-10 KST. Adds an independent, reusable *research-only* helper; no change
to the existing verified single-fold splitter, trader, data cache, model weights
or MarketOS. No Codex CLI or external API calls.

## Scope

- `src/eraleader/walkforward_replay.py`: `replay_walk_forward_folds`
  orchestrates the existing `walk_forward_split` over **2–40** strictly
  chronological windows with **1–90 full calendar-day** embargo.
- Every feature snapshot must declare the same **pinned model version**;
  every outcome must use the same **pinned label-definition ID**. Both remain
  hypotheses, not independent attestations. Mismatches fail closed.
- A later training fold can use an earlier test period's outcome **only if**
  that label became available before the later fold's training cutoff.
  Holdout candidate rows never include labels or future outcomes. Each fold
  has candidate counts, censored training counts and reproducible SHA-256s of
  the candidate and legally known training rows.
- Test windows do not overlap. Train cutoff must advance and never precede
  the previous fold's test end. A configuration hash identifies the *current*
  fold schedule; this hash alone **does not prove advance pre-registration**.
- No forecasting model is trained or tuned, no unknown historical ticker or
  listing is filled in, and no false discovery precision/CAGR is claimed.
  The final separate never-touched blind holdout remains necessary.

## Contract and reproduction

```python
from eraleader.walkforward_replay import replay_walk_forward_folds
report = replay_walk_forward_folds(
    snapshots=snapshots_with_model_version_and_as_of,
    labels=labels_with_label_definition_id_and_label_available_at,
    model_version="research-v1", label_definition_id="leader-180d-v1",
    embargo_days=7,
    windows=[
        {"train_ends_at":"2024-03-01T17:00:00+09:00",
         "test_ends_at":"2024-05-01T17:00:00+09:00"},
        {"train_ends_at":"2024-05-01T17:00:00+09:00",
         "test_ends_at":"2024-07-01T17:00:00+09:00"},
    ],
)
# status = OFFLINE_REPEATED_WALK_FORWARD_RESEARCH_NOT_CERTIFIED
```

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_walkforward_replay.py -q
PYTHONPATH=src python3 -m pytest tests -q
```

## Evidence and remaining gaps

- Synthetic historical exercise only: 4 signals and 2 windows, fold 1
  tests B/C, fold 2 tests D; B enters fold 2 training only because its
  outcome was available by May 1. Later outcomes are censored.
- Regression coverage: 19 tests for chronological window ordering, embargo
  bounds, overlap exclusion, future features, unpublished labels, model
  revision, outcome-definition changes, bool/int type traps and repeatability.
- Must not report historical PIT certification or live discovery precision.
  Independent source vintages, issuer and delisted universe, corporate
  actions and actual sealed mature outcomes still require verification.
- No additional `CycleOS-Lab_BacktestEngine` writes; this helper runs
  independently using dictionaries supplied by the caller.
