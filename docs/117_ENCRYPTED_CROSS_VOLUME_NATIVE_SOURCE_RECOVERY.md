# EraLeader 6_5 — 다른 디스크 암호화 native 최초 원본 ZIP 백업/복구

2026-10-12 KST. 기존 docs/113~116의 원본 ZIP/영수증/first SHA witness/다중 코호트 감시를 보존하고 재사용하는 로컬 opt-in 기능. 공식 PIT/실제 미래 대장주 정확도는 미검증이다.

## 실제 구현

- 신규 src/eraleader/native_encrypted_vault.py. 기존 최초 WATCH/score/features/label/census 비공개 원본 ZIP을 SSD first receipt, 외부 Mac SHA witness와 검증한 경우에 한해 다른 파일시스템에 OpenSSL CMS AES-256-GCM AuthEnvelopedData + RSA-OAEP 공개키로 암호화 복제. Python 암호화 패키지나 네트워크 설치 불필요, OpenSSL 자체 암호화 nonce/세션키 사용.
- 공개 인증서(X509) SHA, 첫 원본 ZIP SHA, 원래 외부 witness raw SHA, 암호문 SHA/크기, 시장/익명 모델 slot, 로컬 관측 시각만 0600 O_EXCL first/guard/lock에 보관. 원본 시세/증권 ID/민감 ZIP plaintext/원본 경로와 개인키는 다른 디스크 백업에 담지 않는다. Mac 암호문 vault 디렉터리 0700, ZIP/원본 변경없음.
- 별도 장치인지 stat.st_dev 검사, symlink·경로 중첩·관대한 폴더권한/first 암호문·receipt·guard·lock 부분 소실, 이전 원본 SHA/외부 first witness 변경, 최초 인증서 변경을 fail-closed. 정상 같은 슬롯/증빙 재실행은 새 ZIP/first receipt0.
- 읽기 전용 verify는 암호문 SHA와 외부 최초 SHA witness 검증만 하므로 authenticated_plaintext_verified=false. 복구는 개인키(파일 소유자 및 0600 권한 검증)로 AES-GCM 인증 복호화, 원본 최초 ZIP SHA 교차검증, 기존 restore_native_evidence_archive를 이용한 최초 WATCH/score/feature/label/census 재생 검증, 저장 ciphertext 재검증 뒤 새 디렉터리에만 복원. 원본 T5DATA에 접근하지 않고도 Mac 별도 vault + 최초 SHA witness + private key로 복구할 수 있다.
- 독립 CLI scripts/native_encrypted_original_vault.py --action backup/verify/restore. 출력에는 종목/회사/개인키/원본 경로 없음.
- scripts/run_local_scheduled.py: --native-first-encrypted-vault-root /절대/경로 + --native-first-encryption-cert /절대/경로 명시한 경우에만 이미 존재하는 --native-first-capture-plan + --native-first-private-archive + --native-first-internal-witness-root 흐름 마지막에 암호화 사본 봉인. 사용 전 공개 인증서·대상 장치·경로 충돌 사전검증. WAITING 시 외부 암호문0, 기존 launchd/무옵션 동작/실제 발송 변화0, generate-plist와 결합 금지.

## 실제 사용 시 준비 (자동 설치·운영 키 생성은 하지 않음)

운영 사용자가 반드시 Git 저장소 밖 제한된 경로에 RSA 3072비트 키쌍/인증서를 만들고 private key를 안전하게 보관해야 한다. 예시는 다음과 같다.

    KEY_DIR="$HOME/Library/Application Support/EraLeader/private_keys"
    mkdir -p "$KEY_DIR"; chmod 700 "$KEY_DIR"
    openssl req -new -x509 -newkey rsa:3072 -nodes -days 3650 \
      -subj '/CN=EraLeader Offline Recovery' \
      -keyout "$KEY_DIR/native_backup_private.pem" \
      -out "$KEY_DIR/native_backup_public.crt"
    chmod 600 "$KEY_DIR/native_backup_private.pem"

위 생성 예시는 평문 private key이므로 보안 담당자만 접근하는 제한 권한 경로와 별도의 오프라인 암호화 키 보관이 필요하다. 분실 시 암호문 복구 불가능. 현재 사용자 운영용 키 생성/설치 0.

처음 백업하기 (실제 plan 파일로 교체):

    cd /Volumes/T5DATA/eraleader
    python3 scripts/native_encrypted_original_vault.py --action backup \
      --project /Volumes/T5DATA/eraleader --plan /경로/first_native_plan.json \
      --witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness" \
      --vault-root "$HOME/Library/Application Support/EraLeader/encrypted_native_vault" \
      --recipient-cert "$KEY_DIR/native_backup_public.crt"

반환 JSON의 slot을 이후 verify/restore에서 사용한다:

    python3 scripts/native_encrypted_original_vault.py --action verify \
      --slot kr_모델SHA24자리 --witness-root /기존/sha_witness \
      --vault-root /별도디스크/encrypted_native_vault \
      --recipient-cert "$KEY_DIR/native_backup_public.crt"

    python3 scripts/native_encrypted_original_vault.py --action restore \
      --slot kr_모델SHA24자리 --witness-root /기존/sha_witness \
      --vault-root /별도디스크/encrypted_native_vault \
      --recipient-cert "$KEY_DIR/native_backup_public.crt" \
      --private-key "$KEY_DIR/native_backup_private.pem" \
      --target /완전히/새로운/비어있는/private_restored_source

예약 옵션은 이미 설정한 first capture/archive/별도 SHA witness 옵션 뒤에 아래 둘을 추가한다.

    --native-first-encrypted-vault-root /별도디스크/encrypted_native_vault \
    --native-first-encryption-cert "$KEY_DIR/native_backup_public.crt"

## 검증과 한계

- 집중: PYTHONPATH=src python3 -m pytest -q tests/test_native_encrypted_vault.py tests/test_scheduled_native_encrypted_vault.py --tb=short. Mac 실제 T5DATA vs /private/tmp 다른 파일시스템에서 합성 최초 WATCH/census 증거를 사용해 OpenSSL subprocess 암호화/최초 SHA 검증/반복 무재작성/원본 ZIP 숨김 후 복구/replay/암호문 변조 거부 시험.
- 기밀성은 개인키 관리에 의존하며 동일 Mac 관리자/OS clock 위조와 동일 장소 Mac 장치 전체 분실은 독립 공증·오프사이트 백업에 해당하지 않는다. 인증된 SHA는 실제 공인 시장 PIT·미래 발굴 성과 인증이 아니다. 키와 암호문을 클라우드로 업로드하거나 실제 시장 API 연결하지 않는다. D-017 외부 API 최종, D-021 실물 SSD 탈착·재연결·재부팅 최종.
- 전체 회귀 수, Git SHA, 실측 상세 증거는 PROJECT_STATE.md 최신 기록 참조.
