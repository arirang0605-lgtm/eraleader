# EraLeader 1_3 / 2_2 / 2_5 — KR·US staged 원천자료 → 공급자 중립 PIT 정규화 어댑터

2026-10-11 KST. **KRX/DART 또는 SEC의 공식 원시 API 응답 형식을 그대로 구현한 것이 아닙니다.** API 연결을 뒤로 미룬 사용자 결정 D-017을 준수하면서, 그 전에 수동·공급자 어댑터로 수집해 놓은 **명시적 중간 내보내기(staged export) 형식**의 필드·증거·정규화를 로컬에서 검증합니다. KRX·DART·SEC/미국거래소의 실제 발행자 서명, 증권 영구 ID, 역사 전체 상장/상폐 자료, 실전 조기 발굴 정확도는 계속 미인증입니다.

## 이번 구현 범위와 기존 코드 재사용

- 새 `src/eraleader/provider_export_normalizer.py`의 `normalize_provider_export`는 읽기 전용 로컬 입력 `eraleader.provider_staged_export.v1` manifest 및 1~4종 JSONL을 검증하고, **새 폴더에만** 기존 `provider_pit_adapter.BUNDLE_SCHEMA` 형식의 `manifest.json`과 `membership/actions/fundamentals/industry.jsonl`를 정규화해 생성합니다. 원본 source 파일 수정 0, 외부 API 호출 0, SQLite 수입·등록 시각 변경 0.
- 이미 1,086개 테스트로 검증된 `provider_pit_adapter.inspect_provider_bundle`을 결과 저장 전 **동일한 실제 정규화 manifest/JSONL**에 재실행해 기업ID·업종ID 참조·복수 클래스·기업 코드 중복·공시 시각을 검증합니다. `OfflineLedger`, `provider_pit_adapter.import_provider_bundle`, `audit_registered_provider_asof`를 재개발하지 않습니다.
- `src/eraleader/cli.py`에 `normalize-provider-export --manifest --stage-dir --out` 명령만 추가. `src/eraleader/local_backup.py`에는 파생 **`provider_stage_normalization_research.json`** 한 파일만 추가하며, 수집된 원시 JSONL·정규화 JSONL·`normalization_witnesses.jsonl`·공급자 manifest·수입 SQLite는 GitHub·파생 ZIP에 포함하지 않습니다.

## 입력 계약: 실제 외부 API 데이터가 아닌 선언된 중간 형식

manifest 정확한 최상위 필드: `schema_version, market, profile, source_id, publisher_id_claimed, vintage_id, retrieved_at_claimed, streams`. `streams[]`의 각 객체는 `kind,file,sha256,record_count` 네 필드만 포함하며 `kind=membership`은 필수입니다. `file`은 같은 디렉터리의 숨김파일이 아닌 안전한 JSONL basename이고 `sha256`은 해당 **실제 바이트**의 64자리 소문자 해시입니다. `retrieved_at_claimed`는 시간대가 있는 ISO 8601 문자열이며 실제 CLI의 로컬 OS 시각보다 미래이면 거부합니다. 단 이 값 자체는 외부 신뢰기관이 공증하지 않았습니다.

### KR: `profile=KRX_DART_STAGED_V1`, `market=KR`

`membership` 한 행의 필수 선언 필드: `corp_code` (숫자 8자리), `issue_uid` (명시적 종목/발행 증권 구분자), `stock_code` (6자리), `industry_code`, `listed_on`, `delisted_on` (null 가능), `published_at`, `revision`, `source_document_id`.

- 정규화 연구용 종목 식별자: `KR:CORP<8자리 법인코드 주장>:ISSUE:<원천이 선언한 issue_uid>`.
- `stock_code`는 **시장 거래기호**로만 저장하고, 법인 ID·종목 ID와 동일하게 간주하지 않습니다. 이 `issue_uid` 역시 아직 공식 영구 증권ID가 확인된 것이 아니므로 외부 원문 대조는 미완료입니다.
- `industry_code`는 `KR:INDUSTRY:<선언 코드>`로 분리.
- 동일한 issuer/issue를 지칭하는 `actions` 행: `corp_code,issue_uid,event_uid,action_type,effective_on,published_at,revision,source_document_id`; split은 양의 `ratio`, dividend는 `cash_amount` 필수. 상폐·합병을 현금 지급 확정으로 자동 해석하지 않습니다.
- `fundamentals`: 동일 회사·issue + `metric,period_end,published_at,value,unit,revision,source_document_id`.
- `industry`: `industry_code,metric,period_end,published_at,value,unit,revision,source_document_id`.

### US: `profile=SEC_EXCHANGE_STAGED_V1`, `market=US`

