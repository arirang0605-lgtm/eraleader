# 3단계 개발 — 산업·기업·주가 발굴 분석 엔진

> 목표: PIT 스냅샷만 입력받아 미래정보를 쓰지 않고 산업과 종목의 정량 점수·원인·품질 플래그를 생성.
> 점수와 임계값은 **검증 전 실험 가설**. 특정 산업을 영구 가산하지 않음.

## 1. 수집/입력 데이터 및 특성

| 분석 모듈 | 2단계에서 가져올 자료 | 계산할 지표 |
|---|---|---|
| 산업 구조 변화 | 섹터별 PIT 회원·매출·CAPEX·수주, 산업생산·투자 | 산업 매출 YoY, CAPEX 증가율, 산업 RS, breadth |
| 기업 성장·경쟁력 | 최근 이용 가능한 공시 재무·현금흐름·산업 소속 | 매출·이익 성장 가속, 영업이익률, FCF, ROIC/ROE |
| 실적 예상 변경(선택) | 과거 EPS 컨센서스 스냅샷 | revision_1m/3m, 추정치 상향 비중 |
| 주가/모멘텀 | OHLCV/가격 조정·상폐 이력 | 6·12개월 상대수익률, 10·20주선, 주봉 신고가 |
| 기관수급(가용 시) | 공식 투자자 매매/기관 보유 이력 | 순매수 비중, 기관 보유 증가 등 |
| 공시 이벤트(선택) | 계약·증설·정책·이벤트 timestamp | 수주/투자 이벤트, 리스크 이벤트, 근거 URL |

시장마다 다른 산업·회계 기준은 **market/industry 그룹 내 기준 분포**로 정규화; 각 업종의 대표 성장률 다름을 반영.

## 2. 알고리즘(초기 버전)

### 초기 100점 가중치(검증 필요)
\`\`\`text
산업 성장성 20
경쟁력/재무 품질 20
실적 모멘텀 25
가격 RS·추세 25
기관 수급 10
----------------
합계 100
\`\`\`
\`\`\`python
score = 0.20 * industry_pct_rank * 100 \
      + 0.20 * quality_pct_rank * 100 \
      + 0.25 * earnings_pct_rank * 100 \
      + 0.25 * momentum_pct_rank * 100 \
      + 0.10 * flow_pct_rank * 100
\`\`\`
이산화·rank 방식, 최소 관측치, 결측 가중 재정규화 여부는 스모크/장기 검증으로 결정. 충분한 데이터가 없는 그룹은 \`N/A\`; '0'으로 임의 대체 금지.

### 연구용 필터(모두 절대 필수 아님)
- 매출 YoY 20%+, 영업이익 YoY 30%+; 전년 적자 시 단순 성장률 대신 영업 레버리지·FCF 개선.
- 기업 EPS 전망 3개월 +5~10%(컨센서스 PIT가 실제 확보된 경우에만).
- 최근 6/12개월 수익률 시장 상위 15% 또는 업종 상위 3위.
- 20주선 위·10주/20주 기울기 상승, 주봉 RS 증가·상승시 거래량 확산.
- 월봉 5/10/20개월 이동평균 장기 Gate(연구 가설), 주봉은 확정 후 판정, 일봉은 경고.
- 규모/유동성/상장기간 필터는 config/version으로 보존하고 시장별 정책 분리.
- 시장 변화 감지 예시: AI 연산→반도체→데이터센터→전력설비. **선정 산업 자체를 고정하지 않고 데이터로 동적으로 탐색**.

### 산업 점수 설계
1. 과거 당시 산업분류 회원을 합산/가중.
2. 산업별 매출 증가·CAPEX 증가·주가 RS·EPS revision breadth(가용 시) 각각 계산.
3. 산업 TOP N과 value chain 이웃 산업을 함께 탐색.
4. 경제국면/정책/수급은 맥락 변수이며 단독 매수 신호가 아님.

### 조기 발굴 강조
실적 '수준'과 '가속도'를 분리해 lagging 대장주 점수 vs early candidate 점수를 각각 계산, 이후 같은 기준으로 개별 백테스트 비교. 대장주였던 기업으로 역학습할 경우 과거 승자만 고른 표본 편향을 통제.

## 3. 개발 모듈/파일(목표)

\`\`\`text
src/eraleader/features/
    industry.py         # 산업 규모·성장·강도·확산
    fundamentals.py     # 성장률/마진/현금흐름
    revisions.py        # 실제 과거 snapshot 있는 경우에만
    relative_strength.py# 업종/시장 대비 6·12개월 RS
    institution_flow.py # 가용 시 수급
    event_features.py   # 문서 근거 기반 이벤트
    normalize.py        # 시점 내 퍼센타일, 이상값, 결측
src/eraleader/discovery/
    scoring.py          # 100점 + 구성별 breakdown
    explain.py          # 증거/실패 근거 자동 생성
tests/features/ tests/discovery/
\`\`\`

## 4. 출력 스키마 예시
\`\`\`json
{
  "security_id": "TEST-001", "market": "KR",
  "as_of": "2024-06-28T16:00:00+09:00",
  "scores": {"industry": 17, "quality": 15, "earnings": 20, "momentum": 22, "flow": 6},
  "total_score": 80, "score_version": "v0-experimental",
  "industry_rank": 3, "market_rs_percentile": 0.89,
  "reasons": ["매출 증가율 가속", "업종 RS 상승", "주봉 추세 확인"],
  "missing": ["historic_eps_consensus"], "quality_status": "PARTIAL",
  "input_manifest_hash": "example-hash"
}
\`\`\`
**위 숫자와 종목은 설명용 가상 예시이며 실데이터 분석 결과가 아님.**

## 5. 실행 순서
- S3.1 단독 특징 추출/결측 처리 unit tests.
- S3.2 baseline: 6/12개월 단순 RS 순위 구현.
- S3.3 산업 전반 산업/기업 점수 구현.
- S3.4 실적 가속, 산업 점유 변동, 수급(가용 시) 추가.
- S3.5 TOPN 설명/반증/시점 출처 trace 생성.
- S3.6 **모듈별** PIT 백테스트: 산업 단독, 실적 단독, RS 단독, 결합 비교 → 정보가치 낮은 지표 보류.

## 6. 테스트·인수 조건
- PIT를 위반하는 데이터가 들어오면 점수 생성 중지.
- 해당 기간 상장종목만 사용하며 당일 횡단면 퍼센타일이 미래 통계를 보지 않음.
- 가중치 합 100, 그룹 커버리지·동점·이상값·상장초기 사례 처리.
- 기준 실험과 구성요소 제거 실험(ablation) 리포트.
- 산출물: \`feature_snapshots.parquet\`, \`industry_rankings.json\`, \`candidate_scores.parquet\`, \`score_explanations.json\`, \`module_validation.json\`.
- **Gate S3:** 상위 종목 랭킹+근거 재현, baseline 결과/지표 공개. 높은 과거 수익률만으로 합격 불가.

## 7. 명령 목표(아직 코드 아님)
\`\`\`bash
python -m eraleader.cli features build --market KR --as-of 2024-06-28
python -m eraleader.cli rank industry --market KR --as-of 2024-06-28
python -m eraleader.cli research ablation --as-of 2024-06-28
\`\`\`
4단계 상태 머신이 점수 결과와 실적/추세 확인조건을 구분해서 사용한다.
