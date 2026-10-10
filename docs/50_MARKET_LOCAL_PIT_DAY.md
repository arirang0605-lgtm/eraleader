# 2026-10-10 2_3 / 2_2 / 2_5 — 거래소 현지일 PIT 스냅샷 오류 수정

## 실제 버그와 재현

기존 `OfflineLedger.snapshot(as_of, market)`는 공시 자료의 `available_at`을 UTC 절대시간으로 올바르게 필터링했지만, 상장 시작/종료와 기업행동의 `effective_on` 날짜는 **호출자가 입력한 타임스탬프의 달력 날짜**로 비교했다. 예를 들어 `2026-05-01T00:30:00+09:00`는 미국 뉴욕에서는 아직 **2026-04-30 11:30 EDT**다. 이 기준에서 5월 1일 신규 상장이 앞서 들어오거나 기존 기업의 5월 1일 상폐가 하루 일찍 확정되어 **PIT 미래 종목군 누출**을 야기할 수 있었다. 반대로 미국 시간대 문자열로 입력된 한국 5월 2일 00:30 KST 스냅샷에서는 한국 신규 상장이 사라질 수 있었다.

## 최소 수정과 지켜지는 계약

- `src/eraleader/offline_pit.py`: 정규화된 절대시각 `cutoff`을 `KR=Asia/Seoul`, `US=America/New_York`의 IANA 타임존으로 변환하여 `trading_day` 결정. 해당 시장 현지 달력일을 **상장 유효일/상폐/기존 기업행동 유효일 판정에만** 사용. 이는 거래소 휴장일 판정이 아니다.
- 기존 `available_at <= cutoff`의 UTC 시점 비교, append-only DB·원본 자료, action 원본 JSON, 재무 피처/홀드아웃, 스케줄러는 그대로 보존.
- 동일 절대시각의 서로 다른 시간대 문자열은 완전히 같은 스냅샷을 내야 한다. 뉴욕 DST 변경도 고정 UTC 오프셋으로 계산하지 않는다.

## 테스트 및 실측 (합성자료, 원천 공식 인증 아님)

- 새 `tests/test_snapshot_market_clock.py` 5개: 미국 시간대 앞당긴 5월 1일 상장/상폐 PIT 누출 거부, 서울 시간대 상장 지연 누락 수정, 미국 2026-03-08 DST 전/후 2건, timezone-naive 입력 거부.
- **수정 전 실제 재현:** `PYTHONPATH=src python3 -m pytest tests/test_snapshot_market_clock.py -q --tb=short` → 5건 중 4건 실패(서로 동일 절대시각 불변성 및 뉴욕 DST 관련), naive 검사 1건 통과.
- **수정 후 집중 검증:** `PYTHONPATH=src python3 -m pytest tests/test_snapshot_market_clock.py tests/test_offline_pit.py tests/test_fiscal_freshness.py -q --tb=short` → 31건 통과 / 0 실패.
- **전체 회귀:** `PYTHONPATH=src python3 -m pytest tests -q --tb=short` → 전체 실행 exit=0 / 실패 0 (이전 380 + 신규 5, 385건). `python3 scripts/check_handoff.py` → PASS, 고유 30개 개발번호 정상.
- 기존 백테스트 원자료 `/Volumes/T5DATA/CycleOS-Lab_BacktestEngine`는 읽기 전용 보존, 외부 API/실전 공시/주식 데이터 수집하지 않음. 이 변경은 **시점 일관성 버그 수정이지 역사적 PIT 정확성 또는 실전 대장주 발견 성공 증명이 아니다**.

## 남은 핵심 공백

독립 공인 거래소 상장·상폐·기업행동 원천, 재무/산업 실제 발표시점, 공급자 가격 조정·분할·현금 정산, 미국 구성종목 생존편향 제거, 진짜 성숙한 미래 라벨 및 5_5 홀드아웃 강건성. API 연결은 30개 로컬 기능 구현·검증까지 사용자 지시로 보류한다.
