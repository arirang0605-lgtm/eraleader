# EraLeader 3_5 / 5_3 — 계산식 SHA까지 봉인되는 로컬 랭킹 점수

> 2026-10-10 KST. 로컬 오프라인 연구 기능이며 **과거 PIT 공인자료, 독립 발행시각, 실제 대장주 적중률을 인증하지 않는다.** 기존 건강한 WATCH 코드 및 원시 시장자료 재작성 금지.

## 기존 코드와 연결

`compute-rank-scores` (`src/eraleader/rank_score_pipeline.py`)는 당시 제출된 4개 명시적 특성 `revenue_yoy`, `operating_income_yoy`, `industry_revenue_yoy`, `momentum_6m`를 고정 초기 연구가설로 정규화(각 target에 나눠 0..1로 절단)하여 동등 가중 평균 점수(0..100)를 계산한다. **이 값은 실전 대장주 공식 점수나 성과 최적화 모델이 아니다.** 기존 `rank_score_ledger.py`는 점수와 원래 양성 WATCH 신호 ID·원문 해시·최초 등록시각, 특성 JSON 해시, 최초 점수 저장 OS UTC를 보존한다.

기존 단절점은 고정 계산식 `HEURISTIC_VERSION`이 **CLI 출력에만** 존재했고 실제 점수 원장에는 계산식 메타데이터가 없었다는 것이다. 따라서 나중에 수식이나 계수를 바꿔도 기존 점수와 어떤 계산식이 연결됐는지 확인할 수 없었다.

## 새 동작

- `rank_score_pipeline.formula_provenance()`는 `HEURISTIC_VERSION`, `FORMULA_RULE`, 고정 `TARGETS`의 canonical JSON SHA256를 계산한다. 실행 결과 및 개별 SQLite `rank_score_events.payload.computation_provenance`에 `kind=LOCAL_FIXED_FOUR_FACTOR`, `formula_version`, `formula_sha256`를 저장한다. **원래 점수 이벤트와 같은 SQLite 트랜잭션 내에서** 함께 처음 기록되며, 기존 수동 입력 점수 이벤트에는 이 태그가 없다.
- `rank_score_ledger.register_rank_scores(...,computation_provenance=...)`는 이전 generic 점수 등록의 동작을 보존한다. **동일 종목·모델의 최초 외부 제출 점수는 나중에 native-computed로 위장하거나 업그레이드 불가**, 반대로 formula digest가 다른 새 점수로 최초 기록을 바꾸는 것도 불가하다.
- `audit_computed_rank_provenance`는 봉인된 rank의 모형/K/점수와 숫자 점수 이벤트의 고정 formula tag, 원본 feature 파일 SHA256, 4요인 결과 **재계산**, 실제 score first-write timestamp, 최초 WATCH 원문 신호 ID·SHA/시장/모델을 read-only로 확인한다. 원본 WATCH가 수정되거나 계산식/점수/feature 문서가 달라졌다면 blocker를 표시한다.
- 기존 랭킹 봉인 CLI `python3 -m eraleader.ranked_discovery freeze`에 선택적 `--require-native-computation` 추가. 이 옵션은 `--prospective-ledger`, `--score-ledger`, `--features-dir` 3개를 함께 요구하며 **임시 prototype에서 양쪽 원장/4요인 원천을 검증한 뒤에만 최종 파일을 생성**한다. 기본 legacy WATCH-only/수동 점수 기반 연구 CLI는 기존 계약 그대로 둔다.
- 개념상 **첫 WATCH 등록**과 **그 다음 수초 내 실제 숫자 점수 계산·저장**은 다른 이벤트다. Strict-native 랭킹 `recorded_at`은 실제 숫자 score 최초 저장시각으로 맞춰야 한다. 새 strict 경로는 WATCH의 최초시각과 event ID를 개별 점수 원장의 원본 WATCH proof로 검증하고, rank score record와 frozen rank의 `recorded_at`을 일치시킨다. 점수 계산시각이 최초 WATCH보다 이르다고 거짓 주장하는 것도 거부한다. 기존 WATCH-only 경로는 이전과 같이 rank 등록시각=첫 WATCH 시각을 검사한다. **이 두 기록의 시간을 동일하게 조작하지 않는다.**
- `python3 -m eraleader audit-native-rank-scores --frozen-rank ... --score-ledger ... --watch-ledger ... --features-dir ... --out ...`에서 파생 `native_score_{kr,us}_research.json` 생성. 이 한 개의 가벼운 요약만 로컬 안전 백업 allowlist에 추가했다. SQLite 원시 점수/특성/시장가격/미래라벨/개인키는 Git·해당 ZIP 미포함.

## 실제 검증 및 한계

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_rank_formula_provenance.py \
  tests/test_rank_score_pipeline.py tests/test_rank_score_ledger.py \
  tests/test_ranked_discovery.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

`tests/test_rank_formula_provenance.py` 신규 합성 케이스는 native 첫 기록에 공식 버전/digest 동시 저장, 외부 수동 점수의 native 위장 거부, 수동 점수 원장 사후 업그레이드 금지, payload 자체 재해시를 동반한 가짜 formula hash 검출, feature 파일 수정 탐지, 첫 WATCH보다 이른 계산시각 주장의 차단, 점수 첫 기록시각을 앞당긴 랭킹 거부, WATCH 원문 재해시 변조 거부, 실제 native 이중 사전검사를 통과한 봉인, CLI 검증 및 ZIP 복구를 포함한다.

Mac의 실제 로컬 OS 시간을 사용해 **합성 WATCH 1건 → 4요인 점수 직접 계산·첫 기록 1건 → strict native 랭킹 봉인 → 원문/점수/모델 재계산 감사 → SHA256 ZIP 복구** 수행. 버전 `eraleader.local_four_factor_rank_heuristic.v1`, formula digest `234530af8f49...`, score write clock `2026-10-10T12:37:55.085959+00:00`. 일관성 차단사유 0건, **독립 계산 및 출처시각 인증 FALSE, 확정 대장주 0건**.

**중요 제약**: formula digest/자기선언된 feature timestamp는 독립 공증이 아니고, 사용자가 소스파일·원장·프로세스시계를 모두 통제할 수 있다. 현재 코드는 불변 내부 기록의 **로컬 정합성**만 보장한다. 실제 KR/US 상장/상폐 이력, 공식 공시 발표시각·수정 이력, 법적 기업행동·현금 정산 및 충분히 성숙한 실제 미래 outcome 없이 예측 정확도나 투자성과 인증 불가. D-017 외부 API 연결은 로컬 개발 후, D-021 물리 SSD 재연결/재부팅은 API 연결 이후 최종 단계.
