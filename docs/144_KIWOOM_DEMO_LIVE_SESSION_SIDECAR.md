# 144 — 키움 모의 수급 최신 관측일 연구 패널 (기존 KRX·DART와 분리)

## 기능/개발 ID
- `1_2 / 3_2 / 4_2 / 6_2`; 기존 `143` 키움 모의 API 최초 실수신 후 최소 연결.
- 목표: 오늘 실제 **모의투자 서버**에서 수신한 선정 종목 기관·외국인 **주 수량**을 로컬 대시보드에 표시하되, 서로 다른 날짜의 KRX·DART 가격/연간실적/산업을 결합해 **사후 대장주 점수·투자 판단**을 만들지 않는다.
- 기존 main code/WATCH/재무 DB/랭킹 계산 규칙·키움 주문/실거래 경로 변경 없음.

## 구현
- `src/eraleader/kiwoom_live_research_panel.py`: 기존 `build_overlay(...,flows={})`를 이용해 현재 가격·재무·업종 원본 SHA와 10개 회사 종목코드/순서를 감사. 키움 원본 `verify_flow` SHA·PIT 수신시각 및 demo mode만 허용, 종목 중복/불일치 거부. KRX 날짜 `2026-10-08` ↔ 키움 날짜 `20261013` 형식 정규화 후 비교.
- `scripts/publish_kiwoom_live_panel.py`: `read_flows`의 capture manifest pin + 개별 응답 원본 SHA 확인. 새 폴더 `site/kiwoom_demo_YYYYMMDD/`의 HTML+JSON을 O_EXCL로 생성/원자 rename하고 기존 `site/index.html`에는 링크 1개만 원자 삽입. 재실행 덮어쓰기 금지 및 실패 롤백. 인증키·provider OAuth·실거래 주문 0.
- 새 JSON: `baseline_market_session`, `observed_flow_session`, `baseline_session_equal`, `DEMO_FLOW_DIFFERENT_SESSION_NOT_JOINED`, `score_eligible=false`, `investment_ranking_available=false`, `orders_enabled=false`, SHA. 5/20관측은 주(share)수량이며 다른 날짜의 수급을 기존 거래일에 소급하지 않는다.
- 키움 수신이 없는 후보(기존 나머지 9사)는 이번 별도 화면에서 **수급 관측하지 않은 것으로 유지**하고 0/중립 신호로 만들지 않는다. 기존 10사 `investor_flow_kr.html` 미수신/오래된 지표는 이전대로 보존.

## 실측(2026-10-13 KST)
- 기존 `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013`: KRX/DART `2026-10-08` 회사10사, first-SHA 기준 미완전 역사 PIT 연구용.
- Mac 공식 Kiwoom **demo** HTTP `ka10059` 삼성전자 005930, 거래일 `20261013`, **100관측행**, 최신일 당일, `historical_pagination_complete=false`, first-local-received 및 SHA pin 통과.
- 명령:
  ```sh
  cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
  PYTHONPATH=src python3 scripts/publish_kiwoom_live_panel.py \
    --candidate-json /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/basic_candidates_kr.json \
    --industry-json /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/industry_peers_kr.json \
    --kiwoom-manifest /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kiwoom_live_research_20261013_005930_v2/manifest.json \
    --site /Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/site
  ```
- 결과: `site/kiwoom_demo_20261013/index.html`, `report.json`, 기준일 불일치 `sessions_aligned=false`, scores_changed=false, official_leaders=0, orders=0. 로컬 `http://127.0.0.1:8770/kiwoom_demo_20261013/index.html` **HTTP200**, 기존 메인 `/index.html` HTTP200/새 링크 동작. 실제 sidecar `content_sha256` 재계산 일치. 동일 위치 재발행 거부.

## 제한 및 다음 작업
- **모의 서버 결과를 실제 생산시장의 투자수급·전향적 적중률로 인증하지 않는다.** 날짜/종목/주권클래스의 독립 교차원천, DART 재무 최신 공개시각/PIT, 공식 생산 수급/거래대금 단위 대조는 미완료.
- 다음에는 KRX/DART 동일 거래일 실데이터 새 수집/재무 기업 매핑의 날짜 일치를 확보한 후에만 수급과 가격 결합 후보를 검증. 기존 데이터 불일치면 별도 연구 패널 유지. 실거래/주문 자동화 금지.
