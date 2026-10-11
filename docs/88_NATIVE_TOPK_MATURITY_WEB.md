# EraLeader 5_3 / 5_5 / 6_2 — native Top-K 미래 성과 평가 만기 및 로컬 웹

> 2026-10-11 KST. 목적: **미래 대장주를 발견한 뒤 사전 동결된 기록의 평가 기간과 아직 확인되지 않은 결과를 운영 중 지속 추적**한다. 소급 데이터·종목군·과거 종가로 예측력이 확인됐다고 착각하지 않는다. API 연결(D-017)·SSD 물리 탈착/재부팅(D-021)은 로컬 완료 뒤 마지막 단계.

## 실제 보완한 미완료 경로

기존 5_3 native Top-K는 첫 WATCH/숫자점수와 label 성공기준 원문 SHA, 시장/K/기간을 처음 저장한 시점에 동결했고 5_5 outcome receipts는 미래 자료가 이미 존재할 때 감사했다. 하지만 **미래 결과가 아직 없는 수개월 동안**, 현재 어떤 후보가 원래 horizon 중인지, 어떤 후보가 기간은 지났으나 원천 정답문서가 없는지를 사용자 화면에서 구별할 방법이 없었다. 오래된 로컬 기록과 미래 결과가 없는 상황에서 missing을 실패로 계산하는 오류를 막기 위해 outcome input을 아예 받지 않는 상태 모니터를 추가.

## 신규 실제 코드

- 신규 src/eraleader/ranked_maturity.py / tests/test_ranked_maturity.py; 기존 cli.py 명령 report-ranked-maturity, delivery.py 렌더링/쓰기, local_backup.py 파생 JSON 2개 이름만 allowlist 확장. 기존 native_topk_freeze.py, ranked_outcome_receipts.py, WATCH/score SQLite와 backtest/기업행동 코드는 수정하지 않는다.
- 단순 JSON summary를 신뢰하지 않고 원본 frozen Top-K SHA/순위/시장/모델/스냅샷·실제 seal 시각, 사전 등록한 leader label rule **원본 문서 bytes SHA**, 시장별 평가기간을 recheck한다. 모든 original WATCH score의 native 4요소 점수를 실제 원본 피처 byte SHA/원장/계산 공식으로 audit_computed_rank_provenance를 재사용해 **전수 재계산**. 원본 score/WATCH first-write IDs/hash를 cohort binding SHA와 다시 비교한다. 원본이 삭제·수정되면 report/dashboard 발행 전 예외. 입력 DB·동결 파일은 읽기 전용.
- Top-K **선정 분모를 절대 축소하지 않는다**. 선택된 K에 대해 원래 snapshot의 한국 Asia/Seoul·미국 America/New_York 현지 wall-clock + horizon calendar days를 계산하고 UTC 완료 시각을 노출. US DST 넘어갈 때도 현지 거래일 시계를 유지한다. 경계 1마이크로초 전=HORIZON_PENDING, 정확한 완료시각 이상=HORIZON_ELAPSED_OUTCOME_UNKNOWN.
- 평가 horizon 만기는 결과 확정이 아니다. 입력에 outcome labels/주가/별도 정답문서 없음. 기간 만료 후에도 known positive/negative/precision@K/recall@K **전부 null**, 실전 인증 false/official leader promotion0. 결과 원문·당시 독립 확인이 추후 확보되면 기존 strict audit-ranked-outcome-receipts 명령으로 별도 평가해야 한다. 이미 과거 날짜를 오늘 봉인한 cohort는 RETROSPECTIVE_SEAL_NOT_A_PREDICTION으로 표시.
- 화면 및 API 없는 로컬 연구: JSON ranked_maturity_kr|us_research.json, HTML site/ranked_maturity_kr|us.html 생성. 모바일 화면용 한글 표/상태 구분, 목표 만기일, 점수 첫 기록시각, 모델/원본 규칙 ID, 후보 K/평가기간 경과/라벨 미확인 수, 명확한 실제 적중률 N/A 및 **확정 대장주 0**. 입력 security_id/모델 값은 HTML escape, UI fake 인증/성공률 또는 수치 불일치 시 렌더 거부. 샘플 수가 100 이하라도 통계분모는 원래 K 고정.
- 원본 시세·PIT/vintage JSONL/first registration score 및 비밀키는 Git 및 연구 보고서 ZIP 제외, 파생 JSON/HTML 2개만 기존 SHA 검증 백업/복원. CLI에서는 과거 결과 labels를 보지 않으며 미래 as-of를 OS 시계보다 앞당기지 못함.

## 실제 사용 명령

아래 경로는 신규 실제 공식 자료가 현재 존재한다는 뜻이 아닌 명령 예시입니다. 반드시 과거 실수입이 아닌 **현재 최초 등록한 실제 WATCH와 native score 및 첫 동결**이 먼저 존재해야 합니다. 같은 시장/코호트는 고유 model_version으로 보존.

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader report-ranked-maturity \
  --freeze output/live/frozen_native_topk.json \
  --definition-file output/live/leader_rule.json \
  --score-ledger output/live/native_rank_scores.sqlite \
  --watch-ledger output/live/prospective.sqlite \
  --features-dir output/live/feature_evidence \
  --as-of '2026-10-11T19:30:00+09:00' \
  --sample-limit 100 \
  --out output/live/derived
~~~

## 검증과 남은 제약

- 테스트: KR/US/DST 초단위 만기 경계, 2개 Top-K 고정 분모와 샘플 제한, no labels 상태에서 성과 N/A, 소급 seal censor, 미래 clock/rehashed/오염된 frozen native binding/원본 feature/score/WATCH 변조 거부, XSS 처리, 가짜 인증/성과 및 카운트 조작 렌더 거부, CLI JSON+HTML HTTP 200, derived ZIP manifest SHA 복원. **첫 감사가 끝난 뒤 원본 feature 파일 또는 frozen snapshot 자체를 바꾸는 두 가지 경쟁조건을 RED 실패로 재현하고, 종료 직전 계산공식/피처 전체 재감사+frozen 원본 재조회로 GREEN**. 테스트·커밋 SHA는 PROJECT_STATE.md 최신 기록 확인.
- 실제 Mac synthetic e2e(실제 OS 첫 등록 시각): KR/US 각각 가상 WATCH1→고정 4요소 native rank1→기준규칙 원문 SHA 동결→report-ranked-maturity pending1/positive/negative N/A→site HTTP200→JSON+HTML backup/restore 동일 bytes. **공식 대장주 탐지·실제 180일 만기 성과를 증명한 것이 아니다**.
- 블로커: 현재 한국·미국 당시 전체 상장·상폐/기업행동/주식클래스 PIT 및 실전 KRX/DART/SEC 원시공시 공개·수집시각 독립 증명, 실운영 새 후보 누적, 사전 동결 후보의 수개월 뒤 독립 outcome/결측률·false positive·precision/lead days. local OS/SHA timestamp 자체는 publisher 독립 공증이 아님. 결과 누락을 0% 실전 성과로 기록하거나 대장주 확정 승격하지 않는다.
- NEXT 6_4/6_5 정기 자동 배치에 이 read-only maturity report를 별도 옵트인 연결하여 신규/만기/결측 변경 발생 시 일·주·월 운영 모니터링, 외부 API 후 실전 first ingest→성과 확인. D-017 API 및 D-021 물리 SSD 최종 이후만 연결·시험. REWRITE 금지.
