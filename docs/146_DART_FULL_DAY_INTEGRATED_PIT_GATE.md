# 146 — KRX/DART/Kiwoom 동시점 검사: DART 전수 페이지 SHA 증명 연결 (2026-10-13)

**개발 ID:** 1_2 · 2_2 · 3_2 · 4_2 · 6_2. 기존 normalizer/PIT/점수/주문 경로 재작성 금지.

## 실사용 기능
- SSD의 이미 수신한 DART 첫 페이지 원문/영수증을 **owner UID + 그룹/기타 권한 0 + 독립 SHA256**으로 읽기 전용 검증한 후, Mac 내부 0700 보호 디렉터리에 **동일 bytes/SHA**로 0600 복사한다. T5DATA exFAT의 `0600 -> 0700` 모드 표시 탓에 기존 strict DART page collector가 실패하던 문제를 원본 검증기 수정 없이 해결한다.
- 기존 `official_dart_daily.capture_dart_day/verify_dart_day` 코드를 그대로 호출, 나머지 페이지를 수신·전체 공시 접수번호 고유성/행수/일자/페이지·first-received UTC/페이지 SHA·최종 manifest SHA를 확인한다. 원본 SSD first 자료/기존 시장·PIT 원장은 변경하지 않는다. 동일 original first receipt에 대해 이미 PASS 받은 DART full 산출물은 다시 다운로드하지 않고 SHA 검증하여 재사용한다.
- 독립 맥북 보관 경로: `~/Library/Application Support/EraLeader/dart_full_live/` (0700, API 보안 JSON 0600). 별도 비밀번호/서비스 추가 없이 기존 owner-only Mac DART 키 사용. 원시 공시·비밀키/시세를 Public GitHub에 업로드하지 않는다.
- 신규 파일: `src/eraleader/official_dart_full_mac_bridge.py`, `scripts/complete_dart_mac_bridge.py`, `tests/test_official_dart_full_mac_bridge.py`. 기존 `official_three_provider_session_gate.py`과 `scripts/publish_three_provider_session_gate.py`에 **옵션** `dart_complete` (경로+독립 manifest SHA)만 추가. 미제공 시 기존 첫 DART 페이지 감사 그대로 작동하며 첫 페이지가 미완성이면 보류. 완전한 full DART 페이지에 대해 기존 strict verifier가 확인해주어야만 당일 DART 커버리지 flag를 PASS 처리한다. 이 상태도 **역사 최초공개시각 PIT/issuer-class/모의 생산시장 적합성 인증 불가**이다.

## 실제 공인 DART 당일 실증
- 기준일 `2026-10-13` 최초 캡처: `first_a26e209f6a3c4cd496528f5d83a3c3b7`, pinned 첫 영수증 `972e98a9077269038945da29a1d01c3c78657c478a75c1f1e565ae26e57a3ded`.
- 최초 100건 + 신규 4개 페이지 수신 → **455건 / 5페이지 전수 검증 PASS**. Mac 전수 보관 `dart_full_09ff29663f4d41708278478ddd7cd53b`, manifest SHA `c386539aae308640022951594d27ce99a459942dc19120e0c2378b3da283a8fb`. 이번 동일날짜 API 데이터 모집단의 완성으로만 해석. 시장 전 기간·법적 상장유니버스·수정 공시 이력 인증 아님.
- 기존 **KRX 10/13 코스피 0행/코스닥 0행**은 그대로 보존·재조회 반복 안 함, 키움 모의 005930 100행 SHA PIN 재사용(새 키움 호출0). 두 자료 모두 같은 거래일 코드이나 KRX 가격 원천 결측이므로
  `PAUSED_MISSING_OR_INCOMPLETE_OFFICIAL_EVIDENCE`;
  `blockers=[KRX_ONE_OR_BOTH_MARKETS_EMPTY, SELECTED_ISSUE_NOT_IN_SAME_DAY_KRX]`;
  `dart_full_listing_sha_verified=true`;
  `can_compare_same_session_research=false`; 공식 leader/점수/주문 0.
- 새 로컬 읽기전용 화면 `http://127.0.0.1:8770/provider_session_20261013_dart_full/index.html`과 동반 SHA 원장 `report.json`. 기존 first-page 연구 화면 불변, 링크만 추가.
- 합성/단계 시험: 동일 첫 SHA의 엄격 0600 Mac 재현, 3페이지 전수/중복 재실행 네트워크0, 원본 SHA 위조·데이터 변조·페이지 총건수 변경·max-pages 제한, full DART 증거 없는 경우 fail-closed, KRX/DART/Kiwoom 동시점에서도 투자 승격 거부.
- 후속: 실제 KRX 최신 **비어 있지 않은** 양시장 스냅샷을 확보할 때만 동일시점 연구 재개; DART 455건은 조회일 당일 실측 보관, 공개시각 원천 감사·법인/주권 class 독립 검증 및 전향적 Top-K 자연 성숙은 별도 필요.

## 검증 종료 체크포인트

- 변경 영향 **12개 테스트 모듈 192/192 PASS(EXIT0)**, 신규 bridge/게이트/CLI Python `py_compile` PASS, Git diffcheck PASS. Mac/T5DATA의 protected DART full evidence 8개 파일 SHA256 별도 복제·일치 PASS.
- 실제 완전 DART 455행/5페이지를 독립 Mac 원본 SHA로 복원·검증: `verify_dart_day` EXIT0. 기존 10/13 KRX 양시장 0행 → `PAUSED`; DART 관련 blocker는 `dart_full_listing_sha_verified=true` 증거에 따라 제거. 새 패널·기존 index HTTP200, 원본 JSON checksum PASS.
- 분석 함수에 검증되지 않은 `complete_dart` dict만 넘겨 DART 보류를 해제하는 경로도 차단. 기존 strict page verifier에서 실물 SHA/수신시각을 확인한 경우에만 내부 승인 토큰 전달. 이 내부 토큰 자체는 외부 공증이나 암호학적 독립 인증을 대체하지 않음.
