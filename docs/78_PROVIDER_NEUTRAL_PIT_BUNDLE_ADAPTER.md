# EraLeader 2_2 / 2_5 — 공급자 독립 PIT 원문 번들 수입 + 최초 로컬 등록시각 게이트

> 2026-10-11. **실제 외부 API/공식 기관 원문을 조회하거나 인증하지 않습니다.** 사용자·공급자 파일을 로컬로 제공한 뒤, 신중한 버전·시점·원본 SHA 감사와 단일 SQLite 트랜잭션을 거쳐 **연구용 PIT 원장**에 수용할 수 있게 하는 최소 안정 계약입니다. 이 번들이 공식 한국·미국 거래소 또는 공시기관에서 왔다고 주장해도 그 진위·라이선스·역사 모든 종목군/상폐 현금정산은 독립 인증되지 않습니다.

## 기존 정상 모듈 재사용

- 최초 개발한 `OfflineLedger`의 **불변 자연키/수정충돌 거부/PIT 스냅샷**과 `source_vintage.py`의 **원본 빈티지 SHA·timestamp 오염 검사**를 재작성하지 않습니다.
- 신규 `src/eraleader/provider_pit_adapter.py`에 `inspect_provider_bundle`, `import_provider_bundle`, `audit_registered_provider_asof`를 추가했습니다. 외부 공급자와 상관없는 JSONL 표준입력이라 향후 공급자별 KRX/DART/SEC 변환기에서 같은 계약을 사용할 수 있습니다. 직접 외부 API 키/HTTP 호출을 사용하지 않습니다.
- 기존 2026-10-11 실측 미국 시장가격 캐시의 **마지막일 1 ticker와 최근 광범위 493개**, 한국 10-02 가격 2873종목/미국 02-26 가격 지연 문제는 별도 `pit_provider_readiness.py`에 그대로 보존했습니다. 가격 cache의 raw code를 법적 issuer key로 간주하지 않습니다.

## 1. 정확한 입력 구조

필수 파일은 하나의 로컬 디렉터리에 놓으며, 원본 bytes 및 `manifest.json` SHA를 보존합니다. 모든 필드·파일명·row_count를 엄격 검사하므로 **공급자 고유 원본 API payload를 곧바로 넣는 것이 아닙니다**. 각 공급자 어댑터가 아래 정규화 JSONL로 변환하고 **변환 후에도 원본 파일 별도 보존/취득 시각 입증**이 필요합니다.

`manifest.json` 예시:

~~~json
{
  "schema_version": "eraleader.provider_pit_bundle.v1",
  "market": "KR",
  "source_id": "declared-provider-snapshot-20261011",
  "publisher_id_claimed": "DECLARED_PUBLISHER_NOT_AUTHENTICATED",
  "vintage_id": "2026-10-11-session-01",
  "retrieved_at_claimed": "2026-10-11T13:00:00+09:00",
  "streams": [
    {
      "kind": "membership",
      "file": "membership.jsonl",
      "sha256": "EXACT_SHA256_OF_BYTES_FROM_REAL_LOCAL_FILE",
      "record_count": 1
    }
  ]
}
~~~

SHA는 예시의 설명 문자열 그대로 쓰면 **거절**됩니다. 실제 파일 SHA256 64자리 소문자 hex를 계산해 넣어야 합니다. 각 JSONL 파일 한 줄은 **한 개의 `OfflineLedger.normalize(kind, row)`에 입력 가능한 객체**입니다.

회원 기록 예시(`membership.jsonl` 첫 줄):

~~~json
{"source_id":"declared-provider-snapshot-20261011","revision":1,"security_id":"DECLARED-PERM-ID-001","market":"KR","ticker":"000001","industry_id":"DECLARED-IND-01","valid_from":"2026-01-01","valid_to":null,"known_at":"2026-01-05T10:00:00+09:00"}
~~~

선택적 `actions.jsonl`에는 `security_id/action_id/action_type/effective_on/known_at/revision/source_id`, split이면 `ratio`, 배당이면 `cash_amount`를 지정합니다. `fundamentals.jsonl`에는 `security_id/metric/period_end/available_at/value/unit/revision/source_id`, `industry.jsonl`은 `industry_id`를 사용합니다. 모든 action/fundamentals의 영구 회사 ID, industry fact의 산업 ID는 **동일 번들 내 membership**에서 참조할 수 있어야 합니다. `membership` 번들은 필수, 나머지는 선택 사항입니다. 출처 선언만으로 실제 상폐 현금 지급·정정공시 이용가능시점·투자 가능성은 인증하지 못합니다.

## 2. 수입 전 검증·트랜잭션/실제 시각

