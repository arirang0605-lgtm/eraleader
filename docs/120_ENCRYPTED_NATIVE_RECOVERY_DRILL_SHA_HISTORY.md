# EraLeader 6_5 — 암호화 최초 native 증거의 실제 복구 리허설·SHA 이력

2026-10-12 KST. 기존 docs/113~119 first WATCH·score/Top-K/원본 ZIP·Mac 외부 최초 SHA 증빙·AES-256-GCM 암호문·키 준비도 검사 코드는 **재작성하지 않는다**. 이 구현은 사용자 명시 실행용 **로컬 백업 복구 리허설**이고 실물 SSD 제거·재부팅·공식 PIT 인증·대장주 적중 성과 검증이 아니다.

## 실제 구현

- 신규 src/eraleader/native_recovery_drill.py: 원본 T5DATA와 **다른 stat.st_dev**에 있고 mode 0700이며 symlink가 아닌 기존 임시 디렉터리(scratch)를 명시적으로 받아, 외부 SHA witness·암호문·공개 인증서가 서로 겹치지 않고 SSD 위로 이동하지 않았는지 사전 검사. 사용자 운영 private key는 입력을 명시한 경우에만 활용하고 원문/키 경로를 연구 로그·HTML/Git에 기록하지 않는다.
- 기존 native_encrypted_vault.verify_encrypted_native_original을 재사용해 암호문 SHA·첫 외부 SHA witness·공개 X509 cert 일치를 검사하고, restore_encrypted_native_original을 호출해 **실제 OpenSSL AES-256-GCM 태그 인증 복호화 + 첫 ZIP SHA/first WATCH/원본 정량 점수/피처·라벨/census 최초 등록인덱스 SHA 재생 검증**한다. 별도 임시 하위 폴더에서만 복구하며 원본 WATCH/score/census/기존 vault/first witness/가격파일은 수정하지 않는다.
- 성공 및 실패 모두 임시 복구 폴더의 **경로 삭제 완료** 여부를 검사한 뒤, 성공/실패 원인과 digest만 결과에 저장한다. 안전하지 않거나 없는 private key, 암호문 변조, AES 인증 복호화/원본 점수·census replay 미충족, 임시경로 삭제 실패는 절대로 PASSED 판정으로 승격하지 않는다. 단, SSD에서 파일 경로 삭제는 **물리적 완전 소거/secure erase 보장과 다름**. macOS APFS/SSD 스냅샷·저널·wear leveling은 별도의 운영 개인정보 보호 설계 대상이다.
- output/native_recovery_drills: O_EXCL genesis + 첫 event 영수증, append-only prev SHA/현재 SHA/UTC·익명 market/model SHA/복구 PASS 또는 FAIL·상태 고정 코드와 original ZIP SHA·cipher SHA, 마지막 report SHA checkpoint, private flock. 이전 기록/첫 영수증/락·마지막 checkpoint 삭제·역전/변조 및 로컬 시각 역행은 fail-closed, 실패 기록의 성공으로의 소급 수정 금지. 관리자 공동 위조나 OS 로컬 시계 조작의 독립 공증은 불가능.
- 출력 HTML은 output/native_recovery_drills/site/index.html 및 기존 output/site/native_recovery_drill.html. 기존 output/site/index.html에 링크를 하나만 추가. 회사/issuer/ticker/시장 시세/원본 경로/private key/원문 복구파일은 로컬 웹/JSON/Git에 담지 않음. 상태는 인증된 복구 리허설 근거이지 공식 미래 대장주 정확도/PIT/보증 복구성공이 아님.
- 독립 CLI scripts/run_native_recovery_drill.py --action run 또는 --action verify-history. 실제 run은 private key 경로 명시 필수. 실패 이벤트도 SHA 원장에 봉인하지만 종료코드 2로 반환해 실패를 성공으로 숨기지 않는다. verify-history는 개인키·암호문 복호화 없이 기저 SHA 이력/최종 checkpoint만 감사한다. 네트워크 연결·메시지 발송·실제 launchd 설치·Mac 물리 재부팅 없음.
- 기존 run_local_scheduled.py와 다른 세션의 미커밋 키 준비도 변경 파일을 **건드리지 않았다**. 본 리허설은 기본 예약작업이 임의로 개인키로 복호화하는 일을 막기 위해 명시적 독립 CLI 실행 전용이다. 향후 운영 승인 하에 월 단위 옵트인 예약·기록 주기 관리를 연결할 수 있다.

