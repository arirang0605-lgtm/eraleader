# 142 — 실제 DART 업종코드 기반 산업 대분류/기업 실적·가격 비교 (기본 발굴 기능)

**개발일:** 2026-10-13 KST. **개발 ID:** 1_2 · 3_1 · 3_2 · 3_3 · 3_4 · 4_1 · 6_2.
**기준 코드:** `feature/core-official-factor-coverage-20261013` / `0c6b947e667d470ee9174c7fa82e8bedfcad5591`.
**사용자 지시:** 백업·에스크로 등 부가 기능 확장을 중단하고 **실제 대장주 발굴 기본 기능**부터 완성. 기존 정상 PRICE WATCH20·FY CFS원시 SHA·기존 실물 대시보드 보존.

## 해결된 기본 발굴 문제

이전 `basic_candidates_kr.html`은 실제 FY2024/25 DART 연결 CFS 10개 회사와 3/6개월 가격을 비교할 수 있지만, 회사의 **실제 산업/업종 구분이 N/A**여서 같은 산업에 속한 기업을 서로 비교할 수 없었다.

1. 새 `src/eraleader/official_dart_industry.py`: OpenDART **`company.json`** 기업현황의 공개 `induty_code`(현재 산업코드), `corp_cls`(현 KOSPI/KOSDAQ 구분)를 수집. 기존 DART `corpCode.zip`의 **최초 받은 SHA와 기업 고유번호 `corp_code`, 원래 KRX 실제 종목코드**가 모두 맞을 때만 유효. `_http_get` HTTPS 공식 호스트/무리다이렉트/응답 크기 제한 및 `official_dart_corp_directory.verify_dart_corp_directory`를 재사용. 민감한 사업자번호·주소·개별 연락처는 원시 JSON 비공개 저장 외 **공개 연구 결과에 불포함**. SHA256 첫 영수증/원문/첫 로컬 수신 시각·현 기업분류를 `output/official_api_capture/dart_company_<uuid>/` 0700/0600에 보관. 동일 기업의 현재 프로필 원본이 중복 관측되면 임의 채택 금지, 정정 검토로 BLOCK.
2. 독립 배치 CLI `scripts/capture_dart_industry.py`: 기존 10개 후보의 SHA 봉인된 `basic_candidates_kr.json`과 기존 공인 DART directory 첫 영수증 SHA에서만 종목 목록을 추출하여 **최대 20개 회사** 첫 수신. `--only-existing` 시 추가 API호출0 및 누락 N/A; 중복 첫 receipts/임의 회사/시점 초과/기업 클래스 불일치 차단. 승인된 기존 Mac DART 키를 기존 `credentials` 로더로만 사용하고 콘솔·Git에 출력하지 않음.
3. 새 `src/eraleader/official_industry_peer_screen.py`: 기존 가격+실적 후보 `basic_candidates_kr.json` 자체의 SHA256 및 실제 DART **각 기업의 첫 원시 영수증**을 독립 검증한 뒤, `induty_code` 앞 2자리를 **KSIC 산업 대분류**로 연구 묶음. 세부 원코드(3~5자리)를 그대로 보여 그룹 내 **유사업종이지만 직접 경쟁사가 아닐 수 있다**고 표시. 같은 대분류에 표본이 **2개 이상**인 경우에만 실제 선택된 기업의 **매출 YoY 순위·영업익 YoY 순위·3개월 주가 순위**를 1/N 방식으로 계산; 표본1/지표 결손 시 N/A. 동률 시 코드 오름차순 결정적. 대분류 평균은 **표본 평균**이지 실제 산업 전체 성장률이 아니며, 종합100점·매수1~20위·공인 대장주0/N/A 유지.
4. 독립 배포 CLI `scripts/publish_dart_industry_peers.py`: 실제 DART 회사코드 10개와 원본 profile first SHA 검증→연구 HTML/JSON SHA 봉인(`industry_peers_kr.html`, `industry_peers_kr.json`)을 기존 **운영 중 기본 후보 사이트**에 O_EXCL로 신규 파일만 작성, 메인/`kr.html`/`basic_candidates_kr.html`에 최소 링크 추가. PRICE WATCH/실적 데이터/SQLite/원시 API/일주월 보고·실전메시지 변경0. 기존 결과 재발행 덮어쓰기·변조된 표본 등 fail closed.

## 실제 Mac·T5DATA 공식 자료 결선

