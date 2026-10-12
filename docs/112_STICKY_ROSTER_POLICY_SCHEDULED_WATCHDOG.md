# EraLeader 4_1 · 6_5 — 엄격 거래소 명부 WATCH 정책 무결성 DRY-RUN 자동감시

2026-10-12 KST. 제110차 엄격 로스터 정책이 다음 WATCH 실행 전에 조용히 손상·소실되어도 알 수 없던 운영 공백을 메운다. KRX/DART/SEC 실제 원본 및 독립시각 인증, 실전 알림·매매, SSD 실제 탈착은 이 작업에 없다.

## 개발된 기능

- 새로운 src/eraleader/exchange_policy_watchdog.py 는 기존 read-only verify_exchange_roster_policy 재사용: KR/US 시장별 정책·guard·잠금 sentinel의 모두 정상 여부를 직접 점검한다. 원래 WATCH/Score/Top-K·시장 원시자료 및 기존 첫 정책을 수정하지 않는다.
- 최초 정상인 policy의 정확한 SHA-256을 원래 source와 분리된 output/exchange_policy_alerts/genesis.json + history.jsonl SHA-chain에 시장별 고정한다. 이후 정책/guard/lock **3개 모두 사라져도** 최초 신뢰 SHA·이전 기록으로 재인식한다. 일부 소실, 정책 재포맷, symlink, 기존 policy와 다른 SHA로 자기일관성 있게 재봉인한 경우도 이상 경고한다.
- 정책을 아직 활성화하지 않은 시장은 NOT_ACTIVATED(정상/인증의 의미 아님)로 구분. 경고 코드는 POLICY_DISAPPEARED, INCOMPLETE_POLICY, UNSAFE_OR_CORRUPT_POLICY, PINNED_POLICY_REPLACED, POLICY_RESTORED. 같은 이상 반복은 신규 경고를 중복 생성하지 않고 원래 상태 회복을 별도 표기.
- independent 최초 봉인 SHA root fingerprint가 다른 출력폴더로 바꿔 검사하는 다운그레이드를 차단. JSON 정확한 바이트·연속 seq/event 해시·UTC 시각 역행을 검증하며 감시 자체 원장 변조·부분 소실은 새 genesis로 초기화하지 않고 중단한다. 감시 중 엄격 정책 writer lock을 잡고 있다면 완료로 위장하지 않고 종료한다.
- 로컬 전용 report.json + site/index.html, 시장별 상태·신규 경고·첫 정상 SHA. 종목ID/원본 경로/주가/키 없음. 외부 API 호출 0, 메시지 전송 0, 공식 대장주 승격 0, 실전 PIT 인증 false.
- 독립 CLI scripts/run_exchange_policy_watchdog.py 와 기존 예약 스크립트의 opt-in --exchange-policy-out 옵션 지원. 정상 배치 후 점검, 배치 실패 시에도 별도 경고시도(원래 실패 유지). 플리스트 생성/설치와 결합 금지. 기존 옵션 없이 작동 결과 그대로 보존.

## 재현 명령

    cd /Volumes/T5DATA/eraleader
    python3 scripts/run_exchange_policy_watchdog.py --project /Volumes/T5DATA/eraleader --policy-out /Volumes/T5DATA/eraleader/output/YOUR_STRICT_WATCH_OUTPUT
    python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --exchange-policy-out /Volumes/T5DATA/eraleader/output/YOUR_STRICT_WATCH_OUTPUT
    PYTHONPATH=src python3 -m pytest tests/test_exchange_policy_watchdog.py -q

이 명령은 실제 엄격 모드로 WATCH를 실행했던 원래 output 경로를 입력해야 한다. 자동 스케줄러 설치/수정은 하지 않는다. 최초 감시가 있기 전에 모든 policy/guard/lock이 사라졌다면 이전 엄격 정책이 있었는지 추정하지 않는다.

## 테스트 범위와 한계

신규 테스트: 비활성/정상 구분, 최초 KR/US SHA 잠금, 모든 정책 파일 소실·반복·복구, 부분 삭제/변형/심볼릭 링크, 자기일치 새 seal SHA 위조 탐지, 감사 이력 변조·시각 역행·root 교체 차단, CLI 현지 실행/사이트, 기존 예약 정상/실패/플리스트 보존. 단일 로컬 관리자가 원본 정책과 별도 감사 폴더 전체를 동시에 위조하거나 삭제하는 것은 탐지할 수 없다. OS 시계·공급자 원문은 독립 공증이 아니며 실제 최초 WATCH 미래 outcome·정밀도·오탐률과 공식 역사적 PIT 인증은 아직 불가능하다. D-017 외부 API 및 D-021 하드웨어 복구 검증은 최종 단계에 남긴다.

## 최초 기록 이후 로그 롤백 방어 보강

- 감시 전용 genesis에 더해 최초 관측 이벤트의 정확한 SHA와 genesis SHA를 별도 O_EXCL `first_event.json`으로 고정한다. 이후 전체 history.jsonl과 report.json을 함께 지우거나, 원래 첫 로그 영수증을 바꾸거나 삭제하더라도 재등록 없이 명시적 실패한다. 단일 로컬 관리자가 감사 폴더 자체를 통째로 없애거나 신뢰 파일을 일관되게 모두 위조하는 공격을 독립적으로 공증할 수는 없다.
- 별도 report.json의 `chain_head_sha256`·개수·시장 상태/경고·인증 및 전송 금지 선언을 원래 SHA-chain의 마지막 이벤트와 교차 검사한다. 유효한 이벤트 줄을 끝에서 삭제하거나 보고서의 가짜 공식 대장주 인증을 끼워 넣으면 재생성하지 않고 차단한다.
- read-only 수동 무결성 감사도 별도의 .checks.lock 공유 잠금 아래 수행하여 동시에 writer가 파일을 갱신 중인 상황을 정상으로 오인하지 않는다. 감시 로그 심볼릭링크는 접근하기 전에 거부한다. 파일 간 쓰기 도중 crash가 발생하면 임의 자동치유/재봉인을 하지 않고 실패 처리하며 백업에서 사람의 증빙 확인 후 복구해야 한다.
- 이 검증은 **로컬 원장·원본 정책 변경 탐지**이지 독립 타임스탬프/PIT 데이터 출처 진위 검증이 아니다. 자료 공급자가 주장한 상장 클래스/법인 신원과 실제 사전 WATCH 미래성과는 여전히 인증되지 않는다.
