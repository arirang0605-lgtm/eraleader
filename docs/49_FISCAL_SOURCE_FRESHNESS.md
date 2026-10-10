# 2026-10-10 3_1~3_5 / 4_1 / 5_4 — 오래된 재무·산업 자료의 후보 등록 차단

> EraLeader local-first, no external API, no independently PIT-certified stock leaders. **이 규칙은 코드 안전 게이트이며 투자 성능이 검증된 선정 기준이 아니다.** 정상 코드 전체 재작성 없음.

## 실제 발견한 단절

`offline_features.financial_snapshot`은 과거에 마지막으로 관측된 매출 YoY와 영업이익 YoY·산업 YoY를 계산했지만, 2024년에 공시된 자료를 2026년 기준으로 재실행해도 과거 성장 수치를 **현재 유효한 양성 WATCH 스크리닝**으로 인정할 여지가 있었다. `ProspectiveRegistry`가 단순히 모든 `False` screen-hit를 기록하면 **재무 데이터가 누락되거나 오래된 것을 성장 둔화로 잘못 인식**하는 이차 문제가 생긴다.

## 변경 파일과 규칙

- `src/eraleader/offline_features.py`: 시장별 현지 판단일(KR Asia/Seoul, US America/New_York)과 각 자료의 실제 `period_end`를 비교한다. 매출·영업이익·산업 매출의 어느 필수 관측도 판단일로부터 **450일**을 초과하면 연구용 후보 스크리닝은 **보류**된다. 450일은 연간 공시와 분기 혼합 자료를 위한 잠정적 **품질 상한**이지 성과 최적화 값이 아니다. 향후 원천별 분기/연간 공시 주기 및 법적 제출 기한으로 재검증 필요.
- 매출과 영업이익 YoY가 **서로 다른 회계 보고기간**의 수치라면 `FUNDAMENTAL_REPORT_PERIOD_MISMATCH`를 명시하고 보류한다. 미래 `period_end`가 판단일 이후라면 자료 누출로 즉시 오류. 실제 오래된 원본 수치는 진단용 `revenue_yoy`로 남겨 놓되 `screen_hit_heuristic=false`, `screen_evaluated=false`. 결측 등으로 세 필수 성장률을 계산할 수 없어도 보류.
- `src/eraleader/research.py`: 회계/산업 기간별 자료 나이, `screen_evaluated`, 전체 `research_screen_deferred_count`를 동일 시점 연구 스냅샷에 전달한다. 공식 확정 점수·PIT 인증은 계속 `null/false`.
- `src/eraleader/prospective.py`: **명시적 미검증(false)**과 **자료 부족에 따른 평가 보류**를 구분한다. `research_screen_evaluated=false`는 positive 후보도 negative 관찰도 등록하지 않는다. 보류 상태에서 `research_growth_screen_hit=true`로 위조한 모순은 차단한다. 기존 legacy fixture에서 필드가 없을 때는 원래 계약 유지.
- `src/eraleader/watch_progression.py`: 해당 필드를 명시한 row가 `false`인데 원장에서 관측 기록으로 발견되면 거부한다. **근거 부족을 SCREEN_WEAKENED로 오기록하지 않음**.
- `src/eraleader/delivery.py` 및 `src/eraleader/cli.py`: 로컬 통합 연구 페이지에 `STALE_REVENUE_PERIOD`, `STALE_INDUSTRY_REVENUE_PERIOD` 등 사유와 `스크리닝 보류` 건수를 표시한다. CLI 결과에도 `deferred_research_screens` 노출. 출처가 검증되지 않았음을 상시 명시하고 실제 대장주 0건 유지.

## 실제 코드·CLI·검증 결과

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_fiscal_freshness.py tests/test_offline_pit.py \
    tests/test_research.py tests/test_prospective.py tests/test_watch_progression.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
PYTHONPATH=src python3 scripts/verify_local_mvp.py
```

- 신규 `tests/test_fiscal_freshness.py` **10개 검증**: 2024 시점 정상 WATCH 관찰, 2026 시점 stale 보류, 450/451일 경계, 재무 기간 불일치, 조건 없는 자료에서 음성 판정 미기록, 보류 중 양성 위조 차단, 미래 재무 기간 차단, 전체 CLI/로컬 웹 경고. 이전 370개 → **380개 전부 PASS/0 FAIL**.
- 합성 `tests/fixtures/offline_synthetic.json`을 Git-ignored `output/fiscal_freshness_trial_20261010` 경로에 오프라인 import 후 `offline-integrated` 두 기준일로 실행:
  - **2024-09-01**: 연구용 성장 hit 1, 실제 처리는 2026-10-10이므로 **과거 소급 실행**으로만 기록; 앞선 시점에 이미 알고 있었다고 주장 금지.
  - **2026-10-10**: 기업 2건, 연구용 growth hit **0**, `deferred_research_screens=2`, 신규 후보 등록 **0**. 당시 마지막으로 수집된 회계/산업 자료는 이미 오래되어 임의 양성/음성 상태를 만들지 않는다. `audit-watch-progression` 재실행에서 `SCREEN_WEAKENED=0`, 소급 양성 1건은 prospective 평가에서 제외됨.
  - 로컬 `site/research_kr.html` HTTP GET **200** 확인, 장기 미갱신 플래그 및 `근거 부족으로 스크리닝 보류` 표시, 대장주 확정 **0**.
- 재료는 모두 명시적 **합성 테스트**, 실제 최신 거래소·회계·산업 원본이 아니다. 원본 T5DATA 마켓 파일이나 MarketOS/기존 백테스트 엔진 변경 없음. 외부 API 호출·실전 주문·알림 0건.

## 다음 주요 작업

향후 단계 1 API 연동 시 **실제 공급자별 공시 발표·접수시각과 문서 period_end/수정 이력**을 확보하고, 일별·분기별 데이터 신선도 SLA를 재설계해야 한다. 독립 감사된 역사적 기업 ID·상폐·기업행동·조정가격·미국 생존편향 해소 및 5_5 실제 성숙 라벨의 전향적 검증이 없으므로 아직 공식 대장주 확정·전체 1~6단계 완료 주장은 불가.
