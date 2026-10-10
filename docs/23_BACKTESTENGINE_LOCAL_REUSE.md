# EraLeader — T5DATA 기존 백테스트 자료 재사용 점검

> 점검일: 2026-10-10 KST · 점검 범위: 사용자 소유 외장 SSD 로컬 파일(읽기 전용 검사 + EraLeader에만 결과 저장)
>
> **핵심 결론:** \`/Volumes/T5DATA/backtestengine/\`는 비어 있었으나, \`/Volumes/T5DATA/CycleOS-Lab_BacktestEngine/\`에 재사용 가능한 가격 데이터와 모멘텀 백테스트 코드가 있다. **전량 재다운로드·백테스트 엔진 재작성부터 시작하지 않는다.** 단, 해당 자료는 그대로 PIT 적합성을 보장하지 않는다.

## 1. 확인된 기존 자산

| 활용도 | 경로 (기준: \`/Volumes/T5DATA/CycleOS-Lab_BacktestEngine/\`) | 실제 확인 내용 | EraLeader 활용 |
|---|---|---|---|
| 최우선 | \`datasets/external_validation/marcap/data/marcap-YYYY.parquet\` | 1995~2026년 **32개 파일, 15,648,407행**, 기존 점검 요약상 6,953개 종목 코드, **1995-05-02~2026-10-02** | 한국 주가·거래량·거래대금·시가총액 연구, **로컬 원본 재활용** |
| 우선 | \`datasets/yf_sp500_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet\` | S&P 500 구성 종목 주간 바 약 **901,171행**, 2026-02경까지 | 미국 모멘텀/RS 예비 연구용 |
| 우선 | \`datasets/yf_us_stock_w_pq_Asia_Seoul_2026-03-01_SSOT/bars.parquet\` | NASDAQ-100 기반 종목 주간 바 **153,582행** | 미국 종목 지표 검증용 |
| 참고 | \`datasets/yf_kr_stock_w_pq_Asia_Seoul_2026-03-01_SSOT/data.parquet\` | 한국 주간 바 **8,885행** | 코드 호환 스모크테스트용 (수집 범위 작음) |
| 활용 | \`cache/sector_returns_sp500_sectors_w_complete_2026-03-01.csv\` | 11업종 주간 수익률, 기존 manifest상 2,756기간(1973-05~2026-02) | 업종 모멘텀 **baseline 코드 실행** |
| 활용 | \`tools/backtest_mvp/grid_mom_rotation.py\` | lookback·Top N·리밸런싱·전환비용·CAGR·MDD 코드 | 기초 알고리즘 검증/비교. 수정 전 검토 필수 |
| 활용 | \`strategies/sector_mom.py\`, \`strategies/multiasset_mom.py\`, \`strategies/base.py\` | 전략 프로토콜·개별 모멘텀 로직 | 규칙 기반 실험의 비교 baseline |
| 선택 | \`tools/engine/run_registry.py\`, \`tools/engine/poll_requests.py\`, \`docs/BT_REQUEST_V0.md\` | registry 기반 실행, 요청·결과·해시·중복 관리 및 GCS SSOT 계약 | 재현성·run manifest·검증 패턴을 **참고**, 원격 GCS 자동 호출은 하지 않음 |
| 참고 | \`datasets/sp500_constituents_2026-03-01.csv\`, \`datasets/*universe*.txt\` | 특정 날짜의 종목군 스냅샷 | 현재 종목군 정규화 참고. 과거 시점 유니버스로 사용 금지 |
| 선택 | \`datasets/marketos_research_staging/\` 등 | 파일 존재 확인만 완료, 세부 품질은 미검증 | 추가 점검 후 채택 |

로컬 \`datasets/\`에 **약 1.33GB(바이트 합산 기준)** 파일이 존재한다. 그러나 중복 스냅샷·미검증 구간 포함이므로 전체를 EraLeader로 복사하거나 모두 신뢰해서는 안 된다.

## 2. 실제 수행한 검사

### A. 가격 파일 스키마 및 메타데이터 검사 — 통과
- 실행: \`/Volumes/T5DATA/CycleOS-Lab_BacktestEngine/.venv/bin/python /Volumes/T5DATA/eraleader/scripts/verify_backtestengine_reuse.py\`
- \`marcap-1995.parquet\`~\`marcap-2026.parquet\` 32개 Parquet **메타데이터 실제 합계 15,648,407행** = 기존 \`validation_summary.json\`의 행 수와 일치.
- 스키마 확인: \`Code, Name, Open, High, Low, Close, Volume, Amount, Marcap, Market, Date\` 등.
- 테스트 예: 2025년 696,524행; 2026년 529,701행; S&P 500 주봉 901,171행; NASDAQ-100 주봉 153,582행.
- **보고서 위치:** \`results/reuse_probe/local_assets_audit.json\`.
- 점검은 형식/파일 행 수와 최소 샘플을 확인한 것이며 전체 가격 데이터 오류·PIT 적합성을 인증한 것이 아니다.

### B. 기존 백테스트 엔진 실제 실행 — 통과
- 재다운로드 없이 기존 \`cache/sector_returns_sp500_sectors_w_complete_2026-03-01.csv\`를 사용.
- \`tools/backtest_mvp/grid_mom_rotation.py\`에 단일 설정을 적용:
  \`--lookbacks 26 --topns 2 --rebalances 4 --annual-mgmt 0.002 --switch-cost 0.001\`.
- 실제 결과: 평가 구간 1973-11-26~2026-02-23(2727주), \`CAGR=0.141114\`(약 14.1%), \`MDD=-0.559757\`(약 -56.0%).
- 결과 파일: \`results/reuse_probe/sector_mom_baseline_one_config.csv\`.
- **주의:** 이것은 업종 수익률에 대한 기존 계산 코드의 동작 확인이다. ERALEADER 대장주를 조기에 발굴한 기록도 아니며, 해당 섹터 시계열의 당대 존재여부·업종 구성의 PIT 적합성·거래 가능성은 추가 검증이 필요하다. 성과를 실전 수익 전망으로 인용 금지.

## 3. 최적 재사용 아키텍처

\`\`\`text
기존 CycleOS-Lab_BacktestEngine (READ ONLY)
   ├─ marcap/1995~2026 연도별 Parquet  [현지 로컬 캐시]
   ├─ 미국 주·월봉 Parquet / sector returns
   ├─ 기존 전략 모듈·registry·검증 코드
   └─ 기존 결과/데이터 메타데이터
                         │
                     read-only adapter
                         │
                EraLeader 데이터 계층
     종목 ID 표준화 → 기업행동/공시 시각 결합 → PIT 검증
                         │
             산업·기업 특징 + 주도주 후보/이력
                         │
         백테스트 adapter → baseline / 통합 검증
                         │
                웹·알림·정기 보고
\`\`\`

**데이터 복사 대신 로컬 절대경로/구성 가능한 경로로 연결**한다. SSD가 마운트되지 않으면 데이터 결측 오류를 표시하고 기존 데이터 파일을 수정하지 않는다. 특정 코드의 전략 로직을 직접 import할지, 독립 adapter로 재구현할지는 테스트와 라이선스 점검 후 결정한다.

## 4. 남아 있는 필수 작업 (PIT 안전성)

1. marcap의 **분할·배당 보정, 상장/상폐 완전성, 종목코드 이력, 거래정지·신주상장** 품질 확인.
2. 유료/공식 데이터와 일부 기간 샘플 교차검증. 1995년 이후 모두 완전한 당시 종목군이라는 근거 없음.
3. 미국 S&P500/NASDAQ100 자료는 2026-03-01 현재 구성 종목군으로 수집됐으므로 **과거 유니버스 PIT가 아니다**. 과거 실제 구성 변동/상폐 종목 필요.
4. 가격 파일만으로는 과거 DART/SEC 공시 이용시각·EPS 전망치 수정 이력·산업별 투자 증거를 확보할 수 없음.
5. 기존 \`yfinance\` 수집 데이터와 FinanceData/marcap의 라이선스·재사용·외부 표시 범위 확인(특히 웹 공개·배포).
6. 현재 가격까지 연결하려면 **기존 파일의 마지막 일자 이후만** 공식 공급자로 증분 수집하고, 충돌 건만 재검증. 2026년 marcap 요약의 마지막일은 2026-10-02.
7. \`tools/engine/poll_requests.py\` 등의 기존 요청/SSOT/GCS 자동 전송은 **실행하지 않음**. 새 EraLeader의 독립 원칙을 해치지 않는 로컬 adapter만 사용.

## 5. 개발 작업 ID 적용

| EraLeader 작업 | 재사용 가능한 구체 자산 | 기대 절약 효과 |
|---|---|---|
| **1_1** 주가 데이터 수집 | marcap 32개 Parquet와 미국 bars 캐시 | 과거 주가 전체 재다운로드 회피, 부족한 최신 부분만 보강 |
| **1_5** 증분 수집/캐시 | 기존 raw/cache·manifest·해시 설계 | 이미 존재하는 데이터 우선 조회 |
| **2_1** 정합성 검사 | marcap validation_summary/manifest | 스키마·중복검증 기준 재사용 (실제 추가 검사 필요) |
| **2_2·2_3** 종목/PIT | 기존 티커 목록/기업행동 메타 검토 | 원시가격 재활용, PIT 빈틈은 별도 보완 |
| **3_4** 모멘텀 | 기존 sector_mom 및 주봉 시세 | RS baseline의 재구현 부담 감소 |
| **5_1** 초기 백테스트 | grid_mom_rotation/strategies + 캐시 수익률 | 당장 baseline 스모크/개별 테스트 가능 |
| **5_2~5_5** 강건성 검증 | run_registry/결과 해시/CSV | 결과 형식·버전 기록 참고, PIT 엔진은 추가 보완 |

## 6. 다음 실행 순서

- R1: 기존 자산 파일 목록/스키마/해시를 재현 가능하게 보존(이 문서 및 \`scripts/verify_backtestengine_reuse.py\`).
- R2: EraLeader \`legacy_data_adapter\`를 작성해 **read-only**로 연도별 Parquet를 조회, Python이 1~2종목/1~2년 소규모 검증.
- R3: 한국 상장/상폐·기업행동 보강 및 원본/보정 가격 계약 정리.
- R4: 기존 섹터 모멘텀을 baseline으로 사용해 단계별 대장주 발굴 특징 모델과 같은 PIT 유니버스에서 비교.
- R5: 기존 엔진 사용 가능한 부분만 adapter 연결하고 구현되지 않은 워크포워드/리드타임/정밀도는 EraLeader 평가 계층에 별도 구축.
- R6: 데이터 다운로드/백테스트 이전에 로컬 캐시 존재 및 시간 범위 확인 → 부족 시에만 API 호출.

## 7. 사용자 의사결정 기록

- **확정 사용자 방향:** T5DATA의 기존 backtestengine 자료를 적극 재사용하여 다운로드·테스트 시간 절약.
- **실제 위치:** \`backtestengine\` 비어 있음 → \`CycleOS-Lab_BacktestEngine\`에 실제 자료 존재.
- **기존 프로젝트는 수정하지 않음.** EraLeader에만 검사 스크립트·점검 JSON·스모크 CSV/문서를 생성.
- **최종 엔진 선택과 PIT 적격 판정은 아직 미완료.** 이 조사는 활용 가능성 확인 및 첫 실행 검증이다.

## 8. 첫 read-only 가격 어댑터 실행 성공 (추가 검증)

- **코드:** \`scripts/read_cached_marcap.py\`. 환경변수 \`ERALEADER_LEGACY_ROOT\`로 참조 폴더 변경 가능.
- **실제 실행:** legacy \`.venv/bin/python\`으로 기존 \`marcap-2025.parquet\`의 \`005930\` 종목을 2025-01-02~2025-01-31 기간 조회.
- **결과:** **18개 거래일** 반환, 최초 2025-01-02·마지막 2025-01-31. 새 API 호출/다운로드/원본 복제 없음.
- **저장된 출력:** \`results/reuse_probe/marcap_sample_query.json\` (일부 샘플 + row 수/범위/신뢰성 상태).
- **제한:** 단순 날짜 필터로 가격을 얻는 최소 읽기 전용 어댑터다. 당시 공시 가용성·기업행동 완전성·PIT 적격성은 미검증. 전략 신호/투자성능 증명으로 혼동 금지.
