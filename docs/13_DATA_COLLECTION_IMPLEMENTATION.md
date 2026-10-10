# EraLeader 데이터 수집·파이프라인 구현 명세

> 기준일: 2026-10-10 KST
> 상태: **개발 명세(실 API 연동 및 데이터 계약 검증 전)**
> 원칙: 공식·적법한 데이터 우선 → 정확한 PIT 재현 → Python 자동 수집 → 대장주 발굴 성능 검증.
> 관련 명세: \`02_DATA_PIT_SPEC.md\`, \`03_LEADER_DISCOVERY_LOGIC.md\`, \`04_BACKTEST_VALIDATION.md\`, \`11_DATA_SOURCES_COSTS.md\`.

## 1. 목적과 데이터 종류

EraLeader가 수집할 자료를 **(A) 공급자가 주는 원자료**, **(B) 원자료로 계산하는 파생지표**, **(C) 별도 유료 계약이 필요한 자료**, **(D) 공시·뉴스를 분석해 추출하는 자료**로 구분한다. 이 구분이 없으면 비용과 검증 범위가 불분명해진다.

| 수집 범주 | 1차 원자료 | 자체 계산/추출 | 비용·제약 |
|---|---|---|---|
| 주가·거래량 | 일별 OHLCV, 종목 상태, 기업행동 | 주봉/월봉, RSI, 10/20/60/120일선, RS, 거래대금, 밴드 | 한국 KRX 일별 API는 이용신청/승인, 실시간·분봉은 별도 공급자 |
| 기업 실적 | 재무제표, 공시 시각, 보고서 원문 | 매출/이익 YoY, 가속도, 마진, CAPEX, FCF | 한국 OpenDART·미국 SEC는 핵심 공개 자료 제공 |
| 컨센서스 | 당시 기록된 EPS/영업이익 전망 스냅샷 | 최근 1·3개월 추정치 변화, 상향 비율 | 일별/과거 이력은 통상 유료; 현재치로 과거를 재구성하면 안 됨 |
| 산업·거시 | 금리, 환율, 물가, 생산, 수출, 고용, 통화량 | 국면, 산업 이익/투자 성장, 산업 RS | ECOS/KOSIS/FRED/ALFRED 등의 소스별 공표 시각·수정 이력 |
| 공시·기업이벤트 | 계약·증설·수주·상폐·공시·정정 | 이벤트 분류, 경쟁력 변화, 산업 공급 병목 | 공시 API + 문서 파싱, 뉴스 이용약관/신뢰성 고려 |
| 선택적 대체데이터 | 산업별 시장점유율·공급망·수주잔고 등 | 산업 성장 속도, 경쟁력, 주도기업 후보 | 표준 단일 API 없음; 유료 및 비정형 출처 많음 |

**대장주 조기 발굴 목표:** 단순히 주가 상승률 상위 종목을 찾는 것이 아니라 산업 성장 → 기업 실적 가속 → RS 상승이 결합되는 시기를 포착한다.

## 2. ① 주가·거래량 데이터 수집

### 한국
- **KRX OPEN API:** KOSPI/KOSDAQ 일별매매정보 등 서비스별 이용신청·인증·쿼터 확인.
- **수집 필드:** 거래일, 종목 식별자, 시가/고가/저가/종가, 거래량, 거래대금, 거래정지 여부(가능하면), 상장/상폐 이력.
- **주의:** KRX의 일별매매정보 API가 실시간/분봉까지 자동 제공한다고 가정하지 않는다. 공식 제공 기간·권한은 연결 시 재확인한다.
- **실시간/분봉 추가:** 증권사 Open API 또는 전문 시세 공급자; 인증·계약·호출량·재배포 제한 검토.

### 미국
- **미국 시세 공급자 별도 선택:** 거래소별 일봉 OHLCV와 가격조정/기업행동/상장폐지 이력의 범위, 보유기간, 재배포 가능여부, 요금 비교.
- SEC EDGAR는 미국의 **공시·재무** 공급자이며, OHLCV 대체 공급자가 아니다.
- 무료 시세 제공자는 과거 상폐기업 누락 가능성이 있어 장기 PIT 백테스트의 공식 데이터로 즉시 채택하지 않는다.

### Python 파생 지표
- 일봉 → 주봉(주간 **마지막 완성 거래일** 종가), 월봉(월말 **마감 확정** 값)
- 수익률, 거래량 추세, 거래대금, 10/20/60/120일 이동평균, 10/20주 이동평균, 5/10/20개월 이동평균, RSI, 볼린저밴드, 종목/업종 RS
- **미완성 주봉·월봉은 잠정값:** 확정 신호와 분리 표시.
- t일 종가 기반 신호는 t일 장 종료 뒤에만 알 수 있으므로, 거래 성과 시뮬레이션에선 다음 거래가능 시점부터 체결한다.
- 분할/배당 반영 수익률용 보정가격과 실체결가격을 분리한다.

## 3. ② 기업 재무·실적 수집

### 한국 — OpenDART
- 공식: https://opendart.fss.or.kr/
- 문서 및 예시 엔드포인트: \`https://opendart.fss.or.kr/api/corpCode.xml\` (기업식별정보), \`https://opendart.fss.or.kr/api/fnlttSinglAcnt.json\` (단일회사 주요계정). 실제 파라미터와 사용가능 기간은 공식 안내로 확인.
- 매출액, 영업이익, 당기순이익, 자산/부채, 현금흐름표 및 투자활동 현금흐름 관련 항목을 **공시 본문/재무제표 범위 내에서** 표준화.
- 공시의 접수 시점, 정정공시 버전, 사업연도/분기 및 연결/별도 구분 보존.
- 특정 기업의 재무 항목이 없으면 \`N/A\`로 남겨 점수의 커버리지 표기.

### 미국 — SEC EDGAR
- 공식 API 안내: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- \`https://data.sec.gov/submissions/CIK##########.json\`: 공시 목록(접수 관련 정보).
- \`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json\`: XBRL 태그별 과거 재무 사실.
- 미국 SEC 요청 정책, 적절한 User-Agent 식별, 요청 제한, 원본 공시 타임스탬프·XBRL 표준 단위를 준수한다.
- 10-K/10-Q 등 원문이 필요하면 공시 링크의 서류를 조회해 구조화하고 공시 이용가능 시각을 보존한다.
- 회계기준 및 태그 차이를 동일 '영업이익' 등으로 무조건 매핑하지 않고 정의·가용성을 명시.

### 자체 계산
\`YoY = (이번 기간 금액 / 전년 동기 금액) - 1\` (분모<=0이나 음수 시 별도 규칙).
- 매출·이익 성장률, 성장 가속(\`최근 YoY - 직전 비교가능 YoY\`), 영업이익률, FCF, CAPEX 증가율, 재무안정성·효율성.
- 재무정보는 **보고기간 종료일이 아니라 최초 공시/이용가능 일시**부터 모델에 투입.

### EPS·영업이익 전망치
- 한국 FnGuide 등, 미국 전문 컨센서스 공급자: \`snapshot_at\`을 가진 **과거 시계열 스냅샷**이 필요한 별도 서비스.
- \`revision_1m/3m\`, 추정치 상향 기업 비율, 컨센서스 커버리지 등 파생.
- 구매 전 공시 재무만 이용한 기본 모델 vs 컨센서스 포함 모델의 추가 성능을 비교.
- 과거 컨센서스가 없으면 \`N/A\`; **현재 추정치나 당시 존재하지 않았던 전망치를 과거에 소급 적용 금지**.

## 4. ③ 산업·거시 데이터 수집

| 데이터 종류 | 공급자 | 수집/계산 | 주의 |
|---|---|---|---|
| 한국 기준금리·환율·통화량·경제통계 | 한국은행 ECOS (https://ecos.bok.or.kr/) | 공개 통계 API → 시계열 정규화 | 발표일/수정 이력 검증 |
| 산업생산·고용·물가·산업통계 | KOSIS (https://kosis.kr/openapi/) | 공개 통계 API → 계절성·증감 계산 | 분류 체계 변경 추적 |
| 미국 금리·물가·고용·M2 등 | FRED (https://fred.stlouisfed.org/docs/api/fred/) | 시계열 API | 가장 최근 수정치가 곧 과거 당시 값은 아님 |
| 과거에 공개됐던 미국 경제지표 빈티지 | ALFRED (https://alfred.stlouisfed.org/) | \`realtime_start/end\` 등 빈티지 조회 | 데이터별 빈티지 이용범위 확인 |
| 산업 매출·CAPEX 성장률 | DART/SEC+산업 분류 | 회사별 재무 집계 | 산업 분류의 시점별 변화 |
| 업종 RS·신규 고점/저점 비율 | 주가+업종/상장 이력 | Python 일·주·월 계산 | 미래에 확정된 업종 편입정보 소급 금지 |

**산업 성장의 인과 분석 예:** AI 컴퓨팅 투자 증가 → 반도체 → 데이터센터 → 전력설비 → 송배전 투자. 이 연쇄는 탐색 가설이지 사전 확정된 유망산업 목록이 아니다.

## 5. ④ 공시·뉴스·이벤트·대체 데이터

| 항목 | 실수집 방법 | 특기사항 |
|---|---|---|
| 주요 계약·수주·CAPEX | OpenDART와 SEC 공시 목록/원문 | 서류별 파서 + 날짜/정정/금액/단위 |
| 산업 정책·규제 | 정부/규제기관 공식 발표 RSS·웹/API | 1차 출처 우선, 적용일과 발표일 구별 |
| 기업 뉴스·산업 뉴스 | GDELT 등 제공 API 및 허가된 뉴스 데이터 | 중복 제거, 신뢰도, 재배포 저작권 준수 |
| 상장·상장폐지·종목 변경 | 거래소/시세 공급자·기업행동 이력 | 백테스트의 필수 데이터 |
| 시장점유율·공급망·수주잔고 | 사업보고서·산업 연구·통계·선택적 데이터 계약 | 보편 API 없음. 보고 기준, 추정오차 별도 보관 |
| 대체 데이터 | 특정 공급업체 계약(선택) | 위성·카드·물류 등은 비용/적법성/성과 검증 후 |

텍스트 파싱/LLM은 이벤트 **후보 추출**에 사용 가능하지만, 공식 공시와 대조 전에는 점수를 확정하지 않는다. 모든 뉴스·공시 이벤트는 \`published_at, first_available_at, source_url, extractor_version, confidence\`를 보존한다.

## 6. 데이터 파이프라인 및 저장 위치

\`\`\`text
[원천 API / 공식 공시 / 허가된 뉴스]
        ↓ 수집 어댑터 + rate limit + 재시도 + 증분 watermark
[원본 불변 저장(raw, provider response, 요청/수신 시각)]
        ↓ 스키마 정규화 (종목ID/시각/통화/단위/주식분할)
[품질 게이트: 중복·누락·정정·결측·상폐·비정상값]
        ↓ PIT: first_available_at <= 당시 판단 시각
[버전화된 Parquet/DuckDB 저장]
        ↓ 일봉 파생지표 + 산업/기업 특징 계산
[대장주 점수 → 잠재/확정/약화·교체 상태 및 이벤트]
        ↓
[선정 이력 저장 + 모듈별 PIT 백테스트]
        ↓
[웹 대시보드 / 상태변경 알림 / 일·주·월 보고서]
\`\`\`

### 모듈별 인터페이스(초기 계약)

\`\`\`python
ingest(source, start, end) -> RawManifest
normalize(raw_manifest) -> NormalizedDataset
validate(dataset) -> QualityReport
snapshot(as_of, universe_policy) -> PITSnapshot
compute_features(snapshot) -> FeatureTable
rank_and_transition(features, previous_state) -> CandidateEvents
evaluate(signal_stream, pit_market_data) -> BacktestReport
publish(snapshot, events, metrics) -> DashboardAndReports
\`\`\`

### 권장 저장 구조(실행 코드 구축 전)

\`\`\`text
/Volumes/T5DATA/eraleader/
  docs/13_DATA_COLLECTION_IMPLEMENTATION.md
  src/eraleader/data/sources/{krx,dart,sec,us_price,ecos,kosis,fred,news}
  src/eraleader/data/{normalize,quality,pit,store}
  storage/raw/{kr,us,macro,filings,news}
  storage/curated/{prices,fundamentals,macro,events,industry}
  storage/pit_snapshots/
  storage/runs/
  tests/{data,pit,integrations}
  output/{rankings,backtests,reports}
\`\`\`

자료를 GitHub에 올리지 않고, 코드/명세/테스트만 별도 비공개 저장소에 저장한다. 인증키는 환경변수나 .env(추적 제외)를 사용.

## 7. 스케줄 및 재시도 설계

| 실행 시점 | 작업 | 주의 |
|---|---|---|
| 한국 거래소 종가 확정 뒤 | KRX 가격, 기업행동, 국내 공시 증분 수집 | 거래소 휴장·지연 확인 |
| 미국 거래소 종가 확정 뒤 | 미국 가격 증분, SEC 공시 증분 수집 | 미국 서머타임·거래 캘린더 반영 |
| 매일 | 신규 기업 공시·뉴스, FRED/ECOS 공개 통계 빈티지 확인 | 새 수치만 ingest |
| 매주 | 업종 RS, 산업 강도/상승 확산도, 후보 상태 갱신 | 주봉 확정 뒤 |
| 분기보고/연간보고 발행 시 | 해당 기업 재무·이익 모멘텀 업데이트 | 발표시각 이후 |
| 월말/매월 | 월봉 확정, 산업 비교, 리밸런싱용 **참고 후보** 및 성과 보고 | 자동주문 미포함 |

실패 시 백오프/제한 재시도, 부분 실패 저장, 다음 실행에 중복 삽입 방지(\`source+symbol+period+revision\` 고유키). 원본 재다운로드를 피하고 \`watermark\`로 증분 처리. 각 실행 결과에 조회된 기간·종목수·성공/실패·결측비율·API 쿼터 사용량 기록.

## 8. 구축 우선순위와 과금 게이트

### 1차(최소 기능 MVP)
- 한국·미국 **일봉 및 기본 재무** 데이터(수집 권한 되는 국가부터), 원본 저장.
- 종목별 PIT 스냅샷과 상장 상태를 검증하고 상대강도·성장률·기본 산업 점수 산출.
- 간단한 후보 TOP20/TOP10 + JSON 저장 + 최소 웹 조회.
- 상장폐지/기업행동 데이터 부족 시 장기 성과 평가를 '제한적'으로 표시.

### 2차(산업 조기 발견 강화)
- ECOS/FRED/KOSIS/ALFRED, 산업별 성장·투자, 공식 공시 이벤트.
- 산업 강도와 기업 실적 변화 결합, 이벤트 근거와 반증 신호 표시.
- 모듈별 PIT 백테스트/워크포워드 고도화.

### 3차(추가 성능 입증 후 도입)
- 과거 EPS 컨센서스, 시장점유율, 공급망/수주, 선택적 대체 데이터.
- 개별 데이터의 추가 정보가치(ablation)와 성능 개선을 검증한 뒤 비용 지출.
- 유료 데이터 없이도 이전 단계 시스템이 정상 운영되게 설계.

**주의:** 과거 종목군/상장폐지/기업행동/PIT 기준은 비용 최적화 때문에 마지막 단계로 미루면 안 된다. 연구 가능한 기간과 벤치마크 범위를 처음부터 정직하게 제한한다.

## 9. 실제 개발 착수 전 확인 사항

- KRX API 및 OpenDART 이용 신청/인증키 발급 여부(키 채팅창/리포트 공유 금지).
- 미국 일별 시세 공급자 및 장기 종목·상폐 이력의 품질/가격/라이선스.
- KRX·DART·SEC·ECOS·KOSIS·FRED 각각에서 실제 호출 가능 범위·요청 제한·개별 파라미터.
- 국내외 종목 ID·상장 이력·기업행동 확보 방법.
- 예산 제약과 과거 10~15년 성능 검증의 최소 커버리지 기준.
- \`CycleOS-Lab_BacktestEngine\` 등 범용 백테스트 엔진과의 연결은 실제 코드 점검 뒤 결정.

## 10. 테스트 완료 기준 (검증 없이는 '완료' 금지)

1. 각 소스에서 최소 1개 실제 종목/시계열 응답 저장, 원본/정규화 결과가 일치.
2. 같은 날짜 중복 수집해도 행 수 증가하지 않음.
3. t 이후 미래 공시·정정공시를 임의 투입해도 t시점 후보 결과가 변경되지 않음.
4. 상장폐지/거래정지/분할 등 표본으로 PIT 품질 테스트.
5. 누락 데이터 N/A와 데이터 기준 시각이 UI/보고서에 그대로 노출.
6. 최신 실행 결과: run_id, 데이터 커버리지, 에러 코드, 테스트 통과/실패 수, 파일 해시 기록.
7. 산업·기업 점수의 기본 모델 대비 성능은 별도 PIT 백테스트로 평가하고, 가상 데이터 테스트 결과를 실제 투자 성과로 표현하지 않는다.

## 11. 공식 문서·API 참고 링크

- 한국거래소 KRX OPEN API: https://openapi.krx.co.kr/
- 금융감독원 OpenDART: https://opendart.fss.or.kr/
- 미국 SEC EDGAR API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- 한국은행 ECOS: https://ecos.bok.or.kr/
- 국가통계포털 KOSIS OPEN API: https://kosis.kr/openapi/
- 미국 FRED API: https://fred.stlouisfed.org/docs/api/fred/
- ALFRED: https://alfred.stlouisfed.org/
- GDELT(뉴스 데이터): https://www.gdeltproject.org/
- FnGuide FnSpace(유료 컨센서스): https://fnspace1.fnguide.com/

> 링크·쿼터·유료 계약 세부사항은 연결 시점에 공식 사이트에서 다시 확인한다. 이 문서는 설계 명세이며 연결을 완료했다는 뜻이 아니다.
