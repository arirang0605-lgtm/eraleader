# 186 — 공식 DART 현금흐름 필드 → 기존 WATCH·일일 보고 연결

- 2026-10-15 KST / 개발 ID: 3_2·4_1·6_1·6_2·6_4.
- 새 실제 기능: 기존 SHA 봉인 현금흐름 판본을 재사용 → 원본 CFS의 기업ID·회계연도·최초 수신시각·SHA 재대조 → 기존 WATCH50 중립 JSON/HTML에 필드 추가 → 기존 일일 보고 생성기에 전달. 별도 현금흐름 보고를 새로 복제하지 않는다.
- watch_cashflow_bridge.py와 publish_watch_cashflow.py --connect-watch로 연결. 기존 dart_annual_margin_context(include_cashflow=True) 검증·계산을 그대로 재사용하며 외부 API0.
- 같은 코드/명칭/회계연도·원본 first_receipt SHA와 원시 계산값이 맞는 회사에만 부착. 다른 기업·원본/미래시각·원문 변조는 거부. 결측/불완전 취득액 N/A 유지. 산업성장20·기업경쟁력20·정식100점·선정·주문 권한은 기존대로 N/A/0.
- 원래 WATCH 종목 순서·가격/실적/수급 점수·최초 관찰/발행 시각·시장일을 보존한 주석 추가 판본이다. 새 주석 판본의 실제 발행시각과 원본 WATCH 발행시각을 각각 기록하여 새로운 SHA를 과거에 존재했다고 소급하지 않는다. 보관 시장일10/13을 금일 시세나 신규 후보 선정으로 변경하지 않는다.
- 기존 publisher와 dashboard의 중복된 판본 해시식을 watch_version으로 공유하되, 현금흐름 필드가 없는 기존 판본의 해시와 HTML 바이트는 동일하게 유지한다.

## 실행

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/publish_watch_cashflow.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --watch-manifest "$PWD/output/early_leader_watch_queue/KR_20261013_f5a3041ca5838fd2/watch_queue.json" \
  --capture-root /Volumes/T5DATA/eraleader/output/official_api_capture --connect-watch
```

## 실자료와 검증

- 실물 WATCH50 안에서 CFO46·유형/무형취득 후 잔여현금42, 이전과 같은 가용률. 기존 현금흐름 판본 output/watch_annual_cashflow/KR_20261013_a0faa9c9733cc8a7는 ALREADY_PUBLISHED로 재사용.
- WATCH 필드 연결판 output/early_leader_watch_queue/KR_20261013_135e9ea6887231da/{watch_queue.json,index.html}.
- 일일 보고 output/early_watch_daily_briefs/KR_20261015_8991ad8428707f80/{brief.json,index.html}. 기존 일일 보고의 연간 영업이익률 관측24개 개선·22개 악화·4개 N/A는 그대로 두고 영업현금46개·취득후잔여현금42개를 추가. 상태전이/새 선정0.
- 원래 WATCH 발행 UTC 2026-10-14T11:08:02.652786와 추가 판본 발행 UTC 2026-10-14T23:22:39.743072(KST10/15)을 분리. 시장 관측일2026-10-13 유지.
- 세 화면(운영/WATCH/일일 보고) HTTP200. 반복 실행 시 세 출판 모두 ALREADY_PUBLISHED, 새 폴더0, 원본WATCH·현금흐름·부착WATCH·일일 보고 네 파일의 바이트 불변, 순서50/50 보존, API추가0·주문0.
- 집중 테스트 5파일(test_watch_cashflow_bridge.py, test_early_leader_watch_queue.py, test_early_watch_daily_brief.py, test_dart_cashflow_watch.py, test_operations_one_command_auto_watch.py) **51 PASS / FAIL0/ERROR0/SKIP0**, exit0. 정상 연결·N/A·과거자료 주석·회사/명칭/영수증/금액/소스 혼입 거부·미래 수신 거부·일일 보고 미래 필드 거부·기존 판본 호환·중복 및 기본 WATCH 회귀 확인. compile/diffcheck PASS.
- 증거: Git 제외 output/verification_logs/watch_cashflow_bridge_{scope,real,replay_http}_20261015.{xml,json}. 원시 CFS·main 및 타 프로젝트·사용자 미커밋5문서 보존.

## 남은 조건

- KRX10/14 0행·launchd 서비스 미설치 대기는 그대로. 이번 연결은 보관자료 연구용 사용 기능이며 최신 시장일의 정상 WATCH E2E/무인 운영 인수와 구분한다.
- Git 시작 SHA d7562dff8f95803d5d3ccd5d12164cc365926945, 기존 두 커밋 공개 승인/푸시 결과 보존. 새 연결 변경의 공개 범위는 기존 승인된 특정 두 커밋 밖이므로 먼저 검토한다.
- API 제외 12흐름 완료5·부분6·미완1의 약67% 유지. 현금흐름 필드 연결을 정식 경쟁력20점 완성으로 승격하지 않는다.
