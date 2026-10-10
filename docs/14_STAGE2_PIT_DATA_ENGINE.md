# 2단계 개발 — PIT 데이터 검증·저장 엔진

> 현 상태: 구현 명세 / 아직 실제 API·코드 구현 전. 입력은 1단계 수집기 출력. 후속 단계는 3단계 분석 엔진.
> 목표: 특정 과거 날짜에 실제로 알 수 있었던 데이터만 정확하게 복구하고, 중복·오류·정정·상장폐지 이력을 관리한다.

## 1. 수집/입력 데이터

| 유형 | 필요한 자료 | 출처(1단계 어댑터) | 시점 필드 | 실패 시 |
|---|---|---|---|---|
| 일별 OHLCV | 일시·종목·거래가격·량·거래대금 | KRX / 미국 시세 공급자 | session_date, received_at | 누락 표시/신호 보류 |
| 재무 원자료 | 매출·영업이익·분기·연결/별도 | DART / SEC | period_end, filed_at, available_at | PIT 이후 배제 |
| 추정치 이력(선택) | 당시 EPS 예상 스냅샷 | 적법한 컨센서스 공급자 | snapshot_at, available_at | N/A; 다른 모델 |
| 기업행동 | 분할·배당·합병·상폐·티커 변경 | 거래소/가격 공급자 | effective_at, known_at | 공식 백테스트 차단 |
| 종목 이력 | 상장·상장폐지·산업 분류 | 거래소/시세·업종 공급자 | valid_from, valid_to | 결과 커버리지 제한 |
| 거시 빈티지 | 관측일·첫 공개일·수정/공개버전 | ECOS/KOSIS/FRED/ALFRED | release_at, vintage_at | 과거 재현 불가 표시 |

원시 API payload는 공급자별로 **수정 없이** 저장하고 변환 전/후 row_count 및 SHA256을 기록한다. 이용약관 위반 업로드·재배포 금지.

## 2. 실제로 만들 모듈

\`\`\`text
src/eraleader/data/
  raw_store.py           # 원본 payload append-only/immutable
  schemas.py             # pyarrow/typing 스키마
  symbol_master.py       # 국가별 symbol → security_id, ticker history
  corporate_actions.py   # split/dividend/delist as-of 조회
  normalize.py           # 거래일/타임존/통화/단위/연결·별도 표준화
  validate.py            # 시점, 중복, 음수/0, 장외 날짜, 가격·재무 단위
  pit.py                 # as_of 원천 join, 데이터 이용가능시점 여과
  store.py               # DuckDB + Parquet (초기 제안)
  manifests.py           # schema_version / source_version / run_id
tests/data/ tests/pit/
\`\`\`

### 키와 스키마
- \`security_id\`: 변경되지 않는 내부 종목 고유 ID. ticker만 키로 사용 금지.
- \`price_bar\`: security_id, session_date, OHLCV, currency, source, ingest_at, adjustment_version
- \`fundamental_fact\`: security_id, metric, value, unit, fiscal_period, period_end, filing_id, first_available_at, revision_id
- \`security_membership\`: security_id, market, industry_id, valid_from, valid_to, known_at
- \`corporate_action\`: security_id, action_type, ex_date, ratio, cash_amount, known_at
- \`macro_vintage\`: series_id, observation_date, value, release_at, vintage_at, revision
- \`pit_snapshot\`: as_of, universe_version, input_cutoff, data_hash, quality_flags
- 원본 파일명: \`storage/raw/{source}/YYYY/MM/DD/{request_hash}.json.gz\`; 재시도 중복 제거.
- 표준화/스냅샷: \`storage/curated/{market}/{table}/...\`, \`storage/pit_snapshots/{as_of}/{version}/...\`

### PIT 알고리즘
\`\`\`python
def asof_fact(facts, decision_at):
    available = facts[facts.first_available_at <= decision_at]
    # filing correction도 '당시까지' 들어온 것만 취함
    return latest_revision_per_security_metric_period(available)

def security_universe(master, as_of):
    return master[(master.valid_from <= as_of) & (as_of < master.valid_to)]
\`\`\`
- 거래소 현지 시각, 한국/미국 공시 접수 시각 및 공급자 지연 허용.
- 매일 장마감 후 확정 신호는 종가 확정 후 계산; 당일 미완성 주·월봉은 확정 신호 불가.
- 실제로 오래전 '처음 데이터 제공 시작일'이 불명확한 데이터는 보수적으로 당시 사용 불가 처리하거나 제한 표기.

## 3. 정합성 및 차단 조건

1. PK 중복, 공시 시점 역전, 상장 전·상폐 후 가격, OHLC 모순, 거래량 음수, 무효 통화, 유사종목 ticker 충돌 탐지.
2. 재무 **사업기간 종료일 != 공개일**; 공시 수정은 이전 행 덮어쓰지 말고 새 버전 추가.
3. 기업행동은 발표일/실시일 분리; 조정가격 버전/실체결가격 별도 저장.
4. 미래 시점/정정 데이터가 누출되면 해당 구간 결과 전체를 무효로 표시.
5. 필수 자료 결측이면 후보 PENDING_DATA, 선택 항목 결측이면 모델별 점수 정책 적용 및 missing_fields 출력.

## 4. 순차 구현 작업

- S2.1 단일 데이터 소스 raw/normalized 스키마 작성, 20행 표본 로드/검증.
- S2.2 국내·미국 종목 동일 식별 체계와 상장/상폐 이력 구축.
- S2.3 DART/SEC 공시 발표 시각 및 revision history, 수익률 기업행동 처리.
- S2.4 as-of snapshot 생성과 계약 기반 조회 메서드.
- S2.5 DuckDB 쿼리+Parquet 분할 저장, 빠른 재실행/캐싱.
- S2.6 오류 요약/커버리지 보고, 소규모 실제 데이터 e2e 통과.

## 5. 실행 계약(목표 CLI)

\`\`\`bash
python -m eraleader.cli data validate --source krx --start 2020-01-01 --end 2020-12-31
python -m eraleader.cli data snapshot --as-of "2020-08-14T16:00:00+09:00" --market KR
python -m pytest tests/data tests/pit -q
\`\`\`
명령어는 구현 후 확인할 **목표 인터페이스**이며 현재 실행 완료 의미가 아님.

## 6. 완료 검증과 산출물

- 테스트 A: 2020-05-01 시점 생성 → 2020-05-03 공시 추가해도 5/1 스냅샷 불변.
- 테스트 B: 정정공시가 3개월 뒤에 나왔을 때 과거 시점 원값 유지.
- 테스트 C: 상장폐지 기업 포함 당시 universe 및 가격/체결 제한 반영.
- 테스트 D: 분할/배당 전후 수익률 왜곡 없는 조정계열 재현.
- 테스트 E: 동일 실행을 2회 해도 건수/스냅샷 해시 동일.
- 산출물: \`dataset_manifest.json\`, \`quality_report.json\`, \`pit_snapshot.parquet\`, \`unit_tests.txt\`.
- **Gate S2:** 누수 테스트 0건 실패, 중복 방지 및 주요 시점 품질 통과. 상폐 이력 미확보 시 '장기 수익 백테스트 가능' 선언 금지.

## 7. 이후 연결
\`get_pit_snapshot(market, as_of, required_fields) -> {universe, prices, fundamentals, macro, available_at, quality_flags, hashes}\`. 3단계는 오직 이 계약으로 데이터를 가져온다.
