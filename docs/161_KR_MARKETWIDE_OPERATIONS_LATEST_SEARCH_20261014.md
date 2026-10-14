# 161 — 한국시장 최신 전체종목 검색과 운영 대시보드 내비게이션

- 일자: 2026-10-14 KST. 개발 ID: 1_1 · 3_3 · 3_4 · 3_5 · 6_2. 범위: 분리 브랜치 `feature/kr-marketwide-search-20261014`.
- 기존 `operations_overview.py`의 로컬 운영 화면에 `output/marketwide_kr_search_YYYYMMDD[_vN]` 발행 검색 화면 중 **시장 관측일이 가장 최신인 유효 연구 페이지**를 링크한다. 발행 날짜보다 시장 관측일 우선.
- 폴더명·상대 경로·실제 파일/링크 여부·manifest canonical SHA·시장/자료일·미래시각·기존 HTML 내 동일 manifest JSON을 확인하며, 안전한 검색본이 없으면 N/A 표시. 잘못된 링크를 직접 주입하면 거부한다. 원장·시장 가격·개인키 수정 및 다른 프로젝트 연결 없음.
- 원래 검색 화면이 거절하던 **실제 같은 시장 거래일의 키움 기관·외국인 순매매 주수**를 추가 지원. 한 종목 양쪽 signed int, 공식 수급 가용 건수와 최초수신 연구용 인증/원본 manifest SHA가 일치해야 화면·상세에 표시. 비지원/누락 종목은 N/A. 수급은 **기존 가격·실적 50점에 가산하지 않음**. 정식 100점 리더·매수/매도 신호를 생성하지 않음.
- 현장 기존 KRX 2026-10-13 **2,761종목** SHA 출처 원본을 조회하여 `output/marketwide_kr_search_20261014_v2/` 발행: 재무49·산업49·연구 50점 평가 38·동일 거래일 수급 1·공식 확정 0. 구 10/08 발행본은 보존. 로컬 운영 화면 `output/operations/site/index.html`은 10/13 최신 검색으로 상대링크 성공. `output/`과 실제 API/계좌/송신 파일 Git 제외.
- 변경 영향 테스트: `PYTHONPATH=src python3 -m pytest tests/test_marketwide_live_search.py tests/test_operations_marketwide_navigation.py tests/test_operations_overview.py -q --tb=short` -> **59 PASS / 0 FAIL / exit 0**. Python 컴파일·`git diff --check` PASS, 실제 검색 생성/운영 인덱스 최종 확인 PASS. 전체 장기 회귀는 이번 기능 범위에서 미실행.
- 유의: 운영 화면의 연결 검사는 **로컬 생성물 및 자기신고 SHA 구조** 수준이며 외부 독립 공시시점/PIT/실전 미래 수익률 인증이 아니다. 현재 운영 화면의 기존 scheduler 체크포인트 3모드는 이 분리 워크트리에 없어 N/A. 본 기능을 정식 운영 main으로 자동 병합하지 않음.
- 다음: 최신 검색 UI의 배포 동선 통합, 나머지 실물 기관/외국인 수급·산업/경쟁력·이익 가속 요인 확대, 5요소 정식 후보 확정 및 기존 범용 전략 송신으로 연결. 다른 매매 프로젝트에는 수신 연결 금지.
