# 143 — KRX/DART 당일 연구 수집 → 동일 원본 SHA 후보·산업 → 키움 모의 수급 결합 게이트

**날짜:** 2026-10-13 KST
**개발ID:** 2_2·2_5·4_2·5_5·6_2·6_5

## 기존 기능 재사용 및 변경 경계

- 기존 공식 `official_kr_daily_pipeline.capture_and_publish_kr_day`(KRX 코스피·코스닥 + DART 전체 일별 공시 → 연구 WATCH·HTML/보고), 공식 `official_basic_candidates`와 `official_industry_peer_screen`, 기존 `kiwoom_daily_runner.run`(모의 조회 전용) 정상 코드를 **재작성하지 않음**.
- 신규 `src/eraleader/official_kiwoom_daily_bridge.py`: 명시 KST 오늘·평일·19시 이후만 당일 공식 자료를 검사/명시 수집. **기본은 네트워크0 CHECK-ONLY**. 공식 수집 결과가 있어도 별도의 **동일일자 후보·산업 비교 코호트가 완성될 때까지** `WAIT_SAME_DAY_CFS_INDUSTRY_COHORT` 반환, 키움0.
- 별도 후보 비교 JSON 2개의 SHA/identity/first decision clock을 기존 `build_overlay(..., flows={})`로 검사. 또한 `basic_candidates_kr.json.source_watch_run_id`가 지정하는 실제 `runs/<ID>.json` 원본 기록의 **KRX 두 공급자와 DART 첫 수신 PIN·DART 전 페이지 묶음 SHA**를 당일 `official_api_pit_research.json`의 대응값과 비교. 시각·날짜가 같더라도 서로 다른 공급자 최초원본이나 과거 WATCH를 합치지 않음.
- 신규 `scripts/run_official_kiwoom_research.py`: `--day`, `--official-out`, `--cohort-root`, `--codes`, opt-in `--capture-official`, opt-in `--apply-demo-flow`. `--capture-official` 시에는 **이미 존재하고 소유자 전용인 --capture-root를 명시**해야 하며 사용자 Mac 로컬 protected official credentials만 사용. 실전계좌/OAuth 토큰/주문·메시지 외부발송 및 automatic scheduler 설치 없음.
- **중요:** `reject_empty_live_krx()`는 기존 공식 fetch가 가져온 **동일 raw bytes**를 추가 네트워크 호출 없이 수입 전 점검. KRX 코스피/코스닥 중 일별 거래관측 0행이면 `OFFICIAL_KRX_DAILY_ROWS_NOT_YET_AVAILABLE`로 공식 최초 수신 아카이브 발행 이전에 중단. 이것은 거래소 휴장 확정 판정이 아님. DART 원문은 기존 검증기에 그대로 넘김. API 0행을 당일 거래 세션·후행 라벨로 사용 금지.
- 결과는 언제나 연구용(official_pit_certified=false, orders=0), 현재 주권/상장폐지/기업행동 역사·공시 최초 공개시각 및 미래 Top-K 적중률 독립 인증 N/A.

## 실기기 / 독립 사실과 한계

- Mac/T5DATA 온라인, 원래 공식 credential Mac 내부 0600 파일 존재, KRX/DART 설정 사전검사 준비됨(키 원문 노출0).
- 2026-10-13 KST 21:08경 기존 KRX 코스피 공식 endpoint를 별도 직접 read-only 진단한 응답 **17 byte**, `OutBlock_1=[]` → **0행 / NO_DAILY_ROWS**. 이것만으로 KRX 전체 시장 휴장/장애라고 단정 금지. 당시 10/13 공식 연구 원장 새 디렉터리 미발행.
- 최초 opt-in 공식 수집 시도는 **독립 개발 worktree의 디폴트 capture-root가 존재하지 않아 BLOCKED**였고, API 인증 불량이라고 주장하지 않음. 이후 실수집 시 `--capture-root /Volumes/T5DATA/eraleader/output/official_api_capture`처럼 **존재하는 명시적 0700 폴더**를 요구하도록 수정. KRX 최신 0행 확인 이후 원문 재호출·잘못된 fallback 데이터 생성은 실시하지 않음.
- 실제 보관된 2026-10-08 공식 DART 992행+KRX 첫 원문에 대한 read-only `_inspect_official` 계약 통과: 최초 공급자 수신 PIN 3개와 전 페이지 DART manifest SHA 확인. **신규 10/13 금융 cohort 생성 성공이나 실전 대장주 판단을 의미하지 않음.**
- 사용자 키움 모의 10/13 두 종목 연구 원장은 전 세션에 **독립 HTML**로 이미 보존돼 있음. KRX 10/13 공식+기업 재무·산업 cohort가 새로 생성될 때까지 그 연구 관측치를 과거 10/08 후보의 점수·순위에 합치지 않는다.
- 전체 시스템 자동 일별 갱신·휴장 공식 달력 인증·실전 장기간 운영 및 launchd 설치는 **미완료**.

## 검증

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest \
  tests/test_official_kiwoom_daily_bridge.py \
  tests/test_official_kr_daily_pipeline.py \
  tests/test_official_basic_candidates.py \
  tests/test_official_industry_peer_screen.py \
  tests/test_kiwoom_daily_runner.py \
  tests/test_kiwoom_shared_daily_batch.py \
  tests/test_kiwoom_shared_research_sidecar.py \
  tests/test_kiwoom_investor_flow.py \
  tests/test_kiwoom_live_research_panel.py \
  tests/test_kiwoom_gateway_cli.py -q --tb=short
```

- **144 PASS / 실패0 / 오류0 / skip0 / EXIT0**, JUnit `output/verification_logs/official_kiwoom_daily_refresh_20261013.xml`; Python compile 및 staged Git 보안검사 별도 시행. 전체 장기 회귀는 미실행.
- 합성 실제 `runs`/official same-day source 3 SHA 일치·불일치, DART manifest 변조, 후행 금융 의사결정, 틀린 기준일, 0 KRX행, CLI 기본 CHECK-ONLY·명시 root 없이 실제 수집 요청 거부 및 모의투자만 통과 테스트.

## 다음 실행 조건

공식 10/13 KRX 양시장 조회에 **실제 거래일 row>0**가 반환된 뒤 새 `--official-out`과 기존 보호 원본 root를 명시하여 KRX/DART 연구 원본을 1회 수집하고, 별도의 실제 DART 재무 연도 코호트·현재 업종 첫 SHA를 새 연구 run에 결속하여 동일일자 후보/산업 JSON을 만들 것. 모든 PIN이 일치하면 모의 키움 1~5개 종목 측정 연구 페이지를 붙이되, 공식 대장주 자동 확정·실거래·주문은 계속 차단. 완료 후 사용자 승인 시 정기 잡 설치 및 물리 SSD 복구 테스트(D-021 최종).
