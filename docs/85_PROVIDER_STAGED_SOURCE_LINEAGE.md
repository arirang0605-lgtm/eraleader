# EraLeader 2_2/2_5 — 원시 staged·정규화·최초 수입 계보 감사

> 2026-10-11 KST. 오프라인 연구 안전성 기능. KRX/DART/SEC 공식 API 응답이나 법적 issuer/share-class/공시 원문·발행시각 독립 공증 **아님**. D-017 외부 API 연결 후순위, D-021 물리 SSD 재연결/맥북 재부팅 마지막.

## 기존 코드의 실질 공백

1. 기존 provider_export_normalizer.py는 KR/US 선언된 staged JSONL을 정규화하며 normalization_witnesses.jsonl에 **원시 행 SHA + claimed source_document_id + normalized 행 SHA**를 저장했다.
2. 기존 provider_pit_adapter.py의 first-write receipt는 **정규화 번들 manifest SHA + 최초 SQLite 수입시각**을 보존한다.
3. 하지만 정상 변환/수입 이후에 **staged 원본 줄·문서ID 주장 ↔ normalized 행 ↔ 최초 수입 receipt**를 함께 다시 대조하는 사용 가능한 명령은 없었다. 변환 과정의 원본 claims가 나중에 바뀌면 공급자 계보가 끊길 수 있다.

## 신규 구현

- 신규 src/eraleader/provider_staged_lineage.py, tests/test_provider_staged_lineage.py, docs/85. 기존 cli.py에 audit-provider-staged-lineage 추가, local_backup.py에는 오직 파생 JSON provider_staged_lineage_research.json 안전 ZIP 허용.
- 기존 staged normalizer의 preflight로 raw manifest/JSONL claimed source/time/company issue/class, row count/SHA를 재검사하고, **변환 당시 공식을 그대로 사용하여 모든 normalized JSONL/manifest bytes와 normalization_witnesses.jsonl bytes**를 재작성/비교한다. 원본 행/문서ID 한 글자 변조나 해시 재계산만으로 일치하지 않는다.
- 옵션 --ledger 시 read-only PIT bundle first-ingest receipt와 normalized manifest SHA/시장/공급자명/vintage/claimed retrieval/수입행수를 재대조. 실제 수입시각이 의사결정 뒤라면 CENSORED_STAGED_INGEST_AFTER_DECISION / locally usable false. 미수입이면 LOCAL_STAGED_BYTES_MATCHED_NOT_FIRST_INGESTED/false. 당시 등록된 normalized 번들이 재검증되면 LOCAL_STAGED_TO_FIRST_INGEST_LINEAGE_MATCHED_NOT_CERTIFIED / locally usable true **연구용만**.
- 입력/raw/normalized/SQLite/witness는 읽기 전용. 처음 검사와 receipt 확인 이후 원본·normalized 전체 검사를 재실행하고 receipt도 재조회해 검사 도중 일어난 변조를 탐지한다.
- 원문 문서 ID/개별 ticker·기업 ID/미공개 재무값·원시주가·라이선스 데이터는 **파생 JSON에 기록하지 않음**. 표시는 source manifest/witness/번들 SHA, 총/도메인별 행수, claimed source, first-ingest availability, blockers/비인증 상태에 한정.

## 아주 중요한 보수적 한계

**기존 최초 수입 receipt는 normalized bundle digest만 봉인하며 원본 문서 ID와 staged 원시 SHA/witness digest를 최초 수입 시각에 결합하지 않았다.** 이후 누군가 source_document_id와 raw/witness를 동시에 다시 써서 normalized 내용이 동일하면, 현재 로컬 원본↔normalized 일치는 여전히 성립할 수 있다. 이것을 최초 수입 당시 원문이 그대로라는 독립 증명으로 오인하지 않도록 출력은 original_doc_id_hash_attested_at_first_ingest=false, independent_source_document_verified=false 고정. 실제 official issuer/PIT verified=false, 대장주 확정 0, 실전 미래 적중률 N/A.

## 실행 양식 (live 경로는 실제 존재를 주장하는 것이 아님)

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader audit-provider-staged-lineage \
  --staged-manifest output/example_stage/manifest.json \
  --normalized-manifest output/example_normalized/manifest.json \
  --ledger output/example_received/offline.sqlite \
  --decision-at '2026-10-11T17:00:00+09:00' \
  --out output/lineage_research
~~~

로컬 파일 수입이 없으면 --ledger 생략 가능하며 해당 경우 PIT 연구시점 사용가능=false. CLI는 OS clock으로 검증하고 backdate 옵션 없음. ZIP 허용은 파생 summary JSON 한 파일만. raw staged/normalized JSONL, claimed document witness, SQLite, 개인키 및 시장 원시는 GitHub/derived backup 제외.

## 회귀 및 미완료

합성 KR/US 복수 증권클래스·재무개정 2판, split 이벤트, original source 문서 ID 바꿔치기 + manifest SHA 재계산, stage 행 순서 변경, normalized ratio/manifest 재해시, witness 수정/누락, 원본·normalized symlink, source 혼용, receipt 교체, 검사 중 파일 변경, 소급/누락/늦은 수입, CLI·ZIP SHA 검증/복원을 테스트한다. 전체 테스트/커밋/푸시 결과는 PROJECT_STATE.md 최신 기록을 기준으로 확인.

NEXT: 실제 KRX/DART/SEC 원문/영구 issuer/security class 식별자·사전 원본 witness 독립 시각/공급자 서명, 역사 전체 상장·상폐/현금정산/PIT 커버리지, 최초 실전 WATCH에서 수개월 뒤 성숙된 5_5 future outcome/오탐률·lead-time 검증. 정상 모듈 REWRITE 금지.
