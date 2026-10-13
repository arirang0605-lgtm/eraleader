# 143 — EraLeader 키움 REST 모의·실전 구분 및 읽기 전용 기관·외국인 수급

## 목적 / ID
- 개발 ID: `1_2 / 2_1 / 3_4 / 4_1 / 6_2`.
- 기존 **KRX→DART→선별 10사 가격·연간실적·산업 비교** 유지.
- 최초 기관·외국인 수급은 **선정된 1~20개 주권**만 조회한 후 결합하는 별도 sidecar.
- 실전 투자 계좌의 **주문·잔고·계좌번호 조회·비밀번호 요청 없음**. EraLeader는 발굴기이며 주문 시스템이 아님.

## 공식 키움 TR 확인
- 키움증권 REST 문서 `ka10059` (국내주식/종목정보/종목별투자자기관별요청).
- `POST /api/dostk/stkinfo`; 헤더 `authorization: Bearer ...`, `api-id: ka10059`.
- 요청은 `dt=YYYYMMDD, stk_cd=6자리, amt_qty_tp=2(수량), trde_tp=0(순매수), unit_tp=1(단주)`.
- 결과 `stk_invsr_orgn[]`: `dt, frgnr_invsr, orgn`. 일부 숫자 `--40142` 형태 부호 변환 검사.
- 제공 서버 및 API 키 **각각 분리**: `demo=https://mockapi.kiwoom.com`, `real=https://api.kiwoom.com`. 기본 profile `demo`, 실전/모의 키 혼용 금지.
- 출처: https://openapi.kiwoom.com/m/guide/apiguide 및 https://github.com/Kiwoom-Securities/Kiwoom-REST-API
- 실전 수급을 자동으로 '매수 신호'로 승격하지 않으며 값 없는 날짜를 0으로 채우지 않는다.
- `5/20`은 **일자 있는 관측행 5/20개**이지 공식 거래소 달력의 완전 연속성 인증은 아니다. 미정밀·선택표본·과거 최초게시시점 N/A.

## 구현 (모든 코드는 worktree feature 브랜치)
- `src/eraleader/kiwoom_investor_flow.py`: 선택 종목/고정 모드 HTTPS OAuth/token, ka10059 페이지 상한, 날짜·부호·SHA·결측·비정상 응답 거절, 5/20관측 순매수 수량 집계. **허용된 OAuth/token과 조회 TR만 호출**.
- `scripts/capture_kiwoom_investor_flow.py`: `--profile demo|real`, `--codes ... --day YYYYMMDD --out /new/private/path`. 1~20종목, 비공개 JSON/manifest 새 디렉터리 단위 공개, 중간 실패는 원본 삭제와 미게시. `--check-config`는 외부 호출 0, 키 값 노출 0.
- `src/eraleader/official_kiwoom_flow_overlay.py`, `scripts/publish_kiwoom_flow_overlay.py`: 기존 first SHA 후보/업종 JSON 검증 후 **별도 수급 비교 표**. 3종 기존 HTML은 설정/수급 링크만 추가하고 첫 순서·WATCH/가격·실적·사업보고 SQL은 변경하지 않음.
- `src/eraleader/kiwoom_profile_settings.py`, `scripts/serve_kiwoom_settings.py`: **모의/실전 2개 구역 별도 키/시크릿/별칭, 기본선택 모의**. 로컬 주소 `http://127.0.0.1:8782/`만 허용, Host/Origin/CSRF 검증, 캐시·referrer 금지, frame 거부. 계좌번호·비밀번호·OTP 입력 안 함. POST/키 로그/HTML 리플렉션 0.
- 키는 OS 사용자 내부 `~/Library/Application Support/EraLeader/ProviderKeys/kiwoom_profiles.json`에 원자적 저장, 폴더700/파일600(별도 공개 Git 기록 금지). **현재 평문 파일 권한 보관이며 Apple Keychain 암호화가 아니다. 실전 키는 키체인 보관 지원 전에는 등록 자제**.
- `--profile real`의 실전 키 존재 여부를 명시 확인하되 자동 대체/실전 전환 없음. `--profile demo` 모의 키가 없으면 fail-closed.
- 새로운 로컬 HTTP 설정 서버는 수동 실행 프로세스이며 운영 LaunchAgent 자동 등록 아님.

## 로컬 실제 연결 확인 (2026-10-13 KST)
- Mac/T5DATA 설치 확인, `feature/core-official-factor-coverage-20261013` HEAD 시작 `5e5fa0c` worktree clean.
- 키움 credential 상태: **demo 미설정, real 미설정**. 키움에 실제 HTTP 호출 0, 실제 투자 수급 입수 0.
- 기존 비공개 실데이터: 2026-10-08 공식 KRX **2,765개 거래관측** 중 현재 DART 금융+업종 확보 **10개**.
- `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/site/investor_flow_kr.html` 생성 및 기존 사이트 링크. 연구 결과는 기존 **10개 그대로, 수급 실측 0/10, 5·20 관측 가능 0, 모두 N/A**, 공식 leader 0, 실전 주문 0.
- Mac loopback 설정 `http://127.0.0.1:8782/`, 수급 `http://127.0.0.1:8770/investor_flow_kr.html`, 기존 index 모두 HTTP200, Chrome 2페이지 열기.
- 기존 main의 별도 미커밋 `native_first_capture.py`와 원시 가격·DART/SEC 데이터/복구 DB/외부 프로젝트 변경 없음.

