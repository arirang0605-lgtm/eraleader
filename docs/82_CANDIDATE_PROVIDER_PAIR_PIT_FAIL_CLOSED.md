# EraLeader 2_5 / 4_1–4_3 — 두 공급자 PIT 원장과 실제 WATCH 입력 연결(연구 보류 게이트)

> 2026-10-11. 기존 `offline-integrated`의 안전한 연구용 WATCH 루트를 보존하면서, **사용자가 두 공급자 PIT 원장을 명시적으로 지정한 경우에만**, 해당 날짜의 **실제 후보 입력**과 기업·공시·산업·기업행동을 비교한 뒤 신규 WATCH/상태·웹 기록을 허용합니다. 독립 법적 기업 ID, 과거 공시 사용가능성, 역사 유니버스의 전체 커버리지 및 실제 미래 대장주 발굴력은 **미인증**. 외부 API는 D-017에 따라 후순위입니다.

## 이번 실제 개발 목적

기존 `audit-provider-source-pair`는 별도 `a.sqlite`/ `b.sqlite`의 claim 일치·분쟁을 읽기 전용으로 출력했지만, `offline-integrated`는 **해당 결과를 사용하지 않고** 새로운 `ProspectiveRegistry` 연구용 WATCH 관찰과 `StateHistory`를 기록했습니다. 실제 통합 run의 오프라인 재무·산업 원장이 두 출처와 달라져도 이전에는 보류되지 않았습니다.

## 작동 방식

- `src/eraleader/provider_candidate_gate.py`는 **직접 두 원장의 원본 및 first-ingest receipt**를 기존 `audit_provider_source_pair`로 재검증하고, 한 시장/한 판단시각에서 같다고 주장된 데이터가 실제 `OfflineLedger.snapshot(as_of)`에 쓰인 내용과도 일치하는지 따로 검사합니다. 사후 등록/후행 수집 또는 서로 다른 두 원본의 contradiction/missing source는 **연구용 원장 신규 기록 전에** `BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH`.
- 후보별 영구`security_id` (ticker로 역산 금지) + `ticker,industry_id,valid_from,valid_to`를 A·B 원장의 같은 이름의 활성 membership과 비교. 로컬 후보 원장에서만 나타난 기업 또는 한쪽 source에만 있는 기업은 후보가 아니라 missing data 문제로 보류합니다.
- **실제 연구 입력 세 도메인 추가**: `offline["fundamentals"]`은 `security_id/metric/period_end`, `offline["industry"]`는 `industry_id/metric/period_end`에 대해, 당시까지 알 수 있는 최신 revision의 `unit/value`가 두 출처와 같은지 확인. 틀린 값·단위 또는 누락 기간은 `CANDIDATE_FUNDAMENTAL_...`/`CANDIDATE_INDUSTRY_...` blocker. 기업행동은 `security_id/action_type/effective_on`의 동일 사건으로 분할비율·현금배당 금액을 교차검사하며 **상폐/합병 기업도 오늘 후보 리스트에 없다고 제외하지 않습니다**. 미매칭 또는 불일치는 `CANDIDATE_ACTION_SOURCE_MISMATCH`; 동일 경제 이벤트가 서로 다른 action ID로 중복 제출되면 명시적 blocker.
- 쌍이 서로 일치해도 **자체선언 복수 공급자 이름은 실제 독립 발행자/증권 클래스의 법적 증거가 아닙니다**. 상태는 `LOCAL_CANDIDATE_PIT_PAIR_MATCHED_WATCH_RESEARCH_ONLY`, `research_watch_allowed=true`일 뿐이고 `official_candidate_promotion_allowed=false`, `historic_membership_pit_certified=false`, `leader_accuracy_certified=false`, `official_leader_promotions=0` 고정입니다.
- 오염/부재라면 해당 run은 `provider_candidate_gate_research.json` 한 개의 **파생 실패 증빙**을 남기고 조기 종료. 그 run에 대한 신규 `runs/joined*.json`, `state_history.sqlite`, `prospective.sqlite`, `site/*.html`을 생성하지 않습니다. 원본 PIT SQLite/상장·기업행동·가격 파일은 read-only. 기존 폴더에 이미 있던 이전 산출물을 임의 삭제·변경하지 않습니다.
- 정상 연구용 WATCH도 동결된 `provider_pair_gate` provenance와 그 source-pair digest를 **고유 run_id에 포함**하여, 기존 source 없이 생성한 연구 run과 동일 날짜/숫자라는 이유로 섞이지 않도록 구분합니다. 웹·상태 루트는 기존 WATCH-only/공식 리더 0 로직을 그대로 재사용.
- 사용자 지정 두 출처 확인을 **아예 요청하지 않으면** 기존 `offline-integrated` 동작/대장주 연구용 보류 상태 그대로 호환 유지. 단일 공급자만 제출하는 어설픈 옵션은 거절하며 미인증 상태를 거짓으로 통과시키지 않습니다.

