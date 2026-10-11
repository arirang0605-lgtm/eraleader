# EraLeader 2_2 / 2_5 — 기존 PIT SQLite 무결성 방어 + 실제 가격 캐시/원천 공급자 준비도 점검

> 2026-10-11 KST. 이번 기능은 **실제 저장된 로컬 시장 관측자료를 읽고 PIT 진입에 필요한 증거 공백을 차단하는 코드**입니다. KRX·SEC·거래소의 공인 역사 상장종목 원천, 실제 공시 시각, 기업행동·상폐 현금 정산 또는 미래 대장주 적중률을 자체 인증하지 않습니다. 외부 API 호출·Mac 시스템 환경 변경·SSD 물리 탈착 없음.

## 기존 검증 코드에서 재현한 치명적인 문제

정상 `src/eraleader/offline_pit.py`는 자료를 최초 import할 때 `fingerprint`(canonical payload SHA256)를 기록하고 충돌 수정을 거부합니다. 그러나 예전 `OfflineLedger.snapshot(as_of)`는 **SQLite의 `payload`만 그대로 JSON으로 읽고**, `fingerprint`, `record_key`(원장 자연키), `source_id`, `available_at`, `provenance`의 원본과 일치하는지 검사하지 않았습니다.

따라서 외부 도구나 수동 변경으로 이미 저장된 SQLite에 payload·기업 ID·개정본·공시 가능시각을 수정한 경우, 원장이 바뀌어도 **과거 스냅샷에 탐지 없이 영향을 주는** 결함이 있었습니다. 이 경우 뒤에서 최초 WATCH·점수·전향 결과감사 등을 검증해도 오염된 PIT 원장을 진실 기준으로 사용하게 됩니다.

### 실제 보강 사항

- `verify_stored_pit_record` 순수 검증 함수로, `snapshot`에서 cutoff까지 **실제로 이용 가능하다고 저장된 각 원장 행**을 사용 전에 검사. `kind` / provenance 허용목록, payload bytes SHA256, 중복 JSON 키 거부, 정규화·canonical JSON, 기업/산업 자연키 `record_key`, 원문/SQLite `source_id`, 실제 `available_at=known_at|available_at`와 원장 열의 일치성 모두 검사.
- `normalize`의 revision에는 정수 또는 CSV에서 읽은 십진법 정수 텍스트만 허용. Python의 `int(True)=1`, `int(1.9)=1`처럼 임의 boolean/float이 멋대로 과거 개정 번호로 변환되지 않게 합니다.
- **기존 SQLite 스키마/정상 데이터/공식확정 0 정책은 유지**. 행이 잘못되면 데이터·기존 feature를 재작성하지 않고 `ValueError`로 fail closed; read-only `OfflineLedger.open_readonly`에서도 동일하게 적용됩니다.
- 검사는 로컬 바이트 내부 무결성에 대한 것이며, 누군가 원본 기록·SHA·자기선언 source_id·발행시각을 **모두 같이 새로 작성한 경우** 독립 제삼자 검증이 없으면 진위를 구분할 수 없습니다.

## 실제 KR/US 가격 캐시를 조회하는 명령

~~~bash
cd /Volumes/T5DATA/eraleader

# 현재 T5DATA의 원시 가격 캐시만 읽고, PIT 법적 등록 근거가 없음을 명시
PYTHONPATH=src python3 -m eraleader audit-pit-provider-readiness \
  --cache-root /Volumes/T5DATA/CycleOS-Lab_BacktestEngine \
  --evaluated-at '2026-10-11T09:00:00+09:00' \
  --max-price-age-days 7 \
  --out output/provider_readiness_actual_refined_20261011

# 실제로 공식 원천을 수집한 후 별도 보관한 기존 PIT 원장이 있다면 명시 가능
# --kr-ledger /absolute/path/kr_offline.sqlite --us-ledger /absolute/path/us_offline.sqlite
~~~

- KR: 기존 연도별 `marcap-YYYY.parquet`의 `Date/Code`; US: 기존 주간/비정기 `bars.parquet`의 `ts/ticker` **해당 두 컬럼만** 읽음. 외부 파일 수정 없음. 각 파일 실제 SHA256, 전체 관찰행 수, 최신 날짜 및 그날 raw-symbol 수, 지금과 마지막 날짜의 경과 **시장 현지 달력일**을 출력.
- 특히 미국 캐시는 다수의 주간 관찰 시리즈와 화·목요일의 일부 개별 티커 데이터가 혼재합니다. **마지막 관측일이 종목군 전체가 관측된 날짜라는 가정을 금지**. 마지막 raw-symbol 수뿐 아니라 과거 30달력일 기간에서 최댓값과 최댓값의 80% 이상으로 광범위한 raw symbol이 관측된 가장 늦은 날짜도 따로 계산합니다. 최근 최대값이 20개 이상인데 마지막날 비율이 80% 미만이면 `PRICE_FEED_LATEST_DAY_SPARSE` 차단. 80%는 **자료 표본 불완전성 휴리스틱**, 실제 시장 전체·대장주 판정 기준이 아닙니다.
- 가짜 매수 신호나 종목 후보 없이 데이터 공급자 준비도를 BLOCKED로 반환. 새 `pit_provider_readiness_research.json`에는 별도 PIT 원장 없으면 `KR/US:PIT_LEDGER_MISSING`, 원장에 등록된 영구 기업 ID / 재무 / 산업 / 기업행동 입증이 없으면 명확한 코드로 기록. 사용자 임포트가 모두 합성·자기선언이면 `SELF_DECLARED_OR_SYNTHETIC_PIT_SOURCE`로 표기. 정상 단일 신뢰 기관 원천을 선언했다고 해서 `INDEPENDENT_SOURCE_AUTHENTICITY_MISSING`, `HISTORIC_LISTING_AND_DELISTING_COVERAGE_UNPROVEN`, `CORPORATE_ACTION_AND_CASH_SETTLEMENT_UNPROVEN`를 자동 해제하지 않습니다.
- `independent_pit_verified=false`, `issuer_identity_independently_verified=false`, `future_leader_accuracy_certified=false`, `actual_future_precision=null`, `official_leader_promotions=0`, `external_api_calls=0`는 불변. 이 명령은 **실전 후보를 신규 확정하지 않으며** `OfflineLedger`의 기존 source DB에 기록하지 않습니다.

