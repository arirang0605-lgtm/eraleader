# EraLeader P2 — 실제 공식시장 기반 5요소 점수 준비도 / 운영 보고서 (2026-10-14)

## 개발 목적 및 정상코드 연속성
- 기존 정상 `feature/core-official-factor-coverage-20261013` SHA `9510430360a6b888907f3d4b93259f8ca4258694` 이후 다음 미완료 기능부터 CONTINUE. 원본 main의 미커밋 수정, MarketOS/CoreAStock/NewsCatalystOS, API 인증정보와 KRX/DART 최초 증빙은 불변. 수신 프로젝트는 미지정(D-030), EraLeader에 주문기능 없음.
- **이번 완료 P2** `src/eraleader/official_p2_readiness.py` + `scripts/publish_official_p2_readiness.py`: 기존 현거래일 KRX 전체시장 SHA 1회 확인→기존 `states.SCORE_MAX` / `evaluate_leader_state`에 실측 25+25 부분점수 전달→5요소별 자료관측 및 누락 항목 분해, 우선 보완 대상 TOP20, JSON/HTML 대시보드 생성. StateHistory 별도 WATCH 연구 DB를 READ-ONLY 조회하는 선택옵션. **정식 선정 0**은 기능 미완성 요소를 0점으로 가정해 탈락시킨 결과가 아니라 실사용상 정식 100점 판정을 보류한 것.
- 기존 50점 공식 연구 수치는 3/6개월 상대강도 최대25 + 연간 매출/영업익 YoY 근거 최대25에만 해당하며 모두 N/A 없이 관측 시에만 표시. 가격 일부 원본은 로컬 marcap 캐시로 역사 주권/PIT를 인증하지 못함.
- 실제 한 종목의 업종코드/기술 비교 peer rank는 **산업 전체 성장**(20점)이나 **기업 경쟁력**(20점)을 증명하지 않음. 기관/외국인 순매수 **주수**는 10점의 독립 상대 수급 모형이 아니므로 정규화 점수는 N/A(0 아님). 과거 상폐/기업행동 PIT 미완, `evaluate_leader_state`의 검증 필수조건을 만족하지 않으면 WATCH를 유지한다.
- **실물 E2E**: 기존 KRX 2026-10-13 2,761주권, DART FY CFS 현재49사·산업 현재49사, 상대강도 2,263, 실적 25점 평가38. P2 독립 JSON `output/kr_20261013_p2_readiness_20261014/{p2_readiness.json,index.html}`, 5요소 관측 수: **industry 0, competitiveness 0, earnings 38, momentum 2,263, normalized flow 0**, 정식선정 0. Kiwoom 같은 세션 기관·외국인 주수 1사 실제 수신했지만 10점 점수 산출/유효요건 자동 충족으로 위장하지 않음. 2026-10-13은 시장관측일이고 발행/첫수신은 이후.
- **기존 보고 루트 opt-in 결선**: `scripts/publish_official_marketwide_coverage.py --reuse-marketwide-report ... --watch-state-ledger ... --p2-readiness-out ... --strategy-outbox-dir ... --out ...`는 검증된 기존 전체시장 SHA를 읽고, **새** 시장 보고/Stage4 WATCH(중복 시 멱등)/P2 자료충족률 HTML+JSON/범용 후보 송신까지 단일 실행. 원본 KRX/DART/SQLite 기존 등록 값은 변경하지 않고 동일 시장 WATCH/이전 전달본 덮어쓰기 금지.
- 실제 단일 호출: `output/kr_20261013_p2_all_integrated_20261014/` 및 `output/kr_20261013_p2_operational_integrated_20261014/`. 기존 receiver-neutral JSON `output/strategy_outbox/KR_20261013_a59b7ecdfaa0_c6062c96f4e4.json`은 멱등 `ALREADY_DELIVERED`, 정식선정0/주문권한0.
- 변경영향·P2 단위·실사용 E2E 테스트: `output/verification_logs/kr_p2_readiness_scoped_20261014.xml`의 실제 PASS 수·에러수 확인. 기존 수천 개 회귀/장기간 투자성과는 이번 작은 기능의 선행 조건으로 요구하지 않음.

## 다음
1. **P2 정식 100점 모델**: 역사 기준 산업 **업종 전체 성장값**, 회사 **경쟁력**, 수급 **시장/시총·주수 정규화 비교**의 유효 데이터와 실제 보존된 first-received/시장 시각 제공 계층을 기존 상태점수 엔진에 연결한다. 데이터가 비어 있으면 N/A를 유지하고 POTENTIAL/CONFIRMED 가짜 전이는 만들지 않는다.
2. 기존 `StateHistory`에 각 거래일 검증된 영구 회사 ID/정식 점수 주입 → CONFIRMED·WEAKENING·교체/유니버스 제외 실제 추적. PRICE WATCH 연구 이력과 정식 기업 상태 원장은 분리.
3. P4 정식 선정 JSON outbox, 실시간 대시보드/일·주·월 리포트/알림 및 운영 스케줄 결선. CoreAStock 등 수신기 직접 연결은 사용자 결정 전 보류.