## 실제 사용을 위한 최소 예시

운영용 첫 암호화 백업·Mac 내부 SHA witness·원래 공개 인증서와 읽기 가능한 mode 0600 소유자 전용 개인키가 필요하다. 새 키/디스크/vault를 이번 개발이 자동 생성하지 않는다.

    cd /Volumes/T5DATA/eraleader
    SCRATCH="$HOME/Library/Application Support/EraLeader/private_recovery_scratch"
    mkdir -p "$SCRATCH"; chmod 700 "$SCRATCH"

    python3 scripts/run_native_recovery_drill.py \
      --action run \
      --project /Volumes/T5DATA/eraleader \
      --slot kr_실제모델SHA24자리 \
      --vault-root /별도Mac디스크/encrypted_native_vault \
      --witness-root /별도Mac디스크/native_sha_witness \
      --recipient-cert /기존공개인증서/recipient.crt \
      --private-key /owner600/기존개인키/private.pem \
      --scratch-root "$SCRATCH"

이력만 검증할 때에는 민감 개인키 플래그를 쓰지 않는다.

    python3 scripts/run_native_recovery_drill.py \
      --action verify-history --project /Volumes/T5DATA/eraleader \
      --vault-root /별도Mac디스크/encrypted_native_vault \
      --witness-root /별도Mac디스크/native_sha_witness \
      --recipient-cert /기존공개인증서/recipient.crt \
      --scratch-root "$SCRATCH"

Mac 웹(기존 site가 있을 때): http://127.0.0.1:8765/native_recovery_drill.html

## 테스트 및 한계

- 신규 집중: PYTHONPATH=src python3 -m pytest -q tests/test_native_recovery_drill.py --tb=short.
- 합성 fixture에서 정상 first WATCH/score/census 암호화 증빙 복원·임시경로 삭제·이력 반복, 원본 비암호화 ZIP 없이 DRILL, 잘못된/key 없음/권한 0644/symlink 키, 변경된 암호문 SHA, 강제 원본 replay 검증 실패, 감사 genesis/first event/history/report/lock 변조·전체 이벤트 rollback·UTC 역행, 다른 디스크·경로중첩·scratch symlink 금지, CLI 실패 시 exit2·민감 경로 미노출.
- 실제 Mac/T5DATA 별도 st_dev 합성 E2E는 임시 테스트 인증서·private key만 사용해 실제 독립 CLI 암호문 인증 복호화/원본 first WATCH·census replay를 실행. 원본 합성 ZIP을 임시 숨겨 독립 복원 확인하고 ciphertext 손상은 실패 exit2, 복원 후 이력/HTTP200·임시작업 경로 비움 검증. 이 Mac 시험은 물리 SSD 탈착/재연결/맥 재부팅이 아니다. 키는 임시 테스트 경로에서만 생성되고 종료 후 Mac 임시 폴더 삭제.
- D-017 외부 KRX/DART/SEC API/공식 PIT 최초 수신·상폐현금/기업행동은 마지막에 연결, 5_5 실제 미래 Top-K 1~12개월 outcome 정답은 자연 시계 경과 후. D-021 실물 SSD 물리 재연결·재부팅 마지막.
- 최종 전체 pytest/공개 Git 검사·커밋 SHA는 PROJECT_STATE.md 최신 기록에서 확인. 키 사용/복구는 안전성을 고려해 기본 자동 활성화하지 않으며, 안전한 오프사이트 키 보관·DR 재해 리허설·cert rotation 정책은 후속 독립 과제.
