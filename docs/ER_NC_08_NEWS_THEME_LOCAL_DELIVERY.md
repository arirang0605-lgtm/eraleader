# ER-NC-08 — 뉴스·테마 연구 웹 / 일·주·월 / DRY-RUN (2026-10-13)

**상태: 로컬 읽기 전용 확장 구현·변경 범위 테스트 PASS (실전 운영 인증 아님).**

## 선행 조건과 기존 코드 보존

- ER-NC-B00 백업 두 계층(T5DATA+Mac 독립 암호화)·SHA256·SQLite 일관성·실복원 시험 **PASS** 후 독립 feature worktree에서 구현. 이전 ER-NC-06 `afef097360c16b0c08e3037e62be2bff0cd24142` 다음 단계.
- 기존 EraLeader `main` 및 외부 MarketOS/CycleOS/기존 백테스트 엔진, 원시 KRX/DART/SEC 수신 파일, WATCH/후보 SQLite, 개인키/메시지 발송기는 수정하지 않음. 미커밋 `native_first_capture.py` 6추가/1삭제 및 기존 별개 ER-NC-06 원형 미추적 파일 보존.
- `delivery.py`는 **기존 함수의 keyword-only 기본값 False만 추가**해 NEWS OFF 기존 HTML·index의 실제 바이트를 Git 기준 `bbe9be5`와 같게 유지. NEWS ON에서만 독립 뉴스 연구 페이지로 연결 링크를 표시.

## 코드 및 실제 경로

- 새 `src/eraleader/news_theme_delivery.py`: 기존 `BASE_CSS` 재사용. 정식 EraLeader 점수/후보 변동 없이 ER-NC-06의 검증된 뉴스↔시장 반응과 ER-NC-04의 PIT 테마 가격상태를 **별도 카드·표**로 출력. 재료 `catalyst_state`와 테마 `state` 분리, UNKNOWN/STALE 경고, 각 근거시각과 연구용 표시. ER-NC-07 전략은 실제 신호가 검증되기 전 `NOT_READY`/`UNKNOWN`, `NO_ORDER` 상태만 표시하도록 제한.
- `write_research_bundle(report, new_output_root, enabled=True)`: 신규 격리 디렉터리에 `site/er_nc08_research.html`, `reports/er_nc08_daily.md`, `reports/er_nc08_weekly.md`, `reports/er_nc08_monthly.md`, `alerts_preview.json` **5개 파일** 생성. 새 임시 폴더에서 파일 전체 작성 후 신규 디렉터리로 게시, 동일 SHA 내용 재실행은 불변, 다른 기존 내용·symlink·경로 재사용 덮어쓰기 거부.
- 시장 자료와 뉴스 자료는 동일 임의 백필 시점으로 바꾸지 않고 `as_of`·`market_data_available_at`·`market_session` 시간 순서 검증. 미래 뉴스·가격·테마·전략 판정을 거절. 미검증 공식 leader/자동주문 주장 거절.
- alert 미리보기는 `NEWS_INVALIDATED`, `NEWS_STALE`, `THEME_REACTIVATING`, `THEME_WEAKENING` 등 연구 상태로만 deterministic SHA dedup. **메시지/실주문 0건**, 기존 발송 outbox DB 변경0. 과거에 같은 경보를 실제로 전송했다는 영수증이 아님.
- 새 `scripts/run_er_nc08_delivery.py`: 기본 실행 `NEWS_OFF_NO_WRITE`, 명시 `--news-enabled`가 있어야 진행. 별도 사용자 보관 SHA pin을 검증한 정형 파생 연구 JSON만 read-only로 읽고 위 5파일을 새 디렉터리에만 생성. 최대2MB/중복 JSON 키/잘못된 SHA/현재 이후 시점/일반 symlink fail closed. 비공개 기사 원문/키·민감경로를 stdout에 출력하지 않음.
- 3종 보고서는 **동일한 현재 연구 snapshot을 각 발행 주기별 양식으로 출력**한다. 7일/1개월 누적 집계, 실제 라이브 뉴스 공급자 확보, 지속형 outbox 발송, 모바일 기기 실물 테스트는 후속 과제이며 이 단계의 PASS로 인증하지 않음.

## 실제 테스트

- 신규 `tests/test_news_theme_delivery.py` **22 PASS**. `tests/test_er_nc08_cli.py` **6 PASS**, 신규 합계 **28 PASS EXIT0**.
- 기존 뉴스 PIT 어댑터/시장 진단/CLI/WATCH 회전/테마 라이프사이클/가격보고·dashboard/시장국면 등을 묶은 **10개 테스트 모듈, 204/204 PASS EXIT0**.
- 재현: `PYTHONPATH=src python3 -m pytest tests/test_news_theme_delivery.py tests/test_er_nc08_cli.py tests/test_news_market_response.py tests/test_er_nc06_cli.py tests/test_news_catalyst_adapter.py tests/test_news_rotation_context.py tests/test_watch_operating_reports.py tests/test_peer_score_dashboard.py tests/test_theme_lifecycle.py tests/test_market_regime_experiment.py -q --tb=short`.
- 확인 항목: NEWS OFF 기존 HTML와 index Git 기준 **바이트 일치**, NEWS ON link/화면, 일·주·월 보고, 모바일 viewport/CSS, URL·HTML/Markdown 인젝션 escaping, 같은 입력 재실행 SHA 불변, 이미 존재한 출력 거부, 출처 미래정보·권리 검증 부족·김정수 전략 미포함, 실제 외부전송0.

## 운영 사용 예시 (합법적 파생 JSON과 독립 SHA를 준비한 후)

`PYTHONPATH=src python3 scripts/run_er_nc08_delivery.py` → NEWS OFF, 파일 생성 0.

`PYTHONPATH=src python3 scripts/run_er_nc08_delivery.py --news-enabled --derived-research-json /path/to/pinned_research.json --expected-sha256 <사용자가_별도확인한_SHA256> --new-output-root /path/to/new_empty_destination`

실제 발행이 확인된 뉴스 공급자·공시 최초 공개시각·권리·전체시장 PIT, 공식 미래 리더 성과는 **N/A**. 다음: 기존 scheduler/웹 기동·발행시각과 자연 연결하고 뉴스 장애시 DATA DEGRADED 유지, 실제 실수집 뉴스 공급자 연결·5/20거래일 관측 후 통합 ER-NC-09/10 테스트. 남석관/유목민 원형 전략 최종 원문 검증은 다른 ER-NC-07 브랜치에서 보류.