- 경로 순회·절대/숨김 파일명·symlink·중복 JSON 키, 빈/초과 크기 파일, 원문 SHA·record_count 불일치, 거짓 source_id, 시장 KR/US 혼합, 유실된 필수 ID, 사업기간/공시 역전, 잘못된 비음수 재무·split 배수 등을 **DB 파일 생성 전** 검사.
- 각 원문 `known_at/available_at`은 매니페스트에 **주장된** `retrieved_at_claimed`를 넘어설 수 없고 그 retrieved claim은 실제 CLI OS 수입 시점 이후가 될 수 없습니다. revision 증가 시 알려진 시간이 역전돼서는 안 됩니다. 한 시장에서 다른 두 기업이 같은 ticker를 동시에 차지하는 겹침 구간은 입력 자체를 거절합니다.
- 전체 4종 입력을 `BEGIN IMMEDIATE` SQLite 한 트랜잭션으로 `OfflineLedger._apply_rows`에 연결. 모든 행을 *무조건* `provenance=user_supplied`로 기록하여 단지 주장된 `publisher_id_claimed`만으로 `external_public_file` 또는 공식 인증으로 승격시키지 않습니다.
- 원본별 `kind/record_key/normalized_sha256`를 신규 `provider_ingest_rows`에, 매니페스트 SHA/시장/빈티지/원천 식별자·row_count/처음 실제 등록 UTC를 `provider_ingest_receipts`에 **같은 트랜잭션**으로 저장. 동일 번들은 최초 등록시간 그대로 재생(idempotent), 같은 빈티지의 내용 교체·과거 row의 hash/자연키 변경 거부. 이전 빈티지에 있던 동일 기업행을 새로운 유효 빈티지에서 재사용할 수 있고 증가 revision만 신규 append; 기존 일반 `OfflineLedger.import_file`로 들어와 최초 receipt가 없던 자료를 *사후에 처음부터 공급자 검증된 데이터였다*고 변경하는 것을 차단.
- 이후 as-of 감사 시 두 receipt 테이블의 row inventory와 실제 `offline_records` 내부 payload SHA/종목 키·provenance를 **다시 read-only 전수 대조**합니다. 지우거나 SHA를 다시 계산해 바꾼 행도 최초 수입 당시 행별 digest와 맞지 않으면 fail closed. 이것은 **로컬 무결성**일 뿐 공급자 원천 서명이나 신뢰할 수 있는 하드웨어 타임스탬프는 아닙니다.
- 운영 CLI에는 **수입 시각을 임의로 입력하는 옵션이 없습니다.** 테스트에서만 명시된 주입 clock으로 과거·미래 경계 테스트를 합니다.

## 3. 중요: 미래 정보 누출을 막는 실제 PIT 스냅샷 연결

기존 일반 `OfflineLedger.snapshot(as_of)`를 최소 변경했습니다. 신규 수입된 provider 행은 원문 `known_at <= as_of`만 확인하는 것이 아니라 **동일 번들 첫 로컬 등록 UTC 및 주장된 수집시각도 평가시각 이전인지** SQL 한 statement에서 같이 검사합니다. 2026-10-11에 수입한 2024년 수치를 `snapshot('2024년')`에 넣지 않습니다. 보류된 행 수는 `snapshot['quality']['provider_rows_unavailable_at_decision_excluded']`로 기록합니다. 실제 provider receipts 테이블이 없는 예전 일반·합성 SQLite는 호환/연구 용도로 기존 동작 유지, 공인 PIT 인증은 기존과 동일하게 false입니다.

`audit-provider-pit-asof` CLI는 별도 1차 번들 receipt SHA/row key/digest를 재확인한 뒤, `retrieved_at_claimed <= decision_at` **및** `first_registered_at_utc <= decision_at`일 때에만 `eligible_for_contemporaneous_research=True` 표기. 2026년에 수집한 과거 공개데이터는 당시 실시간 정보였다는 주장을 할 수 없으며 retrospective로 남습니다. 이 boolean 역시 독립 신뢰시각·법적 상장/공시 원본 인증 **아닙니다.**

## 4. 실제 로컬 CLI

~~~bash
cd /Volumes/T5DATA/eraleader

# manifest/JSONL이 실제 로컬에 준비된 경우에만 수행
PYTHONPATH=src python3 -m eraleader import-provider-pit \
  --manifest output/received_pit_bundle/manifest.json \
  --ledger output/received_pit_research/offline.sqlite \
  --out output/received_pit_research

# 이후 최초 등록 영수증을 평가시점과 대조
PYTHONPATH=src python3 -m eraleader audit-provider-pit-asof \
  --ledger output/received_pit_research/offline.sqlite \
  --bundle-sha256 <검증된_수입_결과의_번들_SHA256> \
  --decision-at '2026-10-11T13:00:00+09:00' \
  --out output/received_pit_research
~~~

`--bundle-sha256`는 실제 `import-provider-pit` 응답에 있는 64자리 hash로 교체해야 합니다. 예시 경로는 **명령 계약**이며 해당 공식 자료가 이미 SSD에 확보됐다는 의미가 아닙니다. 출력 `provider_pit_import_research.json`과 `provider_pit_asof_research.json`은 파생 요약이며 원문 rows는 포함하지 않습니다. 두 파일만 기존 `local_backup.py` ZIP 안전 허용목록에 추가합니다. 실제 원본 JSONL/유료 API 원문/SQLite·개인키/접속비밀번호는 GitHub 또는 파생 ZIP에 업로드 금지.

## 5. 실행 검증/미완료

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_provider_pit_adapter.py \
  tests/test_offline_pit.py tests/test_offline_pit_integrity.py \
  tests/test_source_vintage.py tests/test_batch_pit_integration.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

합성 KR+US 회원·분할·배당·상폐·업종·재무 4파일, 원본 SHA/빈티지·시계 역전·시장/issuer/산업 누락·ticker 겹침·입력 트랜잭션 원자성, 동일 번들 replay/새 revision, 이전 legacy 데이터의 사후 세탁, 재해시된 receipt 행·삭제 source 행 차단, 2024 PIT 조회에 2026 수입 데이터 누출 차단을 포함합니다. 전체 테스트 통과 건수/최종 Git SHA는 `PROJECT_STATE.md` 최신 체크포인트 기준.

**남은 필수 입력:** 공식 KR/US 상장·상폐·영구 발행인 ID·기업행동 이력, 공시별 원문 발행/수신 시각/수정공시의 실제 제3자 증거, 소급 생존자 편향 없는 전수 유니버스/상폐 현금 정산, 원천 라이선스, 신규 사전 봉인 후보의 실제 성숙 결과. D-017 외부 API는 로컬 구축 이후, D-021 물리 SSD 분리·재연결/맥 재부팅은 API 연결 완료 후 최종 단계. **실전 대장주 확정 0 / 미래 정확도 미인증**.
