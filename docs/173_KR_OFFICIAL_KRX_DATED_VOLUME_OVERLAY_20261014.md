# 173 — 기존 공식 KRX 원본 수신 거래량으로 Kiwoom 수급 거래일 매칭 보완

**2026-10-14 KST | 개발 ID 1_2 · 3_3 · 3_5 · 6_2 | 작업 브랜치 feature/kr-marketwide-search-20261014**

## 실제 기능 완료

- 신규 `src/eraleader/official_krx_volume_overlay.py` 및 `scripts/publish_official_krx_volume_overlay.py`: 기존 read-only `/Volumes/T5DATA/eraleader/output/official_api_capture`의 KRX 코스피·코스닥 **최초 수신 원본**만 탐색. 이미 검증된 기존 `official_api_pit_bridge.verified_capture` + `_krx_frame`을 그대로 재사용하여 request_date·market·owner-only·raw SHA·first receipt SHA·price/volume/cap 포맷을 재검사한다. 새 KRX 네트워크/API 호출 **0회**.
- 수급 20관측 날짜에 해당하는 양시장 KRX 원본 한 쌍이 **모두** 수신돼 있어야 그 날짜 거래량을 보완에 허용한다. 최초 receipt 기준으로 중복 발행을 회피하며, 요청 시장일 및 그 이전만 인정. 최신 공식 시장일(2026-10-13)은 원본 코스피/코스닥 **전체 2,761개 종목**의 ID/명칭/상장시장/종가/시총/거래대금이 기존 SHA 봉인 `marketwide_kr.json`과 일치하는지 재확인한다. 동일 수급 주권을 양시장 중복 연결하면 차단.
- 종목별 공식 거래량 보완본 `output/official_krx_volume_overlay/KR_<시장일>_<종목코드>_<영수증12SHA>/manifest.json`: 실물 관측 날짜·원본 첫 receipt SHA/최초 수신 UTC/실제 주권거래량과 현행 KRX 출처 SHA를 canonical JSON+SHA로 묶어 **이전 증거를 덮지 않고** 저장. 키움 20개 날짜 전부에 임의 값을 넣지 않는다. 기존 `main`·CycleOS parquet·키움 원본 JSON 원장은 **변경0**.
- 기존 `marketwide_dated_volume.evaluate_exact_volume/publish_exact_dated_volume`의 optional `official_volume_overlay` 인자: 기존 marcap read-only 일별 바에 누락된 날짜만 KRX 공식 수신본의 거래량으로 채움. **동일 날짜 marcap volume과 공식 KRX volume이 충돌하면 중단**, 수급 기간 5/20개 관측 날짜 각각의 완전 커버리지 조건 유지. 공식 추가 날짜/소스 SHA를 출력에 기록, 같은 자료 반복 실행 멱등, source-date/fullscore/주문권한 허위 승격 차단.
- CLI `scripts/check_marketwide_dated_volume.py --official-volume-overlay <verified manifest>` 지원. 기존 운영 CLI `render_local_operations.py --marketwide-dated-volume-code 417840 --marketwide-krx-volume-capture-root /Volumes/T5DATA/eraleader/output/official_api_capture --marketwide-source-root <reports>` **명시 opt-in**으로 기존 탐색→재검증→날짜별 거래량 비교→보고/운영화면 연결. 선택 source가 없을 때는 N/A. 이전 기본 명령/수급·매매 코드는 유지.
- 기존 `operations_overview._latest_dated_exact_volume`가 한 종목/동일시장일에서 verified manifest SHA·파일 바이트·링크를 검증한 뒤 **거래량 날짜가 더 많이 확보된 판본**을 우선 표시하도록 조정. 과거 보수적 파일은 그대로 보존. 거래량 20관측 비율이 없는 기간 전체는 계속 N/A.

## 실물 T5DATA E2E

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/publish_official_krx_volume_overlay.py --project "$PWD" \
 --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
 --capture-root /Volumes/T5DATA/eraleader/output/official_api_capture --code 417840
python3 scripts/render_local_operations.py --project "$PWD" \
 --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
 --marketwide-dated-volume-code 417840 \
 --marketwide-krx-volume-capture-root /Volumes/T5DATA/eraleader/output/official_api_capture
```

- 기존 `marcap-2026.parquet` 거래량은 10월 2일까지. 원본 first KRX receipt에서 **2026-10-08(코스피942·코스닥1,823종목)와 10월13일(941·1,820종목)** 거래량을 추가로 발견·재검증했다. 원본 처음 수신일 10월8일 KRX는 10월12일 로컬 receipt, 10월13일 원본은 10월14일 receipt — 과거 거래 시각에 이용 가능했음을 뜻하지 않음.
- **저스템(417840)** 기준 최근 수급5 관측일 거래량: 이전 **0/5 → 2/5**, 20 관측일 거래량 **15/20 → 17/20**. 누락 **2026-10-06, 10-07, 10-12** (독립 공식 KRX 수신 원본 없음). 따라서 5개·20개 기간 수급 대비 거래량 **전체 비율 N/A**, `flow_score_10=None`, 정식 대장주0/매수매도0.
- 실물 JSON `output/official_krx_volume_overlay/KR_20261013_417840_902a56864a7c/manifest.json`, 최신 연구 보고서 `output/marketwide_dated_volume/KR_20261013_417840_cce0116eae38/{manifest.json,index.html}`. 기존 15/20 판본 역시 유지. `output/verification_logs/krx_volume_source_real_cli_20261014.json`, `krx_dated_volume_supplement_20261014.json`, `krx_volume_ops_real_20261014.json` 생성. 실제 운영 메뉴가 최신 17/20 보완 판본을 선택한 것 확인. 키움/API 추가 사용/외부 메시지0.
- 변경 영향 테스트 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_official_krx_volume_overlay.py tests/test_marketwide_dated_volume.py tests/test_marketwide_dated_flow.py tests/test_marketwide_volume_alignment.py tests/test_marketwide_flow_batch.py tests/test_marketwide_flow_coverage.py tests/test_marketwide_flow_diagnostics.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/official_krx_volume_combined_20261014.xml` → **86 PASS / 0 FAIL / 0 ERROR / 0 SKIP / EXIT0**. 실제 raw SHA/원본가격 전체 2,761 일치, synthetic volume 중복충돌 및 보완날짜 N/A 게이트, 기존 UI 링크 검증, Python compile/diffcheck PASS. 전체 수천 회귀는 이번 기능 영향범위를 우선 확인하고 보류.
- 보존: 원본 main 기존 미커밋 `native_first_capture.py` 변경/DECISIONS/PROJECT_STATE, 사용자 공시 분류 PNG·기타 사용자 파일, 다른 브랜치·CycleOS 데이터·MarketOS·NewsCatalystOS·SharedBrokerAPI 코드/개인 인증정보 변경0.

## 다음 개발

- 먼저 **2026-10-06·07·12 공식 KRX 양시장 거래량 원본**을 기존 API 수집기(별도 명시 opt-in)로 확보하고 새 버전 증거에 연결할 것. 과거 로컬 수신일은 미래 투자 판단시점으로 취급하고 소급하지 않는다. 원본 없을 시 강제 매칭/비율 계산 금지.
- 데이터가 충족되면 같은 종목의 전향적 5/20관측 거래량 대비 수급 비율을 안정적 공식 feature 후보로 검증. issuer 행위·실제 유통주식수·PIT 교차근거가 부족하므로 정식 100점 대장주 자동 승격은 아직 허용되지 않음.
