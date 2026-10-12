# EraLeader 6_5 — 암호화 first-native 원본 복구 준비도: 공개 인증서 만료와 키 일치 DRY-RUN

2026-10-12 KST. 기존 docs/113~118 원본 첫 WATCH·Top-K/ZIP/SSD 첫 SHA/Mac 별도 SHA witness/암호화 ZIP 및 다중 감시를 정상 작동 그대로 재사용한다. **기존 공개 X509 인증서가 만료되어도 원래 AES-GCM 암호문은 개인키로 복호화 가능해야 한다**는 복구 핵심 조건을 보강한다. 이미 발행된 신호가 실제 대장주였다는 공식 PIT/예측 정확도 증명이 아니다.

## 기존 결함 보완 (중요)

- src/eraleader/native_encrypted_vault.py의 _cert(..., require_current=True) 분리: **신규 암호화 최초 발행**은 유효기간 내 X509 요구. 이미 발행된 ZIP에 대한 read-only SHA verify, 반복 first receipt 확인, 원래 최초 ZIP 암호문의 **복구는 인증서 만료만을 이유로 거부하지 않는다**.
- 만료된 X509라도 원래 first receipt에 봉인된 **정확히 동일한 인증서 바이트 SHA**와 최초 Mac witness ZIP SHA/cipher SHA/guard/lock은 계속 필요하다. RESTORE는 별도의 모드0600 개인키와 OpenSSL AES-256-GCM 인증 + 기존 first WATCH/numeric score/features/label/census 원장을 새로운 대상 폴더에만 재생 검증한다. 만료를 우회해 임의 다른 인증서·키로 first-write를 바꾸는 기능은 없다.
- 시험은 실제 과거 시각 발행된 **합성 만료 X509**를 OpenSSL ca로 구성하여 신규 발행 유효기간 검사 실패/과거 인증서 구조 및 SHA 검사 성공을 구별하며, 별도 미래 시각 시뮬레이션에서 기존 암호문 SHA 검증·복원이 계속 작동하는지 검증한다.

## 신규 6_5 운영 진단

- src/eraleader/native_recovery_readiness.py: 기존 encrypted native vault verifier를 사용해 선택 1~128개 KR/US 모델의 원래 암호문 ciphertext SHA/최초 외부 SHA witness를 **읽기만** 재검증한다. 공개 X509의 실제 notBefore/notAfter GMT를 로컬 OpenSSL로 확인하여 CURRENT/EXPIRING_FOR_NEW_BACKUPS/EXPIRED_FOR_NEW_BACKUPS/NOT_YET_VALID/INVALID_OR_MISSING 구분. 경고 사전기간 기본 90일(1~365 선택), 로컬 OS 시계는 외부 공증 아님.
- 사용자가 명시한 private key가 있을 경우 기존 원본 복구키 소유자 모드0600 및 안전 경로를 확인하고, 키에서 **공개 부분(SPKI DER)만 임시 메모리로 도출**해 현재 암호화 X509 공개키와 일치 여부를 판단. 개인키 원문·비밀번호·공개키 DER/원본 ZIP·종목/개별 issuer ID·민감 경로는 화면/JSON/Git에 절대 출력하지 않는다. 비밀키가 없거나 잘못됐거나 보호되지 않았으면 상태를 NOT_CONFIGURED/UNSAFE/MISMATCH로 유지해 복구 성공으로 오인하지 않는다. 암호화된 키/패스프레이즈를 비대화형으로 해독하지 않고 별도 사람 운영 절차 대상으로 남긴다.
- 리포트 상태가 PUBLIC_KEY_MATCHED_NO_RECOVERY_DRILL이어도 **실제 AES-GCM 복호화·ZIP 복구 드릴을 실행했다는 주장이 아니다**. cryptographic keypair match는 실제 재해 복구 성공에 대한 충분조건이 아니다. 인증서 만료는 **새** 백업에 장애가 되지만 과거 암호화 원본이 지워지는 것과는 다르다.
- output/native_recovery_readiness/report.json + index.html, 기존 output/site가 있으면 native_recovery_readiness.html과 index 링크 안전/원자적 발행. 시장/익명 SHA ID·유효성 상태·검증된 저장 증빙 수·경고만 노출. 과거 first archive/receipt/외부 SHA/cipher를 **절대 재작성하지 않는다**.
- 독립 CLI scripts/run_native_recovery_readiness.py, 예약 scripts/run_local_scheduled.py --native-recovery-readiness [--native-recovery-check-key /절대/600/key] [--native-recovery-warn-days 90] 를 기존 필수 --native-encrypted-watch-slot(반복)/--native-encrypted-watch-vault-root/--native-encrypted-watch-witness-root/--native-encrypted-watch-cert 옵션이 있을 때만 활성. 주 배치 stale 실패에서도 독립 상태 관찰을 시도하며 원래 오류는 유지. 기본 예약/설치된 LaunchAgent/실전 메시지/API/SSD 물리 탈착·재연결/재부팅 변경0.

## 사용 예

실제 시장 모델 슬롯, Mac 별도 디스크 암호화 원본·first SHA witness 및 공개인증서를 사용한다. 아래는 옵션의 예시이며 실제 경로를 발명한 설치 명령이 아니다.

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_native_recovery_readiness.py \
       --project /Volumes/T5DATA/eraleader \
       --slot kr_현재모델SHA24자리 --slot us_현재모델SHA24자리 \
       --vault-root /별도디스크/encrypted_native_vault \
       --witness-root /별도디스크/native_sha_witness \
       --recipient-cert /Git외부경로/recipient_public.crt \
       --private-key /Git외부경로/owner600/recovery_private.pem \
       --warn-days 90

--private-key 미지정 시 읽기 전용 ciphertext/X509 검사만 하며 키 복구 준비는 미검증으로 표시한다. 키/폴더를 자동으로 생성하지 않으며, Git 공개 저장소에는 키·원시 시세·민감 ZIP이 절대 커밋되지 않는다. 키를 분실했다면 공개키 일치 검사를 통과할 수 없고, 실제 복구도 불가능하다.

## 검증 및 미완료

- 집중: PYTHONPATH=src python3 -m pytest -q tests/test_native_recovery_readiness.py tests/test_scheduled_native_recovery_readiness.py --tb=short.
- 검증 범위: Mac 로컬 RSA cert/key 공개 부분 일치, 잘못된·world-readable/프로젝트 내부 위험 키 차단, 공개 cert 만료 경고·실제 과거 만료 X509 거부·기존 암호문 검증 및 복구 유지, 여러 감시 슬롯 기원 SHA 검증, JSON/HTML 키/민감 경로 비공개, 기본 scheduler·옵트인·stale 오류 보존, plist 자동 설치 금지.
- 이 read-only readiness는 비밀키가 안전하게 **오프사이트** 보관된 증명이나 실제 DR drill 기록이 아니다. 외부 공인 PIT·1~12개월 prospective 리더 성능은 API 연동 및 자연 경과 후 확인. 외부 API D-017 최종, 실제 SSD 물리 분리·재부팅 D-021 최종. 마지막 전체 pytest·GitHub SHA는 PROJECT_STATE.md 하단 기록을 우선한다.
