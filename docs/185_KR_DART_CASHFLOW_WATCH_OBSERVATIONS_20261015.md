# 185 — 보관된 WATCH의 공식 DART 연간 현금창출 관측 연결

- 2026-10-15 KST / 개발 ID: 3_2·4_1·6_1·6_2·6_4.
- 새 실제 기능: 기존 공식 DART 연결재무 원본 → 영업현금흐름·유형/무형자산 취득액 → 보관된 WATCH50 현금창출 JSON/HTML 보고 → 운영 대시보드 링크. KRX 최신일 0행 대기와 독립적으로 기존 연간 원본을 재사용했다.
- dart_profitability_watch.py는 기존 영수증 SHA·기업 매핑·CFS/연도/최초 이용시각 검증을 그대로 재사용한다. 새 include_cashflow=True에서만 CF 계정을 추출하고, 기본 기존 수익성 출력·판본은 그대로 유지한다.
- 새 dart_cashflow_watch.py/publish_watch_cashflow.py는 정확한 표준 CF account_id 세 개만 사용한다. 영업현금은 원래 부호 유지, 취득액은 현금유출을 양수로 정규화하되 원래 부호의 금액도 JSON에 보존한다. 부문·외화·충돌 계정은 해당 총계에 사용하지 않는다.
- 계산: 영업현금−유형취득−무형취득. 하나라도 없으면 N/A, 실제 보고된 0만 0으로 인정. 기업 인수·리스·기타 투자항목을 제외한 제한된 잔여현금 관측치로 표시하며 완전한 FCF나 경쟁력20점으로 주장하지 않는다. 영업현금/매출 %, 흑자 순이익 대비 현금배율, 연속 두 회계연도 영업현금 양수 여부 제공. 산업20·경쟁력20·정식 리더·주문은 기존대로 N/A/0.
- SHA 봉인된 WATCH와 시장보고가 같은 입력인지 확인하고 별도 output/watch_annual_cashflow/KR_<시장일>_<입력해시> 판본에 원자 발행. 기존 WATCH·일일 보고·원시 수신 불변. 보관 WATCH 시장일·새 분석일·원본 최초 수신 UTC를 각각 표시하고 새 시장일의 WATCH로 재분류하지 않는다.

## 재현

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/publish_watch_cashflow.py --project "$PWD" \
  --marketwide-report /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/kr_20261013_marketwide_49f49i_20261014/marketwide_kr.json \
  --watch-manifest "$PWD/output/early_leader_watch_queue/KR_20261013_f5a3041ca5838fd2/watch_queue.json" \
  --capture-root /Volumes/T5DATA/eraleader/output/official_api_capture
```

## 실제 증거

- 공식 연간 CFS 원본에서 CF 행 존재 기업57, 기존 검증의 수익성 가용54. 보관 WATCH50 안에서 영업현금46, 유형·무형취득 후 잔여현금42, 연속2년 영업현금 양수35. 나머지는 N/A. 시장 관측일2026-10-13, 분석일2026-10-15, 원본은 기존 실제 영수증 그대로. 최신 시세 발행 기능 아님.
- 새 판본 output/watch_annual_cashflow/KR_20261013_a0faa9c9733cc8a7/{cashflow.json,index.html}; 이전 WATCH 파일 바이트 보존 확인. 재실행 ALREADY_PUBLISHED, API0, 주문0, 중립 receiver_project=null/selected_candidates=[].
- 운영 대시보드 링크 정상, 메인·새 상세 HTTP 각각200. output/verification_logs/watch_cashflow_real_20261015.json 및 watch_cashflow_replay_http_20261015.json에 기록, Git 제외.
- 집중 테스트 4파일(test_dart_cashflow_watch.py, test_dart_profitability_watch.py, test_operations_one_command_auto_watch.py, test_early_watch_daily_brief.py) **31 PASS / 0 FAIL/ERROR/SKIP**, Python compile/diffcheck PASS. 부호·결측/0·손실 분모·회사/연결재무 혼합·계정 충돌·외화/부문·미래 수신·이전 출력 보존·JSON/HTML/대시보드·반복 발행 확인. 증거 watch_cashflow_scope_20261015.xml.

## 현재 운영 조건

- 사용자 2026-10-15 명시 공개 브랜치 푸시 승인 후 이전 기능4928395·상태68724f5 푸시 성공, 원격 SHA68724f5 일치 확인. 비밀키·원시자료·output 제외.
- KRX2026-10-14 양시장0행 대기는 유지하며 동일 조건 재조회하지 않았다. 새 현금흐름 기능 API 추가0. 최신 KRX 자료 정상 발행 및 실제 launchd 설치는 여전히 별도 미완.
- 현행 API 제외 실운영 진행률 약67% 유지: 기존12개 운영 흐름 완료5·부분6·미완1. 현금창출 관측을 정식 경쟁력20점 완성으로 승격하지 않는다.
- 다음: 공식 현금흐름 관측을 사용할 경쟁력 모델의 미확보 정의·자료 범위를 구분하며, 시장 원본 반환 시 기존 증분 WATCH 정상 실자료 발행을 확인한다.
