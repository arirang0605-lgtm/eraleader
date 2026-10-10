# EraLeader 5_3 — 영구 종목 ID·WATCH 실제 등록시각 ↔ 봉인된 상위 K개 랭킹

> 2026-10-10 KST, 로컬 전용 연구 감사. 이번 기능은 **랭킹의 종목 ID/시각을 실제 ProspectiveRegistry에 연결**한다. 원장에 숫자형 점수가 저장된 적이 없으므로 **그 점수가 당시 존재했다거나 진짜 미래 대장주 예측력이라고 인증하지 않는다**.

## 기존 코드 보존, 빠졌던 연결만 추가

기존 `ranked_discovery.py`는 `security_id`, 점수, 자기선언된 `features_available_at`/`score_computed_at`/`recorded_at`으로 순위를 봉인하고 top-K 결과를 검증한다. 기존 `prospective.py`는 성장 스크린을 통과한 실제 WATCH 기록을 `prospective.sqlite`에 최초 등록시간과 SHA256으로 보존한다. 이전에는 두 기능이 독립 동작해 **원장에 없는 기업을 임의의 과거 기록 시각으로 순위에 추가해도** 기존 top-K 평가가 그대로 작동할 수 있었다.

신규 `src/eraleader/ranked_registry.py`의 `audit_ranked_watch_registry`는:

1. `ranked_discovery._frozen`으로 봉인된 랭킹의 해시·모델 버전·K·점수/후보 순서·시각을 검증한다. 미래 결과 라벨은 **읽지 않는다**.
2. 기존 원장 `prospective.sqlite`에 **SQLite read-only mode**로 접근하며, 동일 시장·동일 모델 버전의 양성 WATCH 기록에 대해 등록 ID 계산식, 원문 canonical JSON, SHA256, 기업 ID, `source_run_id`, 실제 관측시각/등록시각, WATCH 상태(`full_score=None`, 확정 리더 아님)를 모두 재검증한다. 변조/손상 원장은 허용 가능한 데이터로 취급하지 않고 오류 처리한다.
3. 등록 시각보다 현지 거래일 기준 3일 초과 이전을 관측했던 **역사적 소급 실행**을 제외하고, 랭킹이 봉인되기 전에 실제 등록된 첫 양성 WATCH만 신뢰 가능한 로컬 연결 대상으로 잡는다.
4. 동결 순위의 종목 영구 ID가 해당 원장에 없는 경우, 다른 모델 버전의 기록을 빌린 경우, `recorded_at`이 실제 최초 등록보다 앞서거나 뒤로 재기록된 경우, feature available/score computed 시각이 실제 등록 이후인 경우 **구체적 차단 사유**를 출력한다. 절대 날짜를 인위적으로 앞당기거나 점수·미래 라벨을 만들어 보충하지 않는다.
5. 일치한 원장 등록 ID·원본 payload SHA를 파생 JSON에 포함하되, 유료 시세·원문 신호 JSON·미래 라벨과 점수 입력 원본은 복사하지 않는다. 검증은 읽기 전용이고 `ranked_registry_{kr,us}_research.json`만 로컬 백업 허용 목록에 추가한다.

CLI 예시:

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader audit-ranked-registry \
  --frozen-rank output/ranked_registry_trial_20261010/ranking.json \
  --ledger output/ranked_registry_trial_20261010/prospective.sqlite \
  --out output/ranked_registry_trial_20261010/derived