- `membership`: `cik` (숫자 문자열 1~10자리), `share_class_uid` (명시적 클래스/증권 구분자), `ticker`, `sic` (4자리), `listed_on,delisted_on,published_at,revision,source_document_id`.
- 정규화 **연구용** 종목 식별자: `US:CIK<10자리 제로 패딩>:CLASS:<선언 클래스 ID>`. SEC CIK는 보고 주체를 식별하는 데이터이므로 **CIK만으로 주식 클래스·상장 증권 하나를 추정하지 않습니다**. 클래스 ID는 별도 출처 확인 전까지 사용자가 주장한 값입니다. `ticker`는 별도 거래기호이며 한 회사의 복수 클래스도 서로 다른 ID를 유지합니다.
- 섹터 키는 `US:SIC:<4자리 주장 코드>`; `actions/fundamentals`는 `cik`와 `share_class_uid` 둘 다 명시해야 하며 `industry`는 `sic`를 사용합니다. 기업 단위 SEC 재무정보를 자동으로 모든 주식 클래스에 복제하지 않습니다. 각각 명시적 클래스에 연계됐다는 원천 근거가 없으면 입력하지 않아야 합니다.

두 프로필 모두 JSONL의 `published_at`을 `OfflineLedger.known_at/available_at`으로 시간대 인지 UTC로 정규화합니다. 단 `period_end`는 공시 가능시각과 별도이며 이전에 정상화된 회계기간 조회 규칙을 사용합니다. `source_document_id`는 각 행의 **원천 주장 문서 ID**이며 별도 `normalization_witnesses.jsonl`에 원본 라인 SHA·정규화 SHA·자연키와 함께 보존됩니다. 원천 문서의 실제 서명/발행 여부는 미검증입니다.

## 실행 방법: 두 단계는 완전히 분리

~~~bash
cd /Volumes/T5DATA/eraleader

# 단계 A: 기존에 별도로 안전 확보한 staged 원천 파일을 검증/정규화. 출력은 새 폴더.
PYTHONPATH=src python3 -m eraleader normalize-provider-export \
  --manifest output/declared_vendor_stage/manifest.json \
  --stage-dir output/pit_bundle_new_20261011 \
  --out output/derived_research

# 단계 B: 실제로 만들어진 정규화 manifest를 append-only PIT 원장에 수입
PYTHONPATH=src python3 -m eraleader import-provider-pit \
  --manifest output/pit_bundle_new_20261011/manifest.json \
  --ledger output/pit_received/offline.sqlite \
  --out output/derived_research

# 단계 C: 첫 로컬 등록시각 이전 날짜로 자료가 누출되지 않았는지 사후 감사
PYTHONPATH=src python3 -m eraleader audit-provider-pit-asof \
  --ledger output/pit_received/offline.sqlite \
  --bundle-sha256 YOUR_ACTUAL_64_CHARACTER_IMPORTED_SHA256 \
  --decision-at '2025-09-01T17:00:00+09:00' \
  --out output/derived_research
~~~

위의 경로는 **명령 양식**일 뿐, 해당 공식 입력이 실제 SSD에 준비되어 있다는 뜻이 아닙니다. 프로필별 **동일 staged bundle 재실행**은 기존 정규화 출력폴더를 절대로 덮어쓰지 않으므로 다른 이름으로 실행해야 합니다. 기존 PIT 수입기의 동일 normalized bundle 재수입은 최초 등록시각을 보존하며 중복 삽입하지 않습니다.

## 실제 Mac 오프라인 검증 범위

- 합성 KR·US staged source 각 4종 (`membership/actions/fundamentals/industry`)을 **로컬 파일에서만** 생성. 두 시장의 독립된 issuer/issue/class 매핑, 미국 CIK 1~10자리 zero-pad, 별도 share class, 동일 KR 법인 내 issue UID, ticker 겹침/잘못된 corp_code/CIK/stock_code/sector/문서 ID/누락 class ID 등 fail-closed 테스트.
- 원본 SHA/row_count/시장 profile 불일치·rehashed 미래 공개/수집시각·후행 개정 역전·미소유 액션/재무·산업 fact·잘못된 split/cash optional·source file symlink/traversal·추가 API 필드/중복 normalized key를 자동 검사하고 **검증 실패 시 최종 staging folder 생성 전 종료**.
- 실제 **KR+US CLI 각각 정규화 4행→기존 append-only PIT 수입 4행→과거 2025 시점 0개 등록회사로 조회(미래정보 누출 차단)**. 원본 JSONL 바이트 불변, 수입 후 감사만으로 SQLite SHA 불변, 실제 파생 JSON 3파일만 시장별 ZIP SHA `LOCAL_BACKUP_VERIFIED` 및 동일 bytes 복원.
- 전체 프로젝트 테스트·테스트 수·Git 커밋 결과는 `PROJECT_STATE.md` 최신 기록이 우선합니다.

## 중요한 실전 미완료

D-017에 따라 KRX/DART/SEC 네트워크 API는 아직 연결하지 않았습니다. 공식 기관이 보낸 원본 실제 필드/규정에 맞춘 수집기·제3자 법인/클래스 영구 ID 증빙, 역사 전체 상장/상폐·기업행동·현금정산, 금융정보 개정/수정공시의 독립 PIT 공증, 생존자 편향 없는 후보 universe, 사전 동결된 미래 대장주와 실제 성숙 outcome가 필요합니다. 따라서 성공적인 변환 결과만으로 WATCH 승격/확정·예측력/수익률을 만들지 않습니다. 실제 SSD 분리/재연결/재부팅 검증은 D-021 최종 단계에만 진행합니다.
