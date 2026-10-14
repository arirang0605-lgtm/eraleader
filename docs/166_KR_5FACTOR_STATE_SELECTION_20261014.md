# 166 — KR 5요소 평가 → 후보 상태 → 범용 JSON 송신 파이프라인

2026-10-14 KST · 개발 ID **3_3 · 3_4 · 3_5 · 4_1 · 4_2 · 4_3 · 4_4 · 6_4** · feature/kr-marketwide-search-20261014

## 운영 기능과 기존 코드 재사용

- 신규 `src/eraleader/factor_selection_pipeline.py`, `scripts/run_factor_selection.py`. 기존 공식 KRX 전체시장 `marketwide_kr.json`의 canonical SHA/시장일/가격 상대강도·수급·재무 부분충족 자료를 **기존** `marketwide_live_search._source/prepare_search`로 다시 검증한다. `StateHistory`의 5요소 `evaluate_leader_state`, `strategy_handoff.state_history_handoff/publish_versioned_handoff/verify_handoff`를 **그대로 재사용**한다.
- 입력이 없으면 실제 커버리지 확인만 하고 `FIVE_FACTOR_INPUT_NOT_AVAILABLE`을 반환한다. **정식 후보/실전 신호 0**, 상태 SQLite·수신 JSON·파일 원장을 생성하지 않는다. 이 모드로 현재 로컬 KRX의 실제 5요소 준비도를 바로 확인할 수 있다.
- 5요소 점수 파일이 있으면 **명시적인 `--factor-input`으로만** 실행한다. 필수 `eraleader.kr_5factor_local_assessment.v1` 구성: `market=KR`, `market_session`, `source_marketwide_sha256`, `decision_at_utc`, `certification_level=LOCAL_ATTESTED_RESEARCH_NOT_INDEPENDENT_PIT`, `factor_rows`(1~500). 각 종목은 6자리 실제 KRX code/ticker, `issuer_id_validated_as_of=true`, `components` (`industry[0,20]`, `competitiveness[0,20]`, `earnings[0,25]`, `momentum[0,25]`, `flow[0,10]`) 또는 null, 동일 키의 `factor_receipts` (각 nonnull 요소마다 `sha256`, `available_at_utc`, `provider`)와 `evidence` (financial/universe/corporate-action/issuer PIT, fundamental growth, confirmed weekly trend Boolean) 포함. 전체 JSON은 canonical content SHA256로 봉인. 예시 형식은 `tests/test_factor_selection_pipeline.py` 참조.
- **미래정보/중복 차단:** `available_at_utc <= decision_at_utc <= now`, 원본 시장 관측일 <= 의사결정 날짜. `decision_at_utc`보다 늦게 조합한 시장/수신데이터 금지; 과거 거래일에 오늘 수신을 소급 기록하지 않음. 판정 `as_of`는 **실제 의사결정의 한국 날짜**를 사용하여 전일 종가를 오늘 판단에 사용하는 것을 허용한다. 원시장보고 `stale_warning=true`인 오래된 자료에서는 신규 후보 승격 차단.
- **검증되지 않은 값은 N/A:** 시장 보고서에서 기존 가격 강도와 입력 25점 momentum 반드시 일치, DART 현재 코드 매칭·시장 코드/issuer 식별·요소 점수범위·영수증시각/서명 필드·중복 종목을 검사. 요소 하나라도 null이거나 필수 PIT 불충족이면 기존 `evaluate_leader_state`가 WATCH 또는 PAUSED, 정식 후보 승격 금지. 불완전 부분지표를 강제로 100점으로 환산하거나 기관 매매주수를 임의의 수급10점으로 변환하지 않는다.
- **POTENTIAL/CONFIRMED/WEAKENING 실행:** 완전 입력(명시 연구자료)이 제공되면 기존 5요소 상태기계로 후보 → 2회 확인 → 약화를 구분하고 별도 **`output/five_factor_local_state_history.sqlite`**에 같은 날짜 멱등/이전 기록 불변 등록, `output/qualified_research_outbox/KR_YYYYMMDD_<sourceSHA>.json` 발행. 종목 자체가 누락됐다고 자동 EXIT/매도하지 않으며 **오늘 5요소 재평가가 없는 기존 후보는 오늘 송신 목록에서 제외** (`stale_prior_candidates_suppressed`로 수량 표시). 원장 이력은 보존한다. 원래 가격 WATCH 연구원장/기존 outbox와 파일 완전 분리.
- **중요한 구분:** 현재 새 factor receipts/issuer flags는 **로컬 작성자가 주장하는 provenance 계약**만 검증한다. 독립 공적 최초공시시각·상장/합병 issuer PIT·성과는 증명하지 않는다. 따라서 완전 입력으로 계산된 상태도 **`LOCAL_ATTESTED_RESEARCH_NOT_INDEPENDENT_PIT` 연구용 후보**, 정식 공인 대장주 인증 아님. 범용 JSON에 `factor_assurance`, `factor_assessment_sha256`, `source_market_session`, 최초 `first_local_decision_at_utc`, `formal_leader_certified=false`·`historical_independent_pit_certified=false` 명시. `execution_authority=false`, `order_instruction=false`, `broker_account=null`, `research_only=true`. 특정 수신 프로젝트·주문 엔진 결선하지 않는다.

