# EraLeader 6_5 — 최초 cold ZIP의 독립 SHA PIN 기반 실복구 리허설

2026-10-12. **이번 작업은 기존 docs/113~123 복원 엔진을 재작성하지 않고 연결해 한 단계 더 검증한다.** 이전 6_5의 periodic SHA 확인은 암호문의 보전만 의미했다. 이 작업은 명시적인 비공개 RSA 키가 제공된 경우에 한하여 **cold 패키지 ZIP → 원래 immutable first PIN 확인 → ZIP에 봉인된 독립 witness/cipher/공개 X509를 신규 위치에 복원 → 기존 AES-256-GCM 인증 복호화 → 원래 최초 WATCH·numeric score·피처·등록 census index 실제 replay**까지 독립적으로 수행한다. API/실전 주식 거래/문자 전송/실제 SSD 분리·재부팅하지 않는다.

## 신규 실행 모듈

- `src/eraleader/native_cold_replay_drill.py`, `scripts/run_native_cold_replay_drill.py`: `--action run|verify-history`, 원래 `--project`, 외부 PIN 저장소 `--pin-root`, 별도 사설 임시 공간 `--scratch-root`. 실제 `run`에서만 원래 등록 alias `--name` / 24자리 SHA 모델 `--slot` / 사용자 명시 private 키 `--private-key` 필요. history만 확인할 때는 **키 입력 자체를 거절**. 기존 정상 `native_cold_integrity`, `native_cold_custody.check_portable_native_custody`, `native_encrypted_vault.verify_encrypted_native_original` 및 `restore_encrypted_native_original`만 호출.
- PIN root의 원래 first receipt/guard, PIN 연속 SHA 원장/체크포인트, portable ZIP 전체 SHA/member/first witness 검증을 통과해야만 복호화 시도. 직접 전달받은 새 SHA로 이전 PIN 대체·새 first witness 발행·삭제 방지. 실패시 fail-closed `INDEPENDENT_PIN_NOT_VERIFIED`, `UNSAFE_OR_MISSING_KEY`, `COLD_PACKAGE_RECONSTRUCTION_FAILED`, `ORIGINAL_WATCH_OR_CENSUS_REPLAY_FAILED`, `PRIVATE_TEMPORARY_CLEANUP_FAILED`, `INDEPENDENT_PIN_CHANGED_DURING_REHEARSAL` 고정 상태.
- 처음 등록 당시 암호화 portable ZIP의 원본 SHA가 복호화·처음 WATCH/score/census 검증 이후까지 동일해야 한다. 원래 민감 ZIP, 원래 AES vault/witness, 과거 모델/증권 데이터는 **덮어쓰거나 정상 리허설 위해 필요하지 않다**. 사전 준비된 owner-only 0700 별도장치 scratch를 사용하고 새 임시 암호문+원본 재생 폴더만 생성/종료 후 삭제. 이 삭제는 물리 디스크 섹터·스냅샷에 대한 **secure erase 주장이 아님**.
- 로컬 `output/native_cold_replay_drills`에 O_EXCL 첫 genesis/first-event SHA, 개인권한 lock, 이전 event SHA→현재 event SHA append history, 독립 최종 report SHA checkpoint. 첫 동결과 임시 scratch 지정/pin-root 계약을 그대로 보존, 깨진 이전 기록/파일·소급 시계 역행 재승격 불가. 원래 PIN SHA·암호문 SHA/ZIP SHA·KR/US 익명 슬롯만 기록. `site/index.html`/기존 `output/site/cold_replay_drill.html`에 최종 PASS/FAIL·고정 코드·익명 SHA prefix를 보여준다. 비공개 원본 파일경로/종목/issuer/개인키/원래 점수/평문을 웹/출력에 사용하지 않는다. 부분·전체 관리자 공동위조와 OS 시각 조작에 대한 독립 공증은 아님.
- **예약 자동 복호화 옵션 추가 0.** 기존 launchd, `scripts/run_local_scheduled.py`, PIT 엔진, 1~5단계, 자동 알림/거래 코드 전부 유지. 지금 기능은 운영자가 필요시 키를 명시해서 별도 실행하는 시험이다. 기본은 각기 다른 `stat.st_dev` 저장소 요구, `--allow-colocated-research-only`는 합성 연구 전용이고 운영 offsite 인증 false. 세 번째 저장 장치 없으면 운영 모드로 성공 주장 금지.

## 실행 계약

```bash
cd /Volumes/T5DATA/eraleader
# 사전에 docs/122 최초 cold ZIP export, docs/123 별도 SHA PIN 등록 완료
# 키는 Git outside, 소유자 전용 파일 0600. scratch는 원래 T5DATA 외장 SSD 바깥 0700
python3 scripts/run_native_cold_replay_drill.py --action run \
  --project /Volumes/T5DATA/eraleader \
  --pin-root /Mac_외부_보호된_SHA_PIN_root \
  --scratch-root /별도_디바이스_0700_임시_복원공간 \
  --name kr-first --slot kr_원래모델해시24자리 \
  --private-key /Git_밖_소유자전용_복원키.pem

python3 scripts/run_native_cold_replay_drill.py --action verify-history \
  --project /Volumes/T5DATA/eraleader \
  --pin-root /Mac_외부_보호된_SHA_PIN_root \
  --scratch-root /별도_디바이스_0700_임시_복원공간
```

## 검증·한계·NEXT

- `tests/test_native_cold_replay_drill.py`: 독립 최초 PIN/암호문 실제 복원 성공 및 원래 WATCH·score·census replay 확인; repeated idempotent 원본/기록 append, ZIP 변조/유실/symlink, PIN guard/첫 receipt 변경, world-readable/missing/invalid key, 잘못된 모델 슬롯, 재생 결과 위조, 이전 genesis/history/first receipt/checkpoint 수정, 시계 역행, private scratch 권한, 모드 제한, CLI 비밀 경로 미노출/키 없는 SHA history. **집중 테스트 24/24 PASS**, 전체 회귀 및 Git SHA는 PROJECT_STATE 맨 아래 최신 기록.
- 실제 Mac T5DATA SSD와 Mac 내부 `/private/tmp`의 서로 다른 filesystem 합성 CLI: 최초 native WATCH/score/census→비공개 ZIP→Mac SHA witness→AES-GCM first vault→portable cold package/원래 PIN 연구모드. 원래 T5DATA 비공개 ZIP과 기존 Mac vault/witness 경로를 임시로 **논리적 숨김 상태**에서도 다른 저장된 cold ZIP만으로 완전 인증 복원 PASS; 패키지 훼손한 채 리허설 FAIL(exit2); 원래 bytes 복구 후 PASS. 마지막 원래 ZIP SHA 동일, private scratch 비었음, 로컬 웹 HTTP200. ignored `output/verification_logs/native_cold_replay_mac_e2e_20261012.json`. 원래 실제 SSD를 물리 분리한 것은 아니며 다른 3번째 storage/offsite/법적 공증 인증도 아니다.
- API 제외 기능 구현 약99%(추정), KRX/DART/SEC 공식 시계열 PIT/상폐·기업행동 인증과 실제 prospective Top-K의 자연 만기 성능은 **D-017 후반**. 물리 SSD 탈착·재연결·재부팅 **D-021 최종**. 다음 개발은 운영할 3번째 파일시스템 지정 시 실제 strict custody·SHA escrow 검증 및 live API 준비 점검(키/원시자료 Git 불포함). 기존 완성 로컬 기능의 정상 코드를 재작성하지 말 것.
