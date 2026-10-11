# EraLeader 5_3/5_5 — 최초 WATCH와 native score 최초 기록의 사전 Top-K 동결

> 2026-10-11 KST. 한국·미국 미래 대장주를 조기 발굴하기 위한 오프라인 전향 평가 준비 기능. 실제 PIT 및 독립 공급자 인증/실전 미래 성과는 미검증. D-017 API 연결 후순위, D-021 물리 SSD 재연결·재부팅 마지막.

## 실제 미완료 기능 보완

기존 모듈의 WATCH 최초등록, 4요소 native 숫자 점수 최초기록, Top-K 선동결 및 후행 outcome 검열은 각각 작동했지만, 그 사이에 모델별 전체 WATCH 후보군에서 순위를 자동 생성하는 연결이 없었다. 과거 WATCH를 numeric score의 등록시각으로 오인하거나 점수가 낮은 양성 WATCH를 수작업으로 제외하면 시점 누출/성과 과장이 가능했다.

신규 src/eraleader/native_topk_freeze.py 및 tests/test_native_topk_freeze.py 와 기존 cli.py 명령 freeze-native-topk:

- 같은 market/model의 모든 긍정 prospective_signals와 대응하는 실제 research_screen_observations를 read-only SQLite로 비교. 하나라도 빠지거나 변조된 경우 중단. WATCH ID 및 원본 payload SHA는 기존 검증기 재사용.
- 모든 긍정 WATCH 회사에 이미 최초 등록된 numeric score가 있어야 하며 K는 그 회사 수 이하. 외부 수기 점수는 허용하지 않고 기존 4요소 원본 공식/feature bytes SHA/evidence hash를 전수 재계산. 원본 시장 데이터와 양성/음성 회사 상태 원장 변경 없음.
- frozen ranked candidate의 score_computed_at/recorded_at은 WATCH 첫날의 임의 시점이 아니라 실제 native score first-WRITE 시각 사용. WATCH->score first write 60분 이내, 신규 점수 기본 24시간(허용 범위 1~168시간) 이내. 현재 OS clock 이전에 기록됐던 것만 사용.
- snapshot/seal 시각은 신규 동결 실행의 현재 OS clock; CLI에서는 소급 시점 주입 불가. label ID·시장·horizon·긍정 판정 기준 원문 SHA256은 결과가 생기기 전에 의무 동결. 평가용 미래 outcome은 선정 시 입력되지 않는다.
- 한 모델의 모든 처음 기록된 WATCH와 점수 증거 ID/SHA를 결합하여 native_cohort_binding에 scope + 해시 저장. 원본 데이터/점수 DB/원본 라벨은 로컬에만 둔다.
- preflight 중 원본 WATCH 데이터 또는 피처 파일이 바뀌면 첫 번째 감사만으로 동결되지 않도록 원본 DB witness 재수집·feature SHA/공식 재감사 2회·leader 규칙 바이트 SHA 재검사, 이후 O_EXCL 새 파일 발행.

## 실행 계약(경로는 예시이며 실제 live 데이터가 있다는 뜻 아님)

먼저 첫 WATCH를 기록하고 동일 모델로 compute-rank-scores를 실행해 native 첫 점수를 등록한다. 매회 새 시장 시점은 고유 모델 버전을 부여해 과거 점수를 소급 덮어쓰지 않는다.

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader compute-rank-scores \
  --market KR --model-version kr-unique-cohort-v1 \
  --features-dir output/live/feature_evidence \
  --watch-ledger output/live/prospective.sqlite \
  --score-ledger output/live/native_rank_scores.sqlite

PYTHONPATH=src python3 -m eraleader freeze-native-topk \
  --market KR --model-version kr-unique-cohort-v1 \
  --features-dir output/live/feature_evidence \
  --watch-ledger output/live/prospective.sqlite \
  --score-ledger output/live/native_rank_scores.sqlite \
  --label-definition-file output/live/leader_rule.json \
  --label-definition-id LEADER_CRITERION_FIXED_V1 \
  --horizon-days 180 --k 20 \
  --out-file output/live/frozen_native_topk.json

PYTHONPATH=src python3 -m eraleader audit-native-rank-scores \
  --frozen-rank output/live/frozen_native_topk.json \
  --score-ledger output/live/native_rank_scores.sqlite \
  --features-dir output/live/feature_evidence \
  --watch-ledger output/live/prospective.sqlite \
  --out output/live/derived_reports
~~~

## 합성 회귀·제한사항

- 신규 유닛과 기존 rank/registry/outcome 모듈 회귀. 정상 KR/US 동결, 최초 WATCH와 최초 numeric score 시각 구분, 양성 WATCH 전체 커버리지, 원장/원본 feature 수정 거부, score 값 해시까지 같이 위조한 공격의 공식 재계산 실패, 선동결 규칙 ID/내용, 재봉인 O_EXCL, stale/후행 score, CLI OS clock, 뒤늦은 피처 수정을 주입한 TOCTOU 실패 포함.
- 로컬 SHA/OS timestamp는 독립 발행기관 공인 시각이 아님. 동시 피처/원본 변화 차단도 프로세스 외부 모든 공격을 원자적으로 막거나 방지자 독립 제3자 공증이 되는 것은 아니다.
- 법적 영구 issuer/class/industry, 상장폐지·현금/분할·배당 원본, 한국/미국 전체 상장우주 당시 PIT, 실전 신규 WATCH, 수개월 후 성숙된 독립 outcome, precision/false positives/lead time은 아직 데이터가 없다. 공식 리더 확정 0; 적중률 N/A.
- Public Git에는 코드/테스트/문서만, SQLite/feature 원문/미래 라벨/원시 시세/키·유료 데이터 미업로드. API 호출·물리 SSD 분리/재부팅은 수행하지 않는다.

다음: 실제 공식 원천 issuer/security-class/기업행동 PIT 수급 계약(2_2/2_5), 신규 코호트 실전 첫 등록 누적과 성숙된 source receipt 및 5_5 outcome 통계. 기존 정상 코드 CONTINUE.
