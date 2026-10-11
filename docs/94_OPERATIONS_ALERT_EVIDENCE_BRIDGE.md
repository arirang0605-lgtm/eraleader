# EraLeader 6_2 / 6_5 — 검증된 장애 원장을 운영 대시보드에 읽기 전용 결합

2026-10-11 KST. 기존 `operations_overview.py`(예약 완료 체크포인트 3종 검증)와 `local_failure_outbox.py`(로컬 오류/로컬 아티팩트 복구 dry-run SQLite SHA 원장)는 **그대로 보존**한다. 신규 `operations_alert_bridge.py`에서 두 출력의 증거가 모두 일치하는 경우에만 오류 이벤트를 표시한다.

## 신규 기능 및 기존 코드 보호

- 신규 `scripts/render_local_operations.py --include-local-outbox`: 명시 실행 시에만 신규 `output/operations_alerts/operations_alerts_research.json`, `output/operations_alerts/site/index.html` 두 파생 파일 생성. 기존 플래그 없는 `render_local_operations.py`의 `output/operations` 보고서는 변경하지 않는다.
- 메인 price/WATCH/native maturity 3모드 체크포인트는 기존 `audit_local_operations`로 **읽기 전용** 감사. 별도 로컬 장애 이력은 `output/local_failure_outbox_control/verified.json` 체크포인트, `output/local_failure_outbox_backups/dry_run_alerts_*.zip`, `output/local_failure_outbox/dry_run_alerts.sqlite` 및 JSON/HTML만 읽는다. 사용자 후보/재무/시세 원시 자료·키·외부 API/실제 메일·텔레그램은 액세스하지 않는다.
- 백업 경로가 반드시 승인된 `local_failure_outbox_backups`여야 하고, ZIP에는 승인된 파생 SQLite/JSON/HTML **정확히 3개 파일**이 존재해야 한다. `verify_backup` manifest 해시/크기 확인→live JSON/HTML 바이트 동일→ZIP 내 SQLite를 **메모리에서 역직렬화**하고 전체 사건 SHA 체인/모드 상태 봉인 재검증→현 live SQLite 체인과 대조→`_report`로 JSON 재작성 결과 동일→고정 HTML renderer 바이트 재현 일치→완료 체크포인트 count/무발송/미인증 claims 대조한다. 파생 JSON의 과장된 이벤트 건수/실전 정확도, 검증 완료 행의 허위 전달/실제 리더/외부 경로·심볼릭 링크를 거부한다.
- 기록 없음→`OUTBOX_NOT_CONFIGURED`; 원장/파일/ZIP 변조→`OUTBOX_UNVERIFIED` + 건수·활성 장애수 **N/A**; 검증된 과거 스냅샷과 현재 예약 증거 SHA mismatch→`OUTBOX_STALE_VS_SCHEDULER` **재점검 필요**, 완전 일치→`VERIFIED_LOCAL_SNAPSHOT`로 분리한다. **ZIP이 정합해도 원천 PIT 인증 아님**. 날짜 변화로 과거 스냅샷 비교가 stale 되는 것은 의도한 안전한 상태이며 실제 공급자 장애로 오인하지 않는다.
- 읽기 전용 최초 + 최종 두 번 동일 시각 감사가 달라지면 새 화면/JSON을 발행하지 않는다. 기존 SQLite 또는 3개 예약 원장, live 보고서/ZIP, 원시 시장캐시, 장기 백테스트·다른 프로젝트 코드를 변경하지 않는다.
- 화면은 이벤트 최대 최근 10건, 상태/원인 코드 및 UTC만 escape하여 표시. `live_notifications_sent=0`, `external_api_calls=0`, `real_precision_at_k=null`, `official_leader_promotions=0`를 유지. 운영 화면 접근은 여전히 **맥 localhost 전용**으로, 사용자 로그인이 가능한 공개 웹페이지가 아니다.

## 실행

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/render_local_operations.py --project /Volumes/T5DATA/eraleader --include-local-outbox

# Mac 브라우저에서만, 별도 터미널. 기존 eraleader serve 재사용:
PYTHONPATH=src python3 -m eraleader serve --out /Volumes/T5DATA/eraleader/output/operations_alerts --port 8765
# http://127.0.0.1:8765/
```

이 명령은 오류 원장을 새로 갱신하지 않으며 기존 로컬 연구 장애 기록을 확인·표시만 한다. 데이터 갱신 후에는 `scripts/run_local_scheduled.py --local-outbox-dry-run`처럼 **사용자가 명시적으로** 예약 로컬 점검을 수행해야 한다. `launchctl load`/daemon 설치, 백그라운드 모니터링/외부 데이터 수집, SSD 물리 분리/재부팅 0회.

## 테스트

```bash
PYTHONPATH=src python3 -m pytest tests/test_operations_alert_bridge.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/operations_alert_bridge.py scripts/render_local_operations.py
```

회귀: 원장 미설정/변조·ZIP/HTML/JSON/SQLite 위조·동일 SHA manifest 재계산에도 잘못된 archive SQLite 차단, 체크포인트 외부 redirect/symlink, 가짜 실전 전송/리더, 현재 배치 SHA 달라진 stale 분리, 초기↔최종 감사 TOCTOU, 기존 메인 화면 원본 bytes 무변경 및 CLI 이전 방식 호환. `TDD` 최초 모듈 import 실패(RED), 코드 추가 후 새 회귀 통과(GREEN).

**미완료**: KRX/DART/SEC 실제 독립 issuer/share class/상폐 현금/기업행동/공시 PIT 원천, 5_5 실제 미래 첫 WATCH/Top-K 만기 outcome·false discoveries·precision/lead days, 로컬 dashboard 로그인/실전 알림·API 연결. 공식 leader 0, 실전 skill N/A. D-017 API 연결은 뒤, D-021 실제 SSD 탈착·재연결/재부팅은 마지막.

## 2026-10-11 Mac 실측 최종

- 시작 main/origin `8668e9598600584b64c970d8158f25d9695e6afd`, clean. 신규 TDD 첫 missing module ImportError RED 후 focused 21/21 PASS. 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1432/1432 PASS exit0**(기존1411+21), collect-only 1432, `python3 scripts/check_handoff.py` 30 IDs/40 필수 PASS, Python py_compile/diffcheck PASS.
- 실제 원장/가격 메인 운영 자료를 Mac CLI에서 read-only 실행: `alert_evidence_state=VERIFIED_LOCAL_SNAPSHOT`, verified local incident 1, official leader0/live message0/API0, 현재 실제 예측 성능 N/A. 별도 site/JSON **2개** 원자 발행. 예약 체크포인트 + outbox DB/control/report 네 원본 파일의 SHA가 시작/종료 **동일**.
- 기존 `eraleader serve --out .../output/operations_alerts --port <로컬 임시 포트>` 실제 실행, `127.0.0.1` HTTP200·DATA_FAILURE_LOCAL/N/A 문구 응답 확인 후 즉시 서버 종료. 실전 라이브 채널 연결/재부팅/물리 SSD 탈착·API 호출 0.
