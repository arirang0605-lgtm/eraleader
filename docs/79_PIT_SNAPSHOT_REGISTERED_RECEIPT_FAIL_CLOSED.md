# EraLeader 2_2 / 2_5 — PIT 스냅샷 단계 공급자 receipt 무결성 게이트

2026-10-11. **CONTINUE**, 원본 정규화 데이터/API·WATCH/후보 선정·백테스트 엔진 재작성 없음.

## 실제 수정 목적과 발견한 결함

기존 `import-provider-pit`는 최초 등록 시각/normalized SHA와 전체 receipt digest를 저장했고 `audit-provider-pit-asof`는 검증했지만, 일반 `OfflineLedger.snapshot`은 receipt digest와 비교하지 않았습니다. 공격·오작동으로 저장된 membership 원문과 그 행 fingerprint를 동시에 다시 계산한 경우 내부 JSON 자체의 해시는 유효하므로, 정식 등록 때 봉인한 행별 digest와 다르더라도 스냅샷에 포함될 수 있었습니다. 또한 receipt 링크/영수증 삭제 및 수량/전체 해시 조작도 스냅샷에서는 검출되지 않았습니다.

## 변경 사항

- `src/eraleader/offline_pit.py`: `_read_pit_snapshot_rows`의 SQLite SAVEPOINT 트랜잭션에서 **읽기와 원장 무결성 검증을 동일 스냅샷**으로 처리합니다. receipt 쌍 중 한 테이블만 있으면 실패합니다. receipt row 링크의 고아·실제 등록된 행 누락, `by_kind_json` 수량/중복키, manifest SHA 형식, 각 normalized record 해시, `row_keys_sha256` 전체 digest, 원문 provenance, claimed 수집/최초 등록 시각 역전 여부를 확인합니다. 과거/미래 시점과 무관하게 등록된 receipt 자체가 손상되면 **일반 PIT 스냅샷을 fail-closed** 합니다.
- `src/eraleader/provider_pit_adapter.py`: 기존 `_verify_registered_bundle_rows`의 재사용 감사에 receipt의 `source_id`와 원문 source, receipt의 `market`과 membership 원문 시장 일치 검사를 추가했습니다. 별도의 `audit-provider-pit-asof`도 같은 검사를 받습니다.
- 검증 후 반복 PIT 재생 시 비용 완화: 동일 ledger connection의 `PRAGMA data_version`(다른 연결의 변경), `schema_version`(DDL), `total_changes`(같은 연결 데이터 변경)를 확인하고 DB revision이 변할 때만 receipt 전체를 재감사합니다. 매 스냅샷에서 원시 레코드와 cutoff/as-of 검사는 그대로 수행합니다. 원본 SQLite는 read-only 열기에서 변경하지 않습니다.
- `tests/test_provider_pit_adapter.py`: receipt의 source/market 바꿔치기, 행 payload·fingerprint 동시 재해시, row digest/수량/전체 digest 수정, 링크/receipt/원장 행 삭제, 읽기 연결의 외부 SQLite 변경 감지, 동일 연결 쓰기 후 cache 무효화, 과거 시점 fail-closed, read-only SHA 보존의 회귀 테스트를 추가했습니다.

## 재현 및 한계

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_provider_pit_adapter.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 scripts/check_git_safety.py
```

수정 전 신규 변조 케이스 중 7개가 실패(변조 허용)를 실제 재현했고, 수정 후 집중 회귀를 통과했습니다. **이는 로컬 SQLite 내 내부 일치성 검사입니다.** 악의적 사용자가 DB 전체와 두 receipt 테이블 자체를 모두 바꾸거나 모두 제거하면, 오프라인 원장만으로는 독립 불변·실시간 공증을 증명할 수 없습니다. 그래서 외부 issuer identity·공식 listing/상폐/기업행동 원문, 서명·공개/취득시각 독립 인증, 모든 소스 누락률, 미래 예측 적중률은 여전히 미인증입니다. `historic_membership_pit_verified=false`, 공식 대장주 승격 0 고정입니다.

## 다음 작업

서로 다른 claimed publisher의 영구기업 ID·업종·상폐/기업행동 실제 독립 원문 확보 후 PIT 매핑 충돌/동의 **연구용** 교차 대조와 전향 WATCH의 실제 성숙 성과 검증. 외부 API D-017은 마지막 연결, 물리 SSD 분리/재연결/재부팅 D-021은 API 후 최종 단계. 기존 MarketOS/CycleOS 원자료는 이동·수정하지 않음.
