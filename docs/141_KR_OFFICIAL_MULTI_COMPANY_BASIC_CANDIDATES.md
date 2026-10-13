# 141 — EraLeader 기본 기능 우선: 한국 공식 KRX+DART 여러 기업 실적·가격 후보 비교

**개발ID:** 1_2, 3_3, 3_4, 3_5, 4_1, 6_2. **날짜:** 2026-10-13.
**결정:** 사용자 `이런건 극단적이지 않아? 기본 기능 먼저 해라` 지시에 따라 추가 백업·에스크로 확대 중단, *실제 종목 후보를 검색하고 비교하는 기능*부터 구현. REWRITE 금지, main/뉴스 분리 브랜치/기존 WATCH20 원형 보존.

## 실제 기능 및 결과

1. `official_dart_multi_company.collect_multi_company_cfs`와 독립 CLI `scripts/capture_dart_multi_company.py`: 기존 KRX 첫 수신·SHA와 현재 DART corpDirectory PIN의 **실제 종목코드 교집합** 검증 후 1~12개 종목에 대해 공식 2024·2025 `11011` 연결 CFS만 수집. `capture_dart_financial/verify_dart_financial` 재사용, 별도 API SDK·임의 스크래핑 추가 없음. 호출 간 딜레이, 기존 실물 FY first SHA 재사용, 동일 기업 FY에 여러 SHA(정정/다른 수집본)가 있으면 자동 선택 금지, 자료 없는 기업 N/A. 암호화·키·비밀 DART 인증정보는 기존 Mac owner-only 설정 유지, 원본 API 응답/시장자료는 T5DATA Git-ignored `output/official_api_capture` 0700·0600.
2. **실제 검증된 10종목**: 삼성전자 005930, SK하이닉스 000660, 현대차 005380, 기아 000270, NAVER 035420, 삼성바이오로직스 207940, LG에너지솔루션 373220, 한화에어로스페이스 012450, 두산에너빌리티 034020, 한미반도체 042700. 공식 KRX 거래관측 해당 종목·DART 현재 고유법인코드 독립 첫 SHA 모두 대조 **10/10 PASS**.
3. 기존 삼성전자 FY2024/25 원본 2건 재사용+다른 9개 기업 FY2024/25 DART API 실제 수신 18건: **총 영수증 20건, 연속 재무 2연도 검증 10/10 기업**. `output/multi_company_cfs_20261013_v1.json` 실제 비공개 출력. 첫 수신일은 이번 실행시각(2026-10-13)이며 **2024/25 사업년도 말 또는 2026-10-08 시장일 당시에 알았던 투자신호로 인정 금지**.
4. `official_api_pit_bridge.build_official_price_snapshot(...,basic_candidate_screen=True)`는 기존 가격 TOP20을 그대로 만들고, **opt-in에서만 전체 현재 거래관측 주권의 기존 로컬 3개월/6개월 가격강도 계산**을 별도로 실행한 뒤 재무 10개 기업만 추려 증거를 결합. 기존 WATCH 점수/승격/거래 DB/알림/일주월 보고는 변경하지 않음.
5. `official_basic_candidates.build_basic_candidate_research`는 재무 10개 기업에 KRX 주가 3/6개월 변화, 매출 YoY·영업익 YoY, 현재 사업년도 매출 성장 가속(3년 원본 없는 종목은 **N/A**)을 같이 표시. **관찰 순서**는 `세 지표(3개월 가격·매출 YoY·영업익 YoY) 양(+) 방향 일치 개수`→ 기존 25점 가격강도→실제 매출 YoY; **투자 1~20위 / 공식 100점/CONFIRMED ≠ 이 임시 순서**. 세 지표 하나라도 자료 없으면 `DATA_INCOMPLETE`, 임의 0으로 채우지 않음. 기업 10개 중 가격·매출·영업익 동시에 증가한 회사 **0개**로 실제 원본에 표시, 허위 대장주 승격0.
6. `scripts/publish_basic_company_screen.py` 재생 가능 CLI: 처음 DART 시장 PIN/캡처 폴더/멀티기업 매니페스트 영수증 SHA 검증 → 기존 `build_official_price_snapshot(top=20)` → 기존 `run_official_research(...,basic_candidates=True)` → 신생 새 사이트 `basic_candidates_kr.html`, SHA 봉인 `basic_candidates_kr.json`, 원래 `site/kr.html`, `factor_readiness_kr.html`, `site/index.html`에서 후보 링크. **오직 새로운 출력 폴더**에 게시하고 전일 상태 덮어쓰기0.
7. 실제 실행 출력: `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/` (git ignored). 실제 KRX 기준 **2026-10-08 거래관측행 2,765**, DART 같은 거래일 공시 **992건**, 2024/25 CFS 10개 기업, 비교 가능한 10/10, 연구용 WATCH20, 일·주·월 보고서3, 실전 메시지0, 공식 대장주 0. Mac 로컬 서버 `http://127.0.0.1:8770/basic_candidates_kr.html` 및 기존 `kr.html` **HTTP200**, Chrome에서 페이지 open PASS.

