# EraLeader 4_5 / 5_3 / 5_5 — 전향적 동종업종 점수 시계열과 교체 가설 교차검증

> 2026-10-11 KST. *당시 실제로 저장한 연구용 숫자 점수의 불변성과 두 번 연속 동종업종 우위를 검증하는 로컬 개발*. 실제 거래소 기업/산업분류 PIT 인증, 공식 대장주 확정 또는 검증된 예측력이 아닙니다. 외부 API/스크래핑 0회.

## 기존 정상 코드와 연결

기존 `rank_score_ledger.rank_score_events`는 시장/모델/영구ID별 최초 점수를 **딱 한 번** 저장합니다. 이를 덮어쓰거나 스키마를 바꿔 점수 변화인 척하면 과거 발견시점을 오염시킵니다. 한편 `watch_rotation.audit_watch_rotation`는 기존 WATCH의 양성2→음성2와 신규 동종업계 WATCH 양성2를 이용해 **업종 교체 연구 가설**을 만들어 놓았습니다. 하지만 실제 수치 점수의 동종 비교가 없으면 단순 스크린 변화와 상대적 주도력 우위를 혼동할 수 있습니다.

신규 `src/eraleader/peer_score_series.py`는 **별도** `peer_scores.sqlite`에 명시적 SCREEN 관찰 1건당 정확한 최초 시점의 계산 점수를 추가 기록합니다. 정상 `rank_scores.sqlite`, WATCH 원본, 동결 후보/평가라벨을 변경하지 않습니다.

## 점수 입력 계약 — 과거 자료 소급 불가

- `record_peer_score_series`: 실제 OS의 UTC 시계를 사용하여 `ProspectiveRegistry.research_screen_observations`의 **같은 시장·모델·종목 영구ID** 및 **등록 현지 달력일**에 해당하는 실제 WATCH 관찰을 확인. 같은 날짜에 둘 이상 관찰돼 모호한 경우 자동으로 하나를 택하지 않고 오류 처리. 관찰/등록 뒤 **60분 이내** 점수 최초 기록만 허용, 나중에 옛 연구 관찰을 오늘 데이터인 것처럼 기록하는 것 금지. 인위적 clock 지정은 함수 단위테스트에만, CLI에는 존재하지 않습니다.
- 입력은 불변 보관용 feature root 아래 `<KR/US 거래소 현지 YYYY-MM-DD>/<파일명>.json`으로 분리. 이전 날짜 폴더는 지우거나 덮어쓰지 않습니다. 각 파일은 기존 `eraleader.rank_feature_document.v1` 스키마 `schema,market,model_version,security_id,available_at,features`. 네 가지 관측치(`revenue_yoy`, `operating_income_yoy`, `industry_revenue_yoy`, `momentum_6m`)가 전부 필요합니다. 이용 가능시각이 기록시각보다 늦으면 차단. 미래 outcome/label, 누락값, NaN, 중복 키, 심볼릭 링크 파일, 불완전 파일은 차단.
- 점수 자체는 기존 `rank_score_pipeline.compute_research_score()`의 **고정 네 요소 계산식**을 그대로 재사용. 수치 가중치/식 변경 및 사용자가 사후 숫자를 입력하는 루트는 제공하지 않습니다. 이 식의 정합성은 모델 예측력과 별개이며 **검증 전 가설**입니다.
- 새 테이블 `peer_score_observations`의 PK `(market,model_version,security_id,screen_observed_at_utc)`로 기록한 최초 점수를 덮어쓰지 않습니다. 동일 입력 재실행은 최초 기록시각을 변경하지 않고, 기존 등록의 피처/점수/원본 WATCH SHA를 바꾸면 전체 트랜잭션에서 오류. 실제 UTC 기록시각과 원래 WATCH payload SHA, 원본 feature bytes SHA, pinned formula SHA, 산업ID, 당시 screen 양/음, 계산점수를 canonical JSON SHA로 보존. 일부 파일 오류면 같은 신규 등록 묶음을 부분 commit하지 않습니다.

## 실제 교체 가설과 수치 우위 대조

`audit_peer_score_advantage`는 기존 `watch_rotation.audit_watch_rotation`로 후보 가설이 만들어졌는지 먼저 확인한 뒤 별도 점수 원장+원본 WATCH SQLite를 **둘 다 read-only** 조회. 평가 cutoff 이후에 기록된 점수는 과거 평가에서 제외하고, 원본 스크린의 영구ID/모델/market/산업/양음/실제 등록시각/SHA와 저장 점수의 원본 증거를 다시 대조합니다. 원천 feature 파일을 다시 읽어 실제 SHA와 고정 공식 점수도 재계산합니다. 공급자가 나중에 파일을 바꾸면 오류 처리.

- 같은 시장·같은 산업의 기존 WATCH 명시적 음성 vs 신규 WATCH 명시적 양성이 **두 시장 현지 거래 관찰일**에 각각 점수 기록까지 연결돼야 합니다. 같은 날 점수를 두 번 찍은 기록만으로 2회로 세지 않습니다.
- 기존 WATCH 첫 약화 등록 후 신규 종목이 관찰된 기간의 같은 날 점수만 비교. 신규 후보 점수 − 기존 WATCH 점수가 **최근 두 개 매칭 관찰일 모두 5점 이상**인 경우에만 `locally_two_session_score_correlated`를 1 증가. 두 번 가운데 한 번만 우위이거나 최근 점수가 역전하면 가설을 점수로 보강하지 않습니다.
- 5점/2회는 **미검증 고정 초기 가설**이며 현재까지의 유명 대장주 승자에 맞춰 최적화하지 않았습니다. 수치형 랭킹의 독립 공시 시각, 업종별 비교 모집단의 전체 수, 기업동일성/상폐/기업행동을 인증하지 않습니다.
- 각 가설에 paired 현지 시장일, 두 점수 차이, 두 개 점수 이벤트 SHA256 및 차단 사유를 파생 JSON으로 남깁니다. 원본 feature JSON/성과 라벨의 원문은 넣지 않습니다.

