# 140 — 공통 키움 모의 수급 → EraLeader 변경 없는 연구 원장 연결

## 목적과 실제 변경 (2026-10-13 KST)

작업 ID: `2_5 / 4_2 / 5_5 / 6_2`. 이미 존재하는 EraLeader의 가격·실적·산업 분석과 `SharedBrokerAPI`의 **모의** `ka10059` 조회 응답을 직접 혼합하거나 점수에 주입하지 않고, 한 종목·한 기준일에 대한 **별도 증거 원장/HTML 연구화면**으로 연결한다. 이전의 정상 `kiwoom_demo_20261013` 캡처·페이지 게시 기능은 재작성하지 않는다.

- 새 `src/eraleader/kiwoom_shared_research_sidecar.py`: 공통 서비스의 `selected_flow_research(..., recent_sessions=20, max_pages=1, mode='demo')`를 **하나의 새 immutably named 폴더** `site/kiwoom_shared_<day>_<code>_<SHA12>/`의 `report.json` 및 `index.html`에 저장. 페이지 원본 SHA + 최초 gateway UTC 수신시각, 후보·산업 SHA와 비교 기준일을 보존. 기존 메인 `index.html`에는 새 링크 1개만 추가.
- 새 `scripts/publish_shared_kiwoom_flow.py`: 명시적 `--code/--day/--candidate-json/--industry-json/--site` 옵션, Mac local owner-only SharedBrokerAPI UNIX socket으로만 인증/수급 접근. **실계좌 모드 옵션 없음**. API 키·OAuth 토큰·원본 응답을 저장하거나 렌더링하지 않음.
- 새 `tests/test_kiwoom_shared_research_sidecar.py`: 한 페이지 100행 출처, 가짜 투자 승격 차단, SHA/PIT 시간/모드/issuer/단위/의사결정 경계 변조, 기준일 미일치, 기존 index 보존/실패 rollback, 클라이언트 사전게이트, symlink 거부.
- 기존 `read(...)`, `build_overlay(..., flows={})`, `_swap(...)`을 재사용. 별도 원본 source의 `content_sha256`과 한 페이지 `source_payload_sha256` 및 UTC 수신 증거 검사. 진단 로그에 원시 키·시세·기관 순매수 결과 공개 금지.

## 실제 생산 API가 아닌 모의 서비스 수신/게시 검증

- `SharedBrokerAPI` 모의 credentials configured, 실계좌 unconfigured. 2026-10-08 삼성전자(005930) 모의 `ka10059` 최근 **100관측행 1페이지**, 최근5/20개 관측 주 수량 계산; 더 오래된 페이지 전체 미수신(`source_recent_window_only=true`).
- 기존 공식 KRX/DART 연구 기본 JSON 각 SHA: `basic_candidates_kr.json=69199271...`, `industry_peers_kr.json=b8c63a39...`, 해당 원시/기존 score는 변경하지 않음.
- 실제 새 연구 증거 `/Volumes/T5DATA/eraleader/output/official_basic_multicompany_20261013/site/kiwoom_shared_20261008_005930_0edb8ee48235/report.json`, SHA `0edb8ee48235c52dfe6bda9dd10fcbfcefb3d6a4b92eb0ade3822d020c076446`. 연구기준일 2026-10-08 일치, 다만 **수신 2026-10-13이므로 과거 의사결정의 PIT/선행 성과라고 주장하지 않음**. 전체 페이지·역사종목군·시장전체 수급·실적 미래성능 N/A.
- 원본 후보/산업 SHA 재확인, 새 report SHA 일치, main index 새 링크 정확히 한 번 삽입 확인. 기존 WATCH/score/원본 Git·API 인증파일·주문·메시지 변경 **0**.
- 초기 CLI 실호출 1회는 일반 `BLOCKED`(exit2)로 실패했으나 직접 동일 read-only `publish()` 통합 실호출에서 통과, 이후 원장 SHA 일치 검증. CLI는 synthetic test에서 PASS; **초기 CLI 오류 원인은 확정하지 않음**, 외부 장애/인증 호출인지 추측하지 않는다.

## 검증/재현 명령

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest \
  tests/test_kiwoom_shared_research_sidecar.py \
  tests/test_kiwoom_investor_flow.py tests/test_kiwoom_live_research_panel.py \
  tests/test_kiwoom_profile_settings.py tests/test_kiwoom_gateway_cli.py \
  tests/test_kiwoom_publication.py -q --tb=short
# 테스트 종료 exit 0; 전체 회귀/20거래일 PIT·투자 성과 인증이 아님
```

명시 실행 시 원래의 `--candidate-json`/산업 원본/사이트 절대경로와 새로운 실행 시점의 SHA로 **새 연구 기록**을 추가한다. 같은 증거 디렉터리는 덮어쓰지 않는다. `real` 모드는 이 코드에서 거부되며 API 원본 키는 Mac 내 공통 게이트웨이에서만 읽는다.

## 다음

과거 기간 전체를 추정값으로 채우지 말고 실제 KR/US issuer/share-class, 기업행동·상폐·공시 공개시각과 prospective 1~12개월 자연 만기 평가 준비. 공통 API 연구 화면에는 모집단 수급 금액과 한 종목 순매수 **주 수량**을 동일 지표로 결합하지 않는다.
