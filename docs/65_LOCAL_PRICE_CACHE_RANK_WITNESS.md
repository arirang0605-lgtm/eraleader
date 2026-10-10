# EraLeader 2_5 / 3_4 — 로컬 KR/US 시세 캐시 재계산 증거

> 2026-10-10. `src/eraleader/price_cache_witness.py`와 opt-in `prepare-rank-features --price-cache-root` 추가. 공개 시세의 **독립 공급자 PIT 인증이 아니라 로컬 원본 캐시 ↔ 표시된 가격 화면의 수익률 무결성 검사**입니다.

## 기능

- 기존 `read_market_bars`를 활용하여 T5DATA의 연도별 한국 marcap 일봉, 미국 주봉 Parquet를 **읽기 전용**으로 조회합니다. 외부 API·다운로드/복제·원본 수정 없음.
- 화면에 담긴 선택된 ticker마다 마지막 종가·마지막 관측일, 한국 60/130/250거래관측(약 3/6/12개월) 및 미국 13/26/52주 전 종가를 사용해 수익률을 다시 계산합니다. 숫자 비교는 화면의 6자리 소수점 반올림 정밀도에서 수행합니다.
- 가격 파일에 `run_id`를 재해시해도 원본 캐시와 다른 수익률/종가, 최근 180일 거래정지, 종목별 부족한 최소 6개월 관측행, 가격 화면과 다른 마지막 시장일, 미래 관측과 누락 과거 종가 등은 **입력 피처가 생성되기 전에 실패**합니다.
- 복합 `prepare-rank-features` 실행 시 `--offline-ledger <offline.sqlite>`와 `--price-cache-root <read-only root>`를 함께 지정하면 **재무 PIT SQLite + 로컬 시장가격 캐시 두 출처에서 각각 다시 계산하는 옵션**이 활성화됩니다. 둘 중 하나라도 불일치면 새 결과 폴더가 만들어지지 않습니다. 옛 연구모드는 종전 동작을 보존하고 `recomputed_from_readonly_price_cache=false`입니다.
- 산출물의 `_meta/source_manifest.json`은 감사 대상 선택 종목 종가/기간수익률의 SHA256을 기록합니다. 해당 해시는 당시 거래소 공신력/조정주가/완전 종목군/상장폐지 여부를 입증하지 않습니다. 공식 대장주 승격 0건 고정.

## 명시적 로컬 실행 (현재 데이터 시점 3일 이내에만 feature 생성)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader prepare-rank-features \
  --offline output/offline_kr_features.json \
  --price output/kr_latest.json \
  --offline-ledger output/offline.sqlite \
  --price-cache-root /Volumes/T5DATA/CycleOS-Lab_BacktestEngine \
  --cache-days 550 \
  --features-dir output/strict_dual_source_kr \
  --model-version research-native-v1
PYTHONPATH=src python3 -m pytest tests/test_price_cache_witness.py -q
~~~

실행 예시는 실제 `offline.sqlite`에 시점 일치 재무자료가 있고 가격/재무 기준일이 현재로부터 3일 이내일 때만 정상 생성됩니다. 파일이 오래되었으면 별도 가격 대조 연구는 가능하지만 **지금의 신규 발굴 신호로 소급 등록하지 않습니다**.

## 기존 실제 로컬 시세 자료 검증 (이번 세션)

- Git 무시 output/kr_latest.json: KR 2026-10-02 20종목 화면, 실제 로컬 marcap 캐시에서 3/6/12개월 원시 가격 수익률 교차계산 20/20 일치. Witness SHA256: `2f7e9494dd8107bb4541efe01b1baf61eee4beb3015ae0c506618cc565cec5aa`.
- Git 무시 output/us_latest.json: US 2026-02-23 20종목 화면, 실제 로컬 미국 주봉 캐시 원시 가격 수익률 교차계산 20/20 일치. Witness SHA256: `acc0f7ba64fbfad324f50a7e86166b6cb6bbb1bef014ad79d6232f282b2fdd30`.
- 미국 캐시는 2026년 무렵의 S&P500 현재 구성으로서 과거 생존편향이 있으며, 양국 조정주가/배당/분할/상폐/전체 공식 기업 ID는 별도 원천으로 검증되지 않았습니다. 20/20 일치란 **이 특정 화면과 기존 캐시의 계산 일치**이지 모델이 대장주를 맞혔다는 뜻이 아닙니다.

## 남은 차단점

공식 KR/US 기업 식별/생존·상폐 이력, 기업행동·배당·조정주가의 독립 교차 공급자, 공시 원문 발표시각, 전향적 홀드아웃 성숙 라벨 및 실제 미래 발굴 적중률은 여전히 미인증. API 통합은 D-017에 따라 나중, 실제 SSD 탈착·재부팅은 D-021에 따라 마지막 검수 단계.