## 실제 CLI

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR \
  --as-of '2026-10-11T14:00:00+09:00' \
  --out output/secure_candidate_research \
  --provider-ledger-a output/provider_a/offline.sqlite \
  --provider-bundle-a ACTUAL_BUNDLE_SHA256_A \
  --provider-ledger-b output/provider_b/offline.sqlite \
  --provider-bundle-b ACTUAL_BUNDLE_SHA256_B
~~~

전제: `--out` 경로에는 기존 로컬 일반 `OfflineLedger`의 `offline.sqlite`가 있어야 합니다. 입력 A/B도 각각 `import-provider-pit`로 수입해 **최초 등록 영수증이 남아 있는 정상 로컬 파일**이어야 합니다. SHA 인자 64자리는 예시 문자열 대신 각 실제 수입의 digest를 넣습니다. 위 경로는 **명령 예시**, 공식 원천 자료 확보 또는 현재 시장 분석 결과를 뜻하지 않습니다.

신규 파생 안전 백업 허용목록: `provider_candidate_gate_research.json` **단 한 파일**. 원본 `offline.sqlite`, provider `*.jsonl`, 문서·공시 원문, 개인키/유료시세는 GitHub/파생 ZIP 제외.

## 검증 범위

- `tests/test_provider_candidate_gate.py`: 새 단독 연구 후보원장 2개를 synthetic `import_provider_bundle`로 등록 후, 같은 날짜/같은 기업 ID·업종·티커·분할/배당·재무·산업 수치와 최초 등록시각 전/후 감사. 서로 일치하면 연구용 WATCH만 저장, 공식 대장주0/PIT false; **다른 회사의 같은 ticker, 다른 industry, 빠진 기업, 분할비율·재무/산업 수치 변경(원장 내부 SHA만 재계산된 공격 포함), 없어진 분기, 상장폐지 기업행동 누락** 모두 신규 run/DB/웹 생성 전에 차단.
- `tests/test_provider_dual_source_audit.py` 기존 두 provider receipt 감사/원본 integrity, `tests/test_research.py`/`test_prospective.py` 기존 WATCH 등록 불변, `tests/test_state_history.py` 기존 검증 선행/상태 기록 보존. 전체 pytest/handoff/실제 Mac CLI/파생 ZIP SHA/복원 실행 결과는 `PROJECT_STATE.md` 최신 체크포인트 우선입니다.

## 실전 미완료/다음 기능

이번 기능은 실제 데이터가 아닌 합성 source 기반 fail-closed 연결을 구현했습니다. **같은 로컬 PC에서 위조한 두 "다른 공급자" 선언 및 수집시각은 원천 진위의 독립 증명이 되지 않습니다.** 실제 KR/US 공식 상장·상폐·기업행동·현금지급·산업공시의 발행시각/법적 issuer/share class/전체 종목군 빈티지 및 미래 사전 봉인 후보 5_5 성숙 결과/실제 오탐률·선행기간 검증은 여전히 필요합니다. 외부 API 연결(D-017) 및 물리 SSD 탈착/재부팅(D-021)은 기존 순서에 따라 마지막. 테스트 없이 전체 30개 완료 또는 실제 대장주 탐지력 인증 금지.
