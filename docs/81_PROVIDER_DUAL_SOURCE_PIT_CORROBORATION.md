# EraLeader 2_2 / 2_5 — 두 개의 선언된 PIT 원장 공급자 주장 교차검증

> 2026-10-11 KST. **공식 KRX/DART/SEC 또는 민간 원천의 독립성·서명·이용가능시각을 인증하는 기능이 아닙니다.** API 연결 전에 따로 반입된 두 공급자 주장 자료의 기업 ID/업종/기업행동/재무 의미상 충돌을 찾고, 일치하지 않은 항목을 임의로 채워 대장주 선정으로 넘기지 않는 연구용 검사입니다. 사용자 지침상 외부 API 연동은 로컬 기능 구축 이후(D-017), SSD 물리 탈착·재부팅은 최종(D-021)까지 연기합니다.

## 목적/기존 모듈과 연결

- 직전 `provider_export_normalizer.py`는 KR/KRX-DART 계열 또는 US/SEC-exchange 계열 **선언된 staged export**를 기존 `provider_pit_adapter.py` JSONL 번들로 변환합니다. `import-provider-pit`는 이를 `OfflineLedger`에 처음 실제 PC로 접수한 시각과 원문 정규화 개별 SHA256/전체 digest를 동시에 저장합니다.
- 신규 `src/eraleader/provider_dual_source_audit.py`의 `audit_provider_source_pair`는 같은 시장에 속하는 **두 개의 서로 다른 기존 SQLite 원장+번들 digest**를 각각 read-only로 열어 원본 receipt/원장 연계 검증을 기존 `audit_registered_provider_asof`에 위임합니다.
- **같은 sqlite 경로 / 동일 source_id 주장 / 동일 publisher_id_claimed**는 독립된 두 원천이라고 취급하지 않고 입력 자체 거부. 서로 다른 publisher_id를 썼더라도 같은 사람이 만든 파일일 수 있으므로 결과 `publisher_independently_authenticated=false`, `permanent_issuer_identity_independently_attested=false`, `historic_pit_certified=false` 유지합니다.
- 두 번들의 `retrieved_at_claimed`와 **실제 최초 로컬 등록시각**이 요청 `decision_at`보다 늦으면 `CENSORED_NOT_CONTEMPORANEOUSLY_REGISTERED_SOURCES`: 어떤 기업·동종업종/이벤트 일치도 과거에 확보된 근거인 양 출력하지 않음.

## 비교 규칙

1. **영구 회사·증권 ID 주장**: ticker로 join하지 않으며 정확히 **같은 자체선언 `security_id`**의 과거 시점 membership만 비교. 최신 이용 가능 membership 빈티지의 `ticker / industry_id / valid_from / valid_to` 중 한 필드라도 다르면 충돌. 한쪽만 해당 `security_id`를 알면 `MEMBERSHIP_ONLY_A/B`. 양 출처에서 같은 ticker를 서로 다른 active `security_id`에 붙이면 별도 `CROSS_PROVIDER_TICKER_ISSUER_CONFLICT` (가짜 동일기업 병합 방지). 이는 법적 ID가 같다는 독립 증거를 뜻하지 않음.
2. **기업행동**: 각 원천 내 `security_id + action_id` 수정 이력을 당시 `known_at`까지 최신화하고, 서로 다른 공급자끼리는 `security_id/action_type/effective_on`의 동일 사건을 비교 (행마다 공급자 내부 event ID가 달라도 허용). 같은 사건 여러 개면 임의 축약 없이 `AMBIGUOUS_ACTION_SEMANTIC_KEY` 차단. Split ratio/배당 cash amount가 다르면 각각 `SPLIT_RATIO_CONFLICT`·`DIVIDEND_CASH_AMOUNT_CONFLICT`. 소스 한쪽만 있는 사건은 `ACTION_ONLY_A/B`로 기록. **상폐·합병에 지급된 현금액과 통화는 이 입력 스키마만으로 알 수 없으므로 지급 입증 false**.
3. **회계 정보**: `security_id/metric/period_end`가 같은 경우 당시 공시 가능시각·revision에 따라 최신 claim의 `unit/value`를 대조. 단위가 달라지면 통화환산 등을 지어내지 않고 `FUNDAMENTAL_UNIT_CONFLICT`; 같은 단위 금액 불일치는 `FUNDAMENTAL_VALUE_CONFLICT`. 한쪽 결측은 `FUNDAMENTAL_ONLY_A/B`.
4. **산업 근거**: `industry_id/metric/period_end`로 동일한 unit/value·이력 비교. 일치하더라도 **공식 산업 분류/동종업계 전수 종목 구성**까지 검증된 것이 아님.
5. 원천 유형 중 두 출처 모두 일치하는 활성 기업/기업행동/재무/산업 관찰이 하나도 없으면 `NO_MATCHING_..._EVIDENCE` blocker. 문제별 **전체 건수와 최대 지정 개수 샘플을 분리**하여 많은 오류의 합계가 샘플 크기로 잘못 축소되지 않음. 샘플에는 내부 정규화 연구 ID와 문제 코드만, 원시 공급자 파일/고유 API 인증키·유료 가격·실제 재무값은 포함하지 않음.

