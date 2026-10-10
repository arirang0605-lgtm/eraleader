# EraLeader 2~6단계 상세 개발 및 구조도 목차

> 2026-10-10 작성. 기존 1단계 데이터 수집에 연결되는 **개발 실행 명세**.
> 아래 파일은 코딩 설계·구조도 산출물이며, 이 SSD 폴더에 단계별 실제 Python 기능이 구현되었다는 뜻이 아니다.

| 단계 | 개발할 핵심 | 필수 입력 | 구체적 MD | 한 장 그림 |
|---|---|---|---|---|
| **2 PIT 검증·저장** | 원본·정제·시점별 PIT DB, 정정/상폐/분할 재현 | 1단계 일별 주가·공시·기업행동·거시 빈티지 | [14_STAGE2_PIT_DATA_ENGINE.md](14_STAGE2_PIT_DATA_ENGINE.md) | [2단계 PNG](../EraLeader_2단계_PIT검증저장_구조도.png) · [SVG](../EraLeader_2단계_PIT검증저장_구조도.svg) |
| **3 발굴 분석 엔진** | 산업·실적·RS·수급 지표, 초기 100점 점수, 점수 근거 | 2단계 PIT 스냅샷 | [15_STAGE3_ANALYSIS_ENGINE.md](15_STAGE3_ANALYSIS_ENGINE.md) | [3단계 PNG](../EraLeader_3단계_분석엔진_구조도.png) · [SVG](../EraLeader_3단계_분석엔진_구조도.svg) |
| **4 대장주 상태 판정** | 잠재·확정·약화, 교체 후보, 이벤트 원장 | 3단계 점수 + 과거 후보 이력 | [16_STAGE4_LEADER_STATE_MACHINE.md](16_STAGE4_LEADER_STATE_MACHINE.md) | [4단계 PNG](../EraLeader_4단계_대장주상태판정_구조도.png) · [SVG](../EraLeader_4단계_대장주상태판정_구조도.svg) |
| **5 백테스트** | 조기 발견 정확도·리드타임, 투자 성과, 워크포워드·홀드아웃 | PIT 가격/종목군·후보 이력·벤치마크 | [17_STAGE5_BACKTEST_RESEARCH.md](17_STAGE5_BACKTEST_RESEARCH.md) | [5단계 PNG](../EraLeader_5단계_단계별백테스트_구조도.png) · [SVG](../EraLeader_5단계_단계별백테스트_구조도.svg) |
| **6 결과 제공** | PC/휴대폰 웹, 중복 없는 알림, 일·주·월 보고·PDF | 최신 랭킹/이벤트/성과/품질 DB | [18_STAGE6_DASHBOARD_ALERT_REPORT.md](18_STAGE6_DASHBOARD_ALERT_REPORT.md) | [6단계 PNG](../EraLeader_6단계_대시보드알림보고_구조도.png) · [SVG](../EraLeader_6단계_대시보드알림보고_구조도.svg) |

**통합 구조도(1~6단계, 번호 포함):** [PNG](../EraLeader_전체설계도_1-6단계_세부번호.png) · [SVG](../EraLeader_전체설계도_1-6단계_세부번호.svg) · [번호표](21_MASTER_ARCHITECTURE_NUMBERING.md)
**원본 도면 생성 스크립트:** [render_stages_2_to_6.py](../render_stages_2_to_6.py). 실행하면 개별 상세 SVG 5개 재생성; PNG는 Chrome headless 변환.
**1단계 기존 문서:** [13_DATA_COLLECTION_IMPLEMENTATION.md](13_DATA_COLLECTION_IMPLEMENTATION.md) 및 [구조도](../EraLeader_데이터수집_전체구조도.png).

## 단계별 순서 및 검증 게이트

1. 먼저 **PIT 최소 엔진**(2단계)을 만든다. 장기 투자를 시뮬레이션하기 전에 당시 상장종목과 공시 이용가능 시각을 검증한다.
2. 동시에 **최소 백테스트 baseline 기반**(5단계의 일부)을 만든다. 사용자 확정 원칙대로 **백테스트를 마지막에 몰아서 하지 않는다**.
3. 산업/기업/RS 지표(3단계)는 지표별 테스트와 PIT baseline 비교를 반복한다.
4. 상태 엔진(4단계)은 독립 규칙으로 구현하고, 후보 최초 등장/확정/약화/교체의 이력을 보존한다. 임계치 65/80과 20/20/25/25/10은 **미검증 가설**이다.
5. 통합 백테스트(5단계)로 조기 발견 precision/recall/lead time과 투자 수익/MDD를 **분리 평가**한다.
6. 웹/알림/보고(6단계)를 한 결과 DB에 연결하고 끝단 테스트까지 통과시킨다. 가장 단순한 로컬 웹 UI는 3~4단계에 병행 제작해 조기 확인할 수 있다.
7. 미국 확장/유료 컨센서스/클라우드는 데이터와 운영 여건이 확보된 후 검증된 이점이 있을 때 추가한다.

### 공통 개발·AI 사용량 원칙

- AI는 설계·코드 변경·예외 해결. 수천 종목 처리/백테스트는 Python 배치.
- AGENTS.md → PROJECT_STATE.md → 작업별 MD 1개만 우선 확인하여 문맥 재분석 비용 절약.
- 코딩 완료는 실행 테스트·결과파일·Git 체크포인트가 남았을 때만 기록.
- MarketOS와 독립. 필요한 경우에만 버전 관리된 JSON/읽기 전용 API로 연결.
- 실패/미구현 기능을 완료로 과장하지 않는다.

### 실행 담당자가 먼저 수행할 일

1. 사용자 SSD에서 18+개 명세와 6개 구조도가 실제 존재하는지 확인.
2. 실제 코드/깃 저장소 유무를 확인하고, 별도 v0.1 ZIP이 있으면 원본 보존 후 테스트.
3. 2단계 단일 표본 PIT 테스트를 최소 단위로 구현하고 baseline 백테스트를 동시에 준비.
4. 실행 결과를 PROJECT_STATE.md에 근거와 함께 갱신.
