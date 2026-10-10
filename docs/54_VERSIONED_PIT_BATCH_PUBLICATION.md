# 6_1 / 6_5 — Immutable, recoverable two-market PIT research publication

> 2026-10-10 KST. Applies ONLY when running explicit `batch --integrate-pit-research`. The default price-only batch, launchd schedule, existing PIT/strategy engines and readonly T5DATA price source are preserved.

## Defect and safety boundary

The previous input preflight (see `docs/53_BATCH_BOTH_MARKETS_PREFLIGHT.md`) prevented errors found while loading KR/US inputs from making any output, but a failure after writing the KR state/SQLite or reports and before completing US could leave partially visible files. There was no durable, single commitment mark for readers.

The implementation in `src/eraleader/pit_publication.py` provides a **single-filesystem generation-and-pointer publication protocol**, not a globally atomic filesystem/SQLite transaction or independent PIT source attestation:

1. Acquire exclusive non-blocking publication lock at `--out/.pit_publication.lock`; confirm the **previous** published pointer and every artifact checksum if one exists. Refuse to build on a corrupted current generation.
2. Use SQLite read-only `connection.backup` to copy `--out/offline.sqlite` and any prior published `state.sqlite`, `prospective.sqlite`, `state_history.sqlite` into an isolated `--out/.pit_staging/<uuid>` directory. Legacy root state may also be migrated on first published generation. No edits to the original input/source SQLite.
3. Run the existing **two-market PIT preflight** and full price+industry+fundamentals+WATCH+six-reports+preview batch entirely inside that temporary generation. Any KR/US analysis/persistence error aborts without changing `current_pit_batch.json`. Temporary staging is removed on handled failure; an abnormal power-off may leave ignored orphan directories.
4. Verify the output contains both KR and US, 6 reports, non-certified PIT results, actual HTML paths and the three finished state ledgers. Rewrite manifest's temporary internal paths to immutable final-generation paths. Generate `PUBLISH_RECEIPT.json` with SHA256 and length for **every** generated artifact (including SQLite, reports, HTML and manifest), with `official_leaders=0` and `pit_certified=false`.
5. Flush content and folders (`fsync`), `os.replace` complete stage to `--out/pit_generations/<uuid>` on the same filesystem; then atomically replace **one** `--out/current_pit_batch.json` pointer (including receipt digest). This last pointer rename is the **commit point**; failed publication leaves prior current generation selected.
6. `PYTHONPATH=src python3 -m eraleader verify-pit-publication --out ...` reads only the current pointer, refuses path symlinks, verifies the generation receipt and all artifact SHA256/lengths, checks exact KR+US manifest status and all certification flags. Orphan or incomplete generations are never considered current. The CLI returns `NO_PUBLISHED_PIT_RESEARCH_GENERATION` if no pointer exists.

**Reader rule:** In explicit PIT research mode, consumers must use `verify-pit-publication` / `verify_pit_publication(root)` to find the current result. The old unversioned root `batch_manifest.json`, if from a legacy run, is NOT an authoritative current PIT publication. Price-only batch remains unmodified and continues its original output layout.

## Actually executed checks

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_pit_publication.py \
  tests/test_batch_pit_integration.py tests/test_batch.py tests/test_local_schedule.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

Synthetic unit/integration tests cover: correct dual-market version publishing, repeat idempotent candidate registration and first-generation preservation; deliberate failure **after KR writes but while US executes**; first-ever failure with no pointer; deliberately failing the **atomic pointer replacement** after new generation creation (old current stays valid; incomplete/orphan generation ignored); corrupt published Markdown report refusal and no new run; pointer or directory symlink attack refusal; orphan with no pointer; CLI inspection, falsified certification rejection and output-root symlink refusal. Default price-only schedule/batch integration regressions also run unchanged.

**Actual T5DATA smoke (real historical prices + explicitly synthetic PIT financial/issuer fixture, NOT a real leader performance test):** `output/batch_pit_integration_20261010` at KR 2024-09-01, US 2024-08-30, `--days 550 --top 5` published first immutable generation `0a5c6f456abb4a29a69f3f437fb093d4`, then generation `34692ba18db6467c927f97261127e719`; each was verified by `verify-pit-publication` with **25 artifact checks**; previous first generation's receipt SHA unchanged, zero duplicated new WATCH registrations, 2 markets, 6 Markdown reports, US deferred 1. **0 official leaders, 0 messages, 0 external APIs.** Raw T5DATA Parquet unchanged.

## Limitations and next work

This does not protect against an attacker replacing the *entire* writable local source, pointer and all hashes (no external timestamp signing), nor against two different physical volumes requiring cross-filesystem atomic commits. A crash before pointer replacement can leave a **garbage-collectable orphan** in `pit_generations`; consumers never display it as published. A crash after pointer replacement but before the success response may leave the new generation legitimately published, and the next verifier must inspect the pointer. Actual forced-power-loss, reboot and physical SSD disconnect tests have **not** been run. Long-term retention/garbage collection and backup of immutable published generations require a separate carefully tested policy. Real historic corporate events and independently sourced future labels remain absent. Full stage 1_1–6_5 completion and true future leader forecasting accuracy **NOT certified**.
