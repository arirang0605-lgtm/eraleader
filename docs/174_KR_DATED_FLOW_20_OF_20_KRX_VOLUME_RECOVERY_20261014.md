# 174 — KRX 2026-10-06·07·12 공식 수신 및 키움 거래량 5/20일 완전 정합

**2026-10-14 KST | 개발 ID 1_2·3_3·3_5·6_2 | feature/kr-marketwide-search-20261014**

## 실제 수집·완료

- 기존 정상 `scripts/capture_official_api.py`의 KRX 코스피/코스닥 소스와 기존 승인된 개인 인증정보를 그대로 재사용, 환경 점검 두 건 모두 `READY_TO_REQUEST_NOT_TESTED` 확인 후 **2026-10-06·10-07·10-12 각 양시장 1회씩 합계 공식 KRX API 6회 수신 성공**. AUTH_KEY는 출력·커밋하지 않음, 실계좌·주문·브로커 API0.
- **새 증거 저장 위치**는 기존 owner-only `/Volumes/T5DATA/eraleader/output/official_api_capture` 안의 **새 `first_<uuid>` 디렉터리만** 사용. 이전 원본 first receipt, 사용자 미커밋 코드/문서, 다른 브랜치 원시자료/가격캐시 수정0. 매 응답 원본 SHA256과 `first_local_received_at_utc` UTC/거래일·종목수/소스 ID를 개별 영수증에 봉인. 이는 **10월14일 실제 최초 수신한 과거 거래일 자료**이며 10월6·7·12일 당시 사용 가능했다는 역사적 PIT 인증이 아니다.
- 실물 검증된 거래량 응답: 10월6일 코스피942/코스닥1,824, 10월7일 코스피942/코스닥1,823, 10월12일 코스피941/코스닥1,821. 이전 보관 10월8일(942/1,823), 10월13일(941/1,820)도 첫 SHA 재검사해 5개 날짜 양시장 모두 확인.
- 이전 기능 `official_krx_volume_overlay.py`의 `verified_capture + _krx_frame` 검증을 그대로 실행, 날짜 5개를 합쳐 **저스템(417840) 기존 `marcap-2026` 일별 캐시 결측**을 보완하는 새 불변 overlay `output/official_krx_volume_overlay/KR_20261013_417840_b9d5afd97e0a/manifest.json` 발행. 이전 2일 보완판 및 원본 parquet 그대로 유지.
- 기존 `marketwide_dated_volume.py`에서 키움 모의 수급과 날짜별 공식 KRX+marcap 거래량의 **최근5개 5/5, 최근20개 20/20 일자 일치** 달성. 새 불변 최종 JSON·HTML 경로 `output/marketwide_dated_volume/KR_20261013_417840_8b00c364ac38/`. 그 5행 실제 외국인 순매매주수427,294/동일날짜 거래량8,634,932 ⇒ **+4.948435%**, 기관55,054 ⇒ **+0.637573%**. 20행 외국인1,232,905/거래량25,212,258 ⇒ **+4.890101%**, 기관266,006 ⇒ **+1.055066%**.
- 산출된 값은 **기간별 총 거래량 대비 관측순매매 비율(연구용)**이고 유통주식수 대비 매집률/지분 증감·정식 flow10점/투자선정·과거 공시/PIT 인증이 아니다. `formal_flow_score_10=None`, 정식 leader0, 실전 매수/매도·알림 발송0 유지. 최초 수신 UTC가 과거 시장일보다 늦다는 사실을 보존.

## 새 운영 기능 / 실행

- 신규 `src/eraleader/krx_volume_gap_planner.py` + `scripts/plan_krx_volume_gaps.py`: **네트워크/API 호출 0회**, 이미 SHA 검증된 키움 20개 날짜/로컬 marcap 결측과 기존 코스피/코스닥 owner-only 공식 첫 영수증을 확인. 실제 **거래량 결측 날짜만** 양시장 원본 수신 필요 여부를 계산하고, 기본 회당 최대 6요청으로 제한. 기존 영수증이 있는 날짜는 중복 API 재요청 대상으로 만들지 않음. 검증 불량 영수증/잘못된 거래일·종목은 FAIL/CLOSE, 기존 수급20 증거가 없는 종목은 조회 계획 자체를 만들지 않음.
- 실제 마감 KRX 복원 후 실행:
```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/plan_krx_volume_gaps.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --capture-root /Volumes/T5DATA/eraleader/output/official_api_capture --code 417840
```
  결과 `KRX_VOLUME_GAP_EXISTING_RECEIPTS_READY`, `already_receipted_dates=[2026-10-06,07,08,12,13]`, **추가 요청0/API호출0/실주문0**. 실물 CLI 근거 `output/verification_logs/krx_missing_gap_actual_20261014.json`.
- 기존 운영 `scripts/render_local_operations.py --marketwide-dated-volume-code 417840 --marketwide-krx-volume-capture-root /Volumes/T5DATA/eraleader/output/official_api_capture --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output` 재실행 EXIT0, 소스 영수증 날짜5개와 최종 `fully_aligned_5=true`/`fully_aligned_20=true` 표시, 운영 최신 URI가 20/20 완성판을 가리킴. 메인 운영/세부 HTML 각각 로컬 HTTP200. 근거 `output/verification_logs/krx_full_dated_ops_20261014.json`.
- 테스트 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_krx_volume_gap_planner.py tests/test_official_krx_volume_overlay.py tests/test_marketwide_dated_volume.py tests/test_marketwide_dated_flow.py tests/test_marketwide_volume_alignment.py tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_marketwide_flow_diagnostics.py tests/test_operations_overview.py tests/test_marketwide_auto_refresh.py -q --tb=short --junitxml=output/verification_logs/krx_gap_complete_scope_20261014.xml`: **101개 PASS, FAIL0/ERROR0/SKIP0, EXIT0**. 별도 Python py_compile/git diffcheck PASS. 역사적 5요소 전략 적중률·전체 2,000개 회귀는 본 변경과 다른 단계.

## 다음 개발

1. 실제 공식 KRX 날별 거래량 수신·검증 및 20개 관측행 합산 기능은 이 대상종목에 대해 완료. 다른 기존 키움 모의 수급 종목(006110,446540)의 **날짜별 20행 영수증 확보**가 다음 실사용 확대 항목. 기본 모의/읽기전용, 별도 opt-in으로만 호출.
2. 수급 비율은 독립 기업행동/유통주식수 및 실제 충분한 기간 데이터가 누적되어야 **5요소 수급10점 규칙을 확정**할 수 있음. 산업 성장·기업 경쟁력20점의 실제 원시 공급자 증거 확보 후에만 POTENTIAL/CONFIRMED 상태로 발굴/neutral strategy JSON 승격.
3. 기존 정상 코드 REWRITE 금지. 원본 main의 미커밋 `native_first_capture.py`·DECISIONS·PROJECT_STATE 및 사용자 공시유형 PNG 등 보존. 완료 개발은 분리 feature 브랜치에만 커밋; main 병합은 별도 결정.
