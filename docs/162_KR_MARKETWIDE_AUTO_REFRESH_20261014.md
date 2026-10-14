# 162 — KR 전체시장 최신 검증본 자동 갱신 + 로컬 운영 화면 연결

- 2026-10-14 KST. 개발 ID: **1_2 · 3_4 · 3_5 · 6_2 · 6_5**.
- 목표: 매번 수동으로 전체시장 연구 JSON 경로를 지정하지 않고 새 공식 KR 자료가 들어온 후 기존 로컬 대시보드 명령으로 **최신 보관본 검색화면 발행과 링크 연결을 한 번에** 수행. 새 REST/키움 조회, 실거래, 주문, 알림 발송은 하지 않는다.

## 작동 기능

- 신규 `src/eraleader/marketwide_auto_refresh.py`: 사용자 지정 **source-root의 바로 아래 한 단계 디렉터리**의 기존 `marketwide_kr.json`만 읽는다. 후보 JSON 자체 canonical SHA, 발행·관측 시간, 연구 점수/재무/업종·수급 건수/정식 미승격 계약은 **기존** `marketwide_live_search._source/prepare_search`와 동일한 검증을 재사용한다.
- 동일 소스 공간에서 검증된 **거래일 최신** 우선, 같은 날에는 50점 부분연구 평가 건수 > 재무·산업 건수 > 동거래일 수급건수 > 발행시각 > 원천 SHA 순으로 선택. 신선도가 뒤진 양질 자료로 최신 날짜를 덮지 않음. 검증 실패한 신자료가 있으면 연구용 기존 유효 원천으로 fallback하고 누락 종목/시세를 만들지 않음.
- `output/marketwide_kr_search_YYYYMMDD_r<source-version-hash>/`에 신규 생성만 허용. source SHA·일자 기준 1일 멱등, 이후 CFS/수급 개선 버전은 원본 이전 화면을 유지하며 새 경로 발행. 같은 파일 재실행은 원본 연구 데이터 및 HTML/manifest를 재대조해 `ALREADY_CURRENT`로 종료. HTML/manifest 충돌·변조 시 덮어쓰기 금지.
- 신규 코드가 기존 `scripts/render_local_operations.py --marketwide-source-root /allowed/output` **명시적 opt-in** 옵션으로 연결됨. 이 명령이 실행될 때 자동 갱신한 결과를 운영 화면의 `kr_marketwide_search` 자동 메뉴가 선택. 아무 옵션도 없으면 기존 운영 명령 100% 동일하게 동작.
- 입력 후보가 모두 없거나 실패하면 `NO_VERIFIED_KR_MARKETWIDE_SOURCE`로 알려주고 마지막 정상 버전·운영 원장을 보존한다. API가 자동으로 호출되거나 매일 자동 실행되는 스케줄러를 **설치한 것은 아님**. 이후 운영 스케줄러가 이 CLI를 호출하도록 별도 opt-in 연결 가능.
- 기준 거래일/사용자 조회일 및 stale_warning 명확히 분리. 가격/실적2요소 연구 50점은 정식 100점 투자순위가 아님. 특정 외부 수신 프로젝트 연결 없음.

## 실제 실행 명령

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root '/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output'
```

- 실물 보관본 직접 실측: 후보 시장일 2026-10-08~13. 최신 2026-10-13 KRX **2,761종목**, 실제 연결 CFS 49 / 산업49 / 기존 2요소 연구점수38 / 동일 거래일 키움 수급 1; 정식확정 0. `KR_MARKETWIDE_SEARCH_REFRESHED` 후 새 검색 화면·운영 HTML 링크 성공. 동일 명령 두 번째 실행 `KR_MARKETWIDE_SEARCH_ALREADY_CURRENT`, 신생 중복 디렉터리 0. 버전별 이전 10/08/13 검색 화면과 원본 원장·source SHA 불변.
- `output/verification_logs/marketwide_auto_refresh_{real_e2e,repeat}_20261014.json` 및 `marketwide_autorefresh_scope_20261014.log` (Git 제외).
- 변경 범위 `PYTHONPATH=src python3 -m pytest tests/test_marketwide_auto_refresh.py tests/test_marketwide_live_search.py tests/test_operations_marketwide_navigation.py tests/test_operations_overview.py -q --tb=short` => **67 PASS / 0 FAIL / exit0**, 이전 59 테스트 + 신규 8. Python compile/diffcheck PASS. 사용자 요청에 따라 전체 수천 건/역사 엄격 PIT 재검증은 이 최소 기능에서 실행하지 않음.
- 위험/향후: latest source는 운영자가 지정한 보관 root만 신뢰하며 독립 PIT 최초공시시각 인증 아님. `main` 원본 미커밋, 다른 worktree 및 타 프로젝트 변경 금지. 정식 리더 선정까지 필요한 5요소 가격/실적/산업성장/경쟁력/수급의 실제 커버리지 확장·발굴 상태 자동 판정·프로젝트 중립 송신이 다음 핵심 개발.
