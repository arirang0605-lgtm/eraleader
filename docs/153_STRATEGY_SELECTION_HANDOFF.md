# 153 — EraLeader 대장주 선정 → 후속 매매전략 프로젝트 전달 기능

**2026-10-14 · 개발 ID: 4_1·4_2·4_3·4_4·4_5·6_1·6_5 · 운영 원칙 D-027/D-028**

## 역할과 경계

**EraLeader는 종목 발굴·후보 상태 판단·선정 종목 전달까지 담당**한다. 다음 단계인 매매전략 프로젝트는 종목을 전달받은 다음 자체적으로 전략·진입/청산 타이밍·리스크·투자 허용을 결정한다. EraLeader는 주문 API를 실행하거나 계좌·포지션을 변경하지 않는다.

기존 CoreAStock에는 `coreastock.ranking.ranker.Candidate(code, ...)` 등 자체 후보 입력 구조가 있다(외부 프로젝트 READ-ONLY 확인). 미국 MarketOS는 미국 ETF 전용 CORE_V1 경계이므로 EraLeader가 미국 개별 종목을 임의 자동 등록하지 않는다. **어느 소비 프로젝트든 생산된 JSON을 명시적으로 읽도록 별도 어댑터를 연결**해야 하며 해당 프로젝트 코드는 이번 작업에서 변경하지 않았다.

## 추가한 실제 기능

- `src/eraleader/strategy_handoff.py`: **공통 1방향 JSON 계약** `eraleader.strategy_selection_handoff.v1` 구성/원본 시점·정체성·SHA 재검증/원자 파일 발행/중복이면 원본 그대로 재사용/변경이면 별도 파일 요구. `verify_handoff(path,expected_market=...)`로 받은 쪽도 동일 파일을 검증할 수 있다.
- **관찰 종목(WATCH)**: 기존 KRX2+DART 실제 가격·연간 CFS·업종 두 SHA 보고서를 재사용. `research_watchlist`에 종목명/코드/관찰순서/원래 거래일/처음 로컬 수신시각과 연구근거를 제공. `selected_candidates`는 **빈 배열**이며 이를 매매전략 선정 종목으로 잘못 승격하지 않는다.
- **선정 종목**: 기존 4단계 `StateHistory` 원장을 **읽기 전용**으로 조회하여 최근 `POTENTIAL`·`CONFIRMED` 상태만 `selected_candidates`에 전달한다. 원래 종목ID/거래용 코드(ticker)/점수/최초 후보 날짜/원래 판단일/상태·이유/입력 SHA 포함. `WEAKENING`·`PAUSED`·`EXITED`는 기존 선정 목록에서 빠지고 `state_changes`에 이벤트로 보존한다. 중복 같은 날짜는 안전 재사용.
- 선택한 `--identity-ledger`(기존 offline.sqlite)로 영구 주권ID → 당시 거래용 ticker를 조회할 수 있다. 실제 ticker 확인이 안 된 종목은 `ticker=null` 및 `strategy_research_allowed=false`이므로 다음 전략이 그대로 주문 종목으로 오인하면 안 된다.
- `scripts/export_strategy_handoff.py`는 기존 데이터에서 독립 실행하고, 기존 `offline-integrated --strategy-handoff-out /절대경로/파일.json` 옵션은 기존 상태 기록 이후 사용자가 선택한 후속 단계 수신함에 별도 JSON을 발행한다. 기존 옵션 없이 실행하면 전과 동일하다.
- 파일에는 시장 KR/US·원래 관측일·데이터 시점·상태변경·`content_sha256`·`execution_authority=false`·`order_instruction=false`·`research_only=true`를 명시한다. **선정 정보 전달은 주문 명령이나 전략 매수 승인과 완전히 다르다.**

## 사용

실제 보존된 공식 코호트를 **연구 WATCH 전용** JSON으로 내보내는 예시:

```sh
cd /Volumes/T5DATA/eraleader-core-factor-coverage-20261013
PYTHONPATH=src python3 scripts/export_strategy_handoff.py \
  --research-cohort "$PWD/output/same_session_cohort_3fy_20261013" \
  --market KR --as-of 2026-10-14 \
  --out "$PWD/output/strategy_handoff_kr_realuse_20261014.json"
```

실제 4단계 선정 상태가 기록돼 있을 때, 매매전략 전용 수신함으로 보내는 예시:

```sh
PYTHONPATH=src python3 scripts/export_strategy_handoff.py \
  --state-ledger /절대경로/state_history.sqlite \
  --identity-ledger /절대경로/offline.sqlite \
  --market KR --as-of 2026-10-14 \
  --out /절대경로/전략프로젝트_수신함/eraleader_selection_20261014.json
```

수신 프로젝트는 별도 권한/전략 판단 단계에서 JSON을 **읽기 전용으로** 가져온다. `selected_candidates` 중 `ticker_resolved=true`와 `strategy_research_allowed=true`인 코드만 자신의 종목 후보 유니버스에 넣고, WATCH는 사전 관찰로 별도 관리한다. 별도 전략 프로젝트의 후보 필터, 거래 가능성, 위험한도, 브로커/주문 승인은 **전달된 파일로 대체되지 않는다**.

## 실제 실행과 변경 영향 테스트

- **기능 집중 14/14 PASS**: 연구 WATCH vs 선정 상태 구별, KR/US 시장 코드, `POTENTIAL→CONFIRMED→WEAKENING` 선정/제외 이력, 시점·기업ID 매핑, 파일 재실행 멱등성/원본 변조 중단, `offline-integrated` 자동 전달, CLI.
- 관련 기존 state history·PIT 원장·공식 기업화면 포함 **4개 모듈 총 48/48 PASS EXIT0**. 로그는 Git 제외 `output/verification_logs/strategy_handoff_impact_20261014.{xml,log}`.
- 기존 실제 KRX(2026-10-08 거래관측 2,765행 연구 영수증)·DART 3FY/현재 업종(10/13 최초 로컬 수신) **10개사** 기록으로 별도 JSON **첫 발행 EXIT0, 같은 파일 두 번째 실행 ALREADY_DELIVERED EXIT0, 수신측 읽기·SHA PASS**.
- 실물 현재 연구자료는 아직 정식 100점 종합 `POTENTIAL/CONFIRMED`가 없으므로 **전달된 선정 종목 0개 / 관찰 WATCH 10개**. 상태 승격·약화 시험은 *합성 PIT fixture/검증용 원장*이며 실물 대장주 선정 성과는 아님.
- 사용자 원본 main 미커밋 7줄/가격 원시데이터/SharedBrokerAPI·CoreAStock·MarketOS 외부 코드는 변경하지 않음. 시장 API 추가 호출·실주문 0.

## 다음 기능 구현 순서

**(1)** 공식 전체 종목 후보 점수/정식 상태 확보 후 실물 선정 종목 전달, **(2)** CoreAStock 등 구체적인 후속 전략 프로젝트 쪽에 읽기 전용 인입 어댑터를 별도로 연결하여 실제 수신 종목이 자체 전략 후보에 나타나는 E2E 실행, **(3)** 예약 배치에서 날짜별 새 결과 파일 발행 + 선정·약화·교체 업데이트. 순서대로 작은 기능만 구현. 반복 주문방지 시험/외부 자동주문 코드는 EraLeader 범위 밖.
