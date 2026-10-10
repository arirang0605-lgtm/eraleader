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

## 2026-10-11 — 5_3 완전한 현지 시각 horizon 음성 라벨 검열

이전 부정 라벨 검사는 `mature_at`의 거래소 현지 **날짜**만 비교해 만기일 00:01에 발표된 실패를 당일 장 마감 신호보다 조기에 확정할 수 있었다. `ranked_discovery.evaluate_ranked_precision_at_k`의 음성 만기 조건을 `snapshot_at` 현지 시각에서 정확히 `horizon_days` 일 뒤 **같은 현지 시각**으로 강화했다. 미국 DST 전후는 `America/New_York`의 wall-clock arithmetic으로 이동하고 UTC instant로 비교한다. 미래 라벨을 선별/순위 입력에 넣지 않으며, 미성숙 음성은 `censored`와 `premature_negative_censored`에 남긴다. 파생 JSON에는 `negative_maturity_not_before_utc` 경계시각을 기재하여 검증 가능하게 했다. 새 회귀 5개는 KR 만기 1분 전·정확 만기 및 US 서머타임 전환 만기 1분 전·정확 만기·UTC+30일 계산과 달라지는 사례를 포함한다.

재현: `PYTHONPATH=src python3 -m pytest tests/test_ranked_discovery.py -q --tb=short` 및 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short`. 합성자료 검열 로직이며 실제 종목의 독립 PIT·만기 성과·조기발굴 precision@K 인증이 아니다. 외부 API와 물리 SSD 분리·재부팅은 기존 D-017/D-021대로 보류한다.

## 2026-10-11 — 5_3 양성 조기적중 만기 경계 1분 오류 수정

양성 결과 `leader_start_at`의 이전 평가는 거래소 현지 **날짜 차이**만 확인해 고정된 horizon 종료 **1분 후** 시작한 리더도 `early_hit`으로 집계했다. 기존 `negative_maturity_not_before_utc`와 동일한 `snapshot_at` 현지 시각 + `horizon_days`를 **양성 리더 등장 마감시각**으로도 사용한다. `0 < lead_days <= horizon_days`와 `leader_start_at <= horizon_deadline` 두 조건을 모두 만족할 때만 early hit. 초과 시 `known_failure`이며 분자·리드타임 분포에 포함되지 않는다. 모델/점수/동결 SHA/당시 후보 목록은 변경 없음.

신규 합성 6개 회귀: KR 기한 1분 전·정시·1분 후, US 뉴욕 2026년 3월 DST 전환 포함 1분 전·정시·1분 후. **수정 전 KR/US 각 1 FAIL(조기 성공 오분류)**, 수정 후 집중 테스트 통과. 연구용 성숙 라벨·시점 경계만 검증하며 실제 과거 공개정보 PIT, 전향적 실적, 독립 조기발굴 정확도 인증은 아니다. 외부 API와 물리 SSD 탈착/재부팅은 D-017/D-021에 따라 연기.
