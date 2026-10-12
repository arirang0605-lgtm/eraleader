# EraLeader 6_5 — encrypted first-native ZIP SHA DRY-RUN watchdog

2026-10-12 KST. 기존 docs/113~117 first native WATCH/census, original ZIP, external first SHA witness, AES-256-GCM encrypted vault를 재작성하지 않고 재사용하는 선택형 로컬 읽기 전용 감시기. 외부 API/투자주문/실전 메시지 전송 기능 아님.

## 기능과 실패 처리

- 신규 src/eraleader/native_encrypted_watchdog.py: 1~128개의 명시적 KR/US 모델 해시 slot마다 기존 encrypted vault._verified 재사용. Mac 별도 디스크의 encrypted .cms, first receipt/guard/lock, 원래 별도 디스크 SHA witness first/guard/lock, 공개 X509 cert SHA 검증. 개인키 요청/복호화/first native 생성/ZIP 원본 재작성 0.
- 최초 VERIFIED에서 암호문 SHA, ZIP 원본 SHA, original witness SHA, certificate SHA 네 개를 독립 SHA 이력에 PIN. 이후 암호문·first receipt·guard/lock 부분/전체 소실, 인증서/원래 first witness 변조·교체, 자기일치된 다른 encrypted bundle replacement, 매번 등록된 slot을 스캔에서 빠뜨림까지 ANOMALY. 최초 원본 first witness와 암호문 모두 없으면 WAITING(정상 대기/새 경고0), first witness만 있고 ciphertext 없으면 ENCRYPTED_BACKUP_MISSING. 동일 오류 반복 경고0, 오류 종류 변경 및 정상복구 RESTORED 기록.
- output/native_encrypted_alerts: 최초 O_EXCL genesis/first event, UTC/전체 slot snapshot prev SHA→event SHA 원장, 마지막 report SHA checkpoint, flock 비밀 잠금. 최초 PIN 유실/원장 rollback/클록 역행/최초 lock 삭제/세트 분실 시 fail-closed. 완성되지 않은 검사나 쓰기 동시 실행은 성공으로 기록하지 않음.
- output/native_encrypted_alerts/site/index.html 독립 DRY-RUN HTML. 기존 output/site가 있으면 native_encrypted_dry_run.html 안전한 미러와 index.html 메뉴 링크를 중복 없이 발행해 기존 로컬 8765 서버에서 확인. 화면/JSON에는 KR/US, 익명 모델 SHA 식별자 앞12자리, HEALTH 상태/사유만 표시. 회사, 종목, 원본 경로, 개인키, 비공개 ZIP/시세, raw source 절대 경로 노출0.
- 독립 CLI: scripts/run_native_encrypted_dry_run.py --project --slot(반복) --vault-root --witness-root --recipient-cert. SHA-only이므로 private key 필요없음.
- scripts/run_local_scheduled.py 옵트인 --native-encrypted-watch-slot(반복) --native-encrypted-watch-vault-root --native-encrypted-watch-witness-root --native-encrypted-watch-cert. 4가지 정보가 모두 있어야 실행, 없으면 기존 예약 동작 그대로, 일부만 있으면 실행전 차단. 기존 main scheduler가 stale cache로 실패해도 암호화 SHA 점검만 별도 시도하고 원래 실패는 그대로 유지. --generate-plist와 함께 선택 불가, 설치된 LaunchAgent/전송 기능 변경 없음.

## 독립 실행 예시 (실제 암호화 원본이 있는 경우에만)

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_native_encrypted_dry_run.py \
      --project /Volumes/T5DATA/eraleader \
      --slot kr_원본모델SHA24자리 --slot us_원본모델SHA24자리 \
      --vault-root "$HOME/Library/Application Support/EraLeader/encrypted_native_vault" \
      --witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness" \
      --recipient-cert "$HOME/Library/Application Support/EraLeader/private_keys/native_backup_public.crt"

slot은 이전 docs/117 AES 암호화 백업 실행 출력의 hash slot을 그대로 사용. 위 경로는 예시일 뿐 상시 운영용 Mac cipher vault/공개 cert/개인키를 이 개발 중 임의로 설치하거나 생성하지 않는다.

기존 로컬 예약 실행에는 다음 네 가지 opt-in을 추가:

    --native-encrypted-watch-slot kr_원본모델SHA24자리 \
    --native-encrypted-watch-slot us_원본모델SHA24자리 \
    --native-encrypted-watch-vault-root /기존/encrypted_native_vault \
    --native-encrypted-watch-witness-root /기존/native_sha_witness \
    --native-encrypted-watch-cert /기존/native_backup_public.crt

웹 출력: 기존 output/site를 보유한 프로젝트에서 http://127.0.0.1:8765/native_encrypted_dry_run.html ; 기존 명령 python3 -m eraleader serve --out output --port 8765.

## 검증과 기술 한계

- 집중: PYTHONPATH=src python3 -m pytest -q tests/test_native_encrypted_watchdog.py tests/test_scheduled_native_encrypted_watchdog.py --tb=short. 37개 신규 합성 케이스에서 KR/US 다중 slot, 첫 SHA PIN 고정/중복·회복, root/witness 전체 유실·암호문/receipt/guard/lock/인증서 변조, 처음 미확보 WAITING, source first witness만 존재 시 BACKUP_MISSING, slot 누락/추가, 감사 체인/report rollback/clock, scheduler default/사전검증/stale 오류/설치 금지, 민감 원본 미노출 검증.
- 감시기가 검사하는 것은 ciphertext SHA + external first witness SHA + cert 지문이다. AES-GCM 태그와 원본 WATCH/score/census replay 검증은 docs/117의 명시적인 restore 단계에서만 가능하다. 개인키는 감시에 사용하지 않는다.
- 동일 Mac 사용자/관리자 하의 두 디스크는 독립 공증이나 지리적 오프사이트 백업이 아니다. 둘 모두 의도적으로 교체되고 감시 first chain까지 위조되거나 로컬 시계가 조작되면 탐지 한계 존재. 실제 시장 PIT/첫 거래소 공시 수신시각 및 장기간 prospective 성공률 검증은 별도 작업. D-017 API 연결은 마지막, D-021 SSD 실물 탈착·재연결/재부팅은 최종.
- 전체 통과 수·실제 Mac 합성 CLI·Git commit SHA는 PROJECT_STATE.md 최하단 최신 기록 참조.
