# 4단계 개발 — 대장주·잠재 후보·교체 판정 엔진

> 입력: 3단계 시점별 산업/기업 정량 점수 및 근거, 2단계 PIT 품질 메타. 목표: 후보 '순위'를 기업의 성장 상태 변화와 연결해 시간순 이력으로 남긴다.

## 1. 상태 정의 (운영 시점만 사용)
| 상태 | 의미 | 핵심 데이터 | UI |
|---|---|---|---|
| WATCH | 추적·관찰 | 현재 산업분류/기본 재무/RS | 관찰 |
| POTENTIAL | 잠재 대장주 | 실적 가속 또는 산업 개선 + 초기 RS | 잠재 TOP 20 |
| CONFIRMED | 확정 대장주(모델상) | 실적·RS·주봉 추세 다중 확인 | 확정 TOP 10 |
| WEAKENING | 확정주의 지위 약화 | RS 하락 + 추정치/실적·추세 중 복수 훼손 | 위험 알림 |
| REPLACEMENT_CANDIDATE | 더 강한 새 경쟁 후보가 기존 주도주 위협 | 동종업종 상대점수/실적/RS 비교 | 교체 검토 |
| PAUSED | 가격정지·공시결측·데이터 신뢰 불충분 | validation flags | 신호 중지 |
| EXITED | 투자유니버스 제외/상폐 등 | 유효한 과거 상장/종목 상태 | 이력보존 |

**CONFIRMED는 미래 수익 보증이나 승률 100%가 아니라 규칙상 '현재 주도주' 판정.** 개별 종목·시장 국면별 조건이 달라질 수 있음.

## 2. 수집 자료 및 갱신 타이밍
- score_snapshot: market, security_id, as_of, score, component_scores, evidence, quality_status, score_version.
- 산업별 상대 순위와 산업 성장 상향/둔화 추이.
- 주봉 종가 확정 후 RS·주봉 10/20선·신고가 유무·업종 breadth.
- 신규 분기 실적·공시·당시 EPS 컨센서스가 있으면 관련기업 score 재계산.
- 이전 상태 이력(\`candidate_state\`), 판정 근거, 초회 후보 날짜.
- 시장별 휴장일·거래정지·상폐/합병 이벤트, 이전 모형 버전과 데이터 변경 이력.
- 본 단계에서 외부 API를 별도 중복 수집하지 않고 2~3단계 결과 재사용.

## 3. 예비 전이 규칙(미검증, 설정형)
- WATCH→POTENTIAL: total_score 65~79 **또는** 산업/실적 가속·RS 신호 등 연구용 조기 조건; 근거 2개 이상.
- POTENTIAL→CONFIRMED: total_score >=80 **그리고** 재무 또는 성장 근거 1개 이상 + RS/주봉 조건 1개 이상. 기간 경계의 불안정한 신호만으로 승격하지 않음.
- CONFIRMED→WEAKENING: 총점 하락+주봉 추세 훼손 또는 실적 감소 등 독립적 근거 복수; 미확정 주봉 일시 이탈은 경고만.
- WEAKENING→CONFIRMED: 반증 근거 회복 시 판정 복귀 가능.
- 기존 leader와 신흥 후보 비교: 동일 시점·같은 산업 내 상대 RS·실적 수정·점수 우위를 **2회 연속** 확인하는 전이 옵션(정확한 간격·히스테리시스는 백테스트로 튜닝).
- 어느 상태든 \`quality_status=FAIL\` 또는 공시/가격 데이터 불완전 → PAUSED(신호 전파 금지).
- EXITED 이력은 지우지 않으며 다른 티커로 자동 합병해 과거 성과를 왜곡하지 않음.
- 모든 전이는 최소 유지기간(min dwell), 점수 진입/이탈 임계값 차이(hysteresis), 주간 확정 시각으로 잡음 억제.

## 4. 단일 상태 머신과 보조 관계 구분
후보의 'POTENTIAL/CONFIRMED/WEAKENING/PAUSED'는 종목별 **단일 기본 상태**로 관리.
'REPLACEMENT_CANDIDATE'는 두 종목을 연결하는 **교체 관계 이벤트**로도 표현 가능(\`challenger_id -> incumbent_id\`); 한 종목이 동시에 잠재 후보이자 교체 도전자일 수 있다.
따라서 주상태(state)와 플래그/이벤트(replacement_signal)를 분리한 설계를 우선 검증한다.

## 5. 설계 모듈
\`\`\`text
src/eraleader/discovery/
  policies.py        # 임계치·근거 게이트·주봉 확정 정책 (버전관리)
  state_machine.py   # 결정적 상태 전이 / 히스테리시스
  leaderboards.py    # 산업별/시장별 TOP N, 신규/확정/약화
  replacement.py     # incumbent vs challenger 관계 감지
  event_ledger.py    # append-only 상태변화 이벤트/중복 키
  explanations.py    # 왜 승격/강등했는지, 반증 조건
tests/discovery/test_transitions.py
tests/discovery/test_replacement.py
tests/discovery/test_event_idempotency.py
\`\`\`

## 6. 데이터 계약 예시
\`\`\`json
{
  "event_id":"test-evt-0001", "event_type":"PROMOTED_CONFIRMED",
  "security_id":"TEST-001", "market":"US", "as_of":"2024-07-05T20:00:00Z",
  "prior_state":"POTENTIAL", "new_state":"CONFIRMED",
  "candidate_first_seen":"2024-01-19", "score":84.0,
  "reasons":["매출 성장 가속","주봉 RS 추세 확인"],
  "risk_factors":["영업현금흐름 약화"],
  "score_version":"v0-experimental", "input_hash":"example",
  "idempotency_key":"TEST-001:PROMOTED_CONFIRMED:2024-07-05:v0"
}
\`\`\`
예시 회사·점수는 실데이터가 아니다.

## 7. 구현 순서
- S4.1 상태표/전이 다이어그램과 입력 품질 게이트 테스트
- S4.2 기본 분류 WATCH/POTENTIAL/CONFIRMED/WEAKENING
- S4.3 PAUSED/EXITED·히스테리시스·정정공시 변경 반영
- S4.4 leader/challenger 산업 상대 비교 및 replacement event
- S4.5 append-only 이력과 중복 이벤트 전파 방지
- S4.6 잠재 TOP20/확정 TOP10/신규·교체 이벤트 JSON/Parquet 저장 및 5·6단계 연결

## 8. 테스트 및 완료 기준
- 동일 입력/상태에 대한 재실행 결과 항상 동일.
- 2회 연속 조건 없이 흔들리는 임계점에서 과다 승격·강등하지 않음.
- 미래 공시·미확정 주봉 유입 시 이벤트가 생성되지 않음.
- 상장폐지/거래정지/누락 시 안전하게 PAUSED 또는 EXITED 처리.
- 중복 알림 방지를 위한 event_id / idempotency_key의 유일성.
- 최초 발굴 시각, 상태 유지기간, 현재 상태·지난 상태 모두 조회 가능.
- 교체는 투자계좌 매수/매도 실행과 분리(연구용 신호).
- **Gate S4:** 상태 이력/근거/이벤트가 재생 가능한 배치 테스트 통과; 실제 발굴 정확도는 5단계에서 별도로 검증.

## 9. 목표 CLI(미구현)
\`\`\`bash
python -m eraleader.cli discovery transition --market US --as-of 2024-07-05
python -m eraleader.cli discovery leaderboard --market KR --as-of 2024-07-05 --format json
python -m pytest tests/discovery -q
\`\`\`
