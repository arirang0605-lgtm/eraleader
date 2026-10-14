# 169 — 공식 KRX 전체시장 → SharedBrokerAPI 키움 모의 기관·외국인 증분수급

**2026-10-14 KST · 개발 ID 1_2·3_3·3_4·3_5·6_2·6_4 · feature/kr-marketwide-search-20261014**

## 이번 신규 실사용 기능

- 기존 정상 `SharedBrokerAPI/src/shared_broker_api/client.py`의 **ReadOnlyClient("eraleader")**와 `selected_flow_research`를 중복개발 없이 이용. 이 공통 API 프로젝트/원시 Kiwoom 인증정보·MarketOS·CoreAStock 코드는 **변경0**, EraLeader에서 가져온 모의 ka10059 선정종목 기관/외국인 *주수*만 이용.
- 신규 `marketwide_flow_batch.py`, `scripts/run_marketwide_flow_batch.py`. 기존 KRX/DART 시장전체 `marketwide_kr.json`의 canonical SHA, 거래일·수집시각·시장일 자료 신선도 확인. 기존 시장 WATCH20 → 기존 50점 부분연구 순위 → 관측 거래대금 → 코드순으로 **연구용 수집 우선순위**를 정함. 매수 순위나 강한 수급/대장주 평가 아님. 6자리 정규 KR 주권 코드·매매 가능 관측만, 이미 해당 시장일·원본 SHA 버전에 수집된 코드 skip.
- 명령 기본은 **체크만(네트워크/API 0, 쓰기0)**, `--apply-demo`를 명시할 때에만 1~5개 **모의/demo, read-only** 수급 호출. 사용자의 실계좌(real)·주문경로/매도는 구현·사용0. 게이트웨이 `status`에서 demo configured=true 및 orders_enabled=false 필요. `recent_sessions=20,max_pages=1`; 부족·누락·공급자 오류시 전체 소배치 발행 전 중단. 일부 종목 응답실패 시 부분 결과를 정상처럼 게시하지 않음.
- 성공한 수급응답은 공통 client의 hash/프로젝트/환경/종목/거래일·first gateway UTC 수신/실제 판정시점·shares 단위/과거 PIT false/권한없음 재검증. 원본시장 보고 SHA가 조회 중 바뀌지 않았는지 다시 확인. `output/marketwide_flow_batches/KR_YYYYMMDD_<sourceSHA16>_<codesSHA12>/{manifest.json,<code>.json}`으로 개인영역 O_EXCL 원자 출판. 재실행은 기존 manifest·각 보고서 SHA 재감사 후 저장 종목을 건너뛰고 다음 묶음 선택. 변경·변조/심볼릭링크·동일종목 중복은 차단. API 응답 원문·계정정보는 Git 추적/공개 제외.
- 신규 `marketwide_flow_coverage.py`: 모든 증거검증된 소배치를 누적해 5/20 **관측행**의 외국인·기관 순매매 주수만 분석, 누락 N/A. `output/marketwide_flow_coverage/KR_YYYYMMDD_<sourceSHA16>_<batchSHA12>/{manifest.json,index.html}`로 버전별 생성, 과거 버전 보존, 실제 보고 JSON canonical SHA 검증 및 HTML 스크립트 주입 차단. 이것은 전체 시장의 수급비중/금액·거래소 20거래일 연속성·기관 수급 **0~10점**이 아님. flow 정식 점수=N/A, 공식 대장주0, 매수주문0.
- 기존 `scripts/render_local_operations.py --marketwide-flow-coverage --marketwide-source-root <saved reports>`는 **명시 opt-in**. 기존 `operations_overview.py`에 연구용 키움 누적 수급 링크(현재 수집코드/20관측수·관측시장일)만 추가, SHA+생성페이지 bytes 검증된 결과 외 표시 거부. 운영 대시보드/기존 WATCH20·5요소 상태기계·가격자료 원본 보존. 정기 launchd 설치/권한 변경 없음.

