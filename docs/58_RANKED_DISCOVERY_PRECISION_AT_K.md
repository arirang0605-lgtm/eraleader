# 5_3 — PIT-guarded frozen ranking and research precision@K

2026-10-10 KST. Offline-only additive module `src/eraleader/ranked_discovery.py`.
The baseline `discovery_metrics.py` already reports aggregate research precision and lead time; it did **not** bind a predetermined, ordered top-K list to a specific model/snapshot cutoff. This change introduces that **distinct** research feature without modifying old selection or live screening code.

## Input / outputs

`python3 -m eraleader.ranked_discovery freeze --input <candidates.json> --market KR --snapshot-at '<ISO UTC offset>' --model-version '<version>' --horizon-days 180 --k 20 --out <fresh_holdout.json>`

Input candidates: JSON array of objects with **exactly** `security_id`, `score` (finite 0–100 research-only value), `features_available_at`, `score_computed_at`, `recorded_at` (timezone-aware ISO timestamps). Explicit chronology contract: `features_available_at <= score_computed_at <= recorded_at <= snapshot_at <= local freeze clock`. Research future labels and hindsight returns are forbidden input fields. Permanent IDs must be unique. Ties break lexicographically by ID. Deterministic full ranking, pinned K/horizon/model, actual freeze time and SHA256 of canonical JSON saved with exclusive-create semantics; repeating the command cannot overwrite an existing seal. Only local file digest integrity is established — the author's timestamp or the availability of the initial features is **not independently attested**.

`python3 -m eraleader.ranked_discovery evaluate --freeze <fresh_holdout.json> --outcomes <separate_future_labels.json> --evaluated-at '<ISO UTC offset>' --out <new_research_result.json>`

Outcomes are a **separate file**, with `security_id`, boolean `is_future_leader`, `mature_at`, `outcome_available_at` and for positive outcomes `leader_start_at` (all times ISO offset aware). No label can enter the original snapshot. Evaluation checks frozen SHA and ranking, pinned cutoff, publication time >= maturity and evaluation cutoff, KR/US local trading-calendar **date** semantics and US DST. A late/onset-on-same-day leader is **not an early hit**. Unpublished and immature labels remain **censored**, never auto-fail. Negative labels maturing before the full predeclared horizon remain censored, even if published. Unknown candidate labels remain in the frozen top-K denominator. Labels for candidates outside the frozen list cannot increase scores.

Metrics: `early_hits`, `known_failures` (including late), `censored`, `precision_at_k_on_known` (null if no mature known labels), `conservative_precision_at_k_floor = early_hits / selected_count`, and `median_early_lead_days` from actual rank snapshot to later leader onset. The conservative floor assigns unresolved outcomes no hit **for a lower bound only**, not as false labels. Recall@K is **null** without independent full historical universe and labels. `requested_k` may exceed the candidate universe; denominator is actual `selected_count`, never phantom K.

`retrospective_freeze` flags a file first sealed over 60 minutes after its stated snapshot; `evaluation_as_of_precedes_actual_seal` flags historical replay for an earlier evaluation cutoff. In both cases accuracy remains purely research, not a prospective prediction. Local SHA does not provide independent trusted time stamping and cannot prevent a party from replacing both JSON content and checksum. **Always** `independent_pit_or_outcome_certified=false`, `real_leader_prediction_certified=false`, `official_leader_promotions=0`. No live ranking is changed. Without actual historical sources / market-cleared cash settlements or independently logged prospectively registered outcomes, there is **no verified real stock leader hit rate**.

## Reproduction

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_ranked_discovery.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

The additive 38 synthetic test cases cover deterministic ties, sealed non-overwrite, future features and forged registration, JSON hash tampering and even rehashed reordered lists, exact 30-day maturity for negative labels, late onset, publication censoring, extra unknown outcomes, KR/US DST dates, symlinks, invalid clocks, CLI output. Research fixtures are synthetic, not realized market accuracy. The existing `CycleOS-Lab_BacktestEngine` is not modified. No live API, broker, message or SSD hardware reconnection is involved.

## Outstanding

1. Connect rankings exclusively to an independently archived real `prospective.sqlite` registration and locally certified availability contract; avoid claiming today's ad hoc research JSON ranks were contemporaneously known in the past.
2. Attach independently proven listed/delisted issuer universe, splits/dividends/cash corporate-action settlements and original publication timestamp attestations.
3. Evaluate actual mature future outcomes and separate sealed walk-forward / untouched holdout; report top-K under multiple markets and regimes with uncertainty.
4. D-021: physical SSD removal/reconnect or Mac reboot only after external API integration at final acceptance. Continue logical corruption and archive tests in the meantime.
