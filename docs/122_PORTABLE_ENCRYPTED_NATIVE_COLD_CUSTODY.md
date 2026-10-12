# EraLeader 6_5 — 첫 native 암호화 증거 휴대용 보관·외부 SHA PIN·재구성

2026-10-12 KST. docs/113~121의 WATCH/score/Top-K/민감 원본 ZIP/첫 SHA witness/AES-256-GCM 암호화 및 복구 코드를 **변경하지 않고 재사용**하는 별도 선택 기능이다.

## 구현

- 신규 src/eraleader/native_cold_custody.py: 원본 private AES-256-GCM CMS 암호문, 원래 encrypted-vault 최초 receipt+guard+lock, 원래 cross-volume SHA witness first+guard+lock, 원래 공개 X509 인증서만 **고정 7개 파일/모델+인증서**의 allowlist로 보관. 개인키, 평문 원본 ZIP, ticker/issuer/원시시세, 개별 절대 파일경로/개인키는 포함하지 않음. 다만 공개 X509 내용/첫 SHA·경로 지문은 평문으로 ZIP 내부에 존재할 수 있으므로 패키지 전체를 완전한 비밀 ZIP이라고 부르면 안 된다. ZIP 내 원래 CMS 암호문만 인증 암호화됐다.
- 첫 생성은 기존 _verified로 암호문·원래 SHA witness·인증서 바이트 PIN 검증 → O_NOFOLLOW streaming 암호문 복제 → 멤버 allowlist·SHA/길이/정상파일모드 전수검증 → 원본 source 재검증 → O_EXCL/0600 최종 package ZIP 기록, 덮어쓰기/부분 오류 자동 재시도 금지. KR/US 1~16 모델 slot 명시 등록 가능.
- 운영 보관 경로는 기존 T5DATA SSD와 기존 Mac 암호문 vault 및 SHA witness에서 **세 번째로 다른 stat.st_dev 파일시스템**이 기본 필수다. stat.st_dev가 다르다는 것은 별도 파일시스템 확인이지 지리적 오프사이트/실물 디스크 독립 공증이 아니다. 세 번째 파일시스템이 없다면 기본 export는 거부. 오직 합성 연구용 --allow-colocated-research-only 명시적 선택 시 같은 Mac 파일시스템에서도 시험용 PACKAGE를 만들지만 third_filesystem_st_dev_distinct=false, offsite_geography_attested=false로 강제 표시.
- export 출력 package_sha256 원문을 사용자 독립 장소에 별도 안전 보관할 것을 요구. verify와 restore는 모두 **원래 외부에 별도 보관된 SHA-256 64자리 전체 입력 필수**: 패키지 전체 SHA→모든 멤버 SHA/길이/압축여부/위험경로·symlink/명세 중복·누락 거부→새 전용 temp 위치에서 기존 first encrypted vault verifier로 ZIP 원래 first SHA/공개 인증서 교차검증. 파일 내용/첫 receipt 임의 재봉인은 fail-closed.
- restore는 인증된 encrypted .cms, 원래 first SHA witness, 원래 receipt/guard/lock, 공개 인증서, manifest를 **사용자가 명시한 완전히 새 보호된 0700 부모 아래**에만 복제한다. 원래 project/SSD/vault가 분실됐어도 package+외부 SHA PIN으로 검증된 암호문을 재구성할 수 있다. 이 단계는 PRIVATE KEY를 요구하거나 평문 AES-GCM 복호화를 하지 않는다. 그 이후 원래 first WATCH/score/census 실제 복구는 docs/117의 명시적 복구 명령+원래 개인키로만 수행.
- 독립 CLI scripts/native_cold_custody.py --action export|verify|restore. 출시 시 암호문 파일만 로컬로 생성, 외부 API 호출/실전 메시지/주문·LaunchAgent 배포/사용자 개인키 자동생성0. 기존 정상 원본 코드는 건드리지 않음.

## 예시 (실제 세 번째 별도 파일시스템 사용자 준비 필요)

    cd /Volumes/T5DATA/eraleader
    python3 scripts/native_cold_custody.py --action export \
      --project /Volumes/T5DATA/eraleader \
      --slot kr_원래모델SHA24자리 --slot us_원래모델SHA24자리 \
      --vault-root /Mac원래/private_encrypted_vault \
      --witness-root /Mac원래/first_sha_witness \
      --recipient-cert /Mac원래/original_public.crt \
      --archive /제3별도파일시스템/보호된0700폴더/first_native_encrypted_only.zip

반드시 반환된 package_sha256 전체 SHA 문자열을 **패키지 밖 독립적인 안전한 장소**에 기록할 것. 기존 인증된 SHA 없이 새로 계산한 ZIP digest만 믿는 복원은 신뢰할 수 있는 첫 증빙이 아니다.

    python3 scripts/native_cold_custody.py --action verify \
      --archive /제3별도파일시스템/보호된0700폴더/first_native_encrypted_only.zip \
      --expected-sha256 따로보관한SHA64자리

    python3 scripts/native_cold_custody.py --action restore \
      --archive /제3별도파일시스템/보호된0700폴더/first_native_encrypted_only.zip \
      --expected-sha256 따로보관한SHA64자리 \
      --target /기존보호된0700부모/새로만드는_reconstructed_encrypted_evidence

## 실제 시험·한계

- 집중 tests/test_native_cold_custody.py: 원래 ZIP/키 없이 encrypted-only export·SHA pin 검증·새 vault/witness 복구 → 기존 키로 AES-GCM 원본 first WATCH·score/census index replay, KR+US 여러 모델, 암호문/인증서/first SHA 위조/분실, ZIP 멤버·경로 위험·SHA mismatch/무단 덮어쓰기 차단. 출처 first PIN과 별개인 임의 ZIP SHA는 독립 서명·공증이 아니다.
- 실제 Mac/T5DATA 합성 E2E: T5DATA SSD와 Mac /private/tmp의 서로 다른 stat.st_dev 확인, **3번째 별도 스토리지 없는 상태라 strict export는 거부**. 오직 연구용 colocated 플래그로 두 시장 패키지 생성→원래 Mac vault/witness를 논리적으로 숨김→독립 CLI 검증/새 위치 복원→기존 복구키로 AES-GCM first WATCH/score/census 재생 PASS. 임시 시험 패키지·키 삭제, 원본 비공개 ZIP SHA 보존. 실물 오프사이트 보관·물리 재연결/재부팅 인증 아님.
- 사용자 운영용 외부 세 번째 볼륨 준비/설치, 안전한 X509 개인키 escrow·키 회전 및 독립 시간공증은 최종 운영과제. D-017 외부 KRX/DART/SEC PIT 연동 마지막, D-021 실물 SSD 물리 재연결·재부팅 맨 마지막. 진짜 prospect의 1~12개월 미래 성능/FDR/lead-days는 시간경과 후에만 검증. 최종 테스트/커밋 SHA PROJECT_STATE 최신 기록 참조.
