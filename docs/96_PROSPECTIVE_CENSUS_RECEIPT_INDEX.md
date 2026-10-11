# EraLeader 5_3 / 5_5 — 최초 Top-K 코호트 누락/삭제 탐지용 로컬 영수증 인덱스

2026-10-11 KST. 기존 `prospective_census.py`의 최초 코호트 등록·전수 감사 기능은 변경하지 않는다. **첫 등록 코호트 JSON 파일이 삭제되면 기존 glob 기반 전수평가에서 보이지 않던 결함**을 로컬 별도 SQLite SHA 체인으로 보완한다. 구현은 opt-in으로만 활성화한다.

## 추가 로컬 기능

- 신규 `src/eraleader/prospective_census_seal.py`가 `registry_dir`의 **형제 파일** `<registry_dir>_receipt_index.sqlite`에 최초 등록 영수증을 보존한다. 등록 하나마다 일련번호, 등록 JSON 안전 basename, 원문 바이트 SHA256, 원래 UTC 작성시각, 이전 이벤트 SHA 및 현 이벤트 SHA를 SQLite `BEGIN IMMEDIATE` 직렬 트랜잭션으로 삽입한다. count/head metadata 및 전체 SQLite quick_check를 매번 재검증한다.
- 기존 O_EXCL `register_census`를 DB 트랜잭션 안에서 호출한다. 최초 등록 clock 및 이전 영수증 clock의 단조성 검증, 최초 코호트 동결/label 원문 SHA, 미래 outcome/receipt 사전 존재 금지 등 **기존 엄격 조건을 그대로 적용**한다. 최초 등록 전에 이미 unindexed 코호트 파일이 있었다면 나중에 index를 만들면서 과거 최초기록인 것처럼 **소급 승격하지 않는다**.
- 등록 파일이 삭제·이름 변경·내용 수정됐거나, SQLite receipt/metadata/chain이 누락·개조됐거나, 미추적 manifest가 있으면 strict `audit`가 **오류 종료**하여 누락 코호트를 성과 분모에서 몰래 빼지 못하게 한다. 평가 본체 `audit_all_registered_censuses` 전/후에 두 번 영수증과 전체 원본 manifest SHA를 재검증하고 중간에 바뀌면 보고서 생성 차단.
- 유실된 인덱스 또는 인덱스 트랜잭션 실패 후 남은 O_EXCL 코호트는 **fail-closed**. 자동 삭제·덮어쓰기·이력을 소급 재생성하는 복구는 수행하지 않는다. 복구는 최초 원본 및 안전한 별도 백업 증빙 없이 하지 않는다.
- CLI `scripts/run_prospective_census.py register|audit --receipt-index`로만 활성. 미설정 기본 CLI 동작은 그대로. `audit` 파생 JSON에는 영수증 수·SHA 체인 head와 local verified 표시만, 실제 security_id·원시 ranking·issuer source 문서/DB bytes는 추가하지 않는다.
- **한계**: 동일 사용자가 index와 원본 디렉터리까지 모두 고쳐 쓰거나 삭제하면 독립 공증이 없으므로 변조/누락을 완전히 알아낼 수 없다. Mac OS clock/단일 SQLite SHA는 거래소·발행사·공시 원천 시각의 독립 인증이 아니다. 멀티파일 등록 중단 시 orphan registry가 생기면 자동 복구 없이 조사해야 한다. 실제 PIT 인증·전향 대장주 적중률 모두 N/A, 공식 leader0.

## 사용 예 (실제 공급자 자료 확보 주장 아님)

```bash
cd /Volumes/T5DATA/eraleader
# 최초 prospective Top-K / label 규칙이 동결된 당일에만 실행
python3 scripts/run_prospective_census.py register \
  --spec output/live/first_watch_census_input.json \
  --registry-dir output/live/registered_censuses \
  --name census_20261011_kr.json --receipt-index

# 기존 모든 receipt/index/Top-K를 빠짐없이 검증
python3 scripts/run_prospective_census.py audit \
  --registry-dir output/live/registered_censuses --receipt-index \
  --evaluated-at '2026-10-11T22:00:00+09:00' --out output/live/derived
```

`--receipt-index` 없는 오래된 registry는 후행 생성한 receipt로 엄격 기록임을 주장할 수 없다. 신규 운영 첫 등록부터 정확히 같은 옵션을 사용해야 한다. 동결된 기존 시장 WATCH 및 PIT source ledger는 read-only.

## 실행 테스트/최종 검증

- RED: 신규 모듈 미존재 ImportError, 구현 중 backward-clock 선행 검사 누락으로 **1 FAIL** (DB rollback이더라도 orphan manifest가 남던 결함) 탐지 후 선검사 → GREEN.
- 대상 신규 회귀: 최초 SHA binding, manifest 삭제/이름변경/내용 재해시 변조, 인덱스 유실, 기존 미인덱스 등록 소급 승격 차단, SQLite SHA chain·count 훼손, 중복/동시 등록, 2코호트 합산 원분모 보존, clock 소급 방지, SQLite 권한/link, 트랜잭션 실패 orphan 탐지, CLI 선택 옵션.
- 전체 pytest/handoff/Git push 검증은 PROJECT_STATE.md 최신 기록을 따른다.

**다음 블로커**: 공인 시장 원천(기업ID/share-class/공시·상폐 cash·분할/배당/시장 PIT) 독립 인증, 실제 first-write 미래 코호트의 수개월 후 결과 만기. API 연결(D-017) 및 SSD 물리 재연결(D-021) 시험은 마지막 단계까지 보류.

## 2026-10-11 Mac 실측 추가

- 기존 코호트 24 + 신규 영수증 인덱스 15회귀 **39/39 PASS**. 인덱스가 있는 registry에 기존 약한 audit CLI를 의도적으로 사용해 누락 감지가 우회되던 추가 RED FAIL을 검출; `--receipt-index` 없는 CLI에 엄격 거부를 추가한 후 GREEN. 기본 unindexed 과거 레지스트리(인덱스 자체 미존재)는 이전과 동일.
- Mac 현재 OS-clock synthetic KR+US 각 2개 first freeze, 개별 최초 CLI `register --receipt-index` 두 번, 이후 `audit --receipt-index` ⇒ 등록 코호트2, 전체 고정 분모4, 기간 미도래·성과 없음 unknown4, 영수증 체인2, 데이터 원본 SHA 실행 전후 동일, sanitized JSON-only ZIP SHA 검증·새 경로 복원 통과. live/API0, real precision N/A, official leader0.
