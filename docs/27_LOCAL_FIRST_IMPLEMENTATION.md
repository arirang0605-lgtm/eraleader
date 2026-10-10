# EraLeader 로컬 우선 1~6단계 통합 첫 구현

> 개발 착수/실행: 2026-10-10 KST. **외부 API 연결·스크래핑·실제 메시지 전송 없이** Mac + T5DATA SSD의 기존 자료를 이용해 작동시킨 첫 통합 MVP.
> 사용자 확정: **1~6단계를 로컬에서 먼저 완성 → 외부 API는 그 후 필요할 때 연결**. 다만 가짜 재무·산업 자료로 '확정 대장주'를 만들어선 안 된다.

## 목적
최종 목표는 **미래 대장주를 조기에 발견하는 능력**. 현재 첫 버전은 로컬 가격을 활용해 데이터 입력 → 유효성 검증 → 가격 관찰 순위 → 상태/이벤트 저장 → 연구용 baseline → 웹·알림 모의·보고서까지 **실행 경로를 검증**하는 작업이다. 장기 PIT 기업자료 없는 단계이므로 미래 대장주 발굴 성능은 아직 검증되지 않았다.

## 실제 새 파일

- \`pyproject.toml\`, \`.gitignore\` — Python 패키지 설정 및 개인 데이터/결과 제외.
- \`src/eraleader/data.py\` — local Parquet read-only, KR marcap/US S&P500 주간, 무거래·거래정지 0 OHLC 보존/제외, 비거래 원인 아닌 오류는 표시·격리.
- \`src/eraleader/pit.py\` — SQLite timestamp/정정 공시 PIT 테스트 가능한 facts, 후보 스냅샷, 변경 이벤트 중복 방지 및 알림 Outbox.
- \`src/eraleader/discovery.py\` — 가격 기반 3·6개월 상대강도 관찰점수(25점 이내), WATCH. 실적·산업/수급이 없으면 전체 100점 및 POTENTIAL/CONFIRMED 산출 **금지**.
- \`src/eraleader/states.py\` — 신뢰할 수 있는 PIT 재무/가격/기업행동·업종 데이터가 완비된 경우에만 임시 규칙으로 POTENTIAL/CONFIRMED/WEAKENING 전이; **현재는 synthetic fixture unit test에서만 확인**.
- \`src/eraleader/backtest.py\` — t시점 신호를 t+1 구간에 적용하는 주간 모멘텀 연구용 baseline. 누적 가치·업종/시장 비교의 정확도·유동성·기업행동·수수료·PIT는 검증 전.
- \`src/eraleader/delivery.py\` — 한국/미국 정적 로컬 웹페이지, 일·주·월 Markdown 정기보고.
- \`src/eraleader/cli.py\`, \`src/eraleader/__main__.py\` — CLI \`run\`, \`baseline\`, \`report\`, \`alerts-preview\`, \`serve\`.
- \`tests/test_pit.py\`, \`tests/test_pipeline.py\`, \`tests/test_states.py\` — 데이터 오류·미래정보 차단·PIT 수정·중복·가격선별·상태·웹 출력을 단위 테스트.
- \`scripts/verify_local_mvp.py\` — 실제 JSON/웹/보고서/알림/기준시각 통합 점검.

## 실제 실행 명령 (Mac, 인터넷/API 불필요)

\`\`\`bash
cd /Volumes/T5DATA/eraleader
# 패키지 설치 없이 현재 사용 가능한 Python3.12 + pandas/pyarrow/pytest
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m eraleader run --market KR --as-of 2026-10-02 --top 20 --days 550
PYTHONPATH=src python3 -m eraleader run --market US --as-of 2026-02-23 --top 20 --days 550
PYTHONPATH=src python3 -m eraleader baseline --market KR --as-of 2026-10-02 --days 550 --top 3 --lookback 26 --rebalance 4
PYTHONPATH=src python3 -m eraleader alerts-preview
PYTHONPATH=src python3 -m eraleader report daily --market KR
PYTHONPATH=src python3 -m eraleader report weekly --market KR
PYTHONPATH=src python3 -m eraleader report monthly --market KR
PYTHONPATH=src python3 -m eraleader report weekly --market US
PYTHONPATH=src python3 -m eraleader serve --port 8765
# 브라우저: http://127.0.0.1:8765/
# 또는 Mac에서 /Volumes/T5DATA/eraleader/output/site/index.html 파일 직접 열기
PYTHONPATH=src python3 scripts/verify_local_mvp.py
python3 scripts/check_handoff.py
\`\`\`

## 2026-10-10 실측 테스트 증거

| 검증 | 결과 | 제한 |
|---|---|---|
| 자동 테스트 17개 | **17 PASS** | synthetic PIT fixture + 실제 SSD 샘플 포함 |
| 한국 전체 관찰 목록 | **20종목 JSON/로컬 HTML 생성 PASS** | 자료 기준 2026-10-02, 산업·실적 미연결 |
| 미국 전체 관찰 목록 | **20종목 JSON/로컬 HTML 생성 PASS** | 기준 2026-02-23, 2026-03 현재 구성 S&P500 편향 |
| 원본 데이터 이상 | 한국 분석 구간 1,062,518행 중 **51,214행의 비정상 OHLC 식별** | 그중 51,213행은 비거래/정지로 보이는 OHLC=0, 거래량=0 기록을 유지·관찰 순위 제외, **1행은 이상으로 격리** |
| 주간/월간/일간 로컬 보고서 | KR 3개 + US 주간 1개 생성 PASS | HTML/PDF/실전 전송 미구현 |
| 알림 상태 이력/재실행 | 초기 연구용 WATCH 이벤트 44건 저장, 두 번째 알림 preview 0건 PASS | **실제 외부 알림 발송 없음** |
| 로컬 HTTP 테스트 | \`index.html\`, \`kr.html\`, \`us.html\` 모두 HTTP 200 PASS | 루프백 로컬 전용·외부 공개 안 함 |
| 주간 가격 모멘텀 baseline | 52개 관측구간 계산 PASS | **PIT/상폐/분할/비용 미검증**. 결과 수익성을 실제 성과라고 해석 금지 |
| 인수인계 자동 점검 | PASS | 실전 모델 성능 검증 아님 |

관련 파일: \`output/kr_latest.json\`, \`output/us_latest.json\`, \`output/state.sqlite\`, \`output/baseline_research.json\`, \`output/site/*\`, \`output/reports/*\`, \`output/alerts_preview.json\`. **이 폴더는 Git ignore**. SSD에서 실행 결과 유지.

## 엄격한 단계별 현재 상태

| ID | 상태 | 실제 확인 |
|---|---|---|
| 1_1·1_5 | **로컬 대체 구현/실행 PASS** | KR/US 기존 시세 읽기, API 어댑터는 미연결 |
| 1_2~1_4 | **설계만/미구현** | DART·SEC/산업·거시/뉴스·스크래핑은 나중 |
| 2_1·2_3·2_4 | **일부 구현/단위검증** | 가격 검증·정정 공시 fixture PIT·SQLite 원장 |
| 2_2·2_5 | **부분/미완료** | 거래정지 신호 처리, 상폐/기업행동 PIT 완전 검증 필요 |
| 3_4·3_5 | **가격전용 연구 구현/테스트** | 3·6개월 RS, 설명 가능한 가격 관찰점수 |
| 3_1~3_3 | **자료·알고리즘 연결 미완료** | 산업·경쟁력·실적 PIT 데이터 아직 없음 |
| 4_1 | **WATCH 작동** | 가격 전용 기업 관찰 스냅샷 |
| 4_2~4_5 | **pure state logic 단위테스트만** | 신뢰된 재무·산업 PIT 자료 없어서 운영 후보 승격 금지 |
| 5_1 | **로컬 baseline 실행 PASS** | 다음 기간 수익 적용, PIT 인증/비용 검증 전 |
| 5_2~5_5 | **미완료** | 과거 라벨·상폐·전향적 검증·walkforward 필요 |
| 6_1·6_2 | **로컬 초안 작동** | SQLite, JSON, 반응형 정적 사이트/loopback 200 |
| 6_3 | **dry-run 작동** | 실제 텔레그램/메일 연결은 후순위 |
| 6_4 | **Markdown 정기 보고 작동** | PDF·이메일 자동 발송 후순위 |
| 6_5 | **부분 구현** | localhost만, 일정 실행·클라우드/백업 미완료 |

## 다음 개발 우선순위

**NEXT=2_2·2_3 보강 + 3_1~3_3 최소 오프라인 PIT fundamentals/industry 자료 연결 → 4_2~4_5 실제 자료로 통합 테스트**.

1. 가격데이터 누적 수익 계산 전에 **기업행동 및 역사적 종목군** 검증, 종목별 거래정지/상폐 보강.
2. 공개 공시자료가 API 미연결인 동안에도 오프라인 CSV/JSON 정형 데이터 import 계약, 데이터 provenance/PIT 공시일 강제.
3. 산업별 시점 종목구성/실적 revision 수집이 없으면 N/A·PAUSED로 처리. 예시 데이터로 시뮬레이션 검증과 실제 성능을 명확히 구분.
4. 미래대장주 평가 라벨 사전 등록, 조기발견 precision/recall 및 리드타임 테스트.
5. 실데이터 PIT가 채워지면 그때부터 확정 대장주 판정을 허용. 마지막 외부 API 연결은 동일 데이터 인터페이스를 통해 수행.
6. GitHub \`arirang0605-lgtm/eraleader\`는 **Public** 확인됨: 승인/Private 전환 전 원격 push 금지. 로컬 Git 커밋만 생성 가능.

**완료 선언 범위는 '로컬 통합 연구 파이프라인 1차 구동'까지다.** 30개 항목과 최종 발굴성능/운영 6단계 전체가 완료된 것은 아니다.
