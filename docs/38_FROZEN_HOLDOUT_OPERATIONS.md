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

## 2026-10-10 5_5 post-freeze negative-outcome maturity fix

- Before this fix, `evaluate_frozen_candidates` counted every already-published `is_future_leader=false` label as a false discovery even if its `mature_at` predated the candidate's complete frozen horizon. This could turn a partial-window observation into a conclusive 180-day negative.
- Negative labels now require `mature_at` (in market-local calendar days) **on or after** `recorded_at + horizon_days`, with `outcome_available_at <= evaluated_at`. A premature negative remains `censored_outcomes` and increments the new explicit `premature_negative_labels_censored` counter. Verified positive/late outcomes follow the existing checks. Exact-horizon day is accepted.
- Existing synthetic fixture B negative was revised to maturity on 2026-10-02 (after its 2026-04-02 registration + 180 days), preserving the original meaningful negative-label test. New tests: an early negative observed on 2026-08-01 stays censored; a negative maturing exactly 2026-09-29 is permitted. No existing certification state is upgraded.
- `PYTHONPATH=src python3 -m pytest tests/test_frozen_holdout.py -q` and `PYTHONPATH=src python3 -m pytest tests -q` **207 PASS/0 FAIL** (205 prior + 2 new tests). Still synthetic, not true matured real-market outcomes.

## 2026-10-10 5_4/5_5 등록원장 무결성 사전검사 보강

- 기존 `freeze_registered_candidates`가 SQLite에 있는 `payload_hash`를 검사하지 않고 해시 문자열만 동결 목록에 옮기는 문제를 수정했다. `prospective_signals`의 최초 등록 행별로 등록ID·시점별 기업ID·연구용 `WATCH` 상태·모델/실행ID·원본 canonical JSON 및 SHA256를 **동결 전에** 검증한다.
- 해시만 바꾼 셀 손상, 다시 해시한 기업ID/실행ID/공개일자 바꿔치기, 이미 `CONFIRMED` 승격된 척하는 payload, 원장 PK/신호 유형 변조를 거부한다. 첫 등록 후보뿐 아니라 **동일 모델·시장 전 행** 검사를 적용한다. 원장 불일치 시 holdout manifest를 만들지 않는다.
- 신규 합성 회귀 `tests/test_holdout_registry_integrity.py` 12개와 기존 `tests/test_frozen_holdout.py` 26개를 로컬에서 실행했다. `PYTHONPATH=src python3 -m pytest tests -q`, `python3 scripts/check_handoff.py` 재현 가능. 진짜 발굴 성과나 실제 거래소 PIT 인증이 아니라 로컬 손상 탐지 시험이다.
- **제한:** 공격자가 SQLite의 원시 JSON, 키 필드, 로컬 시각, SHA를 함께 완전 재작성하면 단일 PC 자체검사로는 구분할 수 없다. 외부 공증 타임스탬프, 신뢰할 수 있는 원천 자료, 실제 미래 성숙 라벨이 없으므로 `historic_pit_certified=false`, 확정 대장주 0건 유지한다.
