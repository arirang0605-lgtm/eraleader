# 172 — KR 키움 날짜별 20관측 수급 최초 영수증 보관 + KRX 거래량 일자 정확 매칭

2026-10-14 KST · 개발 ID **3_3 · 3_5 · 6_2** · 브랜치 `feature/kr-marketwide-search-20261014`.

## 구현

1. 기존 `SharedBrokerAPI/src/shared_broker_api/client.py:ReadOnlyClient('eraleader')`의 **모의 데모 read-only `investor_flow_page`**, 기존 `marketwide_flow_coverage`의 종목별 원 누적5·20 수급보고를 그대로 활용. 공통 API/키움 Secret·기존 `main`·다른 프로젝트/가격캐시 소스 파일에 수정 없음.
2. 신규 `src/eraleader/marketwide_dated_flow.py`, `scripts/capture_marketwide_dated_flow.py`: 기본 **사전 확인 전용(API0)**, `--apply-demo` 옵션으로 **기존 저장된 수급20관측이 있는 명시된 코드 1종목**에만 키움 demo 조회 1페이지 실행. 응답 원문 SHA/모드/demo/종목/시장일/주문권한 비활성/first gateway receipt 시각을 검증, 최근20 관측 날짜와 signed 순매매 주수만 정규화한다. 각 5·20개 외국인/기관 합이 원래 보관된 SHA 검증 수급보고와 **정확히 일치**해야만 신규 `output/marketwide_dated_flow/KR_YYYYMMDD_<marketSHA16>_<CODE>.json`을 O_EXCL 불변 보관. 응답을 전체 byte로 재현하는 공식 기관 PIT 인증이 아닌 **20행 날짜·수량 요약+원본페이지 SHA 증인**임. 이전 report 변경, 응답일자/합계 불일치, provider 오류는 저장 전 중단. 재실행: 기존 artifact SHA 재검증, 동일 코드는 추가 API 호출 0. 오리지널 공급자 full-page raw는 별도 법적 public timestamp 인증 아님.
3. 신규 `src/eraleader/marketwide_dated_volume.py`, `scripts/check_marketwide_dated_volume.py`: 기존 `data.read_market_bars`에서 **날짜와 코드가 동일한 5·20개 캐시 거래량 바**를 검색. 해당 기간의 개별 수급일자 5/20 모두 원시 거래량에 정확히 존재하고 양수인 경우에만 `net investor shares / exactly matched daily traded shares ×100%` **연구용 비율** 계산. 하루라도 없으면 기간 전체 비율 N/A, 결측 날짜 목록과 확보한 거래량 바 수량을 유지한다. 카운트/합계가 같다고 실제 거래소 holiday·issuer 조정 PIT를 인증하지 않는다. `formal_flow_score_10=None`, `orders_enabled=false`, `formal_leaders=0` 고정.
4. 연구 결과 `output/marketwide_dated_volume/KR_YYYYMMDD_<CODE>_<SHA12>/{manifest.json,index.html}` 버전/원본 cacheSHA·flowSHA 기반 O_EXCL 원자 발행, 앞 판본 유지, canonical JSON/HTML 변조 차단. 기존 `scripts/render_local_operations.py --marketwide-dated-volume-code CODE --marketwide-source-root ROOT` opt-in으로 운영 대시보드 링크 추가, `operations_overview.py`가 SHA/HTML 실제 일치 확인한 결과만 표시. 기존 가격 WATCH20/5요소 원장·JSON neutral sender·launchd 설정 불변.
5. 출력은 개별 키움 demo 주권별 **날짜별 수급 데이터가 실제 확보된 종목에 한함**. 외부 실거래/선정점수/PIT·조정주가·기업행동/과거 IPO 생존성 공식 인증, SMS 전송 0.

## 실제 T5DATA 성공 검증

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/capture_marketwide_dated_flow.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --code 417840 --apply-demo
python3 scripts/check_marketwide_dated_volume.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --code 417840
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
  --marketwide-dated-volume-code 417840
```

- 실제 이전 키움 모의 2026-10-13 시장일 저스템 **417840**의 SharedBrokerAPI `investor_flow_page` **1회 read-only 호출**: 최근20개 날짜별 기관·외국인 순매매 수량 저장, 이전 검증된 외국인 합계5=427294 / 기관5=55054 / 외국인20=1232905 / 기관20=266006 **완전 일치**. 실제 첫 gateway 수신시점은 2026-10-14 이후, 10월 13일 매수시점의 자료였다고 주장하지 않음.
- 실제 read-only CycleOS-Lab marcap-2026 20개 관측행 중 기간 내 **15개만 거래량 일치**; 최근 5개(2026-10-13/12/08/07/06)는 캐시에 거래량 바가 없어 5행 0/5, 20행 15/20. 따라서 **투자가능 수급5·20 거래량 대비 비율=N/A**, 오더0. 새 `output/marketwide_dated_flow/KR_20261013_a59b7ecdfaa0b707_417840.json`와 `output/marketwide_dated_volume/KR_20261013_417840_a82296481453/{manifest.json,index.html}` immutable SHA 완료. 운영 `output/verification_logs/dated_volume_real_ops_20261014.json` 및 보관본 최종 HTML 링크 `kr_marketwide_dated_exact_volume` PASS.
- 모의 synthetic 20개 일자와 동일 캐시 바를 만든 독립 기능 테스트는 날짜 20개 모두가 일치하면 **외국인5 10.20%, 외국인20 10.95%, 기관20 -1.95%** 등 연구 비율 계산 정상. 5개 중 일부/20개 중 일부 결측이면 구간 비율 N/A 처리, 이미지/구형 보고서와 별개 검증.
- 변경 영향 테스트 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_marketwide_dated_flow.py tests/test_marketwide_dated_volume.py tests/test_marketwide_volume_alignment.py tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_marketwide_flow_diagnostics.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/marketwide_dated_witness_scope_20261014.xml` **79/79 PASS, FAIL0/ERROR0/SKIP0/exit0**. Python compile/git diffcheck PASS, 새 실물 유효한 날짜/합계/누락 조사 완료. 전체 수천개 테스트 반복 생략(변경범위 조건 충족).
- 이전 main 미커밋 `native_first_capture.py`·문서/공시유형 분류 PNG, 다른 기능 브랜치, SharedBrokerAPI 원본/API 키, CycleOS Lab read-only 가격캐시/기존 SQL 변경0.

## 다음 개발

1. **최신 KRX 거래량 바**를 2026-10-13 이상으로 갱신해 정확한 날짜별 수급 대비 거래량 연구 비율 계산. 원가 캐시 역사적 신뢰와 기업행동/유통주식수는 별도 검사.
2. 성공 저장된 다른 키움 모의 종목(006110,446540)에서 날짜별 행을 같은 방식으로 증분 보관, 대상 확대는 API 사용량과 운영판정이 필요.
3. 실운영 수급 모듈은 원시 날짜 정합·분모 검증 전 정식 flow10/리더100점으로 승격 금지. 뉴스/공시 강한 재료는 NewsCatalystOS에서 담당하므로 EraLeader는 기존 결과 인터페이스만 소비.
