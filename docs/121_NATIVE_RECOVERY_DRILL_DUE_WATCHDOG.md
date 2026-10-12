# EraLeader 6_5 — 최초 native 암호화 원본 복구 리허설 만기 SHA DRY-RUN 감시

2026-10-12 KST. docs/113~120의 최초 WATCH/score/census·외부 first SHA witness·암호화 원본·실제 복구 리허설 성공/실패 SHA 이력을 **수정하지 않고 읽기만** 한다. 본 감시는 운영 안전성 검사용이며 투자 성능, 공인 PIT·법적 회사 신원, 독립 시간공증을 인증하지 않는다.

## 기능

- 신규 src/eraleader/native_recovery_due.py: 한국·미국 1~128개의 원래 모델 해시 slot을 opt-in 등록. 원래 docs/120 리허설 output/native_recovery_drills/history.jsonl + genesis/first event/checkpoint를 기존 auditor와 원본 SH-flock으로 확인. 실제 복구 AES-GCM 복호화, 개인키 읽기, ZIP/원본 가격 접근 **0**.
- 직전 **성공한** 리허설 기록시각부터 30일(사용자 선택 1~365일) 주기로 UTC 만기 산정. 7일(사용자 선택 0~due-1일) 전부터 DUE_SOON, 만기 도래 시 OVERDUE. 마지막 리허설이 실패하면 **과거 성공이 있어도 FAILED**, 최초 성공 없음은 NEVER_TESTED. 성공 기록 없이 정상 리허설이 완료됐다고 보고하지 않으며, 리허설 실패/결측을 투자 예측 정확도의 오탐으로 계산하지 않는다.
- 이전 최초 감사 시 보고된 전체 리허설 이력 길이+최종 SHA를 **다른 로컬 감시 원장에 pin**. 다음 점검에서 원래 리허설 이력 전부/일부 분실, report/chain 위조·자기일치 다른 first history 교체, 미래시각 기록이 발견되면 INVALID_EVIDENCE. 등록된 한 slot을 다음 스캔 명령에서 빼도 삭제하지 않고 MISSING_SCAN_INPUT. 경고는 첫 사건/이상 종류 전환 때만 새로 표시, 동일 사건 반복은 신규경고 0. 실제 새 유효 리허설로 HEALTHY가 되면 VERIFIED_RECOVERY_DRILL_FRESH.
- 최초 주기 정책(일수·사전경고) 및 vault/witness/cert/private scratch 실제 경로의 SHA 지문, O_EXCL genesis·first event, append-only 전체 slot별 SHA history/event+최신 report/checkpoint+private flock 보호. 임의로 주기·감시 루트를 바꿔 이전 만기 경고를 소급 없애지 못하도록 fail-closed. 관리자 권한으로 두 원장을 동시에 위조하거나 OS 시각을 조작하는 것은 독립 공증으로 검증 불가.
- output/native_recovery_due_alerts/site/index.html 및 기존 output/site/native_recovery_due.html, index 메뉴 링크(중복 방지). 표시에는 KR/US, 모델 익명 SHA prefix, DRY-RUN 상태/사유, 다음 만기 UTC만 사용. 종목/issuer/private key/원본 source·인증서 절대경로/ZIP/민감정보를 JSON/HTML/Git에 반출하지 않는다.
- 신규 scripts/run_native_recovery_due.py --action audit|verify-history. verify-history는 원래 복구 리허설의 암호화 데이터나 개인키를 요구하지 않고 이번 **만기 감시 자체 SHA 이력**을 검증한다.
- 기존 scripts/run_local_scheduled.py의 선택 --native-recovery-due + --native-recovery-due-scratch-root + --native-recovery-due-days/--native-recovery-due-warn-days 연결. 반드시 기존 --native-encrypted-watch-slot(반복) / --native-encrypted-watch-vault-root / --native-encrypted-watch-witness-root / --native-encrypted-watch-cert 네 옵션도 있어야 한다. 기존 주업무 stale 실패 시에도 별도 관찰을 시도하되 원래 실패는 유지. --generate-plist 혼용 금지, LaunchAgent 설치/실전 알림/실제 매매/외부 API 0.

## 재현 예시 (모든 위치는 실제 사용자의 기존 값으로 대체)

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_native_recovery_due.py --action audit \
      --project /Volumes/T5DATA/eraleader \
      --slot kr_실제모델SHA24자리 --slot us_실제모델SHA24자리 \
      --vault-root /원래Mac/encrypted_native_vault \
      --witness-root /원래Mac/native_sha_witness \
      --recipient-cert /원래Mac/original_public_cert.crt \
      --scratch-root /원래Mac/기존private0700_drill_scratch \
      --due-days 30 --warn-days 7

예약 opt-in은 기존 encrypted SHA watchdog의 4개 설정을 붙인 상태에서 다음만 추가한다.

    --native-recovery-due --native-recovery-due-scratch-root /원래Mac/기존private0700_drill_scratch

서버의 기존 `output/site`가 있을 때 로컬 웹:
http://127.0.0.1:8765/native_recovery_due.html

## 정확한 한계/검증

- 실제 첫 SHA 기록에 기반한 로컬 운영 리허설의 **만기 계산**이지 실전 대장주 선정 모델의 앞선 예측력 증명이 아니다. 일반 시장 공시의 독립 PIT 인증·미래 결과 데이터는 아직 수집/인증되지 않았다.
- Private key가 없이도 작동한다. DRILL 자체의 실행·복구는 docs/120의 **사용자 명시 run 옵션**에서만 수행하고, 만기 감시가 임의 복호화를 실행하지 않는다.
- 이미 발행한 안전한 첫 SHA 이력 자체를 독립기관에 공증하거나 신뢰할 수 있는 외부 시간기준으로 검증하지는 않는다. OS 시계·관리자 공동 변조 가능. 로컬 감시자와 원래 리허설 원장이 함께 물리적으로 손실되면 완전 검출 불가능.
- Python 집중: PYTHONPATH=src python3 -m pytest -q tests/test_native_recovery_due.py tests/test_scheduled_native_recovery_due.py --tb=short. Mac 실제 서로 다른 filesystem 합성 원본 암호문/첫 SHA/복구 리허설/만기 경고·웹 검증, 전체 테스트 수·Git SHA는 PROJECT_STATE.md 최하단 참고.
- D-017 외부 KRX/DART/SEC API와 2_2/2_5 역사 PIT는 사용자가 지정한 최종 단계, D-021 실물 SSD 탈착/재연결·재부팅도 최종. 최초 실전 prospect의 1~12개월 뒤 precision/FDR/lead-days는 자연 시간 경과 후 별도 평가.
