# EraLeader 5_5 — 전체 Top-K 코호트 조기 발견일·오탐률 정확한 통합 집계

2026-10-11 KST. 목표는 **미래 대장주를 얼마나 일찍 발견하고, 성과가 확인된 후보 중 오탐이 얼마나 되는가**를 여러 코호트에 걸쳐 평가하는 것이다. 사용자가 사전 봉인한 신호/Top-K와 이후 별도 수집한 실제 미래 결과가 아직 없으면 성능 인증은 **N/A**를 유지한다. 기존 점수 공식, WATCH/Top-K freeze 및 outcome label 기준 변경 없음.

## 발견한 실질 미완료

기존 `ranked_outcome_receipts.py`는 코호트 **개별** documented early-hit 중앙 선행일 수만 기록했다. `prospective_census.py`는 모든 사전 등록 코호트의 hit/failure/unknown과 local precision 상하한을 이미 집계했지만 **전체 조기 발견일 분포·중앙값·오탐률 및 미확인 결과를 고려한 오탐률 범위**는 계산하지 않았다. 코호트별 중앙값을 단순 평균하면 서로 다른 hit 건수가 가중되지 않아 조기 발견 능력을 왜곡한다.

## 추가한 실제 기능

- `src/eraleader/ranked_outcome_receipts.py` 기존 strict outcome-document 판정에 **정확한 source 일치/사전고정/기간 내 early hit**의 시장 로컬 일(day) 값만 카운트한다. `documented_early_lead_day_histogram` (예 `{"2":1,"4":1}`)은 sample_limit와 무관하게 원래 K 전체에 대해 작성. 원본 `security_id`, issuer 문서 또는 시장자료는 histogram에 포함되지 않는다. `locally_documented_false_discovery_rate_on_known`은 document가 일치한 known failure/(known positive+known failure)만으로 계산, known=0이면 null. 사후 뒤늦은 양성이나 결과 미제출은 hit에 포함하지 않는다.
- `src/eraleader/prospective_census.py`의 **기존 모든 first-write registry 코호트** 집계에 source-documented lead-day histogram을 누적한다. `int` 타입/양수 정수/정상 문자열 키/`horizon_days` 이내/positive 건수 정확한 합계 검증. 원래 K hit/negative/unknown 검열 조건을 유지하며 `median_locally_documented_lead_days`를 전체 pooled histogram **실제 중앙 순서통계**로 계산. per-cohort median 단순 평균이나 반환 sample N개만 계산하는 오류 방지, 대량 1000개 이상 registry가 있어도 per-security list 재구성 없음.
- `false_discovery_rate_on_documented_known`=자료로 확인한 known 실패 / 자료로 확인한 known 전체(known0=N/A), `full_frozen_k_false_discovery_floor`=known 실패/K, `full_frozen_k_false_discovery_ceiling`=(known 실패+unknown)/K로 집계. 이 **상하한은 unknown의 최악/최선 가정에 따른 산술범위**이며 빈도주의 신뢰구간·실전 정확도 추정값/공식 false discovery rate 인증이 아니다. 기존 precision 및 `real_precision_at_k=null`, `recall_at_k=null`, 공식 leader0, 라이브/API0 보존.
- KR/US의 서로 다른 성공기준/분류 대상/horizon들을 포함한 pooled lead/FDR은 **그 혼합된 연구 표본의 조건부 수치**다. 실제 투자전략 비교에는 market, rule, horizon별로 분리 평가해야 하며 이 통합 지표만으로 실전 대장주 예측력·공식 기업 PIT 진위·오탐률을 주장할 수 없다.
- 기존 `scripts/run_prospective_census.py audit` 및 더 엄격한 `--receipt-index --native-evidence-config` 명령 모두 바꾸지 않고 자동 출력 JSON에 신규 파생 항목을 포함. 기존 DB/first-write registry, 점수/WATCH/feature/시장 raw, source receipts **읽기 전용**. `local_backup.py`의 기존 allowlisted `prospective_census_research.json`만 재사용하여 derived-only ZIP SHA 및 새 경로 복원 가능.

## 재현 및 검증

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_census_lead_discovery_metrics.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/ranked_outcome_receipts.py src/eraleader/prospective_census.py
```

- TDD 신규: aggregate metric 필드/가짜 histogram 미검증 **13 RED** 재현→코드 변경 후 **13 GREEN**. doc claim vs source 원문/unknown 검열, 선행일 중앙값/분모, malformed/범위 밖/중복/boolean/fraction key, positive가 0일 때 null 검증. 각 cohort median 3일(KR 두 hit: 2/4일)과 24일(US 한 hit)의 단순 평균은 틀림. 전체 hit[2,4,24]의 정확한 중앙값은 **4일**.
- 실제 Mac 로컬 ignored 합성 KR/US 첫 census 2개 / 당초 Top-K 6 / documented early hits3 / known negative1 / unknown2를 정식 `run_prospective_census.py audit --receipt-index` 경로로 실행: 전체 중앙 선행일4, known에 대한 오탐률 0.25, full-K 오탐률 산술 하한 0.166667·상한0.5. 첫 영수증 index SHA 검증·원본 outcome/rule/freeze bytes 실행 전후 보존, 파생 JSON-only local ZIP SHA 및 새 폴더 복원 통과. **이 데이터는 합성·테스트용 미래 라벨만 사용한 연구 회귀이며 실전 미래 리더 성공이나 정답성 인증은 아님.**
- 마지막 전체 테스트/GitHub code 커밋 SHA는 `PROJECT_STATE.md` 최신 체크포인트 참고.

## 남은 차단요인

2_2/2_5 실제 KRX/DART/SEC 발행자·주식클래스/상장·상폐 cash/기업행동 당시 공시 원문·독립 수집시각/전체 상장종목군 PIT; 5_5 실제 *지금부터* 사전 최초 WATCH/native Top-K 코호트의 수개월 후 독립 미래 outcome 누적·실측. D-017 외부 API 연동과 D-021 SSD 물리 분리·재연결/재부팅은 최종 단계까지 보류. 코드 재작성 금지, 합성 테스트 수치를 실전 성과로 승격 금지.

## 2026-10-11 Mac 전체 검증/운영 경로 실측

- 이번 TDD 새 13건 최초 구현 전 **13 RED FAIL 재현**, 구현 후 focused **13/13 GREEN**. 기존 strict outcome, 전체 census, native proof 및 첫 등록 receipt 테스트와 호환 PASS. 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1512/1512 PASS exit0**(기존1499+13), collect-only1512, handoff 30개 ID/40 필수 경로 PASS, py_compile/diffcheck PASS.
- 실제 Mac CLI `python3 scripts/run_prospective_census.py audit --receipt-index --registry-dir <ignored trial>` 성공. 합성 KR·US 각각 사전 봉인 simulated Jan 2026 소스 2개/총 선정 K6, source-corrob positives3/known failures1/unknown2, **pool median 4일**(개별 median 평균 13.5일과 달라야 함), known 오탐률25%, 전체 고정분모 오탐산술 하한16.6667%/상한50%, 실전 precision N/A. 기존 O_EXCL 영수증 DB SHA 확인, frozen/outcome/rule 원문 바이트 처음/끝 동일, derived `prospective_census_research.json`만 안전 ZIP SHA 검증 및 새 위치 복원.
- 테스트에서 사용된 라벨과 문서 발행시각은 **합성/주입 시점**이며 실제 2026-01 미래 예측 성과를 소급 인증한 것이 아님. 기존 살아 있는 전체 주식시장 PIT/공시·상폐/법적 issuer 독립 검증 N/A.
