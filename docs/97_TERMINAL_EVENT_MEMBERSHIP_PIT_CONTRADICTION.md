# 97 — 2_2 / 2_5 상장폐지·합병 효력일과 살아 있는 종목군 모순 차단

2026-10-11 KST. 기존 정상 `provider_dual_source_audit.py` 및 `provider_candidate_gate.py`의 **서로 다른 두 로컬 출처 비교**를 이어서 보강한다. API, 원시 시세 수집, 기존 SQLite 원본 쓰기, 실전 후보 승격은 모두 0.

## 실제 발견한 결함

두 공급자의 `membership.valid_to`가 모두 NULL로 남아 있지만, **동일한 공급자들의 이미 공개되어 입력된 `actions`에 효력이 지난 `delist`/ `merger`가 명시된 경우**, 기존 2-source 비교기가 해당 회사를 active로 세어 `LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED`를 반환했다. 회사가 이미 상장폐지되었다는 일치하는 정보 자체가 서로 모순되어도 “두 자료가 서로 같으니 일치”로 취급하던 오류. 실제 합성 PIT 전처리에서 RED 테스트로 확인됨.

## 변경

- 기존 `_full_receipt_source`로 **기준시각까지 실제 로컬에 등록된 자료만** 불러오는 절차를 그대로 재사용한다. 새로운 조회·스크래핑·전달 기능 없음.
- 기존 `_latest`를 재사용하여 공급자별 action revision을 `(security_id,action_id)` 기준으로 추린 뒤, `action_type in {delist,merger}` 및 `effective_on <= decision_market_day`인 실제 효력 발생 건만 계산한다. 향후 발표된 예정 exit는 active 오인 차단 대상이 아니다.
- 각 공급자에 `SOURCE_A_KNOWN_TERMINAL_EXIT_STILL_ACTIVE`, `SOURCE_B_KNOWN_TERMINAL_EXIT_STILL_ACTIVE` blocker를 추가한다. 원래 멤버십 유효 종료일이 기준일 이후이거나 NULL이면 모순으로 차단한다. `matched_active_issuer_count`와 ticker 비교에서 알려진 과거 종료 종목을 제외한다. `valid_to`가 의사결정일까지 종료됐으면 같은 오류를 중복 신고하지 않는다.
- 두 공급자가 **같은 잘못된 기록**을 반환해도 결과가 성공 상태가 아니며, 기존 `provider_candidate_gate`는 해당 blockers를 `PAIR_...`로 이어받아 실제 후보 `research_watch_allowed=False`. 대상 코호트 안에 이미 종료된 종목이 없더라도, **전체 출처 범위 내 종료 오류**이면 차단한다.
- 이전 필터 `provider_pit_adapter`가 **동시 ticker 충돌 자체는 이미 intake에서 거부**하는 것을 확인하고 중복 개발/중복 테스트 3건은 추가하지 않았다. 기존 동시 티커 충돌 필터 정상 로직은 변경 0.

## 검증

- 신규 TDD: 두 공급자가 이미 효력 발생한 delist 종목을 여전히 open membership으로 주장해도 기존 status가 SUCCESS이던 **RED FAIL 재현 후 GREEN**. 단일 A만 유실, 합병, 미래 효력일, 기준일에 정확히 종료된 멤버십, 후보 검증 게이트까지 회귀 추가.
- 집중 실행: `PYTHONPATH=src python3 -m pytest tests/test_provider_dual_source_audit.py tests/test_provider_candidate_gate.py -q --tb=short`.
- 전체: `PYTHONPATH=src python3 -m pytest tests -q --tb=short`; `python3 scripts/check_handoff.py`; `python3 -m py_compile src/eraleader/provider_dual_source_audit.py`; `git diff --check`.
- 원본 발행자 PIT/법적 share-class/상폐 실제 지급액/독립 게시시각/시장 전체 당시 coverage는 **인증되지 않음**. 모든 출처는 synthetic/공급자 자칭 데이터를 대상으로 한 **일관성 검사**이며 실전 leader0, 실제 발굴 적중률 N/A, API0. D-017 API 연결과 D-021 실제 SSD 물리 재연결/재부팅은 마지막 단계 유지.

## 다음 실제 작업

API 연결 이전에 가능한 수정은 미래정보 유출·상폐 정산금 미확인·특정 주식클래스 식별 충돌을 fail-closed로 보강하는 범위. 실제 KRX/DART/SEC 등 독립 원본 서명/시각 및 수개월 뒤 미래 Top-K 결과를 확보하기 전 실전 대장주 발견 성과를 발표하지 않는다.

## 2026-10-11 실제 Mac 검증 결과

- 최초 RED: 이미 유효일이 지난 `delist` 이벤트가 공급자 A/B 모두에 있음에도 `membership.valid_to=null`로 현재 보이던 종목을 `STATUS_CONSISTENT`로 통과시키는 실패를 테스트로 직접 재현.
- 수정 후 신규 **6개 회귀**(두 공급자 동일 결함, 한 공급자만 오류, merger, 미래 효력일 무오탐, 이미 종료된 membership 무오탐, 후보 WATCH gate 전체 차단). 기존 동시 ticker 충돌은 importer가 이미 막고 있어 불필요한 재구현 없이 제거.
- `PYTHONPATH=src python3 -m pytest tests/test_provider_dual_source_audit.py tests/test_provider_candidate_gate.py -q --tb=short` **66/66 PASS**. 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1477/1477 PASS(exit0)** (기존1471+6), collect-only 1477, handoff 30 ID/40필수 PASS, Python compile/diffcheck PASS.
- Mac synthetic KR 공급자 A/B 원시 fixture 기반 **실제 CLI `audit-provider-source-pair` E2E**: 결함 자료 `BLOCKED_CONFLICTING_DECLARED_PIT_SOURCES` / 두 각 출처 blocker 1, 종목 정상 자료 `LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED` / 동일 실존 아님, 활성 종목 2. 두 보고서 각각 derived-only ZIP SHA 검증·새 경로 복원 통과; 입력 provider SQLite SHA 실행 전후 동일, API0/공식 리더0, real PIT·선행 발굴 성능 인증 아님.
- 소스/테스트/설명 문서만 GitHub Public 코드 심사 및 push, 원시 데이터·로컬 시험 산출물은 `output/` ignored로 보존.
