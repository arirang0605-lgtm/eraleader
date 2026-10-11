# EraLeader 2_2 · 2_5 — 제3 거래소 전시장 상장 클래스 명부 PIT 대조

> 2026-10-12 KST. 이 기능은 기존 `issuer_class_bridge.py`가 검증한 **두 개의 별도 주장 원천**과 제3의 **선언형(공인되지 않은) 전체 거래소 상장 클래스 명부**를 시점별로 대조하는 로컬 연구용 검사다. KRX/DART/SEC API·외부 시세·비밀키·실전 메시지·상폐 현금 결제를 호출하거나 인증하지 않는다. 등록된 명부가 official exchange dataset임을 증명하지 않는다.

## 새 기능과 실질적인 검증 공백

기존 `issuer_class_bridge.py`는 스테이징된 issuer/share-class와 별도 법인 계보 간의 영수증·원문 SHA·시점/상폐 효력일 및 정확한 주식 클래스가 맞는지 검증한다. 그러나 **두 출처에 동일하게 누락된 제3의 상장 클래스를 발견하지 못한다**. 기존 `pit_coverage.py`는 price feed 관측과 대조하지만 거래정지·매매 부재를 상폐로 오인할 수 있어 공식 거래소 전체 명부의 대체물이 아니다. 이번 `exchange_roster_crosscheck.py`는 **제3의 당시 전시장 명부**를 명시적으로 요구하고 두 검증 원천이 모두 빠뜨린 클래스/티커/상장기간 모순을 탐지한다.

신규 `audit_declared_exchange_roster(staged_manifest, issuer_lineage_file, roster_file, *, decision_at, clock=None)`:
- 기존 `audit_staged_issuer_class`, `provider_export_normalizer._preflight`, `issuer_class_bridge._stage_active/_reference_active`를 **읽기 전용 재사용**. 당초 original staged JSONL SHA, issuer lineage revision/공시 공개 주장 시점, 이미 유효해진 merger/delist, 단일 issuer 아래 복수 주식 클래스를 그대로 확인한다.
- 세 번째 명부는 시장(KR/US), 단일 **시장 현지 거래일**(`session_day`), 발행 `published_at`과 원본 확보 `retrieved_at`, 고정 `scope_id=ALL_LISTED_EQUITY_CLASSES`, `complete_scope_claimed: true`, 영구 issuer+share-class `security_id`·ticker·상장/종료 **반개구간 [valid_from, valid_to)** 전체를 선언한다. 클래스 누락·과잉, 같은 ticker인데 법인·share-class가 다른 경우, interval 차이, 거래소 주장과 issuer lineage 차이, 같은 issuer의 서로 다른 증권 클래스 생략을 각각 검사한다. 종가/체결 데이터로 상장 명부를 추론하지 않는다.
- `session_day`는 `decision_at`의 KR Asia/Seoul 또는 US America/New_York **현지 날짜와 정확히 같아야** 한다. 다른 날/미래 snapshot 자동 대용 금지. 특히 거래소의 해당 일자 전체 명부를 과거에 알고 있었다고 위조하지 않도록 **명부 claimed 발행일의 시장 현지 날짜가 해당 session보다 빠르면** 에러로 차단한다. claimed `published_at <= retrieved_at <= 현재 감사 OS clock` 검사, `published_at/retrieved_at > decision_at`이면 당시 사용 불가인 `CENSORED_DECLARED_EXCHANGE_SCOPE_NOT_CONTEMPORANEOUS_OR_INDEPENDENT`로 처리한다. US DST 경계에서도 고정 UTC 날짜로 조인하지 않는다.
- 제3 출처의 claimed `publisher_id_claimed` 및 `source_id`는 기존 두 출처와 다르게 선언되어야 한다. 대소문자만 바꾼 동일 출처는 독립 근거가 아니며 검열. **실제 발행기관 서명/공식 KRX/SEC 원천 확인, 최초 게시/취득 시각의 독립 공증이 아니므로** `historical_exchange_universe_pit_certified=false` 및 `official_leader_promotions=0`은 모든 결과에서 고정.
- 동일 소스를 **2회 독립 재검증**하면서 전체 staged JSONL·issuer·exchange roster 원문 SHA가 도중 변조된 경우 결과를 발행하지 않는다. 중복 영구 ID/동시 ticker/미래 class·비양수 listed interval/원문 JSON 중복키·symlink·oversized 파일은 fail-closed. 공인 supplier business claims나 raw 종목ID·ticker·CIK·corp_code/로컬 입력 파일경로는 파생 보고서에서 제외. 상태는 `LOCAL_THREE_DECLARED_SOURCES_COMPLETE_SCOPE_MATCH_NOT_CERTIFIED`, `BLOCKED_DECLARED_EXCHANGE_SCOPE_CONFLICT`, `CENSORED_DECLARED_EXCHANGE_SCOPE_NOT_CONTEMPORANEOUS_OR_INDEPENDENT` 중 하나.

