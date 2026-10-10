# EraLeader — 2_2·2_3·3_1~3_3 오프라인 PIT 및 성장 분석 구현

> 2026-10-10 실제 구현·실행. 외부 API, 스크래핑, 유료 데이터 접근 **0회**. 최종 목표는 **미래 대장주 조기 발견**이며, 과거 데이터는 검증 수단.

## 이번 구현 파일과 기능

| 파일 | 실제 구현 내용 | 신뢰 수준 |
|---|---|---|
| `src/eraleader/offline_pit.py` | 로컬 JSON/CSV 수집 → SQLite append-only 보존 → 기준 시점 복원 | 공개 시각 필터 단위 검증, 전체 공급자 완전성 미검증 |
| `src/eraleader/offline_features.py` | 산업 매출/CAPEX YoY, 기업 매출·영업이익 YoY, 매출 성장 가속, 영업이익률 | PIT 입력 기반 연구용 지표 |
| `src/eraleader/cli.py` | `offline-import`, `offline-features` 추가, 시점별 원본 분석 결과 별도 저장 | 오프라인 실행 검증 |
| `tests/test_offline_pit.py` | 미래정보 차단, 정정공시, 멱등성, 트랜잭션, 상장/상폐/티커 중복, 시간대, 조기징후 | 합성 시나리오 테스트 |
| `tests/fixtures/offline_synthetic.json` | 일부러 가상의 SYN-A/SYN-B/SYN-C 기업과 산업을 구성 | **실제 투자 데이터 아님** |

### 오프라인 데이터 입력 계약

- JSON: `{"schema_version":"eraleader.offline.v1","provenance":"synthetic_fixture","records":{"membership":[],"actions":[],"fundamentals":[],"industry":[]}}`.
- CSV: `--kind fundamentals|membership|actions|industry --provenance user_supplied` 같이 명시.
- 공통: `source_id`, `revision`, 공개·최초 이용가능 일시(시간대 포함) 필수.
- 종목 이력: `valid_from/valid_to/known_at`, 종목/산업 ID·티커·국가.
- 기업행동: `action_id/action_type/effective_on/known_at`, split ratio 또는 dividend cash 등.
- 기업 재무·산업: `metric/period_end/available_at/value/unit`, 정정본은 새 revision.
- 입력이 겹쳐 동일 ID에 다른 값을 넣으면 실패·전체 파일 트랜잭션 롤백, 동일 자료 재실행 시 중복 없음.
- 기준일의 **로컬 거래소 날짜**를 사용하면서 공시 이용가능 일시는 UTC로 비교. 미래 이벤트가 발표만 됐으면 `announced_future_actions`로 노출하고 거래가격에는 적용하지 않는다.
- 가격 원본 가격조정/기업행동 역사 완전성·당시 유니버스·전망치의 공급자 신뢰성은 **추가 검증 필요**.

## 실행 예제 (실행 성공 확인)

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader offline-import \
  --file tests/fixtures/offline_synthetic.json --out output/demo_offline
PYTHONPATH=src python3 -m eraleader offline-features \
  --market KR --as-of '2024-07-01T17:00:00+09:00' --out output/demo_offline
PYTHONPATH=src python3 -m eraleader offline-features \
  --market KR --as-of '2024-09-01T17:00:00+09:00' --out output/demo_offline
PYTHONPATH=src python3 -m pytest tests -q
```

실제 사용자 CSV 입력 예: `offline-import --file /your/data/fundamentals.csv --kind fundamentals --provenance user_supplied --out output/real_offline`. 이 코드는 임의 사용자 CSV의 시점/상장폐지 **완전성까지 인증하지 않는다**.

### 합성 데이터 기준 날짜별 계산 검증

| 가상 기준일 | SYN-A 매출 YoY | 영업이익 YoY | 산업 매출 YoY | 성장 연구 신호 | 대장주 판정 |
|---|---:|---:|---:|---|---|
| 2024-07-01 | +25% | 미확보 | 자료 미공개 | 0 | WATCH |
| 2024-09-01 | +60% | +100% | +15% | 1(가상) | WATCH |
| 2024-10-05 | +66%(10/01 정정분) | +100% | +15% | 1(가상) | WATCH |

2024-10에 발표된 정정 값은 2024-09의 연구 결과에 소급되지 않는다. 각각의 실행은 `output/demo_offline/runs/offline_*`에 시간·입력내용 기반 해시명으로 저장된다.

## 실제 검증과 제한

- 전체 pytest: **33 PASS** (이전 17개 + 이번 16개).
- 테스트: 공개시각/정정본·기업행동 발표 vs 실시, 상장폐지, 종목번호 충돌, UTC 날짜 경계, 데이터 변조·원자성, 성장율/가속·결측, 시간별 결과 재현, 합성 자료가 실전 후보로 승격되지 않음.
- `historical_membership`, `corporate_actions_complete`, `financial_pit_complete`는 현재 모두 **미검증**이다. 원자료 일부가 있다고 공급자 완전성이 증명되는 것은 아니다.
- **실제 잠재·확정 대장주를 판별한 적은 없다.** 합성 실적은 실데이터 `output/kr_latest.json`·`us_latest.json`에 혼합하지 않고 `output/demo_offline/`에 격리했다.

## 다음 하나의 개발 패키지

- **3_4·3_5:** 시장 가격 RS + 산업·실적 시점 피처가 동일 기준 시각으로 결합되는 규약/자료품질 연결.
- **4_2~4_5:** PIT 제공자 완전성이 검증되었을 때만 상태 승격을 허용하도록 실제 모듈과 연결, 중요 이벤트 최초 기록.
- **5_2~5_5:** 뒤늦은 승자 맞히기가 아니라 최초 발견 시점·오탐·선정 이후 업종 초과성과/리드타임 검증.
- 사용자가 확정한 **API 마지막 연결** 원칙 준수. PIT 원본이 없는 지표는 N/A 처리하며 가짜 실적을 생성하지 않음.

사용자 보고/새 대화 복구는 `PROJECT_STATE.md` 최신 스냅샷 및 `START_HERE_NEXT_CHAT.md`를 참조.
