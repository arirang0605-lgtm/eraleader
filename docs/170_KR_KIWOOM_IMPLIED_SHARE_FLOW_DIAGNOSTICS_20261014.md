# 170 — 실제 Kiwoom 수급 5·20관측 + KRX 시총·종가 기준 추정 주식수 비율

**일자:** 2026-10-14 KST. **개발 ID:** 3_3 · 3_5 · 4_1 · 6_2. **분리 브랜치:** feature/kr-marketwide-search-20261014.

## 이번 개발 목적과 연결

- 직전 `169_KR_MARKETWIDE_SHARED_KIWOOM_FLOW_BATCH_20261014.md`의 정상 `marketwide_flow_batch.py`와 `marketwide_flow_coverage.py`가 저장한 **실물 키움 모의 read-only 기관·외국인 선택주권 5·20관측 순매매 주수**를 버리지 않고, 같은 시장일 KRX `marketwide_kr.json`의 기존 종가와 시가총액으로 **추정 전체발행주식수 대비 순매매 주수 비율**을 파생한다.
- KRX `close>0`, `market_cap>0`, `market_traded=true`일 때 **추정 총주식수 = 당일 KRX 시가총액 ÷ 종가**. 외국인/기관 5·20관측 누적 순매매비율(%) = `100 × 누적 순매매 주수 × 종가 ÷ 시가총액`. 소수점6자리, 누락 분모/원수급은 `N/A`. 양기간 모두 순매수, 모두 순매도, 혼합/0만 방향 분류.
- **이 수치는 기업 공시 상장주식수의 독립 검증값이 아니며 유통주식수(free float), 5·20거래일 거래량 대비 매집률, 실제 보유주주 증가율, 과거 수급 PIT 인증이 아니다.** 5/20는 키움 제공 *관측행* 수이고 독립 거래소 영업일/수정주식수·상폐 검증은 아직 없다. 5요소 정식 `flow_score_10`, 산업/경쟁력 점수, 투자 1~20위, 자동매매 신호는 **N/A**, 공식 대장주0/주문0 유지.
- 신규 `src/eraleader/marketwide_flow_diagnostics.py`: 앞선 기존 `marketwide_live_search._source`의 source SHA와 `summarize_flow_coverage`의 소배치 SHA/시장일·종목ID를 교차 확인해 `eraleader.kr_selected_flow_implied_share_proxy.v1` canonical SHA JSON·안전 HTML을 `output/marketwide_flow_diagnostics/KR_<시장일>_<sourceSHA16>_<batchSHA12>/`에 새로운 폴더로만 원자적 게시한다. 동일 원본의 반복 게시 `ALREADY_PUBLISHED`, 손상 원본/출판본 덮어쓰기 거부. 외부 네트워크/실계좌/주문0.
- 기존 `scripts/render_local_operations.py`에 `--marketwide-flow-diagnostics` 명시 opt-in 추가(기존 `--marketwide-source-root` 필요). `operations_overview.py`는 SHA와 HTML 완전일치, source 시장일, 표시권한 false을 확인한 새 비교화면 링크를 운영 메인에 추가한다. 모듈/기능을 중복 재작성하지 않음.

## Mac T5DATA 실물 E2E

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' \
  --marketwide-flow-diagnostics
```

- KRX 2026-10-13 종가/시가총액 + 키움 모의 2026-10-14 최초수신 연구용 수급 **3종목**에 실제 적용. `output/marketwide_flow_diagnostics/KR_20261013_a59b7ecdfaa0b707_19a48c607209/{manifest.json,index.html}`; 전체 수급3, 추정 분모 가용3, `flow_score_10=None` 모두.
- **실측 참고(연구용)**: 삼아알미늄(006110) 외국인 20관측 추정 총주식수 대비 -0.642201%, 기관 +1.943200%; 저스템(417840) 외국인 +5.372912%, 기관 +1.159235%; 메가터치(446540) 외국인 -0.497440%, 기관 +1.010691%. 이는 실제 지분 변화·시장참여자 매집률이 아니며 특히 저스템의 5.37%를 *정식 수급10점이나 매수신호*로 사용하는 것은 금지.
- 실수급 원장 변경0, 기존 산업 비교·부분 5요소500 WATCH·선정0·중립 가격WATCH20 송신·실주문0. 메인 운영 HTML 및 신규 HTML `127.0.0.1` HTTP GET 각각 **200**. 일반 명령에는 실행 없음(명시적 opt-in).
- **변경 테스트**: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_marketwide_flow_diagnostics.py tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_operations_overview.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_handoff_bridge.py tests/test_sector_peer_flow_research.py tests/test_kiwoom_investor_flow.py -q --tb=short --junitxml=output/verification_logs/marketwide_flow_normalized_scope_20261014.xml` → **118 PASS, errors0/failures0/skips0, exit0**. 새 집중 단위8 PASS, 실물 결과 확인 및 Python compile/git diffcheck PASS. 전체 수천 건 회귀/유통주식수 공급자 독립 비교는 이 모듈 영향 범위 밖에서 미실행.
- 보호: 원본 `/Volumes/T5DATA/eraleader` main 미커밋 native_first_capture.py/PROJECT_STATE/DECISIONS 및 사용자 원본 미수정, SharedBrokerAPI/MarketOS/NewsCatalystOS/CycleOS 재사용 캐시 수정0, 실제 원시 수급 JSON과 대시보드 생성물은 Git 제외.

## 다음 핵심 개발

1. **정확한 발행주식수/유통주식수, 주권 분할·증자/감자·상장폐지 정보**와 Kiwoom·KRX 과거 일일 거래량의 동일 거래일 자료를 확보해 실제 수급기간별 분모/유통주식수 기반 정규화 모델을 연결. 장중/공시시각 조작 없이 최신 신호만 등록한다.
2. 산업성장20·경쟁력20 요인은 현재 DART 일부기업의 동종 재무 순위뿐이라 N/A. 독립 산업 수요/매출/주요 수주 및 기업 경쟁우위 자료의 공식 원천 연결 필요. 5요소 실제 충족 이후 기존 Stage4 리더 상태판정·프로젝트 중립 JSON 발행 완성.
3. 테스트와 실물 기능 우선, 전체 수천건 회귀/원본 main 병합은 변경 영향·미커밋 보존 후 수행. 실전 운용 진척률 구 38%/99% 추정치 사용 금지.