## 상태는 '가짜 인증'이 아님

| 응답 status | 실제 의미 |
|---|---|
| `LOCAL_TWO_DECLARED_PIT_SOURCES_CONCORDANT_NOT_CERTIFIED` | 서로 다른 **claimed** 원천의 로컬 연구 입력이 동일 `decision_at`에서 검증한 필드·관찰 범위에 대해 일치. 실제 공급자의 독립성이나 **전체 역사시장 커버리지 증명 아님** |
| `BLOCKED_CONFLICTING_DECLARED_PIT_SOURCES` | 회사 ID, 티커, 산업, 공시, 기업행동·재무값 등 출처 간 누락 또는 모순. 사용자/공급자 확인 전 연구용 후보 확정 불가 |
| `CENSORED_NOT_CONTEMPORANEOUSLY_REGISTERED_SOURCES` | 의사결정 시점보다 한 원천의 최초 등록 또는 claimed retrieval이 늦음. **사후자료를 과거 발굴 정보로 사용할 수 없음** |

모든 status는 `official_leader_promotions=0`, `real_future_leader_precision=null`, `historic_pit_certified=false`, `publisher_independently_authenticated=false`를 유지합니다. 완전히 같은 SHA나 같은 선언 ID를 스스로 생성한 두 파일을 두 개의 진짜 독립 공시 증거로 주장해서는 안 됩니다.

## 사용법 — 이미 반입된 두 원장 필요

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader audit-provider-source-pair \
  --ledger-a output/provider_a/offline.sqlite \
  --bundle-a BUNDLE_A_ACTUAL_SHA256 \
  --ledger-b output/provider_b/offline.sqlite \
  --bundle-b BUNDLE_B_ACTUAL_SHA256 \
  --decision-at '2026-10-11T16:00:00+09:00' \
  --out output/dual_provider_research
~~~

위 경로와 SHA 문구는 실행 양식이며, 실제 한국·미국 기관 자료가 SSD에 등록됐다는 의미가 아닙니다. `bundle_a/b`는 각각 `import-provider-pit` 결과의 진짜 64자리 digest여야 합니다. 양 시장은 **한 쌍으로 섞지 않고**, 한국 KR 입력 두 개 또는 미국 US 입력 두 개를 별개로 대조합니다. 결과는 `provider_source_pair_research.json` **단일 파생 파일**이며 기존 `local_backup.py`의 안전 ZIP 허용목록에서만 백업. 원본 `offline.sqlite`와 raw/staged `*.jsonl`, 증빙 스냅샷 원문은 GitHub·파생 ZIP 제외.

## 오프라인 실제 테스트와 다음 단계

- `tests/test_provider_dual_source_audit.py`: 100% synthetic 서로 다른 provider ID/원장 두 개를 기존 `import_provider_bundle`로 수입해 동일 회사·업종·두 발표일 사건 비교, KR/US 시장 구분, ticker reuse·다른 issuer ID, 분할비율/배당금·재무/산업 단위·수치·상장폐지일 충돌, 후행 receipt 반입 시 검열, 고아/재해시 source 변조 차단, 표본 잘림 표시, CLI/파생 JSON만 ZIP SHA/복원. 실제 source 공개시각/공급자 독립성은 **검증 안 됨**.
- `PYTHONPATH=src python3 -m pytest tests/test_provider_dual_source_audit.py -q --tb=short`, `PYTHONPATH=src python3 -m pytest tests -q --tb=short`, `python3 scripts/check_handoff.py`로 회귀 검증.
- 다음: 법적 security/master corporate registry 실제 공식 제공자 항목·업종/공시 원본 시점과 라이선스/상폐 현금 정산의 외부 독립 증명, 후보 탐지 이후 **사전 봉인된 실제 미래 결과**로 5_5 precision@K, 허위 후보율/발굴 선행일 검증. 위 기능은 **데이터 충돌을 찾아 차단하는 단계**이며 실제 시대 대장주 판정능력 확정의 대체가 아닙니다.
