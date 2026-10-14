# 175 — KR 세 종목 날짜별 Kiwoom 수급·KRX 거래량 20/20 완전정합

2026-10-14 KST · 개발 ID 3_3·3_5·4_1·6_2 · feature/kr-marketwide-search-20261014

## 실제 완료
- 이전 정상 Kiwoom demo read-only 종목별 수급 수집기를 재사용해 006110 삼아알미늄과 446540 메가터치 각각 모의 API 1회, 날짜별 20관측행과 기존 5/20 집계의 원천 SHA 일치 확인 후 owner-only 로컬 output에 불변 저장. 실제 로컬 최초 수신 2026-10-14.
- 기존 KRX 2026-10-06/07/08/12/13 양시장 original first receipt SHA를 재검증해 두 종목 주권 거래량 일자 복원. 추가 KRX API 호출 0. 기존 CycleOS-Lab 가격 parquet·원래 시장보고 원본·SharedBrokerAPI 소스·실주문 프로젝트 미변경.
- 새 증분 결산: 이전 417840 저스템을 포함해 세 종목 모두 최근 수급5행/거래량5일 = 5/5, 최근 수급20행/거래량20일 = 20/20. 종목별 기관/외국인 연구용 수급·거래량 비율:
  - 006110 삼아알미늄: 외국인5 -9.814200%, 외국인20 -2.567517%; 기관5 +16.482965%, 기관20 +7.768904%.
  - 417840 저스템: 외국인5 +4.948435%, 외국인20 +4.890101%; 기관5 +0.637573%, 기관20 +1.055066%.
  - 446540 메가터치: 외국인5 -2.904073%, 외국인20 -0.650015%; 기관5 +0.144207%, 기관20 +1.320692%.
- 변경 코드: 기존 operations_overview.py의 단일 SHA/HTML 검증 경로를 all_stocks 옵션으로 재사용. 감사된 최고 날짜 커버리지 판본을 종목마다 1개 선택하고 운영 HTML에 세 보고서 링크 추가. 기존 단일 링크는 보존, 악의적 링크/위조 SHA·HTML/중복 종목 파일 제외. 신규 test_operations_dated_flow_all_stocks.py 테스트.
- 출력 증거(Git ignored): output/marketwide_dated_flow/KR_20261013_a59b7ecdfaa0b707_{006110,446540}.json, output/official_krx_volume_overlay/KR_20261013_006110_8742c0253d72, KR_20261013_446540_040d5e557e11, output/marketwide_dated_volume/KR_20261013_006110_80aaf9e1a4f5, KR_20261013_446540_d57e25272581. 가격일은 10월13일이나 첫 로컬 수신은 10월14일; 과거 시점에 실시간 이용 가능했다는 역사 PIT 인증 없음.
- 실 Mac 운영 명령: python3 scripts/render_local_operations.py --project CURRENT_WORKTREE. 운영 화면 output/operations/site/index.html에 현재 검증 종목 006110/417840/446540 보고서 링크3개와 5/5,20/20 출력. 명시 read-only 조회, 실거래 주문0, 외부 수신 프로젝트 고정 결선0.
- 테스트: PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_operations_dated_flow_all_stocks.py tests/test_operations_overview.py tests/test_marketwide_dated_volume.py tests/test_marketwide_dated_flow.py tests/test_official_krx_volume_overlay.py -q --tb=short --junitxml=output/verification_logs/dated_all_stocks_focus_20261014.xml → 58 PASS/0 FAIL/0 ERR/0 SKIP. Python compile 및 staged git diffcheck PASS.
- 보호: 원본 main 사용자 미커밋 native_first_capture.py/DECISIONS/PROJECT_STATE와 공시 유형 참고 이미지 유지, 키움/API credential·원 raw·산출 분석 HTML/JSON은 public Git 제외.

## 다음 우선
- 수급 공식10점은 아직 N/A. 유통주식수, 분할·증자 기업행동 및 독립 전향적 데이터 수집/시점 증거 확보 전 수급비율을 정식 점수나 자동매수 신호로 사용하지 않음.
- 산업성장20/기업경쟁력20의 실자료 공급자 연결과 상태판정으로 정식 5요소 대장주 조기 발굴 구현을 계속해야 함. EraLeader에서 실주문하거나 특정 후속전략 프로젝트에 고정 연결하지 않음.
