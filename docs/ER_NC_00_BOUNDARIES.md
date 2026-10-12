# ER-NC-00 — 기존 EraLeader 보존·소유권·진입경계 (2026-10-13 KST)

상태: **ER-NC-B00 BACKUP_READY=PASS** 선행 확인 후 신규 작업 수행.
기준 Git: `a24400237f6a454b788ed1802ff6859c6a7a5c66`. 원래 `main`은 별도 디렉터리에서 보존.
백업: Mac 내장장치(FileVault) + T5DATA의 별도 AES-256 쌍(본문+AppleDouble 메타); 암호키 macOS Keychain 별도 보관.
무결성: 주 아카이브 SHA `2c5709ac71ccb329...`, 메타 보관 SHA `835303858a0d159a...`, 31,150 항목 원본 매니페스트 일치, SQLite 273개 integrity_check PASS, 독립 복원 네트워크 차단 pytest EXIT0.
운영 원본 `native_first_capture.py` 미커밋 6추가·1삭제의 원래 SHA256 `6d3139f0bf7d594812fca62e77ccb1648b31e283c563898e6a7f706361ca43b6` 보존.
실제 백업 보관 경로/키 식별자는 Public Git에 올리지 않고 보호된 로컬 `ER_NC_BACKUP_RECEIPT.md/.json` 참조.

## 기존 기능 재사용/신규 개발의 경계

| 영역 | 기존 정상 자산 | ER-NC 확장 규칙 |
|---|---|---|
| KRX/DART/SEC 공식 데이터 | `official_api_capture`, `official_api_pit_bridge`, `official_kr_daily_pipeline` | 완전 재사용; 새 수집기 금지 |
| 시점·재무·종목 원장 | `offline_pit`, `pit`, `state_history` | 원본 변경 금지, 외부 이벤트는 시점별 read-only |
| 미래 WATCH·랭킹·교체 | `prospective`, `rank_score_pipeline`, `watch_rotation`, `peer_score_series`, `states` | 뉴스는 별도 근거·가설로만 링크, 자동 승격 금지 |
| 백테스트·홀드아웃 | `backtest`, `frozen_holdout`, `rotation_holdout` | 새 기록일/가용일로 확장 비교, 기존 정답 누출 금지 |
| 웹·보고·알림 | `delivery`, `cli`, 기존 DRY-RUN | NEWS_ENABLED=false 기본 유지, opt-in 추가 |
| 뉴스 기사 수집·분류·재료 확인 | 기존 EraLeader 책임 아님 | **NewsCatalystOS 독립 소유**, EraLeader는 버전 고정 export 소비만 |
| 남석관/유목민 원형 | 아직 근거 완결 미확정 | 네 개 독립 인터페이스, 미확인 규칙 NOT_READY; 김정수 제외 |

## 변경 상한·검증

- `ER-NC-01`: 새 `news_catalyst_adapter.py` + 합성 fixture/test/MD. 기존 공식 API/가격/PIT/CLI 파일은 이번 단계 **수정하지 않는다**. `NEWS_ENABLED=false`면 기존 점수·state·웹 HTML이 **바이트 단위 동일**한지 검증한다.
- 후속 단계도 뉴스 수집기·기존 WATCH를 다시 쓰지 않으며, 독립 버전 sidecar/선택 연결부터 시작한다.
- PIT: `published_at` != `first_seen_at` != `available_at`; LIVE_OBSERVED 과거 소급 금지. 권리 불명·재료 미인증은 UNKNOWN.
- `ER-NC-02~10`은 선행 단계 테스트가 PASS한 경우에만 진행한다. 실거래, 라이브 메시지, 신규 유료/브라우저 자동화, SSD 물리 조작 금지.
- 실제 미래 대장주 적중률·20거래일 운영과 공식 역사 전체시장 PIT: 미검증 / N/A.
