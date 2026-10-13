# 137 — DART 사업연도 CFS 최초 로컬 빈티지 등록 · 정정 차단 · PIT 연구 대시보드

**개발 ID:** 2_2 / 3_1 / 3_2 / 6_2. 실제 개발일 2026-10-13 KST.
**작업 기반:** `feature/core-official-factor-coverage-20261013` / 선행 `9739e960efce030fe17e921d9db2338c6e972578`, 기존 정상 KRX/DART/SEC 및 3연도 가속 코드 보존.
**상태:** 로컬 전향 첫 등록 장부 작동/테스트 검증. **DART 공식 최초 공개시간·정정 전체 빈티지·주권 클래스 PIT 인증 아님.**

## 실제로 해결한 구조적 위험

기존 `annual_acceleration_diagnostic`은 로컬 최초 receipt SHA와 FY2023/24/25 당기값의 연속 3연도 비교 자체는 검증했지만 **나중에 API에서 동일 회계연도를 다시 받아 회계숫자가 바뀌면 과거 의사결정에 어느 빈티지를 썼는지 저장/조회할 독립 이력이 없었다.**

새 `src/eraleader/official_dart_vintage_registry.py`는 기존 `official_dart_financials.verify_dart_financial`을 직접 재사용한다. 당일 원시 제공자 SHA, DART 사업연도·법인·주권코드, 정확히 1개 14자리 DART 보고 접수번호, IFRS 원화 계정을 원본에 재검증한 뒤 **별도 SQLite DB에 최초 로컬 수신시각과 실제 이력 등록시각을 함께 등록**한다. 사업연도에 추가 원본이 등장하면 INSERT만 허용하고 기존 레코드 UPDATE/DELETE는 DB 트리거로 차단한다. 동일 SHA는 처음 등록시각을 유지하며 중복 등록하지 않는다.

원본이 여러 개면 서로 다른 접수번호일 때 `MULTIPLE_ACCESSIONS_REVISION_RECONCILIATION_REQUIRED`, 같은 접수번호인데 재무응답이 달라졌다면 `SAME_ACCESSION_CHANGED_UNVERIFIED`. 둘 다 **연도 재무값 선택을 자동 보류**한다. DB 레코드는 SHA256 canonical payload와 이전 이벤트의 SHA256 hash chain으로 연결되고 조회 때 다시 검사된다.

**중요:** SQLite의 append-only trigger·SHA chain은 운영자나 파일 시스템 관리자가 원본 DB를 직접 변조·대체하는 공격에 대한 독립적 봉인이 아니다. 보고서의 `registry_local_not_independently_sealed=true`, `historical_first_publication_certified=false`, `issuer_share_class_pit_certified=false`, `prospective_early_discovery_certified=false`는 상시 표시한다. 접수번호 앞 8자리의 **신고 달력 날짜 ≠ 공인 공개시각**이며, *최초 EraLeader 등록시각*과도 다르다.

## Mac 내부 DB vs T5DATA 외장 SSD

실제 T5DATA `output/`에서 새 `.sqlite` 스키마를 만든 직후 첫 INSERT가 `sqlite3.OperationalError: attempt to write a readonly database`로 막히는 현상을 재현했다. 생성 후 얼마 지나 재시작한 프로세스에서는 등록 성공했다. 따라서 임시 재시도로 운영 완료라고 주장하지 않고 다음처럼 분리했다.

- 시장 원시 API/재무 원본 영수증(0700/0600, read-only 검증): `/Volumes/T5DATA/eraleader/output/official_api_capture`
- **실제 운영 가능 연구 이력 DB**: Mac 사용자 계정 `~/Library/Application Support/EraLeader/research-ledgers/dart_cfs_vintage_forward_20261013.sqlite`. 부모 0700/파일 소유자 제한, 환경변수·API 키 공개 금지.
- SSD 시험 도중 만들었던 `output/dart_cfs_vintage_forward_20261013.sqlite` 등 **부분/시험 DB는 운영 진실원본으로 사용하지 않음**. 임의 삭제도 하지 않음.
- 실제 등록 직후 3연도 **3개 이벤트**의 `checksum` hash chain 검사 PASS. FY2023/24/25 `2026-10-08T12Z` 조회 결과 각각 **0** (소급 불가), 실제 신규 등록 이후 UTC 조회 각 **1** (현지 최초 인지 연구). 원본 DART 상폐·정정 전체 이력은 부재.
- Mac 내부 소유자 이력 DB는 기존 EraLeader B00 SSD 백업 완료 이후의 **신규 파일**이다. 별도 암호화 후속 백업 범위에 아직 포함됐다는 증거가 없다. 이후 운영 안정화 시 정기 암호화 분리 SHA/독립 물리 매체 백업에 추가해야 한다.

## 운영 CLI

`scripts/run_dart_cfs_vintage.py` — `PYTHONPATH` 설치 없이도 원래 `src/`를 import. credentials 호출/외부 HTTP/실거래/실알림 전부 **0**.

초기 FY 개별 등록(직접 사용 시 실제 SHA PIN 입력):

```text
python3 scripts/run_dart_cfs_vintage.py register --db /abs/mac_local/vintage.sqlite \
  --first-capture /abs/private/dart_fin_FY_original \
  --first-sha256 <original SHA256 first receipt> \
  --directory /abs/private/original_dart_corp_directory \
  --directory-sha256 <independent directory first SHA>
```

확정 과거시점 조회 및 local chain 체크:

