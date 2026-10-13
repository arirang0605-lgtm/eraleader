# 145 — KRX·DART·키움 최초수신 3원천 동일시점 가용성 게이트

## 작업 식별 및 인수 범위
- EraLeader ID: **1_2 · 2_2 · 3_2 · 4_2 · 6_2**. 기존 1_1~6_5 번호 체계 및 계산·원장을 유지하는 추가 기능.
- 목적: **같은 일자**라는 이유만으로 KRX 시장 가격, DART 공시, 키움 기관·외국인 수급을 합산하거나 미래 대장주로 승격하지 않도록 **원본 SHA/수신시각/종목/품질**을 자동 검사한다.
- 실제 금융정보 발행·이용 가능 시각(PIT), 법적 기업/주권 클래스 및 완전한 전시장 종목군/독립 수급원 검증을 이 모듈만으로 보증하지 않는다.

## 코드와 입력
- `src/eraleader/official_three_provider_session_gate.py`: 세 공급자 KRX KOSPI/KOSDAQ 및 DART의 기존 **first raw+first receipt** 두 파일을 **READ-ONLY** 검증; 사용자 지정 독립 첫 영수증 SHA256, 원본 raw SHA/행수/품질/수신 UTC, 중복 종목·거래일·미래시각 검사. 증권코드 6자리·키움 모의 `ka10059` 보고 SHA/20관측·동일 종목·시장세션을 추가 감사.
- T5DATA 외장 매체는 파일 소유자 실행권한으로 원래 0600이 0700으로 표시될 수 있어, **그룹/기타 권한 모두 0**과 소유자 UID/파일 형식/원본 SHA를 모두 요구한다. 기존 `official_api_pit_bridge.py` 검증기를 수정/우회하여 대장주 허가하지 않음.
- `scripts/publish_three_provider_session_gate.py`: 기존 비공개 ZIP·암호·API key는 요청하지 않음. 명시적인 3개 첫 캡처 경로와 독립 SHA, 키움 manifest, 시장 날짜, 종목 코드, 기존 사이트를 받아 별도 `provider_session_YYYYMMDD/{index.html,report.json}` 작성/원자 게시. 기존 사이트 메인에는 링크 1개만 추가, 재실행 덮어쓰기/부분 게시 차단.
- 결과 상태: `PAUSED_MISSING_OR_INCOMPLETE_OFFICIAL_EVIDENCE` 혹은 `SAME_DAY_RESEARCH_OBSERVABLE_NOT_CERTIFIED`. 후자도 **매수/매도/공식 leader/실행권한 0**이며 연구용 동시점 관측이 가능하다는 뜻뿐이다.

## 실제 공인 HTTPS 신규 수신 — 2026-10-13 현지 한국시장일
- 기존 정상 공식 KRX/DART 키를 Mac 소유자 비공개 저장소에서 재사용, 외부 API **KRX 코스피·코스닥 각각 1회, DART 첫 페이지 1회**, 새 raw/first receipt 두 파일씩 별도 비공개 경로 생성. 키 원문/발급·교체/원시 데이터 공개 Git 업로드 0.
- **코스피 원문 HTTP 정상이나 거래관측 0행**, **코스닥도 0행** (`quality=NO_DAILY_ROWS`). 이는 해당 시각 응답이며 시장 전체에 데이터가 존재하지 않는다는 일반 결론은 아님.
- DART 공시 **첫 페이지 100건**, 일간 총 건수보다 적어 `INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY`; **전수 수집 아님**.
- 키움 demo `ka10059` 삼성전자(005930) **100관측행**, 첫 Mac 수신·SHA 별도 보관. 모의환경은 실제 생산시장 수급의 독립 증거가 아니다.
- 실제 수신자료와 독립 SHA pin으로 감사 결과:
  `blockers=[KRX_ONE_OR_BOTH_MARKETS_EMPTY, SELECTED_ISSUE_NOT_IN_SAME_DAY_KRX, DART_DAY_NOT_COMPLETE_OR_PROVIDER_NO_DATA]`;
  `can_compare_same_session_research=false`,
  `historical_source_publication_pit_certified=false`,
  `investment_leader_score_available=false`,
  `official_leaders=0`,
  `orders_enabled=false`.
- 로컬 EraLeader 화면: `http://127.0.0.1:8770/provider_session_20261013/index.html`. 상태를 정직하게 **PAUSED**로 게시해 기존 10월 8일 분석/10월 13일 모의 수급을 부적절하게 섞지 않는다.

## 검증과 운영 기준
- 합성 증거: 양시장 양수 관측·DART 첫 페이지 완전·동일 종목·키움 20관측 시 **연구용 조건부 가용**, 생산 PIT와 매매는 계속 N/A. KRX 0행, DART 불완전, 일자/issuer 불일치, 원본 SHA 변조, 과거 의사결정에 미래 시각 삽입, 실계좌 프로필, 모의 응답 손상 모두 차단. end-to-end CLI 원자 새 게시/재발행 거부 테스트.
- 출력 JSON에는 **증권사 API 인증키·OAuth 토큰·원시 시세·공시 본문** 없음.
- 다음: KRX 양시장 실데이터가 정상 수신된 다른 영업일과 DART 전체 페이지 수신/법인·주권 매핑을 먼저 확보한 다음 단일 종목의 독립 동일시점 연구 가능 여부를 재확인; 이후에야 prospective 성능 검증. 지속적인 자동 재시도/불필요한 API 호출 금지.
