# EraLeader 6_2 / 6_5 — 한국·미국 로컬 연구 운영 상태 대시보드

2026-10-11 KST. **미래 대장주 발굴 실운영의 증거 상태를 거짓 양성 없이 표시하기 위한 로컬 읽기 전용 화면**. 기존 가격/최근 WATCH/사전 native Top-K 성숙도 3개 스케줄러는 수정/재실행하지 않고, **메인 작업 경로의 완료 체크포인트**만 읽는다. 지난 synthetic trial 폴더를 실전 운영 기록으로 자동 승격하지 않는다.

## 실제 기능

- 신규 `src/eraleader/operations_overview.py`: `audit_local_operations(project,clock)`가 메인 `output/scheduler_control/last_verified_batch.json`, `output/scheduler_watch_control/last_verified_watch_only.json`, `output/scheduler_maturity_control/last_verified_ranked_maturity_only.json`만 조회. 데이터 수집/점수 재계산/시장·공시 원천 DB 읽기 **0회**.
- 각 체크포인트의 로컬 완료 상태/UTC·dry-run/라이브 발송0/공식 leader0/독립 PIT false를 검사, 다른 폴더 백업 참조나 ZIP 심볼릭 링크·오염/크기 초과/중복 키·미래 시간/한국·미국 한쪽 누락을 차단. 최초 가격 스케줄러의 구형 선택필드 `watch_research_enabled` **부재**는 허용하되, 없는 것을 새로운 WATCH 발행으로 해석하지 않음.
- 각 모드의 **허용 백업 디렉터리** ZIP `verify_backup` SHA 검사 후, KR/US 필수 파생 보고서 inventory와 아카이브에 들어있는 모든 비-SQLite 파일을 **현재 live 보고서 바이트 SHA256·길이와 다시 대조**. ZIP만 정상이거나 HTML/MD/JSON이 수정된 상태는 `PUBLISHED_BYTES_MISMATCH` 경고. 파일 내용, 주식 코드, 원시 DB, API 키 및 archive 절대경로는 웹·JSON에 출력하지 않음.
- 3개 서로 다른 '새로움' 정책: **가격**은 KR/US 관측일을 UTC 점검 시각과 비교해 10일 초과 경고(`STALE_PRICE_OBSERVATIONS`); **WATCH**는 마지막 예약 실행이 7일 초과면 `OUTDATED_RESEARCH_SNAPSHOT`(최근 종목 등록 신선도 재확인은 안 함); **180일+ Top-K**는 오래된 사전 동결이 정상일 수 있으므로 일괄 날짜 지연 판정을 내리지 않음. 모든 정상 백업/현재 페이지 일치에도 상태는 `SOURCE_NOT_RECHECKED`; 실전 적중률/오탐/공식 대장주 0/실제 원천 PIT 인증 false 고정.
- `publish_operations_overview`: 최초 감사 + **동일 고정시각 read-only 재감사** 일치할 때에만 `output/operations/site/index.html`와 `output/operations/operations_health_research.json` 안전 atomic 생성. 검증 전후 checkpoint 변조면 원래 화면·JSON을 발행하지 않는다. 별도 운영 디렉터리여서 기존 `output/site/index.html`이나 기존 스케줄러 ZIP/원장/웹을 덮어쓰지 않는다.
- 신규 `scripts/render_local_operations.py`: 매번 명시적으로 실행하는 **일회성 로컬 연구 보고서 빌더**. launchd 신규 설치, 메일/텔레그램 전송, Cloud 배포, 주문, 외부 API 접속 없음. 이미 존재하는 `eraleader serve`가 로컬 127.0.0.1에만 바인딩되는 기능을 그대로 재사용. **새 인증/로그인이나 외부 접근 허용 기능을 만들지 않는다.**

## 실행

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/render_local_operations.py --project /Volumes/T5DATA/eraleader

# 로컬 맥 브라우저에서만 열기 (기존 서버 재사용)
PYTHONPATH=src python3 -m eraleader serve --out /Volumes/T5DATA/eraleader/output/operations --port 8765
# http://127.0.0.1:8765/
```

서버를 실행하지 않아도 HTML은 로컬 파일로 읽을 수 있다. 스케줄러가 데이터를 갱신하면 위 **렌더링 명령을 다시 실행해야** 상태가 반영된다. 이 화면은 자동 새로고침/실시간 감시기가 아니다. 웹은 localhost 전용이며 **모바일에서 외부 접속·실제 로그인/권한·HTTPS**는 아직 구현되지 않았다.

## 실제 확인된 운영값 (메인 경로, 2026-10-11)

- 현재 메인 `output/scheduler_control/last_verified_batch.json`: 한국 관측일 2026-10-02, 미국 2026-02-26. 과거 버전 호환 문제를 수정한 뒤 가격 보고서/백업 내용 SHA 일치로 검증됐으나 관측일 지연으로 `STALE_PRICE_OBSERVATIONS`.
- `output/scheduler_watch_control`, `output/scheduler_maturity_control`의 해당 **메인 예약 완료** 기록은 현재 없음: `NO_CHECKPOINT`. 예전에 실행된 `output/*trial*` 합성 실험 결과가 있어도 메인에 합치지 않는다. 실제 미래 코호트/공식 원천/적중률은 N/A.
- 화면은 로컬 보고서와 백업이 서로 일치하는지 보는 **운영 무결성 관측**이지 체크포인트가 기록한 원천 이용시각·공급자 독립 인증·현재 실제 미래 대장주 성과를 증명하는 것은 아님.

## 자동검증 / 인수조건

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_operations_overview.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/operations_overview.py scripts/render_local_operations.py
```

구체적으로 3개 모드별 파일 변조/삭제, 유효한 외부 ZIP 포인터·링크, ZIP 손상, 체크포인트 중복키/과대형/잘못된 타임존·미래시각, 실제 시장별 날짜/낡은 WATCH·구형 가격 체크포인트, 잘못된 official/success/live 값, HTML forged count/XSS, 감사 중간 변조 및 atomic 미발행, 로컬 HTML HTTP200, 독립 CLI 실행을 테스트한다. 원본 시장·실제 공급자 데이터는 **조회·변경 없이** 샘플 fixture로 수행한다.

## 남은 실제 개발

2_2/2_5 원본 KRX/DART/SEC 법적 issuer/share-class, 회사행동/상폐 현금정산/전체 시장 PIT 및 공개시각, 5_5 실제 첫 WATCH/Top-K의 미래 성숙 outcome/오탐·적중률·선행일 실증, 6단계 사용자 알림/인증·클라우드 운영은 인증 정보/데이터 공급/사용자 운영 정책이 필요. 외부 API 연동은 D-017 후순위, **D-021 물리 SSD 탈착·재부팅은 최종 단계**. 정상 코드 보존(continue only).
