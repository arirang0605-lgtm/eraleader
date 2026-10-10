# 5단계 개발 — 대장주 발굴 백테스트·성과 검증

> 백테스트 **기반은 2단계 PIT 이후 곧바로** 만들고, 3·4단계에서 개별 검증하며, 이 단계에서 통합 검증한다. 5단계에 처음 만드는 엔진이 아니다.

## 1. 목적과 평가 분리
A. **발굴 품질**: '미래 대장주'를 얼마나 일찍, 얼마나 적은 오탐으로 발견하는가?
B. **거래 가능한 전략 성과**: 선정 후 정해진 포트폴리오/리밸런싱을 구성할 경우 비용을 제외하고 시장보다 성과가 높은가?
두 지표가 다를 수 있으므로 한 점수로 합치지 않는다.

## 2. 입력 자료와 수집 요건
| 자료 | 어디서 가져오나 | 필수 여부 |
|---|---|---|
| 일별 adjusted/unadjusted 가격, 배당/스플릿/상폐 이력 | 2단계 PIT 저장 | 필수 |
| 각 시점 유니버스/섹터 편입, 실제 거래가능 상태 | 2단계 PIT 종목 마스터 | 필수 |
| 과거 월·주별 score/rank + 상태 이벤트 스트림 | 3·4단계 이력 | 필수 |
| S&P 500, NASDAQ-100/KOSPI/KOSDAQ 등 비교지수 | PIT 가격/지수 공급 | 필수 |
| 공시/추정치의 발표 시각·거시 빈티지 | 2단계 PIT | 사용한 피처 범위 내 필수 |
| 수수료·슬리피지·호가/거래량 제약 | 시장별 명시적 시뮬레이션 가정 | 필수 |
| 과거 10~15년 장기 완전 데이터 | 라이선스/품질 검토 | **목표**, 실제 제공범위에 따라 제한 |

과거 상장폐지 기업 누락이면 장기 실적 수익률을 **편향 없는 백테스트로 발표 금지**.

