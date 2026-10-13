# 2026-10-14 | KR 시장 전체관측 결합 및 부분요소 TOP20 (개발 1_2·3_4·4_1·6_2)

- 범위: **기존 정식 가격 WATCH/StateHistory/주문 프로젝트/원시 API 파일은 변경하지 않음**. 별도 feature worktree에서 기존 공식 KRX/DART 최초 SHA, 가격 탐색 결과, 3FY 연구 코호트, 개별 CFS/업종 캡처를 읽어 전시장 coverage 자료 생성.
- 2026-10-08 공식 KRX 단일 거래일 KOSPI 942 + KOSDAQ 1823 = **2765** 관측. 현재 DART directory 매칭, 연간 CFS 2~3년/업종 프로필은 각각 **28사** 결합. 추가 20개 price-WATCH 중 2개사는 FY 연속 자료 불완전으로 N/A; 2026-10-14 확보된 새 최초 수신 영수증은 당시 2026-10-08 가격의 과거 투자판단 근거로 소급하지 않음.
- **임시 2요소 연구 비교 순서**: 기존 가격강도 최대 25점 + 매출YoY 최대 12.5점(40% 상한) + 영업익YoY 최대 12.5점(60% 상한), 음수 0. 가격과 2개 재무성장률이 모두 있을 때만 50점 점수 계산. 현재 20사 평가 가능. 별도 JSON 및 HTML에 N/A·자료일·원천코호트SHA·부분요소 한계를 명시. **산업 성장성·경쟁력·기관외국인 수급 N/A, 정식 100점/투자 TOP20/CONFIRMED 0**. 값의 크기는 수익성/투자 우선순위 검증이 아님.
- 범용 전략 출력은 기존 `strategy_handoff.py` 재사용하여 **가격 WATCH20만** 연구용 `research_watchlist`로 전달. `selected_candidates=[]`, `selection_count=0`, 주문 권한 없음. 2요소 연구순위는 투자대상으로 승격하지 않음. 기존 전용 전략 프로젝트에는 송신/코드 변경 없음.
- 실제 연구 결과 (git ignored): `output/marketwide_kr_28f28i_researchtop20_20261014/{index.html,marketwide_kr.json}`, `output/strategy_handoff_marketwide_28f28i_20261014.json`. 공식 최초원본은 로컬 `/Volumes/T5DATA/eraleader/output/official_api_capture`에 owner-only 보존, 원격 업로드 금지.
- 관련 코드: `src/eraleader/official_marketwide_coverage.py`, `scripts/publish_official_marketwide_coverage.py`, 기존 `official_dart_multi_company.py`, `scripts/capture_dart_{multi_company,industry}.py`, 기존 `strategy_handoff.py`, `scripts/export_strategy_handoff.py`.
- 직접 영향 시험 9개 모듈 pytest **129 PASS, failure0 error0 skipped0**, `output/verification_logs/marketwide_full_scoped_20261014.xml` (exit0 여부는 최신 pytest 직접 확인). 최초 원본 PIN 검사/issuer·date/증권코드/누락·반복 전달 및 오염 시험 포함. 전체 장기 PIT/수천 회귀는 이번 단계에서 미실행.
- **다음**: KRX 최신 당일 시세 0행 문제 해소 및 일별 자동 취득 → 거래일 동기화 → 기관/외국인 수급을 회사/주권별로 통합 → 산업 전체 성장·기업 경쟁력 및 실적 가속 점수 확장 → 5요소 정식 TOP20/상태 이력/수신 프로젝트 통합. 전향 적중률/성과 N/A.
