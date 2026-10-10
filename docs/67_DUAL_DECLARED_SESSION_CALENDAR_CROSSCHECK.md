# 2_2 / 2_5 — 두 개의 오프라인 거래일·종가 주장 교차검증

2026-10-11 로컬 기능. 외부 API 연결 없음. 기존 `audit-total-return --session-clock`의 종가 이전 자료 차단에 더해 선택적 `--exchange-calendar <file.json>`을 연결한다. 둘 중 하나만 있을 때, 달력만 제공하는 명령은 오류로 종료된다. 다른 기존 명령은 그대로 유지한다.

기존 `eraleader.session_close_manifest.v1`에는 거래일별 `close_at`을 지정한다. 별도의 `eraleader.exchange_calendar_reference.v1` 계약에는 `market`, 원본 `source_id`, `publisher_id_claimed`, `retrieved_at`, `asserted_complete=true`, `coverage_start/end`, `trading_sessions`, `closed_sessions`와 새 선택형 확장 `trading_session_closes`를 추가한다. 예: `{"2024-03-11":"2024-03-11T16:00:00-04:00","2024-03-12":"2024-03-12T16:00:00-04:00"}`. 두 파일은 별도의 **자기선언 공급자 ID**만 검증하며 실제 독립 공급자 여부는 검증할 수 없다.

엄격 검사에서는 해당 로컬 달력의 입력시점이 신호 의사결정 시각보다 늦지 않아야 하며, 기준 시장·종목 가격/참조지수/종가 출처와 달력 출처 ID가 중복되면 차단한다. 캘린더 커버리지, 정확한 ISO 거래일, 중복/정렬/개장·휴장 충돌, 개장일별 종가 전체 명세, 뉴욕 DST/한국 현지일을 검사한다. 달력에 존재하지 않는 거래일·달력과 다른 종가·참조지수의 중간 개장일 누락은 파생 결과를 게시하기 전에 오류로 처리한다. 반장일(조기 종가)은 양쪽 파일이 같은 시각을 명시할 때만 허용한다. 달력의 시간대·거래일 기록은 원격 독립 인증되지 않는다.

`PYTHONPATH=src python3 -m eraleader audit-total-return --file INPUT.json --session-clock CLOCK.json --exchange-calendar CALENDAR.json --security-id ID --market US --decision-at ISO8601 --evaluated-at ISO8601 --out output/dual_calendar_trial`

정상 결과는 `total_return_crosscheck_research.json`에 `declared_session_close_audit` 및 `declared_calendar_corroboration_audit`를 추가한다. 후자는 달력 전체 SHA256, 확인된 거래일 수, 주장된 출처 ID와 원천 취득시각, `independent_calendar_verified=false`, `historic_pit_certified=false`를 저장한다. 데이터가 일부라도 모순되면 출력 전에 오류로 차단한다.

회귀: `PYTHONPATH=src python3 -m pytest tests/test_session_calendar_crosscheck.py tests/test_session_close_gate.py -q --tb=short`; 전체: `PYTHONPATH=src python3 -m pytest tests -q --tb=short`. 가짜 휴장/중복일/늦은 달력/서로 다른 조기 종가/거래일 누락을 합성으로 주입한다. 합성 일치 결과는 실제 PIT·거래소 확인/상폐·조정주가의 공식 인증이나 미래 대장주 예측 성능이 **아니다**.

다음 단계: 시장별 실제 독립 공급자 서명·발행/수정 시각, 공식 반장·휴장 이력, issuer 변동/상폐 현금정산/기업행동 실효시각, 실제 전향적 만기 라벨 검증. D-017 API 연결은 로컬 30개 기능 이후, D-021 실제 SSD 탈착·재부팅은 마지막 단계.