- 첫 제공자 수신 원본 **공식 KRX 2026-10-08 관측 2,765개 주권**/DART 당일 992개 공시, DART 현재 법인코드 고유번호 맵 + FY2024/25 연결 재무 10개 기업의 20개 영수증은 이전 성공 자료를 **재사용**.
- **신규 DART 회사 현황 공식 API 10개**(삼성전자/SK하이닉스/기아/현대차/한미반도체/두산에너빌리티/LGES/NAVER/삼성바이오/한화에어로)를 실제 조회·매 API응답 first raw SHA 체크: **10/10 정상**, `output/dart_industry_cohort_20261013_v1.json` (git ignored). 현재 세부 DART 코드 **9개**, 두자리 산업 대분류 **7개**.
- 해당 7개 중 **3개 대분류에서 2개 회사씩(6개)** 표본비교. 실제 FY2025 매출 YoY 비교와 현재 관측 3개월 가격강도:
  - **26 전자 관련**: 매출 YoY SK하이닉스 > 삼성전자, 3개월 가격 삼성전자 > SK하이닉스.
  - **29 기계 관련**: 매출 YoY 두산에너빌리티 > 한미반도체, 3개월 가격 한미반도체 > 두산에너빌리티.
  - **30 자동차 관련**: 매출 YoY 현대차 > 기아, 3개월 가격 기아 > 현대차.
  - 다른 대분류 **표본 1개이면 자동 N/A**. 이 그룹화는 KSIC 두자리 유사 산업 기준이므로 직접 경쟁사 또는 공식 세부 업종 peer라고 주장할 수 없다.
- 실제 출력 `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/site/industry_peers_kr.html`, 동일 output root `industry_peers_kr.json`, 로컬 서버 `http://127.0.0.1:8770/industry_peers_kr.html` **HTTP200**, Mac Google Chrome 열기 PASS. 기존 후보/가격/메인 링크에서 새 업종 비교 진입 가능.
- 원본 결합 SHA `338277723d3748628c7f6aac73f392638278b10ab5c6d4d77dd6cb2e6dcdfa72` 독립 JSON 재산출 PASS. 공인 미래대장주 0/실투자 알림0/실거래0.

## 시간정보·검증 상태·한계

- DART 회사별 현재 업종코드는 **2026-10-13에 처음 로컬 수신**. 역사적 KSIC 업종 분류/정정 시점·합병/상장폐지/영구 share-class PIT까지 검증된 자료가 아님.
- 가격의 거래일(2026-10-08)과 실제 회사 첫 수신(2026-10-13)을 구분하며 **시가·성과 소급으로 돌려 쓰지 않음**. 주가 3/6개월 이력은 기존 가격 캐시(원시 제공자 당시 가용 증명 없음) 사용. 기업당 FY2024/25 두 연도만 확보; 실적 성장 가속도는 FY2023 추가 원본 있는 회사만 가능.
- 산업전체 성장 통계·수급(기관/외국인)·FCF·시장점유율·뉴스 촉매·산업 비중/기업행동/과최적화 검증·공인 종합100점·선행 적중률 **N/A**, 스크린 현재는 10개사를 선택한 표본이다.
- 신규 `tests/test_official_dart_industry.py`+ `tests/test_official_industry_peer_screen.py` 등 실제 DART 업종 파서/정정/최초시각/국내기업 원본 교차검증/동일 업종 peer 랭크/시점 거부/SHA 무결성/사이트 O_EXCL/HTML escaping 테스트. 관련 1_2·3_1·3_3·6_2 직접 테스트 수/EXIT는 최신 `PROJECT_STATE.md`에 기록; 전체 2450+ 회귀는 현재 단계에서 불필요하게 재실행하지 않음.
- 기존 인수척도 **45/120=37.5%(표시38%) 유지**. 업종 분류 10개사 연결로 핵심기능 진전은 실제지만, 산업 전체 2,765종목 전수·산업통계/실전 PIT 인수 관문을 통과했다고 3단계 진행률을 과장하지 않음.

## 다음 기본 기능

1. 주가·재무·산업 비교가 가능한 종목군을 **업종별 최소 3~5개**로 확대. 중복공시 재호출 없이 DART first receipts를 재사용.
2. ECOS/KOSIS 업종별 실제 매출/출하량·CAPEX 성장 데이터의 최초 가용시각을 연결하고, 시장 전체 산업 성장과 **현 표본 평균의 차이**를 표시.
3. KRX 외국인·기관 공식 수급·PIT 개별 종목·기업행동 source 확보, 실적·가격과 합산 가능한 부분 평가를 연구하고 결측 인식 종합 모델 완성.
4. 그 후 업종·실적·가격·수급 전체 인수와 워크포워드·전향 성과 확인을 거쳐야 진짜 *미래 대장주 조기 발굴 1~20위*가 가능하다. 보조 백업/에스크로 추가개발은 계속 후순위.
