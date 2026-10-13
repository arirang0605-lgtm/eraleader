# 138 — 6_5 DART CFS 최초등록 이력 SQLite 증분 암호화 백업·독립 복원

**개발일:** 2026-10-13 KST · 개발 ID: **6_5 (백업/DR)**, 2_2·3_1 연구 최초 영수증 보호
**기준 브랜치:** `feature/core-official-factor-coverage-20261013` / 이전 `831e7c703b81c8107f89cbd8eb664dddad1b2cef`.
**원칙:** 기존 ERA B00 원본 백업/Keychain/API 설정·실행코드 무재작성. 원본 Mac CFS ledger first SHA 3건과 T5DATA 공식 KRX/DART 원시자료는 읽기 전용, 암호문만 SSD와 Mac 내부에 별도 기록.

## 새 코드 및 로컬 암호화 구조

- `src/eraleader/dart_cfs_vintage_backup.py`: 기존 `native_encrypted_vault._openssl/_cert/_private_key`, `official_dart_vintage_registry.DartCFSVintageRegistry` 재사용. SQLite 온라인 백업 API로 실행 중 원본을 **일관성 있는 새로운 임시 스냅샷**으로 복제; 원본·복제 각각 `PRAGMA integrity_check = ok`, first registration SQLite 내부 SHA 체인(3건) 재확인.
- 기존과 같은 OpenSSL CMS **AES-256-GCM** + **RSA-3072 OAEP 수신자 공개 인증서**를 사용하여 스냅샷을 암호화. 평문은 Mac 0700 임시 디렉터리에만 생성하고 종료·오류 시 제거, 두 암호문만 별도 저장.
- **외장 SSD:** `/Volumes/T5DATA/EraLeader_Recovery_Backups/VintageCFS/<fresh_slot>/vintage.cms`
- **Mac 내부:** `~/Library/Application Support/EraLeader/ProtectedBackups/VintageCFS/<same_slot>/vintage.cms`
- 각 사본에는 동일 owner-only `receipt.json` (스냅샷 SHA/원본 SHA/등록 체인 SHA/암호문 SHA/공개 인증서 SHA/크기/생성시각)과 `complete.json` (영수증 SHA+암호문 SHA)을 **마지막에** 기록. 둘이 다른 물리 장치인지 `st_dev` 대조. 경로/기존 사본 덮어쓰기 금지, 누락·변조·복제 불일치는 즉시 차단. 복원/검증은 기존 사본을 읽기 전용으로만 사용.
- `verify_authenticated_recovery`: 외장 SSD 암호문+Mac 사본 두 SHA 일치와 원래 인증서 PIN 확인 → **별도 Mac 0700 임시 격리 경로**에서 올바른 RSA 개인키로 AES-GCM 인증 복호화 → 복원 SQLite 파일 전체 SHA 및 SQLite 무결성 + 원래 등록 SHA 체인 + 각 FY의 **최초 등록 이전/이후 as-of 상태** 재연산 → 임시 평문 자동 삭제. 실제 개인키 내용은 출력/로그/Git에 노출하지 않는다.
- `scripts/run_dart_cfs_backup.py`: `init-keys`, `backup`, `verify`, `restore-test` 독립 CLI. 실전 API HTTP/시장 원시자료 복사/매매/메시지 전송0. `--mac-root`/ `--ssd-root`는 각각 이미 존재하는 0700 소유자 폴더만 허용. `init-keys`는 **완전히 새로운** 키 디렉터리에서만 RSA-3072 생성, 파일 0600; 기존 개인키 덮어쓰기 금지.

## 실제 Mac+SSD 암호화 발행 및 복구 검증

