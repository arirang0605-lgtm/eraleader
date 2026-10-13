# 139 — 6_5 복구 개인키의 독립 수탁자 공개키 에스크로

**개발 ID:** 6_5. **개발일:** 2026-10-13. **기준:** `feature/core-official-factor-coverage-20261013` / `e02b14172025ddfd193f529a83eaad994f61875c`.

## 배경·안전 목표

기존 증분 DART CFS SQLite 이력 DB는 외장 SSD와 Mac에 각각 AES-256-GCM 복구 암호문을 보관하고, 실제 Mac RSA-3072 개인키로 독립 복원/첫 등록 시점 재연산까지 검증했다. 그러나 개인키가 **동일 Mac 내부에만 있어서 Mac을 분실하거나 Mac 내부 키가 유실될 때 두 암호문을 복구할 수 없다**.

이번 변경의 안전 계약은 **다른 물리 기기에서 생성·보관한 별개의 RSA-3072 공개 인증서**로, 원래 Mac에 있는 CFS 복구 개인키를 오직 **암호문으로만 외부 장치에 저장**하는 것이다. 인증서의 공개키는 Mac에 전달해도 되지만, **외부 별개 개인키는 이 Mac에서 새로 만들거나 기본값으로 복사하지 않는다**. 실제 오프라인 수탁·지리적 분산은 사용자가 확보하고 확인하기 전까지 항상 `false`.

## 추가 구현 (기존 코드는 변경하지 않음)

- 새 `src/eraleader/dart_cfs_external_key_escrow.py`. 검증된 기존 OpenSSL3 CMS `AES-256-GCM / RSA-OAEP`와 `native_encrypted_vault._openssl/_cert/_private_key`, 기존 CFS 복구/DR 함수 재사용.
- `prepare_external_key_escrow(...)`: **원래 Mac 비공개 키의 공개 SPKI와 기존 CFS 암호화 공개 인증서가 서로 같은지 확인**, 외부 수탁 공개 인증서의 SPKI가 **다른 RSA 키쌍인지** 비교, 외부 수탁 인증서 현재 유효·정상 확인. 실제 외장 저장은 소유자 전용 `0700` 절대경로 및 키와 다른 물리 장치 `st_dev` 필요. 원래 개인키 원문/새 외부 개인키 원문/암호 해제 비밀번호를 로그·스크립트 인수·Git에 내보내지 않는다.
- 복구키를 외부 수탁 인증서 공개키로 CMS AES-256-GCM 암호화해 새로운 랜덤 슬롯 `escrow_<UTC>_<random>` 내부 `recovery_key.cms`와 `receipt.json`(수신자 cert SHA, SPKI SHA, 암호문 SHA), `complete.json`(영수증 SHA·암호문 SHA)을 **원자적 새 경로**로만 게시. 기존 슬롯·원본 키 파일 덮어쓰기 금지. `plain_key_escrowed=false`, `actual_independent_private_key_custody_attested=false`를 영구 기록.
- `verify_external_key_escrow`: 공개 인증서 2개 + 암호문/영수증·완료 마커 SHA만 읽기 전용 검증; 개인키를 읽지 않으며 인증 복호화 완료를 주장하지 않음.
- `drill_external_key_escrow`: **사용자가 의도적으로 별도 수탁자의 개인키를 제공한 경우에만** 두 외장·Mac CFS 백업 사본 SHA 확인→격리 `0700` scratch에서 외부 RSA 키로 원래 Mac 복구키를 인증 복호화→그 복원된 원래 키로 기존 원장 암호문을 다시 인증 복호화→SQLite `integrity_check=ok`, first registration chain/as-of replay→임시 평문 삭제. 돌려주는 상태는 `actual_offline_private_key_custody_verified=false`를 고정한다. 이 시험 자체도 외부키가 실제 지리적으로 따로 보관됐다는 독립 증빙은 아님.
- 독립 `scripts/run_dart_cfs_external_escrow.py`: `export`, `verify`, `drill` CLI. 외부 개인키는 `export`와 `verify`의 인자가 아니며 `drill`에서만 명시적으로 필요. 오류시 암호원문/키경로/CMS stderr은 노출하지 않는다. 옵션 없이 기존 `run_dart_cfs_backup.py`와 KRX/DART/SEC 수집/종합순위는 전혀 변하지 않는다.

