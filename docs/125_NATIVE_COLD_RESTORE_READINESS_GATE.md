# EraLeader 6_5 — cold ZIP·최초 SHA PIN·실제 재생 리허설 통합 복구 준비도 게이트

2026-10-12. docs/122~124 **정상 cold 원본 ZIP, 외부 PIN, AES-GCM 실제 WATCH/score/census replay 구현을 재작성하지 않고 재사용**. 이전에는 콜드 암호문 무결성 정상과 진짜 복구 이력/리허설 만기를 **서로 독립적으로** 보여주므로 운영 담당자가 실제로 사용 가능한지 놓칠 수 있었다. 신규 `src/eraleader/native_cold_restore_gate.py`는 **원본 first SHA PIN 증거 + 전체 ZIP 암호문/멤버/witness + 모든 모델의 첫 WATCH/census AES 인증복구 이력**을 결합해 로컬 DRY-RUN 상태로 판정한다.

## 핵심 기능 / 안전 판정

- Original PIN root의 first receipt/guard/append SHA history/checkpoint를 잠금 상태로 검증한다. 매 실행시 **등록된 전체 cold package (최대 128개)**를 원본 PIN SHA로 실제 전수 검사; 고장난 패키지/첫 PIN의 SHA를 새로운 값으로 자동 재고정하지 않는다.
- ZIP은 하나에 **1~16개의 KR/US 원래 모델 SHA 슬롯**을 보관할 수 있다. 패키지 manifest는 원래 SHA256과 정확히 비교한 후 읽으며 모든 슬롯에 대해 **같은 PIN·같은 package SHA·각 모델 slot SHA에 일치하는 최신 PASSED AES-GCM/first WATCH/score/census replay**를 요구한다. 일부 모델만 리허설한 경우 전체 복구 성공이라고 절대 표시하지 않는다. 동결된 ZIP 속 KR+US 전수 분모 변경 불가.
- default due 30일 / warning 7일 (연구용 **운영 정책 가설**, 최적화·실전 인증값 아님). 정상 기한 `READY_FRESH` 또는 합성 제한 `RESEARCH_ONLY_FRESH`, 조기경고 `DUE_SOON`, 만료 `OVERDUE`; 미실시 `NEVER_REPLAYED`, 마지막 실패 `LAST_REPLAY_FAILED`, ZIP/PIN 위조·분실 `UNTRUSTED_COLD_SHA`, 원본 replay/first PIN chain 이상·자기일치 rollback 등은 별도 fail-closed 경고.
- **한 번 연구용 co-located flag로 등록한 ZIP은 상시 `RESEARCH_ONLY_FRESH`**. 정말 세 번째 별도 device에 cold ZIP이 있고 PIN root/원본 SSD가 모두 다른 st_dev인 strict 로컬 환경에서만 `READY_FRESH` 가능. 그마저도 지리적 offsite·독립 타임스탬프/실전 재부팅·외부 신뢰 공증이 아님. `operational_offsite_attested=false` 및 공식 PIT·미래 대장주 적중률 인증 false.
- 같은 PIN의 이전 감사 스냅샷에 남은 **원본 PIN SHA 체인 count+HEAD / 복구 리허설 SHA chain count+HEAD / 익명 cohort inventory**를 독립 `output/native_cold_restore_readiness` first O_EXCL genesis/first event/append previous→SHA history/checkpoint에 PIN한다. 누락·롤백·first PIN 교체·시계 역행·소급 healthy 오인 금지; 동일 경고 반복시 신규경고0, 복구 후 RESTORED_FRESH_REPLAY.
- SHA-only 읽기 기능으로 **실제 복호화·PRIVATE KEY 로딩·원본 대장주 종목/시세/issuer 접근·주문·실전 전송·API 호출0**. local `report.json`, `site/index.html` 및 기존 `output/site/cold_restore_readiness.html` 접속 링크에는 익명 PIN SHA prefix/시장/상태/기한만. 원시 ZIP 및 PIN의 private 절대경로/키·종목은 웹 반출 금지. USB/SSD 실제 분리·재부팅하지 않음.
- 독립 `scripts/run_native_cold_restore_gate.py --action scan|verify-history`; 기존 `scripts/run_local_scheduled.py` opt-in `--native-cold-pin-root --native-cold-restore-scratch-root`, 선택 `--native-cold-restore-due-days 30 --native-cold-restore-warn-days 7`. 원래 stale 가격 연구 실행이 실패해도 새 게이트는 가능한 범위에서 읽기 감사를 하고 **기존 실패를 성공으로 덮지 않는다**. 자동 개인키 복호화·LaunchAgent 설치/변경0, `--generate-plist` 결합 거부, 일반 무옵션 예약 동작 유지.

