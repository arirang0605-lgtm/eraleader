# 171 — KRX·Kiwoom 수급 기간과 read-only marcap 거래량 관측일 일치 게이트

**2026-10-14 KST. 개발 ID: 3_3·3_5·6_2. 작업 브랜치: feature/kr-marketwide-search-20261014.**

## 이번 미완료 실제 기능 구현

- 신규 `src/eraleader/marketwide_volume_alignment.py`, `scripts/run_marketwide_volume_alignment.py`. 이전 완료의 SHA 검증 `marketwide_flow_coverage.summarize_flow_coverage`(SharedBrokerAPI Kiwoom 데모 저장 수급)와 `marketwide_live_search._source/prepare_search`(공식 KRX 시장관측본)을 그대로 사용한다.
- 기존 읽기전용 `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine/datasets/external_validation/marcap/data/marcap-2026.parquet`를 **변경 없이** SHA256 봉인 및 기존 `data.read_market_bars`로 필요한 수급 3개 종목/해당시장일 이전 가격 캐시만 조회한다. 원본 KRX 회사ID·시장일·수급 source SHA가 불일치하면 거부.
- 종목별 `cache_last_price_session`, `cache_matches_source_session`, 20개 이상 관측 바가 있고 가격 관측일이 같은 경우에만 캐시 자체의 `last_5/20_volume_observations`을 독립 참고 수치로 표시한다. **수급의 5/20일 관측날짜는 기존 공통 Kiwoom 요약 JSON에 남아 있지 않기 때문에**, 가격 캐시의 20개 행과 수급의 20개 행이 동일한 영업일이라고 주장하거나 두 값을 나눠 수급 강도를 계산하지 않는다. 날짜가 맞는 경우라도 `NO_DATED_INVESTOR_ROWS_TO_MATCH`, 실제 수급 대비 거래량 비율=N/A / 정식 flow10 점수=N/A.
- 캐시가 과거일이면 `PRICE_CACHE_NOT_AT_KRX_SESSION`, 현재 가격 캐시의 정확한 해당 시장일이 없으면 절대로 최신 수급의 분모로 사용하지 않는다. 결측 가격/실험 캐시는 N/A. `flow_volume_fully_aligned_stocks=0`, `flow_score_10_available=0`, `formal_leaders=0`, `orders_enabled=false`.
- `output/marketwide_volume_alignment/KR_YYYYMMDD_<sourceSHA16>_<flow-cache-hash12>/{manifest.json,index.html}`에 immutable canonical JSON SHA와 안전 로컬 HTML을 발행한다. source/수급배치 SHA·캐시 SHA로 버전화하여 이전 증거 불변, 동일 반복 `ALREADY_PUBLISHED`, 변조·잘못된 링크 차단.
- 기존 `render_local_operations.py --marketwide-volume-alignment --marketwide-source-root <saved source>` 명시 opt-in으로 운영 대시보드의 「기관·외국인 수급과 거래량 날짜 일치 보기」 링크 연결. 기존 `main`·사용자 미커밋 코드·SharedBrokerAPI·타 개발 프로젝트/API/실계좌는 변경하지 않음. 외부 네트워크 호출/매수매도 0.

## 실물 T5DATA 검증

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
 --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
 --marketwide-volume-alignment
```

- 실제 공식 KRX 가격 관측일 `2026-10-13`. 이전 수집 키움 모의 기관외국인 수급 3종목 `006110,417840,446540`, 최초 gateway 수신 2026-10-14.
- 읽기전용 marcap-2026.parquet 19,504,683bytes의 해당 3종목 **최종 실제 캐시 바는 모두 2026-10-02**, 시장관측일과 다르다. **시세일 일치0/3, 실제 5·20 수급-거래량 일자 정합0/3, 정식 수급10점0**. 기존 추정 총주식수 대비 비율이 실제 매집률이 아닌 점 유지. 보고 `output/marketwide_volume_alignment/KR_20261013_a59b7ecdfaa0b707_4d5c4ac80fd8`, 운영용 JSON `output/verification_logs/volume_alignment_real_ops_20261014.json`. canonical SHA 동일성 검사 성공, 대시보드+신규 HTML 로컬 HTTP GET 모두200.
- 단독 신규 테스트 및 기존 소배치·누적·수급비율·운영 영향: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_marketwide_volume_alignment.py tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_marketwide_flow_diagnostics.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/volume_alignment_scoped_20261014.xml` → **65/65 PASS, FAIL0/ERROR0/SKIP0, exit0**, Python compile/git diff check 및 HTML 본문 검증 PASS. synthetic marcap stale/current(현재일 일치해도 수급 관측날짜 부재시 비율 계산 금지)/일부 주권 누락/소스변조/중복·기존발행 충돌·잘못된 저장경로 검증. 전체 수천건 회귀는 이번 변경 범위 밖이므로 생략.

## 후속 실제 구현 우선순위

1. 기존 `SharedBrokerAPI.selected_flow_research`의 개별 관측일자와 공식 KRX 일별 volume을 동일 종목·거래일에 맞추는 **dated row evidence**를 증분·immutable 방식으로 보존할 것. 현재 shared gateway 결과의 5/20 합계만으론 일별 volume 비율 계산 금지.
2. 공식 KRX 가격캐시를 2026-10-13 및 이후 시장일로 증분 갱신. marcap 과거 캐시는 10/02에서 멈췄으므로 cache가 갱신되기 전 신규 분모 계산 금지.
3. 두 시계열 교차확인 후 검증된 수급/거래량 비율을 실사용 모델 검토. 유통주식수·주권분할, 산업성장·경쟁력의 독립자료가 없는 현재 정식 100점 후보로 승격 금지.
