# 176 — 날짜별 Kiwoom 수급·KRX 거래량 실측 기반 KR 수급 임시 연구10점 + 5요소 입력 연결

**2026-10-14 KST · 개발 ID 3_5·4_1·6_2 · feature/kr-marketwide-search-20261014**

## 개발 이유·완료

- 앞선 175 단계에서 실제 키움 모의/demo 3개 종목(006110,417840,446540) 날짜별 수급 20관측행과 KRX 원본 거래량 각 20개 날짜를 SHA/종가/PIT 경계로 검증했다. 기존 연구단계의 실제 5요소 입력은 가격500, 실적38, 수급 점수0이었음.
- 신규 `src/eraleader/marketwide_flow_research_score.py`는 기존 **`marketwide_dated_volume.evaluate_exact_volume`을 각 종목에 대해 새로 실행하여 원래 Kiwoom dated receipt·공식 KRX volume overlay SHA·동일 관측일 거래량을 재검증**한다. 실제 자료 5/5·20/20 기간 모든 날짜 및 양의 분모를 요구하고, 저장된 5/20 기관·외국인 비율은 원 순매매 주수와 분모로 다시 계산해 6자리 소수까지 일치하는지 검사. 날짜 한 개라도 결측/원천 변조·미래 응답·시장 SHA·주권 ID가 틀리면 연구점수 발행 전 차단.
- **임시 연구 고정규칙 V1 (예측/성과 검증 안 됨):** 5개 관측일의 (외국인 순매매/같은5일 총거래량% + 기관 순매매/같은5일 총거래량%)를 F5, 20개를 F20이라 할 때, `research_flow10 = clip(5.0 + 0.5 × (0.60 × F5 + 0.40 × F20), 0, 10)`, 소수4자리. 중립점5, 주수 거래량 대비 변화폭에 0.5배 변환이 연구용 규칙. 미래 적중률/시장수급 전체 횡단면 보정·기업행동 PIT·상장주식수/유통주식수/비교업종 점수는 미검증. **정식 `flow_score_10` 확보가 아니라 `research_score_10`라는 별도 속성**, `formal_flow_score_10_available=false`.
- 3종목 실물 결과: 006110 삼아알미늄 **8.0409**, 417840 저스템 **7.8648**, 446540 메가터치 **4.3062**. 이 숫자로 매수·매도·대장주 순위·CONFIRMED/POTENTIAL 승격을 단정하지 않음.
- 신규 CLI `scripts/derive_marketwide_flow_research.py`는 정확한 3개 `CODE=/absolute/official_volume_overlay_manifest.json`을 명시 입력하여 소스별 실제 수급 정합을 재계산/임시점수 생성. 외부 API, 인증키, 원본 SHA 수집·브로커 주문 0. 새 `output/research_flow10_assessments/KR_20261013_<version>.json` canonical SHA/계산 산식·일일 시장원본 출처·최초 평가 실제시각+원본 영수증 SHA와 함께 버전 발행, 기존 파일 불변. 고정 산식 메타 위조/점수 변조·재발행 충돌/미래시각 거절.
- 이어서 기존 SHA 잠금 `partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_PARTIAL_500.json`을 **읽기전용**으로 가져와 내부 500종목 중 해당 세 주권의 `components.flow`에만 임시 연구점수 연결. flow receipt에는 보관 새 점수연구 source SHA와 실제 평가시각, `provider=KR_FLOW_VOLUME_HEURISTIC_V1_NOT_VALIDATED`. 원래 가격·실적·공백 industry/competitiveness 및 PIT=false는 그대로. `decision_at_utc`는 원래 source build 시각보다 **늦은** 새 연구평가 실제 수신 시각으로 설정. 새 `output/partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_FLOWV1_<version>.json` 별도 불변 판본, 이전 PARTIAL_500 파일 bytes 변형0.
- **이미 2026-10-14에 등록된 Stage4 state_history SQLite를 동일 날짜에 다른 성분으로 덮지 않음.** 이번 기능은 `_validate`의 입력 구조/시장 SHA·타임스탬프·수급 receiver-contract 재검증까지만 수행하고, `StateHistory.record`의 당일 이력·이전 전략송신을 변경하지 않음. 다른 날짜 실제 시장 source가 들어오면 새 의사결정일에 forward-only 변경 가능.
- 기존 `operations_overview.py` 메뉴에 SHA/고정산식/비정식 연구 경고 확인을 통과한 가장 최근 `research_flow10_assessments`로부터 세 종목을 표기. 과거 평가시점과 시장 관측일을 분리 표기하며 공인 leader0/실주문0. 점수 외부투자순위로 노출 금지.

