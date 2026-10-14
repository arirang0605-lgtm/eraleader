# 2026-10-14 — 한국시장 재무·산업 12종목 추가 및 원본 보존형 증분 결합 (P1)

- **CONTINUE**: 기존 feature worktree HEAD `1e2f213`에서 계속. main 및 별도 미커밋 `native_first_capture.py`, 원시 KRX/DART 첫 수신 증거, 다른 프로젝트는 수정하지 않음.
- 2026-10-13 공식 KRX KOSPI941/KOSDAQ1820 = **2,761종목** 기존 수신 원본 및 당일 DART 현재 기업 directory 연결. 기존 시장 관찰 보고서 18사 CFS·산업·Kiwoom 삼성전자 수급1·관찰 WATCH20/2요소 연구11을 입력으로 사용.
- 이미 구현된 **DART 재무 자동 큐** `capture_dart_multi_company.py --auto-marketwide-report`로 미수집 거래대금 상위12사 (해당 날짜 기준) FY2024/25 2개년 CFS 원본을 기존 first SHA 캐시 재활용+필요분 공식 API 읽기 전용 수신. **12/12사 연속 2개년 CFS complete**. 동일 12사 현재 DART 산업 profile 원본: 기존 10 + 새로 수신한 2, **12/12**. 수신 이후 데이터이므로 가격 관찰일 당시 공개된 정보라고 소급하지 않음.
- 기존 `official_marketwide_coverage.py` **확장 함수 `extend_saved_marketwide_factors`**, `publish_official_marketwide_coverage.py --extend-marketwide-report` 선택옵션: 기존 전체시장 JSON SHA, 최신 KRX/DART 거래일·현재 issuer·원본 등록 PIN을 읽기 전용 검증하여 **새 CFS와 업종만 증분 추가**. 이미 검증한 전체 시장 550일 상대강도/ WATCH/SQLite/보고서를 재작성하지 않고 **별도 신규 출력 경로**로 발행. 기존 공식 원본과 이전 결과 파일은 변경하지 않음. 동일 CFS manifest 재투입·중복 주권·잘못된 업종·미등록 SHA는 거부, 재무 결측값은 N/A.
- **실데이터 E2E PASS**: `output/kr_20261013_marketwide_30f30i_20261014/marketwide_kr.json` 및 HTML. 공식 2,761, CFS **18→30**, 산업 **18→30**, 캐시 상대강도 2,263 유지, 2요소50점 비교 가능 **11→22**, 정확한 시장일 Kiwoom 모의 수급1 유지. 정식 5요소100점/CONFIRMED/투자 순위는 0 또는 N/A. 이전 연구 입력 SHA·추가 재무/산업 증거 SHA와 생성 UTC 보존.
- 기존 전략 독립 outbox `output/strategy_outbox/KR_20261013_a37aa3f6978c_6d6d702983cb.json`: PRICE WATCH20 및 2요소 연구 TOP20 / 선정0 / 주문0. 파일 SHA 계약 검사 PASS, 동일 입력 재발행 `ALREADY_DELIVERED` PASS. 수신 프로젝트는 특정하지 않음(D-030).
- 변경 범위 `tests/test_official_marketwide_coverage.py` 신규 실제 연동 mock 실패/중복/원본불변 테스트 추가 및 기존 8모듈 관련 **125 PASS, 실패0, 오류0** (`output/verification_logs/kr_fast_incremental_factors_scope_20261014.xml`). 2,000+ 전체/장기 성과는 반복하지 않음.
- 다음 최우선: 신규 거래세션 KRX 가격 갱신→DART 재무·산업·기관 외국인 동시점 커버리지 추가 확장→산업성장/경쟁력 근거 채워 기존 5요소 100점 TOP20·상태 기록 및 프로젝트 중립 선정 송신. 연구용 상대순위를 검증된 정식 투자신호로 오인시키지 않음.