## 비추천·누락 투명성

- 3개월/6개월 가격 이력은 **기존 로컬 가격 캐시**라 원래 공급자 first-availability, 역사 기업행동/상폐/주권 클래스에 대한 전시장 PIT 인증이 아직 안 됐음.
- DART FY2024/25 재무자료는 처음 **2026-10-13 시각에 수집**. 역사적 최신 공개 시각·수정공시 일지·거래가능성 독립 인증 아님.
- 10개 대상은 여러 업종의 **우선 수집 표본**으로 선택한 것이며, 전 종목 2,765의 재무 완전 확보를 의미하지 않음. 수급·산업성장·현금흐름·시가총액·가치/위험/리밸런싱 모델은 N/A.
- `comparison_order`는 발굴 연구용 정렬일 뿐 투자 우선순위가 아니며 `total_score_100=None`, `official_future_leaders=0`, `precision@K=N/A` 유지. 이후 실제 PIT 인증과 전시장 커버리지/동일 산업 peers 확보 후 검증된 종합순위 개발.

## 자동·실제 테스트

- 신규 `tests/test_dart_multi_company.py`: 최대종목 수·중복·회계연도 고정·원본 재사용·무API 재검증·정정중복 차단·누락 시 `NOT_CAPTURED` 확인.
- 신규 `tests/test_official_basic_candidates.py`: 다양한 주가/실적 방향 정렬, 가격 TOP20 밖, 진짜 100점 N/A, 자료 없는 지표 N/A, 최초 수신이 미래면 차단, 사업일 불일치·음수/범위초과 가격, HTML SHA/파일 재발행 방지.
- 기존 `tests/test_official_api_pit_bridge.py`의 FY3 synthetic에서 새 opt-in 후보 페이지와 원형 가격 TOP1 무변경을 통합 E2E 검사.
- 실제 DART API **새 18호출+기존 first SHA 2건**, 기존 KRX/DART/SEC 원문/동일날 SHA read-only 재연결 시 후보 비교 HTML/JSON/보고/DRY-RUN E2E PASS. 시장의 공식 전향적 대장주 예측 성능은 별도 장기간 평가 필요.
- 관련 테스트/컴파일 통과 개수·커밋SHA/원격 푸시는 후속 `PROJECT_STATE.md` 최신 상태에 기록.

## 다음 **기본 기능** 개발 순서

1. DART 자료를 중복 호출 없이 우선 10개→20개→50개→시장 내 대표 산업 peers로 확대하면서 신뢰할 수 있는 최초공개·최초로컬 수신시각을 따로 유지.
2. 가격 + 실제 실적 가속 + 산업 성장성(실제 ECOS/KOSIS/FRED 원본) + 기관/외국인 수급을 종목별로 연결. 결측/N/A가 있으면 종합100점·실전 BUY순위로 승격 금지.
3. 종목 데이터 갱신/후보 최초 발견일부터 실전 5/20거래일 성능·전향적 precision@K를 기록한 뒤 기술적 완성률 인수 점수에 반영.
4. 보안·백업 추가확장은 운영상 필요 수준까지만. 과거 95/99% 전체 완료 추정은 철회. 개발인수 `45/120=37.5%(표시38%)`는 **아직 30ID의 다음 전체 관문을 새로 통과한 증거가 부족하여 이번 소규모 샘플 확대만으로 상향하지 않음**.