## 3. 미래 대장주 평가용 라벨(사전 고정)
\`future_leader_label\`은 기준일 이후 1/3/5년 (또는 조건 정의 기간) 시장/업종 대비 수익률, 규모, 유동성, 드로다운 등을 이용한 **평가용 정답**.
초기 가설: '향후 3년 업종 대비 +100%p 이상'을 하나의 실험 정의로 고려하되, 업종·시대가 달라 동일 조건의 의미가 달라질 수 있으므로 여러 라벨 정의를 사전 등록하여 결과 비교. 이 라벨은 **발굴 엔진의 입력 절대 금지**.

## 4. 실험 설계
1. 훈련기간과 시계열 검증기간/미사용 최종기간(holdout) 분할.
2. \`baseline1: 시장/업종 동일가중\`; \`baseline2: 과거 6~12개월 RS TOP K\` 등 통일.
3. 모델별 단독 테스트: 산업 단독/실적 단독/RS 단독/수급 단독/조합.
4. 조기 후보 vs 확정 후보 **별도 성능 보고**.
5. 주/월 리밸런싱(사전 지정), 거래 제약, 다음 체결가능 시점 평가, 비용 차감.
6. Walk-forward: 훈련구간에만 모델 보정 → 앞으로 굴려 out-of-sample 평가. 라벨 기간 중첩에 따른 purge/embargo 검토.
7. 최종 미사용 홀드아웃은 모델 고정한 뒤 평가; 실패 후 재튜닝에 재사용 금지.
8. 상승장/횡보/하락장, 한국/미국, 산업집중도, 시총/유동성별 강건성.
9. 전략 변경 시 새 실험 ID와 설정 기록, 실패 실험을 제외하지 않음.

## 5. 지표
**발굴 지표**
- \`Precision@10/@20\`: TOP K 중 사전 정의된 미래 성공라벨 달성 비율.
- \`Recall@K\`: 해당 시점 유니버스에서 성공라벨 종목을 TOP K가 찾은 비율.
- \`False Discovery Rate\`: 1-Precision@K.
- \`Lead time\`: 최초 후보 선정과 나중에 정의된 주요 상승/시장선도 이벤트 사이 기간 (미리 정의된 이벤트 정의 사용).
- 선정 후 +3,+6,+12,+36,+60개월 업종/시장 대비 수익 분포(가능한 관찰기간만).
**포트폴리오·위험 지표**
- CAGR, total return, excess return, MDD, Sharpe(무위험/계산방식 명시), turnover, 비용 후 수익률, 종목별 최대손실/생존률.
- 리밸런싱 규모, 거래대금 대비 주문 비율, 상폐 후 처리 가정.
- 표본 수·신뢰구간·상관/동시 노출과 데이터 커버리지.

## 6. 엔진 개발/재사용 정책
기존 로컬 범용 엔진 후보:
\`\`\`text
/Volumes/T5DATA/CycleOS-Lab_BacktestEngine
/Volumes/T5DATA/backtestengine
\`\`\`
**읽기 전용**으로 API, PIT, 기업행동, 평가 결과 계약을 점검한 뒤 재사용 여부 결정. EraLeader 전용 별도 전체 백테스트 엔진을 중복 개발하지 말고, \`BacktestAdapter\`로 신호 스트림과 성능 결과를 표준화. 기존 엔진이 동작하지 않으면 최소 리서치 평가기를 독립적으로 만들어 기초 성능부터 확보.

## 7. 구현 파일(목표)
\`\`\`text
src/eraleader/backtest/
  protocol.py             # Adapter 공통 계약
  adapter_generic.py      # 범용 엔진 연결
  universe_replay.py      # 과거 유니버스 재생
  label_generator.py      # 미래 성공 라벨(평가 전용)
  experiment_runner.py    # 실험별 신호 / 비용 / 정책
  portfolio_sim.py        # 실제 매매 시점·비용(선택 전략)
  metrics.py              # 발굴 정확도·초과성과·위험
  walkforward.py          # 시계열 검증 및 holdout
  registry.py             # 데이터 해시·설정·코드 버전
tests/backtest/
\`\`\`

## 8. 실행·산출물
\`\`\`bash
python -m eraleader.cli backtest baseline --market KR --start 2016-01-01 --end 2025-12-31
python -m eraleader.cli backtest leader --config config/backtest_leader_v1.yaml
python -m eraleader.cli backtest walkforward --config config/validation_v1.yaml
python -m pytest tests/backtest tests/pit -q
\`\`\`
위 명령어들은 **개발 목표**. 출력:
- \`experiment_manifest.json\`: 코드 SHA/설정/종목군/기간/가정/데이터 해시.
- \`precision_recall_by_vintage.csv\`, \`leadtime_distribution.csv\`
- \`benchmark_comparison.csv\`, \`equity_curve.parquet\`, \`risk_metrics.json\`
- \`failed_pit_checks.json\`, \`validation_summary.json\`, charts/reports.

## 9. 반드시 통과할 테스트
- 가격 t종가 신호는 t종가 체결에 사용되지 않음.
- 2018년에 미래 공시 추가해도 2017년 랭킹과 실험 결과 동일.
- 상폐·분할·배당·휴장·이동평균 준비기간 처리.
- 선정 이후의 미래 성공라벨이 특징 컬럼에 없어야 함.
- 상위종목만 사후 골라 평가하지 않고 **선정된 전체 이력** 평가.
- 결과 재실행 해시 동일, 거래비용 상승 시 비용 차감된 수익 왜곡 없음.
- **Gate S5:** 각 실험 기간·시점별 종목수·비용·비교지수·검증구간 공개. 신뢰성 충족과 전략 수익성 판정은 별도.

## 10. 중요한 판단
통합 백테스트 성과가 좋지 않으면 지표를 무작정 늘리기보다 PIT·라벨·산업집중·후보 승격시차·위험자산장세를 먼저 원인 분석한다. 모델 고도화는 새 독립 검증으로 증명.

## 기존 SSD 백테스트 자산 활용 관련 추가 근거 (2026-10-10)

[23_BACKTESTENGINE_LOCAL_REUSE.md](23_BACKTESTENGINE_LOCAL_REUSE.md) 참조. \`CycleOS-Lab_BacktestEngine\`의 저장 수익률과 모멘텀 전략을 **baseline/스모크 검증에 우선 사용**. 미국 최근 구성 종목군 주간 데이터는 과거 시점별 종목 구성이 보장되지 않아 미래 대장주 검증용 정식 PIT 유니버스로 사용 금지. 국내 \`marcap\` 과거 가격을 재사용해 API 다운로드량을 줄이되 상폐 이력·기업행동·재무 공시 시점 검증 전엔 공식 성능 발표 금지.