## 실물 T5DATA 검증 근거

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/derive_marketwide_flow_research.py \
  --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --base-partial-assessment "$PWD/output/partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_PARTIAL_500.json" \
  --code-overlay "006110=$PWD/output/official_krx_volume_overlay/KR_20261013_006110_8742c0253d72/manifest.json" \
  --code-overlay "417840=$PWD/output/official_krx_volume_overlay/KR_20261013_417840_b9d5afd97e0a/manifest.json" \
  --code-overlay "446540=$PWD/output/official_krx_volume_overlay/KR_20261013_446540_040d5e557e11/manifest.json"
```

- 실측 output `output/verification_logs/flow_research_real_20261014.json` (Git excluded):
  - `output/research_flow10_assessments/KR_20261013_a2514d74812e5df3.json`; 점수 006110 8.0409 / 417840 7.8648 / 446540 4.3062.
  - `output/partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_FLOWV1_2080b026ae1bef1e.json`; 총 500 관찰종목 중 가격500 / 실적38 / **수급 연구3** / 산업성장0 / 경쟁력0. `decision_at_utc=2026-10-14T09:41:07.083086+00:00` (10월14일 현지 18:41 KST), historical PIT=false.
  - 기존 `factor_selection_pipeline._validate`로 실제 시장원본 SHA·새 투입성분·평가 시각 수용 PASS, StateHistory DB는 **본 작업에서 미수정**. 공식 leader0/중립 실주문0.
  - 실제 운영 `render_local_operations.py --project "$PWD"` 일반 명령을 사용해 로컬 readonly 화면 점수3개 출력 PASS. 원래 full leaderboard/주문 경로 및 NewsCatalystOS 역할은 변경0.
- 테스트 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_marketwide_flow_research_score.py tests/test_official_partial_factor_bridge.py tests/test_factor_selection_pipeline.py tests/test_marketwide_dated_volume.py tests/test_marketwide_dated_flow.py tests/test_official_krx_volume_overlay.py tests/test_operations_overview.py tests/test_operations_dated_flow_all_stocks.py -q --tb=short --junitxml=output/verification_logs/flow10_research_combined_20261014.xml` → **103 PASS / 0 FAIL / 0 ERROR / 0 SKIP**, 원본 불변·누락분모·부분기간·응답데이터 점수/산식 조작·future time/중복·Stage4 500개 부분 점수 계약, Python compile/git staged diffcheck PASS. 전체 2,000개 장기 회귀/실제 predictive performance 검증은 별개.

## 다음 핵심 개발

1. 기존 5요소 **산업 성장성20·기업 경쟁력20**에 실제 전향적 issuer/산업 데이터와 연동. 기존 DART 업종코드만으로 산업 성장 점수 또는 3사 peer relative rank를 지속 경쟁우위로 가정하지 않는다.
2. 기간별 flow10은 연구 고정규칙으로는 구현됐지만 **실전 사용 승인/미래 성과 검증 전**이며 전체시장 2,761종목 중 3종목만 증거 확보. 실제 여러 시장일 누적 후 안정성 평가 및 유통/기업행동 신뢰도 확인.
3. EraLeader는 중립 JSON 송신만 담당, 특정 매매전략 프로젝트 수신 연결·실주문은 사용자 추후 결정까지 범위 제외. Git 기능 브랜치 결과는 원본 `main`에 자동 병합하지 않음.
