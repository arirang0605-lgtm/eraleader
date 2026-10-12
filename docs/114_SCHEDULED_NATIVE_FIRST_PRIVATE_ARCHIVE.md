# EraLeader 5_5 / 6_5 — 최초 native Top-K 동결 직후 비공개 원본 SHA 자동 봉인 (opt-in)

2026-10-12 KST. 지난 docs/111의 first-native prospective freeze+census와 docs/113의 원래 WATCH·score·feature·label·census ZIP을 **정확히 이어서 실행**하는 선택형 예약 단계. 별도 사용자 동의 없는 상시 예약 설치·외부 API·실전 메시지·원시 데이터 Git 업로드는 하지 않는다.

## 해결한 운영 공백

기존 예약 run_local_scheduled.py 의 --native-first-capture-plan 옵션은 최초 positive WATCH의 모든 숫자 점수가 확보되면 native Top-K 동결 → first-write census 등록까지 실행했다. 그러나 그때의 첫 WATCH/score SQLite, 원래 피처·라벨 등 원천 보관(docs/113)은 사람이 별도로 실행해야 했다. 이번 변경으로 옵션을 명시한 예약에서만 **첫 동결/등록이 완료된 직후 원천 전체를 보관하고 최초 보관 SHA를 별도 로컬 영수증에 고정**한다. 첫 코호트 예측 시각과 보관 시각은 구분한다.

## 신규 기능 및 안전 게이트

- scripts/run_local_scheduled.py 의 신규 --native-first-private-archive 플래그는 --native-first-capture-plan 이 하나 이상 있어야 동작한다. 무옵션/과거 first-native 단독 명령 계약은 그대로 유지, macOS LaunchAgent plist를 설치하거나 수정하지 않는다. 새 src/eraleader/scheduled_native_archive.py 에서 이미 첫 등록이 완료된 결과에 한해 백업을 연결한다.
- 최초 positive WATCH 또는 일부 numeric score가 누락되어 동결 자체가 WAITING인 경우에는 ZIP·영수증·잠금파일 **모두 새로 생성하지 않는다**. 최초 출처를 거슬러 소급 생성하지 않는다.
- 완료/기존 완료 코호트는 시장+사전 고정 model_version SHA 슬롯으로 분리하여 Git 무추적 output/native_first_private_archives/native_<slot>.zip 에 비공개 원본을 보관한다. output/native_first_archive_receipts/native_<slot>_receipt.json 및 native_<slot>_guard.json 은 ZIP과 다른 출력 하위 폴더에 O_EXCL 최초 기록한다. 원본 plan SHA, 원래 capture receipt SHA, 실제 archive SHA-256, source root 지문, 보관 UTC 로컬 OS 시각, nonce와 별도 guard SHA를 정규 JSON 원문 바이트로 잠근다.
- 별도의 .native_<slot>.lock 은 한 슬롯의 동시 실행을 막고, 잠금만 남고 원래 ZIP+영수증이 사라지는 중단/손상을 사고로 구분한다. ZIP/receipt/guard/lock 중 하나가 없거나 변조됐다면 성공 판정과 새 최초 SHA 재등록을 거부한다. ZIP만 남았는데 영수증이 없는 경우도 자동으로 추후 ZIP을 최초 입증으로 소급 인증하지 않는다. 오염된 파일은 기존 안전 백업과 외부 신뢰 SHA를 통해 별도 복구해야 한다.
- 반복 실행 시 새로운 ZIP/보관 최초 시각을 다시 쓰지 않고, 원래 영수증/guard·ZIP 정확 SHA·내부 manifest의 first source/model/census 바인딩을 재확인한다. 이미 최초 코호트가 존재한 모델에 새 cohort_id/K를 부여한 중복 계획이 입력되면 첫 source 쓰기 전에 차단한다. KR+US 다중 시장에서는 각 시장을 따로 봉인하고 일부 실패를 전체 성공으로 표시하지 않는다.
- 원래 예약 연구가 stale-cache 또는 데이터 품질로 실패해도 선택된 archive 경로를 별도로 시도하고 원래 실패를 보존한다. archive가 실패하면 원래 예약을 성공으로 보고하지 않는다. API 호출 0, 실전 발송 0, 공식 대장주 승격 0.

## 사용 예 (실제 원래 사전계획 경로가 있어야 함)

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_local_scheduled.py \
      --project /Volumes/T5DATA/eraleader \
      --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
      --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/us_first_plan.json \
      --native-first-private-archive

반환된 private_original_archive.archive_original_sha256은 **SSD 외부의 신뢰할 수 있는 별도 보안저장소**에 기록해야 훗날 함께 변조된 ZIP과 로컬 영수증을 구별하는 데 도움이 된다. 현 구현은 자동 외부 백업이나 독립시각 공증을 하지 않는다. 복구는 docs/113의 별도 --action restore --expected-sha256 사용. ZIP에는 원시 WATCH·score·feature·당시 원본 절대 경로가 평문 포함돼 있으므로 Public GitHub 업로드 금지. 로컬 영수증과 ZIP은 다른 디렉터리지만 동일 장치·관리자가 일관되게 위조할 수 있는 한계를 명확히 보존한다.

## 테스트/독립 인증 한계

- 코드: 신규 scheduled_native_archive.py, 스케줄러 선택형 확장, 집중 tests/test_scheduled_native_archive.py. 기존 native_first_capture.py의 다른 세션 미커밋 수정분은 릴리스에 포함하지 않는다.
- KR/US 최초 positive WATCH+numeric score 실제 Python fixture를 예약 함수로 실행, 부분 source WAIT의 원장/ZIP 생성0, 최초 ZIP+별도 영수증/guard 봉인 및 재실행 시 0개 신규 ZIP, 임의 영수증/원본 ZIP 삭제·조작 시 fail-closed, duplicate model 사전 거절, scheduler 기존 실패 보존, plist 설치 금지. 실제 Mac T5DATA 이전 합성 한국·미국 소스에 first/archive/read-only replay 2회 실행하여 최초 정책 SHA 유지, 원본 바이트 전후 불변, 라이브 전송0. 결과는 output/verification_logs/scheduled_native_archive_os_e2e_20261012.json (Git 무추적).
- 현물 KRX/DART/SEC 법적 issuer·상폐·기업행동·first published/first retrieval PIT 독립 인증 및 실제 미래 대장주 발견 precision/false discoveries/lead-days는 미완료. 외부 API D-017 및 SSD 실제 물리 탈착·재연결 D-021은 최종 단계.
