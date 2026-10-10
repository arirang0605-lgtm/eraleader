# EraLeader 실제 개발 체크포인트 — 2_2·2_5 기업행동 수익률 및 종목군 감사

> 2026-10-10 KST. **외부 API/스크래핑 연결 없이 기존 로컬 시세 캐시와 합성 단위시험만 사용**.
> 최종 목표는 미래 주도주 조기 발굴이며, 역사 자료와 백테스트는 이 능력의 검증 수단이다.

## 이번에 추가된 실행 모듈

- `src/eraleader/corporate_returns.py`: 분할비율(신주수/구주수)과 배당금(분할 이후 주당 현금)을 이용해 **비조정(raw) 종가 기반** 관측구간의 주식 수 증가와 현금 배당을 계산. 각 일봉의 **이용 가능 시각(`available_at`)은 필수**이며 판단시각 후에 확정되는 종가를 과거 신호에 사용하는 경우 차단. 주식분할 뒤 가격이 반으로 보이는 경우 가짜 -50%를 방지. `price_basis=raw_unadjusted`를 강제하여 이미 조정된 가격을 다시 보정하는 오류 차단. 단위·음수·NaN·중복·시간대·기준시점/평가시점 미래자료를 확인하고 분할·배당의 거래기준 날짜 반영.
- `src/eraleader/universe_audit.py`: 과거 두 거래일의 **실제 관측 종목 코드**를 비교하여 등장·미관측·거래정지·무거래 종목 현황과 시점 차이를 보고. 미관측 종목을 **자동 상장폐지 판정하지 않음**. 미국 현존 종목군의 역사적 생존편향도 해결되지 않았으므로 별도 인증 필요.
- `src/eraleader/cli.py`: `corporate-return`, `audit-universe` 명령 추가. 기존 정상 경로를 변경하지 않고 확장.
- `tests/test_corporate_returns.py`, `tests/test_universe_audit.py`, `tests/fixtures/corporate_split_dividend_synthetic.json`: 다양한 기업행동/상폐/거래중단·시점·종목군 감사 회귀 테스트.

## PIT 안전 규칙

1. **분할 및 배당**: raw unadjusted 가격만 사용; 같은 날짜 분할과 배당은 배당금을 분할 후 1주 기준으로 해석. 서로 다른 영업일의 종가 수익을 곱하여 누적.
2. **상폐·합병·권리락·스핀오프 등 미지원 구조**: 정산금/실제 현금흐름을 모르면 총수익률을 지어내지 않고 **오류로 차단**.
3. **거래정지·상장종목 누락**: 0% 수익이나 강제 상폐로 대체하지 않음. 사후 관찰 자료의 커버리지·조정가격/비조정가격·원본 실효일 검증까지 별도.
4. **기업행동의 발표시각과 실효일**: 실제 평가일 이후 알게 된 내용은 역사 평가에 주입할 수 없음. 거래소 현지일과 UTC 날짜 경계가 다른 경우에도 영업일 시점이 틀어지지 않도록 회귀 테스트.
5. `corporate_actions_complete`/ `price_sessions_complete`가 외부에서 참으로 입력되더라도 독립 원천 감사를 거치지 않았으므로 결과 `pit_certified=false`.
6. 수익률 계산은 향후 현금흐름·다시 투자 조건에 따라 달라질 수 있으며 역사 유니버스/벤치마크 검증 전 **연구용**이다.

## 실제 실행 명령

```bash
cd /Volumes/T5DATA/eraleader

# 실제 공시가 아닌 명시적 합성/시험용 분할·배당 시나리오
PYTHONPATH=src python3 -m eraleader corporate-return \
  --file tests/fixtures/corporate_split_dividend_synthetic.json \
  --security-id SYN-SPLIT --market KR \
  --decision-at '2024-04-01T16:00:00+09:00' \
  --evaluated-at '2024-04-10T16:00:00+09:00' \
  --price-basis raw_unadjusted --out output/demo_offline

# 실제 SSD marcap 2026-10-02의 관측 종목군 변화 점검 (API 없음)
PYTHONPATH=src python3 -m eraleader audit-universe \
  --as-of 2026-10-02 --days 35 --out output/research_universe_20261002

PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py
```

## 실제 검증 결과

- 이전 54개 자동 테스트에 기업행동·관측종목 감사 19개 추가 → **전체 73개 pytest PASS**.
- 합성 SYN-SPLIT 사례: 2:1 분할 전 100, 분할 뒤 50, 다음날 현금배당 후 49 등 3거래일 합성 관측의 누적 총수익 **0%**. 이 수치는 수식 검증용 가상 데이터이지 실제 주가/성과가 아니다.
- **실제 마캡 관측 자료**: 2026-10-02 종가 기준 2,873 종목 관측, 132 종목의 정지·무거래 상태 플래그, 직전 관측일 대비 새 등장 0/관측 중단 0. 이는 시세 공급자의 관측 코드로 **역사적 상장·상폐 진실 등록부가 아님**.
- 출력: `output/demo_offline/corporate_returns_research.json`, `output/research_universe_20261002/universe_observation_audit.json`. `output/`는 Git 추적 제외.
- 기존 1~6단계 로컬 가격·상태·웹·배치 테스트 유지.

## 다음 개발 미완료 우선순위

**2_2·2_5**: 산업·상장기업/기업행동 원본 PIT 커버리지 감사와 조정가격 계열/가격 소스 교차검증, 상폐 정산금 별도 공급 계약 필요. **5_2·5_4·5_5**: 거래가능성·거래비용·상장폐지 포함 가치검증, 인과 순서 및 워크포워드·봉인 홀드아웃. **6_5**: 자동 일정·오류 재시도/백업·복구를 로컬 환경에서 검증. API는 사용자가 결정한 대로 로컬 기능 구현 후 연결.

전체 30개 세부 ID가 완료됐다고 선언하지 않는다. 합성 데이터로 실제 미래 대장주를 확정하지 않는다.
