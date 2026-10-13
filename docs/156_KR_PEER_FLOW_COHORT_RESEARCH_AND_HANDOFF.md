# EraLeader KR 업종별 표본 비교 · 수급 거래일 결선 · 연구후보 송신
2026-10-14 / 3_4·3_5·4_1·6_2 / 실사용 기능 우선

- 기존 실제 첫수신 SHA를 검증한 KRX **2026-10-08** 거래일 2,765종목, 이후 받은 DART CFS33종목·현재 산업코드33종목과 로컬 3/6개월 상대강도 2,261종목을 **새 원장 변경 없이** 재사용.
- `src/eraleader/official_marketwide_coverage.py` 안에 기존 산업코드 기준 동일업종 표본 매출/영업익 YoY 비교(최소2개), 자료 없는 회사 N/A, 동점 같은 순위, 해당 코드 표본만 모수로 계산. 실물 33회사 중 **2개 이상 동일코드 6그룹**, 매출성장 상대비교 **15사**, 영업익성장 **9사**. 이는 업종 전체 성장률·기업의 경쟁우위·정식 산업20점/경쟁력20점 인증이 아니며 투자 순위로 사용하지 않는다.
- 기존 `kiwoom_investor_flow.verify_flow` 재사용하여 `--kiwoom-flow-folder` 선택 시 사용자가 실제 요청한 KRX 관측 거래일과 Kiwoom 요청·최근 관측일이 **둘 다 일치하는 경우에만** 20관측 외국인/기관 순매수 주수 추가. 미일치 자료는 N/A, 수급점수 0 대입 없음. 실제 보존된 2026-10-13 삼성전자 모의 Kiwoom 첫수신 1건은 가격관측 2026-10-08과 달라 **flow usable 0, mismatch 1** E2E 확인. 합성 테스트에서는 같은 거래일 정상 연결 확인. 키움 실계좌/주문 기능 변경 없음.
- 기존 시장 JSON이 검증된 경우 `scripts/publish_official_marketwide_coverage.py --verified-marketwide-report ... --kiwoom-flow-folder ... --out ...`로 KRX/DART 전체를 다시 수집하지 않고 업종 표본과 수급 결과 **별도 신규 산출물** 발행. 원본은 그대로 보존, SHA 재계산. 자료 신선도는 **요청 로컬일/가격관측일/달력 경과일**을 분리 표시하며 휴장을 반영한 *실제 거래일 경과 수 N/A*.
- 기존 `strategy_handoff.py` 범용 송신에는 (1) 원형 PRICE-WATCH20 및 (2) **2요소 50점 연구용 비교 상위20**을 별개 목록으로 발행. 후자는 `selection_state=WATCH`, `score_100=null`, `strategy_research_allowed=false`, 첫 판단 가능시각은 자료 발행시각, 원본 SHA 포함. 정식 `selected_candidates=[]`, 주문0, 수신 프로젝트 미결정(D-030) 유지. 동일 자료 중복발행 멱등/다른 SHA 버전은 불변 보존.
- 실제 결과: `output/marketwide_kr_33f_peers_flow_gate_v3_20261014/{marketwide_kr.json,index.html}` 및 `output/strategy_outbox/KR_20261008_c9fef37148c126ee.json` (Git 미추적). 2요소 50점 평가 가능 25사, 그중 TOP20 연구전달, 시장 전체 비교/공식 5요소 TOP20 아님.
- 변경영향 10개 관련 모듈 테스트 **160 PASS / failure0 error0 skipped0 EXIT0**, `output/verification_logs/marketwide_peer_flow_handoff_20261014.xml`. 보존된 실제 Kiwoom 원본 및 KRX/DART 자료 E2E도 별도 새 출력으로 PASS. 전체 수천 개 장기/홀드아웃 반복 테스트는 미실시.
- **NEXT 핵심**: 실제 최신 KRX 정규마감 세션 자동 수신(당일 0행·시차 처리), 키움 정확히 같은 세션의 외국인/기관 수급 확대, 동종기업·산업 전체 성장의 공통 첫수신 및 경쟁력 피처 확보 → 기존 100점/StateHistory에서 **POTENTIAL·CONFIRMED·WEAKENING·교체** 실제 운영 인수 → 프로젝트 중립 선정 outbox. 실거래는 EraLeader 범위 밖.
