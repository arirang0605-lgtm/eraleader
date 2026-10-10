# 모듈 인터페이스 계약 (개발용)

## 호출 경계
- ingest.run(source, since, until) -> DatasetManifest + QualityReport
- pit.snapshot(as_of, universe_policy) -> PITUniverseSnapshot
- features.compute(snapshot, feature_version) -> FeatureTable
- discovery.rank(feature_table, score_config) -> RankedCandidates
- discovery.transition(previous_state, current_scores, as_of) -> CandidateEvents
- backtest.evaluate(signal_stream, market_data, assumptions) -> EvaluationResult
- delivery.publish(candidate_snapshot, events, metrics) -> DB/API/report outputs

## 필수 공통 필드
`schema_version, run_id, as_of, created_at, universe_version, data_cutoff, data_version, model_version, source_list, quality_status`.

## 최소 후보 JSON 예시(가상 데이터, 실제 추천 아님)
```json
{
  "schema_version": "1.0",
  "run_id": "example-run",
  "as_of": "2026-10-09T16:00:00+09:00",
  "market": "KR",
  "security_id": "EXAMPLE-0001",
  "ticker": "EXAMPLE",
  "state": "POTENTIAL",
  "score": 74.0,
  "component_scores": {"industry": 15, "quality": 15, "earnings": 19, "momentum": 18, "flow": 7},
  "reasons": ["산업 상대강도 상승", "매출 성장 가속"],
  "risks": ["컨센서스 이력 부재"],
  "data_quality": {"status": "PARTIAL", "missing": ["estimate_history"]},
  "input_data_cutoff": "2026-10-09T16:00:00+09:00",
  "model_version": "rule-v0-experimental"
}
```
실제 JSON에서 예시 종목코드를 사용하지 않으며 데이터 검증 실패는 구조화된 오류로 전달.

## 백테스트 엔진 어댑터
EraLeader가 입력하는 것은 시간순 signal stream(최초 관측일, 종목 ID, score, state, portfolio_policy_version)이며 엔진 출력은 거래내역·평가곡선·비용·검증 메타데이터. 엔진이 다르면 adapter만 바꾼다.

## 외부 MarketOS 연동
MarketOS 코드를 EraLeader 내부에서 import하지 않는다. 버전 고정 REST 읽기 API 또는 export된 읽기 전용 JSON/CSV를 외부 측이 소비한다. 스키마 변경 시 version bump + backward compatibility 검증. MarketOS의 Regime/배분/주문 의사결정은 별개.

## 재현
입력 데이터 해시, 코드 commit, config hash, 실행 시간, 오류 요약을 모든 결과에 첨부. 같은 입력·모델·코드로 같은 랭킹을 반환해야 한다.
