# EraLeader 6_5 — 다중 코호트 native 첫 ZIP/SHA 자동 감시 및 DRY-RUN 대시보드

2026-10-12 KST. 기존 docs/113~115의 최초 native WATCH/score/census, 비공개 원본 ZIP, SSD 첫 SHA receipt, Mac 별도 디스크 SHA witness를 **재작성하지 않고 재사용**하는 선택형 로컬 운영 감사다. 공식 PIT·미래 대장주 정확도 인증과는 별개다.

## 구현

- 신규 src/eraleader/native_sha_watchdog.py: 1~128개의 명시적 KR/US 최초 native plan 목록을 원래 verify_native_sha_witness()로 다시 확인. 원본 ZIP, 내부 receipt/guard/lock, 별도 파일시스템 SHA first/guard/lock을 검사. 표시에는 시장, 경로 SHA 익명 ID, 상태/사유만 사용; 종목명·issuer·raw 가격·private ZIP·원본 경로는 로컬 HTML/JSON 및 별도 디스크로 복사하지 않음.
- 첫 VERIFIED에 관측한 ZIP SHA와 외부 witness SHA를 append-only SHA chain으로 첫 고정. 같은 plan의 SHA 자기일치 교체·원본 분실/삭제·부분 손상·symlink/위변조, 전날 등록된 plan을 스캔 목록에서 빼먹은 경우까지 ANOMALY/DRY-RUN 경고. 새 코호트 점진 등록 가능. 처음부터 ZIP이 없는 미성숙 plan은 WAITING, 경고0. 경고 중복은 상태 전환 시에만 새로 발생하고 복구 시 RESTORED 기록.
- 감시 파일: output/native_sha_alerts 아래 genesis.json, first_event.json, history.jsonl (prev SHA/현재 SHA 사슬), report.json (체크포인트), .checks.lock, site/index.html. 최초 기록 O_EXCL+fsync, 후속 파일 손상·시각 역행·역사 로그 롤백은 자동 재봉인 금지, fail-closed. 원본 ZIP/SSD receipt/외부 SHA는 감시자가 수정하지 않는다.
- 로컬 API 서버의 문서 루트가 output/site이므로 기존 site가 있으면 민감자료를 제거한 output/site/native_sha_dry_run.html 파일을 별도 발행하고 site/index.html의 DRY-RUN 링크를 중복 없이 등록. 원본 감시 독립 화면도 output/native_sha_alerts/site/index.html에 발행한다.
- 독립 진입점 scripts/run_native_sha_dry_run.py --project ... --plan ... (반복) --witness-root ... . 예약 opt-in scripts/run_local_scheduled.py --native-sha-dry-run-plan ... (반복) --native-sha-dry-run-witness-root ... . 후자는 일반 배치 실행이 신선도 차단으로 실패해도 감시를 시도하고 원래 오류를 감추지 않는다. 새 감시 옵션만 사용하면 WATCH/ZIP/witness를 새로 만들지 않는다. 기존 사용 중인 launchd, 자동 설치, 실전 메시지/API 전송은 변경 0.

## 재현 명령 (경로는 실제 존재하는 plan으로 바꿀 것)

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_native_sha_dry_run.py --project /Volumes/T5DATA/eraleader \
      --plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
      --plan /Volumes/T5DATA/eraleader/output/native/us_first_plan.json \
      --witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness"

    python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader \
      --native-sha-dry-run-plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
      --native-sha-dry-run-plan /Volumes/T5DATA/eraleader/output/native/us_first_plan.json \
      --native-sha-dry-run-witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness"

기존 first capture를 동시에 수행하려면 그에 따른 별개 --native-first-capture-plan / --native-first-private-archive / --native-first-internal-witness-root를 함께 설정. --generate-plist와 감시 옵션 동시 실행 거부. 로컬 서버: python3 -m eraleader serve --out output --port 8765 실행 후 http://127.0.0.1:8765/native_sha_dry_run.html 에서 감시 화면 확인(기존 output/site 있을 때).

## 실제 시험 및 한계

- 집중 명령: PYTHONPATH=src python3 -m pytest -q tests/test_native_sha_watchdog.py tests/test_scheduled_native_sha_watchdog.py --tb=short. 합성 KR/US 첫 코호트 여러 개, 최초 SHA 고정, append 후 event SHA 검증, ZIP/SSD/external 원시 SHA 변조, 전체 witness 분실, plan 삭제/누락, 동일 경고 중복 억제, 정상복구, 감시원장/lock 손상·보고 rollback, XSS/개별 경로 비공개 및 예약 옵트인 기본 보호 검사.
- 최초 시험에서 전체 감시 lock이 삭제돼도 다시 생성되는 결함 1건을 발견하여 최초 genesis/history 존재 시 lock 분실을 차단하고 집중 재시험 PASS.
- 동일 Mac 관리자에 의한 두 디스크/감시이력 동시 공모교체, 최초 감시 전 자료 소실, OS clock 조작은 독립 공증이 아니어서 보장하지 않는다. 비암호화 원본 ZIP의 독립 외부 백업·오프사이트 타임스탬프/추후 만기 outcome 검증은 아직 미구현. API D-017 마지막, 물리 SSD 탈착·재연결/재부팅 D-021 마지막. 정확한 전체 pytest 수 및 Git SHA는 PROJECT_STATE.md 최신 항목 참조.

## 실제 Mac/T5DATA 오프라인 E2E (2026-10-12)

- 원격 Mac/T5DATA 상의 실제 서로 다른 stat.st_dev (원본 T5DATA vs Mac /private/tmp 임시 비밀 SHA witness) 확인. 합성 KR/US first WATCH/score 및 private ZIP 생성 뒤 별도 디스크 최초 PIN 2건 봉인하고, 실제 subprocess 독립 CLI를 총 5번 실행.
- 최초 정상 신규경고0, 반복0, 임시 Mac witness guard 1개 분리 신규경고1, 같은 손상 반복0, 원본 bytes 복구 후 RESTORED1. 기존 로컬 사이트 index 링크 발행과 HTTP localhost 200 확인, 원래 fixture SHA 변경0, 외부 API/메시지/공식 leader0.
- 증거 로그는 Git ignored output/verification_logs/native_sha_watchdog_mac_e2e_20261012.json. 임시 외부 witness 폴더는 해당 E2E 후 제거했으며 상시 운영용 Mac witness를 설치한 것은 아님. 독립 공인 PIT/실전 신호 성능 데이터 아님.
