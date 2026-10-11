# EraLeader 6_4 / 6_5 — 사전 native Top-K 평가 만기 일·주·월 예약 보고

2026-10-11 KST. 실제 새 WATCH→원본 native 점수 최초등록→Top-K / 미래 성공규칙을 사전 동결한 다음, 평가기간 중/만기 이후 결과 미확인 상태를 안전하게 계속 추적한다. 실전 정답·실제 공식 issuer/KRX/SEC 공급자 PIT/알림 발송을 만들어 내는 기능이 아님. 사용자 D-017(API 연결 후순위), D-021(SSD 물리 재연결/재부팅 최종) 유지.

## 해결된 기존 공백

기존 report-ranked-maturity는 1회 실행으로 KR/US JSON/HTML 보고만 만든다. 기존 WATCH-only 배치는 7일 내에 새 WATCH가 없으면 배치를 보류하므로 사전 동결된 180일 이후의 결과 미확인 모니터링에는 적합하지 않다. 따라서 기존 가격 배치와 WATCH-only 스케줄러를 그대로 보존한 채, 가격 캐시·최근 WATCH 등록 여부와 독립된 maturity-only 안전 예약 모드를 새로 추가한다.

## KR/US 원본 등록의 입력 양식

Git 추적에서 제외되는 output/ranked_maturity.local.json에 다음 JSON을 작성한다. 경로는 실제 확보된 사전 동결 첫 등록 자료의 예시이며 지금 공식 원천이 존재한다는 뜻이 아니다.

~~~json
{
  "schema_version": "eraleader.scheduled_ranked_maturity.v1",
  "markets": {
    "KR": {
      "freeze": "/Volumes/T5DATA/eraleader/output/kr/frozen_native.json",
      "definition_file": "/Volumes/T5DATA/eraleader/output/kr/leader_rule.json",
      "score_ledger": "/Volumes/T5DATA/eraleader/output/kr/scores.sqlite",
      "watch_ledger": "/Volumes/T5DATA/eraleader/output/kr/prospective.sqlite",
      "features_dir": "/Volumes/T5DATA/eraleader/output/kr/features"
    },
    "US": {
      "freeze": "/Volumes/T5DATA/eraleader/output/us/frozen_native.json",
      "definition_file": "/Volumes/T5DATA/eraleader/output/us/leader_rule.json",
      "score_ledger": "/Volumes/T5DATA/eraleader/output/us/scores.sqlite",
      "watch_ledger": "/Volumes/T5DATA/eraleader/output/us/prospective.sqlite",
      "features_dir": "/Volumes/T5DATA/eraleader/output/us/features"
    }
  }
}
~~~

모든 필드는 정확히 일치해야 하고 KR/US 양국 모두 별개 원본 frozen native 점수 자료가 있어야 한다. 절대경로 필수, JSON 중복키/추가 outcome 파일/심볼릭 링크/파일 누락, 같은 시장 cohort 재사용·원시점수/label rule/frozen 변조 등은 차단한다. 시장 출시·상폐 유니버스의 완전성 인증을 요구하는 실전 데이터가 아닌 검증된 로컬 증빙에 한정.

## 한번의 예약 로컬 실행 (설정파일이 먼저 존재해야 함)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --maturity-only \
  --ranked-maturity-config /Volumes/T5DATA/eraleader/output/ranked_maturity.local.json \
  --maturity-sample-limit 100
~~~

