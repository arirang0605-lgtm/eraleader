# 167 — 실제 공식 KR 시장보관본의 5요소 부분 입력 자동 생성·상태 추적

2026-10-14 KST · 개발 ID **1_2 · 3_3 · 3_4 · 3_5 · 4_1 · 4_2 · 6_2 · 6_4** · feature/kr-marketwide-search-20261014.

## 구현

- 신규 `src/eraleader/official_partial_factor_bridge.py`: 기존 SHA 완결 `marketwide_kr.json`의 시장일·발행시각·연구 전용 조건을 원래 `marketwide_live_search._source/prepare_search`로 검증하여 **실제 자료에서 존재하는 요소만** 기존 `eraleader.kr_5factor_local_assessment.v1` 계약으로 자동 조립한다. 독립 백테스트 엔진·KRX/DART/키움 원시 저장소 쓰기0.
- **반영되는 값:** 기존 `price_strength_25` 그대로 momentum (0~25), `earnings_research_25`가 기존 `two_factor_research_50 = momentum + earnings` 및 매출/영업이익 원자료와 일치할 경우에만 earnings (0~25). 신규 계산식/임의 점수 최적화 없음.
- **결측값 처리:** `industry_code`는 실제 산업 성장성 점수가 아니므로 industry=None; 회사 규모/순위만으로 competitiveness=None; 키움 외국인·기관 순매매 주수는 검증된 flow 0~10 점수가 아니므로 flow=None. issuer historied PIT/financial PIT/기업행동 등 각 flag를 **False**로 명시, 현재 DART 코드매칭을 영구 issuer PID로 주장하지 않음. 존재하는 요소는 원래 시장보고 canonical SHA와 실제 해당 전체 보고서의 `built_at_utc`를 연구용 `factor_receipts`로만 기록한다. 최초 수신시각 독립 공인 PIT 인증 아님.
- **실제 발행일:** `decision_at_utc=marketwide.built_at_utc` (전체 연구보고서가 로컬에 존재했던 가장 이른 주장 가능 시각). 과거 거래일로 판단시점 소급0. 자료 지연이 2평일 이상이면 신규 5요소 입력 파일을 만들지 않는 `PARTIAL_FACTOR_STALE_MARKET_HOLD` (휴장 달력은 별도 인증 전).
- 증분 우선순위: 실제 가격·실적 두 요소가 있는 종목 → 가격 WATCH20 → 가격 상대강도순, 동점 코드순. **상한 500개**이며 이 정렬은 매수·대장주 순위가 아닌 **증거 확보 작업 우선순위**다. 전체시장 또는 정식 100점 TOP20으로 오해 금지. `limit=1..500` 선택 가능. 버전명 `output/partial_factor_inputs/KR_YYYYMMDD_<sourceSHA16>_PARTIAL_<limit>.json`, O_EXCL + canonical source SHA/재검증, 기존 동버전 반복 실행은 내용 동일 확인 후 `ALREADY_DERIVED`, 변조·미래 정보 차단.
- 기존 5요소 분석 파이프라인 `factor_selection_pipeline._validate`이 **실제 KRX 6자리 영숫자 주권 코드**를 누락하지 않도록 허용. `issuer_id_validated_as_of=false`는 issuer PIT가 거짓일 때만 허용하고 해당 코드는 연구 WATCH까지만 유지. 가격/실적 외 3요소 결측과 PIT false 때문에 `StateHistory`가 500종목 전부 WATCH, `selected_candidates=[]`, 정식 확정0/주문0.
- CLI: `python3 scripts/run_factor_selection.py --project "$PWD" --marketwide-report <verified-report> --derive-official-partial --max-research-rows 500`. 기존 `--factor-input`과 상호배타적, 옵션 없이 실행하면 구형 조회 전용 동작 불변.
- 기존 운영 배치 `scripts/render_local_operations.py`에 `--marketwide-derive-partial-factors` 명시 opt-in(반드시 `--marketwide-source-root`). 이미 검증된 `refresh_latest_marketwide`가 선택한 **정확한 보고서**를 재사용해 파생자료 생성→5요소 연구 상태기록→운영상태 JSON. 종전 `--marketwide-publish-outbox`와 병용 가능하되 중립 JSON 수신 프로젝트/주문 권한 0. 원래 정기 launchd 설치설정은 변경/로드하지 않음.

## 실제 Mac/T5DATA 실측

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' \
  --marketwide-publish-outbox --marketwide-derive-partial-factors
```

- 공식 KRX 2026-10-13 거래관측 2,761, 기존 로컬 가격RS 2,263, 실제 DART 재무49/산업 프로필49, **가격·실적 2요소 평가가능38, 동일 거래일 수급 연구 1**.
- 보관 원본 `kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json` (sourceSHA `a59b7ecdfaa0b707…`) 읽기 전용. `output/partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_PARTIAL_500.json`: **500종목 momentum500/earnings38/산업성장0/경쟁력0/수급 점수0**, 가격요소 관측 가능 2,263 중 상한으로 제외1,763. 기존 SQLite `output/five_factor_local_state_history.sqlite`에는 WATCH500 / 승격·교체 이벤트0. 공식 정식선정/확정0, `orders_enabled=false`, API 신규 호출0.
- 운영 E2E `output/verification_logs/partial_factor_operations_real_20261014.json`: 기존 중립 가격WATCH20 정상 유지, 부분 5요소500 WATCH, 전시장 검색 및 운영화면 갱신, 동일 근거 재실행 `ALREADY_DERIVED`. 원본 first SHA, 외부 전략 프로젝트 원본, 기존 main 사용자 미커밋 파일 변경0.
- 변경 영향 테스트 `PYTHONPATH=src python3 -m pytest tests/test_official_partial_factor_bridge.py tests/test_factor_selection_pipeline.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_handoff_bridge.py tests/test_marketwide_live_search.py tests/test_operations_overview.py tests/test_strategy_handoff.py -q --tb=short --junitxml=output/verification_logs/partial_factor_full_scope_20261014.xml` → **127/127 PASS, 오류0·실패0·스킵0**, 실제 source SHA/미래입력/점수합계불일치/누락/영숫자코드/idempotency/CLI 운용 통합 시험 포함. 전체 2,000+ 회귀·실제 미래 대장주 예측 성과 테스트는 미실행.

## 다음 우선 과제

1. **현재 산업성장·경쟁력·기관외국인 flow 실제 정량 신호**는 아직 수집/계산 근거가 없어 모두 N/A. 다음 변경은 기존 DART/키움·산업 데이터를 사용해 자료가 확보된 회사부터 이 값의 **독립 검증 가능한 실제 모델/입력**으로 보완. 매출성장과 산업성장을 같은 수치로 중복 계산하지 않는다.
2. 실제 완전 5요소인 기업이 생기면 issuer/금융/기업행동 PIT 근거에 따라 연구용 후보와 공인 대장주를 별도 표시. 전향적 최초 신호 등록 후 조기 발견 성과 평가.
3. 프로젝트 중립 JSON **발행 기능은 이미 완료**, 매매전략 수신 프로젝트 선택과 실주문 연결은 사용자 추후 결정. 새로운 파일은 feature 브랜치에만 저장, 원본 main 미병합.
