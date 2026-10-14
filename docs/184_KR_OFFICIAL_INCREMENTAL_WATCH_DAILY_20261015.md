# 184 — 공식 KRX 일별 증분 갱신 → WATCH·일일 보고 연결

- 일자: 2026-10-15 KST / 개발 ID: 1_1·1_5·2_1·2_3·6_1·6_2·6_4·6_5.
- 브랜치: feature/kr-marketwide-search-20261014, 시작 SHA 2cd5bbd76adc18ad47d745e02d9a7959a975ab1b.
- 새 입력→출력: 누락된 마감일 공식 KRX 양시장 수신 → 기존 receipt SHA·종목/일자 검증 → 기존 가격 모델과 DART 캐시 결합 → 불변 marketwide JSON → 기존 부분5요소/WATCH·일일 보고·웹 파이프라인.
- 신규 official_market_incremental.py 및 run_marketwide_daily.py가 기존 공식 수신/검증·가격 계산·coverage 발행·render_local_operations.py를 재사용한다. 기본은 저장본만 읽으며 --apply-official 때만 누락된 공식 KRX 조회를 실행한다.
- 캡처는 해당 feature/output의 새 경로에만 추가. 원본 main, CycleOS 가격 캐시, SharedBrokerAPI 및 사용자의 기존 미커밋 5문서는 보존. raw/SQLite/키/output은 공개 Git에서 제외한다.
- 시점: KST 19시 이전에는 당일 수신을 시도하지 않음. 날짜 간격은 평일 후보일을 요청하고 실제 양시장 행이 있는 경우만 거래 관측일로 발행한다. 0행을 공식 휴장일 증명으로 주장하지 않는다.
- 중복/지연: 기존 양시장 수신 재사용, 중간 실패 후 성공한 한 시장 재사용, 동시 수신 파일 잠금. 0행은 실제 원본을 보존하고 당일 중복 조회 없이 다음 KST 날짜에 재시도. 한 시장만 0행이면 새 시장판을 발행하지 않는다.
- 재무·업종은 최초 검증 캐시의 SHA/관측일/이용 가능 시각을 유지하여 동일 코드+명칭+시장에만 이월. 신규 공시 갱신 아님을 WATCH JSON/HTML·일일 보고에 표시. 다른 시장일 키움 수급은 N/A로 초기화. 정식 산업/경쟁력 점수 및 대장주 확정은 기존대로 N/A/0.
- 기존 WATCH 링크가 자정 이후 한국 시장일을 UTC 날짜와 비교해 빠지는 문제를 KST 기준으로 수정. CLI 테스트의 고정 날짜가 경과하여 지연 차단되는 문제는 운영 기준을 완화하지 않고 테스트 자료 시각을 실행일에 맞춰 수정했다.

## 실행

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/run_marketwide_daily.py --project "$PWD" \
  --source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
  --capture-root "$PWD/output/official_api_capture" \
  --existing-capture-root /Volumes/T5DATA/eraleader/output/official_api_capture \
  --dart-cfs-root /Volumes/T5DATA/eraleader/output/official_api_capture --apply-official
```

새 예약 설정: generate_marketwide_schedule.py의 --auto-watch --update-official --capture-root 및 --existing-capture-root 옵션으로 위 실행을 평일 19:40에 연결한다. --update-official이 없으면 기존 18:40 로컬 재발행 동작 유지. 실제 launchd 서비스 설치는 이번 범위에 포함하지 않았다.

## 검증과 실제 결과

1. 기능·변경 영향: tests/test_official_market_incremental.py, test_marketwide_schedule.py, test_operations_one_command_auto_watch.py, test_early_watch_daily_brief.py, test_early_leader_watch_queue.py, test_official_partial_factor_bridge.py — **71 PASS / FAIL0 / ERROR0 / SKIP0, exit0**. 정상 수신→가격 계산→WATCH3→보고3, 재실행 API0, 저장본-only, 두 날짜 누적, 다음 날짜 재시도, 부분 실패 복구, 수급 이월 차단, 회사 변경 결측, 원본 변조/미래일/동시 실행 확인. 정상 수신 테스트의 HTTP 응답은 합성 시험자료이며 실자료로 주장하지 않는다.
2. 실제 공식 조회 E2E: KRX 2026-10-14 코스피/코스닥 **2회 조회 성공, 양쪽 0행 NO_DAILY_ROWS**. 최초 수신 UTC 2026-10-14T19:10:44/46, 실제 KST 수신일 10/15. 최신 검증 시장일은 10/13로 유지. 지연 판단으로 새 WATCH·보고를 생성하지 않고 기존 발행본 보존. 최신일 정상 발행 E2E는 공급자 행이 반환되어야 확인 가능.
3. 준비한 output/kr_official_incremental_watch_1940_20261015.plist의 ProgramArguments 재실행 **exit0/API0**, 동일 0행 보존·WATCH 지연 HOLD 확인. plutil -lint 및 Python compile/diffcheck PASS. launchd 설치·실발송·매매 주문0.
4. 증거는 Git 제외 output/verification_logs/{official_incremental_scope_20261015.xml,official_incremental_real_20261015.json,official_incremental_plist_replay_20261015.json}. 원시 수신은 output/official_api_capture/first_*에 보존.

## 남은 조건·다음 작업

- 공급자 최신 KRX 10/14 행 반환 후 다음 날짜의 정상 갱신→WATCH50·일일 보고·대시보드 실자료 확인. 동일 원인 반복 조회는 하지 않는다.
- 무인 서비스 설치 및 운영 인수는 미완. 공식 DART 신규 재무 갱신, 산업성장20·기업경쟁력20 자료 연결은 별도 미완료 기능이다.
- API 제외 실운영 진행률은 기존 12흐름 완료5·부분6·미완1, (5+6×0.5)/12 = **약67% 유지**. 새 코드/지연 경로 확인을 최신일 정상발행·서비스 설치 완료로 승격하지 않는다.
