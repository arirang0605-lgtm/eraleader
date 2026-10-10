# EraLeader 5_3 — retrospective negative-label horizon gate

2026-10-10 KST. Applies only to the research-only `validate-discovery` evaluator, not live screening. Existing 5_5 sealed-holdout protections stay unchanged.

## Reproduced defect and correction

The standalone retrospective evaluator previously counted `is_future_leader=false` as a false discovery after outcome publication, even if its observation lasted just 30 of 180 required days. This prematurely penalized early alerts.

A negative label now requires `mature_on >= recorded_at + horizon_days`, using actual `recorded_at` when present, otherwise `first_seen`. An immature negative stays censored and increments `premature_negative_labels_censored`. Exact-horizon maturity is accepted after publication. Existing positive outcomes remain unchanged.

## Repro commands

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_discovery_negative_maturity.py tests/test_discovery_metrics.py tests/test_prospective.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
python3 scripts/check_git_safety.py
```

The regression first failed 3 cases against the original evaluator. An older synthetic negative fixture also needed correction to represent a full 180-day window. New cases test early negative censoring, exact maturity, and actual-registration cutoff.

**Limits:** Historical issuer, original source clock, labels and completeness are not independently certified. Research metrics never imply verified future leader skill, official PIT, or investment performance. Raw market data and authentication remain local; external APIs deferred.
