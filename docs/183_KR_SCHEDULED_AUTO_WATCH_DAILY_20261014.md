# 183 — 한국 전체시장 WATCH·일일 보고 예약 실행 연결

- 일자: 2026-10-14 KST / 개발 ID: 6_1·6_2·6_3·6_5
- 브랜치: `feature/kr-marketwide-search-20261014` (원본 main은 변경하지 않음).
- 실제 새 기능: 기존 평일 18:40 launchd 설정 생성기에 `--auto-watch` 및 `--dart-cfs-root` 옵션을 추가. 기존 정상 `render_local_operations.py --marketwide-watch-auto` 경로를 그대로 재사용하여 검증된 시장자료 → 기존 5요소 부분 입력 → WATCH 50 → 당일 KST 일일 수익성 관찰 보고 → 웹 대시보드로 연결한다. DART 최초 원본 경로는 명시한 경우에만 읽기 전용 전달. 기본 기존 가격 검색 스케줄과 호환된다.
- 준비만 수행: launchd plist는 owner-only `output/` 아래 새 파일에만 생성. launchctl 설치/부팅 활성화·API 호출·실발송·매매 주문은 이번 작업 범위에 없음. 마켓 세션과 발행일 차이를 화면에 그대로 표시, 출처 지연 시 기존 보류 동작 유지.
- 재현 명령:

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/generate_marketwide_schedule.py --project "$PWD" \
  --source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
  --out "$PWD/output/kr_weekday_watch_daily_new.plist" \
  --auto-watch --dart-cfs-root /Volumes/T5DATA/eraleader/output/official_api_capture
# 실제 서비스 설치 없이, 생성된 ProgramArguments를 승인된 테스트 환경에서 직접 실행한다.
```

- 실제 SSD E2E (기존 보관된 공식자료): 생성한 `output/kr_weekday_watch_daily_1840_20261014.plist`의 ProgramArguments 1회 직접 실행, WATCH 50 · 일일 보고 50, 두 산출 모두 `ALREADY_PUBLISHED`(정상 멱등 재실행), 시장원천일 `2026-10-13`, 주문 0, API 0, launchd 설치 0. 감사 결과 `output/verification_logs/weekday_watch_daily_e2e_20261014.json`; `plutil -lint` OK, `py_compile` 및 `git diff --check` PASS.
- 변경 영향 테스트: `PYTHONPATH=src python3 -m pytest tests/test_marketwide_schedule.py tests/test_operations_one_command_auto_watch.py -q --tb=short` **20/20 PASS(exit 0)**. 자동 WATCH+일일 보고 긍정 경로/재실행, 옵션 일관성, 기존 예약 검색 동작, 파일 접근 안전 규칙 회귀.
- 범위 제한: 새 실시간 API 다운로드·산업성장/경쟁력 미확보 20점의 인위적인 채점·정식 대장주 판정·특정 투자전략 수신처/실거래 연결 없음. 실제 설치는 경로 고정·사용자 승인된 운용 인수에서 별도 진행.
- 다음 실제 기능: 검증된 최신 시장원본의 매일 증분 수집→본 준비된 스케줄 입력까지 자동 갱신(원본 및 공개시각 보존), 정식 5요소 중 미구현된 산업 성장성과 기업 경쟁력은 승인된 정의 및 공식 원천 확보 이후 연결. 운영 12항목 기준 API 제외 67% 추정 유지(기능 연결만으로 다른 부분 완료 승격 금지).
