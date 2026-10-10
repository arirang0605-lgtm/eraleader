# EraLeader 2_2 / 2_5 / 5_5 — 로컬 PIT 증거 통합 품질 게이트

> 2026-10-10 KST, SSD /Volumes/T5DATA/eraleader에서 실행·검증. **모든 로컬 증거가 충족되어도 법적 원천/PIT 인증, 모델 실전 대장주 발견 성능 인증과 확정 승격은 할 수 없다.**

## 목적과 동작

기존 EraLeader는 PIT 원천 파일 버전/획득시각(`source_vintage.py`), 영구 기업 ID/티커·합병·상폐 계보(`issuer_lineage.py`), 거래소 캘린더 대 가격 주기(`calendar_audit.py`), 다일·다주 가격 누락(`continuity_audit.py`), 상장종목군 대 가격 관측(`pit_coverage.py`)을 **각자** 검사했다. 누락 보고서나 서로 다른 거래일/시장별 감사 결과를 조합해 후보 확정에 사용하면 오류를 놓칠 수 있다.

이번 `src/eraleader/evidence_gate.py`는 **이 다섯 개 파생 감사 결과 JSON만** 한 시점에 대조한다. 필요한 파일명은 고정이며 다른 폴더 또는 심볼릭 링크로 우회하거나 가짜 `certified=true`를 포함할 수 없다. 각 파일 SHA256 및 존재 여부·표준 감사 상태·해당 시장과 현지 판단일·진단 불일치 항목을 기록한다. 원본 공시, 실제 지급증빙, 분할·배당·원시 시세는 읽거나 복사하지 않는다.

| 입력영역 | 요구하는 로컬 연구 감사 |
|---|---|
| `source_vintage` | `source_vintage_audit_research.json`: 가입자/기업행동/재무/산업/원시가격/총수익지수 여섯 계열의 선언 소스, 해시·취득/공개 시각 및 후행 수집 여부 |
| `issuer_lineage` | `issuer_lineage_{kr,us}_research.json`: 티커 충돌, 미확인 영구ID, 기업행동 후계, 상폐 현금 정산 미확정 |
| `exchange_calendar` | `calendar_{kr,us}_research.json`: 거래소 전체 기간 누락, 가격에만 존재하는 날짜, 사후 수집 및 완전성 *주장* |
| `price_continuity` | `continuity_{kr,us}_research.json`: 한국 일봉/미국 주봉 주기 일치, 종목별 중간 공백/최종 관측 종료 |
| `membership_price` | `pit_coverage_{kr,us}.json`: 상장종목군·관측 코드 미일치, 기상폐 종목 관측, 원본 미인증 여부 |

- 어떤 필수 파일이 빠져도 `REPORT_MISSING`이며 수치 0으로 대체하지 않는다. `source_vintage`에 지정 거래일·시장에 대한 소스가 없거나 후행 등록이면 차단한다.
- 유효한 *진단* 보고서가 모두 존재하고 불일치 0건이면 `LOCAL_AUDIT_DIAGNOSTICS_COMPLETE_NOT_PIT_CERTIFIED`; 단 **`official_promotion_allowed=false`, `historical_pit_certified=false`, `model_accuracy_certified=false`가 불변**이다.
- 실제 차단·누락 결과는 `BLOCKED_MISSING_OR_UNRESOLVED_PIT_EVIDENCE`. `blockers`에 미해결 종목·거래소 날짜, PIT 소스 후행성 등 원인을 붙이며, 근거 파일 해시만 보관한다.
- 진단 자체가 위조됐다고 의심될 정도로 스키마/상태/인증 필드가 잘못됐으면 오류 처리한다. 이것은 실제 외부 공인 기록·독립 Timestamp attestation을 대신하지 않는다.

## CLI 및 실제 재현

```bash
cd /Volumes/T5DATA/eraleader

PYTHONPATH=src python3 -m eraleader audit-evidence-gate \
  --market KR --decision-at '2026-10-02T17:00:00+09:00' \
  --input-root output/evidence_gate_trial_20261010/real_cache_only \
  --out output/evidence_gate_trial_20261010/real_partial_report

PYTHONPATH=src python3 -m pytest tests/test_evidence_gate.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

### 실제 검사 결과

- **T5DATA에 있는 한국 로컬 가격 연속성 결과 1개**를 입력한 시험: 다섯 필수 영역 중 현존 1/5, `source_vintage`·`issuer_lineage`·`exchange_calendar`·`membership_price` 보고서 **4개 미존재**, 관측 종료된 종목에 대한 기업행동 정합성 **1개 미해결** → 합계 **차단 5건**. 이 실물 산출물은 PIT 인증 불가.
- 명시적 **합성 연구 감사 보고서 5개**: 형식/시장/시점과 진단상 결함 0 → `research_diagnostics_complete=true`, `blocker_count=0`. 그러나 발행기관/법적 출처 검증 없으므로 **공식 승격 `false`**.
- 연구 결함 5건이 담긴 파생 파일 **`evidence_gate_kr_research.json`만** `output/continuous/evidence_gate_blockers_20261010.zip`에 보관, SHA256 검증·새 경로에 복구 성공. 정산금·원본 벤더 파일·비밀키 업로드 없음.
- 신규 `tests/test_evidence_gate.py`: 누락 파일/합성 정상 보고서/각 소스별 시점·시장·품질 이상/인증값 위조/파일 심볼릭 링크·크기/CLI/백업 등 **25개 사례 추가**. 전체 pytest 기준 300 → **325개 PASS**.

## 반드시 남겨야 할 미완료 사항

실제 거래소 역사적 상장·상폐 목록/영구 기업ID/기업행동 증빙, 정산금 지급/정정 이력, 발행자 공신력 및 당시 이용가능 시각의 독립 기록, 미국 현재 구성원 편향 해소, 실제 봉인 후보의 미래 성과 확인. **이 모듈을 입력 보고서 모두 통과시키기 위한 합성 데이터 조작이나 보고서 조작은 금지**한다. 이 통합 게이트는 미래 대장주 조기 발굴의 진짜 성능검증을 위한 안전장치이지 성능의 증명이 아니다.