- **원본 진실원장:** `~/Library/Application Support/EraLeader/research-ledgers/dart_cfs_vintage_forward_20261013.sqlite` (Mac 로컬). 삼성전자 FY2023·FY2024·FY2025 진짜 DART SHA 최초 수신/최초등록 이벤트 **3개**, 독립 처음 등록 time·hash-chain 보존.
- 공개 RSA 인증서/개인키는 Mac 사용자 전용 `~/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/`에 생성, 소유자 제한 0700/0600. **GitHub 커밋/백업 SSD 내에 개인키 복사0**. X509 공개 인증서 SHA `8e0da4f8316a6f3efbf6eff594100540462dde2a46d067679168637fd5474520`.
- 생성된 첫 증분 슬롯: `cfs_20261013T051710Z_fe24a7df3513`; Mac SSD 각각 파일 `vintage.cms`+`receipt.json`+`complete.json`, 외부/내부 **서로 다른 `st_dev` 증거**. 암호문 SHA `042ad5f33f7ab188c868bd529269ab35ade47b8b885c87c2432489aa32de9d65`, 스냅샷 원문 SHA `0c5fbb10db2764be2a46bc7f6c257924cdba128904ee166c7b5f15053eef5f22`, 데이터 노출 없음.
- **실제 복원 CLI `restore-test` PASS**: AES-GCM authentication, SQLite `integrity_check`, 등록 이벤트3·최종 `a001ed0b51832f5d...` 체인 일치, FY별 원본 **최초등록 이전에는 0건/등록 이후에는 해당 1건** PIT as-of 재검산. `plaintext_retained=false`. 과거 사업연도 최초 공식 공개시각의 독립 공인 증명은 아님.
- 안전 정량: 기존 KRX 2026-10-08 단 하루 관측/삼성전자 단일사의 FY3개 재무원본 이력에 한정. 다른 종목 데이터·역사적 issuer/share-class/상폐·산업·수급 PIT를 이번 백업으로 보충한 것 아님.

## 운영용 재검증 예시

Mac에서 이 feature worktree의 `scripts/run_dart_cfs_backup.py` 사용. 대괄호 부분은 소유자 전용 경로/slot.

```bash
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
python3 scripts/run_dart_cfs_backup.py verify \
  --ssd-snapshot /Volumes/T5DATA/EraLeader_Recovery_Backups/VintageCFS/cfs_20261013T051710Z_fe24a7df3513 \
  --mac-snapshot "$HOME/Library/Application Support/EraLeader/ProtectedBackups/VintageCFS/cfs_20261013T051710Z_fe24a7df3513" \
  --public-cert "$HOME/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/recovery_public.crt"
python3 scripts/run_dart_cfs_backup.py restore-test \
  --ssd-snapshot /Volumes/T5DATA/EraLeader_Recovery_Backups/VintageCFS/cfs_20261013T051710Z_fe24a7df3513 \
  --mac-snapshot "$HOME/Library/Application Support/EraLeader/ProtectedBackups/VintageCFS/cfs_20261013T051710Z_fe24a7df3513" \
  --public-cert "$HOME/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/recovery_public.crt" \
  --private-key "$HOME/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/recovery_private.pem" \
  --scratch-root "$HOME/Library/Application Support/EraLeader/vintage-restore-scratch"
```

**복구키 분실 경고 (미완료):** 현재 RSA 개인키는 Mac 내부에만 소유자 전용 저장. Mac 자체 분실·재해 시 SSD/다른 Mac 암호문은 개인키가 없으면 복호화할 수 없다. 별도의 외부 오프라인 암호화 키 에스크로/키 복구 절차는 아직 설정·검증하지 않았다. 단일 Mac 키 저장을 “완전 재난 복구”로 광고하지 말 것. Mac 내부·SSD 사본도 지리적으로 같은 위치일 수 있어 이중 저장=지리적 재난 대책이 아니다.

**독립 SHA의 한계:** SHA 영수증은 암호문 각각과 복원 원문 무결성을 교차확인한다. 독립 외부 공인시각/서드파티 서명·WORM 불변 보관을 인증하는 것은 아니다. 실제 미래 대장주 적중률·종합100점·공식 랭크는 계속 N/A.

## 테스트 / 실패·복원 주입

- 신규 `tests/test_dart_cfs_vintage_backup.py`: 실제 OpenSSL3 RSA-3072 keypair 생성, AES-GCM 스냅샷 암호화/복호화, 두 사본 SHA, 전체 SQLite integrity+first-known chain/as-of 리플레이, 중복 다른 슬롯 분리, 암호문/receipt 변조·잘못된 공개키/개인키·없는 원본·중간 complete 표식 누락, 같은 장치 2곳 저장 기본 차단, 암호문에서 평문 헤더 부재/키 노출·기존 키 덮어쓰기 차단, 남는 평문 0 등 집중 시험.
- 공식 FY CFS3·DART/KRX/SEC 실수신 이력, `DartCFSVintageRegistry`, `run_official_api_pit`, SHA/PIT/DRY-RUN 기능 재작성 없이 기존 영향범위 테스트와 같이 실행. 정확한 신규/관련 통과 수와 Git 최종 SHA는 `PROJECT_STATE.md` 최신 기록 참조.
- 전체 2,000+ 장기 회귀/주간 실제 자동운영/별도 키 에스크로 검증/상폐·정정 공개 원형 확보는 여전히 미완료. 진행률 95/99% 전체완료율 과거 추정은 계속 **철회**.