```

### 무엇을 증명하지 못하는가?

**기존 양성 WATCH 원장은 `full_score=None`이다.** 즉 랭킹의 숫자형 점수는 당시 양성 WATCH의 immutable payload에 존재하지 않는다. 그러므로 두 기록의 종목 ID·등록시각이 모두 일치해도 **`original_watch_has_independently_recorded_numeric_score=false`**, `rank_score_availability_independently_attested=false`, `issuer_universe_pit_certified=false`, `prospective_discovery_skill_certified=false`, `official_leader_promotions=0`을 항상 유지한다. 다른 파일과 로컬 시각의 자기 선언은 과거 원천 PIT 독립 인증이 아니다. 소급 동결은 `retrospective_freeze=true`로 표시한다.

실전 진짜 rank@K 검증으로 발전시키려면 **점수를 계산한 그 시점에 score+feature-source hash+model의 복구 가능한 append-only 원장을 함께 등록**해야 한다. 기존 `WATCH`의 `full_score=None`을 사후 숫자로 채우는 것은 금지다.

## 실행·검증

```bash
PYTHONPATH=src python3 -m pytest tests/test_ranked_registry.py \
    tests/test_ranked_discovery.py tests/test_prospective.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

`tests/test_ranked_registry.py` 합성 테스트에는 동일 모델·등록시각 연결, 원장에 없는 랭킹 종목, 등록시각 앞당기기, 모델 버전 불일치, 소급 신호, 원장에서 WATCH 행 소실, checksum 변조, 다시 해시한 가짜 full_score, 원장 signal_id 변경, 봉인 SHA 위조, symlink/누락 원장, 미국 DST, 뒤늦은 봉인, CLI/파생 JSON 백업 복원이 포함된다. 테스트 시각·종목은 합성 고정값이며 실제 발견 성과가 아니다.

## D-021/원천 제한

D-017에 따라 외부 API는 나중 연결. D-021에 따라 물리적 T5DATA SSD 분리·재연결과 맥북 재부팅 시험은 API 연동 후 최종 단계로 이월한다. 독립 발행자 공시 timestamp, 상장폐지·기업행동 현금 정산, 당시 전체 상장종목군과 실제 성숙된 미래 라벨이 없으므로 대장주 발견 정확도는 현재 인증 불가.


## 명시적 랭킹 봉인 전 WATCH 원장 사전검증 (추가)

`src/eraleader/ranked_discovery.py`의 기존 독립 CLI에 `freeze --prospective-ledger <prospective.sqlite>` **선택 옵션**을 추가했다. 옵션을 지정하면 새 영구 랭킹 파일을 작성하기 **전에**, 임시 파일에 연구용 랭킹을 구축하고 `audit_ranked_watch_registry`가 모든 종목 ID·시장·모델·첫 양성 WATCH 등록시각을 확인한다. 불일치가 1건이라도 있으면 `ValueError`로 실행을 중단하고 **최종 봉인 파일은 생성하지 않는다**. 전 종목의 ID와 최초 등록시각이 정합적일 때만 기존의 O_EXCL(기존 동결 파일 덮어쓰기 금지) 방식으로 결과를 작성한다. 사후에 가짜 점수를 포함한 랭킹이 정상적인 원장 기반 동결이라고 통과하는 상황을 막는 **필수 로컬 계약 검사**다.

```bash
PYTHONPATH=src python3 -m eraleader.ranked_discovery freeze \
  --input output/ranked_registry_trial_20261010/scores.json \
  --market KR --snapshot-at '2026-04-02T08:05:00+00:00' \
  --model-version synthetic-real-registration-v1 \
  --horizon-days 180 --k 1 \
  --prospective-ledger output/ranked_registry_trial_20261010/prospective.sqlite \
  --out output/ranked_registry_trial_20261010/registry_preflight_seal.json
```

**중요**: 이 옵션도 숫자 점수가 실제 WATCH 원장에 당시 보존됐음을 인증할 수 없다. 별도의 동시 작성된 score registration ledger를 미래 작업에서 구현해야 한다. 기본 `freeze` 독립 연구 모드는 이전 동작 그대로 유지하며 인증 false. 관련 추가 합성 테스트 4개는 연결이 정확한 경우만 파일 생성, 미등록 종목/모델 불일치일 경우 파일 미생성, 기존 O_EXCL 반복 금지, 이전 기본 모드 보존을 검증한다.
