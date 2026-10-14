# EraLeader 2026-10-14 최신 거래일 실증 — KRX/DART → 재무·업종 → WATCH 교체 관찰 → 범용 송신

## 실제 코드 계속 개발
- 기존 분리 브랜치 `feature/core-official-factor-coverage-20261013` (시작 SHA `c75aaf289cff5004617419d50af91951092584ea`)에서 CONTINUE. 원본 main 미커밋 native_first_capture.py, 계좌/API 설정, 기수집 최초 원본, 별도 프로젝트 변경 금지 준수.
- 공식 2026-10-13 KRX KOSPI 941+KOSDAQ 1820 = **2761종목**, DART 당일 공시 전체 **456행/5페이지** HTTPS 실수신. 2026-10-14 발행 당시 이용 가능한 DART 고유 기업코드 directory 첫 SHA를 연결해 일·주·월 보고, 기존 WATCH20, DRY-RUN 알림20 작성. 금융자료는 요청일 2026-10-13과 최초수신 2026-10-13~14를 구분. 10/13 전 이미 알려진 재무라고 소급하지 않음.
- 신규 10/13 가격 WATCH 상위12에 대해 DART FY2024/2025 연결실적 12사 수집/재사용, 완전 10·불완전 2 → N/A. 회사 프로필 실제 첫원본 12건, 공통 후보표에 완전 10사와 동일 업종 10사 연결. 나머지 가격 순서13~20 8사 CFS 완전8·업종8. 신규 표본 **총18사 공식 재무/산업**, 전체 KRX 2761/550일 캐시 RS **2263**가 분석 가능, 그중 **2요소 가격+실적 연구 점수 계산 가능 11사**. 현재 정식 산업·경쟁력·기관수급 5요소 TOP20/100점은 N/A.
- **KRX 10/08 → 10/13 최초로 관찰 WATCH 목록 변동 실데이터 비교**: 신규 진입4, 가격 관찰목록 밖 이동4, 잔류종목 내 상대순서 변경14. 이는 상태기계의 POTENTIAL/CONFIRMED/WEAKENING/EXITED가 아닌, 기존 `discovery.detect_watch_changes` 재사용 **연구용 관찰 이벤트**다. 시총·수급·회계정정이 추가 인증되지 않았으므로 자동 확정·매수·매도 지시를 발행하지 않음.
- 기존 보존 Kiwoom demo 2026-10-13 삼성전자 005930 20관측 해외/기관순매수 *주수* 자료 검증된 첫수신 원본을 같은 KRX 거래일에만 연결 → **수급 매칭 1사**, 이외 2760사는 N/A(0 아님). 계좌 권한/실계좌 주문/네트워크 신규 실매매 호출 없음.
- `scripts/publish_official_marketwide_coverage.py`의 선택적 `--strategy-outbox-dir`로 연구 대시보드가 발행되면 EraLeader 자체 `output/strategy_outbox`에 기존 `strategy_handoff` 프로젝트 중립 JSON 자동 발행. 신규 SNAPSHOT은 PRICE WATCH20, 50점 연구상위11, 기술 관찰 이벤트22(신규4+이탈4+순위변경14), `selected_candidates=[]`, `state_changes=[]` 및 `order_instruction=false`. 기존 버전 파일 불변, source SHA + 출력 구조 해시를 포함한 새 불변 파일 이름 사용, 멱등성 및 과거 v1 검증 호환 유지. 수신 프로젝트 직접 연결은 사용자 D-030에 따라 개발 제외.
- 최신 검증된 출력 (모두 Git 제외): `output/official_kr_20261013_dart_dir_20261014/`, `output/kr_20261013_cfs10_research_20261014/`, `output/kr_20261013_marketwide_18cfs18industry_20261014/`, `output/kr_20261013_marketwide_flow_delivery_20261014/`, `output/strategy_outbox/KR_20261013_b33e26987690_00e164ca58a1.json`. 최신 일부 원본은 `/Volumes/T5DATA/eraleader/output/official_api_capture` owner-only 위치에 누적되며 Git stage 대상 아님.

## 변경 영향 테스트·결론
- 관련 11개 모듈 pytest **173 PASS/0 FAIL/0 ERROR/0 SKIP/exit0**: `output/verification_logs/kr_latest_same_session_scoped_20261014.xml`. 정해진 범위의 실제 10/13 KRX+DART+기존 Kiwoom E2E, 과거 WATCH/신규 관찰 이벤트, 발행 JSON 검증 실증. 전체 장기 백테스트/수천개 회귀는 이번 단위 기능 선행조건으로 반복하지 않음.
- 아직 없음: 10/14 장마감 확정 일봉, 한국 전체 재무·산업·기업 경쟁력·동일 거래일 수급 전시장 연결, 100점 전체모델, 장기 후보 적중률, 미국 전체시장 매일 갱신, 실제 후속 수신기. 2026-10-13 KRX 2,761 및 DART456은 당시 관측 증거이며 10/14 가격이라고 주장하지 않음.
- **다음 핵심 P1/P2/P3**: 실제 갱신된 KRX 최종 장세션 수집/기존 공식 CFS·업종 코드 확장, 수급 표본 확대, 경쟁력 독립지표 및 산업 성장성 결선 → 전체 5요소 TOP20 자동 선정·POTENTIAL/CONFIRMED/WEAKENING/교체 인수. 기존 StateHistory와 strategy_handoff를 재사용한다. 운영 진척 38% (과거 엄격 기준) 폐기, 현재 전체 실사용률은 재산정 전.