## EraLeader CLI

~~~bash
cd /Volumes/T5DATA/eraleader

# 실제 작성 시각만 사용. feature-root/YYYY-MM-DD/*.json 는 현재 시장 현지 날짜.
PYTHONPATH=src python3 -m eraleader record-peer-scores \
  --market KR --model-version local-screen-v1 \
  --watch-ledger output/research/prospective.sqlite \
  --score-history output/research/peer_scores.sqlite \
  --feature-root output/research/peer_features_vault

# 로컬 원장 증거와 잠정 WATCH 교체를 두 관찰일의 점수로 대조 (읽기 전용)
PYTHONPATH=src python3 -m eraleader audit-peer-score-rotation \
  --market KR --model-version local-screen-v1 \
  --watch-ledger output/research/prospective.sqlite \
  --score-history output/research/peer_scores.sqlite \
  --feature-root output/research/peer_features_vault \
  --evaluated-at '2026-10-11T17:00:00+09:00' \
  --out output/research/peer_rotation_derived

PYTHONPATH=src python3 -m pytest tests/test_peer_score_series.py tests/test_watch_rotation.py tests/test_rank_score_ledger.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

`peer_score_rotation_kr_research.json` / `peer_score_rotation_us_research.json`만 안전한 파생 JSON 로컬 백업 allowlist에 추가. 별도 신규 원장 `peer_scores.sqlite`는 SQLite online-backup을 통한 *로컬* `backup-local` allowlist에 추가. 원래 특성 파일 폴더와 금융 시세 원본·API 키·실제 outcome label은 ZIP/Git에 복제하지 않습니다.

## 신뢰 한계 및 다음 검증

현재 실제 원장에 종목군의 완전한 전향 점수 기록이 아직 누적되지 않았다면 점수 우위 가설은 0 또는 N/A이며, 이를 음성 결과나 실패 대장주로 꾸미지 않습니다. 기능 검증에 사용한 synthetic 2026년 10월 KR / 3월 미국 DST 시장일 데이터는 미래 실제 발견 실적이 아닙니다.

`official_leader_replacements=0`, `issuer_industry_pit_certified=false`, `rank_scores_independently_authenticated=false`, `real_leader_replacement_certified=false`는 어떠한 로컬 일치성 통과에도 승격되지 않습니다. 다음은 (1) 4_5 연속 점수의 실제 운용 시간 누적과 오탐·누락 계측, (2) 5_3/5_5 사전 봉인과 이후 성숙된 미래 leader label 별도 검증, (3) 2_2·2_5 독립 법적 기업ID/업종 이력/공시 PIT·상폐 현금정산. 외부 API는 D-017대로 로컬 기능 완성 후, 물리 SSD 분리/재부팅은 D-021대로 API 후 최종 단계에만.

## 2026-10-11 실제 테스트·오프라인 합성 실행 기록

- 새로운 `tests/test_peer_score_series.py` 26개 합성 회귀: 기존 WATCH 원장 존치/별도 점수 시계열 기록, 기준일보다 늦은 점수의 과거 재사용 차단, 최근 두 관찰일 점수 우위/역전, 원본 feature SHA·점수 해시가 서로 바뀐 경우 거부, 관측 60분 초과 늦은 등록, WATCH 원장 누락, 일괄 트랜잭션 원자성, 재실행 최초 시각 유지, US 3월 EST/EDT 교차, 중복 JSON 키/비정상 시각, 실제 OS 시각으로 기록하는 CLI, KR/US·모델 격리, 이중 read-only SQLite/파생 JSON ZIP을 포함.
- `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **전체 exit 0 / 853 PASS / 0 FAIL**, `pytest --collect-only` 합산 853; `scripts/check_handoff.py` 30작업 PASS. 기존 `rank_score_ledger`, `watch_rotation`의 회귀도 함께 PASS.
- CLI 단독 실측은 `output/peer_score_rotation_trial_20261011` Git ignored **100% 합성** input. 기존 WATCH `INC` 2회 명시 약화/신규 `NEW` 2회 상승에 맞춘 특성/점수 원장을 2개 관찰일(2026-10-03, 2026-10-04)에 작성한 뒤 `audit-peer-score-rotation` 실행. 2일 연속 점수 우위 **25.0 / 34.0점**, 점수 우위 연구 가설 1개, 공식 확정/교체 0. WATCH/peer score SQLite SHA256는 감사 전후 동일. **파생 JSON 1개 + SQLite 읽기 일관 스냅샷 2개**를 서로 다른 안전 로컬 ZIP으로 SHA 검증/새 디렉터리 복원 PASS. 원본 feature 문서는 백업 대상에서 명시적 제외.
- 이는 인위적으로 작성한 단위시험 실험이며 실제 2026년 해당 일자에 미래 대장주를 발견했다는 기록 **아님**. 공식 PIT/거래소/기업행동 출처 시각·실전 leader labels 모두 미인증.