## 실제 SSD 가격 캐시 관찰 결과 — 2026-10-11 실행

2026-10-11 09:00 KST를 공통 평가 cutoff로 주고 실제 원본 parquet 두 파일의 `Date/Code` 및 `ts/ticker`를 읽어서 계산:

| 구분 | KR | US |
|---|---:|---:|
| 가장 늦은 가격 관측 날짜 | 2026-10-02 | 2026-02-26 |
| 가장 늦은 날짜의 관측 **raw symbol** 수 | 2,873 | **1** |
| 관측 마지막 30달력일 raw-symbol 일자별 최대값 | 2,874 | 494 |
| 광범위 관측이 발생한 마지막 날짜 (휴리스틱) | 2026-10-02 | **2026-02-23** |
| 해당 날짜 raw-symbol 수 | 2,873 | **493** |
| 마지막 관측일 경과 달력일 | 9 | 226 |
| 원본 가격 자료만으로 공인 상장종목 명부 인증 | 아니오 | 아니오 |

US 전 데이터는 901,171행·역사 전체 개별 `ticker` 약 499종이고, 최근 월요일 광범위 표본은 ~493개지만, 마지막 목요일(02-26)은 단 1개 raw ticker만 있습니다. 이것을 2026-02-26에 미국시장 상장사가 1개뿐이라고 해석해서는 안 됩니다. 최신 광범위 가격 입력도 **2026-02-23 기준, 매우 오래됨**. 이 파일은 S&P 500 부근의 관측캐시이며 **전체 미국 과거 상장/상폐 기업 목록도 아닙니다**.

실제 `audit-pit-provider-readiness` CLI 출력: `status=BLOCKED_PIT_PROVIDER_INPUT_READINESS_RESEARCH_ONLY`, 미충족 증거 **11개**. 최신 자료 경과·미국 목요일 표본 부족·공식 PIT 원장 미연결·기업행동·상폐 현금정산 등. 실전 확정 대장주 0 / PIT 독립공증 false. 이는 실제 사용 가능한 기존 가격자료의 **누락/지연을 계측한 결과**이지 2026년 미래 주도주 발굴 성적이 아닙니다.

## 테스트 및 기존 자산 활용

~~~bash
PYTHONPATH=src python3 -m pytest \
  tests/test_offline_pit_integrity.py tests/test_pit_provider_readiness.py \
  tests/test_offline_pit.py tests/test_rank_feature_ledger.py \
  tests/test_batch_pit_integration.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
~~~

새 회귀는 기존 PIT SQLite 원본·SHA/자연키/소스 열·타임스탬프 변조, 본문 키 중복, 소수/boolean revision, read-only 불변/거래소 KR↔US 기간차, 원본 parquet 실측, 가짜 과거 증거 누출·비정상 미래 cutoff, missing/symlink/corrupt parquet, 작은 synthetic 표본과 실제 미국처럼 광범위 주간/산발적 마지막날 관측 차이, CLI 및 파생 1파일 안전 로컬 ZIP SHA 검증·복원을 포함합니다.

## 진행 전 필수 남은 근거

최종 목표는 실제 **미래 시대 대장주를 조기 발굴**하는 것이므로, 원장·백테스트의 수치적 정합성 검증만으로 완료 선언할 수 없습니다. 필요한 독립 데이터:

1. **KR/US 법적 영구 issuer ID/기업별 상장/상폐·티커/업종 변경 이력·PIT 기업동일성**, 역사적으로 포함되지 않은 상폐·퇴출기업.
2. **재무·산업 성장/실적 리비전 공시**의 문서 원본/발행·접수·실제 이용가능시각, 수정공시·후행 정정 빈티지.
3. **배당/액면분할/합병/상폐 현금정산** 원문과 실제 처분·대체일, 시장 수익률 대조용 조정주가 및 세션달력.
4. 실전 배치가 **당시 이미 수집한 자료만으로 사전 봉인**한 WATCH·점수/교체 후보, 평가기간 이후 *독립* 미래 결과 자료·누락률/오탐률/선행기간/precision 검증.

사용자 결정 D-017대로 외부 공급자 API 접속은 로컬 코드 기반 완성 이후; D-021대로 실제 T5DATA SSD 물리 탈착/재부팅 복구 시험은 API 완료 뒤 최종 단계. MarketOS와 별개이며 참조 CycleOS 경로는 읽기 전용. 검증 가능한 정제 코드/문서만 Public GitHub 푸시, 원시 가격/유료 DB/비밀키 업로드 금지.