## 오프라인 데이터 계약

아래는 **연구 합성 계약 예시**이며 실제 KRX/SEC 원본 API 응답 형식이 아니다. `security_classes`에는 해당 시장/해당 거래일의 **전체 선언 상장 증권 클래스**만 포함한다.

```json
{
  "schema_version": "eraleader.declared_exchange_roster.v1",
  "market": "KR",
  "source_id": "CLAIMED_ROSTER_SOURCE_C",
  "publisher_id_claimed": "CLAIMED_EXCHANGE_PUBLISHER_C",
  "scope_id": "ALL_LISTED_EQUITY_CLASSES",
  "complete_scope_claimed": true,
  "session_day": "2026-10-12",
  "published_at": "2026-10-12T16:00:00+09:00",
  "retrieved_at": "2026-10-12T16:05:00+09:00",
  "security_classes": [
    {
      "security_id": "KR:CORP00001234:ISSUE:ISSUE_A",
      "ticker": "123456",
      "valid_from": "2020-01-01",
      "valid_to": null
    }
  ]
}
```

US 클래스는 `US:CIK0000012345:CLASS:CLASS_A` 등 개별 주식 클래스를 명시한다. **전체 기간 역사 거래소 명부 완전성은 개별 `session_day` 입력과 시점 감사가 누적되어야** 시험 가능하며, 당장은 실제 공인 거래소 제공본이 없어 연구 모의일 뿐이다.

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/audit_exchange_roster.py \
  --staged-manifest output/local_stage/manifest.json \
  --issuer-lineage output/local_issuer/identities.json \
  --exchange-roster output/local_exchange_roster/market_20261012.json \
  --decision-at '2026-10-12T16:10:00+09:00' \
  --out output/research_exchange_roster
```

기본 WATCH/Top-K 자동 승격 경로에는 연결하지 않음. 조건 일치만으로 후보·공식 시장 PIT 인증을 주장하지 않는다. `exchange_roster_coverage_research.json` 하나만 안전 원자 출력, `local_backup.py`의 안전 JSON allowlist에 파일명 하나만 추가 → 기존 ZIP manifest SHA 검증/새 위치 복원. 공식 KRX/DART/SEC issuer/class·거래소 전체 PIT 원천 및 상폐 cash와 기업행동/공시 최초 수집시각은 D-017 실제 API 연동·원본 출처 인증 시 **별도 검증** 필요.

## 테스트

`PYTHONPATH=src python3 -m pytest tests/test_exchange_roster_crosscheck.py -q --tb=short`
`PYTHONPATH=src python3 -m pytest tests -q --tb=short`
`python3 scripts/check_handoff.py`

새 케이스: KR/US 3중 로컬 정확 일치, 같은 SEC CIK 2개 share-class 보존, 교차 공급자와 명부 누락/과잉·동일 ticker 다른 법인/클래스·상장기간, declared issuer/publisher alias·대소문자 우회, late availability, 발표 이전 취득 위조, 명부 날짜 틀림/미래 날짜, **다음 시장 날짜를 전날 발행했다고 주장하는 정보 누출**, 미국 DST, 이미 효력된 상폐/합병, 중간 원문 SHA 변형/중복 ID/JSON 중복키/symlink, CLI/출력 개인정보 비노출 및 ZIP 백업·복구. 어떤 합성 검증도 실제 법적 issuer·공시 PIT·실전 대장주 확정이 아님.