```text
python3 scripts/run_dart_cfs_vintage.py as-of --db /abs/mac_local/vintage.sqlite \
  --stock-code 005930 --corp-code 00126380 --fiscal-year 2025 \
  --decision-at 2026-10-13T14:00:00+09:00
python3 scripts/run_dart_cfs_vintage.py checksum --db /abs/mac_local/vintage.sqlite
```

기존 공식 첫 영수증만 재사용하는 연구 발행기 `scripts/run_official_api_pit.py`에 선택적 `--vintage-ledger /abs/mac_local/vintage.sqlite` 추가. 명시한 경우 **새 WATCH/SQLite/HTML/보고를 쓰기 전에** 각 FY의 자료 최초 등록시간·현재 공식 원본 SHA·다중 정정 충돌을 검사. 미등록·원본 SHA 불일치·후발 정정이 있으면 출력 시작 전에 `BLOCKED`. NEWS/OFF와 기존 순위 default는 변경하지 않음.

기존 `run_official_research(...,vintage_ledger=...)`의 선택 경로에서는 다음 신규 게시물까지 함께 생성:

- `site/dart_cfs_vintages.html` : 연도별 최초 확보/등록/접수번호 정정 위험 (현재 투자 우선순위 N/A)
- `dart_cfs_vintages.json` : 전체 원시가 아닌 연구용 SHA 증거 링크 및 report SHA
- 기존 `site/kr.html`와 `site/index.html`에서 선택적 새 페이지 링크. **명시적 ledger 선택이 없으면 변경 전 가격·WATCH·보고 경로 유지**.

## 실제 보관 공식 원본 E2E 증거

삼성전자 `005930` FY2023·2024·2025 DART 공식 연간 CFS 최초 수신 SHA 3개 + 현재 corpDirectory, KRX 2026-10-08 관측행 2,765 + DART 해당날 공시 전체 992건의 **기존 최초 원본을 다시 읽고** Mac 내부 이력 DB를 새로 등록/조회:
- FY2023·FY2024·FY2025 연구 DB 각 `PROSPECTIVE_VINTAGE_RESEARCH_RECORDED` 기록(시험 시계 주입 아님). FY2023·24·25 모두 실제 최초 등록 이전 시각에서 N/A, 등록 이후 시각에서 각각 로컬 FIRST_SEEN 단일 원본 상태.
- `output/official_core_cfs_vintage_dashboard_20261013`으로 최초 SHA 재생 CLI 전체 실행 **PASS**: 원본 MARKET WATCH20/일주월 보고서3/독립 실적3연도 1개 기업, DART 첫 로컬 등록 3개 조회 및 SHA 연결, 정정 검토 필요 0. **이는 전체 정정이 없다는 공인 증명이 아니다.** 실전 메시지0, 공식 대장주0.
- 실제 투자 1위~20위·100점 합산·공인 미래 대장주 성공률은 **전부 N/A**. 원본 수신은 2026-10-12~13이라 2023~25에 후보를 발견했다고 주장하지 않음.
- 동일 FY 증빙을 가상으로 수정한 합성 테스트에서는 `SAME_ACCESSION_CHANGED_UNVERIFIED`/다른 접수번호 출현시 `MULTIPLE_ACCESSIONS_REVISION_RECONCILIATION_REQUIRED` → `run_official_research`에서 **SQLite/HTML 최초 생성 전에 차단**.

## 테스트 범위

- 신규 `tests/test_dart_vintage_registry.py`: first receipt pin/원시 SHA, 실제 first registration, 후발 revision, 이전시점 재현, 다른 기업코드·후발공시 차단, SQLite UPDATE·DELETE trigger 및 chain corruption 발견.
- 신규 `tests/test_dart_vintage_cli.py`: CLI 운영 판정, 중복등록, 잘못된 SHA, 출력 비밀 경로 비노출 및 DB 없음 차단.
- 신규 `tests/test_dart_vintage_delivery.py`: 공식 가격·DART CFS3 연구 pipeline과 실제 별도 first receipt 조합 synthetic E2E, 정정 시 미게시, 미등록 조회, 일주월 WATCH 보존, hash-seal HTML 검증.
- 이전 `tests/test_dart_annual_acceleration.py`, `tests/test_official_factor_readiness.py`, `tests/test_official_api_pit_bridge.py`, KRX/DART/SEC/atomic publication/PIT research 영향 13모듈 **전부 PASS EXIT0**. 전체 수천건 회귀, 진짜 장기 선행적중률/정정원문 전체 역사 인증은 아직 별도 진행.
- 공개 GitHub에는 코드/합성 테스트/문서만 업로드. `~/Library/Application Support/EraLeader/research-ledgers/`, `output/official_api_capture/`, 3 FY 실제 원시값/비밀 API 인증·원본 DART 자료는 Git 제외.

## 다음 하나의 작업

지금은 삼성전자 1개사의 최근 DART 공식 CFS 연간 3건에 한정한 first-receipt 전향 데이터 관리다. 다음은 DART 최초 공시의 실제 역사 빈티지·정정 공시 원문/최초 공개시간, KRX 종목 법인/영구 주권 클래스 매핑과 상폐/기업행동, 공식 산업/기관 수급 범위 확대 및 매일 증분처리다. 인증 없는 실적/주도주 승격 0 유지. 안전한 Mac 내부 신규 이력 장부는 별도 암호화 백업에 포함시킬 것.

**진행률:** 과거 99%/95% 전체 완성률 표현 철회. 기능·실데이터 시점완전성·현장운영·전향적 성능을 별도 PASS로 보고한다.
