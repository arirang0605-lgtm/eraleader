# 178 — 기존 공식 DART 세부업종 표본·기업 상대 실적을 WATCH 큐 JSON/HTML에 연결

**2026-10-14 KST | 개발 ID 3_4·4_1·4_2·6_2 | feature/kr-marketwide-search-20261014**

## 새로 실제 작동하는 기능 (입력 → 처리 → 출력)

- **입력**: 기존 SHA-봉인 `marketwide_kr.json`(KRX 2026-10-13, 2,761종목)와 기존 부분 5요소 시장일 평가 입력 500종목. 공식 DART 현재 업종코드, 매출 전년대비 YoY, 영업이익 YoY, 기업 ID 연계 증거 및 현재 시점에 확인 가능한 동업종 부분순위를 그대로 재사용. 신규 API·웹 스크래핑·새 DART 재수집 **0회**.
- **처리**: 기존 `src/eraleader/early_leader_watch_queue.py`의 WATCH 50개 산출 경로를 재사용·확장. DART 현재 세부 `industry_code`가 **정확히 같고** KRX 회사 식별자가 매칭되며 실측 매출 YoY가 있는 기업 **2개 이상**의 표본만 묶음. 그룹마다 매출 YoY 중간값과 영업익 YoY가 실제 2개 이상 있는 경우 영업익 YoY 중간값을 계산하고, 같은 회사 성장률에서 표본 중간값을 뺀 차이를 백분율포인트(pp)로 표시. 기업영업 YoY가 없는 경우 경쟁 실적 차이는 N/A. **표본 업종 성장률은 공식 업종 전체 성장률이나 기업 해자/지속경쟁력 점수가 아니다.** 산업성장20·기업경쟁력20 **정식 점수·전체 100점/진짜 대장주 확정0을 유지**, 원래 A/B/C/D 그룹 선정·검토 우선순위는 변경하지 않음.
- **출력**: 수신자 중립 `watch_queue.json`에 `industry_sample_peer_count`, `industry_sample_revenue_growth_median_pct`, `company_revenue_growth_pct`, `company_revenue_growth_vs_peers_pp`, `industry_sample_operating_growth_median_pct`, `company_operating_growth_pct`, `company_operating_growth_vs_peers_pp` 및 결측/N/A 안전필드 추가. 로컬 `index.html`에는 **업종 표본 매출 성장 중간값 / 기업 매출성장 / 표본 대비 pp / 기업 영업이익 증가율의 표본 대비 pp**를 추가. 기존 운영 `operations_overview.py`는 기존 파일 SHA/HTML 검증 루틴을 그대로 사용하되 새 판본 ID에 `sector_peer_context_method`를 포함. 같은 입력 반복 시 `ALREADY_PUBLISHED`, 기존 관찰 큐 및 원본 입력 파일은 **원본 불변 보존**. `receiver_project=None`, `selected_candidates=[]`, `orders_enabled=False` 그대로.
- 운영 판본: `output/early_leader_watch_queue/KR_20261013_0933ebaddb43934c/{watch_queue.json,index.html}`. 기존 정상 `KR_20261013_c29ba0bf7695e6c0`은 덮지 않음.
- 독립 조건: 사업장의 계약/외부승인을 기다려야 하는 산업 전체 성장률·시장점유율·ROIC·장기 해자 지표는 이번 실물 관찰 경로를 차단하는 필수 조건으로 승격하지 않음. 다른 기능은 계속 운영하고 해당 미확보 20점만 N/A.

## 실물 T5DATA 통과 증거

```sh
cd '/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014'
python3 scripts/render_local_operations.py --project "$PWD" \
  --marketwide-source-root /Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output \
  --marketwide-watch-queue-input "$PWD/output/partial_factor_inputs/KR_20261013_a59b7ecdfaa0b707_FLOWV1_2080b026ae1bef1e.json" \
  --marketwide-watch-queue-top 50
```

- 실제 49개 DART 재무+세부업종 프로필 관찰 중 동업종 2종 이상 묶이는 그룹 **8개**. 기존 50종목 WATCH 중 **매출 동업종 표본 비교 20종목**, **영업이익 동업종 표본 비교 16종목** 연결 성공. 그 외 후보는 NULL/N/A. 실주문0, 정식 leader0, 정식 산업20+경쟁력20 모두 N/A.
- 실측 JSON 예시 (회사 YoY – 동업종 관찰 중간 YoY): 000660 SK하이닉스 업종표본 매출중간 **24.3401%**, 회사매출 **46.7629%**, 상대 **+22.4228 pp**; 072950 빛샘전자 업종표본 **22.6335%**, 회사 **41.9849%**, 상대 **+19.3513 pp**; 353200 대덕전자 **14.5473% / 19.4094% / +4.8622 pp**; 417840 저스템 **7.1829% / 24.7752% / +17.5923 pp**, 영업이익 비교는 N/A. 전체업종 공식 추정이나 미래 투자수익률 점수로 주장하지 않음.
- 새 버전 로컬 JSON/HTML 정상 발행, 일반 운영 opt-in 재실행은 `ALREADY_PUBLISHED`, 중립 JSON의 종목50/각 결측 필드 유지. 운영 `output/verification_logs/sector_peer_ops_real_20261014.json`, 발행 `output/verification_logs/sector_peer_watch_real_20261014.json`. 로컬 HTTP 운영 메인/신규 상세 각각 200.
- 변경 집중 테스트 `PYTHONPATH=src:/Volumes/T5DATA/SharedBrokerAPI/src python3 -m pytest tests/test_early_leader_watch_queue.py tests/test_operations_overview.py -q --tb=short --junitxml=output/verification_logs/sector_peer_operable_scope_20261014.xml`: **51 PASS / FAIL0 / ERR0 / SKIP0**. 실제 동업종 2기업 양·음 상대값이 정확히 통과하고, 업종 1기업 또는 기업 영업익 결측에는 N/A로 빠지는 정상/결측 경로 재현. Python compile/git diffcheck 성공. 다른 기존 수천 건 전체 회귀는 D-032 실제 운영 필수 기준상 미실행.

## 현재 진행률 / 인수 구분

- **기능 구현·변경 테스트**: 이번 DART 동업종 관찰값 → 기존 WATCH JSON/웹 화면 경로 완료.
- **실자료 실행**: KRX/DART 실제 2026-10-13 관측값 → 50개 WATCH 중 매출20/영업16 실제 출력 완료.
- **운영·출시 인수**: 로컬 화면/파일 소비 가능. 일/주/월 정기 실행·외부 수신자 지정·정식 20점 계산/대장주 선발은 별도 남음.
- **API 제외 개발률: 약 67% 유지** (고정 12개 워크플로: 완료5/부분6/미구현1 = 8/12). 이번에는 산업/기업 비교 데이터를 실제 화면에 추가했으나 **산업성장20/경쟁력20 정식점수 기능은 아직 완료 아니므로** 항목 상태를 임의 승격하지 않음.

## 다음 하나의 실사용 개발

독립 공식 자료가 존재하는 기업부터 **업종 관찰된 다수 기업을 넘어 시장 전체 업종 성장 원천** 또는 **시장점유율/현금창출·ROIC 등 회사 경쟁력 증거** 중 실제 확보 가능한 필드의 입력·계산·선정 보조 출력 연결. 종목군·모형 전체 완전 PIT 인증을 이번 기능의 신규 필수 게이트로 추가하지 않는다. 데이터가 없는 회사는 명시 N/A, 다른 WATCH 출력을 계속 발행.
