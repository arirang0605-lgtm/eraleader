# EraLeader 6_5 — 공급자 품질 약화 · SHA 무결성 이상 로컬 DRY-RUN 경고

> 2026-10-12 KST. **기존 코드 CONTINUE**. `docs/104_PROVIDER_QUALITY_HISTORY_LOCAL_FIRST_WRITE.md`의 실제 최초 기록 SHA 이력을 READ-ONLY로 감시한다. 외부 API·발송·매매·공식 대장주 승격은 **모두 0**. 이 문서와 테스트는 로컬 합성 입력 검증이며 공인 시장 원천/실전 예측 검증이 아니다.

## 작동 경로

- 신규 `src/eraleader/provider_quality_watchdog.py`: 기존 `provider_quality_history`의 동일 파일잠금으로 SQLite+최초 marker를 읽고, 원래 모듈의 **전체 사건 SHA/원문·순서/OS 기록시각** 감사를 재사용. 파생 HTML/캐시를 믿지 않으며 원본 DB를 **쓰기/복원/삭제하지 않는다**.
- 마지막 감시 후 생긴 모든 KR/US 사건을 순회하여 **WATCH 허용→보류** (첫 관찰부터 보류도 포함)와 **원본 PIN·법인클래스 검증 강도 약화**를 구별한다. 게이트의 `REVISED_SAME_DECISION_REVIEW`/후행 재평가에도 이전 사건과 직접 비교해 악화 숨김을 차단. 중간 악화 후 회복된 경우에도 **새로 관측한 악화 사건을 빠뜨리지 않는다**.
- 원래 이력의 SHA 체인 오류, marker 분실·변형, DB 단독/동시 삭제, 처음 확인한 원장보다 **자기 일관성 있게 롤백한 과거 원장**, 최초 marker를 새로 발행한 원장 재생성, 원장 시각이 지금보다 미래인 상황을 `INTEGRITY_ANOMALY`로 판정. 원래 자료를 자동 '수리'하거나 근거 없는 성공으로 바꾸지 않는다. 확인된 마지막 **원본 prefix/marker SHA**는 별도 체크포인트 원장에 남겨 후일 비교한다.
- 별도 `output/provider_quality_alerts/provider_quality_watchdog.sqlite` + O_EXCL `provider_quality_watchdog_genesis.json`: 전체 순번/UTC 기록/검사 조건/마지막 신뢰 원본 SHA·수량/경고 종류/발송0을 SHA 연결·SQLite meta anchor로 봉인. 같은 이력/같은 장애 재실행은 체크포인트와 **신규 경고 중복 0**, 문제가 해결될 때 `LOCAL_HISTORY_RESTORED`는 원본 prefix가 신뢰 기준과 호환되는 경우에만 '로컬 파일 복구'로 기록한다. 개별 감시 원장의 유실·손상·공증 위조도 차단한다.
- 미설치 상태에서 이력 DB+marker가 모두 없으면 `NOT_CONFIGURED`: 공급자 오류를 날조하지 않음. 실제로 **한 번 확인했던** 이력의 두 파일이 모두 사라지면 독립 감시 체크포인트에서 오류 감지.
- DRY-RUN 경고 종류: `QUALITY_EVIDENCE_WEAKENED_LOCAL`, `WATCH_GATE_BLOCKED_LOCAL`, `LOCAL_HISTORY_SHA_INTEGRITY_ANOMALY`, `LOCAL_HISTORY_RESTORED`. 이름처럼 로컬 미발송 운영 경고이며 실전 상품 매수/시장/기업 판단이 아니다.
- 산출물: 안전 집계 JSON `output/provider_quality_alerts/provider_quality_alerts_research.json`; 정적 화면 `output/provider_quality_alerts/site/index.html`. ZIP은 별도 `output/provider_quality_alerts_backups/quality_alerts_*.zip`: 승인된 원장 SQLite/최초 marker/JSON/HTML **정확히 4파생**만 SQLite 온라인 백업, manifest SHA 검증/신규 디렉터리 복구 테스트. 이력 공급자 원본, CIK·법인코드·개인키·원본 시세·실전 WATCH/Top-K·유료 자료는 ZIP/Git 제외.

## 예약 배치 및 수동 실행

기존 스케줄러 진입점 `scripts/run_local_scheduled.py`에 **선택** `--provider-quality-dry-run` 연결. `--local-outbox-dry-run`과 독립/동시 적용 가능하며, 일반 무옵션 가격/WATCH/Top-K 배치 동작은 불변. 예약 연구의 정상 종료/기존 안전한 `SKIPPED_STALE_CACHE` 이후 감시; 예외 종료 시에도 감시 기록을 시도하되 기존 실패를 성공으로 덮어쓰지 않는다. 백업 미검증/발송 주장/중복 실행은 성공 반환 금지. `--generate-plist`와 선택 DRY-RUN 경고 동시 사용을 막아 **자동 LaunchAgent 설치/변경을 하지 않는다**.

```bash
cd /Volumes/T5DATA/eraleader
# 예약 스크립트의 품질 SHA 감시 선택(기존 stale 데이터 보류 유지)
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --provider-quality-dry-run
# 운영용 별도 수동 로컬 점검(데이터 수집/배치 없이)
python3 scripts/run_provider_quality_dry_run.py --project /Volumes/T5DATA/eraleader
# 기존 scheduler 로컬 DATA_FAILURE 사건 원장도 동시 연결할 때
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --local-outbox-dry-run --provider-quality-dry-run

PYTHONPATH=src python3 -m pytest -q tests/test_provider_quality_watchdog.py tests/test_provider_quality_history.py tests/test_scheduled_failure_outbox_bridge.py tests/test_local_backup.py --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
```

> **주의:** `--provider-quality-dry-run`는 명시 선택 시만 수행하며 현재 설치된 LaunchAgent/실전 메시지 채널을 자동 변경하지 않는다. 기본 스케줄러에 위 옵션이 없으면 자동 경고가 발행되는 것은 아니다. API·배포 후 운영 정책에 따라 별도 활성화한다. 시세·PIT 독립 인증 전 실전 경고 전달을 활성화하지 않는다.

## 검증 범위와 엄격한 한계

합성 KR/US 원본 판정/복제·수정·삭제·자기 일관적 롤백·독립 원장 훼손·과거 OS 시각 재실행·고의 위조 발송 주장·중복 실행·ZIP 복구/서빙을 포함한다. 바깥 공급자 발행시간과 컴퓨터 시스템시계, 원장과 감시 원장 **둘을 함께 교체하는 관리자 공격**은 단일 장비 SHA만으로 공증할 수 없다. 외부 신원·원천 PIT·상폐 현금·독립 미래 결과 실증 및 실제 SSD 물리분리/재부팅은 각각 D-017/D-021에 따라 마지막 단계까지 미룸. 공식 확정 대장주 **0**, 실전 precision/오탐률 **N/A**, 외부 API **0**, 라이브 발송 **0**.
