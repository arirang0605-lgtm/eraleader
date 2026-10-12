# EraLeader 5_5 / 6_5 — 최초 WATCH·native Top-K 원천 증거 비공개 보관 및 검증 복구

2026-10-12 KST. 이전 docs/111의 첫 prospective native Top-K 동결 및 등록 이후 남은 공백: 첫 WATCH SQLite, numeric score SQLite, 원래 피처 문서, 사전 고정 라벨 룰, 최초 동결·census 영수증을 한 묶음으로 저장하고 독립 폴더에서 검증한다. 기존 정상 발굴·동결·성과검증 코드는 보존하고, 외부 API/실전 주문·메시지/물리 SSD 탈착 없음.

## 신규 구현 범위

- src/eraleader/native_evidence_archive.py 및 scripts/archive_native_first_evidence.py: 이미 완성·등록된 첫-native prospective 코호트만 허용. 원래 first-write 동결 lock을 공유하고 기존 read_capture_plan + _inspect_complete + audit_native_census를 읽기 전용 재사용; 부분등록/소급 생성/미래 라벨 선택 금지.
- ZIP 파일에는 원본 plan, WATCH·score SQLite, 원래 모든 feature JSON, label definition, first frozen Top-K, native proof config, census input/manifest, first receipt index SQLite, native gate marker, first capture receipt, 최초 lock 증빙이 포함된다. 민감 원본/절대 경로를 담는 ZIP이므로 **Public GitHub 업로드 금지**. 모든 멤버의 길이/원래 경로/SHA-256과 모델·라벨·원장 관계를 원본 manifest에서 검사한다. 경로 탈출·중복·심볼릭 링크·압축폭탄·SQLite WAL/journal·감춰진 추가 바이트 차단.
- 실제 T5DATA 파일시스템은 하드링크를 지원하지 않는 것을 확인. 임시 ZIP 전체검증 후 O_EXCL 새 대상 파일에 스트리밍 쓰기+fsync 및 SHA 재검증. 기존 ZIP 절대 덮어쓰기 금지. 장애로 중간 복사가 끊어지면 일부 ZIP을 자동 덮거나 성공으로 표시하지 않고 검증 실패로 보류(원자적 게시라고 주장하지 않음).
- 별도 새 폴더로만 복원하고 기존 활성 WATCH/score/Top-K 위치에는 자동 덮어쓰지 않는다. 복원 전 사전에 **별도 보관해 둔 원래 ZIP SHA-256 필수**. 복원본에서 첫 WATCH·숫자 점수·피처·규칙으로 audit_ranked_maturity를 재실행하고 census receipt 인덱스 SHA-chain을 검증. 기존 census manifest는 원래 절대 경로를 그대로 보존해 최초 발굴일/후속 증거를 소급 위조하지 않는다. future_outcomes.json 등 미래 결과는 절대 보관하지 않는다.
- 최초 ZIP 생성 시 첫 원본 바이트를 재확인하고 자료가 변조·변경됐으면 실패한다. 명령 결과에는 원본 회사ID/원시 주가/공급자 출처의 개별 원본 파일 경로를 표시하지 않는다. ZIP은 **암호화되지 않은 비공개 로컬 원본 자료**이므로 보관 위치·별도 접근통제·외부에 안전하게 SHA 보관할 책임이 있으며 현재 코드는 이를 외부 전송하지 않는다.

## 사용 명령

    cd /Volumes/T5DATA/eraleader
    python3 scripts/archive_native_first_evidence.py --action create --project /Volumes/T5DATA/eraleader --plan /Volumes/T5DATA/eraleader/output/native/kr_first_plan.json --capture-root /Volumes/T5DATA/eraleader/output/native_first_captures --archive /Volumes/T5DATA/eraleader/output/private_native/KR_first.zip

    python3 scripts/archive_native_first_evidence.py --action verify --project /Volumes/T5DATA/eraleader --archive /Volumes/T5DATA/eraleader/output/private_native/KR_first.zip --expected-sha256 <create_결과_64자_SHA256>

    python3 scripts/archive_native_first_evidence.py --action restore --project /Volumes/T5DATA/eraleader --archive /Volumes/T5DATA/eraleader/output/private_native/KR_first.zip --expected-sha256 <원래_64자_SHA256> --target /Volumes/T5DATA/eraleader/output/private_native/KR_new_verify_folder

실제 최초 확정 Plan/capture-root를 넣어야 하며 임의 예시 경로는 존재한다고 가정하지 않는다. 기존 영수증을 수정하지 않고 새로운 파일을 복원했다는 것은 공인 KRX/DART/SEC 역사 PIT 인증이나 실제 미래 대장주 적중률 측정이 아니다.

## 실제 로컬 실행 증거 및 이후 과제

- Mac의 기존 합성 KR+US 두 시장(first prospectively captured source)을 실제 새 CLI create → verify → restore 명령으로 각각 실행. 각 15개 원본/증거 파일 ZIP SHA 검증과 독립 score/feature 재계산 감사 + census SHA 인덱스 검증 통과; 기존 원본 SHA 모두 불변, API·실전 메시지0, 공식 대장주 승격0. Git-ignored output/native_evidence_archive_e2e_20261012/research_only_cli_results.json.
- tests/test_native_evidence_archive.py: 한·미 정상 백업/복원, 변조·손실/SQLite 뒤쪽 바이트/sidecar/symlink/숨김파일/ZIP path traversal, 기존 백업 덮어쓰기 거부, 원본 추후 변경 후 복원 copy 독립검증, 실제 CLI e2e. 프로젝트 분리된 원래 첫 native capture의 미커밋 7줄 변경은 이번 릴리스에 포함하지 않는다.
- 남은 별개 과제: 최초 예측 cohort 다수 보관·후속 결과 전수 관리, 현물 KRX/DART/SEC 역사 원천·상폐·기업행동·PIT, 실제 미래 outcome 관측. 외부 API D-017과 실제 T5DATA 재연결/재부팅 D-021은 최종 단계.
