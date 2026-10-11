# EraLeader 6_4 / 6_5 — 로컬 연구 데이터 오류/파일복구 DRY-RUN 알림 원장

2026-10-11 KST. 6_2/6_5 메인 운영 상태 감사 `operations_overview.py` 결과를 재활용해 **가격/WATCH/Top-K 예약 파일의 데이터 오류·복구를 로컬 SQLite outbox에 최초기록**한다. 장기 목표는 사용자 승인을 받은 후 외부 API/실제 수신채널과 별도로 연결하는 것이나 이번 구현은 **외부 API 0회, 실제 메일/텔레그램/주문/웹 공개 0회**이다. 현재 데이터 지연이나 보고서 파일 SHA mismatch를 '대장주 약화' 혹은 '시장 실패'로 해석하지 않는다.

## 정상 코드 보존/운영 입력

- 신규 `src/eraleader/local_failure_outbox.py`의 `run_local_failure_outbox(project)`는 기존 `audit_local_operations`와 `render_operations_overview`를 재사용한다. 실제 메인 가격 `scheduler_control`, 최근 WATCH `scheduler_watch_control`, 사전 freeze Top-K `scheduler_maturity_control` 세 가지 스케줄러 파일/검증 ZIP/파생 HTML·MD·JSON만 조회한다.
- 기존 운영 대시보드의 3모드 상태값을 품질 조건으로 바꾼다. `STALE_PRICE_OBSERVATIONS`, `OUTDATED_RESEARCH_SNAPSHOT`, `ARCHIVE_UNVERIFIED`, `CHECKPOINT_INVALID`, `PUBLISHED_BYTES_MISMATCH` 등은 **`DATA_FAILURE_LOCAL`**; `SOURCE_NOT_RECHECKED`는 **`LOCAL_EVIDENCE_ONLY`**(시장에서 진짜 정답/공시 인증 아님); 최초 `NO_CHECKPOINT`는 **`UNCONFIGURED`**로 분리하여 미설치된 WATCH/Top-K를 외부 업체 장애로 오인하지 않는다.
- 이미 정상 혹은 오류를 관측한 모드에서 체크포인트가 **이후 사라지면** `NO_CHECKPOINT_AFTER_PRIOR_RUN`으로 별도 `DATA_FAILURE_LOCAL` 기록. 파일이 다시 일치해 `SOURCE_NOT_RECHECKED` 상태로 돌아온 경우만 **`LOCAL_ARTIFACTS_RESTORED`** 이벤트를 1회 기록. 복구는 오직 로컬 보고서·백업 상태의 정합성 회복이며 issuer PIT/실제 시장 자료/실전 알파의 복구 인증이 아니다.
- **동일 원인 반복은 중복 기록하지 않고**, 손상 이유가 달라지면 1회 새로운 오류, 나중에 같은 문제가 재발하면 다시 새 오류 이벤트. 각 mode의 전 상태/사유와 각 이벤트의 global sequence, 원장 최초기록 UTC/원본 파생 상태 SHA, 개인식별·원시가격 없는 summary를 분리 기록한다. 외부 시장 데이터·기업명/상폐/PIT DB 등 기존 원장은 읽기/쓰기 하지 않는다.

## 로컬 저장/회귀 안전

- 새 별도 영역 `output/local_failure_outbox/dry_run_alerts.sqlite` (SQLite `BEGIN IMMEDIATE` / WAL 사용 없음), `output/local_failure_outbox/dry_run_alerts_research.json`, `output/local_failure_outbox/site/index.html`. 보고서 미리보기는 일단 최근 50개 사건과 3모드 상태/원인만 표시.
- 이벤트 행은 `event_no`/SHA256 event-ID/`previous_sha256`/현재 행 SHA256으로 연결, `meta`에 event_count/head SHA와 mode_conditions 전체 SHA를 봉인한다. 변조된 보낸상태, attempt_count 비0, 전송시각 기록, 누락 이벤트/원장 상태 불일치는 다음 실행을 **중단**. 실제 발송용 API 함수 **없음**, `delivery_channel=LOCAL_PREVIEW_ONLY`, `delivery_status=DRY_RUN_NEVER_SENT`, `attempt_count=0`, `sent_at_utc=NULL` 고정. SQLite 내부 무결성은 독립 서명이나 공급자 인증이 아님.
- 최초와 중간(쓰기가 잠긴 `BEGIN IMMEDIATE` 안) operations 상태를 다시 읽어 SHA/live 파일 변경이 있으면 **트랜잭션 롤백**. 프로세스 간 별도 `batch.lock`(non-blocking flock)으로 동시 중복등록 제한; UTC 소급 최초 기록 차단. 오류 한 개 뒤 다음 이벤트 삽입 실패도 같은 트랜잭션에서 전체 롤백.
- 새 JSON/HTML 2개는 원자적 텍스트 기록. 기존 `local_backup.py`의 엄격한 allowlist에만 `dry_run_alerts.sqlite`(SQLite online consistent backup) 및 `dry_run_alerts_research.json` **두 이름** 선택 추가, 로컬 `output/local_failure_outbox_backups/dry_run_alerts_*.zip`에 SQLite+sanitized JSON+HTML **3개 파일** SHA/manifest 검증. 실패하면 `output/local_failure_outbox_control/verified.json` 완료 표시 **갱신하지 않음**, 재시도 때 같은 이유 중복 이벤트 미발행. 기존 시장 가격/재무 데이터·원본 WATCH/score ledger·개인키는 Git/알림 ZIP 모두에서 제외.