## 실제 맥북/T5DATA 실행과 증거

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
# 확인만 (실제 수급 API 조회 없음)
python3 scripts/run_marketwide_flow_batch.py --project "$PWD" \
 --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json --max-codes 3
# 사용자가 허용한 기존 공유 모의 ReadOnlyClient를 통해 소배치 수급 1회 실제 호출:
python3 scripts/run_marketwide_flow_batch.py --project "$PWD" \
 --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json --max-codes 2 --apply-demo
# 로컬 누적 현황만 게시 (API 사용 0):
python3 scripts/render_local_operations.py --project "$PWD" \
 --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
 --marketwide-flow-coverage
```

- 현재 보관 기준: 공식 KRX 2026-10-13 양시장 2,761종목, 기존 CFS49·산업49·부분실적 RS38, 키움 단일종목 기관·외국인 수급 원형1. **신규 실제 키움 모의 선택종목 수급 3개** (417840, 446540, 006110)를 2개 별도 소배치로 성공 저장, 각 recent20 관측 수급 제공; first local gateway receipt는 2026-10-14, 가격일 10/13로 소급 불가. 3개 묶음 시도 1번은 안전 차단·배치 미발행; 후속 단일코드 재실행으로 006110 정상 발행. 신뢰할 수 있는 확정 시장전체 flow 점수0·주문0. 다음 큐 042510·092870·098120 (현재 source 버전/필터만).
- 실제 `output/marketwide_flow_batches/KR_20261013_a59b7ecdfaa0b707_*/`의 2개 첫 SHA 단위 검증, 누적 `output/marketwide_flow_coverage/KR_20261013_a59b7ecdfaa0b707_cb0321344c41`의 **collected3/20관측3**, HTML/JSON 게시 PASS. `output/verification_logs/marketwide_flow_demo_{real,second}_20261014.{json,err}` (second 실패는 부분게시0), `output/verification_logs/flow_coverage_real_ops_20261014.json` 및 로컬 UI 운영 링크 확인. 연구용 공유 게이트웨이 실제 status: demo=true/real=false/orders_enabled=false.
- 새 자동 테스트 + 기존 kiwoom/운영 변경 영향: `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_operations_overview.py tests/test_sector_peer_flow_research.py tests/test_official_partial_factor_bridge.py tests/test_marketwide_handoff_bridge.py tests/test_marketwide_auto_refresh.py tests/test_kiwoom_shared_daily_batch.py tests/test_kiwoom_investor_flow.py -q --tb=short --junitxml=output/verification_logs/kiwoom_marketwide_incremental_scope_20261014.xml` → **137 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, Python compile / Git staged diffcheck/공개 비밀검사 별도. 모의 수급 client는 테스트 fake provider만 사용; 실제 호출은 명시 2+1 수신 성공.
- `main` 사용자 미커밋 `native_first_capture.py` 7줄/문서, 타 기능 브랜치, KRX 원본·DART first SHA/비밀키 및 타 투자 프로젝트 전부 미변경. 실제 모든 신규 수급 원시 응답·SQLite/output은 Git 제외.

## 다음 개발

1. 기존 수집 성공 소배치의 근거와 시장 거래량/주식수·과거 영업일을 연결해 **5·20관측 수급의 비율·지속성에 대한 실제 모델** 마련. 현 3종목은 투자 종합 100점의 flow10 적용금지. API quota·현실적 증분 소배치/일별 신선도 기준에 맞춰 수급 관찰 대상 범위 확대.
2. 산업 성장·경쟁력 자료는 동종 일부 회사의 현재 업종코드만으로 점수 부여하지 말고 산업 수요·사업 경쟁우위의 독립 근거 우선 확보. 전체 5요소가 실제 출처/시점 통과하면 본래 StateHistory 상태판정/neutral strategy JSON 송신으로 연결, 매매 수신프로젝트 선정은 보류.
3. 사용자 실운영 최소 검증을 유지하며 feature/main 충돌·미커밋 보호. 전체 대형 회귀 및 실물 SSD 분리·재부팅은 최종 단계.
