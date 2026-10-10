# 2_2 / 2_5 — 시점별 영구 기업 ID·티커 재사용·기업행동 계보 감사

> 2026-10-10 KST. 기업 ID·거래소 코드·공시 원천의 역사적 정합성을 검사할 **오프라인 계약**을 구현했다. 합성 예시는 절대 실제 상장·상폐·기업결합 인증이나 미래 대장주 발굴 결과가 아니다. 외부 API 호출 0회.

## 기존 작업과의 접합

기존 `OfflineLedger.snapshot`은 한 시점의 회원 집합 및 동시 티커 중복을 검사하고, `source_vintage.py`는 소스 공개/획득 시각 및 파일 해시를 감사하며, `delist_cash.py`는 지급된 현금 정산금이 명시된 특수한 상폐 사례에 대해 별도 수익률을 계산한다. 이번 `src/eraleader/issuer_lineage.py`는 **이 모듈들을 대체하지 않고** 공급자의 영구 종목 ID가 기업 개편·티커 재사용·정정 이력을 통과해도 일관되는지 독립적으로 감사한다.

- 로컬 `eraleader.issuer_lineage_research.v1` JSON 계약: `market`, `source_id`, 주장되는 `publisher_id_claimed`/`retrieved_at`; 버전별 `identities` 목록(`record_id`, `security_id`, `ticker`, `market`, `source_id`, `valid_from`, `valid_to`, `known_at`, `revision`), `events` 목록(`event_id`, `security_id`, `action_type`, `source_id`, `effective_on`, `known_at`, 선택적 `successor_security_id`); 관측 티커 목록.
- 동일 `record_id` 수정판이 다른 `security_id` 또는 최초 적용일로 바뀌면 차단; 개정번호 중복/역순 공개시간/미래에 알려진 자료의 과거 반영/데이터 수집일보다 나중 공개된 행도 차단한다.
- 같은 티커를 서로 다른 영구 ID가 **순차적**으로 사용한 경우(예: A→B)는 `declared_historical_ticker_reuse_count`로 관측하되 한 기업으로 합치지 않는다. **동일 시점 겹침**은 `active_ticker_conflict_count`로 별도 표시하며, 가격 코드를 특정 영구 ID에 자동 할당하지 않는다. 한 시점에 보이지 않는 관측 티커도 `observed_tickers_unmatched_count`로 따로 검사한다.
- 기업행동에 등록되지 않은 원 주체, 미등록 합병 후계 `successor_security_id`, 현금 정산 근거 없는 상장폐지 이벤트의 수를 독립적으로 기록한다. 현금 정산액 또는 신규 주식의 금전적 가치를 **생성하거나 추측하지 않는다**.
- 가장 중요한 시점 차단: 주장된 파일 획득 시각이 의사결정 시점보다 뒤이면 `RESEARCH_RETROSPECTIVE_IDENTITY_NOT_PIT`로 처리하고 과거 결정의 인용 가능한 활성 종목을 0으로 표시한다. `independently_usable_asof_identity_count=0`, `historic_membership_pit_certified=false`, `permanent_identity_independently_verified=false`는 어떤 테스트/사용자 입력에서도 참으로 승격하지 않는다. 소스 이름/해시가 진짜 법적 신원·과거 존재를 인증하는 것은 아니다.
- CLI: `PYTHONPATH=src python3 -m eraleader audit-issuer-lineage --file <local JSON> --decision-at '<TZ ISO>' --out <local dir>`. 파생된 `issuer_lineage_{kr,us}_research.json`만 기존 해시/안전 백업 허용 목록에 추가했다. 원본 기업/시세/공시 파일은 ZIP·Git에 넣지 않는다.

## 실제 실행 증거 (합성 / Git ignored)

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_issuer_lineage.py tests/test_local_backup.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 -m eraleader audit-issuer-lineage \
  --file output/issuer_lineage_trial_20261010/synthetic_reference.json \
  --decision-at '2024-06-01T17:00:00+09:00' \
  --out output/issuer_lineage_trial_20261010/reference_result
```

- **합성 정상 계보:** 서로 다른 ID가 AAA를 순차적으로 사용 → 티커 재사용 1, 동시 충돌 0. 미확인 현금 정산 이벤트 1, 미등록 기업행동 대상 1, 불명확한 합병 후계 ID 1. PIT 인증 false.
- **합성 충돌 계보:** A/B가 같은 AAA를 동시에 사용 → 동시 충돌 1. 종목 병합 자동 추론 없음.
- **합성 사후등록 파일:** 자료 취득은 2026-10-10이지만 판단시점은 2024-06-01 → 과거 결정에 사용 가능한 활성 ID 0, `RETROSPECTIVE_IDENTITY_NOT_PIT` 명시.
- 파생 JSON만 `output/continuous/issuer_lineage_research_20261010.zip`에 저장하고 SHA256 검증 및 새 폴더로 복구 PASS. 원본 `synthetic_reference.json` 제외.

## 남은 실제 검증

공식 영구 법적 발행인 ID/티커 변경 이력과 기업행동 원본, 그 당시 실제 공개됐던 원본 버전, 합병 지급대가, 현금 상장폐지 정산 확인, 독립 거래소/데이터 공급업체의 원천 서명/보관시각은 **미확보**. 전향적 미래 대장주 성능은 실제 미래 결과가 성숙하기 전까지 인증 불가. 지표 점수·성과를 과거 유명 종목에 맞추지 말고 먼저 공급자 PIT를 증명해야 한다.

## 2026-10-10 correction: announced exits vs stale open-ended membership

- A confirmed-by-input `cash_delist`, `delist` or `merger` action can have a known `effective_on` prior to the decision day while the supplier's old identity interval remains open-ended. The as-of research view now explicitly **excludes its predecessor security ID** once that event's effective date is reached, rather than continuing to call it an active issuer.
- Pre-effective announced exits do **not** remove an issuer prematurely. Event/source known-at time and supplier retrieval must still be <= decision, otherwise historical eligible count is zero. The output adds `declared_effective_exited_permanent_id_count`. All exchange membership, event provenance, payout and PIT certifications remain false.
- Two additional synthetic regression tests cover a closed cash/delist predecessor and a merger crossing the exact local effective date. Full shared pytest **297 PASS** at last test (including 19 uncommitted other-session walkforward tests). No corporate event source data downloaded.
