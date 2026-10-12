# 2026-10-12 — 1_2·2_2·3_1·4_2·6_2 공식 API → PIT as-of 관찰 → WATCH·대시보드·정기 보고

## 범위
새 `official_api_pit_bridge.py`와 `scripts/run_official_api_pit.py`는 기존 live 공식 HTTPS 원시 수신/첫 SHA 증거를 읽는 **read-only 소비자**다. KRX 코스피·코스닥 **동일 1일** 원문을 first_receipt SHA로 검증하고 최초 수신 시각보다 과거의 판단에 투입하지 않는다. 6자리 영문혼합 종목코드도 보존하며 중복 코드/정지/비정상 OHLC는 차단한다. 해당 일자 이전 기존 marcap read-only 캐시는 **모멘텀 참고**로만 결합하며 공식 인증 역사 가격/issuer/class PIT로 승격하지 않는다.

기존 `data.validate_bars` → `discovery.score_price_observations` → `execute_run`(SQLite WATCH 신규/재실행 증거) → `execute_alerts`(DRY-RUN) → `execute_report`(일/주/월 3개) → `delivery.write_dashboard`를 재사용한다. 출처·최초 로컬 확보시각/first SHA·한계는 추가 `official_api_pit_research.json`, `site/official_api.html`로 제공. 원래 정상 API 캡처 모듈, PIT 원장, 공시 원본, 모델/점수/임계값은 미변경이다. 새 HTML은 API 일봉 연결 / 공식 PIT 인증 미완료 구별.

선택 `--pit-ledger /absolute/offline.sqlite`를 주면 **존재하는** 기존 `OfflineLedger.open_readonly`의 동일 `decision_at` 시점 `snapshot`을 `integrated_snapshot`과 결합, `official_pit_integrated_research.json`/`site/research_kr.html`로 저장한다. 파일이 없으면 만들거나 임의 issuer/member/industry 기록을 넣지 않는다. 공급자 영구 issuer/share-class 연결이 독립 입증되지 않아 결과는 research-only, 확정 0이다. DART/SEC는 최초 SHA/수신시간·건수/자료 누락 상태만 추가한다. DART 최초 100건만으로 하루 전체 공시, SEC CIK/facts만으로 한국 종목의 재무·공시 PIT 피처를 만들어 넣지 않는다.

## 실제 수신본 사용 예
`scripts/run_official_api_pit.py --kospi /absolute/first_KOSPI --kospi-sha256 <따로 확인한 최초 SHA> --kosdaq /absolute/first_KOSDAQ --kosdaq-sha256 <따로 확인한 최초 SHA> --decision-at 2026-10-12T20:10:00+09:00 --as-of 2026-10-12 --out /Volumes/T5DATA/eraleader/output/official_api_integrated_20261012`

선택 `--aux dart-disclosures /absolute/first_DART <SHA>`, SEC도 두 계열 동일. 비밀키 전송/파일 조작·추가 네트워크 수집 없이 기존 원본만 재사용한다. 기존 출력 경로 덮어쓰기 금지.

## 미완료·검증 한계
2026-10-08 기준 KRX 합계 2,765행(코스피 942·코스닥 1,823)은 **거래 일봉 수**다. 코스피/코스닥 법적 상장종목 전수·상폐 기업행동·issuer/share-class 기간 이력과 독립 사실 대조 안 됨. DART 2026-10-08 첫 페이지만 100행으로 하루 전체 누락, SEC는 Apple 단일 CIK. 현재 `output/offline.sqlite`는 없으므로 live 실행의 PIT 재무 결합이 불가능하며 **WATCH는 가격 관찰용**, 실제 성장 주도주 예측력 N/A. 최초 공식 API 수신 시각은 2026-10-12이므로 2026-10-08에 이 모델이 실제 선택한 것으로 소급하면 안 된다. 가격 참고 캐시의 조정·누락, 독립 주권ID, DART 페이지네이션/최초 공시 공개시각, SEC 파일링 영구맵, 실전 Top-K 1~12개월 만기는 후속 데이터 계약/시간 경과 필요.

검증: `PYTHONPATH=src python3 -m pytest tests/test_official_api_pit_bridge.py -q`. 실제 비공개 원시 캡처로 순환 실행 시 키/개별 원시가격은 stdout·Git에 남기지 않는다. 본 작업의 정확한 테스트 수·전체 회귀/commit SHA는 PROJECT_STATE.md 체크포인트 참조.

참고: 연구 as-of는 반드시 공식 최초 확보 이후 KR 기준 현지 의사결정일이어야 하며, 공식 일봉이 10일 이상 오래되면 차단한다. 점수 원장 run_id는 최초 증거 source digest에 결박해 동일 종가라도 출처 SHA 변경을 구별한다.

시점 누출 방지: 기존 price snapshot 원래 거래 세션은 보존하지만, 새 API WATCH 이벤트의 SQLite `as_of` 및 본문 `recorded_at_date`는 **최초 API 이후 연구 판단일**로 별도 기록한다. `first_local_received_at_utc`, `observed_market_session`, `historical_backfill=true`, `prospective_leadtime_eligible=false`로 2026-10-08 시세를 10-08 당시 발굴한 것으로 간주하지 않는다. API 미사용 기존 이벤트는 날짜/로직 그대로다.
