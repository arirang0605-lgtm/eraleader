# EraLeader 5_5 / 6_5 — 최초 native 원본 ZIP의 다른 파일시스템 SHA 영수증

2026-10-12 KST. 기존 113~114 기능은 원본 WATCH/score/feature/label/census의 민감 비공개 ZIP과 SHA 영수증 모두 T5DATA SSD 안에 존재했다. 이번 기능은 **사용자가 별도로 명시한 파일시스템에 SHA만 복사**해 SSD 전체 파일의 묶음 교체·손상 시 추가로 비교할 로컬 근거를 보존한다. 독립 외부 공증이나 암호화 원본 전체 백업은 아니다.

## 구현

- 신규 src/eraleader/native_sha_witness.py : Mac 파일시스템 stat.st_dev가 원래 EraLeader T5DATA와 다를 때만 witness 기록. 대상의 절대경로·symlink 없는 부모·비중첩 위치·mode 700 private witness 디렉터리를 검사하고, 부적합하면 연구 배치가 시작되기 전에 차단한다.
- 기존 처음 positive WATCH/numeric score → Top-K freeze/census 원장 등록 → private 원본 ZIP+SSD 내부 original SHA receipt 검증 **이후에만** 별도 witness 생성. WAIT/원시점수 누락·ZIP 미확보는 별도 디스크 새 파일0.
- 별도 witness 폴더 안 native_<market-modelhash>_first.json 및 native_<...>_guard.json을 각각 O_EXCL/fsync로 최초 기록. .native_<...>.lock을 이용해 시장+모델 슬롯마다 동시 쓰기를 차단하고 일부 소실/분리 사고를 실패로 처리. 반복 실행은 ZIP 새 생성이나 first timestamp 재작성 없이 원래 SSD ZIP raw SHA·first receipt/guard·원본 출처 모델 관계와 다른 볼륨 SHA 영수증/guard를 다시 대조한다.
- witness는 KR/US·모델 해시·원래 plan/capture 루트 해시·원본 최초 capture 영수증 및 SSD 원래 receipt/guard SHA·ZIP SHA·로컬 OS 첫 witness 시각/nonce만 포함한다. 실제 ticker, 회사/issuer 클래스ID, 원본 절대 경로, 시세 원문, API 키, 민감 ZIP 본문을 다른 파일시스템으로 복사하지 않는다. 관련 메시지와 CLI 출력에도 원본 경로는 노출하지 않는다.
- 신규 예약 옵트인 --native-first-internal-witness-root 은 반드시 기존 --native-first-capture-plan 및 --native-first-private-archive와 함께 사용. 무옵션/과거 first-native 예약 동작은 동일. 잘못된 대상은 원래 예약 작업 시작 전에 차단, --generate-plist와 혼용 금지. 별도 읽기 전용 CLI scripts/verify_native_sha_witness.py가 ZIP+별도 SHA의 상호 무결성 검증을 수행한다.
- SHA 원본/첫 receipt 하나라도 삭제/변조됐거나 내부 guard·첫 witness가 부분 소실, symlink가 끼어들면 fail-closed. ZIP과 SHA는 서로 다른 물리 파일시스템이지만 **동일 Mac 사용자와 로컬 시계**에 의존하므로 외부 타임스탬프·PIT/대장주 성능 인증 아님. Mac 자체 고장·두 디스크 동시 관리자 위조·witness 파일 전체 삭제는 완전 탐지할 수 없고, SSD가 파괴되면 SHA만으로 민감 원본을 복원할 수도 없다.

## 실제 사용자 선택 실행 예

원래 최초 Plan 파일 경로는 **실제 존재하는 문서**로 대체해야 한다. 다음 설정은 자동 설치가 아니라 직접 실행할 때만 작동한다.

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_local_scheduled.py \
      --project /Volumes/T5DATA/eraleader \
      --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
      --native-first-capture-plan /Volumes/T5DATA/eraleader/output/native/us_first_plan.json \
      --native-first-private-archive \
      --native-first-internal-witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness"

읽기 전용 검증:

    python3 scripts/verify_native_sha_witness.py \
      --project /Volumes/T5DATA/eraleader \
      --plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json \
      --capture-root /Volumes/T5DATA/eraleader/output/native_first_captures \
      --witness-root "$HOME/Library/Application Support/EraLeader/native_sha_witness"

## 실제 테스트 증거 및 다음 단계

- T5DATA Mac과 /private/tmp 서로 다른 st_dev 확인. 기존 **합성** KR/US 최초 native 코호트 2개에서 SSD ZIP·first SHA 일치 → Mac 로컬 임시 경로 최초 SHA witness → 동일 재검증 → 실제 별도 read-only CLI, 원본 각 6개 SHA 전후 동일, 외부 API/실전 전송0. 결과는 Git ignored output/verification_logs/native_sha_cross_volume_mac_e2e_20261012.json. 임시 Mac witness는 테스트 종료 후 제거되었으며 **상시 운영용 Mac 내부 보관 경로는 설치하지 않음**.
- 테스트 모듈 tests/test_native_sha_external_witness.py, tests/test_scheduled_native_witness_bridge.py: 복수 마켓, 최초 봉인/중복 검증, 자기일치 SSD 교체/원장 손상·삭제/lock·symlink/경로·권한, 스케줄러 기존 상태 보존, 실제 CLI/비활성 기본 동작.
- 공식 시장 KRX/DART/SEC 법적 issuer/share class·기업행동·상폐·최초 공시 공개/수신 시각 PIT, 최초 WATCH의 수개월 후 진짜 예측 precision/FDR/lead-days 아직 미인증. D-017 외부 API 마지막, D-021 실제 T5DATA 물리 분리·재연결/재부팅 마지막.