## 실제 실행/검증

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/run_factor_selection.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json
# 향후 인증·동시점 검증된 5요소 파일을 준비한 뒤에만:
# python3 scripts/run_factor_selection.py --project "$PWD" --marketwide-report <verified_kr_marketwide.json> --factor-input <locally_attested_factor_snapshot.json>
```

- **실물 KRX 2026-10-13**: 2,761 관측, 과거 가격상대강도 2,263, CFS49/산업49, 2요소 연구평가38, 동일시장 일치 수급1. 5요소 자료 입력 없음 → `FIVE_FACTOR_INPUT_NOT_AVAILABLE`, 연구 선발0, 공인 확정0/실주문0. CLI EXIT0, **새 생산 5요소 상태 원장 생성0**. 이 수치는 현재 공식 5요소100점 전체시장 완성도를 뜻하지 않는다.
- **실제 Mac SSD 합성 E2E**: 별도 Git ignored `output/verification_logs/fivefactor_synthetic_e2e_20261014`에서 5요소 서명 JSON → Stage4 SQLite write → POTENTIAL 연구후보 1 → receiver-neutral JSON checksum 읽기/주문권한false 확인, EXIT0. 이는 **합성 입력**으로 기능을 검증한 것일 뿐 시장의 실제 대장주 선정 성공이 아니다.
- 테스트 `PYTHONPATH=src python3 -m pytest tests/test_factor_selection_pipeline.py tests/test_state_history.py tests/test_strategy_handoff.py tests/test_marketwide_handoff_bridge.py tests/test_marketwide_live_search.py tests/test_marketwide_auto_refresh.py -q --tb=short --junitxml=output/verification_logs/fivefactor_scope_final_20261014.xml` → **86/86 PASS, failures0/errors0/skipped0**, 실제 3거래일 POTENTIAL→CONFIRMED→WEAKENING, 첫일 이후 새 증빙없는 이전후보 송신제외, 룩어헤드/중복/주권 불일치/서명변조/부분점수·PIT 보류 검증. Python compile/diffcheck PASS. 전체 장기 수천 테스트·실전 성과검증은 이번 작은 기능 인수조건에서 미실행.

## 남은 실사용 핵심 과제

1. 실제 동시점 산업 성장/기업 경쟁력/PIT 매출·이익·기관외국인 수급을 각 공급자 커넥터가 위 요소 파일과 원시 provenance에 입력하도록 연결. `--factor-input`을 임의 가공값으로 채우지 않는다.
2. 장기 회사/주권 ID와 역사 PIT·기업행동·정정공시 근거를 독립 교차 확인하여 LOCAL_ATTESTED와 공인 검증 가능한 차이를 판정. 현재 우선순위는 실제 사용 가능한 발굴 속도/후속 추적 구현.
3. 신규 검증된 공급자에서 매일 5요소 갱신 가능해지면 현재 5요소 선택/상태/중립 outbox를 정기 운영 배치와 연결. 후속 전략 프로젝트·실거래 주문 연결은 사용자 결정까지 보류.
4. 기존 분리 feature 브랜치는 `main`에 자동 병합하지 않음. 본 프로그램은 MarketOS와 독립. 외부 CycleOS backtest 폴더·공식 원자료·키·기존 정상 코드는 수정하지 않음.
