# 151 — 검증된 최신 거래일 연구 결과의 안전한 재실행

**일자:** 2026-10-14 KST · **개발 ID:** 1_5·2_3·6_2·6_5 · **브랜치:** feature/core-official-factor-coverage-20261013

## 실사용 문제와 개선
기존 하루 1회 연구용 fallback HTML/JSON은 같은 날짜를 다시 실행하면 기존 출력 디렉터리 때문에 종료 코드 2로 실패했다. 변경 후 **현재 최신 검증 출처·종목 선정 순서·원본 SHA가 동일하면 이전 결과를 읽기 전용 반환**한다. 처음 발행한 시각·사유·SHA와 파일 수정시간은 그대로다. 같은 날짜에 더 최신 공식 연구코호트가 생겼다면 이전 결과를 덮어쓰지 않고 새 출력 경로를 요구한다.

별도 신규 모듈 official_latest_baseline_replay.py는 owner-only 디렉터리와 정규 파일, 심볼릭 링크·과다 파일·공개 권한 차단, JSON 중복 필드 및 canonical SHA, 기존 HTML 일치, 최초 게시/연구시각 제약을 검사한다. 수정된 기존 공식 원본 검증 로직은 유지하며, 원본 WATCH·가격·CFS·업종·순위·키움 거래 설정·실주문은 건드리지 않는다.

## 검증과 실제 자료 스모크
- **집중 테스트 41/41 PASS EXIT0:** 이전 fallback 테스트 및 새로운 동일일 재실행·출처/종목 변경·SHA/HTML 변조·파일 누락·권한/심볼릭 링크·미래 시각 차단.
- **변경 영향 6모듈 90/90 PASS EXIT0:** 추가 공식 키움 일별 브리지, 동일시점 CFS/업종 코호트, DART 디렉터리, 기본후보 영향 테스트. 로그는 Git 미추적 output/verification_logs/baseline_realuse_impact_20261014.log/.xml.
- **기존 실제 공식 KRX/DART 원본 읽기 전용 E2E:** output/same_session_cohort_3fy_20261013을 다시 검증하여 2026-10-14 요청 시 2026-10-08 거래 관측일을 명시한 output/latest_verified_20261014_realuse_replay/index.html 및 report.json 생성. 첫 실행 EXIT0, 두 번째 실행 EXIT0, 동일 두 파일·CLI 출력 SHA/bytes 불변, JSON content SHA 검증 PASS, 로컬 HTTP GET 2건 200/200.
- **데이터 표시:** 삼성전자·SK하이닉스 2종목, 지연 상태 STALE_RESEARCH_WARNING=true, 새 매매신호·정식 대장주·실주문·키움/API 호출 0. 과거 자료를 오늘 매매 근거나 과거 PIT 인증으로 간주하지 않는다.
- 전체 수천 건 회귀·신규 공식 HTTPS 수신·실제 스케줄 설치·SSD 물리 재연결/재부팅은 이 변경에서 수행하지 않았다.

## 다음 작업
같은 날짜 더 최신 거래일·실적 원본 발생 시 버전이 있는 새 연구판 자동 출력을 보완하고, 최신 실제 KRX 양시장 수신→DART/CFS/업종→WATCH→웹·일주월 보고를 실사용 E2E로 운영한다. 과거 엄격 인수 45/120(38%)는 재산정 전 스냅샷으로 유지. 원본 main의 미커밋 native_first_capture.py 6추가/1삭제 및 사용자 미추적 자산은 보존한다.
