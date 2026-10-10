# EraLeader 5_3 — 숫자형 랭킹 점수·입력 특성 SHA 최초 기록 원장

> 2026-10-10 KST, 오프라인 개발. **이 기능은 숫자 점수가 실제 로컬 원장에 언제 처음 쓰였는지를 검증하지만, 점수의 실제 계산 여부·제3자 원천 발행시각·대장주 예측 성능을 공인하지 않는다.**

## 해결 대상

기존 `ProspectiveRegistry.prospective_signals`는 WATCH 양성 이벤트 ID와 최초 등록시각을 불변 원장에 기록하지만 연구용 `full_score=None`이다. 한편 `ranked_discovery`는 외부 제공된 숫자 점수를 모델·K·기간과 함께 봉인한다. 두 기록을 ID·등록시각으로 연결하는 `ranked_registry`만으로는 **사후에 입력한 숫자 점수가 당시 존재했는지** 알 수 없었다.

## 실제 작성 시각을 보존하는 별도 점수 원장

- `src/eraleader/rank_score_ledger.py`: 새로운 `rank_scores.sqlite` 안의 `rank_score_events` 테이블에 **(시장 KR/US, 모델버전, 영구 종목ID)별 최초 숫자 점수**를 기록한다. 사용자 입력 점수는 미래 라벨이 없는 0~100 유한 수치로 제한한다. 동일 모델·종목의 정정/덮어쓰기는 거부하고, 동일 입력 재실행은 원래 최초 저장시각을 바꾸지 않는다.
- `record_rank_scores(..., clock=None)` 형태의 로컬 기록기는 기본적으로 **실제 OS UTC 시각**을 사용하며, 단위테스트에만 clock을 주입한다. CLI에서는 시각 지정 인자가 없다. 점수를 기존 WATCH `full_score` 필드에 사후 삽입하지 않는다.
- 각 등록 전에 `prospective.sqlite`를 **SQLite read-only**로 열어 같은 시장·모델·영구ID의 원래 양성 WATCH `signal_id` 계산식·canonical payload JSON·SHA256·원본 시점·출처 run ID·연구 전용 상태를 재확인한다. 데이터 관측일이 등록일보다 3 현지일 이상 뒤늦은 과거 backfill이면 제외한다. **WATCH 최초 기록 후 60분 이내**에 점수를 처음 기록하는 것으로 제한한다(임시 로컬 품질 규칙이며 시장 예측 성과로 최적화한 값이 아님). 실제 시각에 너무 늦은 점수는 과거의 전향적 점수였던 것처럼 기록할 수 없다.
- 입력 `scores.json` 행 필수 키: `security_id`, `score`, `feature_file`, `feature_sha256`, `features_available_at`. 자료 특성 JSON 파일은 `eraleader.rank_feature_document.v1`의 `market`, `model_version`, `security_id`, `available_at`, `features` 형식(실측 수치 특성만). 실제 파일 SHA256과 행 SHA/이용가능 시각을 대조하며, future/outcome/label/realized 등 이름의 정보는 금지한다. 원천 timestamp와 값은 공급자 공인 자료가 아니라 로컬 입력 주장이다.
- 저장한 숫자 점수·WATCH 최초 등록 신호/원본 해시·특성 파일 해시·feature available/점수 기록시각의 전체 payload는 canonical JSON과 내부 SHA256으로 묶인다. 오프라인 SQLite 트랜잭션으로 후보 여러 개를 동일 배치에 처리하며 같은 등록을 다시 실행해도 시각을 바꾸지 않는다.
- `audit_frozen_rank_scores(frozen_rank, rank_scores.sqlite, feature_dir)`: 기존 봉인 rank의 영구 종목ID·모델·수치 점수가 기존 점수 원장에 있는지 확인, 실제 첫 **점수 저장시간이 rank snapshot 이후면 차단**. 점수 원장과 별도 입력 특성 JSON 실제 파일의 해시를 재검사한다. 누락/수치 변조/원천 파일 수정이면 구체적 blocker. 원장 원본을 수정하지 않는다.

## CLI와 동결 사전검사 연결

```bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader record-rank-scores \
  --market KR --model-version local-screen-v1 \
  --scores output/research/scores.json \
  --features-dir output/research/feature_inputs \
  --watch-ledger output/research/prospective.sqlite \
  --score-ledger output/research/rank_scores.sqlite

PYTHONPATH=src python3 -m eraleader audit-rank-scores \
  --frozen-rank output/research/frozen_rank.json \
  --score-ledger output/research/rank_scores.sqlite \
  --features-dir output/research/feature_inputs \
  --out output/research/derived
```

기존 별도 CLI `python3 -m eraleader.ranked_discovery freeze`에도 `--score-ledger`와 `--features-dir`를 **동시 입력**하도록 옵션 추가. 반드시 `--prospective-ledger`가 함께 있어야 한다. 임시 랭킹을 먼저 생성해 (1) 원본 WATCH 첫 등록 신호의 ID·시각 확인, (2) 숫자 점수가 rank snapshot **이전에 실제 점수 원장에 기록**됐는지와 수치·특성 SHA가 맞는지 모두 검사한다. 실패하면 **최종 봉인 파일을 아예 만들지 않는다.** 기존 독립 freeze(신규 ledger 옵션 없음)는 이전과 동일하게 비인증 연구용으로 남는다.

`rank_score_{kr,us}_research.json`은 **파생 감사 JSON만** 기존 안전 백업 allowlist에 추가했다. 실제 `rank_scores.sqlite` 및 원본 특성 파일·미래 라벨·키는 공개 Git/파생 ZIP에 포함하지 않는다. 실제 원장은 SSD 보존 및 별도 운영 백업 계획 대상이다.

## 검증 범위와 한계

- `tests/test_rank_score_ledger.py`: 첫 점수 기록·시각 불변·원본 WATCH 신호 연결·모델/종목 불일치·3일 이상 backfill·60분 이후 뒤늦은 점수·미래 특성·결과 유출 가능 메트릭 거부·파일 SHA 변조·원장 SHA 변조·랭킹 점수 변경·rank보다 늦은 실제 숫자 점수·WATCH/score 둘 다 확인하는 guarded freeze·기존 기본 freeze 보존·CLI 실제 OS 시각과 파생 JSON SHA ZIP 복원.
- 실전 현금·기업행동·PIT 데이터 소스 인증·실제 주도주 조기예측 성능은 **아직 0건 인증**. 소스도 지금은 별도 제출 JSON과 OS 로컬 시각이므로 독립 서명/공증이 필요하다. `score_computation_independently_verified=false`, `original_feature_publication_independently_attested=false`, `real_leader_prediction_certified=false` 계속 불변.
- 사용자 D-017 API 연결은 로컬 단계 완료 후, D-021 물리 SSD 분리·재연결 및 Mac 재부팅은 API 연결 **이후 최종 단계**에서만 검증.
