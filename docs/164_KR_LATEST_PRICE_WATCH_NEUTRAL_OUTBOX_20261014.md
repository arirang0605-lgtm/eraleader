# 164 — KR 공식 최신시장 연구 WATCH20 → 프로젝트 중립 JSON 송신 자동 연결

**2026-10-14 KST · 개발 ID 3_4·4_1·6_2·6_4 / 분리 브랜치 `feature/kr-marketwide-search-20261014`**

## 문제 / 이번 완성 기능

- 기존 `marketwide_auto_refresh`(최신 KRX·DART 보존자료의 날짜·SHA·시장가격/부분50점 검색 갱신)와 기존 `strategy_handoff.marketwide_research_handoff` / `publish_versioned_handoff`(프로젝트 중립 JSON)는 별개 명령이어서 정기 배치에서 중복 조회/수동 경로 선택이 필요했다.
- 새 `src/eraleader/marketwide_handoff_bridge.py`는 **기존 두 구현을 재사용**하여 `source_root` 하위 실제 시장 보고서 중 최신 검증자료를 하나 선택해 검색 HTML 갱신→해당 정확한 source SHA를 읽기 전용 재검증→가격 WATCH20를 연구용으로 범용 JSON 발행한다. 기존 PDF/회사 API/주가 모델/실매매 코드는 재작성하지 않는다.
- `scripts/render_local_operations.py`에 `--marketwide-publish-outbox` 추가. **명시 opt-in**, 반드시 `--marketwide-source-root` 지정. 해당 플래그가 없을 때는 기존 운영 화면만 갱신. 기존 예약 launchd plist와 `main` 정상 원장은 변경/자동 활성화하지 않는다.
- 산출물: `output/strategy_outbox/KR_YYYYMMDD_<sourceSHA16>.json`. 기존 `verify_handoff`가 SHA·시장·계좌/주문권한 없음·WATCH 상태를 재검사. 한 소스 버전 1파일만 유지하며, 새 수집본 SHA가 다르면 별도 파일. 당일 자료 지연 시 같은 source의 과거 발행파일을 **재사용**하고 기존 최초 발행시각/`as_of`를 새 날짜로 소급·덮어쓰지 않음. 기존 JSON/원시 데이터 변경0.
- 가격 WATCH20 요건 미충족·원천 SHA 충돌·주문/정식선정 위조·기존 발행파일 손상·outbox symlink 등이 발견되면 중단. 해당 거래일에 자료가 없으면 검증된 최신 기존 자료의 날짜를 명시하고, 자료가 모두 없으면 `NO_VERIFIED_KR_MARKETWIDE_SOURCE`. 외부 메시지·수신 프로젝트·실거래 주문 0.
- **중요 한계:** 선택20은 주가상대강도 연구 관찰이며 **100점 종합 대장주 선정 결과가 아니다**. `selected_candidates=[]`, `selection_count=0`, `state_changes=[]`, `execution_authority=false`, `order_instruction=false`, issuer/historical PIT 인증 false. 미래 성능 주장 없음.

## 실제 Mac/T5DATA E2E

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output' \
  --marketwide-publish-outbox
```

- 원본 공식 KRX **2026-10-13 / 2,761종목**, 재무·업종 각49·가격실적 연구50점 평가38·동일시장 수급1의 SHA 완결 보관본 선택. 기존 시장 전체 검색화면 `ALREADY_CURRENT`, 실제 범용 outbox `output/strategy_outbox/KR_20261013_a59b7ecdfaa0b707.json` 신규 생성. 직접 `verify_handoff`로 PRICE WATCH20 / selected0 / 변화0 / 주문권한false 확인. 재실행 후 출처버전 outbox 여전히 1건, EXIT0, 계좌/호출/알림 전송0.
- 변경 영향 + 기존 중립 송신 계약: `PYTHONPATH=src python3 -m pytest tests/test_marketwide_handoff_bridge.py tests/test_strategy_handoff.py tests/test_marketwide_auto_refresh.py tests/test_marketwide_live_search.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/marketwide_handoff_bridge_final_20261014.xml` → **87 PASS / 0 FAIL / 0 ERROR / 0 SKIP / EXIT0**. 신규 9개 테스트: 연구20, 중복 재호출, 다음 조회날짜 source 재사용, 다른 source 변경버전, 19개 요건 불충족, source 소실, 변조/링크 outbox 차단, CLI E2E, 플래그 단독실행 거부. Python py_compile / git diff check PASS.
- `output/` SHA·보고/JSON/SQLite 실체는 Git 추적 제외. 출처는 독립 first public PIT 인증이 아니며 실제 정식 후보 선정을 했다고 주장하지 않는다.

## 다음 구현

- 자료 확보된 재무·산업·경쟁력·수급까지 **동일 관측시점에 맞게 검증하고 기존 5요소 결정 엔진의 실제 입력에 연결**. 지금은 일부만 관측돼 정식 100점 리더0이 정답.
- 기존 `official_watch_state_bridge.py`(다른 정상 feature 브랜치에 이미 있음)와 신규 자동 최신 송신이 통합되는 단계에서 충돌/중복 확인, 안전하게 병합·테스트. 독립 recipient 구현/실주문 연결은 후속 프로젝트 선정 전까지 보류.