## 실제 운영 적용에서 아직 필요한 별도 외부 준비

1. **Mac과 T5DATA가 아닌 독립 오프라인 장치**에서 외부 수탁자가 개인 RSA 복구키와 X509 공개 인증서를 만든다. **이 Mac에서 외부 개인키를 생성해 놓고 독립 키 에스크로라고 기록하지 않는다.**
2. 외부 개인키는 해당 오프라인 기기에만 보관하고, **공개 인증서 `.crt`만** Mac의 소유자 제한된 위치에 전달한다.
3. 외장 T5DATA 내 Git 저장소 밖 `EraLeader_Recovery_Backups/ExternalKeyEscrow`와 같은 owner-only 새 디렉터리를 만들고(기존 암호문/백업·원본 DB와 별도), 아래 `export` 실행. 이미 존재하는 슬롯을 덮어쓰지 않는다.
4. 외부키 실제 위치 및 분실 시 복구 절차를 수탁자와 확인한다. 테스트는 외부 수탁자가 안전한 별도 기기에서 복구 시뮬레이션을 수행하는 것이 바람직하다. 만약 Mac에 외부키를 연결해 `drill`할 경우 해당 키의 노출 위험이 있으므로 보호된 환경에서 일시적 연결 후 제거한다.

```bash
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
# 외부 수탁자 PUBLIC .crt만 사용; 외부 PRIVATE key를 이 Mac에 만들지 않는다.
python3 scripts/run_dart_cfs_external_escrow.py export \
  --original-private-key "$HOME/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/recovery_private.pem" \
  --original-public-cert "$HOME/Library/Application Support/EraLeader/recovery-keys/dart_cfs_20261013/recovery_public.crt" \
  --external-public-cert /owner-only/external-custodian-public.crt \
  --escrow-root /Volumes/T5DATA/EraLeader_Recovery_Backups/ExternalKeyEscrow
```

`verify`는 `--escrow <slot>` + `--original-public-cert` + `--external-public-cert`; `drill`은 거기에 `--external-private-key`, `--ssd-snapshot`, `--mac-snapshot`, `--scratch-root`를 추가한다. 실제 수탁자가 보관하는 외부 개인키는 별도의 사용자 통제 장치에 있어야 한다.

## 이번 작업의 실제 검증 범위와 상태

- Python synthetic fixture로 별도 RSA3072 외부 키쌍을 임시 생성해 **실제 암호화 CMS → 두 단계 인증 복호화 → 기존 CFS 3개 이벤트 SHA chain/as-of 재생 → 평문 scratch 0** E2E 수행, 틀린 개인키/인증서/원래키·같은 RSA 키쌍·같은 장치 가짜 분리·봉인영수증 변조·마커 누락·기존 키/슬롯 덮어쓰기 방지 테스트.
- **합성 테스트용 외부키는 임시 파일로 실행한 것**이며 별도 오프라인 수탁자의 개인키 보관을 확인한 것은 아니다. 실제 사용자의 독립 외부 공개 인증서는 아직 지정되지 않았다면 **프로덕션 에스크로 생성·최종 개인키 DR 검증은 WAITING**. 기존 CFS SSD/Mac 두 암호문과 Mac 원래 RSA키, 이력 DB 3개는 그대로 보호.
- 새 `tests/test_dart_cfs_external_key_escrow.py` 신규 11개와 기존 187개 관련 테스트 결과는 `PROJECT_STATE.md` 최신 기록과 동일해야 한다. 대규모 전체 회귀/외부 지리적 재난 복구 시험은 별도.
- 향후 외부 인증서가 주어졌을 때도 사용자 데이터·비공개 운영 원장·CMS 암호문/개인키는 Public GitHub에 넣지 않는다.

**근본 목표:** 이 보호 기능은 EraLeader 미래 대장주 발굴의 데이터 시점무결성 하부구조다. 전국/미국 전종목 PIT issuer/class·정정 이력, 실제 산업·수급·실적 종합순위, 20거래일 운영 및 3~12개월 전향적 적중률 인증은 **미완료**이며 전체 개발률 95/99% 주관 추정은 계속 철회한다.
