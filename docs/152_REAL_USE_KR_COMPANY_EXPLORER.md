# 152 — 공식 보관 자료 기반 종목 검색·상세 분석 화면 (실제 운용 기능)

**일자:** 2026-10-14 KST · **개발 ID:** 3_3·3_4·3_5·4_1·6_2 · **기준:** D-027(기능 구현 우선).

## 실제로 추가한 기능

- 신규 `src/eraleader/official_company_explorer.py`: 이미 검증된 KRX 가격 + DART 연간 연결 실적(CFS) + 현재 DART 업종 연구보고서 2개를 연결하여 **종목명·종목코드 검색, 업종 필터, 개별 기업 상세 페이지, 소규모 같은 업종 그룹 비교**를 제공한다.
- 브라우저에서 초기 전체 종목 표시 및 검색/필터(클라이언트 JS)→회사 선택→가격 3/6개월, 가격 강도, 3개년 매출성장 가속, 매출/영업이익 YoY, 업종별 표본 순서를 확인한다. 누락값은 N/A, 표본 1개면 업종 내 순위 N/A.
- `scripts/publish_official_company_explorer.py` CLI: 기존 완성 코호트 폴더와 새 출력 경로만 지정. **외부 신규 API/키움 조회/자동매매/알림 송신 0**, 기존 WATCH, 공식 원장, 최초 SHA·개발 상태 불변. HTML+JSON+종목별 페이지 생성.
- **데이터 시점 명확화:** 요청일, 실제 시장 관측일, 금융·업종 최초 로컬 수신시각, 자료 지연 경고 별도 표시. 가격·실적 연구표의 ‘관찰 순서’는 공식 대장주 투자순위가 아니며 종합 100점, 정식 확정, 실매매 기능 없음.
- 새 독립 출력 경로에만 원자 게시. 기존 자료의 SHA/종목ID/공시 수신 시점이 맞지 않으면 해당 자료를 게시하지 않는다. 이는 실제 사용자가 잘못된 기업 정보를 보지 않게 하는 **최소 필수 검증**이며 과도한 역사적 인증 업무를 추가하지 않는다.

## 실행 예시 (Mac/T5DATA, 보관된 공식 자료 읽기 전용)

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src python3 scripts/publish_official_company_explorer.py \
  --cohort "$PWD/output/same_session_cohort_3fy_20261013" \
  --day today \
  --out "$PWD/output/company_explorer_$(date +%Y%m%d)_manual"
```

동일 출력 폴더는 덮어쓰지 않는다. 브라우저에서는 새 폴더의 `index.html`과 각 종목 6자리코드 `.html`을 열어 사용할 수 있다. 자동 일일/주간 갱신 및 기존 종합 대시보드의 메뉴 직접 연결은 후속 구현 범위다.

## 실제 데이터·테스트 결과

- 기존 2026-10-08 공식 KRX 거래일 관측 + 2026-10-13 당시 최초 로컬 수신한 DART FY2023~25 연결재무 및 업종 보고서 재사용. 회사 **10개**, 같은 대분류 동종 표본 비교 가능한 기업 **6개**. 연구용 결과 `output/company_explorer_cli_20261014/index.html`, `005930.html` 등 10개 상세 페이지, `report.json` 신규 생성 성공. 지연 경고 활성, 현재 공식 전체 종목 투자순위 0.
- 신규 단위 기능 `tests/test_official_company_explorer.py` **13 PASS**: 종목 검색/비교 상세, HTML 이스케이프, SHA/회사 혼선·미래 관측·잘못된 수치 거부, 기존 게시물 덮어쓰기 방지, CLI 기본 사용과 오류.
- 직접 영향 4개 테스트 모듈(신규, 기존 가격·재무 후보, 업종 비교, 동일시점 게시) **48 PASS**. 로그 `output/verification_logs/company_explorer_impact_20261014.xml/.log`; 전체 수천 건 회귀 재실행 안 함(D-027 실운용 기준).
- Python 컴파일 PASS, 사용자 GitHub 공개 파일만 별도 staged 검사. 기존 원본 main, 미커밋 native_first_capture.py 및 MarketOS/SharedBrokerAPI는 건드리지 않음.

## 다음 핵심 개발
기존 대장주 검색기 메인 웹 메뉴에서 이 신규 종목 검색 화면을 열도록 연결하고, 최신 실제 공식 거래일 자동 전환과 업종·재무·수급의 결측 요약을 일/주/월 보고서에 이어 붙인다. 운용 인수기준은 D-027·D-028로 적용하고, 종전 엄격 38% 수치는 폐기한 역사 기록으로만 취급한다.