## 재현 명령 예

기존 docs/122 encrypted-only package 및 docs/123 첫 SHA PIN 등록, docs/124 사용자 명시적 PRIVATE KEY 실제 복구 리허설 이력이 필요하다. `--scratch-root`는 기존 리허설 기록과 **동일한 0700 별도 filesystem 경로**여야 한다. 이 게이트 자체는 절대로 키를 요구하지 않는다.

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/run_native_cold_restore_gate.py --action scan \
  --project /Volumes/T5DATA/eraleader --pin-root /Mac_first_sha_pin_root \
  --scratch-root /Mac_owner0700_replay_scratch
python3 scripts/run_native_cold_restore_gate.py --action verify-history \
  --project /Volumes/T5DATA/eraleader --pin-root /Mac_first_sha_pin_root \
  --scratch-root /Mac_owner0700_replay_scratch
# 기존 local research 예약에서 진짜 명시 옵션만 추가:
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader \
  --native-cold-pin-root /Mac_first_sha_pin_root \
  --native-cold-restore-scratch-root /Mac_owner0700_replay_scratch
```

## 시험 범위 및 남은 과제

- 집중 테스트: `tests/test_native_cold_restore_gate.py` (18), `tests/test_scheduled_native_cold_restore_gate.py` (11); 정상/미검증, 사전경고/만기/재복구, 마지막 실패 override, SHA 분실·변조·symlink, owner600 PIN/guard, 자체 일치한 원본 기록 롤백, 실제 두 시장/모델 전수 리허설, 잘못된 시간, 자동 발송/복호화0, stale 원래 오류 유지, 무옵션 계약, 로컬 SHA history tamper 차단. 최초 집중의 JSON 개행 문자 버그를 수정하고 **29/29 PASS** 재검증.
- Mac T5DATA SSD와 `/private/tmp` 두 실제 다른 `stat.st_dev` 기반 오프라인 합성 CLI E2E: 연구용 cold PIN/ZIP과 AES recovery first-WATCH/census를 기존 정상 구현으로 재생, 게이트 최초 `NEVER_REPLAYED`→원본 PASS 이후 `RESEARCH_ONLY_FRESH`→ZIP 변조 `UNTRUSTED_COLD_SHA`→원본 ZIP 복구 `RESEARCH_ONLY_FRESH`; HTTP200/암호문 비공개 원시 SHA/원래 score 경로 변화0. 자료는 Git ignored `output/verification_logs/native_cold_restore_gate_mac_e2e_20261012.json`.
- 실제 외부 API D-017 KRX/DART/SEC 최초 출처 시각/PIT/법인 class·상폐 현금·기업행동 및 prospective TOP-K 자연 성숙 outcome 검증은 나중. 세 번째 콜드 파일시스템 없어 **strict 오프사이트 운영/실물 SSD 탈착·재연결/재부팅 D-021 미검증**. 향후 운영 키 escrow·제3 storage 지정·독립 타임스탬프/지리분리 재해복구에 대한 사용자 결정을 마지막에 반영.
- 모든 local 상태와 SHA는 **같은 Mac 관리자가 공동 위조할 수 있고 OS 시각이 독립 공증이 아니므로 공인 예측력·PIT 인증 주장 불가**. API 제외 로컬 기능 구현 추정 약99%, 실제 성과 검증과 구분. REWRITE 금지, 기존 미커밋 native_first_capture.py 7줄 보존. 테스트 총계/커밋 SHA는 PROJECT_STATE 최하단 확인.
