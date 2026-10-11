# EraLeader 6_4 / 6_5 — 기존 예약 배치 뒤 로컬 오류 원장 옵트인 연결

2026-10-11 KST. 기존 `local_schedule.py` 가격 / WATCH / native Top-K 성숙도 자동 배치 및 `local_failure_outbox.py` 로컬 원장/ZIP 안전검증 로직은 **변경하지 않고**, `scripts/run_local_scheduled.py` 명시 옵션 `--local-outbox-dry-run`만 연결했다.

## 구현 계약

- 기본(옵션 없음): 기존 JSON 출력, 배치 동작, 기록·백업·launchd 동작 전부 이전과 동일. 로컬 outbox를 호출하지 않는다.
- 옵션을 켠 **현재 단일 CLI 실행**: 선택한 기존 가격/WATCH/maturity 배치를 먼저 실행하고, 그 이후 메인 운영 체크포인트 3종을 읽는 `run_local_failure_outbox(project)`를 한 번 호출한다. 오류/복구는 **기존 백업 ZIP 및 live 파생 보고서의 로컬 SHA와 신선도**에 한정; 공급자 장애·시장 지표 판단 또는 실전 미래 리더 알림이 아니다.
- 예약 결과가 `SKIPPED_STALE_CACHE`이면 캐시 문제를 기존 운영 원장으로 별도 기록할 수 있으나, 예약 자체가 성공한 것으로 출력하지 않는다. 출력 형식은 옵션 사용 시에만 `schedule` / `local_failure_outbox` 별도 중첩 JSON; `messages_sent=0`, `external_api_calls=0`, `official_leaders_confirmed=0`, `actual_future_leader_skill_certified=false`.
- 원장 백업이 성공적으로 SHA 검증된 `LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP`가 아니면 **결합 결과를 성공으로 출력하지 않는다**. 로컬 lock 충돌, 송신됨 주장, 공급자 인증/공식 리더 주장도 fail closed. 배치 자체가 실패하면 원장 점검을 한 번 시도하되 원래 배치 오류가 항상 우선; 원장 오류는 보조 메모로만 남긴다.
- **`--generate-plist`와 옵트인 옵션 동시 사용 거부**. launchctl load, 자동 등록, 외부 네트워크/API, 이메일·텔레그램, 주문, SSD 탈착·재부팅, 원본 시세 변경은 모두 수행하지 않는다.

## 실행

```bash
cd /Volumes/T5DATA/eraleader
# 현재 데이터가 오래되면 가격연구 스케줄은 안전하게 SKIPPED_STALE_CACHE:
python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --local-outbox-dry-run

# 기존 WATCH/maturity 옵션과도 조합 가능하되 명시적 실제 config가 필요:
# python3 scripts/run_local_scheduled.py --project ... --watch-only --watch-research-config ... --local-outbox-dry-run
# python3 scripts/run_local_scheduled.py --project ... --maturity-only --ranked-maturity-config ... --local-outbox-dry-run
```

## 검증과 제한

- 선행 RED: 신규 테스트는 기존 CLI에 옵션이 없어 10 FAIL, 변경 구현 뒤 12/12 PASS. 옵션 없는 기본 동작, 3모드 호출순서, plist 동시 옵션 금지, scheduler 실패 시 주오류 보존, outbox 실패·잠금·가짜 발송/가짜 공식 리더 결과 거부, 중첩 출력 정확성을 테스트.
- `PYTHONPATH=src python3 -m pytest tests/test_scheduled_failure_outbox_bridge.py -q --tb=short` 및 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short`로 재검증한다.
- 현재 실제 KR 2026-10-02 / US 2026-02-26 cache는 오래되어 정상 실전 추론 불가. 메인 WATCH/native Top-K 운영 체크포인트 미설정은 `UNCONFIGURED`; 실전 성능 N/A, 실제로 미래 대장주를 인증한 사례 0.
- 다음 2_2/2_5 역사적 공식 issuer/share-class, 상폐 현금·분할/배당/공시 PIT 독립 출처 인증과 5_5 시점동결 미래 코호트 성숙 outcome 검증은 API 또는 검증 가능한 원본 없이는 미완료. D-017 외부 API는 최종 단계, D-021 SSD 물리 재연결/맥 재부팅도 최종 단계.

## 2026-10-11 실제 Mac 검증

- 처음 기존 CLI에는 플래그가 없어서 신규 12건 중 **10 RED FAIL**, 구현 후 신규 **12/12 GREEN**. 전체 1,411개 collected/pytest PASS(exit0), handoff 30 IDs/40 필수 PASS, py_compile/working-tree diffcheck PASS.
- 실제 운영(합성이 아닌 오래된 캐시) `python3 scripts/run_local_scheduled.py --project /Volumes/T5DATA/eraleader --local-outbox-dry-run`: **exit0**, `schedule=SKIPPED_STALE_CACHE`, `local_failure_outbox=LOCAL_DRY_RUN_ALERTS_VERIFIED_BACKUP`, `new_events=0`, `total_events=1`, `active_local_faults=1`; 실제 전송/API 각각 0. 동일 stale 원인 중복 등록하지 않았으며 기존 가격 배치 verified checkpoint 원본 SHA가 실행 전후 같음.
- 새 ZIP은 로컬 파생 SQLite/JSON/HTML만 포함. 보고의 `LOCAL_ARTIFACTS` 복구는 가격 원천·issuer PIT·미래 성과를 인증하지 않는다. 중간 산출물/pytest 로그는 gitignored `output/verification_logs/`에만 보관.
