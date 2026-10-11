# EraLeader 2_2/2_5 — 최초 반입시 raw staged/document witness SHA 봉인

> 2026-10-11 KST. 사용자 D-017에 따라 외부 KRX/DART/SEC API 연동 없이 개발한 로컬 증빙 무결성 기능. 법적 issuer/class, 독립 원천 서명·공개시각, 전체 역사 종목군 PIT 및 실전 미래 대장주 성과는 인증하지 않음. D-021 SSD 물리 탈착/재부팅 시험은 API 이후 최종 단계.

## 이전 기능의 실제 공백

직전 docs/85의 원본→정규화 재계산 감사는 현재 원시 manifest/stream 원본 문서ID 주장과 normalized SHA를 비교하지만, 최초 SQLite 입수 영수증은 normalized bundle SHA만 기록하였다. 이 때문에 원시 source_document_id + witness를 함께 바꿔도 normalized business rows가 동일하면 최초 수입 당시 문서 ID의 동일성을 보증할 수 없었다.

## 이번에 추가한 실제 기능

- 기존 provider_pit_adapter.import_provider_bundle에 staged_manifest 입력을 **선택** 지원한다. CLI import-provider-pit의 --staged-manifest 플래그. 기존 일반 normalized-only 수입 옵션은 정상 보존하며 최초 원본 PIN 인증이 있었다고 소급 승격하지 않는다.
- 신규 staged_first_ingest_pin.py: 기존 provider_staged_lineage._one_pass로 모든 raw staged manifest/JSONL/claimed document IDs/natural key→normalized JSONL/manifest/normalization_witnesses.jsonl의 바이트 정합성을 수입 전에 검증한다.
- 동일 normalized SQLite BEGIN IMMEDIATE 수입 트랜잭션 안에서 변경 여부를 다시 전수검사하고, 새로운 provider_staged_original_receipts 행에 원본 staged manifest SHA256, 원시 종류별 stream SHA256, normalized stream SHA256, original doc ID가 담긴 witness 전체 SHA256, source claimed ID/market/vintage/claimed retrieval, 최초 실제 SQLite 수입 UTC 시각과 normalized bundle SHA를 정규화 JSON으로 결합한다.
- 최초 raw pin 행의 hash를 기존 provider_ingest_receipts 원본 수입 영수증의 새 original_staged_pin_sha256 컬럼에 동일 트랜잭션으로 기록. 한쪽 테이블/행/해시를 삭제·변조하면 그 뒤의 strict audit 및 기존 normalized 재수입도 중단한다. 전체 정상 검증 실패 시 양측 rollback; 원본/중간파일 수정 없음.
- 원래 동일 번들 정상 재수입은 최초 UTC 시각·원본 bytes PIN을 보존. 예전 normalized-only 데이터에 **뒤늦게 원본문서 해시를 수입 당시처럼 추가하는 소급 고정**은 차단.
- 기존 audit_staged_source_lineage에 require_original_first_ingest_pin 및 CLI --require-original-first-ingest-pin 옵션. strict mode에서는 original pin 없는 기존 수입자료를 거부. 원본+최초 normalized receipt가 일치하는 경우 original_doc_id_hash_attested_at_first_ingest=true와 original_doc_id_first_ingest_pin_locally_only=true로 **해당 Mac의 로컬 시점 PIN만** 명시하고 independent_source_document_verified=false/external_pit_certified=false 유지. 제출이 늦은 자료는 시점이 붙어 있어도 CENSORED 처리.

## 재현 방법 (예시 경로, 실전 원천 확보 주장 아님)

~~~bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader import-provider-pit \
  --manifest output/example_normalized/manifest.json \
  --staged-manifest output/example_original/manifest.json \
  --ledger output/received/first_ingest.sqlite \
  --out output/derived

PYTHONPATH=src python3 -m eraleader audit-provider-staged-lineage \
  --staged-manifest output/example_original/manifest.json \
  --normalized-manifest output/example_normalized/manifest.json \
  --ledger output/received/first_ingest.sqlite \
  --decision-at '2026-10-11T19:00:00+09:00' \
  --require-original-first-ingest-pin \
  --out output/derived
~~~

원본 staged/normalized JSONL, witness, SQLite, 원시 시장자료 및 비밀키는 GitHub Public과 derived ZIP에 포함하지 않는다. 파생 요약 JSON만 기존 local_backup allowlist 사용, 외부 API 연결과 물리적 SSD 탈착 0.

## 검증/한계

KR·US synthetic multi-class/issuer/기업행동·재무 원본으로 최초 raw pin+normalized 동시 commit, idempotent 재수입, 구형 legacy backward-compat, 소급 원본 승격 거부, source_document_id/witness 함께 재해시 공격, source 중도 변경시 rollback, 원본 pin 삭제/receipt marker 훼손, timestamp/market/source 불일치, CLI strict audit를 테스트한다. 검증 수치와 Git SHA는 PROJECT_STATE.md 최신 기록을 따른다.

**중요:** 동일 Mac 사용자 또는 공격자가 최초 SQLite 영수증 및 원본을 통째로 동일 시점 재작성할 수 있으면 로컬 SHA/OS clock은 독립 공증이 아니다. 진짜 KRX/SEC 원문 게시시각, 법적 영구 issuer·security class, 산업 시점, 상폐 cash settlement/기업행동·전체 역사 우주 PIT와 실전 성숙 outcome은 확보되지 않았다. official leader0/실전 precision N/A.

NEXT: 오프라인 first-pin 증빙을 실제 독립적인 supplier/PIT source와 교차대조하는 계약 2_2/2_5 및 5_5 사전 첫 WATCH→native Top-K→수개월 뒤 outcome 평가, D-017 API는 로컬 개발 완료 후, D-021 하드웨어 재연결은 최종 검수. 정상 코드 CONTINUE.
