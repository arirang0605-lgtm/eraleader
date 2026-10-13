# ER-NC-07 — 남석관·유목민 독립 원형 규칙 연구 게이트

상태: **PARTIAL (연구용 계약 구현)**. 원문으로 확정된 투자 매수/매도/손절 실행 규칙은 아직 제공되지 않았으므로 실행 가능하다고 선언하지 않는다.

## 백업 선행과 원본 보존

- 2026-10-13 ER-NC-B00 암호화 백업과 복원 검증 PASS. 기본 main a244002.
- 원래 EraLeader 및 읽기 전용 백테스트 의존 자료 31,197파일, SQLite 온라인 스냅샷 273개, 파일별 SHA256·격리 복원·Git 변경사항·pytest EXIT0 검증.
- 별개 기존 feature worktree 546파일과 미추적 뉴스 소스도 추가로 AES 보호된 양 저장소 백업 및 격리 SHA 확인 PASS.
- 기존 native_first_capture.py 미커밋 6+/1- SHA256 = 6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6. 원래 main과 기존 feature worktree 수정0.
- 암호키는 Mac Keychain에만 저장되며 백업 매니페스트·키 경로는 공개 Git에 포함하지 않는다.

## 구현 기능

- author_strategy_rules.py: 남석관 N_ST 단기/N_MT 중기, 유목민 Y_ST 단기/Y_MT 중기 등 4개 독립 읽기 전용 인터페이스.
- AuthorRuleRegistry: JSON 계약 author_rule_registry_v1, 출처·발행시각·매수·매도·손절·시황·확인 상태·버전 필수, JSON 중복 필드·ID 충돌·symlink·과대 입력·다른 저자 차단.
- AuthorStrategyResearch.evaluate: as_of 기준 원문 최초 공개·확인·PIT/시장/뉴스 정보 이용 가능 시각을 검증. 미래 정보는 UNKNOWN, 원형 근거 미확인 또는 매매식 미구현은 NOT_READY.
- 모든 상태 executable=false, trade_permission=NO_ORDER, research_only=true. 저자 원형 수치를 임의 생성하거나 본문을 Python 코드로 실행하지 않는다.
- 기존 KRX/DART/SEC, WATCH, 기존 시장 점수와 보고서·실전 알림·매매 주문 수정 0.

## 테스트

- 신규 집중 25 PASS / EXIT0. 4개 독립 인터페이스, 허위 검증상태·미래 소급·뒤늦은 뉴스, 버전충돌, 김정수 제외, 코드를 가장한 규칙문 실행금지, JSON·파일 안전성, 입력 불변, NEWS_OFF/NEWS_ON 시 원형 판단 불변 시험.
- 이번 단계에서 기존 전체 회귀는 사용자 계획에 따라 확장 통합 수락 시 한 차례 실행한다. 이번 변경 관련 테스트 및 후속 영향범위 테스트를 우선한다.

## 남은 작업

1. 남석관 단기·중기, 유목민 단기·중기 공개 저서/강연의 판본·쪽수/링크·발언 시점과 정확한 매수·매도·손절·시황 정의 확보. 확보되지 않은 규칙은 NOT_READY 유지.
2. 각 저자 규칙을 별도 비거래 연구 실행기로 1차 자료대로 구현하고 전략별 PIT·오탐·봉인 홀드아웃 검증. 임의 뉴스·시장 게이트 수정판은 원형과 별도 실험.
3. 기존 ER-NC-06 작업트리의 미커밋 news_market_response.py는 타 작업물로 보존. 이번 별도 ER-NC-07 브랜치에서 임의 편집하거나 병합하지 않음.

공식 PIT 완전성·실제 미래 대장주 성과·저자 매매원형 실행 검증 N/A.