- output/scheduled_maturity: 시장당 안전 파생 JSON 1개, 원본 maturity HTML 1개, 일·주·월 Markdown/HTML 3쌍씩. KR+US 합산 **총 16 파생 파일**. 사실상 일/주/월 리포트가 같은 시점의 최초 동결 cohort를 읽어 비교 날짜별 label 부재를 숨기지 않고 표시한다. 기간 경과·미경과/다음 만기/첫 실제 점수 시각과 성과 N/A, 공식 대장주 0을 명시한다. 근거 없는 성숙 positive/negative/precision/recall 수치 추정 금지.
- output/scheduler_maturity_control/last_verified_ranked_maturity_only.json: 원본 두 시장 점수/피처/WATCH·동결 규칙과 파일 증빙을 매번 검증하고, 16개 페이지·ZIP SHA 검증 및 최종 원천 재검사 후에만 원자적 완료 체크포인트. 같은 날/원본 근거·pending/elapsed 상태가 같고 ZIP과 화면 파일이 정상일 때만 SKIPPED_UNCHANGED_RANKED_MATURITY_EVIDENCE. 같은 날 만기 시각을 넘기면 fingerprint 상태가 바뀌어 새 리포트 수행.
- output/scheduler_maturity_backups: 기존 허용 파생 JSON·Markdown·HTML만 ZIP으로 SHA 검증; 원본 DB, 시세/정답 label/원시 자료/계좌 비밀키는 제외. ZIP 삭제·손상·유실 웹 보고서가 있다면 정상 재실행.
- 기존 가격/관찰 스케줄러 원본 정상 유지. maturity-only는 price batch 실행 0, 외부 API 0, live 메시지 0, 자동 매매 0. 거래일과 가격 캐시 자료가 낡아도 첫 사전 동결 기록만 원본이면 평가기간 상태를 추적한다. 상태 RANKED_MATURITY_ONLY_RESEARCH_VERIFIED_BACKUP은 파생 보고서/백업의 로컬 검증만 의미한다.

## launchd 설정 파일만 생성 (설치·실행 아님)

~~~bash
PYTHONPATH=src python3 scripts/run_local_scheduled.py \
  --project /Volumes/T5DATA/eraleader \
  --maturity-only \
  --ranked-maturity-config /Volumes/T5DATA/eraleader/output/ranked_maturity.local.json \
  --generate-plist /Volumes/T5DATA/eraleader/output/maturity.generated.plist
~~~

전용 서비스 ID org.eraleader.ranked-maturity-research, 별도 ranked-maturity-launcher.sh/로그 이름. 기존 price/watch 서비스와 bootstrap 이름 충돌 없음. 부트스트랩은 SSD가 없으면 SKIPPED_EXTERNAL_SSD_UNAVAILABLE로 정상 종료, 가격 캐시 없어도 별도 cohort config 읽기. 실제 launchctl load/bootstrap/자동 발송/원격 사이트 배포는 수행하지 않는다. plist의 실행 간격은 기존 로컬 생성 정책에서 가져왔으며 실제 설치 일정이 아니다.

## 실제 오프라인 검증

신규 tests/test_scheduled_maturity_bridge.py는 양 시장의 180일 넘은 최초 신호에도 읽기 전용 리포트 발행, US DST·현지 만기 시각, 16개 출력/ZIP/복원, 중복 skip/분실 ZIP·웹 재시도, 출처·규칙·설정 중간 수정·시점 전환에 따른 checkpoint 취소, 같은 시장날짜에 만기 경계 통과 후 재평가, 두 시장 누락/경로 오염/중복 JSON 키, CLI/비설치 launchd 및 기존 price/watch default 호환성을 검사한다. 정확한 전체 테스트 수·커밋 SHA는 PROJECT_STATE.md 최신 기록을 따른다.

## 핵심 한계/다음 작업

현재 한국·미국 당시 전체 상장·상폐 기업의 법적 issuer/share-class/PIT, 기업행동·상폐 현금정산, 공식 공시 발표·첫 수신 독립 시각과 실제 성숙 outcome 소스는 확보·인증되지 않았다. 이 기능은 평가기간이 끝나도 결과 증빙이 없으면 positive/negative를 null(N/A)로 보존하고 실제 대장주 조기 발굴 성과를 인증하지 않는다. 후속 5_5 실전 source receipt/lead days/false positive/precision 검증은 원천 API 수급과 실제 기간의 경과 이후. D-017 API 및 D-021 SSD 물리 시험은 마지막. 정상 코드 REWRITE 금지.
