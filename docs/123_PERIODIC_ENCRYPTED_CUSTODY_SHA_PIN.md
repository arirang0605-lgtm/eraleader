# EraLeader 6_5 — 암호화 보관본 주기 무결성·독립 SHA 첫 PIN

2026-10-12. docs/113~122의 original WATCH/score/census, 원래 ZIP, AES-256-GCM 암호문, Mac witness, portable cold ZIP **기존 코드와 SHA를 재발행하지 않는다.**

## 기능

- 신규 src/eraleader/native_cold_integrity.py: 사용자가 docs/122의 package export 때 별도로 보존한 **기존 최초 SHA256 64자리**를 입력해야만 enroll 가능. 패키지 SHA뿐 아니라 전체 allowlist ZIP members·ciphertext·원래 first witness·공개 인증서 SHA를 기존 check_portable_native_custody로 검증한 후 O_EXCL 첫 PIN 생성. 패키지로부터 지금 다시 계산한 SHA를 처음 핀으로 자동 채택하지 않음.
- 별도 PIN 저장소는 기존 owner 0700 디렉터리. 0600 pins/<익명ID>_first.json + guard를 최초 기록; 최초 SHA는 변경·덮어쓰기 불가. 128패키지까지, 이름·SHA·원본 archive 중복 등록 금지. private first PIN 안에 실제 ZIP 로컬 경로가 있으므로 별도 디스크 비공개 보관, Git/Public 반출 금지.
- 독립 PIN root와 원본 T5DATA SSD가 반드시 다른 stat.st_dev, PIN root와 cold portable ZIP도 다른 stat.st_dev여야 **운영용**으로 인정. SHA root/원본/ZIP 경로 중첩·symlink·부적절한 root 권한 차단. 같은 파일시스템은 명시적인 --allow-colocated-research-only 합성실험 모드에서만, 상태 RESEARCH_ONLY_VERIFIED로만 보고한다. 파일시스템 번호의 차이는 지리적 오프사이트/외부 time notarization의 증명이 아니다.
- scan은 등록된 *모든* archive를 원래 trusted SHA로 다시 전수검증한다. VERIFIED / RESEARCH_ONLY_VERIFIED / PACKAGE_MISSING / PACKAGE_INVALID / PACKAGE_PATH_UNSAFE / PIN_MISSING / PIN_CORRUPTED / MISSED_SCAN_WINDOW. 손상은 최초 한 번 경고, 반복 중복 경고 0, 복구 RESTORED. 기본 48시간 재검사 간격 초과 기록(운영 초기값이며 최적 기준 미검증).
- PIN 저장소 genesis.json(최초 nonce·정책) + history.jsonl(ENROLL/SCAN 각각 SHA-linked append) + checkpoint.json(모든 최초 등록 PIN 목록·최종 chain SHA) + owner-only flock. 기록·정책·원래 PIN·guard·lock 유실/위조/시간 역행/축소 거부, 장애 시 조용히 PIN 재발행하지 않음. 같은 Mac 관리자 권한으로 원본과 PIN 저장소 모두 재작성되는 공격은 독립 공증 없이 막을 수 없다는 한계.
- 신규 scripts/run_native_cold_integrity.py --action enroll|scan|verify-history. scan은 원본 private key를 전혀 읽거나 복호화하지 않으며 연구용 JSON·HTML에 SHA 익명 식별자·무결성 상태만 공개. output/native_cold_integrity/site/index.html, report.json, 기존 output/site/native_cold_integrity.html 링크.
- 기존 scripts/run_local_scheduled.py에 --native-cold-pin-root [--native-cold-max-gap-hours 48] 명시 옵션만 결선. 기존 장마감 캐시 stale 오류도 보존하고 PIN 검사는 별도로 시도. --generate-plist 자동 설치는 거부, 현재 LaunchAgent·Mac 키·live messaging·API·주식 전략 변경 없음.

## 운영용 CLI 예시

아래의 세 번째 별도 cold ZIP 장치 및 PIN 보관 Mac 장치는 실제 사용자가 선정·보호 후에만 운영할 수 있다. 현재 Mac에는 시험용 T5DATA와 Mac 내부 디스크 2개뿐이므로 실제 strict 3번째 장치 시험은 불가하다.

    python3 scripts/run_native_cold_integrity.py --action enroll --project /Volumes/T5DATA/eraleader --pin-root /Mac_별도_보호된0700_SHA_폴더 --name kr-first --archive /제3장치/private/first_native_encrypted_only.zip --expected-sha256 원래_외부에_보관된_SHA256_64자

    python3 scripts/run_native_cold_integrity.py --action scan --project /Volumes/T5DATA/eraleader --pin-root /Mac_별도_보호된0700_SHA_폴더

    python3 scripts/run_native_cold_integrity.py --action verify-history --project /Volumes/T5DATA/eraleader --pin-root /Mac_별도_보호된0700_SHA_폴더

    python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --native-cold-pin-root /Mac_별도_보호된0700_SHA_폴더

## 검증 및 운영 한계

- 신규 집중 tests/test_native_cold_integrity.py + tests/test_scheduled_native_cold_integrity.py **27/27 PASS**(최종 리팩터 없는 추가 보안 수정 후 재검증), 원래 first PIN·guard 유실/훼손, ZIP/chain/header 위조, symlink, CLI strict 모드, 이미 발행한 SHA 대체 거부, 간격 경고, 보통 예약 모드 불변/과거 캐시 stale 오류에서 별도 감사.
- Mac 실제 T5DATA 대 /private/tmp 서로 다른 st_dev에서 합성 first native positive WATCH/score/census→private original ZIP→별도 Mac SHA witness→AES CMS 암호문→co-located research-only portable ZIP 및 PIN→정상/반복/변조경고/중복0/복원 RESTORED. 로컬 웹 HTTP 200, original ZIP SHA 불변. 결과는 Git ignored output/verification_logs/native_cold_integrity_mac_e2e_20261012.json.
- **실제 제3 보관 파일시스템 없음**: 운영 strict portable export 차단을 확인했을 뿐 운영용 physical offsite·독립 SHA notarization 또는 실시간 복구 성공을 인증한 것이 아니다. SHA 검증은 PRIVATE KEY를 이용한 AES-GCM tag 인증 복호화·first-WATCH/score/census replay를 수행하지 않는다. 필요시 docs/117·120의 별도 키 지정 복구 drill 수행.
- API D-017 KRX/DART/SEC 공인 PIT·issuer/class·상폐 현금 정산, 5_5 실제 prospective 미래 Top-K 자연 성숙 검증은 후반; SSD 물리 분리/재연결/재부팅 D-021 최종. API 제외 로컬 기능 구현률 **약99%(추정)**이며 공인 대장주 발견 성능과는 구별.

다음: 실제 외부 cold 장치·PIN 원장 위치를 사용자가 선정하면 운영 strict 등록/장기간 자동감시, 키 escrow·오프사이트 정책 검증. 테스트 수치·Git SHA는 PROJECT_STATE.md 하단 최신 체크포인트 참고.
