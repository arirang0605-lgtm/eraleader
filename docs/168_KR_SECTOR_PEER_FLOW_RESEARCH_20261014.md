# 168 — KR 산업·동종기업 성장 순위 및 원시 기관외국인 수급 관찰 화면

**2026-10-14 KST · 개발 ID 3_2·3_3·3_4·3_5·6_2 · 분리 feature/kr-marketwide-search-20261014**

## 신규 실제 기능

- `src/eraleader/sector_peer_flow_research.py` 신규. 기존 SHA 봉인 `marketwide_kr.json`을 `marketwide_live_search._source/prepare_search`로 재검증한다. 기존 KRX·DART CFS·현행 DART 업종·키움 당일수급의 **이미 수집된 값을 재사용**한다. 네트워크 호출·다운로드·비밀키·브로커 주문·타 프로젝트 파일 변경 없음.
- 기존 시장 전체 보고서에서 `industry_code`별 관찰 기업을 그룹화하고, 수집된 `peer_revenue_yoy_rank`/`peer_operating_yoy_rank`와 denominator·원 매출성장/영업성장률을 **동일 그룹 전 종목에 대해 재대조**한다. 동일순위·rank 범위/분모 불일치·역순·부분그룹 누락은 게시 차단. 최소 3사 관찰이 있는 업종만 매출/영업이익 **부분표본 성장 중앙값**을 표시하고, 최소 3사 내 실제 기존 순위를 0..1의 관찰 상대 위치로 표시한다. 이를 전체 산업 성장·사업경쟁력/독점력으로 주장하지 않으며 정식 산업20점/경쟁력20점으로 승격하지 않는다.
- `institutional_flow`·`foreign_flow`는 원래 동일 거래일 키움 순매매 **주수**를 표시한다. 1일 원시 순매매 주수를 0~10점 수급 모델이나 실매수 신호로 전환하지 않는다. 나머지 종목 N/A. `industry_growth_score_20_available=0`, `competitiveness_score_20_available=0`, `flow_score_10_available=0`, `formal_leaders=0`, `execution_authority=false`, `orders_enabled=false` 고정.
- 기존 자료 공개 시각/시장일 분리: `source_market_session` / `source_built_at_utc` / `source_marketwide_sha256` 기록. 현재 업종코드 및 선택된 일부 재무 표본이므로 역사적 독립 PIT 인증=false. HTML의 업체명 등은 HTML 이스케이프 처리, 1개의 SHA 봉인 JSON + 로컬 반응형 HTML을 새 `output/sector_peer_flow/KR_YYYYMMDD_<sourceSHA16>`에 원자 게시한다. 동일 SHA 반복 시 두 파일 bytes를 비교해 `ALREADY_PUBLISHED`; 변경·손상 및 symlink 우회/덮어쓰기 금지.
- 기존 운영 `scripts/render_local_operations.py`에 **opt-in `--marketwide-peer-flow-research`** 추가. 반드시 `--marketwide-source-root` 필요, 기존 자동 최신 source 선택 및 outbox/5요소 부분자료 처리를 재사용하되 별도 옵션이 없으면 이전 경로와 동일하게 동작한다. 기존 `operations_overview.py`는 발행 JSON SHA와 실제 HTML 완전성을 확인한 후 `한국 동종기업 성장·수급 비교 보기` 링크/자료 수량/관측일을 로컬 대시보드에 표시. 발행하지 않았거나 변조되면 N/A. 런처/launchd의 설치·로드·설정은 변경하지 않음.

## Mac 실물 보관본 E2E

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' \
  --marketwide-publish-outbox --marketwide-derive-partial-factors \
  --marketwide-peer-flow-research
```

- 이전 공식 KRX 양시장 **2026-10-13 관측 2,761종목**, 산업 현행 프로필49/실제 동종 매출 성장 순위21/동종 영업이익 성장 순위16/키움 기관·외국인 같은 세션 순매매 1종목. **그룹 표본 ≥3개 업종은 2개**: `2622` 3사(매출 성장률 부분표본 중앙값 약 14.55%), `29271` 6사(매출 성장률 부분표본 중앙값 약 7.18%, 영업이익 성장률 4사 중앙값 약 -9.31%). **표본 전체 업종 대표성 미검증**이므로 이 중앙값은 정식 산업성장 점수가 아님. 기관·외국인 raw 수급1 외의 flow10 점수0.
- 생성 경로 `output/sector_peer_flow/KR_20261013_a59b7ecdfaa0b707/{peer_flow.json,index.html}` 및 Git ignored `output/verification_logs/peerflow_real_operational_20261014.json`. JSON canonical SHA 재계산 PASS, 기존 부분 5요소 500 WATCH/POTENTIAL0·기존 가격 WATCH20 중립 송신/주문0·외부 API0. 로컬 HTTP GET 운영 인덱스와 신규 보고서 각각 **200**, 링크 정상.
- 테스트: `PYTHONPATH=src python3 -m pytest tests/test_sector_peer_flow_research.py tests/test_operations_overview.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_handoff_bridge.py tests/test_official_partial_factor_bridge.py -q --tb=short --junitxml=output/verification_logs/sector_peer_flow_scoped_20261014.xml` → **83/83 PASS, failures0/errors0/skips0**. peer rank/분모·value ordering/원본변조·HTML 안전·원자적 기존파일 보존·symlink·CLI 옵션 차단/동작, 브라우저용 로컬 HTTP, Python py_compile, git diffcheck PASS. 전체 수천 건 회귀는 본 변경 기능 범위에서 미실행.

## 남은 핵심

- 산업 성장성20/기업 경쟁력20/기관·외국인 수급10을 **실사용 정량 점수로 전환하려면**, 개별 산업의 구성원 모집단·산업 전체 수익/수요·수주/시장점유율/지속경쟁력 자료, Kiwoom 거래일·주식수/거래량 기준 일별 수급의 더 많은 종목/기간 자료가 필요. 기존 49사 소표본 상대 순위만을 근거로 가중치20/20/10 자동 임의 생성하지 않는다.
- 다음 개발 우선: 공식 최신 수급의 더 많은 종목을 기존 공통 API로 수집하는 증분 큐 및 검증된 flow 피처→기존 5요소 평가/상태 원장으로 연결(실데이터 분모 부족 시 N/A). 그 외 산업·경쟁력의 별도 데이터 확보와 기업 동일성 증거. 실제 미래 발굴 성능 공식 인증 N/A.
- 본 코드는 독립 feature 브랜치에만 배포, 원본 main 미커밋·다른 프로젝트 원시자료/비밀키/주문권한 변경 금지.