## 사용: 수동으로 로컬 재점검 (API/실전 알림 없음)

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/run_local_failure_outbox.py --project /Volumes/T5DATA/eraleader

# 맥에서 기존 정적 서버를 로컬 전용 바인드로 재사용 — 두 번째 명령은 별도 터미널
PYTHONPATH=src python3 -m eraleader serve \
  --out /Volumes/T5DATA/eraleader/output/local_failure_outbox --port 8765
# Mac 로컬: http://127.0.0.1:8765/
```

이 스크립트는 **명시적으로 실행했을 때만** 로컬 상태를 확인한다. launchd 등록/자동 주기 실행/전송 재시도 대기열·채널 선택·로그인·클라우드/모바일 접속은 아직 활성화되지 않았다. 새 대화에서도 실제 SSD의 이전 원장과 `PROJECT_STATE.md`부터 재개한다.

## 실제 Mac 로컬 실행 관찰 (개발 중, 예측성과가 아님)

- 이미 저장된 production 가격 checkpoint는 한국 2026-10-02, 미국 2026-02-26. 현재 오래된 미국 자료를 `STALE_PRICE_OBSERVATIONS`로 감지, 로컬 `DATA_FAILURE_LOCAL` 이벤트 1개를 최초 등록. 다른 WATCH/Top-K의 본 메인 예약 checkpoint 없음 → `UNCONFIGURED`, '실전 신규 리더 실패'가 아님.
- 같은 현재 시점 즉시 재실행 시 새 사건 **0개** (역사 1개 유지). ZIP/HTML/JSON 로컬 백업은 매 수동 실행마다 새로 SHA검증하며 이벤트는 중복 저장하지 않는다. 실제 자동 송신 0 / 공식 대장주 0 / 실전 적중률 N/A.
- 테스트 증거와 GitHub 최종 SHA는 `PROJECT_STATE.md` 최신 체크포인트를 따른다.

## 자동 회귀 및 남은 작업

```bash
PYTHONPATH=src python3 -m pytest tests/test_local_failure_outbox.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/local_failure_outbox.py scripts/run_local_failure_outbox.py
```

합성 시험에서 전향적 로컬 최초 실패/중복·원인 변경, 셋 중 어느 모드든 JSON·HTML/MD 변조, 기존 정상 WATCH 삭제/복구, 실제 복구 후 재발, SQLite chain/count/전송상태 오염, 비정상 시계 소급, 동시 lock, 중간 데이터 변조/트랜잭션 실패/ZIP 백업 실패-재시도, 경로 symlink, SQLite archive 새로운 위치 복원 및 정적 브라우저 HTTP200를 검증한다. 재시작 후 원장 chain은 로컬 무결성 검사를 다시 해야 한다.

**잔여**: 2_2/2_5 독립 KRX/DART/SEC 법적 issuer/share-class·상장폐지/기업행동·공시 최초 시간/PIT 전체 종목군, 5_3/5_5 실제 사전 동결 미래 코호트 수개월 후 outcome/precision·lead days. 6단계 로컬에서 발송 채널 승인·이중 원장 정합성/클라우드 로그인 테스트 및 운영 정책은 별도. D-017 API 나중, D-021 SSD 물리 분리/재연결·Mac 재부팅은 **API 후 최종 단계**, 기존 정상코드 REWRITE 금지.
