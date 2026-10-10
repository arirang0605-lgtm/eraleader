# 2026-10-10 — 2_2 / 2_5 independent source-vintage audit contract (offline)

## Implemented, not certified

`src/eraleader/source_vintage.py` introduces `audit-source-vintage`, a **fail-closed local source manifest** contract for historical listing, actions, prices, total-return indexes, fundamentals, or industry data. It SHA256-hashes the *actual original JSONL bytes* against a local manifest, validates source IDs/record revisions/issuer identity, and checks timezone-aware record availability and retrieval timestamps. Duplicate source-vintage declarations, duplicate record revisions, malformed records, future records predating their claimed retrieval, invalid hashes, symlinks and source traversal paths are rejected. The two distinct date roles are preserved: `known_at` (memberships/actions) vs `available_at` (prices/fundamentals/industry/index).

**Critical limitation:** a manifest may declare that a file was obtained in 2024 even if it was created now. Neither SHA agreement nor a claimed publisher ID proves the publisher, past retrieval time, license, completeness, independent feed identity or correct delisting cash consideration. The audit therefore always emits `historical_pit_certified=false`, and `source_timestamp_independently_attested=false`, `official_historic_universe_verified=false`, `corporate_action_completeness_verified=false`, `delisting_settlement_verified=false`.

When `retrieved_at > decision_at`, every earlier record in that file is marked **retrospective backfill** and contributes **zero as-of-eligible rows**, even when its embedded `known_at` is earlier. Future corrections/revisions are counted separately as excluded; multiple pre-decision revisions of one `record_id` count as only one potentially usable record, with superseded revisions reported. This is a research integrity check, not permission to feed backfilled vendor data into a historical decision. Source contents are never emitted in the audit JSON or included in Git. Stage-2 import is **not** silently made trustworthy merely because this command passes.

## Manifest and local CLI

Manifest `source_vintage_manifest_v1` has `sources: [{source_id, publisher_id, vintage_id, market: KR|US, kind, file, sha256, retrieved_at}]`. `file` is an ordinary, non-symlinked JSONL basename in the same directory. Each JSONL row includes `source_id`, `record_id`, `revision` (positive integer), `security_id` (or `industry_id` for industry rows), and an observation day (`valid_from`, `effective_on`, `period_end` or `session` as appropriate). Membership/action rows require timezone-aware `known_at`; other kinds require `available_at`. This contract is deliberately separate from raw CSV/Parquet vendor imports; adding a vendor adapter must preserve actual retrieval provenance.

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_source_vintage.py -q
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m eraleader audit-source-vintage \
  --manifest output/source_vintage_trial_20261010/manifest.json \
  --decision-at '2024-04-04T18:00:00+09:00' \
  --out output/source_vintage_trial_20261010
python3 scripts/check_handoff.py
```

Output `source_vintage_audit_research.json` records only declared provenance, counts, SHA verification and caution flags; never the raw records or any claimed verified trading signals. Reproduction requires the local manifest and source JSONL files, located under Git-ignored `output/`, plus the code and tests.

## Remaining first priority

Obtain an **independently timestamped** archival source and historic listing/delist and corporate-action data before certifying source PIT. Prove publisher identity, original retrieval logs and licensed feed revision chains; measure missing-issuer/omitted-event coverage and delist settlements, then compare *actual* independent adjusted-return series. Afterward run a frozen prospective 5_4/5_5 holdout on mature actual outcomes; still no outside API or live alarms in this local-only sprint.
