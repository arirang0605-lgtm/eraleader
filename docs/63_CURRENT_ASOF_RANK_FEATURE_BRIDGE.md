# EraLeader 3_4 / 3_5 — 현재 시점 PIT 재무·가격 → 자체 계산 점수 입력 연결

> 2026-10-10. prepare-rank-features는 **연구용 입력 문서 생성기**입니다. 기업 가치·대장주 지위, 역사적 산업구성 및 공식 PIT는 인증하지 않습니다.

## 이어붙인 기존 기능

- offline-features가 만든 offline_research_v1와 run이 만든 PRICE_ONLY_RESEARCH_NOT_PIT_CERTIFIED 랭킹 JSON만 읽습니다. **CycleOS 백테스트 원자료를 수정하지 않으며 API도 호출하지 않습니다.**
- 동일 시장(KR/US)·현지 거래일·당시 분석시각·run_id 재계산·현재 스냅샷 생성시각을 비교합니다. 3일을 넘은 과거 시점 스냅샷은 새 현재형 랭킹 입력으로 위장할 수 없습니다.
- 당일 종가의 이용 가능 시간을 한국 15:40 이후, 미국 현지 16:10 이후로 보수적 가정합니다. 같은 날 종가를 장중 판단시각에 사용하는 누출은 거절합니다. 거래소 휴일/정정시각의 공식 증명은 아닙니다.
- 업종 내 **3개 이상** 품질검사를 통과한 동종 기업의 유효 백분위 그룹에 속하면서 동시에 가격 화면에 6개월 모멘텀이 실제 존재할 때만 네 요인(매출 YoY, 영업이익 YoY, 산업매출 YoY, 6개월 가격수익)을 생성합니다. 누락/중복/미래/오래된 값은 대체하지 않고 보류 또는 거절합니다.
- 생성 available_at은 **실제 출력 당시 OS UTC 시각**입니다. 과거 재무 사업기간이나 추정 공개시각을 첫 점수 등록시각으로 위장하지 않습니다.
- 새로운 출력 디렉터리의 최상단 JSON은 기존 compute-rank-scores의 정확히 일치하는 4요인 입력 계약을 따릅니다. _meta/source_manifest.json은 원본 파생 JSON 두 개와 산출 feature 문서들의 SHA256, 누락 이유, 원천 신뢰 한계를 기록합니다. 입력 파일을 덮어쓰거나 기존 WATCH를 자동 승격하지 않습니다.
- 가격 모듈의 run 결과는 TOP-N 일부 종목일 수 있고, 가격 티커 ↔ PIT 영구기업 ID 결합은 **독립 공인되지 않은 단순 연결**입니다. 산업 3개 동종기업이나 가격 관측이 부족하면 새 숫자형 랭킹 입력을 만들지 않습니다. 조정주가/배당/상폐/공시 공개시각도 공급자 원천으로 인증되지 않았습니다.

## 실제 실행 예시 (외부 API 미사용)

output/은 Git에서 제외되어 있습니다. 아래 날짜는 예시이며 **해당 시점이 지금으로부터 현지일 3일 이내여야** 연구용 입력 생성이 허용됩니다.

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader prepare-rank-features \
  --offline output/offline_kr_features.json \
  --price output/kr_latest.json \
  --features-dir output/prospective_rank_inputs_kr \
  --model-version research-native-v1 --min-peers 3
PYTHONPATH=src python3 -m eraleader compute-rank-scores \
  --market KR --model-version research-native-v1 \
  --features-dir output/prospective_rank_inputs_kr \
  --watch-ledger output/prospective.sqlite \
  --score-ledger output/rank_scores.sqlite
~~~

**주의:** 두 번째 명령은 같은 모델·영구ID의 실제 첫 WATCH 등록이 이미 존재하고, 등록 후 60분 이내인 경우에만 점수를 기록합니다. 소급성 자료는 현재 발굴 성능으로 인정하지 않습니다. prepare-rank-features 자체는 어떤 WATCH도 생성하지 않습니다.

## 테스트 기준

PYTHONPATH=src python3 -m pytest tests/test_rank_feature_bridge.py -q

합성 다중 업종/가격결측/US DST/PIT 가용시각/변조한 run_id/중복 티커/NaN·마이너스 100% 모멘텀/과거 데이터 소급/기존 출력 불변/CLI 실제 OS 시간/기존 WATCH·점수원장 이어붙이기 검증. 실제 시장 미래 수익률과 독립 PIT 출처 공증은 아직 미실행·미인증.

**D-017:** 데이터 API는 1~6단계 로컬 구축 후. **D-021:** 실제 물리 SSD 재연결 및 맥북 재부팅 검증은 API 연결 후 최종 단계.