## 이어서 실행
```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src python3 scripts/serve_kiwoom_settings.py --port 8782
PYTHONPATH=src python3 scripts/capture_kiwoom_investor_flow.py --check-config --profile demo
PYTHONPATH=src python3 scripts/capture_kiwoom_investor_flow.py --check-config --profile real
# 키 등록 후 선택된 회사만:
PYTHONPATH=src python3 scripts/capture_kiwoom_investor_flow.py --profile demo \
  --codes 005930,000660 --day YYYYMMDD --out /ABSOLUTE_NEW_PRIVATE_DIR
# 기존 수급 N/A 화면은 --kiwoom-manifest 없는 경우 1회 발표,
# 실제 data 발표 때는 새 output/site로 별도 생성 (기존 결과 덮어쓰기 금지).
```

## 테스트 및 남은 실제 미완료
- `tests/test_kiwoom_investor_flow.py`, `tests/test_kiwoom_profile_settings.py`, `tests/test_kiwoom_publication.py` 집중 **31/31 PASS**.
- 로컬 owner-only 저장·별도 모드·XSS 탈출·CSRF 방어·실제 HTML에서 키 없음·실전 계정 강제 선택 차단·기존 순서 보존·오염 raw SHA/부분배치 재실행 거부 확인.
- **라이브 모의/실전 API 양쪽 인증 및 TR 응답 형식·호출제한 확인은 키 등록 후 필요**. 조회일 종목별 다중 시장코드(KRX/NXT/SOR) 구분은 현재 KRX 6자리로 강제, NXT 별도 시장연결 N/A.
- 진짜 투자논리 검증: 실물 수급/거래량 대비 비중/산업 수급 추세, 선별표본 확대, 실시간 데이터 게시시간+원천 법적 PIT/20거래일 예측력은 아직 미완료.
- 전체 인수진행률 45/120=37.5%(38%) 유지. 작은 scope 구현만으로 종목군 전체 실사용 인수관문을 올리지 않음.

## 2026-10-13 후속 — 공식 공통 연결계층 SharedBrokerAPI로 일원화

- 별도 독립 경로 `/Volumes/T5DATA/SharedBrokerAPI`. 실행중인 Mac 개인 UNIX socket `~/Library/Application Support/SharedBrokerAPI/gateway.sock` (0600).
- 데모/실전 API 설정 파일의 단일 기본 경로를 `~/Library/Application Support/SharedBrokerAPI/kiwoom_profiles.json`로 변경. 기존 EraLeader 전용 ProviderKeys 경로에는 실제 저장된 키가 없었으므로 자격증명 이전/복사 없음.
- EraLeader `scripts/capture_kiwoom_investor_flow.py` 기본 사용자 CLI는 이제 *직접 OAuth/직접 HTTPS 대신* `shared_broker_api.client.ReadOnlyClient("eraleader")`에 위임. 공통 계층에서만 OAuth와 `ka10059` HTTP 요청 가능; 프로젝트에 실 키/토큰 전달 안 함. 기존 백엔드 `fetch_ka10059` 수량/결측 통합 코드 재사용.
- CoreAStock 및 NewsCatalystOS도 같은 `ReadOnlyClient(project)` 객체로 **시장/수급 조회 기능** 사용 가능, 단 기존 두 프로젝트 소스/전략/주문 코드를 자동 변경하지 않음. 주문 API는 공통 계층에 존재하지 않음. 실계좌 주문 권한은 후속 별도 인증 설계 필요.
- 실제 Mac UNIX socket 서비스 상태: `eraleader`, `coreastock`, `newscatalystos` 세 client 모두 Local status SUCCESS, `orders_enabled=false`, 공유 socket 파일 권한0600. 사용자 키 모의/실전 현재 미설정→실제 Kiwoom HTTP 수신0.
- 합성 two-project 공유: 동일 모의 주권 요청 2회에도 OAuth 1회+TR 1회, 실전 별도 키/토큰 분리, 다른 프로젝트 응답에서 OAuth 원문 없음. 공통 계층 테스트 9/9 PASS, EraLeader 선택 31/31 PASS. 기존 가격 WATCH 데이터·실전 추천 불변, 30ID 총 인수진척률 38% 유지.
- 공통 코드와 아키텍처/운영 제약: `/Volumes/T5DATA/SharedBrokerAPI/README.md`. 공급자 API 사용 약관·속도 한도 및 실제 모의 live 인증 검증은 설정 후.

## 2026-10-13 재검증 — 공통 API 단독 인증 및 타 프로젝트 수급 연구 조회

- EraLeader CLI는 공통 로컬 UNIX socket `ReadOnlyClient.status()`만 호출하고 Mac 개인 키 파일을 더는 직접 열지 않는다. `--check-config`는 `gateway_reachable` + `credentials_configured`만 반환, 실 API 호출0. 실제 수집은 gateway가 없거나 실전/모의 프로필 미준비면 fail-closed. 과거 독립 `access_token()` / 원시 수집 정규화 함수는 외부 주입 transport 없이는 기본 실호출하지 않도록 차단.
- 신규 `tests/test_kiwoom_gateway_cli.py`에서 shared 모의 상태만으로 CLI 수행, 주문 가능하다고 위조된 상태·브로커 다운 시 원본/새 output 미발행 검사.
- 독립 SharedBrokerAPI `ReadOnlyClient.selected_flow_research`는 타 프로젝트 CoreAStock도 소켓으로 이용 가능. `5/20` 관측 순매수는 기관·외국인 **주수량**만 표시하고, 시장 전체 외국인 `foreign_flow_20d` 금액으로 넣으면 **표본과 단위가 달라 투자 모델 오염**. 따라서 `can_fill_coreastock_macro_foreign_flow_20d=false`와 `can_unlock_new_risk=false` 항상 고정.
- **실행 테스트**: 공통 `24/24 PASS`; EraLeader 관련13모듈 `158/158 PASS EXIT0`, 보호 SHA256 정상 유지. 실제 키움 프로필 등록0/공식 수급 수신0/주문0. 실사용 인수진척률 38% 유지.
